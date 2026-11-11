"""Popula `raster_registry` com as camadas já confirmadas (ver
PROXIMOS-PASSOS.md) e seus arquivos locais já baixados.

Uso:
    python db/populate_raster_registry.py

Idempotente: usa INSERT OR REPLACE, pode rodar de novo a qualquer hora
(ex. depois de baixar o recorte final do boxwork).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connection import init_db

TILES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles")

# bbox de teste usado em todos os fetch_*_test.py até agora -- ver
# PROXIMOS-PASSOS.md. Troca quando o recorte final do boxwork sair.
BBOX_TESTE = (137.40, -4.61, 137.48, -4.57)

CAMADAS = [
    {
        "layer_name": "dtm_hirise_1m",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m", "dem_512x512.tif"),
        "categoria": "topografica",
        "tipo_acesso": "raster_unico",
    },
    {
        "layer_name": "mola_topografia_regional",
        "local_tile_path": os.path.join(TILES_DIR, "mola_topografia_regional", "dem_128x128.tif"),
        "categoria": "topografica",
        "tipo_acesso": "raster_unico",
    },
    {
        "layer_name": "ctx_optica",
        "local_tile_path": os.path.join(TILES_DIR, "ctx_optica"),
        "categoria": "optica",
        "tipo_acesso": "tiles_wmts",
    },
    {
        "layer_name": "hirise_optica",
        "local_tile_path": os.path.join(TILES_DIR, "hirise_optica"),
        "categoria": "optica",
        "tipo_acesso": "tiles_wmts",
    },
    {
        "layer_name": "themis_termica",
        "local_tile_path": os.path.join(TILES_DIR, "themis_termica"),
        "categoria": "termica",
        "tipo_acesso": "tiles_wmts",
    },
    {
        # Camada visual derivada do DTM -- não é mais um arquivo baixado
        # do Mars Trek, é gerado sob demanda por api/mosaics.py
        # (build_hillshade_png) a partir do local_tile_path abaixo.
        "layer_name": "relevo_hillshade",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m", "dem_512x512.tif"),
        "categoria": "topografica",
        "tipo_acesso": "hillshade_derivado",
    },
]


def main() -> None:
    conn = init_db()
    min_lon, min_lat, max_lon, max_lat = BBOX_TESTE

    for camada in CAMADAS:
        existe = os.path.exists(camada["local_tile_path"])
        conn.execute(
            """
            INSERT OR REPLACE INTO raster_registry
                (layer_name, local_tile_path, min_lon, min_lat, max_lon, max_lat, categoria, tipo_acesso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camada["layer_name"],
                camada["local_tile_path"],
                min_lon,
                min_lat,
                max_lon,
                max_lat,
                camada["categoria"],
                camada["tipo_acesso"],
            ),
        )
        status = "OK" if existe else "AVISO: arquivo/pasta não existe ainda"
        print(f"{camada['layer_name']}: {status}")

    conn.commit()
    conn.close()
    print("\nraster_registry atualizado.")


if __name__ == "__main__":
    main()
