-- Local database schema for feature 01 (see
-- feature-01-mapa-hiperlocal-boxwork.md, section 3.1).
--
-- Uses SQLite's native R-Tree module (no SpatiaLite/GDAL) for the
-- radius search -- simpler to run offline on any team
-- machine, without having to compile any extension.

-- Rover photos and science targets live in the F03/F04 tables
-- (photos, panoramas, targets, measurements + R-trees), written to this
-- same database by data-pipeline/f03/etl/build.py.

CREATE TABLE IF NOT EXISTS raster_registry (
    layer_name TEXT PRIMARY KEY,
    local_tile_path TEXT NOT NULL,
    min_lon REAL,
    min_lat REAL,
    max_lon REAL,
    max_lat REAL,
    minzoom INTEGER,
    maxzoom INTEGER,
    category TEXT,
    -- 'single_raster': a single georeferenced file (e.g. the DTM GeoTIFF)
    --   that can be opened directly with rasterio for sampling.
    -- 'tiles_wmts': pyramid of PNG/JPG tiles with no per-file georeference
    --   -- it is for display on the map, not for value sampling
    --   (it would first need to become a georeferenced mosaic).
    -- derived/scalar layers: 'derived_hillshade', 'derived_risk',
    --   'thermal_scalar', 'derived_insolation' (see api/tile_server.py).
    access_type TEXT NOT NULL
);
