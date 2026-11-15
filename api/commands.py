"""Feature 11 -- voice viewer: astronaut text -> ONE command from the catalog
web/commands.json ({target, action, args}), which the front executes.

Two layers: rules (instant, cover most: "Atlas, zoom in two") and, only if
the rules do not understand and the phrase looks like a command, the local
Gemma with the output bound to a JSON schema (enum of ids and actions).
Everything that leaves here goes through validate(): an action or argument
outside the catalog never reaches the screen. Plan: docs/feature-11-visor-por-voz.md."""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from agent import MODEL, OLLAMA_URL
from voice import _similar, words

CATALOG_PATH = Path(__file__).resolve().parent.parent / "web" / "commands.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
BLOCKS = {b["id"]: b for b in CATALOG["blocks"]}
TIMEOUT_S = 60
MAX_MODEL_WORDS = 12  # a long report is a question, not a command: goes straight to the agent

# Dropped before matching phrases: "turn on the layer" matches "turn on".
# "one" stays: it is a number ("zoom in one").
FILLER = {"the", "a", "an", "of", "to", "in", "on", "at", "for", "please", "me", "and", "that", "this", "it",
          "marvin", "hey", "hi", "hello", "block", "modal", "card", "page"}
NUMBERS = {"zero": 0, "one": 1, "first": 1, "two": 2, "second": 2, "three": 3, "third": 3, "four": 4,
           "fourth": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
           "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
           "ninety": 90, "hundred": 100}


def _clean(text: str) -> list[str]:
    return [w for w in words(text) if w not in FILLER]


def _matches(phrase: list[str], p: list[str], exact: bool) -> bool:
    """Contiguous phrase inside p (word by word, exact or similar)."""
    n = len(phrase)
    same = (lambda a, b: a == b) if exact else (lambda a, b: a == b or _similar(a, {b}))
    return any(all(same(p[i + k], phrase[k]) for k in range(n)) for i in range(len(p) - n + 1))


def _cited_blocks(p: list[str], exact: bool) -> list[str]:
    cited = []
    for b in CATALOG["blocks"]:
        names = [words(x) for x in b["spoken"] + b["synonyms"]]
        if any(_matches(n, p, exact) for n in names if n):
            cited.append(b["id"])
    return cited


def _best_action(block: dict, p: list[str], exact: bool) -> tuple[int, str | None]:
    """The longest matched phrase wins ("next sol" beats "next")."""
    best = (0, None)
    for name, a in block["actions"].items():
        for f in a["spoken"]:
            fp = [w for w in words(f) if w not in FILLER]
            if fp and _matches(fp, p, exact) and len(fp) > best[0]:
                best = (len(fp), name)
    return best


def _integer(text: str, p: list[str]) -> int | None:
    d = re.search(r"\d+", text)
    if d:
        return int(d.group())
    total, found = 0, False
    for w in p:
        if w in NUMBERS:
            total, found = total + NUMBERS[w], True
        elif found:
            break  # "forty five": consecutive number words add up
    return total if found else None


def _numbers(text: str) -> list[float]:
    """'-4.808 and 137.381' or 'minus 4.808 ...' -> [-4.808, 137.381]."""
    return [float(n) * (-1 if s else 1) for s, n in re.findall(r"(minus\s+|-)?(\d+(?:\.\d+)?)", text.lower())]


def _args(block: dict, action: str, text: str, p: list[str]) -> tuple[dict, str | None]:
    """Extracts the action arguments. Returns (args, missing) -- missing = name of the absent required arg."""
    spec = block["actions"][action].get("args", {})
    args, numbers = {}, _numbers(text)
    for name, s in spec.items():
        v = None
        if s["type"] == "enum":
            for exact in (True, False):
                v = next((k for k, aliases in s["values"].items()
                          if any(_matches(words(a), p, exact) for a in aliases)), None)
                if v is not None:
                    break
        elif s["type"] == "integer":
            v = _integer(text, p)
        elif s["type"] == "number":
            v = numbers.pop(0) if numbers else None
        if v is None:
            v = s.get("default")
        if v is None and s.get("optional"):
            continue
        if v is None:
            return args, name
        args[name] = v
    return args, None


def validate(cmd: dict) -> dict:
    """Command -> normalized command, or ValueError. Nothing outside the catalog passes."""
    block = BLOCKS.get(cmd.get("target"))
    if not block:
        raise ValueError(f"unknown block: {cmd.get('target')}")
    action = block["actions"].get(cmd.get("action"))
    if not action:
        raise ValueError(f"{block['id']} has no action {cmd.get('action')}")
    data, args = cmd.get("args") or {}, {}
    for name, s in action.get("args", {}).items():
        v = data.get(name, s.get("default"))
        if v is None and s.get("optional"):
            continue
        if v is None:
            raise ValueError(f"missing {name}")
        if s["type"] == "enum":
            v = str(v)
            if v not in s["values"]:
                raise ValueError(f"invalid {name}: {v}")
        else:
            v = int(v) if s["type"] == "integer" else float(v)
            if not s["min"] <= v <= s["max"]:
                raise ValueError(f"{name} outside {s['min']}..{s['max']}: {v}")
        args[name] = v
    return {"target": block["id"], "action": cmd["action"], "args": args}


