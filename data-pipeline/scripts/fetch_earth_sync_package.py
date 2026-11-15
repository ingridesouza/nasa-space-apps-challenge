"""ETL for the Earth-Mars sync demo (feature 09 extension) -- see
docs/feature-09-earth-mars-sync.md for the full real-world grounding and
the honesty rules this script and api/earth_sync.py follow together.

Real-world analog: MSL does not have continuous contact with Earth. It
relays through orbiters (Mars Reconnaissance Orbiter, Mars Odyssey) during
scheduled UHF passes, roughly twice per sol in JPL's own mission-planning
estimate (~250 Mb per sol via MRO, recorded and played back later; ~75 Mb
via Odyssey, closer to real time) -- spaceflightnow.com, 2012-07-31,
citing a JPL relay briefing. Outside those passes, and during the ~2-week
solar conjunction blackout that recurs roughly every 26 months (NASA held
commands to its Mars fleet from 2023-11-11 to 2023-11-25 during the most
recent one), there is no contact with Earth at all.

This script fetches ONE real sol ahead of time -- something the rest of
the system has not loaded yet -- and writes it to
data/local/earth_sync/pending.json, separate from data/local/conditions/
(the active cache api/conditions.py reads). That separation is the whole
point: api/earth_sync.py never touches the network, it only reveals this
already-fetched file on request, simulating the moment one of those
scheduled passes delivers it. No live download happens at demo time
(CLAUDE.md: offline at runtime, downloads only here, at build time).

Usage:
    python scripts/fetch_earth_sync_package.py [sol]   # default: 4800
"""

import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rad import PDSRadAdapter
from adapters.pds_rems import PDSRemsAdapter
from scripts.cache_conditions import summarize_rad, summarize_rems  # same summary shape as the active cache

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "earth_sync")
OUT_PATH = os.path.join(OUT_DIR, "pending.json")

# A real sol newer than api/main.py's REFERENCE_SOL (4650) and within the
# PDS buckets already confirmed published this session (up to 4843, see
# scripts/cache_climatology.py) -- real data the running demo has simply
# not loaded yet, not a fabricated "future" sol.
DEFAULT_SOL = 4800


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOL
    if os.path.exists(OUT_PATH):
        print(f"A pending package already exists at {OUT_PATH} (sol {json.load(open(OUT_PATH, encoding='utf-8'))['sol']}); "
              "delete it to fetch a different sol.")
        return

    print(f"[1/2] Downloading REMS for sol {sol}...")
    rems = PDSRemsAdapter().fetch_sol(sol)
    rems_summary = summarize_rems(rems["readings"])
    print("     ", rems_summary)

    print(f"[2/2] Downloading RAD for sol {sol}...")
    try:
        rad = PDSRadAdapter().fetch_sol(sol)
        rad_summary = summarize_rad(rad["readings"])
    except ValueError as e:
        print(f"      RAD not available for sol {sol}: {e}")
        rad_summary = {"mean_dose_ugy_per_hour": None, "estimated_dose_ugy_per_day": None,
                       "peak_dose_ugy_per_hour": None, "n_readings": 0}
    print("     ", rad_summary)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"sol": sol, "rems": rems_summary, "rad": rad_summary}, f, ensure_ascii=False, indent=2)

    print(f"\nPending Earth-sync package saved to {OUT_PATH} (not yet visible to the running system).")


if __name__ == "__main__":
    main()
