"""Feature 11, voice viewer: tests with assert (python test_commands.py), without the model."""

import json
import re
from pathlib import Path

from commands import BLOCKS, CATALOG, has_hint, interpret, validate


def cmd(text, open_blocks=None, focus=None):
    return interpret(text, open_blocks, focus, use_model=False)["command"]


def ok(text, target, action, args=None, **kw):
    c = cmd(text, **kw)
    assert c and (c["target"], c["action"]) == (target, action), (text, c)
    if args is not None:
        assert c["args"] == args, (text, c)


# catalog: unique ids in the sequence m-A, m-B…; every block has a spoken name and an action
ids = [b["id"] for b in CATALOG["blocks"] if b["selector"]]  # "sys" has no block on screen
assert ids == [f"m-{chr(65 + i)}" for i in range(len(ids))], ids
assert all(b["spoken"] and b["actions"] for b in CATALOG["blocks"])

# the front registers a handler for every catalog action (same file on both sides)
app = (Path(__file__).resolve().parent.parent / "web" / "app.js").read_text(encoding="utf-8")
for b in CATALOG["blocks"]:
    block = re.search(rf"register\('{b['id']}', \{{(.*?)\n\}}\)", app, re.S)
    assert block, f"no register('{b['id']}')"
    for a in b["actions"]:
        assert re.search(rf"\b{a}:", block.group(1)), f"{b['id']}.{a} has no handler in app.js"

# by block name, star name or synonym
ok("Marvin, zoom out the map", "m-A", "zoom_out", {"levels": 1})
ok("Atlas, zoom in two", "m-A", "zoom_in", {"levels": 2})
ok("move the map north", "m-A", "move", {"direction": "north"})
ok("turn on the relief", "m-B", "show", {"layer": "relief_hillshade"})
ok("Vega opacity risk 40", "m-B", "opacity", {"layer": "predicted_risk", "value": 40})
ok("Vega, show sun and shade", "m-B", "show", {"layer": "insolation"})  # "shade" alone stays relief
ok("Vega, show shade", "m-B", "show", {"layer": "relief_hillshade"})
ok("turn on the atmosphere layer", "m-B", "show", {"layer": "atmosphere_track"})
ok("Vega, solar hour fourteen", "m-B", "hour", {"hour": 14})
ok("Vega, solar hour now", "m-B", "hour_preset", {"moment": "now"})  # the longer phrase beats "solar hour"
ok("Vega, sun at arrival", "m-B", "hour_preset", {"moment": "arrival"})
ok("Vega, variable pressure", "m-B", "variable", {"variable": "pressure_pa"})
ok("Vega, plot minimum temperature", "m-B", "variable", {"variable": "temp_min_c"})
ok("Polaris, fastest route", "m-C", "type", {"type": "fastest"})
ok("polaris next sol", "m-C", "sol", {"delta": "1"})  # the longer phrase beats "next"
ok("Orion rotate left 90 degrees", "m-D", "rotate", {"direction": "left", "degrees": 90})
ok("Rigel open the second", "m-E", "open", {"n": 2})
ok("close the viewer", "m-H", "close")
ok("Pollux latitude minus 4.808 longitude 137.381", "m-I", "set", {"lat": -4.808, "lon": 137.381})
ok("Atlas, what is the elevation here", "m-A", "read")
ok("Polaris, add stop", "m-C", "stop")
ok("Polaris, I'm here", "m-C", "here")
ok("Altair, science details", "m-F", "science")
ok("Polaris, remove stop two", "m-C", "remove_stop", {"n": 2})
ok("Polaris, sol 1200", "m-C", "go_sol", {"sol": 1200})
ok("Polaris, oxygen 350", "m-C", "o2", {"liters": 350})
ok("Polaris, record measurement sol 4600 minus 80 minus 10 870", "m-C", "measurement",
   {"sol": 4600.0, "minimum": -80.0, "maximum": -10.0, "pressure": 870.0})  # dose is optional
ok("Polaris, delete measurement", "m-C", "delete_measurement")
ok("Orion, look at point", "m-D", "center")
ok("collapse images", "m-E", "collapse")
ok("Draco, repeat", "m-G", "listen")
ok("Antares, read", "m-J", "read")
ok("silence", "sys", "silence")
ok("close all", "sys", "back")
ok("turn off microphone", "sys", "microphone")
ok("help", "sys", "help")

# no block cited: decides by the open blocks, then by the focus; a tie asks
ok("next", "m-E", "next", open_blocks=["m-E"])
ok("next", "m-F", "next", open_blocks=["m-E", "m-F"], focus="m-F")
r = interpret("next", ["m-E", "m-F"], None, use_model=False)
assert r["command"] is None and r["ambiguous"] == ["m-E", "m-F"] and "Which block" in r["speech"], r

# destructive action asks for confirmation
r = interpret("cancel route", use_model=False)
assert r["command"]["action"] == "cancel" and r["confirm"] and r["speech"].endswith("Confirm?"), r

# required argument missing: does not guess, asks
r = interpret("Vega solar hour 23", use_model=False)
assert r["command"] is None and "outside 5..19" in r["speech"], r
r = interpret("Polaris, I am here", use_model=False)
assert r["command"]["action"] == "here" and r["confirm"], r  # moves the route origin: confirms
r = interpret("turn on the layer", use_model=False)
assert r["command"] is None and "missing layer" in r["speech"], r
assert cmd("Pollux set destination") is None  # no coordinate said, no invented coordinate

r = interpret("Polaris, record measurement sol 4600 minus 80 minus 10 870", use_model=False)
assert "sol 4600, minimum -80, maximum -10, pressure 870. Confirm?" in r["speech"], r["speech"]

# a question is not a command
assert interpret("what is the temperature today?", use_model=False) == {"command": None, "source": None, "confirm": False, "speech": None}
assert not has_hint("what is the temperature today?")
assert has_hint("get that map out of the way")

# validate blocks whatever the model invents
for bad in ({"target": "m-Z", "action": "open"}, {"target": "m-A", "action": "fly"},
            {"target": "m-B", "action": "show", "args": {"layer": "lava"}},
            {"target": "m-A", "action": "zoom_in", "args": {"levels": 40}},
            {"target": "m-I", "action": "set", "args": {"lat": -4.8}}):
    try:
        validate(bad)
        raise AssertionError(f"passed: {bad}")
    except ValueError:
        pass
assert validate({"target": "m-A", "action": "zoom_in"}) == {"target": "m-A", "action": "zoom_in", "args": {"levels": 1}}
assert json.dumps(BLOCKS["m-A"])  # serializable catalog (goes whole to the front)

print("ok: commands")
