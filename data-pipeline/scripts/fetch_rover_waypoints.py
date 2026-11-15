"""Downloads Curiosity's official traverse (MMGIS) and saves it locally --
resolves item 11 of feature 01. Discovered on 2026-11-13 by inspecting
the network requests of https://science.nasa.gov/mission/msl-curiosity/location-map/
(the same DevTools technique used for CTX, but here the endpoint is
direct, with no intermediate API).

Official file: https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json
Public GeoJSON, no authentication, updated with the mission (from sol
3 to the latest sol). Each feature = 1 rover stop, with real
sol/site/drive/lat/lon/elevation.

Usage:
    python scripts/fetch_rover_waypoints.py
"""

import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import requests

WAYPOINTS_URL = "https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "rover_waypoints.json")


def main() -> None:
    print("Downloading Curiosity's official traverse (MMGIS)...")
    resp = requests.get(WAYPOINTS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    waypoints = [f["properties"] for f in data["features"]]
    waypoints.sort(key=lambda p: p["sol"])

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(waypoints, f, ensure_ascii=False, indent=2)

    print(f"{len(waypoints)} waypoints (sol {waypoints[0]['sol']} to {waypoints[-1]['sol']})")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
