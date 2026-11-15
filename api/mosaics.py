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


def build_mosaic_png(local_tile_path: str, thermal_palette: bool = False) -> bytes | None:
    """`thermal_palette=True` for layers whose mosaic is pure gray (today
    only THEMIS) -- see `apply_thermal_palette`, same treatment used by
    the tile server (api/tile_server.py), here for the layers panel
    thumbnail (`/mosaics/{layer}.png`)."""
    mosaic = build_mosaic_image(local_tile_path)
    if mosaic is None:
        return None

    if thermal_palette:
        mosaic = Image.fromarray(apply_thermal_palette(np.array(mosaic)), mode="RGB")

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


def _stretch_contrast(gray: np.ndarray) -> np.ndarray:
    """Contrast stretch (2-98 percentile) -- the boxwork is fairly flat, so
    the raw shade is squeezed into a narrow gray band. This only rescales
    the SAME real shading values to the full 0-255 range, as GDAL/QGIS
    hillshade does by default; it does not invent relief. Not applied to
    the overlay (build_hillshade_rgba), which measures the difference
    from flat terrain on the unstretched values."""
    low, high = np.percentile(gray, [2, 98])
    if high <= low:
        return gray
    return np.clip((gray.astype("float64") - low) / (high - low) * 255, 0, 255).astype("uint8")


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


#: sequential palette ("inferno" style) to translate the already-real
#: brightness value of the THEMIS mosaic into color -- only a visual
#: translation of the SAME pixel (it does not calibrate real temperature
#: in °C, which would need radiometric metadata we do not download),
#: hence the name avoids "temperature". Without it THEMIS is pure gray
#: and indistinguishable from the optical image below.
_THERMAL_PALETTE_STOPS = [
    (0, (0, 0, 4)),
    (64, (87, 16, 110)),
    (128, (188, 55, 84)),
    (192, (249, 142, 8)),
    (255, (252, 255, 164)),
]


def apply_thermal_palette(gray: np.ndarray) -> np.ndarray:
    """Takes a 2D array (or RGB with r==g==b) 0-255 and returns RGB
    (..., 3) colored by the sequential palette above -- same real pixel
    value, only mapped to a color the human eye can tell apart."""
    if gray.ndim == 3:
        gray = gray[..., 0] if gray.shape[-1] in (3, 4) else gray[0]

    xp = [s[0] for s in _THERMAL_PALETTE_STOPS]
    r = np.interp(gray, xp, [s[1][0] for s in _THERMAL_PALETTE_STOPS])
    g = np.interp(gray, xp, [s[1][1] for s in _THERMAL_PALETTE_STOPS])
    b = np.interp(gray, xp, [s[1][2] for s in _THERMAL_PALETTE_STOPS])
    return np.stack([r, g, b], axis=-1).astype("uint8")


def build_hillshade_png(dtm_path: str, azimuth_deg: float = 315.0, altitude_deg: float = 45.0) -> bytes | None:
    shade_8bit = build_hillshade_array(dtm_path, azimuth_deg, altitude_deg)
    if shade_8bit is None:
        return None

    img = Image.fromarray(_stretch_contrast(shade_8bit), mode="L").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
