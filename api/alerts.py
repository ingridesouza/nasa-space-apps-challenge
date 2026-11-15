"""Fixed-rule alerts of feature 08 -- see
docs/feature-08-plano-implementacao.md (phase 1).

No language model here: the local model (phase 2) only explains what
these rules already decided, it never creates or cancels an alert.
An empty list means "no alert", never "safe"."""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache

from geo import haversine_m
from mars_time import ls, sol_date, sol_msl
from raster_sampling import classify_slope

WAYPOINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "rover_waypoints.json")

# ponytail: provisional base = Curiosity's stop on sol 4650 (the API's
# reference sol, target "Boxwork ridges"). The repo has no habitat
# position; change it here when the team decides.
BASE_LAT_LON = (-4.8068928, 137.3798418)

# Our choices (listed as an open decision in
# docs/feature-08-agente-local.md): the radius covers the MMGIS
# localization error; 2 km is the distance limit from the module cited
# in the proposal (Artemis).
HISTORY_RADIUS_M = 25
RETURN_TO_BASE_LIMIT_M = 2000
# Our choice: with no rover stop within this radius, the verdict depends only on the
# orbital DTM (~6 m/px), which caught 4 of 25 steep stops measured by the rover.
NO_HISTORY_RADIUS_M = 100

_ORDER = {"danger": 0, "caution": 1, "info": 2}


def _num(value: float) -> str:
    """22.37 -> "22.4" (the message goes to the screen and to voice)."""
    return f"{value:.1f}"


def _alert(level: str, type_: str, message: str, source: str) -> dict:
    return {"level": level, "type": type_, "message": message, "source": source}


