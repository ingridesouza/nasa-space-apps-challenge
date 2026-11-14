"""Geometria na esfera de Marte (Mars 2000, R = 3.396.190 m) -- única
implementação do app (API e ETL do F03/F04 importam daqui).

Latitude planetocêntrica, longitude leste positiva (mesmo sistema do
MMGIS e do mosaico HiRISE).

Nota: isto é distância real no terreno de Marte (raio de Marte), não a
convenção de pixel/grau do Mars Trek usada em
data-pipeline/adapters/mars_trek_wmts.py (aquela é um artefato de como
o Mars Trek gera seus tile sets, baseada no raio terrestre -- não deve
ser reaproveitada aqui)."""

import math

MARS_RADIUS_M = 3_396_190.0
MARS_METERS_PER_DEGREE = (2 * math.pi * MARS_RADIUS_M) / 360.0
R_MARS = MARS_RADIUS_M

DIRECOES_PT = ("N", "NE", "L", "SE", "S", "SO", "O", "NO")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos, usando o raio de Marte."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * MARS_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


haversine = haversine_m


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumo inicial de (1) para (2), em graus a partir do norte (0–360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Direção cardinal (N/NE/E/.../NW) de (1) para (2)."""
    direcoes = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return direcoes[round(bearing(lat1, lon1, lat2, lon2) / 45) % 8]


def compass(az: float | None) -> str:
    """Graus -> ponto cardeal em português (N, NE, L, SE, S, SO, O, NO)."""
    if az is None:
        return "?"
    return DIRECOES_PT[int(((az % 360) + 22.5) // 45) % 8]


def wrap180(a: float) -> float:
    """Normaliza um ângulo para [−180, 180)."""
    return (a + 180) % 360 - 180


def yaw_inicial(rumo_parada_ponto: float, center_az: float) -> float:
    """Yaw do Pannellum para o panorama abrir olhando para o ponto.
    O centro da imagem (yaw 0) aponta para center_az."""
    return wrap180(rumo_parada_ponto - center_az)


def photo_azimuth(mast_az: float, rover_yaw: float | None) -> float | None:
    """Direção real da foto a partir do norte. O mast_az é medido a partir da
    frente do rover (M6, hipótese B), então soma o yaw da parada."""
    if rover_yaw is None:
        return None
    return (mast_az + rover_yaw) % 360


def bbox_radius_degrees(lat: float, radius_m: float) -> tuple[float, float]:
    """Converte um raio em metros para um delta em graus (lat, lon),
    usado para montar a bbox de busca do R-Tree antes do filtro fino
    por distância real."""
    dlat = radius_m / MARS_METERS_PER_DEGREE
    dlon = radius_m / (MARS_METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    return dlat, dlon


def bbox(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Caixa em graus (lon_min, lon_max, lat_min, lat_max) que contém o círculo."""
    dlat, dlon = bbox_radius_degrees(lat, radius_m)
    return lon - dlon, lon + dlon, lat - dlat, lat + dlat
