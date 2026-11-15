"""Answer card (F08): the structured answer shown in the dynamic card during the walk.

Fixed rules build every block from local data (alerts, DTM, THEMIS, rover history,
REMS/RAD, forecast, route); the model only writes the answer line. So the card exists
even when the model is down, and no number on it comes from the model.
See docs/feature-08-cartao-resposta.md.

Blocks: verdict (by rule), facts (2-4, each with source and confidence), options
(route variants, astronaut decides), target (science card, science questions only),
missing (what was needed and is not in the system)."""

import re

from alerts import NO_HISTORY_RADIUS_M, load_stops
from geo import bearing, compass, haversine_m

# Order matters: the first match wins ("is radiation safe?" is environment, not terrain).
INTENTS = [
    ("route", r"\b(which|what|best|safest|fastest|shortest)\b.*\broute\b|\broute\b.*\b(take|choose|best|safest|fastest)\b"),
    ("environment", r"\b(radiation|dose|weather|temperature|cold|hot|pressure|wind|dust|storm|uv|humidity|forecast|climate)\b"),
    ("resources", r"\b(oxygen|o2|how long|turn back|return|get back|base|how far|distance|deadline|window|minutes|time left)\b"),
    ("terrain_here", r"\b(climb|go up|go down|descend|cross|walk|pass|slope|steep|safe|ground|terrain|sand|slip\w*|step|stable)\b"),
    ("science", r"\b(rock|mineral\w*|sample|target|drill\w*|science|scientific|ridge|boxwork|crism|measured|geolog\w*|what is (this|that|here))\b"),
]
INTENT_LABEL = {"terrain_here": "Terrain here", "resources": "Time and return", "environment": "Environment",
                "science": "Science here", "route": "Route choice", "distress": "Distress", "other": "Point",
                "replan": "Problem on the way"}
# alert types that decide the verdict of each intent (the others stay out of the card)
VERDICT_TYPES = {
    "terrain_here": {"slope", "historical_terrain", "no_history", "predicted_risk"},
    "resources": {"return_to_base"},
    "environment": {"stale_data", "dust_season"},
    "other": {"slope", "historical_terrain", "no_history", "predicted_risk", "return_to_base"},
}
VERDICT = {"danger": ("stop", "STOP"), "caution": ("caution", "CAUTION")}
ROUTE_NAME = {"safest": "Safest", "fastest": "Fastest", "most_science": "Most science"}
DUST_SOURCE = "Mars24 (Ls, NASA GISS) + seasonal dust pattern from MCS/MRO (NASA/JPL)"  # same as alerts.py
SPOKEN_HEADING = {"N": "north", "NE": "northeast", "E": "east", "SE": "southeast",
                  "S": "south", "SW": "southwest", "W": "west", "NW": "northwest"}
MAX_FACTS = 4
# intents about "here": with an open route the API sends the astronaut's position, not the destination
HERE_INTENTS = {"terrain_here", "science", "resources", "other"}


# "what is this rock?" asks what it is; "there is a rock ahead" reports an obstacle (replan.py)
IDENTITY = re.compile(r"\bwhat(\s+is|'s|\s+are|\s+kind|\s+type)\s+(of\s+)?(this|that|these|those|it|the|rock)\b"
                      r"|\bwhat\s+(rock|stone|mineral)\b|\bidentify\b|\bmade of\b|\bmineral", re.I)
BLOCKING = re.compile(r"\b(ahead|blocking|blocked|in the way|in front|on the (path|route)|can'?t pass|cannot pass)\b", re.I)


def asks_identity(question: str) -> bool:
    return bool(IDENTITY.search(question)) and not BLOCKING.search(question) and classify(question) == "science"


def route_text(text: str) -> str:
    """Route alerts were computed at route samples: "from here" there means from the route, not from the astronaut."""
    return text.replace(" from here", " from the route")


def classify(question: str) -> str:
    q = question.lower()
    return next((name for name, rx in INTENTS if re.search(rx, q)), "other")


def _fact(label: str, value: str, source: str, confidence: str, hint: str | None = None) -> dict:
    return {"label": label, "value": value, "source": source, "confidence": confidence, "hint": hint}


def _dedupe(alerts: list[dict]) -> list[dict]:
    """The same rover stop comes back at every route sample: keep the 1st of each message without distances."""
    seen = {}
    for a in alerts:
        seen.setdefault((a["level"], re.sub(r"[\d.,]+ m from (here|the base|the start)", "", a["message"])), a)
    return list(seen.values())


