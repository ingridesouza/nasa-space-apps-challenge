"""Feature 08, phase 2 -- local agent: answers questions using the point
context (the same JSON as /api/point + REMS/RAD conditions) and, when the model
supports it, tools that fetch more local data (other point, science targets, route).

No embeddings or SDK: the context fits in ~2 KB and goes whole into the prompt. The model runs on the local hardware (Ollama), with no
external network. Alerts come from the rules in alerts.py, never from the model."""

import json
import os
import re
import urllib.error
import urllib.request

from geo import bearing, compass, haversine_m
from route_forecast import CHANCE_BANDS

OLLAMA_URL = os.environ.get("H2G2_OLLAMA_URL", "http://127.0.0.1:11434")
# gemma4:e2b: the only one with 6/6 in measure_agent.py on 11/14 (tool calling + never "safe"; that run had pt/en cases).
# Needs a recent Ollama (Fedora's 0.12.11 does not even load gemma4). A model without tools (gemma3:4b)
# also works: ask() falls back to context-only mode on its own.
MODEL = os.environ.get("H2G2_MODEL", "gemma4:e2b")
TIMEOUT_S = 120  # CPU (i5-8600) can take tens of seconds on the first call

INSTRUCTIONS = """You are H2G2, the assistant of an astronaut in Gale crater, on Mars.
Answer in English, in at most 3 short sentences, to be read aloud.
Use ONLY the data in the CONTEXT below. Cite the source (instrument or file, never a tool name) and the sol when available.
If the context does not have the requested data, answer exactly: "I don't know: I don't have that data here."
Never invent a number, name or position. Never say a place is safe just because there is no alert.
Do not repeat the DANGER alerts: the system already says them before your answer. Never contradict, create or cancel an alert.
If there is a ROUTE FORECAST, use it for questions about the route: say it is an estimate from history
and give the why (segment, chance, distance from the start). If asked which route to take, repeat the SYSTEM SUGGESTION
with the why, without changing the order. Never choose or approve the route on your own: the astronaut decides.
POINT is where the astronaut is now; the ROUTE FORECAST applies to the whole path. Do not mix the two in the same sentence."""


# A distress call does not go through the model: rule-based answer, right away, only with map data.
# spelled out: the answer is spoken aloud
SPOKEN_HEADING = {"N": "north", "NE": "northeast", "E": "east", "SE": "southeast",
                  "S": "south", "SW": "southwest", "W": "west", "NW": "northwest"}
# bare "fall"/"falling" stay out ("the temperature is falling"); "help" too ("can you help me find...").
# Toxic gas on Mars is only a risk if it gets into the suit (a leak): an emergency, not a route forecast.
# Bare "gas" stays out ("what gas is in the atmosphere?").
DISTRESS = re.compile(r"\b(fell|fallen|mayday|sos|hole|stuck|trapped|hurt|injur\w*|emergency|accident|slipp\w*|leak\w*"
                      r"|toxic(\s+\w+)?\s+gas)\b", re.I)


def distress_answer(point: dict, base: tuple[float, float]) -> str:
    """Fixed procedure + position, ground and way back. shortcut: procedure written by the team,
    no NASA source cited; replace with the EVA checklist when available."""
    lat, lon = point["point"]["lat"], point["point"]["lon"]
    r = point["raster_values"]
    sentences = ["Stop and do not move until you check the suit.", f"You are at lat {lat:.5f}, lon {lon:.5f}."]
    if r.get("slope_deg") is None:
        sentences.append("I don't have the slope of this place.")
    else:
        sentences.append(f"The ground here is {r['slope_deg']:.0f}° on the map"
                         + (": above 20°, do not try to climb alone." if r.get("slope_status") == "danger" else "."))
    sentences += [a["message"] for a in group_alerts(point["alerts"]) if a["level"] == "danger"]
    sentences.append(f"The base is {round(haversine_m(lat, lon, *base))} m away, heading {SPOKEN_HEADING[compass(bearing(lat, lon, *base))]}.")
    sentences.append("Tell the base now.")
    return " ".join(sentences)


