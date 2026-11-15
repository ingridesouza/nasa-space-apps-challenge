"""Test script for the ArcGIS ImageServer adapter (Gale 1m HiRISE DTM).

Usage:
    python scripts/fetch_dtm_test.py

Downloads a real crop of the DEM (`dtm_hirise_1m` in config/layers.yaml) and
confirms, with rasterio, that the values are real elevation in meters (not
a rendered image) -- expected: the Gale Crater floor, around
-4500 m.
"""

import os
import sys

import rasterio
import yaml

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.arcgis_image_server import ArcGISImageServerAdapter
from adapters.base import BBox

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")


def main() -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    layer_cfg = config["layers"]["dtm_hirise_1m"]
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", "dtm_hirise_1m")

    adapter = ArcGISImageServerAdapter(
        image_server_url=layer_cfg["image_server_url"],
        spatial_ref_wkid=layer_cfg["spatial_ref_wkid"],
    )

    print("[1/3] Fetching service metadata...")
    info = adapter.get_service_info()
    print(f"      pixelType={info['pixelType']!r} bandCount={info['bandCount']}")
    print(f"      extent: {info['extent']}")

    bbox = BBox(**layer_cfg["test_bbox"])
    print(f"[2/3] Exporting real crop (512x512) for {bbox}")
    results = adapter.fetch_tiles(bbox=bbox, tile_matrix="512x512", out_dir=out_dir)
    local_path = results[0].local_path
    print(f"      saved to {local_path}")

    print("[3/3] Validating elevation values with rasterio...")
    with rasterio.open(local_path) as ds:
        band = ds.read(1)
        print(f"      crs={ds.crs} shape={ds.shape}")
        print(f"      elevation min/max: {band.min():.1f} m / {band.max():.1f} m")


if __name__ == "__main__":
    main()
