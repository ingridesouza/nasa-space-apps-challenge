"""Tests for the local agent (feature 08, phase 2).

Run: make test   (or: cd api && python test_agent.py)
The model tests only run if Ollama is up with gemma3:4b."""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agent
from fastapi import HTTPException
from main import Question, ask

SOL_4309 = (-4.78679146, 137.4076395)  # danger: history 22.4° and 2,029 m from the base


class Req:  # get_point only uses base_url to build the photo link
    base_url = "http://local/"


def test_context_alerts_first_and_no_data():
    point = {"point": {"lat": 0, "lon": 0}, "raster_values": {"slope_deg": None}, "science_target": None,
             "nearby_photos": [], "alerts": [{"level": "danger", "message": "X", "source": "F"}]}
    txt = agent.context_as_text(agent.build_context(point, None))
    assert txt.splitlines()[1] == "- DANGER: X (source: F)"
    assert "MAP SLOPE: no data" in txt and "ENVIRONMENTAL CONDITIONS: no data" in txt


def test_ollama_down_gives_503_with_alerts():
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, "http://127.0.0.1:9"
    try:
        ask(Question(question="hi", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
        raise AssertionError("should have failed")
    except HTTPException as e:
        assert e.status_code == 503 and e.detail["alerts"]
    finally:
        agent.OLLAMA_URL = url


def ollama_up():
    try:
        urllib.request.urlopen(f"{agent.OLLAMA_URL}/api/tags", timeout=2)
        return True
    except OSError:
        return False


def test_model_out_of_context_and_danger_first():
    if not ollama_up():
        print("skipped: Ollama down")
        return
    r = ask(Question(question="What is the name of the president of Brazil?", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
    assert r["answer"].startswith("Danger: Curiosity measured a 22.4°"), r["answer"]
    assert "I don't know" in r["answer"], r["answer"]


if __name__ == "__main__":
    for name, t in list(globals().items()):
        if name.startswith("test_"):
            t()
            print(f"ok  {name}")
