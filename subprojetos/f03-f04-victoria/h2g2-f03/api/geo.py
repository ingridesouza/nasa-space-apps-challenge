"""Geometria na esfera de Marte (Mars 2000, R = 3.396.190 m).

Latitude planetocêntrica, longitude leste positiva. É o mesmo sistema do MMGIS
e do mosaico HiRISE (M3 e M7).
"""

from __future__ import annotations

import math

R_MARS = 3_396_190.0
DIRECOES = ("N", "NE", "L", "SE", "S", "SO", "O", "NO")


def haversine(lat1: float, lon1: float, lat2: float, lon2: float, r: float = R_MARS) -> float:
    """Distância em metros entre dois pontos."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumo inicial de 1 para 2, em graus a partir do norte (0–360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


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


def compass(az: float | None) -> str:
    """Graus -> ponto cardeal em português (N, NE, L, SE, S, SO, O, NO)."""
    if az is None:
        return "?"
    return DIRECOES[int(((az % 360) + 22.5) // 45) % 8]


def bbox(lat: float, lon: float, radius_m: float, r: float = R_MARS) -> tuple[float, float, float, float]:
    """Caixa em graus (lon_min, lon_max, lat_min, lat_max) que contém o círculo."""
    dlat = math.degrees(radius_m / r)
    dlon = dlat / max(1e-9, math.cos(math.radians(lat)))
    return lon - dlon, lon + dlon, lat - dlat, lat + dlat


def deg_to_m(r: float = R_MARS) -> float:
    """Metros por grau na esfera (ao longo de um meridiano)."""
    return math.pi / 180 * r
