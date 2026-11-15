"""Feature 08, voice: tests with assert (python test_voice.py), without the model."""

from measure_voice import word_errors
from voice import choose_language, interpret, words

assert words("Guide, route to Altadena!") == ["guide", "route", "to", "altadena"]
assert word_errors("Guide, route to the base.", "guide route to the base") == (0, 5)
assert word_errors("route to the base", "route to base") == (1, 4)       # missing word
assert word_errors("route to the base", "boot to the case") == (2, 4)    # two swapped
assert word_errors("yes", "") == (1, 1)                                  # nothing heard

assert choose_language({"pt": 0.134, "en": 0.217, "es": 0.141}) == "en"  # undecided: English
assert choose_language({"pt": 0.9, "en": 0.05}) == "pt"                  # clear Portuguese
assert choose_language({}) == "en"

# real names of the database targets (science_targets)
BASE = {"name": "the base", "lat": -4.8069, "lon": 137.3798, "keys": {"base", "habitat"}, "base": True}
POINT = {"name": "the marked point", "lat": -4.80, "lon": 137.38, "keys": {"point", "marked"}}
DESTINATIONS = [BASE, POINT] + [{"name": n, "lat": 0, "lon": 0} for n in (
    "Boxwork ridges — sulfate cementation", "Altadena — drill hole #43",
    "Totoral / Sillar — ridge vs. depression")]


def ok(text, intent, destination=None, **kw):
    r = interpret(text, DESTINATIONS, **kw)
    assert (r["intent"], r["destination"] and r["destination"]["name"]) == (intent, destination), (text, r)
    return r


ok("Guide, what is the best route to the base?", "route", "the base")
ok("Guide, rout to Altadena.", "route", "Altadena — drill hole #43")              # typical Whisper error
ok("Guide, take me to the boxwork ridges.", "route", "Boxwork ridges — sulfate cementation")
ok("Guid, route to Totoral", "route", "Totoral / Sillar — ridge vs. depression")  # activation misheard
ok("Guide, I want to go back.", "route", "the base")                            # back with no destination = base
ok("Guide, route to the marked point", "route", "the marked point")
ok("Guide, route to Mars Central", "question")                                  # destination outside the list: to the model
# free speech: a report goes whole to the model, even mentioning "route" or "back"
r = ok("Hello guide, I'm in the middle of a route and a very toxic gas showed up", "question")
assert r["activated"] and r["question"] == "I'm in the middle of a route and a very toxic gas showed up", r
ok("Hey, guide, the suit is losing pressure and I think I need to go back soon", "question")
assert ok("Hi, oh guide, route to Altadena", "route", "Altadena — drill hole #43")["activated"]
ok("I talked to the guide yesterday", "none")                                   # "guide" after the 3rd word
ok("What is the best route to the base?", "none")                               # no "Guide": ignored
ok("Yes.", "yes", require_activation=False)                                     # confirmation window
ok("No, cancel.", "no", require_activation=False)
ok("Yeah", "yes", require_activation=False)                                     # short "yes" from small
ok("NO, CANCEL!", "no", require_activation=False)
ok("Thanks for watching.", "question", require_activation=False)                # common hallucination: does not confirm
assert ok("Guide, can I climb here safely?", "question")["question"] == "can I climb here safely?"
assert ok("Guide how much radiation will I get today", "question")["question"] == "how much radiation will I get today"
assert ok("Hey guide, route to the base", "route", "the base")["activated"]
assert ok("A guide, can I climb here?", "question")["question"] == "can I climb here?"
print("test_voice: ok")
