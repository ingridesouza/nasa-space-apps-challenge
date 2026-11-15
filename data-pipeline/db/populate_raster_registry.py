"""Populates `raster_registry` with the confirmed layers (see
NEXT-STEPS.md) and their already-downloaded local files.

Usage:
    python db/populate_raster_registry.py

Idempotent: uses INSERT OR REPLACE, it can run again at any time
(e.g. after downloading the final boxwork crop).
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


def _real_bbox_tiles_wmts(layer_name: str, folder: str) -> tuple[float, float, float, float] | None:
    """Recomputes the REAL bbox covered by the already-downloaded tiles (not the
    bbox requested at fetch time -- see tile_range_to_bbox in
    adapters/mars_trek_wmts.py for why: a tile is quantized to the
    WMTS grid, requested bbox != bbox actually covered, and CTX/HiRISE quantize
    differently -- it caused a real misalignment between the layers on the map).
    It only needs to re-query GetCapabilities (light), not re-download any
    tile -- it reads tile_matrix/row/col back from the names of the files
    already saved on disk."""
    if not os.path.isdir(folder):
        return None

    tile_matrix = None
    rows, cols = [], []
    for name in os.listdir(folder):
        m = TILE_FILENAME_RE.match(name)
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

# REAL bbox of the boxwork campaign (sol ~4500-4684), confirmed on
# 2026-11-13 via MSL_waypoints.json (official MMGIS) -- see
# NEXT-STEPS.md. Replaces the initial guess near the landing site, which
# was 13.3km from the rover's real position during the campaign.
TEST_BBOX = (137.3586, -4.8263, 137.4094, -4.7757)

LAYERS = [
    {
        "layer_name": "dtm_hirise_1m",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m", "dem_512x512.tif"),
        "category": "topographic",
        "access_type": "single_raster",
    },
    {
        "layer_name": "mola_regional_topography",
        "local_tile_path": os.path.join(TILES_DIR, "mola_regional_topography", "dem_256x256.tif"),
        "category": "topographic",
        "access_type": "single_raster",
    },
    {
        "layer_name": "ctx_optical",
        "local_tile_path": os.path.join(TILES_DIR, "ctx_optical"),
        "category": "optical",
        "access_type": "tiles_wmts",
    },
    {
        "layer_name": "hirise_optical",
        "local_tile_path": os.path.join(TILES_DIR, "hirise_optical"),
        "category": "optical",
        "access_type": "tiles_wmts",
    },
    {
        "layer_name": "themis_thermal",
        "local_tile_path": os.path.join(TILES_DIR, "themis_thermal"),
        "category": "thermal",
        "access_type": "tiles_wmts",
    },
    {
        # Visual layer derived from the DTM -- it is no longer a file downloaded
        # from Mars Trek, it is generated on demand by api/mosaics.py
        # (build_hillshade_png) from the local_tile_path below.
        "layer_name": "relief_hillshade",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m", "dem_512x512.tif"),
        "category": "topographic",
        "access_type": "derived_hillshade",
    },
    {
        # Feature 06: historical chance (rover stops) that the real terrain exceeds
        # 15°, painted per pixel from the same DTM -- api/forecast.py
        "layer_name": "predicted_risk",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m", "dem_512x512.tif"),
        "category": "topographic",
        "access_type": "derived_risk",
    },
    {
        # Quantitative THEMIS thermal inertia (scripts/fetch_themis_ti.py) --
        # real value per 100 m cell; bbox = real extent of the GeoTIFF
        "layer_name": "themis_ti",
        "local_tile_path": os.path.join(TILES_DIR, "themis_ti", "ti_100m.tif"),
        "category": "thermal",
        "access_type": "thermal_scalar",
    },
    {
        # Direct insolation and shade per sol/hour (api/insolation.py), inferred from the
        # native 1 m DTM + regional MOLA (scripts/fetch_insolation_relief.py)
        "layer_name": "insolation",
        "local_tile_path": os.path.join(TILES_DIR, "dtm_hirise_1m_native", "dem_3011x2999.tif"),
        "category": "atmospheric",
        "access_type": "derived_insolation",
    },
]


def main() -> None:
    conn = init_db()
    min_lon, min_lat, max_lon, max_lat = TEST_BBOX

    for layer in LAYERS:
        exists = os.path.exists(layer["local_tile_path"])
        layer_bbox = (min_lon, min_lat, max_lon, max_lat)
        status = "OK" if exists else "WARNING: file/folder does not exist yet"

        if layer["access_type"] == "tiles_wmts" and exists:
            try:
                real = _real_bbox_tiles_wmts(layer["layer_name"], layer["local_tile_path"])
                if real is not None:
                    layer_bbox = real
                    status += " (real bbox recomputed from the tiles)"
            except Exception as e:
                status += f" (WARNING: did not recompute the real bbox, using the requested one -- {e})"

        if layer["access_type"] == "thermal_scalar" and exists:
            import rasterio

            with rasterio.open(layer["local_tile_path"]) as ds:
                layer_bbox = (ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top)
            status += " (real bbox of the GeoTIFF)"

        conn.execute(
            """
            INSERT OR REPLACE INTO raster_registry
                (layer_name, local_tile_path, min_lon, min_lat, max_lon, max_lat, category, access_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                layer["layer_name"],
                layer["local_tile_path"],
                *layer_bbox,
                layer["category"],
                layer["access_type"],
            ),
        )
        print(f"{layer['layer_name']}: {status}")

    conn.commit()
    conn.close()
    print("\nraster_registry updated.")


if __name__ == "__main__":
    main()
