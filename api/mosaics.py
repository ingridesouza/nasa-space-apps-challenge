"""Builds a single mosaic from the WMTS tiles already downloaded for a
layer -- it is the real alternative to what we tried first (serving
as a standard XYZ `tiles` source in MapLibre).

Why XYZ `tiles` cannot be used directly: MapLibre assumes Web
Mercator (EPSG:3857) to decide which x/y to request at each zoom. Our
tiles come from Mars Trek's own WMTS grid (geographic/Mars CRS,
different origin and spacing -- see
data-pipeline/adapters/mars_trek_wmts.py). So the x/y the browser
requests almost never matches the file we downloaded -- all 404, blank
map.

Solution: since we only have a small sample of tiles (a single test
area, few of them), stitch everything into a single image and display it via
MapLibre's `ImageSource`, which takes the 4 real corner coordinates
instead of depending on a standard tile scheme.
"""

import io
import os
import re

import numpy as np
import rasterio
from PIL import Image

from geo import MARS_METERS_PER_DEGREE

TILE_FILENAME_RE = re.compile(r"^(\d+)_(\d+)_(\d+)\.png$")


def _list_tiles(folder: str) -> list[tuple[int, int, int, str]]:
    """Returns [(z, row, col, path)] only for the z that actually exists
    -- our adapters save a single zoom level per sample."""
    tiles = []
    for name in os.listdir(folder):
        m = TILE_FILENAME_RE.match(name)
        if m:
            z, row, col = (int(v) for v in m.groups())
            tiles.append((z, row, col, os.path.join(folder, name)))
    return tiles


def build_mosaic_image(local_tile_path: str) -> Image.Image | None:
    """In-memory stitch (returns the image, not already-encoded PNG) --
    reused both by the thumbnail endpoint (`build_mosaic_png`)
    and by the tile server (`tile_server.py`), which needs the pixel
    array to crop windows, not ready PNG bytes."""
    tiles = _list_tiles(local_tile_path)
    if not tiles:
        return None

    rows = sorted({t[1] for t in tiles})
    cols = sorted({t[2] for t in tiles})
    row_min, col_min = rows[0], cols[0]

    with Image.open(tiles[0][3]) as sample:
        tile_w, tile_h = sample.size

    mosaic = Image.new("RGB", (len(cols) * tile_w, len(rows) * tile_h))
    for _z, row, col, path in tiles:
        with Image.open(path) as tile_img:
            mosaic.paste(tile_img.convert("RGB"), ((col - col_min) * tile_w, (row - row_min) * tile_h))

    return mosaic


def build_mosaic_png(local_tile_path: str) -> bytes | None:
    mosaic = build_mosaic_image(local_tile_path)
    if mosaic is None:
        return None

    buf = io.BytesIO()
    mosaic.save(buf, format="PNG")
    return buf.getvalue()


def build_hillshade_array(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray | None:
    """Generates a real hillshade from an elevation GeoTIFF (HiRISE
    1m DTM or MOLA) -- classic Horn/ESRI formula, light coming from the
    northwest (315°) at 45° altitude (standard cartographic convention,
    it is not the real position of the Sun at Gale on that sol -- this is a
    RELIEF layer, not real solar illumination).

    It is not a calibrated "official" algorithm (e.g. GDAL `gdaldem
    hillshade`), but it uses real elevation data, the same approximation
    philosophy already documented in `_slope_degrees`. Returns the 8-bit
    array (not already-encoded PNG) -- reused by the tile server, which
    needs to crop windows from the array, not from ready PNG bytes."""
    with rasterio.open(dtm_path) as ds:
        elevation = ds.read(1).astype("float64")
        nodata = ds.nodata
        if nodata is not None:
            elevation = np.where(elevation == nodata, np.nan, elevation)

        pixel_size_m = abs(ds.transform.a) * MARS_METERS_PER_DEGREE

    dzdy, dzdx = np.gradient(elevation, pixel_size_m)

    slope_rad = np.arctan(np.hypot(dzdx, dzdy))
    aspect_rad = np.arctan2(dzdy, -dzdx)

    zenith_rad = np.radians(90 - altitude_deg)
    azimuth_rad = np.radians(azimuth_deg)

    shade = np.cos(zenith_rad) * np.cos(slope_rad) + np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(
        azimuth_rad - aspect_rad
    )
    shade = np.nan_to_num(shade, nan=0.5)
    return np.clip(shade * 255, 0, 255).astype("uint8")


def build_hillshade_rgba(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> np.ndarray | None:
    """Hillshade as an OVERLAY layer, (4, h, w) uint8: only what differs from flat terrain.

    Flat terrain renders sin(light altitude); what is brighter than that becomes white, what is
    darker becomes black, and opacity grows with the difference. Flat areas stay
    transparent and the image below (HiRISE) shows; ridges and slopes shade on top.
    The contrast is stretched by the 98th percentile of the difference over the whole crop (the same for
    all tiles, so the scale does not change from one tile to its neighbor)."""
    gray = build_hillshade_array(dtm_path, azimuth_deg, altitude_deg)
    if gray is None:
        return None
    flat = np.sin(np.radians(altitude_deg)) * 255
    delta = gray.astype("float64") - flat
    scale = max(np.percentile(np.abs(delta), 98), 1.0)
    strength = np.clip(np.abs(delta) / scale, 0, 1)
    rgba = np.zeros((4, *gray.shape), dtype="uint8")
    rgba[:3] = np.where(delta > 0, 255, 0).astype("uint8")
    rgba[3] = (strength * HILLSHADE_MAX_ALPHA).astype("uint8")
    return rgba


#: maximum opacity of the hillshade overlay (0-255): on the ridges the image is still visible
HILLSHADE_MAX_ALPHA = 200


def build_hillshade_png(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> bytes | None:
    shade_8bit = build_hillshade_array(dtm_path, azimuth_deg, altitude_deg)
    if shade_8bit is None:
        return None

    img = Image.fromarray(shade_8bit, mode="L").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
