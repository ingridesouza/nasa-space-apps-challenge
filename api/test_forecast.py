"""Tests for the local forecast (feature 06).

Run: make test   (or: cd api && python test_forecast.py)"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import forecast
from mars_time import ls, sol_date


def _synthetic_climate():
    """Pure season (cosine of Ls) + a +5 step from sol 1500 (the rover climbed)."""
    out = []
    for sol in range(20, 2001, 20):
        l = ls(sol_date(sol))
        t = -70 + 10 * math.cos(math.radians(l)) + (5 if sol >= 1500 else 0)
        # day peaking at 14h (LMST), as REMS shows
        hourly = {str(h): t + 30 + 30 * math.cos(2 * math.pi * (h - 14) / 24) for h in range(24)}
        out.append({"sol": sol, "ls": round(l, 1), "temp_min_c": t, "temp_max_c": t + 60,
                    "pressure_pa": 800 + 50 * math.cos(math.radians(l)), "hourly_temp": hourly,
                    "dose_ugy_day": 200 - 8 * math.cos(math.radians(l)) - (30 if sol >= 1500 else 0)})
    return out


def test_season_plus_anomaly_reproduces_the_synthetic():
    climate = _synthetic_climate()
    base = next(c for c in climate if c["sol"] == 1900)
    p = forecast.predict(climate, 1960, base)
    real = next(c for c in climate if c["sol"] == 1960)
    for k in forecast.FIELDS:
        # the ±15° Ls window smooths the curve: up to ~1% of the seasonal amplitude
        assert abs(p[k]["value"] - real[k]) < 2.0, (k, p[k], real[k])


def test_dose_repeats_the_last_measured_sol():
    climate = _synthetic_climate()
    base = next(c for c in climate if c["sol"] == 1900)
    assert forecast.predict(climate, 1960, base)["dose_ugy_day"]["value"] == round(base["dose_ugy_day"], 1)


def test_no_previous_year_does_not_invent():
    climate = _synthetic_climate()
    base = next(c for c in climate if c["sol"] == 200)  # nothing before 200 - 100 sols in the same season
    assert all(forecast.predict(climate, 220, base)[k] is None for k in forecast.FIELDS)


def test_eva_window_picks_the_warmest_hours():
    climate = _synthetic_climate()
    base = next(c for c in climate if c["sol"] == 1900)
    j = forecast.eva_window(climate, 1960, base, duration_min=150)  # 2h30 -> 3 hours
    assert j["hours"] == 3 and j["start_lmst"] == "13:00" and j["end_lmst"] == "16:00", j
    # no curve on the base sol (habitat measurement): corrects by the daily mean, the window stays the same
    j2 = forecast.eva_window(climate, 1960, {**base, "hourly_temp": {}}, 150)
    assert (j2["start_lmst"], j2["end_lmst"]) == ("13:00", "16:00"), j2
    assert forecast.eva_window([], 1960, {**base, "hourly_temp": {}}, 60) is None  # no history: does not invent


def test_slope_chance_from_history():
    tab = forecast.table_from([(12.0, 16.0), (12.0, 11.0), (13.0, 18.0), (12.5, 9.0), (5.0, 6.0)])
    r = forecast.slope_risk(12.0, tab)
    assert (r["above"], r["n"], r["chance_pct"], r["map_range"]) == (2, 4, 50, "10–15°")
    assert forecast.slope_risk(None, tab) is None
    assert forecast.slope_risk(16.0, tab) is None  # no stop in this range: does not invent


def test_local_measurement_becomes_base_and_divergence_warns():
    import json
    import tempfile

    if forecast.load_climate() is None:
        print("skipped: run data-pipeline/scripts/cache_climatology.py")
        return
    with tempfile.TemporaryDirectory() as d:
        climate_p, local_p = f"{d}/climate.json", f"{d}/local.json"
        Path(climate_p).write_text(json.dumps({"sols": _synthetic_climate()}))
        normal = next(c for c in _synthetic_climate() if c["sol"] == 1980)
        m = forecast.record_measurement({"sol": 1990, "temp_min_c": normal["temp_min_c"] + 25,
                                         "temp_max_c": normal["temp_max_c"], "pressure_pa": normal["pressure_pa"]}, local_p)
        climate = forecast.load_climate(climate_p, local_p)
        assert forecast._base_for(climate, 1999)["origin"] == "local"  # the habitat data becomes the base
        div = forecast.divergence(climate, m)
        assert [x["field"] for x in div] == ["temp_min_c"] and div[0]["difference"] > 20
        assert forecast.delete_measurement(1990, local_p) and forecast.load_local(local_p) == []


def test_backtest_with_real_data():
    if forecast.load_climate() is None:
        print("skipped: run data-pipeline/scripts/cache_climatology.py")
        return
    # half a Martian year ahead: the season has to beat "repeat the latest data"
    assert forecast.sol_forecast(4650)["earth_date"] == "2025-09-04"
    b = forecast.backtest(330)
    for k in ("temp_min_c", "pressure_pa"):
        assert b[k]["mean_error"] < b[k]["persistence_error"], (k, b[k])


if __name__ == "__main__":
    for name, t in list(globals().items()):
        if name.startswith("test_"):
            t()
            print(f"ok  {name}")
