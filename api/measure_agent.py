"""Compares agent models (F08) on the demo questions: right tool, time and RAM.

  python measure_agent.py gemma4:e2b granite4 phi4-mini

Uses the same /api/ask as the demo. Distress is left out: it is a rule, it does not go through the model.
Unloads each model before the next one (two at once in RAM froze the machine)."""

import json
import sys
import time
import urllib.request

import agent
from main import BASE_LAT_LON, Question, QuestionRoute, ask, get_route

DESTINATION = (-4.80311, 137.39202)  # the one from the demo screenshot
ROUTE = QuestionRoute(origin_lat=BASE_LAT_LON[0], origin_lon=BASE_LAT_LON[1], dest_lat=DESTINATION[0], dest_lon=DESTINATION[1])
SUGGESTED = get_route(*BASE_LAT_LON, *DESTINATION, [], [])["suggestion"]["suggested"]
TYPE_WORDS = {"safest": ("safe",), "fastest": ("fast", "quick"), "most_science": ("scien",)}
DONT_KNOW = ("don't know", "do not know", "no data", "not in", "cannot", "can't")


class Req:
    base_url = "http://local/"


# (question, open route, what counts as a hit, description)
CASES = [
    ("Take me to the nearest science target.", None,
     lambda r: r["actions"] and "science targets (F04)" in r["sources"], "lists targets and plans a route"),
    ("Take me to the Altadena target.", None, lambda r: bool(r["actions"]), "plans a route to a target by name"),
    ("Which route should I take, and why?", ROUTE,
     lambda r: any(w in r["answer"].lower() for w in TYPE_WORDS[SUGGESTED]), f"repeats the suggested one ({SUGGESTED})"),
    ("What is the terrain slope at lat -4.787, lon 137.408?", None,
     lambda r: "queried point (HiRISE DTM)" in r["sources"], "queries the point"),
    ("Who is the president of Brazil?", None,
     lambda r: not r["actions"] and any(w in r["answer"].lower() for w in DONT_KNOW), "does not know, no tool"),
]


def ollama(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{agent.OLLAMA_URL}{path}", data=body and json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def free_ram_gb() -> float:
    line = next(x for x in open("/proc/meminfo") if x.startswith("MemAvailable"))
    return int(line.split()[1]) / 2**20


def measure(model: str) -> None:
    loaded = any(m["name"].startswith(model) for m in ollama("/api/ps")["models"])
    if not loaded and free_ram_gb() < 4:  # e2b ~2-3 GB
        print(f"{model}: skipped, only {free_ram_gb():.1f} GB free (close programs)")
        return
    agent.MODEL, agent._ollama_without_tools = model, False
    hits, ram = 0, None
    print(f"\n== {model}")
    for question, route, ok, descr in CASES:
        t = time.time()
        try:
            r = ask(Question(question=question, route=route), Req())
        except Exception as e:  # noqa: BLE001 -- a model that is down counts as a miss, go on to the next
            r = {"answer": f"ERROR {getattr(e, 'detail', e)}", "actions": [], "sources": []}
        hit = bool(ok(r))
        hits += hit
        ram = ram or next((m["size"] / 2**30 for m in ollama("/api/ps")["models"] if m["name"].startswith(model)), None)
        print(f"{'ok ' if hit else 'X  '} {time.time() - t:5.1f}s  {descr}: {r['answer'][:140]!r}")
    print(f"-> {model}: {hits}/{len(CASES)} hits, model RAM {ram and f'{ram:.1f} GB'}"
          + ("" if not agent._ollama_without_tools else " (NO tool calling)"))
    ollama("/api/generate", {"model": model, "keep_alive": 0})  # unload before the next one


if __name__ == "__main__":
    for m in sys.argv[1:] or ["gemma4:e2b"]:
        measure(m)
