"""Feature 09 (extension): simulated Earth-Mars sync -- see
docs/feature-09-earth-mars-sync.md for the full real-world grounding
(relay passes, solar conjunction) and why this is architected this way.

No network call happens here, ever, at any point -- the data this module
reveals was already fetched by
data-pipeline/scripts/fetch_earth_sync_package.py, at build time, and
sits untouched in data/local/earth_sync/pending.json until a demo asks
for it. This module only moves that one local file into
data/local/conditions/ (the same folder api/conditions.py already reads
for every other sol) and reports what changed -- a local file operation,
simulating the moment a scheduled relay pass would have delivered it,
never a live transmission."""

import json
import os

from fastapi import APIRouter, HTTPException

from alerts import sol_time_and_alerts
from conditions import CONDITIONS_DIR, get_cached_conditions

router = APIRouter()

PENDING_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "earth_sync", "pending.json")

# Real, documented range for the Earth-Mars one-way radio delay (NASA/JPL,
# varies with orbital geometry) -- used only to label the simulated wait,
# never computed live from orbital mechanics here (out of scope, see the
# planning doc). The demo cannot actually wait up to 24 minutes, so the
# frontend runs a short, clearly-labeled simulated pause instead.
REAL_DELAY_RANGE_MIN = (4, 24)


def _pending() -> dict | None:
    if not os.path.isfile(PENDING_PATH):
        return None
    with open(PENDING_PATH, encoding="utf-8") as f:
        return json.load(f)


@router.get("/api/earth-sync/status")
def earth_sync_status():
    """Whether a real, pre-fetched package is waiting to be revealed --
    never the content itself (that would spoil the "what changed" moment
    the apply endpoint is for)."""
    pkg = _pending()
    return {
        "pending": pkg is not None,
        "sol": pkg["sol"] if pkg else None,
        "real_delay_range_min": REAL_DELAY_RANGE_MIN,
    }


@router.post("/api/earth-sync/apply")
def earth_sync_apply():
    """Reveals the pending package: writes it to data/local/conditions/
    (same format and folder as any other cached sol, so every existing
    endpoint that reads a sol -- /api/conditions, /api/ask -- picks it up
    with no special case) and reports the real difference against
    whatever alerts that sol would have shown with no radiation/weather
    data at all (there is no "previous version" of this sol to diff
    against -- it was never loaded before)."""
    pkg = _pending()
    if pkg is None:
        raise HTTPException(status_code=404, detail="No pending Earth-sync package -- run "
                            "data-pipeline/scripts/fetch_earth_sync_package.py first")

    sol = pkg["sol"]
    out_path = os.path.join(CONDITIONS_DIR, f"sol_{sol}.json")
    if not os.path.isfile(out_path):
        os.makedirs(CONDITIONS_DIR, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pkg, f, ensure_ascii=False, indent=2)

    peak = (pkg.get("rad") or {}).get("peak_dose_ugy_per_hour")
    peak_per_day = peak * 24 if peak is not None else None
    _, alerts = sol_time_and_alerts(sol, peak_dose_ugy_per_day=peak_per_day)

    os.remove(PENDING_PATH)  # one-shot reveal: applying it again needs a fresh fetch, like a real pass
    return {"sol": sol, "rems": pkg["rems"], "rad": pkg["rad"], "alerts": alerts}
