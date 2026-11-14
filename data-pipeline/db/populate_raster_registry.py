"""Popula `raster_registry` com as camadas já confirmadas (ver
PROXIMOS-PASSOS.md) e seus arquivos locais já baixados.

Uso:
    python db/populate_raster_registry.py

Idempotente: usa INSERT OR REPLACE, pode rodar de novo a qualquer hora
(ex. depois de baixar o recorte final do boxwork).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml

from adapters.mars_trek_wmts import MarsTrekWMTSAdapter
from connection import init_db

TILES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")

TILE_FILENAME_RE = re.compile(r"^(\w+)_(\d+)_(\d+)\.png$")


def _bbox_real_tiles_wmts(layer_name: str, folder: str) -> tuple[float, float, float, float] | None:
    """Recalcula o bbox REAL coberto pelos tiles já baixados (não o
    bbox pedido na hora do fetch -- ver tile_range_to_bbox em
    adapters/mars_trek_wmts.py pro porquê: tile é quantizado à grade do
    WMTS, bbox pedido != bbox realmente coberto, e CTX/HiRISE quantizam
    diferente -- causava desalinhamento real entre as camadas no mapa).
    Só precisa reconsultar o GetCapabilities (leve), não rebaixar tile
    nenhum -- lê o tile_matrix/row/col de volta do nome dos arquivos
    já salvos em disco."""
    if not os.path.isdir(folder):
        return None

    tile_matrix = None
    rows, cols = [], []
    for nome in os.listdir(folder):
        m = TILE_FILENAME_RE.match(nome)
        if not m:
            continue
        tile_matrix = m.group(1)
        rows.append(int(m.group(2)))
        cols.append(int(m.group(3)))

    if tile_matrix is None:
        return None

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    layer_cfg = config["layers"][layer_name]

    adapter = MarsTrekWMTSAdapter(product_id=layer_cfg["product_id"], region=layer_cfg["region"])
    caps = adapter.get_capabilities()
    matrix = caps["matrices"][tile_matrix]

    bbox = adapter.tile_range_to_bbox(min(rows), max(rows), min(cols), max(cols), matrix)
    return bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat

# bbox REAL da campanha de boxwork (sol ~4500-4684), confirmado em
# 2026-11-13 via MSL_waypoints.json (MMGIS oficial) -- ver
# PROXIMOS-PASSOS.md. Substitui o chute inicial perto do pouso, que
# ficava 13.3km da posição real do rover durante a campanha.
BBOX_TESTE = (137.3586, -4.8263, 137.4094, -4.7757)

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
        bbox_camada = (min_lon, min_lat, max_lon, max_lat)
        status = "OK" if existe else "AVISO: arquivo/pasta não existe ainda"

        if camada["tipo_acesso"] == "tiles_wmts" and existe:
            try:
                real = _bbox_real_tiles_wmts(camada["layer_name"], camada["local_tile_path"])
                if real is not None:
                    bbox_camada = real
                    status += " (bbox real recalculado a partir dos tiles)"
            except Exception as e:
                status += f" (AVISO: não recalculei bbox real, usando o pedido -- {e})"

        conn.execute(
            """
            INSERT OR REPLACE INTO raster_registry
                (layer_name, local_tile_path, min_lon, min_lat, max_lon, max_lat, categoria, tipo_acesso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camada["layer_name"],
                camada["local_tile_path"],
                *bbox_camada,
                camada["categoria"],
                camada["tipo_acesso"],
            ),
        )
        print(f"{camada['layer_name']}: {status}")

    conn.commit()
    conn.close()
    print("\nraster_registry atualizado.")


if __name__ == "__main__":
    main()
