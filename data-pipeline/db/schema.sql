-- Schema do banco local da feature 01 (ver
-- feature-01-mapa-hiperlocal-boxwork.md, seção 3.1).
--
-- Usa o módulo R-Tree nativo do SQLite (sem SpatiaLite/GDAL) para a
-- busca por raio -- mais simples de rodar offline em
-- qualquer máquina do time, sem precisar compilar extensão nenhuma.

-- Fotos do rover e alvos científicos ficam nas tabelas do F03/F04
-- (photos, panoramas, targets, measurements + R-trees), gravadas neste
-- mesmo banco por data-pipeline/f03/etl/build.py.

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
