"""Downloads REMS+RAD for a sol and writes a local JSON summary --
`api/conditions.py` reads only this file (no network call on each
request, consistent with running 100% offline at the event).

Usage:
    python scripts/cache_conditions.py [sol]

Without an argument, uses sol 4650 (same example cited in the feature 01 doc
and already used in the REMS/RAD tests).
"""

import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rad import PDSRadAdapter
from adapters.pds_rems import PDSRemsAdapter

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "conditions")


def summarize_rems(readings: list[dict]) -> dict:
    valid = [l for l in readings if l.get("BOOM1_AIR_TEMP") is not None and l.get("BAROCAP_PRESSURE_1") is not None]
    temps_c = [l["BOOM1_AIR_TEMP"] - 273.15 for l in valid]
    pressures = [l["BAROCAP_PRESSURE_1"] for l in valid]
    uvs = [l["UV_A"] for l in valid if l.get("UV_A") is not None]
    humidities = [l["HUMIDITY_CHANNEL_A"] for l in valid if l.get("HUMIDITY_CHANNEL_A") is not None]

    return {
        "temp_min_c": round(min(temps_c), 1) if temps_c else None,
        "temp_max_c": round(max(temps_c), 1) if temps_c else None,
        "pressure_pa": round(sum(pressures) / len(pressures), 1) if pressures else None,
        "uv_peak": round(max(uvs), 2) if uvs else None,
        "humidity_pct": round(sum(humidities) / len(humidities), 1) if humidities else None,
        "n_readings": len(valid),
    }


def summarize_rad(readings: list[dict]) -> dict:
    doses = [l["dose_e_ugy_per_hour"] for l in readings if l.get("dose_e_ugy_per_hour") is not None]
    mean = sum(doses) / len(doses) if doses else None
    peak = max(doses) if doses else None
    return {
        "mean_dose_ugy_per_hour": round(mean, 2) if mean is not None else None,
        "estimated_dose_ugy_per_day": round(mean * 24, 1) if mean is not None else None,
        # peak_dose_ugy_per_hour (new field, api/solar_events.py): the
        # highest single-observation reading of the sol, not the mean --
        # a solar particle event is a short-duration rate spike that the
        # 24h mean dilutes away. Found while fetching sol 242 (2013-04-12,
        # a real recorded SEP): mean -> 233 uGy/day, but the peak reading
        # (10.87 uGy/hour) matches the ~260 uGy/day the literature cites
        # for that event almost exactly.
        "peak_dose_ugy_per_hour": round(peak, 2) if peak is not None else None,
        "n_readings": len(doses),
    }


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650
    out_path = os.path.join(OUT_DIR, f"sol_{sol}.json")
    if os.path.exists(out_path):
        # already cached: do not depend on PDS (~20 MB files, unstable connection) on every make build
        print(f"Sol {sol} already at {out_path}; skipping download (delete it to download again)")
        return

    print(f"[1/2] Downloading REMS for sol {sol}...")
    rems = PDSRemsAdapter().fetch_sol(sol)
    rems_summary = summarize_rems(rems["readings"])
    print("     ", rems_summary)

    print(f"[2/2] Downloading RAD for sol {sol}...")
    rad = PDSRadAdapter().fetch_sol(sol)
    rad_summary = summarize_rad(rad["readings"])
    print("     ", rad_summary)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"sol": sol, "rems": rems_summary, "rad": rad_summary}, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
