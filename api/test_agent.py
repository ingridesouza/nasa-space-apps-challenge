"""Tests for the local agent (feature 08, phase 2).

Run: make test   (or: cd api && python test_agent.py)
The model tests only run if Ollama is up with the agent.MODEL model (gemma4:e2b)."""

import json
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


def test_distress_answered_by_rule_without_model():
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, "http://127.0.0.1:9"  # proves the model is not called
    try:
        r = ask(Question(question="Hey guide, I fell into a hole, now what?", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
    finally:
        agent.OLLAMA_URL = url
    assert r["distress"] and r["answer"].startswith("Stop") and "The base is" in r["answer"], r
    assert not agent.DISTRESS.search("does the temperature fall at night?")


def test_distress_toxic_gas_and_leak():
    assert agent.DISTRESS.search("I have a toxic gas warning") and agent.DISTRESS.search("my suit is leaking")
    assert agent.DISTRESS.search("a very toxic gas showed up") and agent.DISTRESS.search("mayday")
    assert not agent.DISTRESS.search("what gas is in the atmosphere?")
    assert not agent.DISTRESS.search("the temperature is falling") and not agent.DISTRESS.search("can you help me plan a route?")


def test_target_named_and_path_request():
    from db import get_connection
    from vector_queries import all_science_targets
    from voice import asks_nearest_target, asks_path, mentioned_destination
    targets = all_science_targets(get_connection())
    name = lambda t: (mentioned_destination(t, targets) or {}).get("name")  # noqa: E731
    assert name("I want to study Nevado Sarjama, show me the path options") == "Nevado Sajama"
    assert name("what was measured at the Altadena target?") == "Altadena"
    assert name("where is monte grande and which route is safest?") == "Monte Grande"
    assert name("is the slope here too grande?") is None  # "grande" alone is not Monte Grande
    assert asks_path("how do I get there?")
    assert not asks_path("what was measured at the Altadena target?")
    assert asks_nearest_target("Which science target is closest to me?")
    assert not asks_nearest_target("am I near the base?")
    assert agent.without_urls("SiO2 41% (https://pds-geosciences.wustl.edu/a/b_p1.csv, sol 4634)") == "SiO2 41% (PDS, sol 4634)"


def test_route_to_named_target_comes_by_rule():
    srv, requests = _fake_ollama([{"role": "assistant", "content": "I suggest the safest."}])
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    try:
        r = ask(Question(question="I want to study Nevado Sarjama, how do I get there?"), Req())
    finally:
        agent.OLLAMA_URL = url
        srv.shutdown()
    assert r["actions"] and abs(r["actions"][0]["lat"] - -4.80801) < 1e-4, r["actions"]  # Nevado Sajama
    assert "NAMED TARGET: Nevado Sajama" in requests[0]["messages"][1]["content"]


def test_replan_classifies_and_avoids_the_obstacle():
    from geo import haversine_m
    from main import get_replan
    from replan import classify
    assert classify("There is a big rock ahead") == "obstacle"
    assert classify("it is very steep") == "steep" and classify("I am tired") == "tired"
    assert classify("my oxygen is low") == "oxygen"
    assert classify("dust is coming") == "dust" and classify("I have a problem") == "other"
    assert classify("what is your name?") is None
    assert classify("a huge crater showed up in front of me") == "obstacle"
    assert classify("what is in Gale crater?") is None
    middle, monte_grande = (-4.80460, 137.38397), (-4.80784, 137.38104)
    r = get_replan(*middle, "There is a big rock ahead", *monte_grande)
    ob = r["obstacle"]
    for x in r["routes"]:  # no option goes through the obstacle
        assert min(haversine_m(ob["lat"], ob["lon"], *p) for p in x["points"]) > ob["radius_m"], x["type"]
    assert r["suggestion"]["suggested"] in [x["type"] for x in r["routes"]]
    back = get_replan(*middle, "my oxygen is low")  # no destination: only going back to the base
    assert back["routes"] and all(x["type"].endswith("return") for x in back["routes"])
    tired = get_replan(*middle, "I am tired", *monte_grande)  # tiredness does not send the astronaut back
    assert tired["routes"] and all(x["type"].startswith("continue") for x in tired["routes"])


def test_problem_reported_with_open_route_becomes_replan_action():
    from main import QuestionRoute
    srv, _ = _fake_ollama([{"role": "assistant", "content": "I suggest the safe detour."}])
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    route = QuestionRoute(origin_lat=-4.80460, origin_lon=137.38397, dest_lat=-4.80784, dest_lon=137.38104)
    try:
        r = ask(Question(question="There is a big rock ahead", lat=-4.80784, lon=137.38104,  # lat/lon = open destination
                         pos_lat=-4.80460, pos_lon=137.38397, route=route), Req())
    finally:
        agent.OLLAMA_URL = url
        srv.shutdown()
    action = next(a for a in r["actions"] if a["type"] == "replan")
    assert r["replanning"] and r["answer"].startswith("Obstacle ahead") and "you decide" in r["answer"]
    assert not any(a["type"] == "open_route" for a in r["actions"])  # nothing reopens the normal route over the options
    assert action["result"]["problem"] == "obstacle" and action["origin"] == {"lat": -4.80460, "lon": 137.38397}
    assert agent.strip_repeated_danger("English: The closest target is Mojo.", []) == "The closest target is Mojo."


def test_strips_danger_the_model_repeated():
    a = {"message": "Slope of 37.8° at this point.", "source": "HiRISE DTM (Mars Trek)"}
    r = "DANGER: Slope of 37.8° at this point. (source: HiRISE DTM (Mars Trek)) I don't know: I don't have that data here."
    assert agent.strip_repeated_danger(r, [a]) == "I don't know: I don't have that data here."


def test_suggestion_orders_by_risk_and_hides_no_route():
    from route_suggestions import suggest
    def route(kind, status, minutes):  # noqa: E306
        return {"type": kind, "distance_m": minutes * 10, "estimated_time_min": minutes, "alerts": [],
                "elevation_profile": [{"cumulative_distance_m": 0}, {"cumulative_distance_m": 50}],
                "risk_segments": [{"slope_status": status, "predicted_status": status, "slope_deg": 1}]}
    routes = [route("fastest", "danger", 5), route("safest", "safe", 9)]
    sg = suggest(routes)
    assert sg["suggested"] == "safest" and sg["order"] == ["safest", "fastest"]
    assert routes[0]["suggestion"]["label"] == "danger" and "50 m in danger" in routes[0]["suggestion"]["cons"][0]["text"]
    assert "_key" not in routes[0]["suggestion"] and len(sg["summary"]) == 2


def test_suggestion_with_real_route():
    from main import BASE_LAT_LON, get_route
    r = get_route(BASE_LAT_LON[0], BASE_LAT_LON[1], *SOL_4309, [], [])
    assert r["suggestion"]["suggested"] in [x["type"] for x in r["routes"]]
    assert all(x["suggestion"]["label"] in ("ok", "caution", "danger") for x in r["routes"])
    print(r["suggestion"]["reason"], r["suggestion"]["summary"])


def _fake_ollama(responses):
    """Local server that returns `responses` in order (dict = 200 with message; str = error 400) and keeps the requests."""
    import http.server, threading  # noqa: E401
    requests = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            r = responses.pop(0)
            body = json.dumps({"error": r} if isinstance(r, str) else {"message": r}).encode()
            self.send_response(400 if isinstance(r, str) else 200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, requests


def test_plan_route_tool_opens_route_and_says_danger():
    call = {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "plan_route", "arguments": {"dest_lat": SOL_4309[0], "dest_lon": SOL_4309[1]}}}]}
    srv, requests = _fake_ollama([call, {"role": "assistant", "content": "I suggest the indicated route."}])
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    agent._ollama_without_tools = False
    try:
        r = ask(Question(question="route to sol 4309?"), Req())
    finally:
        agent.OLLAMA_URL = url
        srv.shutdown()
    assert requests[0]["tools"] and requests[1]["messages"][-1]["role"] == "tool"
    assert "SYSTEM SUGGESTION" in requests[1]["messages"][-1]["content"]
    assert r["actions"] == [{"type": "open_route", "lat": SOL_4309[0], "lon": SOL_4309[1]}]
    assert r["answer"].startswith("Danger:"), r["answer"]  # danger of the planned route comes by rule


