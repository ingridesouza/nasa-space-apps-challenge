"""Feature 08, phase 2 -- local agent: answers questions using only the
point context (the same JSON as /api/point + REMS/RAD conditions).

No tool-calling, embeddings or SDK: the context fits in ~2 KB and goes
whole into the prompt. The model runs on the local hardware (Ollama), with no
external network. Alerts come from the rules in alerts.py, never from the model."""

import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("H2G2_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("H2G2_MODEL", "gemma3:4b")  # Gemma 3 4B (Google)
TIMEOUT_S = 120  # CPU (i5-8600) can take tens of seconds on the first call

INSTRUCTIONS = """You are H2G2, the assistant of an astronaut in Gale crater, on Mars.
Answer in English, in at most 3 short sentences, to be read aloud.
Use ONLY the data in the CONTEXT below. Cite the source and the sol when available.
If the context does not have the requested data, answer exactly: "I don't know: I don't have that data here."
Never invent a number, name or position. Never say a place is safe just because there is no alert.
If there is a DANGER alert, start the answer with it. Never contradict, create or cancel an alert."""


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
    if ctx["environmental_conditions"]:
        sources.append(f"REMS/RAD sol {ctx['environmental_conditions']['sol']}")
    return list(dict.fromkeys(sources))  # no repeats, in order


def context_as_text(ctx: dict) -> str:
    """Short text, alerts first: a 3B model gets lost in nested JSON."""
    lines = ["ALERTS (fixed rules, they override everything):"]
    lines += [f"- {a['level'].upper()}: {a['message']} (source: {a['source']})" for a in ctx["alerts"]] or ["- none (this does NOT mean safe)"]
    t = ctx["terrain"]
    lines.append(f"POINT: lat {ctx['point']['lat']}, lon {ctx['point']['lon']}")
    lines.append(f"MAP SLOPE: {t.get('slope_deg')}° ({t.get('slope_status')}) · elevation {t.get('elevation_m')} m (source: HiRISE DTM)"
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
    return "\n".join(lines)


def ask(question: str, ctx: dict) -> str:
    body = json.dumps({
        "model": MODEL,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": f"CONTEXT:\n{context_as_text(ctx)}\n\nQUESTION: {question}"},
        ],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)["message"]["content"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        raise AgentUnavailable(f"local agent unavailable ({MODEL} at {OLLAMA_URL}): {e}") from e
