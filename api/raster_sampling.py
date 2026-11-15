"""Sampling of a real raster value at a lat/lon point -- only works
for layers with `access_type = 'single_raster'` in raster_registry (one
georeferenced GeoTIFF, e.g. the DTM/MOLA), not for `tiles_wmts` (loose
PNG tiles, with no per-file georeference -- they would first need to
become a mosaic, see NEXT-STEPS.md)."""

import os
import sqlite3

import numpy as np
import rasterio

from geo import MARS_METERS_PER_DEGREE

# 20° limit cited in the feature 01 doc ("feature 02" section): the same
# walking slope limit used by the Artemis program.
# "caution" is a warning band before hitting the real limit.
SLOPE_CAUTION_LIMIT_DEG = 15.0
SLOPE_DANGER_LIMIT_DEG = 20.0


def classify_slope(slope_deg: float) -> str:
    if slope_deg >= SLOPE_DANGER_LIMIT_DEG:
        return "danger"
    if slope_deg >= SLOPE_CAUTION_LIMIT_DEG:
        return "caution"
    return "safe"


def _slope_degrees(dataset: rasterio.DatasetReader, row: int, col: int) -> float | None:
    """Computes the slope by finite difference over a 3x3 window
    around the pixel -- enough for the MVP, it is not an "official" slope
    algorithm (e.g. Horn 1981), but it uses real elevation data."""
    window = rasterio.windows.Window(max(col - 1, 0), max(row - 1, 0), 3, 3)
    try:
        win = dataset.read(1, window=window)
    except Exception:
        return None

    if win.shape != (3, 3):
        return None

    pixel_size_deg = abs(dataset.transform.a)
    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE

    dz_dx = (win[1, 2] - win[1, 0]) / (2 * pixel_size_m)
    dz_dy = (win[2, 1] - win[0, 1]) / (2 * pixel_size_m)
    import math

    slope_rad = math.atan(math.hypot(dz_dx, dz_dy))
    return math.degrees(slope_rad)


def sample_point(local_tile_path: str, lat: float, lon: float) -> dict | None:
    """Opens the GeoTIFF and returns {value, slope_deg} at the point, or None if
    the point falls outside the raster extent -- or if the file does not
    exist: the registry may list a layer not downloaded yet (today the
    MOLA, with no fetch script), and that must not break /api/point."""
    if not os.path.isfile(local_tile_path):
        return None
    with rasterio.open(local_tile_path) as dataset:
        bounds = dataset.bounds
        if not (bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top):
            return None

        row, col = dataset.index(lon, lat)
        value = dataset.read(1)[row, col]
        nodata = dataset.nodata
        if nodata is not None and value == nodata:
            return None

        result = {"value": float(value)}
        slope = _slope_degrees(dataset, row, col)
        if slope is not None:
            result["slope_deg"] = round(slope, 2)
            result["slope_status"] = classify_slope(slope)
        return result


#: which elevation layer becomes the "official" value (`elevation_m`/`slope_deg`
#: at the top of the response) when more than one covers the point -- the most
#: precise first.
ELEVATION_PRIORITY = ["dtm_hirise_1m", "mola_regional_topography"]


def sample_all_rasters(conn: sqlite3.Connection, lat: float, lon: float) -> dict:
    """Queries raster_registry and samples all layers of type
    `single_raster` that cover the point.

    Root-level response format (`elevation_m`, `slope_deg`,
    `slope_status`, `ai4mars_class`, `crism_mineral`) follows
    EXACTLY the contract documented in
    feature-01-mapa-hiperlocal-boxwork.md, section 3.2 -- it is what
    feature 02 (route/A*) and feature 08 (voice) must read. `ai4mars_class`
    and `crism_mineral` stay `None` (not `"unknown"` nor invented):
    AI4Mars does not cover the boxwork period and CRISM has no observation in the
    bbox -- see NEXT-STEPS.md.

    `sources` is our own extension (not in the original spec): all the
    elevation sources that cover the point, not only the "official" one -- used
    by the frontend to show "other elevation sources"
    transparently."""
    rows = conn.execute(
        """
        SELECT layer_name, local_tile_path, category
        FROM raster_registry
        WHERE access_type = 'single_raster'
          AND min_lon <= ? AND ? <= max_lon
          AND min_lat <= ? AND ? <= max_lat
        """,
        (lon, lon, lat, lat),
    ).fetchall()

    sources = {}
    for row in rows:
        values = sample_point(row["local_tile_path"], lat, lon)
        if values is not None:
            sources[row["layer_name"]] = {"category": row["category"], **values}

    main = None
    for name in ELEVATION_PRIORITY:
        if name in sources:
            main = sources[name]
            break
    if main is None and sources:
        main = next(iter(sources.values()))

    return {
        "elevation_m": main["value"] if main else None,
        "slope_deg": main.get("slope_deg") if main else None,
        "slope_status": main.get("slope_status") if main else None,
        "ai4mars_class": None,  # AI4Mars does not cover the boxwork period -- see NEXT-STEPS.md
        "crism_mineral": None,  # CRISM with no observation in the bbox -- see NEXT-STEPS.md
        "sources": sources,
    }