def _verdict(alerts: list[dict], has_data: bool) -> dict:
    """Worst alert decides. No alert is NOT "go": the label says only that no rule fired."""
    hits = [a for a in _dedupe(alerts) if a["level"] in VERDICT]
    hits.sort(key=lambda a: a["level"] != "danger")
    if hits:
        level, label = VERDICT[hits[0]["level"]]
        return {"level": level, "label": label,
                "because": [{"text": a["message"], "source": a["source"]} for a in hits[:2]]}
    if not has_data:
        return {"level": "unknown", "label": "NO DATA", "because": []}
    return {"level": "no_alert", "label": "NO ALERT", "because": [],
            "note": "No rule fired. That does not mean safe."}


def _missing(alerts: list[dict]) -> list[str]:
    return [a["message"] for a in _dedupe(alerts) if a["type"] == "no_data"]


def _base_fact(lat: float, lon: float, base: tuple[float, float]) -> dict:
    d = haversine_m(lat, lon, *base)
    if d < 10:  # a heading from 0 m is noise
        return _fact("Base", "you are at the base", "base position (H2G2, provisional)", "context")
    return _fact("Base", f"{d:,.0f} m · heading {SPOKEN_HEADING[compass(bearing(lat, lon, *base))]}",
                 "base position (H2G2, provisional)", "context")


def _rover_nearby(lat: float, lon: float) -> dict | None:
    stops = load_stops() or []
    near = [(haversine_m(lat, lon, p["lat"], p["lon"]), p) for p in stops]
    near = [x for x in near if x[0] <= NO_HISTORY_RADIUS_M]
    if not near:
        return None
    d, p = min(near, key=lambda x: x[0])
    where = "here" if d < 1 else f"{d:.0f} m away"
    return _fact("Rover measured", f"{p['tilt']:.1f}° tilt · {where} (sol {p['sol']})",
                 "MMGIS MSL_waypoints", "measured")


def _terrain(point: dict) -> tuple[list, list]:
    lat, lon = point["point"]["lat"], point["point"]["lon"]
    r, facts, missing = point["raster_values"], [], []
    if r.get("slope_deg") is not None:
        facts.append(_fact("Map slope", f"{r['slope_deg']:.1f}°", "HiRISE DTM (Mars Trek), mean over ~12 m",
                           "inferred from orbit"))
    sf = point.get("slope_forecast")
    if sf:
        facts.append(_fact(f"Chance real ground ≥ {sf['limit_deg']}°", f"{sf['chance_pct']}% ({sf['above']} of {sf['n']} stops)",
                           sf["source"], "estimated"))
    rover = _rover_nearby(lat, lon)
    if rover:
        facts.append(rover)
    else:
        missing.append(f"No Curiosity stop within {NO_HISTORY_RADIUS_M} m")
    ti = point.get("thermal_inertia")
    if ti:
        facts.append(_fact("Thermal inertia", f"{ti['value']} {ti['unit']}", ti["source"], ti["confidence"],
                           "higher = rock or cemented ground; lower = loose material (100 m cell)"))
    else:
        missing.append("Thermal inertia (THEMIS) at this point")
    return facts, missing


def _resources(point: dict, rf: dict | None, base: tuple[float, float]) -> tuple[list, list]:
    lat, lon = point["point"]["lat"], point["point"]["lon"]
    facts, missing = [_base_fact(lat, lon, base)], []
    if rf and "error" not in rf:
        facts.append(_fact("Open route", f"{rf['distance_m']:,.0f} m · ~{rf['estimated_time_min']:.0f} min one way",
                           "A* over the HiRISE DTM", "estimated"))
        w = (rf.get("climate") or {}).get("eva_window")
        if w:
            facts.append(_fact("EVA window", f"{w['start_lmst']}–{w['end_lmst']} LMST (local mean solar time)",
                               rf["climate"]["source"], "estimated"))
        d = rf.get("dose")
        if d:
            facts.append(_fact("Radiation on the walk", f"{d['value_ugy']} µGy" + (f" ±{d['error_ugy']}" if d["error_ugy"] else ""),
                               d["source"], "estimated"))
        else:
            missing.append("Radiation dose for the walk (no RAD forecast)")
    else:
        missing.append("No open route: no time estimate")
    missing.append("Suit oxygen level (not reported to the system)")
    return facts, missing


