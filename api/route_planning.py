"""Real A* over the DTM grid, for feature 02 (smart route +
risk indicators). See docs/H2G2_Proposta_Projeto_Planejamento.md,
section "02", item 2.

Deliberate deviation from the original spec: it asks for AI4Mars for
per-pixel sand/roughness cost, but the feature 01 audit confirmed that
AI4Mars does not cover the boxwork period/region (dataset stops at ~sol
2579, the boxwork campaign is sol 4564+). The cost here uses only real
slope (DTM); the sand risk in the hollows is a fixed text warning
(see SAND_WARNING), not a numeric factor -- a decision made with the
user, do not generate per-pixel data that does not exist.

The cost grid is the real DTM (512x512px, ~5.88m/px -- it is not 1m
despite the layer name), loaded whole once and cached in
memory: point-by-point sampling (raster_sampling.py) does not work for
A*, which needs the full array as a graph.

Radiation (RAD, PDS) enters as a real accumulated dose over the
walk duration (see `_build_route`), not as a spatial cost: it is a per-sol
reading of the instrument on the rover, it does not vary per pixel in our data,
so it does not influence which path the A* chooses -- only how much this
specific walk exposes the astronaut, for real."""

import functools
import heapq
import math
import sqlite3

import numpy as np
import rasterio

from geo import MARS_METERS_PER_DEGREE, haversine_m
from vector_queries import all_science_targets

# Same limits as feature 01 (raster_sampling.py) -- a single "Artemis
# limit" across the whole system, not two values that may diverge.
SLOPE_CAUTION_LIMIT_DEG = 15.0
SLOPE_DANGER_LIMIT_DEG = 20.0

#: extra weight applied to the "caution" band (15-20°) in the "safest"
#: variant -- penalizes harder than in the "fastest" variant, which only
#: avoids what is truly impassable (>=20°).
CAUTION_WEIGHT = {"safest": 6.0, "fastest": 1.8}

#: maximum detour (in meters) worth making to pass by a science
#: target -- the whole bbox is ~5.6km on a side, so 600m is a
#: real but not absurd detour. If none of the targets fit within it, the
#: "most_science" variant does not even appear in the response (never forces
#: passing by something too far just to "have science").
MOST_SCIENCE_MAX_DETOUR_M = 600.0

#: fixed warning, citing the real source (not a per-pixel computation -- see
#: module docstring). The text is for direct display to the end user,
#: so it does not cite an internal repository file path --
#: that goes only in the code comment, not in the warning text.
SAND_WARNING = (
    "Risk of soft sand in the hollows between the boxwork ridges, "
    "reported by the Curiosity operators (the rover's wheels slipped "
    "in these areas). No per-pixel texture data for this region "
    "(AI4Mars does not cover the campaign period) -- treat it as a "
    "qualitative terrain warning, not as a cost already computed in the route."
)

# O2/time model: a simple estimate declared as such (the spec itself
# says "in the demo, the suit level is simulated", there is no real
# suit telemetry). Base speed on flat terrain ~0.8 m/s is the range
# cited in lunar/Apollo EVA studies for cautious walking with a
# pressurized suit; it drops as the slope rises.
BASE_SPEED_M_S = 0.8
O2_RATE_L_PER_MIN = 0.84  # documented Apollo EVA consumption at rest/light walking


class NoPathError(Exception):
    pass


class OutOfGridError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def _load_dtm(local_tile_path: str):
    """Loads the whole DTM once (array + transform), cached in
    memory -- unlike raster_sampling.sample_point, which opens the
    file on each call (ok for a single point, bad for the whole grid)."""
    with rasterio.open(local_tile_path) as dataset:
        elevation = dataset.read(1).astype(np.float64)
        transform = dataset.transform
        bounds = dataset.bounds
        nodata = dataset.nodata
    return elevation, transform, bounds, nodata


def _dtm_path(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT local_tile_path FROM raster_registry WHERE layer_name = 'dtm_hirise_1m'"
    ).fetchone()
    if row is None:
        raise RuntimeError("Layer dtm_hirise_1m not registered in raster_registry")
    return row["local_tile_path"]


def _slope_grid_deg(elevation: np.ndarray, pixel_size_m: float) -> np.ndarray:
    """Per-pixel slope for the whole grid (vectorized np.gradient) --
    same physics as the 3x3 window used in raster_sampling.sample_point,
    just computed at once for all pixels instead of point by
    point."""
    dz_dy, dz_dx = np.gradient(elevation, pixel_size_m)
    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    return np.degrees(slope_rad)


def _latlon_to_rc(transform, lat: float, lon: float) -> tuple[int, int]:
    col, row = ~transform * (lon, lat)
    return int(round(row)), int(round(col))


def _rc_to_latlon(transform, row: int, col: int) -> tuple[float, float]:
    lon, lat = transform * (col + 0.5, row + 0.5)
    return lat, lon


_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

