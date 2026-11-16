"""Tests for the O2-margin addition (Phase 3, route_planning.py) on top
of the terrain/alert-based label that route_suggestions.py already
computed -- see _margin_cons/_margin_label docstrings for the criteria.

Run: cd api && python test_route_suggestions.py
Uses synthetic routes (no DTM or database needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from route_suggestions import suggest


def _route(kind, margin_pct=None, worst_no_return=False, distance_m=100.0, time_min=30.0):
    min_margin = None if margin_pct is None else {"liters": 1.0, "pct": margin_pct, "distance_m": distance_m}
    worst_emergency_segment = {
        "lat": 0, "lon": 0, "distance_m": distance_m,
        "return_minutes": None if worst_no_return else 5.0,
        "return_o2_l": None if worst_no_return else 0.5,
    }
    return {
        "type": kind,
        "distance_m": distance_m,
        "estimated_time_min": time_min,
        "risk_segments": [{"slope_status": "safe", "predicted_status": "safe"}],
        "elevation_profile": [{"cumulative_distance_m": 0.0}, {"cumulative_distance_m": distance_m}],
        "alerts": [],
        "min_margin": min_margin,
        "worst_emergency_segment": worst_emergency_segment,
        "science_target": None,
    }


def test_negative_margin_with_no_terrain_risk_still_becomes_danger():
    routes = [_route("fastest", margin_pct=-20.0)]
    suggest(routes)
    assert routes[0]["suggestion"]["label"] == "danger"
    assert "O2 margin" in routes[0]["suggestion"]["cons"][0]["text"]


def test_margin_between_15_and_30_becomes_caution_not_danger():
    routes = [_route("fastest", margin_pct=25.0)]
    suggest(routes)
    assert routes[0]["suggestion"]["label"] == "caution"


def test_margin_above_30_does_not_touch_the_safe_label():
    routes = [_route("fastest", margin_pct=80.0)]
    suggest(routes)
    assert routes[0]["suggestion"]["label"] == "ok"
    texts = [p["text"] for p in routes[0]["suggestion"]["pros"]]
    assert any("O2 margin" in t for t in texts)


def test_no_o2_given_does_not_force_the_label_down():
    routes = [_route("fastest", margin_pct=None)]
    suggest(routes)
    assert routes[0]["suggestion"]["label"] == "ok"
    assert routes[0]["suggestion"]["cons"] == []


def test_unreachable_return_point_becomes_danger_even_with_good_margin():
    routes = [_route("fastest", margin_pct=90.0, worst_no_return=True)]
    suggest(routes)
    assert routes[0]["suggestion"]["label"] == "danger"
    assert "not computable" in routes[0]["suggestion"]["cons"][0]["text"]


def test_terrain_danger_wins_even_with_good_margin():
    # a "danger" segment by terrain, but good O2 margin -- label still
    # has to be danger (the worse of the two criteria wins).
    route = _route("fastest", margin_pct=90.0)
    route["risk_segments"] = [{"slope_status": "danger", "predicted_status": "danger"}]
    suggest([route])
    assert route["suggestion"]["label"] == "danger"


def test_two_routes_in_danger_by_terrain_tie_break_by_higher_margin():
    routes = [
        _route("safest", margin_pct=20.0),
        _route("fastest", margin_pct=50.0),
    ]
    for r in routes:
        r["risk_segments"] = [{"slope_status": "danger", "predicted_status": "danger"}]
    result = suggest(routes)
    assert result["order"][0] == "fastest"  # higher margin between the two in danger


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
