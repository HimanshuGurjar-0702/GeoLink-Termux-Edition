import json
import subprocess
from datetime import datetime, timezone


def get_location():
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
            raise RuntimeError(result.stderr.strip() or "GPS command failed")

        data = json.loads(result.stdout)

        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))

        if not (-90 <= latitude <= 90):
            raise ValueError("Invalid latitude")

        if not (-180 <= longitude <= 180):
            raise ValueError("Invalid longitude")

        return {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except subprocess.TimeoutExpired:
        raise RuntimeError("GPS timeout")

    except (ValueError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid GPS response: {error}")


if __name__ == "__main__":
    print(get_location())
