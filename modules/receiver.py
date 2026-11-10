
import os
import json
import time
import secrets
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, request, jsonify

from modules.authentication import (
    create_pairing_credentials,
    verify_pairing_code,
    verify_access_token
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4096

DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "locations.json")

lock = Lock()

credentials = None
paired_token = None
pair_attempts = 0
latest_location = None

MAX_HISTORY = 500


def save_location(location):
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        with open(HISTORY_FILE, "r") as file:
            history = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    history.append(location)
    history = history[-MAX_HISTORY:]

    temporary_file = HISTORY_FILE + ".tmp"

    with open(temporary_file, "w") as file:
        json.dump(history, file, indent=2)

    os.replace(temporary_file, HISTORY_FILE)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "GeoLink",
        "version": "1.0.0"
    })


@app.route("/pair", methods=["POST"])
def pair():
    global paired_token, pair_attempts

    data = request.get_json(silent=True) or {}
    candidate = data.get("pairing_code")

    with lock:
        if credentials is None:
            return jsonify({"error": "Pairing unavailable"}), 503

        if paired_token is not None:
            return jsonify({"error": "Device already paired"}), 403

        if pair_attempts >= 5:
            return jsonify({"error": "Pairing locked"}), 429

        pair_attempts += 1

        valid = verify_pairing_code(
            candidate,
            credentials["pairing_code"],
            credentials["expires_at"]
        )

        if not valid:
            return jsonify({"error": "Invalid or expired code"}), 401

        paired_token = credentials["access_token"]
        credentials = None

        return jsonify({
            "status": "paired",
            "access_token": paired_token
        })


@app.route("/location", methods=["POST"])
def receive_location():
    global latest_location

    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()

    with lock:
        if paired_token is None or not verify_access_token(
            token, paired_token
        ):
            return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))

        if not (-90 <= latitude <= 90):
            raise ValueError()

        if not (-180 <= longitude <= 180):
            raise ValueError()

        if not (0 <= accuracy <= 100000):
            raise ValueError()

    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid GPS data"}), 400

    location = {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "received_at": datetime.now(
            timezone.utc
        ).isoformat()
    }

    try:
        save_location(location)
    except OSError:
        return jsonify({"error": "Storage error"}), 500

    with lock:
        latest_location = location

    print("\n[+] New GPS update received")
    print("Latitude :", latitude)
    print("Longitude:", longitude)
    print("Accuracy :", accuracy, "meters")
    print("Time     :", location["received_at"])

    return jsonify({"status": "received"}), 200


@app.route("/latest", methods=["GET"])
def get_latest():
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()

    with lock:
        if paired_token is None or not verify_access_token(
            token, paired_token
        ):
            return jsonify({"error": "Unauthorized"}), 401

        if latest_location is None:
            return jsonify({"status": "waiting"}), 200

        return jsonify(latest_location)


def run():
    global credentials, paired_token, pair_attempts

    os.makedirs(DATA_DIR, exist_ok=True)

    credentials = create_pairing_credentials()
    paired_token = None
    pair_attempts = 0

    print("\n================================")
    print("       GEOLINK RECEIVER")
    print("================================")
    print("\nPairing code:")
    print(credentials["pairing_code"])
    print("\nCode expires in 10 minutes.")
    print("Waiting for authorized sender...")
    print("\nServer: http://127.0.0.1:5000")
    print("Press CTRL+C to stop.\n")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )


if __name__ == "__main__":
    run()
