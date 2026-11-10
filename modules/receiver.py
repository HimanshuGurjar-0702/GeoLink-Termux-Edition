import os
import json
import math
import time
import threading

from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

from modules.authentication import (
    create_pairing_credentials,
    verify_pairing_code,
    verify_access_token
)

app = Flask(__name__)

DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "locations.json")

lock = threading.Lock()

credentials = None
paired_token = None
pair_attempts = 0
sharing_enabled = False
latest_location = None


def read_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def write_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)

    temporary_file = HISTORY_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)

    os.replace(temporary_file, HISTORY_FILE)


def distance_between(lat1, lon1, lat2, lon2):
    radius = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return radius * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


def timestamp_seconds(value):
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()

    except (ValueError, AttributeError):
        return time.time()


def authorized():
    global paired_token

    header = request.headers.get("Authorization", "")

    if not header.startswith("Bearer "):
        return False

    return verify_access_token(
        header[7:],
        paired_token
    )


@app.route("/health")
def health():
    return jsonify({
        "service": "GeoLink",
        "version": "2.0.0",
        "status": "online"
    })


@app.route("/pair", methods=["POST"])
def pair():
    global credentials, paired_token, pair_attempts, sharing_enabled

    data = request.get_json(silent=True) or {}
    code = data.get("pairing_code", "")

    with lock:
        if credentials is None:
            return jsonify({"error": "Pairing unavailable"}), 403

        if paired_token is not None:
            return jsonify({"error": "Already paired"}), 403

        if pair_attempts >= 5:
            return jsonify({"error": "Too many attempts"}), 429

        pair_attempts += 1

        if not verify_pairing_code(
            code,
            credentials["pairing_code"],
            credentials["expires_at"]
        ):
            return jsonify({"error": "Invalid or expired code"}), 401

        paired_token = credentials["access_token"]
        credentials = None
        sharing_enabled = False

    print("\nSender successfully paired.")

    return jsonify({
        "status": "paired",
        "message": "Authentication successful",
        "access_token": paired_token
    })


@app.route("/control", methods=["GET"])
def control():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "sharing_enabled": sharing_enabled
    })


@app.route("/control/start", methods=["POST"])
def start_sharing():
    global sharing_enabled

    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    sharing_enabled = True

    return jsonify({
        "status": "started",
        "sharing_enabled": True
    })


@app.route("/control/stop", methods=["POST"])
def stop_sharing():
    global sharing_enabled

    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    sharing_enabled = False

    print("\nRemote STOP requested by Receiver dashboard.")

    return jsonify({
        "status": "stopped",
        "sharing_enabled": False
    })


@app.route("/location", methods=["POST"])
def receive_location():
    global latest_location

    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    if not sharing_enabled:
        return jsonify({"error": "Sharing is stopped"}), 403

    data = request.get_json(silent=True) or {}

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy", 0))

        battery = data.get("battery_percentage")

        if battery is not None:
            battery = int(battery)
            if not 0 <= battery <= 100:
                raise ValueError("Invalid battery percentage")

        if not -90 <= latitude <= 90:
            raise ValueError("Invalid latitude")

        if not -180 <= longitude <= 180:
            raise ValueError("Invalid longitude")

        if not 0 <= accuracy <= 100000:
            raise ValueError("Invalid accuracy")

    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid location data"}), 400

    timestamp = str(
        data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    )

    location = {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "battery_percentage": battery,
        "timestamp": timestamp,
        "speed_kmh": 0,
        "distance_increment_km": 0
    }

    with lock:
        history = read_history()

        if history:
            previous = history[-1]

            previous_time = timestamp_seconds(previous["timestamp"])
            current_time = timestamp_seconds(timestamp)
            elapsed = current_time - previous_time

            if elapsed > 0:
                distance = distance_between(
                    previous["latitude"],
                    previous["longitude"],
                    latitude,
                    longitude
                )

                speed = distance / (elapsed / 3600)

                # Avoid recording implausible GPS jumps as real movement.
                if speed <= 300:
                    location["speed_kmh"] = round(speed, 2)
                    location["distance_increment_km"] = round(distance, 5)

        history.append(location)
        history = history[-5000:]

        write_history(history)
        latest_location = location

    print(
        f"\nLocation: {latitude}, {longitude} | "
        f"Speed: {location['speed_kmh']} km/h"
    )

    return jsonify({"status": "received"})


@app.route("/latest")
def latest():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    with lock:
        current = latest_location

    if current is None:
        return jsonify({"status": "waiting"})

    return jsonify(current)


@app.route("/history")
def history_api():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    with lock:
        history = read_history()

    return jsonify(history)


@app.route("/stats")
def stats():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    with lock:
        history = read_history()

    if not history:
        return jsonify({
            "distance_km": 0,
            "current_speed_kmh": 0,
            "average_speed_kmh": 0,
            "battery_percentage": None,
            "points": 0
        })

    distance = sum(
        float(item.get("distance_increment_km", 0))
        for item in history
    )

    first_time = timestamp_seconds(history[0]["timestamp"])
    last_time = timestamp_seconds(history[-1]["timestamp"])

    elapsed_hours = max(0, (last_time - first_time) / 3600)

    average_speed = (
        distance / elapsed_hours if elapsed_hours > 0 else 0
    )

    last = history[-1]

    return jsonify({
        "distance_km": round(distance, 3),
        "current_speed_kmh": last.get("speed_kmh", 0),
        "average_speed_kmh": round(average_speed, 2),
        "battery_percentage": last.get("battery_percentage"),
        "points": len(history)
    })