def strip_repeated_danger(answer: str, dangers: list[dict]) -> str:
    """The system already says the danger before the answer; the 4B model sometimes copies it even though forbidden."""
    answer = re.sub(r"^\s*(H2G2|English)\s*[:,]\s*", "", answer)  # e2b sometimes labels its speech
    for a in dangers:
        answer = re.sub(rf"(danger:\s*)?{re.escape(a['message'])}(\s*\(source: {re.escape(a['source'])}\))?\s*",
                        "", answer, flags=re.I)
    return answer.strip()


TOOL_INSTRUCTIONS = """
You have tools to fetch data that is NOT in the CONTEXT: another point, the science targets, a route to a destination.
To go to a target: call list_science_targets and then plan_route with the exact lat/lon of the target from the list.
Never invent a coordinate. When explaining a route, repeat the system suggestion with the why; the astronaut decides."""

TOOLS = [
    {"type": "function", "function": {
        "name": "list_science_targets",
        "description": "Real science targets measured by Curiosity near the boxwork: name, lat, lon and what was measured.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "query_point",
        "description": "Slope, elevation, alerts and science target of a point on the map.",
        "parameters": {"type": "object", "required": ["lat", "lon"], "properties": {
            "lat": {"type": "number", "description": "latitude in degrees"},
            "lon": {"type": "number", "description": "east longitude in degrees"}}}}},
    {"type": "function", "function": {
        "name": "plan_route",
        "description": "Computes the routes from the astronaut's current position to the destination and returns the suggested order with the why. The route opens on the map.",
        "parameters": {"type": "object", "required": ["dest_lat", "dest_lon"], "properties": {
            "dest_lat": {"type": "number", "description": "destination latitude"},
            "dest_lon": {"type": "number", "description": "destination east longitude"}}}}},
]
MAX_ROUNDS = 3  # with no limit, a small model may call tools in a loop
_ollama_without_tools = False  # old Ollama rejects `tools` (e.g. 0.12.11 with gemma4): falls back to context-only mode


def without_urls(text: str) -> str:
    """A PDS URL becomes "PDS": the model does not read a link aloud if it never gets one."""
    return re.sub(r"https?://[^\s,)]+", "PDS", text)


class AgentUnavailable(Exception):
    """Ollama down or without the model: the alerts still apply."""


def build_context(point: dict, conditions: dict | None) -> dict:
    """Trims /api/point to what the model needs (photos become a count)."""
    return {
        "point": point["point"],
        "terrain": {k: v for k, v in point["raster_values"].items() if k != "sources"},
        "science_target": point["science_target"],
        "nearby_photos": len(point["nearby_photos"]),
        "alerts": point["alerts"],
        "slope_forecast": point.get("slope_forecast"),
        "environmental_conditions": conditions,  # None = no cached data for the sol
    }


def context_sources(ctx: dict) -> list[str]:
    sources = [a["source"] for a in ctx["alerts"]]
    if ctx["terrain"].get("slope_deg") is not None:
        sources.append("HiRISE DTM (slope)")
    if (ctx.get("route_forecast") or {}).get("terrain"):
        sources.append("route forecast (Curiosity tilt × DTM, REMS, RAD)")
    if ctx["environmental_conditions"]:
        sources.append(f"REMS/RAD sol {ctx['environmental_conditions']['sol']}")
    return list(dict.fromkeys(sources))  # no repeats, in order