def test_ollama_without_tools_falls_back_to_context():
    srv, requests = _fake_ollama(["registry.ollama.ai/library/gemma4:e4b does not support tools",
                                  {"role": "assistant", "content": "ok"}])
    url, agent.OLLAMA_URL = agent.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    agent._ollama_without_tools = False
    try:
        assert agent.ask("hi", agent.build_context(
            {"point": {"lat": 0, "lon": 0}, "raster_values": {}, "science_target": None, "nearby_photos": [], "alerts": []}, None),
            run_tool=lambda n, a: "") == "ok"
    finally:
        agent.OLLAMA_URL = url
        srv.shutdown()
    assert "tools" in requests[0] and "tools" not in requests[1] and agent._ollama_without_tools
    agent._ollama_without_tools = False


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


def test_route_terrain_meters_by_chance_and_worst_segment():
    from route_forecast import terrain
    route = {"elevation_profile": [{"cumulative_distance_m": d} for d in (0, 10, 30, 60)],
             "risk_segments": [{"chance_pct": 0, "slope_deg": 3}, {"chance_pct": 27, "slope_deg": 12},
                               {"chance_pct": None, "slope_deg": 30}]}
    t = terrain(route)
    assert t["meters_by_chance"] == {"low": 10, "medium": 20, "high": 0, "no_data": 30}
    assert t["worst_segment"]["distance_m"] == 10 and t["worst_segment"]["chance_pct"] == 27


