"""Voice phase 0 (F08): records the test phrases and measures each Whisper model.

  python measure_voice.py --record               # records the phrases on the demo microphone
  python measure_voice.py large-v3 turbo small   # time and error per model

Recordings in data/local/voice_test/ (outside git: it is someone's voice)."""

import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

from voice import RATE_HZ, interpret, transcribe, words

FOLDER = Path(__file__).resolve().parent.parent / "data" / "local" / "voice_test"
SECONDS = 6
# Destinations with the real database names, to show the action each phrase would trigger.
DESTINATIONS = [{"name": "the base", "lat": 0, "lon": 0, "keys": ["base", "habitat"], "base": True}] + [
    {"name": n, "lat": 0, "lon": 0} for n in ("Boxwork ridges", "Altadena", "Totoral / Sillar")]
PHRASES = [
    "Guide, what is the best route to the base?",
    "Guide, route to Altadena.",
    "Guide, take me to the boxwork ridges.",
    "Guide, I want to go back to the base.",
    "Guide, route to Totoral.",
    "Guide, can I climb here safely?",
    "Guide, how much radiation will I get today?",
    "Guide, is there a science target near here?",
    "Yes.",
    "No, cancel.",
]


def word_errors(expected: str, got: str) -> tuple[int, int]:
    """(errors, expected words) by the edit distance between words."""
    a, b = words(expected), words(got)
    row = list(range(len(b) + 1))
    for i, wa in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, wb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (wa != wb))
    return row[-1], len(a)


def record():
    FOLDER.mkdir(parents=True, exist_ok=True)
    for i, phrase in enumerate(PHRASES, 1):
        input(f"\n[{i}/{len(PHRASES)}] Press Enter and say within {SECONDS}s:  {phrase}")
        subprocess.run(["arecord", "-q", "-f", "S16_LE", "-r", str(RATE_HZ), "-c", "1",
                        "-d", str(SECONDS), str(FOLDER / f"{i:02d}.wav")], check=True)
    (FOLDER / "expected.txt").write_text("\n".join(PHRASES) + "\n", encoding="utf-8")
    print(f"\nRecorded in {FOLDER}")


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (RATE_HZ, 1, 2), \
            f"{path.name}: needs 16 kHz mono 16 bits (use --record)"
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def measure(models: list[str]):
    expected = (FOLDER / "expected.txt").read_text(encoding="utf-8").splitlines()
    audios = [read_wav(FOLDER / f"{i:02d}.wav") for i in range(1, len(expected) + 1)]
    summary = []
    for model in models:
        t0 = time.perf_counter()
        transcribe(audios[0], model)  # warm-up: model loading does not count per phrase
        load_s = time.perf_counter() - t0
        errors = total = 0
        times = []
        print(f"\n== {model} (load + 1st phrase {load_s:.1f}s)")
        for exp, audio in zip(expected, audios):
            t = time.perf_counter()
            r = transcribe(audio, model)
            times.append(time.perf_counter() - t)
            e, n = word_errors(exp, r["text"] or "")
            errors, total = errors + e, total + n
            action = interpret(r["text"], DESTINATIONS, require_activation=False) if r["text"] else {"intent": "not understood"}
            target = action.get("destination") and action["destination"]["name"].split("—")[0].strip()
            print(f"  {times[-1]:4.1f}s  {e} error(s)  [{r['confidence']}]  {r['text']!r}  → {action['intent']} {target or ''}")
        summary.append((model, 100 * errors / total, sum(times) / len(times), max(times)))
    print("\nmodel         error%  mean_s  worst_s")
    for m, wer, mean_s, worst in summary:
        print(f"{m:12s} {wer:6.1f}   {mean_s:6.1f}  {worst:6.1f}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--record"]:
        record()
    else:
        measure(sys.argv[1:] or ["large-v3", "turbo"])