def context_as_text(ctx: dict) -> str:
    """Short text, alerts first: a 3B model gets lost in nested JSON."""
    lines = ["ALERTS (fixed rules, they override everything):"]
    lines += [f"- {a['level'].upper()}: {a['message']} (source: {a['source']})" for a in ctx["alerts"]] or ["- none (this does NOT mean safe)"]
    t = ctx["terrain"]
    lines.append(f"POINT: lat {ctx['point']['lat']}, lon {ctx['point']['lon']}")
    lines.append(f"MAP SLOPE: {t.get('slope_deg')}° ({t.get('slope_status')}) · elevation {round(t['elevation_m']) if t.get('elevation_m') is not None else 'no data'} m (source: HiRISE DTM)"
                 if t.get("slope_deg") is not None else "MAP SLOPE: no data")
    sf = ctx.get("slope_forecast")
    if sf:
        lines.append(f"CHANCE THE REAL TERRAIN EXCEEDS {sf['limit_deg']}° (ESTIMATED from rover history): "
                     f"{sf['chance_pct']}% ({sf['above']} of {sf['n']} stops with the map at {sf['map_range']})")
    target = ctx["science_target"]
    lines.append(f"NEARBY SCIENCE TARGET: {json.dumps(target, ensure_ascii=False)}" if target else "NEARBY SCIENCE TARGET: none")
    lines.append(f"ROVER PHOTOS NEARBY: {ctx['nearby_photos']}")
    c = ctx["environmental_conditions"]
    if c:
        r, d = c.get("rems") or {}, c.get("rad") or {}
        lines.append(f"CONDITIONS ON SOL {c['sol']} (source: Curiosity REMS and RAD, sol {c['sol']}): "
                     f"minimum temperature {r.get('temp_min_c')} °C, maximum {r.get('temp_max_c')} °C, "
                     f"pressure {r.get('pressure_pa')} Pa, peak UV {r.get('uv_peak')}, humidity {r.get('humidity_pct')} %, "
                     f"radiation {d.get('estimated_dose_ugy_per_day')} µGy per day")
        lines += [f"- {a['level'].upper()}: {a['message']} (source: {a['source']})" for a in c.get("alerts", [])]
        fc = c.get("today_forecast")
        if fc and fc["temp_min_c"] and fc["temp_max_c"]:
            lines.append(f"FORECAST FOR TODAY, SOL {fc['sol']} (ESTIMATED, not measured; {fc['method']}): "
                         f"minimum {fc['temp_min_c']['value']} °C, maximum {fc['temp_max_c']['value']} °C"
                         + (f", pressure {fc['pressure_pa']['value']} Pa" if fc["pressure_pa"] else "")
                         + (f", ground at noon {fc['ground_noon_c']['value']} °C" if fc.get("ground_noon_c") else "")
                         + (f", radiation {fc['dose_ugy_day']['value']} µGy per day" if fc.get("dose_ugy_day") else ""))
    else:
        lines.append("ENVIRONMENTAL CONDITIONS: no data")
    if ctx.get("searches"):  # the system already searched by rule (named target, requested route): the small model picks the wrong tool
        lines += ["FETCHED BY THE SYSTEM FOR THIS QUESTION (use this first):", *ctx["searches"]]
    lines += route_as_text(ctx.get("route_forecast"))
    return "\n".join(lines)


def _v(field: dict | None, unit: str) -> str:
    return "no data" if not field else f"{field['value']} {unit}"


def group_alerts(alerts: list[dict]) -> list[dict]:
    """The same rover stop (or the base limit) comes back at every path sample: keep the 1st."""
    seen = {}
    for a in alerts:
        seen.setdefault((a["level"], re.sub(r"[\d.,]+ m from (here|the base)", "", a["message"])), a)
    return list(seen.values())


BAND_TEXT = {"high": "high chance (≥50%)", "medium": "medium chance (20–49%)", "low": "low chance (<20%)", "no_data": "no data"}


LABEL_TEXT = {"ok": "no risk on the map", "caution": "caution", "danger": "danger"}


def suggestion_as_text(sg: dict) -> list[str]:
    """Suggestion from route_suggestions.py. "variant X, label Y": with "route X: caution" the model called the route "caution"."""
    out = [f"SYSTEM SUGGESTION (fixed rule, not yours; the astronaut decides): {sg['reason']}"]
    out += [f"- variant {r['type']}, label {LABEL_TEXT.get(r['label'], r['label'])}: {r['why']}" for r in sg["summary"]]
    if sg["dust_warning"]:
        out.append(f"- {sg['dust_warning']} (source: Mars24 + MCS/MRO, NASA)")
    return out


