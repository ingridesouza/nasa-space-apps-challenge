"""Funções geométricas puras usadas pelo endpoint /api/point.

Nota: isto é distância real no terreno de Marte (raio de Marte), não a
convenção de pixel/grau do Mars Trek usada em
data-pipeline/adapters/mars_trek_wmts.py (aquela é um artefato de como
o Mars Trek gera seus tile sets, baseada no raio terrestre -- não deve
ser reaproveitada aqui)."""

import math

MARS_RADIUS_M = 3_396_190.0
MARS_METERS_PER_DEGREE = (2 * math.pi * MARS_RADIUS_M) / 360.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos, usando o raio de Marte
    (não o da Terra) -- é a distância real no terreno, diferente da
    conversão de pixel/grau do Mars Trek usada em outro lugar."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return MARS_RADIUS_M * c


def bearing_cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Direção cardinal (N/NE/E/.../NW) de (1) para (2)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)

    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    angulo = (math.degrees(math.atan2(x, y)) + 360) % 360

    direcoes = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(angulo / 45) % 8
    return direcoes[idx]


def bbox_radius_degrees(lat: float, radius_m: float) -> tuple[float, float]:
    """Converte um raio em metros para um delta em graus (lat, lon),
    usado para montar a bbox de busca do R-Tree antes do filtro fino
    por distância real."""
    dlat = radius_m / MARS_METERS_PER_DEGREE
    dlon = radius_m / (MARS_METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    return dlat, dlon
