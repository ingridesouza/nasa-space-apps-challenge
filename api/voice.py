"""Feature 08, voice: local transcription (faster-whisper) of the audio the
browser already sends raw as 16 kHz mono float32.

It does not decode files: the PyAV of this environment (19) is incompatible with
faster-whisper 1.2.1, and the MediaRecorder WebM was the path that failed.
Plan: docs/feature-08-voz-plano-execucao.md."""

import math
import os
import re
import threading
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).resolve().parent.parent / "data" / "local" / "whisper"
# large-v3: 8.7 s per phrase on this CPU and heard "rota"; turbo (6.8 s) heard "hota" -- the CPU
# cost is in the encoder, the same in both. The confirmation "yes/no" goes to small (fast).
MODEL = os.environ.get("H2G2_WHISPER", "large-v3")
CONFIRM_MODEL = os.environ.get("H2G2_WHISPER_CONFIRM", "small")
# "auto" detects the language, but costs one more pass over the model (16.9 s instead of 8.7 s)
# and fails on short phrases ("Sim." became "Seeing.").
LANGUAGE = os.environ.get("H2G2_LANGUAGE", "en")
RATE_HZ = 16000
# Words Whisper should favor: activation, domain and destinations accepted by voice.
# "EVA" was left out: it pulled "Hey Marvin" towards "EVA". "Hey Marvin" goes in whole, not only "Marvin".
VOCABULARY = ("Hey Marvin, route, base, habitat, boxwork, Curiosity, Altadena, Totoral, Sillar, "
              "Gale crater, sol, slope, radiation, science target, safety, climb, "
              "emergency, toxic gas, leak, oxygen, suit, pressure, dust, "
              "Atlas, Vega, Polaris, Orion, Rigel, Altair, Draco, Castor, Pollux, Antares, zoom, layer, panorama, card, next")
MAX_NO_SPEECH = 0.6    # no_speech_prob above this: the segment is silence/noise
# avg_logprob below this: the model is guessing. -0.6 = confidence 0.55; on the 1st real recording
# (11/14, laptop microphone) the invented phrases came with 0.50-0.55 and the good ones with 0.61+.
# shortcut: calibrated with 10 phrases from one person (in Portuguese); recalibrate with
# make voice-measure and more voices.
MIN_LOGPROB = -0.6


def choose_language(probs: dict[str, float]) -> str:
    """English by default; Portuguese only if it clearly dominates. On short phrases
    detection is undecided."""
    return "pt" if probs.get("pt", 0) > 0.5 and probs["pt"] > 2 * probs.get("en", 0) else "en"


@lru_cache(maxsize=2)
def _load(name: str):
    from faster_whisper import WhisperModel  # late import: the API starts without the model
    return WhisperModel(name, device="cpu", compute_type="int8",
                        download_root=str(MODELS_DIR), local_files_only=True)


_load_lock = threading.Lock()


def _model(name: str):
    # without the lock, preloading and the 1st utterance loaded two copies of large-v3 (ran out of RAM)
    with _load_lock:
        return _load(name)


# The "Confirm?" answer only has to contain yes/no, so a lower confidence is safe there: small heard
# "one, yes." at -0.70 and "no concept" at -0.93, and the -0.6 cut cancelled every route.
# shortcut: calibrated with one person's yes/no; recalibrate with make voice-measure and more voices.
MIN_LOGPROB_CONFIRM = -1.2


def transcribe(audio: np.ndarray, model: str = MODEL, language: str | None = None, min_logprob: float = MIN_LOGPROB) -> dict:
    """audio: float32 mono 16 kHz. Returns {text, language, confidence};
    text None when there is no clear speech -- never an invented phrase."""
    m = _model(model)
    language = language or (choose_language(dict(m.detect_language(audio, vad_filter=True)[2])) if LANGUAGE == "auto" else LANGUAGE)
    segments, _ = m.transcribe(
        audio, language=language, beam_size=5, hotwords=VOCABULARY,
        condition_on_previous_text=False, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 600, "speech_pad_ms": 400})
    good = [s for s in segments if s.no_speech_prob < MAX_NO_SPEECH and s.avg_logprob > min_logprob]
    text = " ".join(s.text.strip() for s in good).strip()
    if not text:
        return {"text": None, "language": language, "confidence": None}
    confidence = math.exp(sum(s.avg_logprob for s in good) / len(good))
    return {"text": text, "language": language, "confidence": round(confidence, 2)}


# ---- phase 2: understand the command (rules, no model: 5 destinations fit in a list) ----

