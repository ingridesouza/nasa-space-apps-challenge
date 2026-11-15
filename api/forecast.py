"""Feature 06: offline local forecast of the Gale climate (REMS).

Method (base cited in the plan: de Cabo-García et al. 2019; here the minimal
version): the Mars climate repeats a lot from year to year in the same season.
  forecast(sol) = climatology(Ls of the sol) + anomaly of the latest data
  anomaly       = observed(base sol) - climatology(Ls of the base sol)
Climatology = mean of sols from other years with Ls within LS_WINDOW degrees.
The anomaly also absorbs the rover's climb up Mount Sharp (pressure drops
with altitude). Band = standard deviation of the climatology. Error measured by
backtest on the data itself, with the same horizon.

Reads only data/local/conditions/climatology.json (cache_climatology.py)."""

import json
import math
import os
from functools import lru_cache
from statistics import mean, pstdev

from mars_time import ls, sol_date

CLIMATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "conditions", "climatology.json")
FIELDS = ("temp_min_c", "temp_max_c", "pressure_pa")  # air climate: they define the base sol
# Also forecast by the same method: ground at noon (REMS/GTS) and daily dose (RAD).
# The dose changes with the season (air column) and with the solar cycle (slow: the anomaly carries it).
# A solar storm (SPE) cannot be forecast: it is an hours-long spike, with no warning in the local data.
FORECAST_FIELDS = FIELDS + ("ground_noon_c", "dose_ugy_day")
# Backtest (231 sols): for the dose, season + anomaly errs MORE than repeating the last sol
# (20 sols: 9.5 × 7.5 µGy/day; 330 sols: 32.8 × 24.2). What drives it is the 11-year solar cycle,
# not the Martian season -- so the forecast dose is the one from the last measured sol.
PERSISTENCE = ("dose_ugy_day",)
LS_WINDOW = 15.0
SAME_PERIOD_SOLS = 100  # stays out of the climatology: it is the "now" of the anomaly