def test_route_text_groups_same_stop_and_says_no_forecast():
    a = lambda d, m: {"level": "caution", "message": m, "source": "F", "distance_m": d}  # noqa: E731
    rf = {"type": "safest", "eva_sol": 5000, "distance_m": 100, "estimated_time_min": 3,
          "terrain": {"meters_by_chance": {"low": 100, "medium": 0, "high": 0, "no_data": 0},
                      "worst_segment": None, "limit_deg": 15},
          "alerts": [a(0, "measured 17.5° 56 m from here (sol 4634)."), a(40, "measured 17.5° 75 m from here (sol 4634).")],
          "climate": None, "dose": None}
    txt = agent.route_as_text(rf)
    assert sum("sol 4634" in line for line in txt) == 1 and "no data" in txt[-1]
    assert agent.route_as_text({"error": "x"}) == ["ROUTE FORECAST: no forecast (x)"]
    assert agent.route_as_text(None) == []


def test_route_forecast_tool_with_real_data():
    from main import BASE_LAT_LON, get_route_forecast
    rf = get_route_forecast(BASE_LAT_LON[0], BASE_LAT_LON[1], *SOL_4309, sol=5000)
    assert rf["eva_sol"] == 5000 and rf["estimated_time_min"] > 0
    assert rf["terrain"]["worst_segment"] and any(a["level"] == "danger" for a in rf["alerts"])
    assert rf["climate"]["eva_window"]
    from forecast import load_climate
    has_rad = any(c.get("dose_ugy_day") for c in load_climate() or [])
    assert (rf["dose"]["value_ugy"] > 0) if has_rad else rf["dose"] is None  # no RAD in the cache: no faked zero


if __name__ == "__main__":
    for name, t in list(globals().items()):
        if name.startswith("test_"):
            t()
            print(f"ok  {name}")