def _environment(conditions: dict | None) -> tuple[list, list]:
    if not conditions:
        return [], ["REMS/RAD conditions for this sol"]
    rems, rad, sol = conditions.get("rems") or {}, conditions.get("rad") or {}, conditions["sol"]
    facts, missing = [], []
    if rems.get("temp_min_c") is not None and rems.get("temp_max_c") is not None:
        facts.append(_fact("Air temperature", f"{rems['temp_min_c']} to {rems['temp_max_c']} °C", f"REMS sol {sol}", "measured"))
    else:
        missing.append("Air temperature")
    if rems.get("pressure_pa") is not None:
        facts.append(_fact("Pressure (sol mean)", f"{rems['pressure_pa']} Pa", f"REMS sol {sol}", "measured"))
    if rad.get("estimated_dose_ugy_per_day") is not None:
        facts.append(_fact("Radiation", f"{rad['estimated_dose_ugy_per_day']} µGy/day", f"MSL RAD sol {sol} (mean hourly dose × 24)", "estimated"))
    else:
        missing.append("Radiation (RAD)")
    fc = conditions.get("today_forecast")
    if fc and fc.get("temp_min_c") and fc.get("temp_max_c"):
        facts.append(_fact(f"Forecast sol {fc['sol']}", f"{fc['temp_min_c']['value']} to {fc['temp_max_c']['value']} °C",
                           fc["method"], "estimated"))
    else:
        missing.append("Forecast for today")
    return facts, missing


def _row_source(row: dict) -> str:
    """instrument · PDS file; the file can be empty when the row only has a URL (shown as text, never fetched)."""
    return " · ".join(x for x in (row.get("instrument"), row.get("source_file") or row.get("source_url")) if x)


def _science(point: dict, card: dict | None) -> tuple[list, list]:
    facts, missing = [], []
    if not card or not card.get("target"):
        missing.append((card or {}).get("message") or "Science target near this point")
    else:
        t = card["target"]
        facts.append(_fact("Target", f"{t['name']} · {t['distance_label']}", "Curiosity team target name", "context"))
        for sec, label in (("mineralogy", "Mineralogy"), ("chemistry", "Chemistry")):
            row = next((r for r in card["rows"] if r["section"] == sec), None)
            if row:
                facts.append(_fact(label, row["text"], _row_source(row), row["confidence"]))
    orbit = next((r for r in (card or {}).get("rows", []) if r["section"] == "orbit"), None)
    if orbit:
        facts.append(_fact("From orbit", orbit["text"], _row_source(orbit), orbit["confidence"]))
    return facts, missing


def _route(rf: dict | None) -> tuple[list, list, list, list]:
    """facts, options, missing, alerts for the verdict."""
    if not rf or "error" in rf:
        return [], [], ["No open route to compare" if not rf else f"No route forecast: {rf['error']}"], []
    sg = rf.get("suggestion") or {}
    options = [{"n": i + 1, "type": s["type"], "name": ROUTE_NAME.get(s["type"], s["type"]), "status": s["label"],
                "why": route_text(s["why"]), "suggested": s["type"] == sg.get("suggested")} for i, s in enumerate(sg.get("summary", []))]
    facts = [_fact("Open route", f"{ROUTE_NAME.get(rf['type'], rf['type'])} · {rf['distance_m']:,.0f} m · ~{rf['estimated_time_min']:.0f} min",
                   "A* over the HiRISE DTM", "estimated")]
    w = rf["terrain"].get("worst_segment")
    if w:
        facts.append(_fact("Worst segment", f"{w['distance_m']:,.0f} m from the start · map {w['map_slope_deg']}° · {w['chance_pct']}% chance ≥ {rf['terrain']['limit_deg']}°",
                           rf["terrain"]["source"], "estimated"))
    if sg.get("dust_warning"):
        facts.append(_fact("Season", sg["dust_warning"], DUST_SOURCE, "context"))
    alerts = [{**a, "message": route_text(a["message"])} for a in rf.get("alerts", [])]
    return facts, options, [], alerts