#: tolerance radius (in pixels) to "snap" the click to the nearest
#: walkable pixel -- a single noisy-slope pixel (e.g. the
#: edge of a boxwork ridge) should not block a click that
#: visually seems to be on reasonable terrain. ~3 pixels * 5.88m/px
#: ~= 17m of tolerance, small enough not to change the meaning of the
#: user's click.
SNAP_RADIUS_PX = 3


def _snap_to_passable(r, c, n_rows, n_cols, passable):
    """Searches in a spiral for the walkable pixel nearest to (r, c)
    within SNAP_RADIUS_PX. Returns None if none is found."""
    if passable(r, c):
        return r, c
    for radius in range(1, SNAP_RADIUS_PX + 1):
        candidates = []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if max(abs(dr), abs(dc)) != radius:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < n_rows and 0 <= cc < n_cols and passable(rr, cc):
                    candidates.append((rr, cc))
        if candidates:
            return min(candidates, key=lambda p: math.hypot(p[0] - r, p[1] - c))
    return None


def _astar(elevation, slope_deg, transform, pixel_size_m, origin_rc, dest_rc, kind: str):
    n_rows, n_cols = elevation.shape
    caution_weight = CAUTION_WEIGHT[kind]

    def passable(r, c):
        return 0 <= r < n_rows and 0 <= c < n_cols and slope_deg[r, c] < SLOPE_DANGER_LIMIT_DEG

    def edge_cost(r1, c1, r2, c2):
        dist = pixel_size_m * math.hypot(r2 - r1, c2 - c1)
        s = max(slope_deg[r1, c1], slope_deg[r2, c2])
        if s >= SLOPE_CAUTION_LIMIT_DEG:
            return dist * caution_weight
        return dist

    def heuristic(r, c):
        dr, dc = dest_rc[0] - r, dest_rc[1] - c
        return pixel_size_m * math.hypot(dr, dc)

    origin_ok = _snap_to_passable(*origin_rc, n_rows, n_cols, passable)
    dest_ok = _snap_to_passable(*dest_rc, n_rows, n_cols, passable)
    if origin_ok is None and dest_ok is None:
        raise OutOfGridError("Origin and destination fall on terrain above the 20° limit (even at the nearest walkable pixel)")
    if origin_ok is None:
        raise OutOfGridError("Origin falls on terrain above the 20° limit -- click a slightly different point")
    if dest_ok is None:
        raise OutOfGridError("Destination falls on terrain above the 20° limit -- click a slightly different point")
    origin_rc, dest_rc = origin_ok, dest_ok

    open_set = [(heuristic(*origin_rc), origin_rc)]
    came_from: dict = {}
    g_score = {origin_rc: 0.0}
    visited = set()

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue
        if current == dest_rc:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        visited.add(current)

        for dr, dc in _NEIGHBORS_8:
            nb = (current[0] + dr, current[1] + dc)
            if nb in visited or not passable(*nb):
                continue
            new_g = g_score[current] + edge_cost(current[0], current[1], nb[0], nb[1])
            if new_g < g_score.get(nb, math.inf):
                g_score[nb] = new_g
                came_from[nb] = current
                heapq.heappush(open_set, (new_g + heuristic(*nb), nb))

    raise NoPathError("No possible path without crossing a slope >= 20°")


def _build_route(kind: str, path_rc, elevation, slope_deg, transform, pixel_size_m, rad_dose_ugy_per_hour) -> dict:
    points = [_rc_to_latlon(transform, r, c) for r, c in path_rc]

    distance_m = 0.0
    profile = [{"cumulative_distance_m": 0.0, "elevation_m": float(elevation[path_rc[0]])}]
    risk_segments = []
    time_s = 0.0
    for i in range(1, len(path_rc)):
        r1, c1 = path_rc[i - 1]
        r2, c2 = path_rc[i]
        d = pixel_size_m * math.hypot(r2 - r1, c2 - c1)
        distance_m += d

        s = max(slope_deg[r1, c1], slope_deg[r2, c2])
        if s >= SLOPE_DANGER_LIMIT_DEG:
            status = "danger"
        elif s >= SLOPE_CAUTION_LIMIT_DEG:
            status = "caution"
        else:
            status = "safe"

        # speed decreases with slope -- a simple and
        # declared model (see BASE_SPEED_M_S above), not a real sensor.
        speed = BASE_SPEED_M_S * max(1 - (s / SLOPE_DANGER_LIMIT_DEG) * 0.6, 0.25)
        time_s += d / speed

        profile.append({
            "cumulative_distance_m": round(distance_m, 1),
            "elevation_m": float(elevation[r2, c2]),
        })
        risk_segments.append({
            "from": [points[i - 1][0], points[i - 1][1]],
            "to": [points[i][0], points[i][1]],
            "slope_status": status,
            "slope_deg": round(float(s), 2),
        })

    time_min = time_s / 60.0
    o2_l = O2_RATE_L_PER_MIN * time_min

    # Real per-sol radiation (RAD) -- it does not vary by position in our
    # data (it is a reading of the instrument on the rover, not a spatial
    # raster), so it does not change WHICH path the A* chooses, but it is a
    # real dose really accumulated over the time the walk takes.
    # None (not 0) when the reference sol is not cached -- see
    # api/main.py REFERENCE_SOL -- so as not to fake "zero radiation".
    rad_dose_ugy = round(rad_dose_ugy_per_hour * (time_min / 60.0), 2) if rad_dose_ugy_per_hour is not None else None

    return {
        "type": kind,
        "points": [[lat, lon] for lat, lon in points],
        "distance_m": round(distance_m, 1),
        "estimated_time_min": round(time_min, 1),
        "estimated_o2_l": round(o2_l, 2),
        "estimated_rad_dose_ugy": rad_dose_ugy,
        "elevation_profile": profile,
        "risk_segments": risk_segments,
    }


