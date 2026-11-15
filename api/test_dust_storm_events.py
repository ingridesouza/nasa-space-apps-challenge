"""Tests for the 2018 global dust storm alert -- see dust_storm_events.py
for the full sourcing of every number used here (two real REMS sols
fetched directly by this session: 2082 during the storm, 2060 pre-storm).

Run: cd api && python test_dust_storm_events.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dust_storm_events as dse
from alerts import sol_time_and_alerts


def test_sol_outside_the_real_event_has_no_level():
    assert dse.alert_level(4650) is None
    assert dse.alert_level(242) is None


def test_confirmed_storm_sol_is_danger():
    assert dse.alert_level(dse.CONFIRMED_SOL) == "danger"


def test_range_boundaries_are_inclusive():
    lo, hi = dse.EVENT_SOL_RANGE
    assert dse.alert_level(lo) == "danger"
    assert dse.alert_level(hi) == "danger"
    assert dse.alert_level(lo - 1) is None
    assert dse.alert_level(hi + 1) is None


def test_known_event_returns_none_outside_the_range():
    assert dse.known_event(4650) is None
    assert dse.known_event(dse.CONFIRMED_SOL) is not None


def test_conditions_alert_fires_on_the_real_storm_sol():
    # End-to-end: sol_time_and_alerts is what /api/conditions calls.
    _, alerts = sol_time_and_alerts(dse.CONFIRMED_SOL)
    storm_alerts = [a for a in alerts if a["type"] == "dust_storm_event"]
    assert len(storm_alerts) == 1
    assert storm_alerts[0]["level"] == "danger"
    assert "46" in storm_alerts[0]["message"]  # diurnal_range_c, 45.8 C rounds to 46


def test_normal_sol_has_no_dust_storm_event_alert():
    _, alerts = sol_time_and_alerts(4650)
    assert not [a for a in alerts if a["type"] == "dust_storm_event"]


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