@lru_cache(maxsize=4)
def load_stops(path: str = WAYPOINTS_PATH) -> list[dict] | None:
    """Curiosity stops (MMGIS), read once. None if the file does
    not exist (make build did not run fetch_rover_waypoints.py)."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _slope_rules(raster_values: dict) -> list[dict]:
    slope = raster_values.get("slope_deg")
    status = raster_values.get("slope_status")
    if slope is None:
        return [_alert("info", "no_data", "No slope data at this point.", "HiRISE DTM (Mars Trek)")]
    if status == "danger":
        msg = f"Slope of {_num(slope)}° at this point, above the Artemis 20° limit."
    elif status == "caution":
        msg = f"Slope of {_num(slope)}° at this point, close to the Artemis 20° limit."
    else:
        return []
    return [_alert(status, "slope", msg + " Mean map value over about 12 m.", "HiRISE DTM (Mars Trek)")]


def _sand_rule(raster_values: dict) -> list[dict]:
    if raster_values.get("ai4mars_class") is not None:
        return []
    return [
        _alert(
            "info",
            "no_data",
            "No sand data at this point: we cannot claim there is no sand.",
            "AI4Mars (no coverage over the boxwork)",
        )
    ]


def _historical_terrain_rule(lat: float, lon: float, waypoints_path: str) -> list[dict]:
    stops = load_stops(waypoints_path)
    if stops is None:
        return [
            _alert(
                "info",
                "no_data",
                "Rover history unavailable (run data-pipeline/scripts/fetch_rover_waypoints.py).",
                "MMGIS MSL_waypoints",
            )
        ]

    # Several stops nearby: only the steepest one becomes an alert.
    worst = None
    for p in stops:
        status = classify_slope(p["tilt"])
        if status == "safe":
            continue
        dist = haversine_m(lat, lon, p["lat"], p["lon"])
        # up to 25 m the measured level holds; from 25 to 100 m (where "no history" does not fire) it becomes caution
        if dist <= NO_HISTORY_RADIUS_M and (worst is None or p["tilt"] > worst[0]["tilt"]):
            worst = (p, dist, status if dist <= HISTORY_RADIUS_M else "caution")

    if worst is None:
        return []
    p, dist, status = worst
    msg = f"Curiosity measured a {_num(p['tilt'])}° slope {dist:.0f} m from here (sol {p['sol']})."
    return [_alert(status, "historical_terrain", msg, "MMGIS MSL_waypoints")]


def _no_history_rule(lat: float, lon: float, raster_values: dict, waypoints_path: str) -> list[dict]:
    stops = load_stops(waypoints_path)
    if stops is None or raster_values.get("slope_deg") is None:
        return []  # already warned by another rule (no history / no slope)
    if any(haversine_m(lat, lon, p["lat"], p["lon"]) <= NO_HISTORY_RADIUS_M for p in stops):
        return []
    msg = (f"No Curiosity stop within {NO_HISTORY_RADIUS_M} m: the slope comes only from the orbital map "
           "(about 6 m per pixel), which cannot see 1 to 2 m ridges.")
    return [_alert("caution", "no_history", msg, "MMGIS MSL_waypoints + HiRISE DTM (Mars Trek)")]


def _predicted_risk_rule(raster_values: dict) -> list[dict]:
    from forecast import slope_risk  # late import: forecast uses this module

    risk = slope_risk(raster_values.get("slope_deg"))
    if not risk or risk["chance_pct"] < 20 or raster_values.get("slope_status") != "safe":
        return []  # the map already warns (>= 15°) or low chance
    msg = (f"The map says {_num(raster_values['slope_deg'])}°, but where the map shows {risk['map_range']} "
           f"the rover measured {risk['limit_deg']}° or more at {risk['chance_pct']}% of the stops.")
    return [_alert("caution", "predicted_risk", msg, "H2G2 forecast: rover history × DTM")]


def _return_to_base_rule(lat: float, lon: float) -> list[dict]:
    dist = haversine_m(lat, lon, *BASE_LAT_LON)
    if dist <= RETURN_TO_BASE_LIMIT_M:
        return []
    meters = f"{dist:,.0f}"  # 2029.4 -> "2,029": in km it would round to "2.0", which reads as within the limit
    msg = f"{meters} m from the base: beyond the 2,000 m distance limit from the module (Artemis)."
    return [_alert("danger", "return_to_base", msg, "H2G2 proposal (Artemis limit)")]


def point_alerts(lat: float, lon: float, raster_values: dict, waypoints_path: str = WAYPOINTS_PATH) -> list[dict]:
    """All alerts for a point, from most to least severe.
    `raster_values` is the same dict that /api/point already returns."""
    alerts = (
        _slope_rules(raster_values)
        + _historical_terrain_rule(lat, lon, waypoints_path)
        + _no_history_rule(lat, lon, raster_values, waypoints_path)
        + _predicted_risk_rule(raster_values)
        + _return_to_base_rule(lat, lon)
        + _sand_rule(raster_values)
    )
    return sorted(alerts, key=lambda a: _ORDER[a["level"]])


# Regional and global storms concentrate in the half of the year around perihelion
# (southern spring and summer): Ls 180° to 360° (Mars24 / MCD climatology).
DUST_LS = (180.0, 360.0)


def sol_time_and_alerts(data_sol: int, now: datetime | None = None) -> tuple[dict, list[dict]]:
    """No-Earth mode (phase 3): current season and age of the REMS/RAD data.
    Valid for the planet, not the point: goes into /api/conditions."""
    now = now or datetime.now(timezone.utc)
    sol_now, ls_now = sol_msl(now), ls(now)
    age = sol_now - data_sol
    time_info = {"sol_now": sol_now, "ls_now": round(ls_now, 1), "data_sol": data_sol,
                 "data_date": sol_date(data_sol).date().isoformat(), "data_age_sols": age,
                 "source": "Mars24 algorithm (NASA GISS) on the local clock"}
    alerts = []
    if age >= 1:
        alerts.append(_alert("caution", "stale_data",
                             f"Conditions from sol {data_sol}, {age} sols ago: not a current reading.",
                             f"REMS/RAD sol {data_sol}"))
    if DUST_LS[0] <= ls_now < DUST_LS[1]:
        alerts.append(_alert("caution", "dust_season",
                             f"Dust storm season (Ls {_num(ls_now)}°, higher risk between 180° and 360°).",
                             "Mars24 (Ls) + dust climatology"))
    return time_info, alerts


#: ~5.88 m/px is the DTM pixel (route_planning.py) -- sampling 1 in every
#: 5 route points already covers the scale of the alert radii (25-100 m)
#: without running the rover history rule point by point on a path
#: with hundreds of pixels.
ROUTE_SAMPLE_STEP = 5


def route_alerts(points: list[tuple[float, float]], waypoints_path: str = WAYPOINTS_PATH) -> list[dict]:
    """Agent alerts (feature 08) crossed with the path computed
    by feature 02 (route_planning.py): steepest slope Curiosity has
    already measured near the route and segments that leave the
    return-to-base radius. The slope itself is already in risk_segments (same
    DTM limit as the A*); here goes only what the agent knows and the A*
    does not use to choose a path.

    Each alert carries `point_index` (index into `points`) -- the caller
    (api/main.py) converts it into the real cumulative distance using the
    same `elevation_profile` it already returns for the chart, to say IN
    WHICH SEGMENT of the walk the alert applies, not just that it exists."""
    sample_idx = list(range(0, len(points), ROUTE_SAMPLE_STEP))
    if points and sample_idx[-1] != len(points) - 1:
        sample_idx.append(len(points) - 1)

    seen = set()
    alerts = []
    for i in sample_idx:
        lat, lon = points[i]
        for a in _historical_terrain_rule(lat, lon, waypoints_path) + _return_to_base_rule(lat, lon):
            key = (a["type"], a["message"])
            if key not in seen:
                seen.add(key)
                alerts.append({**a, "point_index": i})
    return alerts


def stops_in_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[dict] | None:
    """Curiosity track inside the bbox, with the measured slope already
    classified by the same DTM limits (15° and 20°)."""
    stops = load_stops()
    if stops is None:
        return None
    return [
        {"lat": p["lat"], "lon": p["lon"], "sol": p["sol"], "tilt": p["tilt"], "status": classify_slope(p["tilt"])}
        for p in stops
        if min_lon <= p["lon"] <= max_lon and min_lat <= p["lat"] <= max_lat
    ]
