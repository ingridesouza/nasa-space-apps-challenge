"""Popula `rover_images` com fotos reais da Curiosity na campanha de
boxwork (sol ~4560-4660), resolvendo o item 9 da feature 01 -- estava
bloqueado porque a API de fotos não dá posição (`site`/`drive`/`xyz`
vêm `null`).

Solução: a API de fotos dá o `sol` de cada imagem; cruzamos isso com
`data/local/rover_waypoints.json` (gerado por fetch_rover_waypoints.py,
MMGIS oficial) pra pegar a posição REAL do rover naquele sol. Isso é
uma aproximação -- a posição é de onde o rover estava no fim daquele
sol de deslocamento, não necessariamente o ponto exato de onde a foto
foi tirada dentro do sol -- mas é posição real e verificável, não
inventada, e granular o suficiente pra "fotos próximas" (busca por
raio) fazer sentido de verdade.

Uso:
    python db/seed_rover_images.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests

from connection import init_db

WAYPOINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "rover_waypoints.json")
RAW_IMAGES_API = "https://mars.nasa.gov/api/v1/raw_image_items/"

# sóis da campanha de boxwork (ver PROXIMOS-PASSOS.md) -- cobre o
# período dos 3 alvos científicos já cadastrados.
SOL_RANGE = range(4560, 4661)
IMAGENS_POR_SOL = 4
LIMITE_TOTAL = 200

CAMERA_LABEL = {
    "MAST_LEFT": "Mastcam Left",
    "MAST_RIGHT": "Mastcam Right",
    "NAV_LEFT_B": "Navcam Left",
    "NAV_RIGHT_B": "Navcam Right",
    "MAHLI": "MAHLI",
    "FHAZ_LEFT_B": "Front Hazcam Left",
    "FHAZ_RIGHT_B": "Front Hazcam Right",
    "RHAZ_LEFT_B": "Rear Hazcam Left",
    "RHAZ_RIGHT_B": "Rear Hazcam Right",
}


def nearest_waypoint(waypoints: list[dict], sol: int) -> dict:
    return min(waypoints, key=lambda w: abs(w["sol"] - sol))


def fetch_sol_images(sol: int, limit: int) -> list[dict]:
    resp = requests.get(
        RAW_IMAGES_API,
        params={
            "order": "date_taken desc",
            "per_page": str(limit),
            "page": "0",
            "condition_1": "msl:mission",
            "condition_2": f"{sol}:sol",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def main() -> None:
    if not os.path.isfile(WAYPOINTS_PATH):
        raise SystemExit("rode primeiro: python scripts/fetch_rover_waypoints.py")

    with open(WAYPOINTS_PATH, encoding="utf-8") as f:
        waypoints = json.load(f)

    conn = init_db()
    # idempotente: limpa tudo que já existe antes de repopular.
    conn.execute("DELETE FROM rover_images_rtree")
    conn.execute("DELETE FROM rover_images")

    total = 0
    for sol in SOL_RANGE:
        if total >= LIMITE_TOTAL:
            break
        try:
            imagens = fetch_sol_images(sol, IMAGENS_POR_SOL)
        except requests.RequestException as e:
            print(f"sol {sol}: falhou ({e})")
            continue

        if not imagens:
            continue

        wp = nearest_waypoint(waypoints, sol)

        for img in imagens:
            cursor = conn.execute(
                """
                INSERT INTO rover_images (lat, lon, sol, site, drive, camera, heading, local_path, thumbnail_path, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wp["lat"],
                    wp["lon"],
                    img["sol"],
                    wp.get("site"),
                    wp.get("drive"),
                    CAMERA_LABEL.get(img.get("instrument"), img.get("instrument")),
                    wp.get("yaw"),
                    img.get("https_url") or img.get("url"),
                    img.get("https_url") or img.get("url"),
                    img.get("date_taken"),
                ),
            )
            img_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO rover_images_rtree (id, min_lon, max_lon, min_lat, max_lat) VALUES (?, ?, ?, ?, ?)",
                (img_id, wp["lon"], wp["lon"], wp["lat"], wp["lat"]),
            )
            total += 1
            if total >= LIMITE_TOTAL:
                break

        print(f"sol {sol}: +{len(imagens)} fotos (posição do waypoint sol {wp['sol']}) -- total {total}")

    conn.commit()
    conn.close()
    print(f"\n{total} fotos reais inseridas em rover_images.")


if __name__ == "__main__":
    main()