def replan(res: dict, origin: tuple[float, float], base: tuple[float, float], origin_source: str) -> dict:
    """Card for a problem reported mid-walk (/api/replan output). The options are the new A* routes;
    the system only orders them, the astronaut chooses."""
    sg = res["suggestion"]
    by_type = {r["type"]: r for r in res["routes"]}
    options = []
    for i, s in enumerate(sg.get("summary", [])):
        r = by_type[s["type"]]
        options.append({"n": i + 1, "type": s["type"], "name": r.get("title", s["type"]).capitalize(), "status": s["label"],
                        "why": f"{r['distance_m']:,.0f} m · ~{r['estimated_time_min']:.0f} min · {route_text(s['why'])}",
                        "suggested": s["type"] == sg.get("suggested")})
    facts = [_fact("Start of the options", f"lat {origin[0]:.5f}, lon {origin[1]:.5f}", origin_source, "context")]
    ob = res.get("obstacle")
    if ob:
        facts.append(_fact("Obstacle avoided", f"{ob['radius_m']} m circle around lat {ob['lat']:.5f}, lon {ob['lon']:.5f}",
                           "placed from the report, not measured (H2G2 replan rule)", "assumed"))
    facts.append(_base_fact(*origin, base))
    if sg.get("dust_warning"):
        facts.append(_fact("Season", sg["dust_warning"], DUST_SOURCE, "context"))
    verdict = {"level": "caution", "label": "REPLAN",
               "because": [{"text": res["problem_text"], "source": "astronaut report · H2G2 replan rule"}],
               "note": "Options computed by A* over the HiRISE DTM. You decide."}
    return {"intent": "replan", "title": INTENT_LABEL["replan"], "verdict": verdict, "facts": facts[:MAX_FACTS],
            "options": options, "target": None, "missing": res.get("warnings", []), "answer": None}


def build(question: str, point: dict, conditions: dict | None, route_forecast: dict | None,
          science: dict | None, base: tuple[float, float], intent: str | None = None,
          position_source: str = "point asked about") -> dict:
    """science: /science/card output (only needed for the science intent; None otherwise)."""
    intent = intent or classify(question)
    lat, lon = point["point"]["lat"], point["point"]["lon"]
    alerts, options, target = point["alerts"], [], None
    if intent == "distress":
        r = point["raster_values"]
        facts = [_fact("Position", f"lat {lat:.5f}, lon {lon:.5f}", position_source, "context"),
                 _base_fact(lat, lon, base)]
        if r.get("slope_deg") is not None:
            facts.insert(1, _fact("Map slope", f"{r['slope_deg']:.1f}°", "HiRISE DTM (Mars Trek), mean over ~12 m", "inferred from orbit"))
        verdict = {"level": "stop", "label": "STOP", "because": [{"text": "Stop and check the suit. Tell the base now.",
                                                                  "source": "H2G2 team procedure (no NASA checklist yet)"}]}
        return {"intent": intent, "title": INTENT_LABEL[intent], "verdict": verdict, "facts": facts,
                "options": [], "target": None, "missing": [], "answer": None}
    if intent == "terrain_here":
        facts, missing = _terrain(point)
    elif intent == "resources":
        facts, missing = _resources(point, route_forecast, base)
        alerts = alerts + [a for a in (route_forecast or {}).get("alerts", []) if a["type"] == "return_to_base"]
    elif intent == "environment":
        facts, missing = _environment(conditions)
        alerts = (conditions or {}).get("alerts", [])
    elif intent == "science":
        facts, missing = _science(point, science)
        target = science if science and (science.get("target") or science.get("rows")) else None
    elif intent == "route":
        facts, options, missing, alerts = _route(route_forecast)
    else:
        facts, missing = _terrain(point)
        facts = facts[:2] + [_base_fact(lat, lon, base)]

    if intent == "science":
        verdict = None  # a science answer is information, not a go/no-go
    else:
        types = VERDICT_TYPES.get(intent)
        relevant = [a for a in alerts if types is None or a["type"] in types]
        # terrain without the map slope: the slope rules could not run, so silence is NO DATA, not NO ALERT
        no_slope = intent in ("terrain_here", "other") and point["raster_values"].get("slope_deg") is None
        verdict = _verdict(relevant, has_data=bool(facts) and not no_slope)
    missing += [m for m in _missing(point["alerts"]) if intent in ("terrain_here", "other")]
    return {"intent": intent, "title": INTENT_LABEL[intent], "verdict": verdict, "facts": facts[:MAX_FACTS],
            "options": options, "target": target, "missing": list(dict.fromkeys(missing)), "answer": None}
