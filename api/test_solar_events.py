"""Tests for the solar particle event (SPE) alert -- see
docs/feature-05-solar-particle-event.md for the full sourcing of every
number used here.

Run: cd api && python test_solar_events.py
Needs data/local/conditions/sol_242.json and sol_4650.json
(data-pipeline/scripts/cache_conditions.py 242 / 4650)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import solar_events as se
from alerts import sol_time_and_alerts


def test_no_dose_gives_no_level_never_guesses():
    assert se.alert_level(None) is None


def test_background_dose_gives_no_alert():
    assert se.alert_level(se.BACKGROUND_DOSE_UGY_PER_DAY) is None


def test_real_sol_242_event_crosses_caution_not_danger():
    # Real peak reading for sol 242 (fetched directly from PDS-PPI, see
    # solar_events.py docstring): 260.9 uGy/day, ~1.55x the reference
    # background -- above the caution ratio (1.5x), well below danger (3x).
    level = se.alert_level(260.9)
    assert level == "caution"


def test_hypothetical_3x_background_is_danger():
    # Not a real event -- just confirms the danger tier fires at the ratio
    # it is documented to use (anchored to the real Sept-2017 RAD event).
    assert se.alert_level(se.BACKGROUND_DOSE_UGY_PER_DAY * se.DANGER_RATIO) == "danger"


def test_known_event_returns_none_for_an_uncatalogued_sol():
    assert se.known_event(4650) is None
    assert se.known_event(242) is not None


def test_sol_242_conditions_alert_fires_with_real_data():
    # End-to-end: sol_time_and_alerts is what /api/conditions calls.
    _, alerts = sol_time_and_alerts(242, peak_dose_ugy_per_day=260.9)
    solar_alerts = [a for a in alerts if a["type"] == "solar_event"]
    assert len(solar_alerts) == 1
    assert solar_alerts[0]["level"] == "caution"
    assert "2013-04-12" in solar_alerts[0]["message"]
    assert "PDS-PPI" in solar_alerts[0]["source"]


def test_normal_sol_has_no_solar_event_alert():
    _, alerts = sol_time_and_alerts(4650, peak_dose_ugy_per_day=168.5)
    assert not [a for a in alerts if a["type"] == "solar_event"]


def test_no_dose_passed_has_no_solar_event_alert():
    _, alerts = sol_time_and_alerts(242, peak_dose_ugy_per_day=None)
    assert not [a for a in alerts if a["type"] == "solar_event"]


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
