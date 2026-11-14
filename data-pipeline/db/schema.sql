-- Schema do banco local da feature 01 (ver
-- feature-01-mapa-hiperlocal-boxwork.md, seção 3.1).
--
-- Usa o módulo R-Tree nativo do SQLite (sem SpatiaLite/GDAL) para a
-- busca por raio em rover_images -- mais simples de rodar offline em
-- qualquer máquina do time, sem precisar compilar extensão nenhuma.

CREATE TABLE IF NOT EXISTS rover_images (
    id INTEGER PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    sol INTEGER NOT NULL,
    site INTEGER,
    drive INTEGER,
    camera TEXT,
    heading REAL,
    local_path TEXT,
    thumbnail_path TEXT,
    captured_at TEXT
);

-- Índice espacial para busca por raio (feature 3: "fotos num raio de
-- ~200m"). Um ponto é armazenado como um bbox degenerado (min==max).
CREATE VIRTUAL TABLE IF NOT EXISTS rover_images_rtree USING rtree(
    id,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TABLE IF NOT EXISTS science_targets (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    mineral_crism TEXT,
    classe_ai4mars TEXT,
    medicao_curiosity TEXT,
    nome_iau_usgs TEXT,
    confianca TEXT,
    fonte_url TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS science_targets_rtree USING rtree(
    id,
    min_lon, max_lon,
    min_lat, max_lat
);

CREATE TABLE IF NOT EXISTS raster_registry (
    layer_name TEXT PRIMARY KEY,
    local_tile_path TEXT NOT NULL,
    min_lon REAL,
    min_lat REAL,
    max_lon REAL,
    max_lat REAL,
    minzoom INTEGER,
    maxzoom INTEGER,
    categoria TEXT,
    -- 'raster_unico': um único arquivo georreferenciado (ex. GeoTIFF do
    --   DTM) que dá pra abrir direto com rasterio e fazer sampling.
    -- 'tiles_wmts': pirâmide de tiles PNG/JPG sem georreferência própria
    --   por arquivo -- serve pra exibir no mapa, não pra sampling de
    --   valor (precisaria virar um mosaico georreferenciado antes).
    tipo_acesso TEXT NOT NULL
);
