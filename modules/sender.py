import os
import json
import time
import subprocess
import requests

from modules.gps import get_location


INTERVAL = 10
DATA_DIR = "data"
SESSION_FILE = os.path.join(DATA_DIR, "sender_session.json")


def get_battery_percentage():
    try:
        result = subprocess.run(
            ["termux-battery-status"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        percentage = int(data["percentage"])

        if 0 <= percentage <= 100:
            return percentage

    except Exception:
        pass

    return None


def load_session(receiver_url):
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get("receiver_url") == receiver_url:
            return data.get("access_token")

    except (OSError, json.JSONDecodeError):
        pass

    return None


def save_session(receiver_url, token):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(SESSION_FILE, "w", encoding="utf-8") as file:
        json.dump({
            "receiver_url": receiver_url,
            "access_token": token
        }, file)

    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def pair_receiver(session, receiver_url):
    code = input("Enter receiver pairing code: ").strip()

    response = session.post(
        receiver_url + "/pair",
        json={"pairing_code": code},
        timeout=15
    )

    response.raise_for_status()

    token = response.json().get("access_token")

    if not token:
        raise RuntimeError("Receiver did not return an access token")

    save_session(receiver_url, token)
    return token


def send_with_retry(session, url, payload, headers):
    for attempt in range(3):
        try:
            response = session.post(
                url,
                json=payload,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            return True

        except requests.RequestException as error:
            print(f"Connection attempt {attempt + 1}/3 failed: {error}")

            if attempt < 2:
                time.sleep(2)

    return False


def run():
    print("\n================================")
    print("        GeoLink Sender v2")
    print("================================")

    receiver_url = input(
        "Receiver HTTPS URL: "
    ).strip().rstrip("/")

    if not receiver_url.startswith("https://"):
        print("HTTPS URL is required.")
        return

    session = requests.Session()

    try:
        response = session.get(
            receiver_url + "/health",
            timeout=15
        )
        response.raise_for_status()

        if response.json().get("service") != "GeoLink":
            print("Invalid GeoLink receiver.")
            return

    except requests.RequestException as error:
        print("Receiver unavailable:", error)
        return

    token = load_session(receiver_url)

    if token:
        print("Saved pairing session found.")
    else:
        try:
            token = pair_receiver(session, receiver_url)
            print("Pairing successful.")
        except (requests.RequestException, ValueError, RuntimeError) as error:
            print("Pairing failed:", error)
            return

    consent = input(
        "\nShare this phone's GPS location? (yes/no): "
    ).strip().lower()

    if consent != "yes":
        print("Sharing was not started.")
        return

    headers = {
        "Authorization": "Bearer " + token
    }

    try:
        response = session.post(
            receiver_url + "/control/start",
            headers=headers,
            timeout=15
        )
        response.raise_for_status()

    except requests.RequestException as error:
        print("Could not start receiver session:", error)
        return

    dashboard_url = receiver_url + "/dashboard#token=" + token

    print("\nLocation sharing started.")
    print("Update interval: 10 seconds")
    print("Dashboard URL:")
    print(dashboard_url)
    print("\nPress CTRL+C to stop locally.")

    try:
        while True:
            cycle_start = time.monotonic()

            # Check whether Receiver has remotely stopped sharing.
            try:
                control = session.get(
                    receiver_url + "/control",
                    headers=headers,
                    timeout=10
                )
                control.raise_for_status()

                if not control.json().get("sharing_enabled", False):
                    print("Receiver stopped location sharing.")
                    break

            except requests.RequestException as error:
                print("Receiver connection unavailable:", error)
                print("Will retry during the next cycle.")

                time.sleep(INTERVAL)
                continue

            try:
                location = get_location()
                location["battery_percentage"] = get_battery_percentage()

                success = send_with_retry(
                    session,
                    receiver_url + "/location",
                    location,
                    headers
                )

                if success:
                    battery = location["battery_percentage"]
                    battery_text = (
                        f"{battery}%" if battery is not None else "Unavailable"
                    )

                    print(
                        f"GPS: {location['latitude']}, "
                        f"{location['longitude']} | "
                        f"Battery: {battery_text}"
                    )

                else:
                    print("Location update could not be delivered.")

            except RuntimeError as error:
                print("GPS error:", error)

            elapsed = time.monotonic() - cycle_start
            time.sleep(max(0, INTERVAL - elapsed))

    except KeyboardInterrupt:
        print("\nSharing stopped locally.")

    finally:
        session.close()