def route_as_text(rf: dict | None) -> list[str]:
    """Section of the "forecast route" tool (route_forecast.py). Nothing when there is no open route."""
    if rf is None:
        return []
    if "error" in rf:
        return [f"ROUTE FORECAST: no forecast ({rf['error']})"]
    out = []
    if rf.get("suggestion"):  # the other variants too: without them the model cannot compare
        out += suggestion_as_text(rf["suggestion"])
    t = rf["terrain"]
    m = t["meters_by_chance"]
    out += [f"FORECAST OF THE OPEN ROUTE {rf['type']} FOR SOL {rf['eva_sol']} (ESTIMATED from NASA history, not measured):",
            f"- distance {rf['distance_m']} m, estimated time {rf['estimated_time_min']} min",
            f"- terrain (chance the real ground exceeds {t['limit_deg']}°, from Curiosity tilt): "
            + ", ".join(f"{v} m with {BAND_TEXT[k]}" for k, v in m.items() if v)]  # an empty band confuses the model
    if t["worst_segment"]:
        w = t["worst_segment"]
        band = next(BAND_TEXT[n] for n, lo, hi in CHANCE_BANDS if lo <= w["chance_pct"] < hi)
        out.append(f"- segment with the highest chance, {w['distance_m']} m from the start: map {w['map_slope_deg']}°, "
                   f"{w['chance_pct']}% ({band})")
    out += [f"- {a['level'].upper()} from {round(a['distance_m'])} m from the start: {a['message']} (source: {a['source']})"
            for a in group_alerts(rf["alerts"])]
    c = rf["climate"]
    if c:
        out.append(f"- forecast climate (base sol {c['base_sol']}, {c['horizon_sols']} sols before): "
                   f"minimum {_v(c['temp_min_c'], '°C')}, maximum {_v(c['temp_max_c'], '°C')}, pressure {_v(c['pressure_pa'], 'Pa')}")
        w = c["eva_window"]
        if w:
            out.append(f"- best window for this EVA: {w['start_lmst']}–{w['end_lmst']} local solar time, "
                       f"coldest forecast hour {w['coldest_temp_in_window_c']} °C")
    else:
        out.append("- forecast climate: no data")
    d = rf["dose"]
    out.append(f"- forecast radiation during the walk: {d['value_ugy']} µGy" + (f" (typical error ±{d['error_ugy']})" if d["error_ugy"] else "")
               if d else "- forecast radiation during the walk: no data")
    return out


def _chat(messages: list[dict], with_tools: bool) -> dict:
    body = {"model": MODEL, "stream": False,
            "keep_alive": -1,  # the default (5 min) unloaded gemma; reloading it next to Whisper ran out of RAM
            "think": False,  # gemma4 thinks by default: a short spoken answer does not need it, and it costs seconds
            "options": {"temperature": 0, "num_ctx": 8192},  # gemma4's default (131k) wastes RAM
            "messages": messages}
    if with_tools:
        body["tools"] = TOOLS
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)["message"]


def ask(question: str, ctx: dict, run_tool=None) -> str:
    """run_tool(name, args) -> text: runs a tool (comes from main.py). Without it, context only."""
    global _ollama_without_tools
    with_tools = run_tool is not None and not _ollama_without_tools
    messages = [{"role": "system", "content": INSTRUCTIONS + (TOOL_INSTRUCTIONS if with_tools else "")},
                {"role": "user", "content": f"CONTEXT:\n{without_urls(context_as_text(ctx))}\n\nQUESTION: {question}"}]
    try:
        for _ in range(MAX_ROUNDS):
            try:
                msg = _chat(messages, with_tools)
            except urllib.error.HTTPError as e:
                if not (with_tools and "does not support tools" in e.read().decode(errors="replace")):
                    raise
                _ollama_without_tools, with_tools = True, False
                messages[0]["content"] = INSTRUCTIONS
                msg = _chat(messages, False)
            if not msg.get("tool_calls"):
                if msg["content"].strip():
                    return msg["content"].strip()
                break  # empty after using a tool (seen in e2b and granite4): ask for the text without tools
            messages.append(msg)
            for c in msg["tool_calls"]:
                f = c["function"]
                messages.append({"role": "tool", "tool_name": f["name"],
                                 "content": without_urls(run_tool(f["name"], f.get("arguments") or {}))})
        final = _chat(messages, False)["content"].strip()  # rounds exhausted or empty: answer with what was already fetched
        return final or "I don't know: I don't have that data here."
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        raise AgentUnavailable(f"local agent unavailable ({MODEL} at {OLLAMA_URL}): {e}") from e
