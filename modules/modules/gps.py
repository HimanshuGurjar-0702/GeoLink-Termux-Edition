
import json
import subprocess
from datetime import datetime, timezone


def get_location():
    """
    Read the current device's GPS location
    using Termux:API.
    """

    try:
        result = subprocess.run(
            [
                "termux-location",
                "-p", "gps",
                "-r", "once"
            ],
            capture_output=True,
            text=True,
            timeout=40
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or "GPS request failed"
            )

        location = json.loads(result.stdout)

        latitude = float(location["latitude"])
        longitude = float(location["longitude"])

        if not (-90 <= latitude <= 90):
            raise ValueError("Invalid latitude")

        if not (-180 <= longitude <= 180):
            raise ValueError("Invalid longitude")

        return {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": location.get("accuracy"),
            "provider": location.get("provider", "gps"),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }

    except FileNotFoundError:
        raise RuntimeError(
            "Termux:API command not found. "
            "Install Termux:API and its package."
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "GPS timeout. Check location services."
        )

    except (json.JSONDecodeError, KeyError, ValueError):
        raise RuntimeError(
            "Invalid GPS response. Check GPS permission."
        )


if __name__ == "__main__":
    print("\nGeoLink GPS Test")
    print("----------------")

    try:
        data = get_location()

        print("GPS Status: Connected")
        print("Latitude:", data["latitude"])
        print("Longitude:", data["longitude"])
        print("Accuracy:", data["accuracy"])
        print("Provider:", data["provider"])
        print("Timestamp:", data["timestamp"])

    except RuntimeError as error:
        print("\nGPS Error:", error)
