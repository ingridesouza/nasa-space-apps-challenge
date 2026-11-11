"""Sampling de valor real de raster num ponto lat/lon -- só funciona
para camadas `tipo_acesso = 'raster_unico'` no raster_registry (um
GeoTIFF georreferenciado, ex. o DTM/MOLA), não para `tiles_wmts` (tiles
PNG soltos, sem georreferência própria por arquivo -- precisariam virar
um mosaico primeiro, ver PROXIMOS-PASSOS.md)."""

import sqlite3

import numpy as np
import rasterio

from geo import MARS_METERS_PER_DEGREE

# Limite de 20° citado no doc da feature 01 (seção "feature 02"): mesmo
# limite de inclinação de caminhada usado pelo programa Artemis.
# "atencao" é uma faixa de alerta antes de bater no limite real.
LIMITE_SLOPE_ATENCAO_DEG = 15.0
LIMITE_SLOPE_PERIGO_DEG = 20.0


def classify_slope(slope_deg: float) -> str:
    if slope_deg >= LIMITE_SLOPE_PERIGO_DEG:
        return "perigo"
    if slope_deg >= LIMITE_SLOPE_ATENCAO_DEG:
        return "atencao"
    return "seguro"


def _slope_degrees(dataset: rasterio.DatasetReader, row: int, col: int) -> float | None:
    """Calcula a inclinação (slope) por diferença finita numa janela
    3x3 ao redor do pixel -- suficiente para o MVP, não é um algoritmo
    de slope "oficial" (ex. Horn 1981), mas usa dado real de elevação."""
    window = rasterio.windows.Window(max(col - 1, 0), max(row - 1, 0), 3, 3)
    try:
        janela = dataset.read(1, window=window)
    except Exception:
        return None

    if janela.shape != (3, 3):
        return None

    pixel_size_deg = abs(dataset.transform.a)
    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE

    dz_dx = (janela[1, 2] - janela[1, 0]) / (2 * pixel_size_m)
    dz_dy = (janela[2, 1] - janela[0, 1]) / (2 * pixel_size_m)
    import math

    slope_rad = math.atan(math.hypot(dz_dx, dz_dy))
    return math.degrees(slope_rad)


def sample_point(local_tile_path: str, lat: float, lon: float) -> dict | None:
    """Abre o GeoTIFF e devolve {valor, slope_deg} no ponto, ou None se
    o ponto cair fora da extensão do raster."""
    with rasterio.open(local_tile_path) as dataset:
        bounds = dataset.bounds
        if not (bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top):
            return None

        row, col = dataset.index(lon, lat)
        valor = dataset.read(1)[row, col]
        nodata = dataset.nodata
        if nodata is not None and valor == nodata:
            return None

        resultado = {"valor": float(valor)}
        slope = _slope_degrees(dataset, row, col)
        if slope is not None:
            resultado["slope_deg"] = round(slope, 2)
            resultado["slope_status"] = classify_slope(slope)
        return resultado


def sample_all_rasters(conn: sqlite3.Connection, lat: float, lon: float) -> dict:
    """Consulta o raster_registry e amostra todas as camadas do tipo
    `raster_unico` que cobrem o ponto."""
    rows = conn.execute(
        """
        SELECT layer_name, local_tile_path, categoria
        FROM raster_registry
        WHERE tipo_acesso = 'raster_unico'
          AND min_lon <= ? AND ? <= max_lon
          AND min_lat <= ? AND ? <= max_lat
        """,
        (lon, lon, lat, lat),
    ).fetchall()

    resultado = {}
    for row in rows:
        valores = sample_point(row["local_tile_path"], lat, lon)
        if valores is not None:
            resultado[row["layer_name"]] = {"categoria": row["categoria"], **valores}
    return resultado