def _response(cmd: dict, source: str) -> dict:
    block = BLOCKS[cmd["target"]]
    action = block["actions"][cmd["action"]]
    confirm = bool(action.get("confirm"))
    name = f"{block['spoken'][0].capitalize()}, {block['name']}"
    # on confirmation the values are repeated: a misheard number becomes audible before it counts
    values = ", ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}" for k, v in cmd["args"].items())
    speech = (f"Got it: {name}, {action['desc']}{f': {values}' if values else ''}. Confirm?"
              if confirm else f"{name}: {action['desc']}.")
    return {"command": cmd, "source": source, "confirm": confirm, "speech": speech}


def _break_tie(found: list[tuple[int, str, str]], focus: str | None) -> tuple[str, str] | list[str]:
    top = max(f[0] for f in found)
    tied = [f for f in found if f[0] == top]
    if len(tied) == 1:
        return tied[0][1], tied[0][2]
    focused = [f for f in tied if f[1] == focus]
    if focused:
        return focused[0][1], focused[0][2]
    return [f[1] for f in tied]


def by_rules(text: str, open_blocks: list[str] | None = None, focus: str | None = None) -> dict | None:
    """None = the rules did not understand. A dict with 'command' None = understood, but something is missing (speech says what)."""
    p = _clean(text)
    if not p:
        return None
    for exact in (True, False):  # exact first: in fuzzy matching "zoom" could match something else
        cited = _cited_blocks(p, exact)
        groups = [cited] if cited else [[i for i in (open_blocks or []) if i in BLOCKS], list(BLOCKS)]
        for group in groups:
            found = [(s, b, a) for b in group for s, a in [_best_action(BLOCKS[b], p, exact)] if a]
            if not found:
                continue
            choice = _break_tie(found, focus)
            if isinstance(choice, list):
                names = " or ".join(f"{BLOCKS[i]['spoken'][0].capitalize()} ({BLOCKS[i]['name']})" for i in choice)
                return {"command": None, "source": "rules", "confirm": False, "ambiguous": choice,
                        "speech": f"Which block? {names}."}
            block_id, action = choice
            block = BLOCKS[block_id]
            args, missing = _args(block, action, text, p)
            if missing:
                s = block["actions"][action]["args"][missing]
                options = f" Options: {', '.join(v[0] for v in s['values'].values())}." if s["type"] == "enum" else ""
                return {"command": None, "source": "rules", "confirm": False, "missing": missing,
                        "speech": f"{block['name']}: missing {missing}.{options}"}
            try:
                return _response(validate({"target": block_id, "action": action, "args": args}), "rules")
            except ValueError as e:
                return {"command": None, "source": "rules", "confirm": False, "speech": f"{block['name']}: {e}."}
    return None


def has_hint(text: str) -> bool:
    """Does the phrase cite some block or verb of the catalog? Without a hint, the model is not even called (a question goes to the agent)."""
    p = set(_clean(text))
    vocab = {w for b in CATALOG["blocks"] for x in b["spoken"] + b["synonyms"] for w in words(x)}
    vocab |= {w for b in CATALOG["blocks"] for a in b["actions"].values() for f in a["spoken"] for w in words(f)}
    vocab -= FILLER
    return bool(p & vocab) and len(p) <= MAX_MODEL_WORDS


def catalog_as_text() -> str:
    lines = []
    for b in CATALOG["blocks"]:
        actions = []
        for name, a in b["actions"].items():
            args = ", ".join(f"{k}: {'|'.join(s['values']) if s['type'] == 'enum' else f'{s['type']} {s['min']}..{s['max']}'}"
                             for k, s in a.get("args", {}).items())
            actions.append(f"{name}({args}) = {a['desc']}")
        lines.append(f"{b['id']} {b['name']} (\"{b['spoken'][0]}\"): " + "; ".join(actions))
    return "\n".join(lines)


INSTRUCTIONS = """You translate an astronaut's request into ONE interface command from the catalog below.
Answer only the JSON {"target", "action", "args"}. Use only blocks, actions and arguments from the catalog.
If the request is a question, a report or does not fit any action, answer {"target": "none", "action": "none", "args": {}}.
Never invent a coordinate: only use numbers the astronaut said."""


def by_model(text: str, open_blocks: list[str] | None = None) -> dict | None:
    """Local Gemma with the output bound to a schema. None = not a command (or model down)."""
    actions = sorted({a for b in CATALOG["blocks"] for a in b["actions"]} | {"none"})
    schema = {"type": "object", "required": ["target", "action", "args"], "properties": {
        "target": {"type": "string", "enum": [*BLOCKS, "none"]},
        "action": {"type": "string", "enum": actions},
        "args": {"type": "object"}}}
    body = json.dumps({
        "model": MODEL, "stream": False, "format": schema, "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 80},
        "messages": [
            {"role": "system", "content": f"{INSTRUCTIONS}\n\nCATALOG:\n{catalog_as_text()}"},
            {"role": "user", "content": f"Blocks open now: {', '.join(open_blocks or []) or 'none'}.\nREQUEST: {text}"},
        ],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            cmd = json.loads(json.load(r)["message"]["content"])
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None  # model down: the phrase goes on as a question, and the agent says it is down
    if cmd.get("target") == "none":
        return None
    try:
        return _response(validate(cmd), "model")
    except ValueError:
        return None


def interpret(text: str, open_blocks: list[str] | None = None, focus: str | None = None,
              use_model: bool = True) -> dict:
    """{command|None, source: rules|model|None, confirm, speech}. command None and speech None = not a command."""
    r = by_rules(text, open_blocks, focus)
    if r is None and use_model and has_hint(text):
        r = by_model(text, open_blocks)
    return r or {"command": None, "source": None, "confirm": False, "speech": None}