def _best_science_target(origin_lat, origin_lon, dest_lat, dest_lon, targets: list[dict]) -> dict | None:
    """Science target with the smallest real detour (in meters) relative to the
    straight origin-destination line, among those that fit within
    MOST_SCIENCE_MAX_DETOUR_M. None if none fits -- never forces
    passing by a target too far just so a 3rd option exists."""
    direct = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)
    best, smallest_detour = None, None
    for target in targets:
        via_target = haversine_m(origin_lat, origin_lon, target["lat"], target["lon"]) + haversine_m(
            target["lat"], target["lon"], dest_lat, dest_lon
        )
        detour = via_target - direct
        if detour <= MOST_SCIENCE_MAX_DETOUR_M and (smallest_detour is None or detour < smallest_detour):
            best, smallest_detour = target, detour
    return best


def _chained_astar(elevation, slope_deg, transform, pixel_size_m, points_rc: list, kind: str) -> list:
    """Chains A* through a sequence of points (origin, stops..., destination),
    one call per leg, concatenating without duplicating the junction pixel
    between consecutive legs. Generalizes what "most_science" already did
    with 2 legs (origin->target->destination) to N legs (manual stops)."""
    path = _astar(elevation, slope_deg, transform, pixel_size_m, points_rc[0], points_rc[1], kind)
    for i in range(1, len(points_rc) - 1):
        leg = _astar(elevation, slope_deg, transform, pixel_size_m, points_rc[i], points_rc[i + 1], kind)
        path += leg[1:]
    return path


def plan_route(
    conn: sqlite3.Connection, origin_lat, origin_lon, dest_lat, dest_lon, rad_dose_ugy_per_hour=None, stops=None
) -> dict:
    """stops: optional list of (lat, lon) -- points the route must
    visit in order, between the origin and the destination ("intermediate
    stops" gap). With stops, the "most_science" variant is left out:
    it is already an automatic way to visit a point in the middle of the
    path, and two "point in the middle" logics at the same time would only
    confuse which route goes where -- if the astronaut is already
    choosing the points manually, that replaces the automatic suggestion."""
    path = _dtm_path(conn)
    elevation, transform, bounds, nodata = _load_dtm(path)

    pixel_size_deg = abs(transform.a)
    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE
    slope_deg = _slope_grid_deg(elevation, pixel_size_m)

    def inside_bbox(lat, lon):
        return bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top

    stops = stops or []
    all_points = [(origin_lat, origin_lon), *stops, (dest_lat, dest_lon)]
    if not all(inside_bbox(lat, lon) for lat, lon in all_points):
        raise OutOfGridError("Origin, stop or destination outside the area with downloaded DTM data")

    points_rc = [_latlon_to_rc(transform, lat, lon) for lat, lon in all_points]
    origin_rc, dest_rc = points_rc[0], points_rc[-1]

    routes = []
    for kind in ("safest", "fastest"):
        route_path = _chained_astar(elevation, slope_deg, transform, pixel_size_m, points_rc, kind)
        routes.append(_build_route(kind, route_path, elevation, slope_deg, transform, pixel_size_m, rad_dose_ugy_per_hour))

    # "most_science": passes by the real science target nearest to the
    # path, only if the detour is reasonable (see MOST_SCIENCE_MAX_DETOUR_M)
    # -- with few registered targets (feature 4), there will not always be
    # one close enough, and then this variant simply does not appear
    # (better than forcing an absurd detour just to "have science").
    if not stops:
        target = _best_science_target(origin_lat, origin_lon, dest_lat, dest_lon, all_science_targets(conn))
        if target is not None:
            target_rc = _latlon_to_rc(transform, target["lat"], target["lon"])
            try:
                full_path = _chained_astar(
                    elevation, slope_deg, transform, pixel_size_m, [origin_rc, target_rc, dest_rc], "safest"
                )
                science_route = _build_route(
                    "most_science", full_path, elevation, slope_deg, transform, pixel_size_m, rad_dose_ugy_per_hour
                )
                science_route["science_target"] = {
                    "name": target["name"],
                    "lat": target["lat"],
                    "lon": target["lon"],
                    "curiosity_measurement": target["curiosity_measurement"],
                    "source_url": target["source_url"],
                }
                routes.append(science_route)
            except (NoPathError, OutOfGridError):
                pass  # the target exists but has no walkable path to it -- no such variant, without breaking the other two

    return {"routes": routes, "warnings": [SAND_WARNING]}
