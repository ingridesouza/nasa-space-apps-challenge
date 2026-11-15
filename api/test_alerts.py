"""Tests for the rules in api/alerts.py with real points from the repo.

Run: make test   (or: cd api && python test_alerts.py)
Needs data/local/rover_waypoints.json (make build)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alerts import point_alerts

# The map says "safe" and knows nothing about sand -- it is the case the terrain
# memory exists to catch.
SAFE_MAP = {"slope_deg": 11.0, "slope_status": "safe", "ai4mars_class": None}
SOL_4309 = (-4.78679146, 137.4076395)  # rover measured 22.37°, 2,029 m from the provisional base
SOL_4970 = (-4.82096424, 137.3856038)  # rover measured 24.02°, 901 m from the provisional base


def types(alerts):
    return {a["type"]: a for a in alerts}


def test_terrain_memory_and_return_to_base():
    a = types(point_alerts(*SOL_4309, SAFE_MAP))
    assert a["historical_terrain"]["level"] == "danger"
    assert "22.4°" in a["historical_terrain"]["message"] and "sol 4309" in a["historical_terrain"]["message"]
    assert a["return_to_base"]["level"] == "danger"
    assert "slope" not in a  # the map said 11°: the history is what warns


def test_terrain_without_return_to_base():
    a = types(point_alerts(*SOL_4970, SAFE_MAP))
    assert "24.0°" in a["historical_terrain"]["message"]
    assert "return_to_base" not in a


def test_map_slope():
    near_base = (-4.8068928, 137.3798418)
    caution = types(point_alerts(*near_base, {"slope_deg": 15.0, "slope_status": "caution"}))
    danger = types(point_alerts(*near_base, {"slope_deg": 20.0, "slope_status": "danger"}))
    assert caution["slope"]["level"] == "caution"
    assert danger["slope"]["level"] == "danger"


def test_outside_bbox_no_data():
    alerts = point_alerts(-4.59, 137.44, {"slope_deg": None, "slope_status": None, "ai4mars_class": None})
    assert any(a["type"] == "no_data" and "slope" in a["message"] for a in alerts)
    assert any("sand" in a["message"] for a in alerts)


def test_steep_stop_between_25_and_100_m_becomes_caution():
    a = types(point_alerts(-4.7863, 137.4076, SAFE_MAP))  # ~50 m from the 22.4° stop (sol 4309)
    assert a["historical_terrain"]["level"] == "caution" and "22.4°" in a["historical_terrain"]["message"]


def test_forecast_becomes_alert_when_map_says_safe():
    a = types(point_alerts(-4.8150, 137.3750, SAFE_MAP))  # map 11°: the 10–15° range of the history
    assert a["predicted_risk"]["level"] == "caution" and "%" in a["predicted_risk"]["message"]
    flat = {"slope_deg": 5.0, "slope_status": "safe", "ai4mars_class": None}
    assert "predicted_risk" not in types(point_alerts(-4.8150, 137.3750, flat))


def test_area_without_rover_history():
    unexplored = (-4.8150, 137.3750)  # inside the map, far from Curiosity's track
    a = types(point_alerts(*unexplored, SAFE_MAP))
    assert a["no_history"]["level"] == "caution" and "100 m" in a["no_history"]["message"]
    assert "no_history" not in types(point_alerts(*SOL_4309, SAFE_MAP))  # on the rover's track
    no_map = {"slope_deg": None, "slope_status": None, "ai4mars_class": None}
    assert "no_history" not in types(point_alerts(*unexplored, no_map))  # "no slope" already warns


def test_order_by_severity():
    levels = [a["level"] for a in point_alerts(*SOL_4309, SAFE_MAP)]
    assert levels == sorted(levels, key=["danger", "caution", "info"].index)


def test_no_stops_file():
    alerts = point_alerts(*SOL_4309, SAFE_MAP, waypoints_path="/does/not/exist.json")
    assert any("Rover history unavailable" in a["message"] for a in alerts)



def test_mars_time_against_references():
    from datetime import datetime, timezone

    from mars_time import ls, sol_date, sol_msl

    # Mars24 worked example: 6 Jan 2000 0h UTC -> Ls 277.18758°
    assert abs(ls(datetime(2000, 1, 6, tzinfo=timezone.utc)) - 277.18758) < 0.001
    # real dates of F03 bundle panoramas (date only, no time: tolerates 1 day)
    for sol, date in ((4552, "2025-05-27"), (4647, "2025-09-02"), (4816, "2026-02-22")):
        assert abs((sol_date(sol).date() - datetime.fromisoformat(date).date()).days) <= 1
        assert abs(sol_msl(datetime.fromisoformat(date + "T12:00+00:00")) - sol) <= 1


def test_no_earth_mode_age_and_dust():
    from datetime import datetime, timezone

    from alerts import sol_time_and_alerts
    from mars_time import sol_date

    time_info, alerts = sol_time_and_alerts(4650, now=sol_date(4650))
    assert time_info["data_age_sols"] == 0 and not any(a["type"] == "stale_data" for a in alerts)
    _, alerts = sol_time_and_alerts(4650, now=sol_date(4660))
    assert any(a["type"] == "stale_data" and "10 sols" in a["message"] for a in alerts)
    # 2026-11-14: Ls ~22° (out of season); sol 4650 (Sep/2025): Ls ~135° (out as well)
    _, alerts = sol_time_and_alerts(4650, now=datetime(2026, 11, 14, tzinfo=timezone.utc))
    assert not any(a["type"] == "dust_season" for a in alerts)
    _, alerts = sol_time_and_alerts(4650, now=datetime(2026, 5, 1, tzinfo=timezone.utc))
    assert any(a["type"] == "dust_season" for a in alerts)


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
