"""Tests for the return-cost map (Phase 2) and the return-margin profile
(Phase 3) in api/route_planning.py -- min_margin, no_return_point,
worst_emergency_segment, max_return_minutes.

Run: cd api && python test_route_planning.py
Needs data/local/h2g2.sqlite with the dtm_hirise_1m layer (make build)."""

import sys
from pathlib import Path

import numpy as np
from affine import Affine

sys.path.insert(0, str(Path(__file__).parent))

from alerts import BASE_LAT_LON
from db import get_connection
from route_planning import (
    SLOPE_DANGER_LIMIT_DEG,
    _build_route,
    _dtm_path,
    _latlon_to_rc,
    _load_dtm,
    _slope_grid_deg,
    cost_to_base,
)

CONN = get_connection()

TRANSFORM = Affine(0.00005, 0, 137.0, 0, -0.00005, -4.8)
FLAT_ELEVATION = np.zeros((5, 5))
FLAT_SLOPE = np.zeros((5, 5))
STRAIGHT_PATH = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]

# Synthetic return-cost map: cost grows at a constant rate per pixel of
# straight-line distance from (0,0) -- easy to predict exactly where each
# criterion should fire.
INCREASING_COST_MAP = {
    (0, 0): {"return_time_s": 0.0, "return_o2_l": 0.0},
    (0, 1): {"return_time_s": 10.0, "return_o2_l": 0.1},
    (0, 2): {"return_time_s": 20.0, "return_o2_l": 0.2},
    (0, 3): {"return_time_s": 30.0, "return_o2_l": 0.3},
    (0, 4): {"return_time_s": 40.0, "return_o2_l": 0.4},
}


def _route(cost_map, available_o2_l=None):
    return _build_route(
        "fastest", STRAIGHT_PATH, FLAT_ELEVATION, FLAT_SLOPE, TRANSFORM, 5.0, None, cost_map, available_o2_l
    )


def test_no_cost_map_all_fields_are_null():
    r = _route(cost_map=None, available_o2_l=10.0)
    assert r["min_margin"] is None
    assert r["no_return_point"] is None
    assert r["worst_emergency_segment"] is None
    assert r["max_return_minutes"] is None


def test_no_o2_given_margin_is_null_but_the_rest_still_works():
    r = _route(INCREASING_COST_MAP, available_o2_l=None)
    assert r["min_margin"] is None
    assert r["no_return_point"] is not None
    assert r["worst_emergency_segment"] is not None
    assert r["max_return_minutes"] is not None


def test_no_return_point_is_the_first_where_turning_back_gets_more_expensive_than_going_on():
    r = _route(INCREASING_COST_MAP, available_o2_l=10.0)
    # total pessimistic time ~25s (4 segments of 5m at 0.8m/s); the return
    # cost overtakes the remaining time exactly at the 3rd point (index 2,
    # 10m of distance) -- see the hand computation in the implementation session.
    assert r["no_return_point"]["distance_m"] == 10.0


def test_worst_emergency_segment_is_the_one_with_the_highest_return_cost():
    r = _route(INCREASING_COST_MAP, available_o2_l=10.0)
    assert r["worst_emergency_segment"]["distance_m"] == 20.0  # last point, highest return_time_s
    assert r["worst_emergency_segment"]["return_minutes"] == round(40.0 / 60, 1)
    assert r["worst_emergency_segment"]["return_o2_l"] == 0.4


def test_unreachable_point_wins_as_worst_case_even_with_higher_finite_returns_elsewhere():
    cost_map = dict(INCREASING_COST_MAP)
    del cost_map[(0, 3)]  # this point has no path back to base
    r = _route(cost_map, available_o2_l=10.0)
    assert r["worst_emergency_segment"]["distance_m"] == 15.0  # index 3, not index 4 (40s, the highest finite value)
    assert r["worst_emergency_segment"]["return_minutes"] is None
    assert r["worst_emergency_segment"]["return_o2_l"] is None
    # max_return_minutes and min_margin ignore the point with no return --
    # it already got flagged in worst_emergency_segment, no need to repeat it.
    assert r["max_return_minutes"] == round(40.0 / 60, 1)


def test_min_margin_is_the_worst_point_and_matches_the_hand_computation():
    r = _route(INCREASING_COST_MAP, available_o2_l=10.0)
    # liters/pct computed by hand (see the implementation session): the
    # worst point is the last one (index 4): 10 - (o2 spent by there + return o2).
    assert r["min_margin"]["liters"] == 9.18
    assert r["min_margin"]["pct"] == 91.8
    assert r["min_margin"]["distance_m"] == 20.0


def test_min_margin_grows_with_more_available_o2():
    low = _route(INCREASING_COST_MAP, available_o2_l=1.0)
    high = _route(INCREASING_COST_MAP, available_o2_l=100.0)
    assert high["min_margin"]["liters"] > low["min_margin"]["liters"]


def test_base_has_zero_return_cost_on_the_real_dtm():
    path = _dtm_path(CONN)
    elevation, transform, bounds, nodata = _load_dtm(path)
    base_rc = _latlon_to_rc(transform, *BASE_LAT_LON)

    cost_map = cost_to_base(CONN)
    assert cost_map[base_rc]["return_time_s"] == 0.0
    assert cost_map[base_rc]["return_o2_l"] == 0.0


def test_farther_pixel_has_a_longer_return_than_a_closer_one_on_the_real_dtm():
    cost_map = cost_to_base(CONN)
    path = _dtm_path(CONN)
    elevation, transform, bounds, nodata = _load_dtm(path)
    base_rc = _latlon_to_rc(transform, *BASE_LAT_LON)

    near = (base_rc[0] + 5, base_rc[1])
    far = (base_rc[0] + 50, base_rc[1])
    assert near in cost_map and far in cost_map
    assert cost_map[far]["return_time_s"] > cost_map[near]["return_time_s"] > 0
    assert cost_map[far]["return_o2_l"] > cost_map[near]["return_o2_l"] > 0


def test_impassable_pixel_has_no_entry_on_the_real_dtm():
    cost_map = cost_to_base(CONN)
    path = _dtm_path(CONN)
    elevation, transform, bounds, nodata = _load_dtm(path)
    pixel_size_deg = abs(transform.a)
    from geo import MARS_METERS_PER_DEGREE

    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE
    slope_deg = _slope_grid_deg(elevation, pixel_size_m)
    n_rows, n_cols = elevation.shape

    impassable = [
        (r, c)
        for r in range(n_rows)
        for c in range(n_cols)
        if slope_deg[r, c] >= SLOPE_DANGER_LIMIT_DEG
    ]
    assert impassable, "expected at least one pixel >= 20 deg in the real boxwork DTM"
    assert not any(rc in cost_map for rc in impassable[:50])


def test_cache_returns_the_same_object():
    # lru_cache: the second call must not recompute (same dict in memory)
    # -- this is what guarantees Phase 2's "computed once".
    assert cost_to_base(CONN) is cost_to_base(CONN)


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
