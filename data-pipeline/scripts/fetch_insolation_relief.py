"""Downloads the two reliefs used by the insolation layer (see api/insolation.py):

- dtm_hirise_1m_native: Gale HiRISE DTM at 1 m/px over the boxwork crop
  (near shade: ridges, scarps);
- mola_regional_topography: MOLA ±1° around it (distant horizon: Mount
  Sharp shades the crop with a low sun).

Usage:
    python scripts/fetch_insolation_relief.py
"""

import os
import sys

import numpy as np
import rasterio
import yaml

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.arcgis_image_server import ArcGISImageServerAdapter  # noqa: E402
from adapters.base import BBox  # noqa: E402

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")
TILES = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles")


def main() -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        layers = yaml.safe_load(f)["layers"]
    for name in ("dtm_hirise_1m_native", "mola_regional_topography"):
        cfg = layers[name]
        adapter = ArcGISImageServerAdapter(image_server_url=cfg["image_server_url"], spatial_ref_wkid=cfg["spatial_ref_wkid"])
        r = adapter.fetch_tiles(bbox=BBox(**cfg["test_bbox"]), tile_matrix=cfg["size"], out_dir=os.path.join(TILES, name))[0]
        with rasterio.open(r.local_path) as ds:
            z = ds.read(1).astype("float64")
            print(f"{name}: {ds.shape} res={ds.res[0]:.3g}° elevation {np.nanmin(z):.0f} to {np.nanmax(z):.0f} m -> {r.local_path}")


if __name__ == "__main__":
    main()