@app.route("/dashboard")
def dashboard():
    page = r"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GeoLink v2 Dashboard</title>
<link rel="stylesheet"
 href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    background: #101820;
    color: #edf3f7;
    font-family: Arial, sans-serif;
}
header {
    padding: 16px;
    background: #182632;
}
header h2 { margin: 0; }
main { padding: 12px; }
.cards {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
}
.card {
    background: #1b2b38;
    padding: 14px;
    border-radius: 12px;
    min-width: 0;
}
.value {
    font-size: 22px;
    font-weight: bold;
    margin-top: 8px;
}
.label { color: #a8bbc8; font-size: 13px; }
#map {
    height: 48vh;
    min-height: 280px;
    margin-top: 12px;
    border-radius: 12px;
}
button {
    border: 0;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 4px 8px 0;
    font-weight: bold;
}
.stop { background: #e34b4b; color: white; }
.refresh { background: #3b82f6; color: white; }
#status { color: #a8bbc8; margin: 10px 0; }
#history p {
    padding: 10px;
    background: #1b2b38;
    border-radius: 8px;
    overflow-wrap: anywhere;
    font-size: 13px;
}
</style>
</head>
<body>
<header>
<h2>GeoLink v2.0</h2>
<p>Live Location Dashboard</p>
</header>

<main>
<div class="cards">
 <div class="card">
  <div class="label">Current Speed</div>
  <div class="value" id="speed">0 km/h</div>
 </div>
 <div class="card">
  <div class="label">Average Speed</div>
  <div class="value" id="average">0 km/h</div>
 </div>
 <div class="card">
  <div class="label">Distance Travelled</div>
  <div class="value" id="distance">0 km</div>
 </div>
 <div class="card">
  <div class="label">Sender Battery</div>
  <div class="value" id="battery">--</div>
 </div>
</div>

<div id="map"></div>
<p id="status">Connecting...</p>

<button class="refresh" onclick="refreshAll()">Refresh</button>
<button class="stop" onclick="stopSharing()">STOP SHARING</button>

<h3>Location History</h3>
<div id="history"></div>
</main>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const token = new URLSearchParams(location.hash.slice(1)).get("token");

const map = L.map("map").setView([20, 78], 5);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

let marker = null;
let route = L.polyline([], {color: "#2196f3"}).addTo(map);
let firstView = true;

async function api(path, method = "GET") {
    if (!token) throw new Error("Missing dashboard token");

    const response = await fetch(path, {
        method,
        headers: {
            "Authorization": "Bearer " + token
        }
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

async function refreshAll() {
    try {
        const [latest, stats, history, control] = await Promise.all([
            api("/latest"),
            api("/stats"),
            api("/history"),
            api("/control")
        ]);

        if (latest.status === "waiting") {
            document.getElementById("status").textContent =
                "Waiting for first GPS update...";
            return;
        }

        const point = [latest.latitude, latest.longitude];

        if (!marker) {
            marker = L.marker(point).addTo(map);
        } else {
            marker.setLatLng(point);
        }

        const points = history.map(item => [
            item.latitude, item.longitude
        ]);

        route.setLatLngs(points);

        if (firstView) {
            map.fitBounds(route.getBounds(), {padding: [20, 20]});
            firstView = false;
        }

        document.getElementById("speed").textContent =
            stats.current_speed_kmh + " km/h";

        document.getElementById("average").textContent =
            stats.average_speed_kmh + " km/h";

        document.getElementById("distance").textContent =
            stats.distance_km + " km";

        document.getElementById("battery").textContent =
            stats.battery_percentage === null
            ? "Unavailable"
            : stats.battery_percentage + "%";

        document.getElementById("status").textContent =
            control.sharing_enabled
            ? "Sharing active | Accuracy: " + latest.accuracy + " m"
            : "Sharing stopped";

        const box = document.getElementById("history");
        box.replaceChildren();

        history.slice().reverse().slice(0, 30).forEach(item => {
            const p = document.createElement("p");
            p.textContent =
                item.timestamp + " | " +
                item.latitude + ", " + item.longitude +
                " | " + item.speed_kmh + " km/h";
            box.appendChild(p);
        });

    } catch (error) {
        document.getElementById("status").textContent = error.message;
    }
}

async function stopSharing() {
    if (!confirm("Stop location sharing on the Sender?")) return;

    try {
        await api("/control/stop", "POST");
        document.getElementById("status").textContent =
            "STOP sent. Sender will stop on its next control check.";
        refreshAll();
    } catch (error) {
        alert(error.message);
    }
}

refreshAll();
setInterval(refreshAll, 10000);
</script>
</body>
</html>
"""
    return Response(page, mimetype="text/html")


def run():
    global credentials, paired_token, pair_attempts
    global sharing_enabled, latest_location

    os.makedirs(DATA_DIR, exist_ok=True)

    credentials = create_pairing_credentials()
    paired_token = None
    pair_attempts = 0
    sharing_enabled = False

    history = read_history()
    latest_location = history[-1] if history else None

    print("\n================================")
    print("      GeoLink Receiver v2")
    print("================================")
    print("Pairing code:", credentials["pairing_code"])
    print("Code expires in 10 minutes.")
    print("Server: http://127.0.0.1:5000")
    print("Dashboard: /dashboard")
    print("\nStart your Cloudflare tunnel separately.")
    print("Press CTRL+C to stop the receiver.")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )


if __name__ == "__main__":
    run()
