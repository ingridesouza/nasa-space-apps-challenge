"""Serves standard XYZ tiles (`/tiles/{layer}/{z}/{x}/{y}.png`) for the
real raster layers -- replaces the single-image `ImageSource`
(mosaics.py + frontend/src/map/style.ts) with a real tile map:
zoom/pan loading in parts, not a stretched photo.

Why this works without real cartographic reprojection: the standard
slippy map z/x/y -> lon/lat bbox addressing (OSM/Google/
any XYZ) is just a normalized-degree convention -- the radius of the
celestial body only enters the SCALE/physical resolution math, not the
addressing (same caveat already documented about
OGC_METERS_PER_DEGREE in data-pipeline/adapters/mars_trek_wmts.py).
Our Mars coordinates are already real lon/lat across the whole
system, so a window crop by lon/lat (same operation as
`route_planning._latlon_to_rc`) is enough -- without inventing any
precision that does not exist.

Serves the `access_type`s the frontend actually uses as a
tile layer (`tiles_wmts`, `derived_hillshade` and the derived/scalar layers) -- `single_raster`
(DTM/MOLA) is not displayed as a tile directly today, only sampled
point by point (see raster_sampling.py)."""

import functools
import io
import math
import os

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, reproject

from geo import MARS_RADIUS_M
from mosaics import build_hillshade_rgba, build_mosaic_image

TILE_SIZE = 256

# Ad hoc PROJ4 for the Mars sphere -- there is no Mars EPSG, and marking
# it as EPSG:4326 (real WGS84) would be misleading. Only used as
# metadata of the cached GeoTIFF; all tile cropping is done by
# direct transform arithmetic, never by real PROJ reprojection.
MARS_GEOGRAPHIC_CRS = f"+proj=longlat +a={MARS_RADIUS_M} +b={MARS_RADIUS_M} +no_defs"


def tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) of tile z/x/y -- standard
    slippy map formula, independent of the celestial body (see the module
    docstring)."""
    n = 2**z

    def lat_from_y(y_tile: float) -> float:
        t = math.pi * (1 - 2 * y_tile / n)
        return math.degrees(math.atan(math.sinh(t)))

    min_lon = x / n * 360.0 - 180.0
    max_lon = (x + 1) / n * 360.0 - 180.0
    max_lat = lat_from_y(y)
    min_lat = lat_from_y(y + 1)
    return min_lon, min_lat, max_lon, max_lat


def _build_georef_tif(local_tile_path: str, bbox: tuple[float, float, float, float], out_path: str) -> None:
    """Builds (once, cached on disk) a real GeoTIFF from the
    already-stitched mosaic (mosaics.build_mosaic_image) + the already
    corrected real bbox (see NEXT-STEPS.md about the
    georeferencing fix of 2026-11-14) -- same technique as
    `rasterio.transform.from_bounds` already used in route_planning.py."""
    mosaic = build_mosaic_image(local_tile_path)
    if mosaic is None:
        raise RuntimeError(f"No tiles in {local_tile_path}")

    min_lon, min_lat, max_lon, max_lat = bbox
    array = np.array(mosaic)  # (rows, cols, 3) RGB
    height, width = array.shape[0], array.shape[1]
    transform = rasterio.transform.from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype=array.dtype,
        crs=MARS_GEOGRAPHIC_CRS,
        transform=transform,
    ) as dst:
        for band in range(3):
            dst.write(array[:, :, band], band + 1)


@functools.lru_cache(maxsize=8)
def _load_array_and_transform(layer_name: str, local_tile_path: str, access_type: str, bbox: tuple[float, float, float, float],
                              variant: tuple | None = None):
    """(array, transform) cached in memory -- same pattern as
    route_planning._load_dtm, avoids reopening/rebuilding on each
    requested tile."""
    if access_type == "derived_hillshade":
        shade = build_hillshade_rgba(local_tile_path)
        if shade is None:
            raise RuntimeError(f"No DTM at {local_tile_path} to generate the hillshade")
        with rasterio.open(local_tile_path) as ds:
            transform, crs = ds.transform, ds.crs
        return shade, transform, (crs or MARS_GEOGRAPHIC_CRS)

    if access_type == "derived_risk":
        from forecast import risk_grid_rgba

        rgba, transform, crs = risk_grid_rgba(local_tile_path)
        return rgba, transform, (crs or MARS_GEOGRAPHIC_CRS)

    if access_type == "derived_insolation":
        from insolation import insolation_grid_rgba

        rgba, transform, crs = insolation_grid_rgba(*variant)  # variant = (sol, hour)
        return rgba, transform, (crs or MARS_GEOGRAPHIC_CRS)

    if access_type == "thermal_scalar":
        from thermal import ti_grid_rgba

        rgba, transform, crs = ti_grid_rgba(local_tile_path)
        return rgba, transform, (crs or MARS_GEOGRAPHIC_CRS)

    if access_type == "tiles_wmts":
        georef_path = os.path.join(local_tile_path, "_georef_mosaic.tif")
        if not os.path.exists(georef_path):
            _build_georef_tif(local_tile_path, bbox, georef_path)
        with rasterio.open(georef_path) as ds:
            array = ds.read()  # (3, rows, cols)
            return array, ds.transform, (ds.crs or MARS_GEOGRAPHIC_CRS)

    raise ValueError(f"access_type {access_type!r} is not served as a tile -- see the module docstring")


#: caches the final PNG (not just the decoded array) per layer/z/x/y --
#: without this, going back to a zoom level already visited in this session
#: redoes the reproject from scratch every time. ~50KB per tile, 2048 tiles
#: fit in ~100MB -- does not risk repeating the memory cuts that already
#: happened in this session (I did not use multiple uvicorn workers for
#: this same reason: each worker would duplicate the arrays already cached in
#: memory).
@functools.lru_cache(maxsize=2048)
def render_tile(
    layer_name: str, z: int, x: int, y: int, local_tile_path: str, access_type: str, bbox: tuple[float, float, float, float],
    variant: tuple | None = None,
) -> bytes | None:
    """256x256 PNG of the requested tile, or None if the tile does not intersect
    the real coverage of the layer (becomes 404 in api/main.py, same pattern already
    used by /mosaics/{layer}.png).

    Resampling via `rasterio.warp.reproject` (GDAL) instead of an
    integer-index window crop + PIL resize -- the previous version
    rounded each tile's window independently, and since a
    neighboring tile is another request/separate rounding, the edge
    between two tiles did not match pixel by pixel (the visible "seam"/
    distortion reported by the user when zooming). `reproject`
    samples each destination pixel by its real continuous coordinate (without
    rounding the window first), so two neighboring tiles always match
    exactly at the edge -- and being C/GDAL, it is much faster than the
    pure-Python crop+resize from before."""
    min_lon, min_lat, max_lon, max_lat = bbox
    t_min_lon, t_min_lat, t_max_lon, t_max_lat = tile_bounds_lonlat(z, x, y)

    if t_max_lon < min_lon or t_min_lon > max_lon or t_max_lat < min_lat or t_min_lat > max_lat:
        return None

    array, transform, crs = _load_array_and_transform(layer_name, local_tile_path, access_type, bbox, variant)
    dst_transform = rasterio.transform.from_bounds(t_min_lon, t_min_lat, t_max_lon, t_max_lat, TILE_SIZE, TILE_SIZE)

    if array.ndim == 2:
        destination = np.zeros((TILE_SIZE, TILE_SIZE), dtype=array.dtype)
    else:
        destination = np.zeros((array.shape[0], TILE_SIZE, TILE_SIZE), dtype=array.dtype)

    # dst_crs = src_crs (same degree system on both sides) -- it is not
    # a real cartographic reprojection, just continuous resampling
    # between two different pixel grids (see the module docstring
    # about z/x/y addressing not depending on the body radius).
    #
    # Resampling.cubic instead of bilinear -- sharper interpolation
    # of the SAME real pixels when zooming in beyond the native resolution
    # (already confirmed: z16 is the highest level Mars Trek offers for
    # HiRISE in this region, there is no more real detail to download).
    # This does not invent any new pixel, it only changes the way of
    # interpolating the ones we already have to a sharper kernel than the
    # simple average of bilinear.
    reproject(
        source=array,
        destination=destination,
        src_transform=transform,
        src_crs=crs,
        dst_transform=dst_transform,
        dst_crs=crs,
        # categorical (risk) must not mix colors between bands; thermal shows the
        # real 100 m cell instead of blurring
        resampling=Resampling.nearest if access_type in ("derived_risk", "thermal_scalar", "derived_insolation") else Resampling.cubic,
    )

    if array.ndim == 2:
        img = Image.fromarray(destination).convert("L").convert("RGB")
    elif array.shape[0] == 4:
        img = Image.fromarray(np.moveaxis(destination, 0, -1), mode="RGBA")
    else:
        img = Image.fromarray(np.moveaxis(destination, 0, -1)).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