ACTIVATION = {"marvin", "marvim", "marvyn", "marven"}  # spellings Whisper produces
ACTIVATION_WITHIN = 3  # "Hello Marvin, ..." / "Hey, Marvin, ..." / "Hi, oh Marvin, ..."
# A route command is short ("Marvin, take me to the boxwork ridges" = 7). A long report
# ("I'm in the middle of a route and a gas showed up") goes whole to the model, even mentioning "route".
MAX_COMMAND_WORDS = 8
ROUTE = {"route", "path", "take", "go", "lead", "walk", "navigate"}
RETURN = {"return", "back"}
# "yeah"/"yep": how Whisper small writes a short "yes"; only valid in the "Confirm?" window
YES = {"yes", "yeah", "yep", "confirm", "confirmed", "affirmative", "ok", "okay", "correct"}
NO = {"no", "nope", "cancel", "negative", "stop"}
PATH_WORDS = ROUTE | {"get", "way", "paths", "options", "routes"}
_LOOSE_WORDS = {"the", "of", "by", "vs", "hole", "ridge", "ridges", "depression", "drill", "cementation", "sulfate"}


def words(text: str) -> list[str]:
    """Lowercase, no accents, no punctuation: only what the person said."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", plain.lower())


# Destination names need a stricter cut: "fast" vs "east" is 0.75 and opened a route to "Boxwork east
# contact"; real misspellings sit well above ("altadina" 0.88, "sarjama" 0.92, "totorol" 0.86).
NAME_CUTOFF = 0.8


def _similar(word: str, vocabulary, cutoff: float = 0.75) -> bool:
    """Tolerates the typical Whisper error ("rout" for "route") without matching short words by accident."""
    return word in vocabulary or (len(word) >= 4 and bool(get_close_matches(word, vocabulary, n=1, cutoff=cutoff)))


def destination_keys(name: str) -> set[str]:
    """'Boxwork ridges — sulfate cementation' -> {boxwork}: the name before the dash."""
    return {w for w in words(name.split("—")[0]) if len(w) >= 4 and w not in _LOOSE_WORDS}


def mentioned_destination(text: str, destinations: list[dict]) -> dict | None:
    """Destination named in a phrase of any length (question to the agent): the one with most name words.
    With 2+ words in the name, requires 2 ("grande" alone is not Monte Grande)."""
    w = words(text)
    best, n = None, 0
    for d in destinations:
        keys = d.get("keys") or destination_keys(d["name"])
        hits = sum(any(_similar(x, {k}, NAME_CUTOFF) for x in w) for k in keys)
        if hits >= min(2, len(keys)) and hits > n:
            best, n = d, hits
    return best


def asks_nearest_target(text: str) -> bool:
    """"closest science target?": the nearest comes from the rule, not the model."""
    w = set(words(text))
    return bool(w & {"closest", "nearest", "near"}) and bool(w & {"target", "targets", "science"})


def asks_path(text: str) -> bool:
    return any(_similar(x, PATH_WORDS) for x in words(text))


def interpret(text: str, destinations: list[dict], require_activation: bool = True) -> dict:
    """destinations: [{name, lat, lon, keys?, base?}] (base, targets from the database, marked point).
    Returns {activated, intent: route|yes|no|question|none, destination, question}.
    Never returns a coordinate outside the list: an unknown destination becomes None."""
    w = words(text)
    # short spellings only exact: in fuzzy matching, other names could match
    i = next((i for i, x in enumerate(w[:ACTIVATION_WITHIN]) if x in ACTIVATION or _similar(x, {"marvin"})), None)
    activated = i is not None
    rest = w[i + 1:] if activated else w
    # what comes after "Marvin", with the original accents and punctuation (same word split)
    tokens = list(re.finditer(r"[^\W_]+", text))
    question = text[tokens[i].end():].lstrip(" ,.!?;:") if activated and i < len(tokens) else text.strip()
    base = {"activated": activated, "destination": None, "question": question}
    if require_activation and not activated:
        return {**base, "intent": "none"}
    if not rest:
        return {**base, "intent": "none"}
    # exact, not fuzzy: "open" is 0.75 from "nope" and "Marvin, Atlas, open" became a "no"; the
    # spellings Whisper really writes ("yeah", "yep", "nope") are already in the sets
    if len(rest) <= 3 and any(x in YES for x in rest):
        return {**base, "intent": "yes"}
    if len(rest) <= 3 and any(x in NO for x in rest):
        return {**base, "intent": "no"}
    going_back = any(_similar(x, RETURN) for x in rest)
    if len(rest) > MAX_COMMAND_WORDS or not (going_back or any(_similar(x, ROUTE) for x in rest)):
        return {**base, "intent": "question"}
    for d in destinations:
        keys = d.get("keys") or destination_keys(d["name"])
        if any(_similar(x, keys, NAME_CUTOFF) for x in rest):
            return {**base, "intent": "route", "destination": d}
    home = next((d for d in destinations if d.get("base")), None)
    if going_back and home:
        return {**base, "intent": "route", "destination": home}
    return {**base, "intent": "question"}  # "route" with no known destination: the model answers
