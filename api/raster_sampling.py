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


#: qual camada de elevação vira o valor "oficial" (`elevacao_m`/`slope_deg`
#: no topo da resposta) quando mais de uma cobre o ponto -- a mais
#: precisa primeiro.
PRIORIDADE_ELEVACAO = ["dtm_hirise_1m", "mola_topografia_regional"]


def sample_all_rasters(conn: sqlite3.Connection, lat: float, lon: float) -> dict:
    """Consulta o raster_registry e amostra todas as camadas do tipo
    `raster_unico` que cobrem o ponto.

    Formato de resposta no nível raiz (`elevacao_m`, `slope_deg`,
    `slope_status`, `classe_ai4mars`, `mineral_crism`) segue
    EXATAMENTE o contrato documentado em
    feature-01-mapa-hiperlocal-boxwork.md, seção 3.2 -- é o que a
    feature 02 (rota/A*) e a feature 08 (voz) devem ler. `classe_ai4mars`
    e `mineral_crism` ficam `None` (não `"desconhecido"` nem inventado):
    AI4Mars não cobre a época do boxwork e CRISM não tem observação no
    bbox -- ver PROXIMOS-PASSOS.md.

    `fontes` é uma extensão nossa (não está na spec original): todas as
    fontes de elevação que cobrem o ponto, não só a "oficial" -- usado
    pelo frontend pra mostrar "outras fontes de elevação" de forma
    transparente."""
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

    fontes = {}
    for row in rows:
        valores = sample_point(row["local_tile_path"], lat, lon)
        if valores is not None:
            fontes[row["layer_name"]] = {"categoria": row["categoria"], **valores}

    principal = None
    for nome in PRIORIDADE_ELEVACAO:
        if nome in fontes:
            principal = fontes[nome]
            break
    if principal is None and fontes:
        principal = next(iter(fontes.values()))

    return {
        "elevacao_m": principal["valor"] if principal else None,
        "slope_deg": principal.get("slope_deg") if principal else None,
        "slope_status": principal.get("slope_status") if principal else None,
        "classe_ai4mars": None,  # AI4Mars não cobre a época do boxwork -- ver PROXIMOS-PASSOS.md
        "mineral_crism": None,  # CRISM sem observação no bbox -- ver PROXIMOS-PASSOS.md
        "fontes": fontes,
    }
