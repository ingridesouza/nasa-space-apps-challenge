"""Geometry on the Mars sphere (Mars 2000, R = 3,396,190 m) -- the only
implementation in the app (the API and the F03/F04 ETL import from here).

Planetocentric latitude, east-positive longitude (same system as
MMGIS and the HiRISE mosaic).

Note: this is real ground distance on Mars (Mars radius), not the
Mars Trek pixel/degree convention used in
data-pipeline/adapters/mars_trek_wmts.py (that one is an artifact of how
Mars Trek generates its tile sets, based on the Earth radius -- it must
not be reused here)."""

import math

MARS_RADIUS_M = 3_396_190.0
MARS_METERS_PER_DEGREE = (2 * math.pi * MARS_RADIUS_M) / 360.0
R_MARS = MARS_RADIUS_M

COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two points, using the Mars radius."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * MARS_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


haversine = haversine_m


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from (1) to (2), in degrees from north (0–360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_cardinal(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Cardinal direction (N/NE/E/.../NW) from (1) to (2)."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[round(bearing(lat1, lon1, lat2, lon2) / 45) % 8]


def compass(az: float | None) -> str:
    """Degrees -> compass point (N, NE, E, SE, S, SW, W, NW)."""
    if az is None:
        return "?"
    return COMPASS_POINTS[int(((az % 360) + 22.5) // 45) % 8]


def wrap180(a: float) -> float:
    """Normalizes an angle to [−180, 180)."""
    return (a + 180) % 360 - 180


def initial_yaw(bearing_stop_to_point: float, center_az: float) -> float:
    """Pannellum yaw so the panorama opens looking at the point.
    The image center (yaw 0) points to center_az."""
    return wrap180(bearing_stop_to_point - center_az)


def photo_azimuth(mast_az: float, rover_yaw: float | None) -> float | None:
    """True direction of the photo from north. mast_az is measured from the
    rover's front (M6, hypothesis B), so the stop's yaw is added."""
    if rover_yaw is None:
        return None
    return (mast_az + rover_yaw) % 360


def bbox_radius_degrees(lat: float, radius_m: float) -> tuple[float, float]:
    """Converts a radius in meters to a delta in degrees (lat, lon),
    used to build the R-Tree search bbox before the fine filter
    by real distance."""
    dlat = radius_m / MARS_METERS_PER_DEGREE
    dlon = radius_m / (MARS_METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    return dlat, dlon


def bbox(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Box in degrees (lon_min, lon_max, lat_min, lat_max) that contains the circle."""
    dlat, dlon = bbox_radius_degrees(lat, radius_m)
    return lon - dlon, lon + dlon, lat - dlat, lat + dlat
