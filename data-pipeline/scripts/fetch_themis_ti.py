"""Downloads only the boxwork window of the quantitative THEMIS thermal
inertia mosaic (USGS Astropedia) and writes a small local GeoTIFF.

Usage:
    python scripts/fetch_themis_ti.py

The .cub is 2.5 GB; rasterio reads via /vsicurl/ only the window blocks
(HTTP Range). Output at data/local/tiles/themis_ti/ti_100m.tif, already with
the transform in degrees (lon/lat) -- eqc with lat_ts=0 is linear in degrees,
so it is just a matter of rescaling the transform, without resampling any pixel.
"""

import math
import os
import sys

import numpy as np
import rasterio
import yaml
from rasterio.transform import Affine
from rasterio.windows import from_bounds

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", "themis_ti", "ti_100m.tif")
MARGIN_DEG = 0.01  # a bit beyond the bbox, so the crop edge is not left without a cell


def main() -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["layers"]["themis_ti"]
    b = cfg["test_bbox"]

    with rasterio.open("/vsicurl/" + cfg["url"]) as ds:
        radius = ds.crs.to_dict().get("R")
        if not radius:
            raise SystemExit(f"Unexpected CRS (no R sphere): {ds.crs}")
        m_per_deg = math.pi * radius / 180

        def xy(lon, lat):
            return lon * m_per_deg, lat * m_per_deg

        x0, y0 = xy(b["min_lon"] - MARGIN_DEG, b["min_lat"] - MARGIN_DEG)
        x1, y1 = xy(b["max_lon"] + MARGIN_DEG, b["max_lat"] + MARGIN_DEG)
        window = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
        print(f"[1/2] Reading window {window} from {cfg['url']}")
        data = ds.read(1, window=window)
        t = ds.window_transform(window)
        nodata = ds.nodata

    valid = data[(data != nodata) & np.isfinite(data)] if nodata is not None else data[np.isfinite(data)]
    if valid.size == 0:
        raise SystemExit("Window without any valid value -- writes nothing (no invented data)")

    degrees = Affine(t.a / m_per_deg, 0, t.c / m_per_deg, 0, t.e / m_per_deg, t.f / m_per_deg)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with rasterio.open(
        OUT_PATH, "w", driver="GTiff", width=data.shape[1], height=data.shape[0], count=1,
        dtype="float32", transform=degrees, nodata=nodata,
        crs=f"+proj=longlat +a={radius} +b={radius} +no_defs",
    ) as dst:
        dst.write(data.astype("float32"), 1)
        dst.update_tags(source="THEMIS Global Thermal Inertia Mosaic, quantitative 32-bit (USGS Astropedia)",
                        url=cfg["url"], unit="J m-2 K-1 s-1/2", resolution_m="100")

    print(f"[2/2] {data.shape} cells -> {OUT_PATH}")
    print(f"      TI min/median/max: {valid.min():.0f} / {np.median(valid):.0f} / {valid.max():.0f}")


if __name__ == "__main__":
    main()
