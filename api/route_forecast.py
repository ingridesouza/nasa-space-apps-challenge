""""Forecast route" tool (F02 + F06 + F08): predictive analysis of an already
computed route, only with historical NASA data on disk. The backend calls it when
a route is in play and hands the result to the agent.

Gathers, per route and EVA sol:
- terrain: chance that the real ground exceeds 15° on each segment (Curiosity tilt × DTM);
- rover history near the path and return-to-base radius (route_alerts);
- forecast climate on the EVA sol and the best window for the walk duration (REMS);
- forecast dose during the walk (RAD of the last measured sol × time).
Everything is an estimate: each block carries method, source and the error measured in the past."""

from forecast import backtest, sol_forecast
from mars_time import SOL_S

CHANCE_BANDS = (("low", 0, 20), ("medium", 20, 50), ("high", 50, 101))  # same cuts as predicted_status


def terrain(route: dict) -> dict:
    """Route meters per chance band and the worst segment, with the distance from the start."""
    profile = route["elevation_profile"]  # profile[i + 1] closes segment i
    meters = {name: 0.0 for name, _, _ in CHANCE_BANDS} | {"no_data": 0.0}
    worst = None
    for i, seg in enumerate(route["risk_segments"]):
        d = profile[i + 1]["cumulative_distance_m"] - profile[i]["cumulative_distance_m"]
        c = seg.get("chance_pct")
        band = "no_data" if c is None else next(n for n, lo, hi in CHANCE_BANDS if lo <= c < hi)
        meters[band] += d
        if c is not None and (worst is None or (c, seg["slope_deg"]) > (worst["chance_pct"], worst["map_slope_deg"])):
            worst = {"chance_pct": c, "map_slope_deg": seg["slope_deg"], "predicted_status": seg.get("predicted_status"),
                     "distance_m": round(profile[i]["cumulative_distance_m"])}
    return {"meters_by_chance": {k: round(v) for k, v in meters.items()}, "worst_segment": worst,
            "limit_deg": 15, "confidence": "estimated",
            "method": "frequency, at Curiosity stops, of the rover measuring ≥15° with the map in the same range",
            "source": "MMGIS MSL_waypoints (rover tilt) × HiRISE DTM (Mars Trek)"}


def dose(route: dict, fc: dict | None) -> dict | None:
    d = fc and fc.get("dose_ugy_day")
    if not d:
        return None  # no RAD in the cache: do not fake zero
    hours = route["estimated_time_min"] / 60
    error = (backtest(max(fc["horizon_sols"], 1)) or {}).get("dose_ugy_day")
    per_hour = d["value"] / (SOL_S / 3600)
    return {"value_ugy": round(per_hour * hours, 1), "hours": round(hours, 2),
            "error_ugy": round(error["mean_error"] / (SOL_S / 3600) * hours, 1) if error else None,
            "confidence": "estimated", "method": f"daily dose ({d['method']}) × walking time",
            "source": "MSL RAD (PDS)"}


def forecast_route(route: dict, sol: int) -> dict:
    """`route`: one variant of /api/route (already with chance_pct and alerts per segment)."""
    fc = sol_forecast(sol, route["estimated_time_min"])
    climate = fc and {
        "base_sol": fc["base_sol"], "horizon_sols": fc["horizon_sols"],
        **{k: fc[k] for k in ("temp_min_c", "temp_max_c", "pressure_pa", "ground_noon_c")},
        "eva_window": fc["eva_window"], "backtest_error": fc["backtest_error"],
        "method": fc["method"], "source": fc["source"], "confidence": "estimated"}
    return {"type": route["type"], "eva_sol": sol, "distance_m": route["distance_m"],
            "estimated_time_min": route["estimated_time_min"],
            "terrain": terrain(route), "alerts": route.get("alerts", []),
            "climate": climate, "dose": dose(route, fc)}