@lru_cache(maxsize=4)
def load_climate(path: str = CLIMATE_PATH, local_path: str | None = None) -> list[dict] | None:
    """PDS series + local measurements (habitat/suit sensor). The local one wins on the same sol."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        by_sol = {c["sol"]: c for c in json.load(f)["sols"]}
    for m in load_local(local_path or LOCAL_PATH):
        by_sol[m["sol"]] = {**by_sol.get(m["sol"], {}), **m}
    return [by_sol[s] for s in sorted(by_sol)]


# --------------------------------------------------------------------------- #
# Local measurements: on Mars new data comes from the habitat sensor, not from Earth.
# Each one becomes the "last measured sol" and the forecast corrects itself, offline.
# --------------------------------------------------------------------------- #
LOCAL_PATH = os.path.join(os.path.dirname(CLIMATE_PATH), "local_measurements.json")


def load_local(path: str = LOCAL_PATH) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_local(local: list[dict], path: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(local, key=lambda m: m["sol"]), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)  # atomic swap: never leaves the file half-written
    load_climate.cache_clear()
    backtest.cache_clear()


def record_measurement(m: dict, path: str = LOCAL_PATH) -> dict:
    entry = {"sol": m["sol"], "ls": round(ls(sol_date(m["sol"])), 1), "origin": "local",
             **{k: m[k] for k in FORECAST_FIELDS if m.get(k) is not None}}
    _save_local([x for x in load_local(path) if x["sol"] != m["sol"]] + [entry], path)
    return entry


def delete_measurement(sol: int, path: str = LOCAL_PATH) -> bool:
    local = load_local(path)
    remaining = [x for x in local if x["sol"] != sol]
    if len(remaining) == len(local):
        return False
    _save_local(remaining, path)
    return True


def _ls_dist(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _climatology(climate: list[dict], target_ls: float, field: str, base: int) -> list[float]:
    """Values from other periods in the same season, only with data known at the base sol."""
    return [c[field] for c in climate
            if c.get(field) is not None and c["sol"] <= base - SAME_PERIOD_SOLS
            and _ls_dist(c["ls"], target_ls) <= LS_WINDOW]


def predict(climate: list[dict], sol: int, base: dict) -> dict:
    """Forecast for `sol` from the climatology row `base` (the latest data)."""
    sol_ls = ls(sol_date(sol))
    out = {}
    for field in FORECAST_FIELDS:
        b = _last_with(climate, field, base["sol"])  # a sensor may be missing on the base sol: use the last one with data
        if field in PERSISTENCE:
            out[field] = {"value": round(b[field], 1), "stdev": None, "method": "last measured sol"} if b else None
            continue
        target = _climatology(climate, sol_ls, field, b["sol"]) if b else []
        at_base = _climatology(climate, b["ls"], field, b["sol"]) if b else []
        if not target or not at_base:
            out[field] = None  # no previous year in this season: do not invent
            continue
        anomaly = b[field] - mean(at_base)
        out[field] = {"value": round(mean(target) + anomaly, 1),
                      "stdev": round(pstdev(target), 1) if len(target) > 1 else None}
    return {"sol": sol, "ls": round(sol_ls, 1), **out}


def _last_with(climate: list[dict], field: str, up_to_sol: int) -> dict | None:
    before = [c for c in climate if c["sol"] <= up_to_sol and c.get(field) is not None]
    return before[-1] if before else None


def _base_for(climate: list[dict], sol: int) -> dict | None:
    """Last climatology sol before `sol` with all fields."""
    before = [c for c in climate if c["sol"] <= sol and all(c[k] is not None for k in FIELDS)]
    return before[-1] if before else None


@lru_cache(maxsize=32)
def backtest(horizon: int, path: str = CLIMATE_PATH) -> dict | None:
    """Mean absolute error forecasting already-measured sols `horizon` sols ahead,
    against naive persistence (repeating the latest data)."""
    climate = load_climate(path)
    if not climate:
        return None
    errors = {k: [] for k in FORECAST_FIELDS}
    naive = {k: [] for k in FORECAST_FIELDS}
    for c in climate:
        base = _base_for(climate, c["sol"] - horizon)
        if base is None:
            continue
        p = predict(climate, c["sol"], base)
        for k in FORECAST_FIELDS:
            if p[k] and c.get(k) is not None:
                errors[k].append(abs(p[k]["value"] - c[k]))
                naive[k].append(abs(_last_with(climate, k, base["sol"])[k] - c[k]))
    if not errors["temp_min_c"]:
        return None
    return {"horizon_sols": horizon, "n": len(errors["temp_min_c"]),
            **{k: {"mean_error": round(mean(v), 1), "persistence_error": round(mean(naive[k]), 1)}
               for k, v in errors.items() if v}}


def eva_window(climate: list[dict], sol: int, base: dict, duration_min: float) -> dict | None:
    """Best window of the day for an EVA of `duration_min` (F06 PDF: "couple the forecast
    to the route"). Forecast hourly curve = hourly climatology + mean anomaly of the base sol.
    Best = the window whose coldest hour is the warmest (the suit suffers at the worst moment)."""
    sol_ls = ls(sol_date(sol))
    with_curve = [c for c in climate if c.get("hourly_temp")]

    def hourly_climate(target_ls: float, h: int) -> float | None:
        v = [c["hourly_temp"][str(h)] for c in with_curve
             if c["sol"] <= base["sol"] - SAME_PERIOD_SOLS and _ls_dist(c["ls"], target_ls) <= LS_WINDOW
             and str(h) in c["hourly_temp"]]
        return mean(v) if v else None

    base_curve = base.get("hourly_temp") or {}
    diffs = [base_curve[str(h)] - c for h in range(24)
             if str(h) in base_curve and (c := hourly_climate(base["ls"], h)) is not None]
    if not diffs:
        # a habitat measurement has no hourly curve: correct by the daily mean (min.+max.)/2
        mid = lambda c: (c["temp_min_c"] + c["temp_max_c"]) / 2  # noqa: E731
        normal = [mid(c) for c in with_curve if c["sol"] <= base["sol"] - SAME_PERIOD_SOLS
                  and _ls_dist(c["ls"], base["ls"]) <= LS_WINDOW and c.get("temp_min_c") is not None]
        if not normal or base.get("temp_min_c") is None:
            return None
        diffs = [mid(base) - mean(normal)]
    anomaly = mean(diffs)
    curve = {h: round(c + anomaly, 1) for h in range(24) if (c := hourly_climate(sol_ls, h)) is not None}
    n = min(24, max(1, math.ceil(duration_min / 60)))
    windows = [(min(curve[(i + k) % 24] for k in range(n)), i) for i in range(24)
               if all((i + k) % 24 in curve for k in range(n))]
    if not windows:
        return None
    worst, start = max(windows)
    return {"start_lmst": f"{start:02d}:00", "end_lmst": f"{(start + n) % 24:02d}:00", "hours": n,
            "coldest_temp_in_window_c": worst, "hourly_curve": curve,
            "criterion": "window whose coldest hour is the warmest (forecast air temperature)"}


DIVERGENCE_FACTOR = 3  # a measurement more than 3x the typical error for the horizon = outside the season's normal


def divergence(climate: list[dict], measured: dict) -> list[dict]:
    """Compares a local measurement with what the model forecast for that sol without seeing it."""
    before = _base_for([c for c in climate if c["sol"] != measured["sol"]], measured["sol"] - 1)
    if before is None:
        return []
    p = predict([c for c in climate if c["sol"] != measured["sol"]], measured["sol"], before)
    error = backtest(max(measured["sol"] - before["sol"], 1)) or {}
    out = []
    for k in FORECAST_FIELDS:
        if p.get(k) and measured.get(k) is not None and error.get(k):
            limit = DIVERGENCE_FACTOR * error[k]["mean_error"]
            diff = measured[k] - p[k]["value"]
            if abs(diff) > limit:
                out.append({"field": k, "measured": measured[k], "expected": p[k]["value"],
                            "difference": round(diff, 1), "limit": round(limit, 1)})
    return out


def sol_forecast(sol: int, duration_min: float | None = None) -> dict | None:
    climate = load_climate()
    if not climate:
        return None
    base = _base_for(climate, sol - 1)  # never looks at the sol itself: so it can be compared with the measured one
    if base is None:
        return None
    horizon = sol - base["sol"]
    measured = next((c for c in climate if c["sol"] == sol), None)
    local = next((c for c in (measured, base) if c and c.get("origin") == "local"), None)
    return {
        **predict(climate, sol, base),
        "earth_date": sol_date(sol).date().isoformat(),
        "measured": {k: measured.get(k) for k in FORECAST_FIELDS} if measured else None,
        "eva_window": eva_window(climate, sol, base, duration_min) if duration_min else None,
        "base_sol": base["sol"], "horizon_sols": horizon,
        "base_origin": base.get("origin", "pds"),
        "local_measurement": local and {k: local.get(k) for k in ("sol", *FORECAST_FIELDS)},
        "divergence": divergence(climate, local) if local else [],
        "backtest_error": backtest(max(horizon, 1)),
        "confidence": "estimated",
        "method": "REMS climatology by season (Ls ±15°) + anomaly of the last measured sol",
        "source": "MSL REMS (PDS Atmospheres) + Ls by Mars24",
    }


# --------------------------------------------------------------------------- #
# Real slope from the map, by the rover history
# --------------------------------------------------------------------------- #
# The orbital DTM (~6 m/px) smooths the ridges. At Curiosity's stops we have
# both numbers at the same place: the map's and the one the rover measured (attitude, "tilt").
# The observed frequency becomes the chance that the real terrain exceeds 15° (Artemis).
MAP_RANGES = ((0, 7), (7, 10), (10, 15), (15, 90))
REAL_LIMIT_DEG = 15


def table_from(pairs: list[tuple[float, float]]) -> list[dict]:
    """pairs (map slope, slope measured by the rover) -> frequency per map range."""
    out = []
    for lo, hi in MAP_RANGES:
        measured = [t for s, t in pairs if lo <= s < hi]
        out.append({"from": lo, "to": hi, "n": len(measured),
                    "above": sum(t >= REAL_LIMIT_DEG for t in measured)})
    return out


@lru_cache(maxsize=1)
def slope_table() -> list[dict] | None:
    from alerts import load_stops
    from db import get_connection
    from raster_sampling import sample_all_rasters

    stops = load_stops()
    if not stops:
        return None
    conn = get_connection()
    try:
        # shortcut: ~300 DTM reads on the 1st call (a few seconds); precompute at build time if it gets heavy
        pairs = [(rv["slope_deg"], p["tilt"]) for p in stops
                 if (rv := sample_all_rasters(conn, p["lat"], p["lon"])).get("slope_deg") is not None]
    finally:
        conn.close()
    return table_from(pairs) if pairs else None


def slope_risk(map_slope: float | None, table: list[dict] | None = None) -> dict | None:
    table = table if table is not None else slope_table()
    if map_slope is None or not table:
        return None
    f = next(f for f in table if f["from"] <= map_slope < f["to"])
    if f["n"] == 0:
        return None
    return {"chance_pct": round(100 * f["above"] / f["n"]), "above": f["above"], "n": f["n"],
            "map_range": f"{f['from']}–{f['to']}°" if f["to"] < 90 else f"≥{f['from']}°",
            "limit_deg": REAL_LIMIT_DEG, "confidence": "estimated",
            "method": "frequency at Curiosity stops with the same slope range on the map",
            "source": "MMGIS MSL_waypoints (rover tilt) × HiRISE DTM (Mars Trek)"}


def predicted_status(map_status: str, risk: dict | None) -> str:
    """Status that takes the forecast into account: chance >= 20% becomes caution; >= 50% becomes danger only with
    at least MIN_DANGER_STOPS stops in the range (the >= 15° range has only 5: it stays at caution)."""
    order = ["safe", "caution", "danger"]
    if not risk or risk["chance_pct"] < 20:
        by_chance = "safe"
    elif risk["chance_pct"] >= 50 and risk["n"] >= MIN_DANGER_STOPS:
        by_chance = "danger"
    else:
        by_chance = "caution"
    return max(map_status, by_chance, key=order.index)


MIN_DANGER_STOPS = 20
# color by chance: transparent below 20% (do not clutter the map), amber and red of the verdicts
RISK_COLOR = ((50, (232, 100, 63, 200)), (20, (242, 179, 61, 160)))


@lru_cache(maxsize=1)
def risk_grid_rgba(dtm_path: str):
    """"Slope risk (predicted)" layer: each DTM pixel painted by the historical chance
    that the real terrain exceeds 15°. Returns (rgba[4,h,w], transform, crs)."""
    import numpy as np
    import rasterio

    from geo import MARS_METERS_PER_DEGREE
    from route_planning import _load_dtm, _slope_grid_deg

    elevation, transform, _, _ = _load_dtm(dtm_path)
    slope = _slope_grid_deg(elevation, abs(transform.a) * MARS_METERS_PER_DEGREE)
    rgba = np.zeros((4, *slope.shape), dtype="uint8")
    for f in slope_table() or []:
        if not f["n"]:
            continue
        pct = 100 * f["above"] / f["n"]
        color = next((c for limit, c in RISK_COLOR if pct >= limit and (limit < 50 or f["n"] >= MIN_DANGER_STOPS)), None)
        if color:
            rgba[:, (slope >= f["from"]) & (slope < f["to"])] = np.array(color, dtype="uint8")[:, None]
    with rasterio.open(dtm_path) as ds:
        crs = ds.crs
    return rgba, transform, crs
