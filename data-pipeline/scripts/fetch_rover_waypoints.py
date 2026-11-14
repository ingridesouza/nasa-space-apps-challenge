"""Baixa o trajeto oficial do Curiosity (MMGIS) e salva localmente --
resolve o item 11 da feature 01. Descoberto em 2026-11-13 inspecionando
as requests de rede de https://science.nasa.gov/mission/msl-curiosity/location-map/
(a mesma técnica de DevTools usada pro CTX, mas aqui o endpoint já é
direto, sem precisar de API intermediária).

Arquivo oficial: https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json
GeoJSON público, sem autenticação, atualizado com a missão (vai do sol
3 até o sol mais recente). Cada feature = 1 parada do rover, com
sol/site/drive/lat/lon/elevação reais.

Uso:
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
    print("Baixando trajeto oficial do Curiosity (MMGIS)...")
    resp = requests.get(WAYPOINTS_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    waypoints = [f["properties"] for f in data["features"]]
    waypoints.sort(key=lambda p: p["sol"])

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(waypoints, f, ensure_ascii=False, indent=2)

    print(f"{len(waypoints)} waypoints (sol {waypoints[0]['sol']} a {waypoints[-1]['sol']})")
    print(f"Salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
