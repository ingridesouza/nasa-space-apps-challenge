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
CAUTION_WEIGHT = {"safest": 6.0, "fastest": 1.8, "smoothest": 30.0}  # smoothest: replanning "it is steep"

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
# BASE_SPEED_M_S: still without a confirmed real source for walking in
# Martian gravity (see the survey in NEXT-STEPS.md, section
# "Feature 02 (route)") -- previous value kept until a better
# reference exists.
BASE_SPEED_M_S = 0.8

# O2_RATE_L_PER_MIN: average metabolic rate assumed for a Mars EVA suit
# is 350 W (1194 BTU/hr), NASA, "Mars Exploration Portable Life
# Support System Schematic Study: Architecture Down-Selection"
# (ICES-2026-158, NTRS 20260002884) -- fixed value used in the PLSS
# schematic studies for 2 to 8 h EVAs (not a number "for 8 h"; it is
# used for any duration in that range). Converted to L/min of O2 by the
# standard caloric equivalent of O2 (~5 kcal/L = ~20.92 kJ/L):
#   350 W * 60 s/min / 20920 J/L = ~1.00 L/min
# Replaces the old value (0.84), which only had a vague comment
# ("Apollo EVA") with no verifiable source.
O2_RATE_L_PER_MIN = 1.00

# Optimistic-pessimistic range of O2 consumption per segment (Phase 1, F02+F08).
# Speed drops with slope as before (see BASE_SPEED_M_S above): optimistic
# does not reduce it, pessimistic uses the same drop the module already
# had. How much the O2 CONSUMPTION per minute grows with slope, however,
# is no longer an arbitrary factor -- it comes from the Pandolf equation
# (Pandolf, Givoni & Goldman, 1977), in the form NASA/JSC uses today to
# estimate the metabolic cost of EVA walking, including for Mars:
#   Kim, K.J., Hoffmann, B., Estep, P., Marshall-Goebel, K., Buckland, D.
#   "Improving Metabolic Workload Estimation Accuracy for Planning and
#   Analyzing Exploration Traverses". IEEE EMBC 2024. Funded by the
#   NASA Mars Campaign Office. Equation (2) of the paper:
#     MP = 1.5*W + 2.0*(W+L)*(L/W)^2 + eta*(W+L)*(1.5*V^2 + 0.35*V*G)
#   W = body mass (kg), L = external load/suit (kg), V = speed (m/s),
#   G = grade in % (100*tan of the segment angle), eta = terrain
#   coefficient (dimensionless).
# See PANDOLF_* right below for the source of each constant.
OPTIMISTIC_SPEED_FACTOR = 0.0   # optimistic: speed does not drop with slope
PESSIMISTIC_SPEED_FACTOR = 0.6  # pessimistic: same drop as BASE_SPEED_M_S before

# W (body mass, 82 kg = 180 lbm) and L (suit+PLSS mass, 104 kg = 230 lbm,
# initial mass budget target for a Mars suit): NASA, "Mars Suit Mass
# Considerations" (NTRS 20260003038, ICES 2026).
# eta=1.0 (asphalt/treadmill): Soule & Goldman (1972), base value of the
# terrain table used with the Pandolf equation -- eta does not vary per
# pixel, the same decision this module already made for soil texture
# (see SAND_WARNING: sand risk is a qualitative warning, not a numeric
# factor, for lack of per-pixel texture data for this region).
PANDOLF_BODY_MASS_KG = 82.0
PANDOLF_SUIT_MASS_KG = 104.0
PANDOLF_TERRAIN_COEF = 1.0
PANDOLF_GRADE_COEF = 0.35


def _pandolf_metabolic_w(speed_m_s: float, grade_pct: float) -> float:
    """Metabolic rate (watts) by the Pandolf equation -- see the comment of
    PESSIMISTIC_SPEED_FACTOR above for the source of the equation and of
    the PANDOLF_* constants.

    Known and accepted limitation: the equation imposes no ceiling of
    sustainable effort (VO2 max). So the "optimistic" side (speed not
    reduced) can come out, on a real mixed-terrain route, BELOW the old
    `estimated_o2_l` -- not because slope costs less oxygen, but because
    the total exposure time drops more than the rate rises. It is an
    accepted result of the model, not a bug: the "pessimistic" side (used
    in every safety decision) keeps growing with slope on any terrain.
    Fixing it would need a sustained VO2 max limit -- we do not impose a
    value without a source; see docs/fontes-de-dados.md."""
    w, l = PANDOLF_BODY_MASS_KG, PANDOLF_SUIT_MASS_KG
    return (
        1.5 * w
        + 2.0 * (w + l) * (l / w) ** 2
        + PANDOLF_TERRAIN_COEF
        * (w + l)
        * (1.5 * speed_m_s**2 + PANDOLF_GRADE_COEF * speed_m_s * grade_pct)
    )


