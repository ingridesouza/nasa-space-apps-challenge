"""F02 + F08: orders the /api/route variants and says why.

Fixed rule, not the model (a 4B model gets math wrong and omits danger): the label
comes from the worst predicted status of the segments (F06) and from the agent
alerts on the route (F08); pros and cons only with numbers from the route itself.
No route is hidden or swapped on its own: the suggestion is the order, the
astronaut decides."""

from datetime import datetime

from agent import group_alerts
from alerts import DUST_LS
from mars_time import ls, now

ORDER = ["ok", "caution", "danger"]
NAME = {"safest": "safest", "fastest": "fastest", "most_science": "most science"}
TERRAIN_SOURCE = "HiRISE DTM (Mars Trek) × Curiosity history (MMGIS)"
ROUTE_SOURCE = "A* over the HiRISE DTM (route_planning.py)"


def _meters_by_status(route: dict) -> dict:
    profile = route["elevation_profile"]  # profile[i + 1] closes segment i
    m = {"safe": 0.0, "caution": 0.0, "danger": 0.0}
    for i, seg in enumerate(route["risk_segments"]):
        m[seg.get("predicted_status", seg["slope_status"])] += (
            profile[i + 1]["cumulative_distance_m"] - profile[i]["cumulative_distance_m"])
    return {k: round(v) for k, v in m.items()}


def _evaluate(route: dict, routes: list[dict]) -> dict:
    m = _meters_by_status(route)
    alerts = group_alerts(route.get("alerts", []))
    cons = []  # danger before caution: the 1st con becomes the spoken reason
    for level, text in (("danger", "in danger (20° or more, or high chance from history)"),
                        ("caution", "in caution (15 to 20°, or medium chance from history)")):
        if m[level]:
            cons.append({"text": f"{m[level]} m {text}", "source": TERRAIN_SOURCE})
        cons += [{"text": a["message"], "source": a["source"]} for a in alerts if a["level"] == level]

    pros = []
    if route["distance_m"] == min(r["distance_m"] for r in routes):
        pros.append({"text": f"the shortest: {round(route['distance_m'])} m", "source": ROUTE_SOURCE})
    if route["estimated_time_min"] == min(r["estimated_time_min"] for r in routes):
        pros.append({"text": f"the fastest: ~{round(route['estimated_time_min'])} min one way", "source": ROUTE_SOURCE})
    if not m["danger"] and not m["caution"]:
        pros.append({"text": "no segment above 15° on the map nor with high chance in the history", "source": TERRAIN_SOURCE})
    if route.get("science_target"):
        pros.append({"text": f"passes by the target {route['science_target']['name']}", "source": "science targets (F04)"})

    levels = {a["level"] for a in alerts}
    label = "danger" if m["danger"] or "danger" in levels else "caution" if m["caution"] or "caution" in levels else "ok"
    return {"label": label, "pros": pros, "cons": cons,
            "_key": (ORDER.index(label), m["danger"], m["caution"], route["estimated_time_min"])}


def suggest(routes: list[dict], at: datetime | None = None) -> dict:
    """Writes route["suggestion"] on each variant and returns the overall suggestion (new /api/route field)."""
    for r in routes:
        r["suggestion"] = _evaluate(r, routes)
    order = sorted(routes, key=lambda r: r["suggestion"].pop("_key"))
    best = order[0]
    s, name = best["suggestion"], NAME.get(best["type"], best["type"])
    if s["label"] == "ok":
        reason = f"I suggest the {name} route: " + (s["pros"][0]["text"] if s["pros"] else "no risk segment") + "."
    else:
        all_danger = all(r["suggestion"]["label"] == "danger" for r in routes)
        reason = (f"All {len(routes)} routes have danger; the {name} one has the least. " if all_danger and len(routes) > 1 else
                  f"I suggest the {name} route, the lowest risk of the {len(routes)}. ") + f"Caution: {s['cons'][0]['text']}"
    ls_now = ls(at or now())
    dust = (f"Dust storm season (Ls {ls_now:.0f}°): applies to all routes."
            if DUST_LS[0] <= ls_now < DUST_LS[1] else None)
    return {"suggested": best["type"], "order": [r["type"] for r in order], "reason": reason, "dust_warning": dust,
            "summary": [{"type": r["type"], "label": r["suggestion"]["label"],
                         "why": (r["suggestion"]["cons"] or r["suggestion"]["pros"] or [{"text": "no data"}])[0]["text"]}
                        for r in order],
            "method": "H2G2 fixed rule: worst predicted segment + agent alerts; ties by time",
            "who_decides": "astronaut"}