# Normalizes the Pandolf equation by the base case (flat terrain, base
# speed) to turn it into a RATIO over O2_RATE_L_PER_MIN -- so the old key
# estimated_o2_l (which uses only O2_RATE_L_PER_MIN) does not change, and the
# ratio is exactly 1.0 on flat terrain in both cases (optimistic and
# pessimistic have the same speed when the slope is zero).
_BASE_METABOLIC_W = _pandolf_metabolic_w(BASE_SPEED_M_S, 0.0)


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
    o2_optimistic_l = 0.0
    o2_pessimistic_l = 0.0
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

        # Optimistic-pessimistic range of the segment (Phase 1): same form as
        # the speed/time above, with the factors declared at the top of
        # the file -- see *_SPEED_FACTOR.
        speed_optimistic = BASE_SPEED_M_S * max(1 - (s / SLOPE_DANGER_LIMIT_DEG) * OPTIMISTIC_SPEED_FACTOR, 0.25)
        speed_pessimistic = BASE_SPEED_M_S * max(1 - (s / SLOPE_DANGER_LIMIT_DEG) * PESSIMISTIC_SPEED_FACTOR, 0.25)
        segment_min_optimistic = (d / speed_optimistic) / 60.0
        segment_min_pessimistic = (d / speed_pessimistic) / 60.0

        # Pandolf ratio (see _pandolf_metabolic_w above) between the real
        # segment (with the slope and speed of each case) and the flat base
        # case -- this is what makes the O2 rate rise with slope, with a
        # declared source.
        grade_pct = 100.0 * math.tan(math.radians(s))
        o2_rate_optimistic = O2_RATE_L_PER_MIN * (_pandolf_metabolic_w(speed_optimistic, grade_pct) / _BASE_METABOLIC_W)
        o2_rate_pessimistic = O2_RATE_L_PER_MIN * (_pandolf_metabolic_w(speed_pessimistic, grade_pct) / _BASE_METABOLIC_W)
        o2_optimistic_l += o2_rate_optimistic * segment_min_optimistic
        o2_pessimistic_l += o2_rate_pessimistic * segment_min_pessimistic

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
        "estimated_o2_l_range": {
            "optimistic": round(o2_optimistic_l, 2),
            "pessimistic": round(o2_pessimistic_l, 2),
        },
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
    conn: sqlite3.Connection, origin_lat, origin_lon, dest_lat, dest_lon, rad_dose_ugy_per_hour=None, stops=None,
    kinds=("safest", "fastest"), avoid=None,
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
    # avoid: [(lat, lon, radius_m)] -- a reported obstacle (replan.py) becomes impassable terrain
    for lat, lon, radius_m in avoid or []:
        r0, c0 = _latlon_to_rc(transform, lat, lon)
        radius_px = math.ceil(radius_m / pixel_size_m)
        rows, cols = np.ogrid[:slope_deg.shape[0], :slope_deg.shape[1]]
        slope_deg = slope_deg.copy()
        slope_deg[(rows - r0) ** 2 + (cols - c0) ** 2 <= radius_px ** 2] = 90.0

    def inside_bbox(lat, lon):
        return bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top

    stops = stops or []
    all_points = [(origin_lat, origin_lon), *stops, (dest_lat, dest_lon)]
    if not all(inside_bbox(lat, lon) for lat, lon in all_points):
        raise OutOfGridError("Origin, stop or destination outside the area with downloaded DTM data")

    points_rc = [_latlon_to_rc(transform, lat, lon) for lat, lon in all_points]
    origin_rc, dest_rc = points_rc[0], points_rc[-1]

    routes = []
    for kind in kinds:
        route_path = _chained_astar(elevation, slope_deg, transform, pixel_size_m, points_rc, kind)
        routes.append(_build_route(kind, route_path, elevation, slope_deg, transform, pixel_size_m, rad_dose_ugy_per_hour))

    # "most_science": passes by the real science target nearest to the
    # path, only if the detour is reasonable (see MOST_SCIENCE_MAX_DETOUR_M)
    # -- with few registered targets (feature 4), there will not always be
    # one close enough, and then this variant simply does not appear
    # (better than forcing an absurd detour just to "have science").
    if not stops and not avoid and kinds == ("safest", "fastest"):  # replanning offers no science detour
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
