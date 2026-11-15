"""Feature 06: REMS climatology for the offline local forecast.

Downloads a sample of 1 sol every STEP sols of the whole mission (~3 Martian
years) and writes to data/local/conditions/climatology.json the summary of
each sol with the Ls (season) from Mars24. The API (api/forecast.py) only reads this
file.

Each sol comes from fetch_sol_sample (180 rows spread out, ~120 KB). So
max./min. are "of the 180 readings", not the 1 Hz peak of sol_<n>.json:
the forecast uses only this definition, on both sides of the computation.

Usage:
    python scripts/cache_climatology.py        # resumes where it stopped
"""

import json
import os
import sys
from statistics import mean, median

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from adapters.pds_rad import PDSRadAdapter  # noqa: E402
from adapters.pds_rems import PDSRemsAdapter  # noqa: E402
from mars_time import ls, sol_date  # noqa: E402 -- a single Mars24 implementation

STEP = 20
LAST_SOL = 4843  # last bucket published in the PDS on 14/11/2026 (SOL_04710_04843)
EXTRAS = (4650,)  # API reference sol: it must be in the same definition
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "conditions", "climatology.json")


def ground_valid(l: dict) -> bool:
    """Usable ground sensor reading: daytime only (08h–17h local; at night channel B gives
    2–13 K, garbage), good recalibration (byte 3) and no shadow in the field of view (byte 5),
    by the PDS's own flags, and within physics (150–320 K)."""
    t, conf, lmst = l.get("BRIGHTNESS_TEMP_B"), l.get("GTS_CONFIDENCE_LEVEL"), l.get("LMST")
    if not isinstance(t, float) or not isinstance(conf, float) or not isinstance(lmst, str) or "M" not in lmst:
        return False
    bytes_ = f"{int(conf):06d}"
    return 8 <= int(lmst.split("M")[1][:2]) <= 17 and bytes_[3] == "1" and bytes_[5] == "1" and 150 <= t <= 320


def sample_summary(readings: list[dict]) -> dict:
    temps = [l["BOOM1_AIR_TEMP"] - 273.15 for l in readings if l.get("BOOM1_AIR_TEMP") is not None]
    pressures = [l["BAROCAP_PRESSURE_1"] for l in readings if l.get("BAROCAP_PRESSURE_1") is not None]
    # ground at noon (11h–14h): the median copes with GTS noise better than min./max. of loose readings
    ground = [l["BRIGHTNESS_TEMP_B"] - 273.15 for l in readings
              if ground_valid(l) and 11 <= int(l["LMST"].split("M")[1][:2]) <= 14]
    # daily curve by local solar hour (LMST "04650M12:15:35.532" -> 12): F06 EVA window
    by_hour = {}
    for l in readings:
        if l.get("BOOM1_AIR_TEMP") is not None and isinstance(l.get("LMST"), str) and "M" in l["LMST"]:
            by_hour.setdefault(int(l["LMST"].split("M")[1][:2]), []).append(l["BOOM1_AIR_TEMP"] - 273.15)
    return {
        "temp_min_c": round(min(temps), 1) if temps else None,
        "temp_max_c": round(max(temps), 1) if temps else None,
        "pressure_pa": round(mean(pressures), 1) if pressures else None,
        "hourly_temp": {str(h): round(mean(v), 1) for h, v in sorted(by_hour.items())},
        "ground_noon_c": round(median(ground), 1) if len(ground) >= 5 else None,
    }


def sol_dose(rad: PDSRadAdapter, sol: int) -> float | None:
    """RAD dose for the whole sol (µGy/day, detector E), as in cache_conditions.py."""
    doses = [l["dose_e_ugy_per_hour"] for l in rad.fetch_sol(sol)["readings"] if l.get("dose_e_ugy_per_hour") is not None]
    return round(mean(doses) * 24, 1) if doses else None


def main() -> None:
    climate = {}
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as f:
            climate = {c["sol"]: c for c in json.load(f)["sols"]}
    adapter, rad = PDSRemsAdapter(), PDSRadAdapter()
    sols = sorted(set(range(STEP, LAST_SOL + 1, STEP)) | set(EXTRAS))
    for i, sol in enumerate(sols, 1):
        if "dose_ugy_day" in climate.get(sol, {}):
            continue
        try:
            readings = adapter.fetch_sol_sample(sol)["readings"]
        except Exception as e:  # sol without an RNV product in the PDS (gap) or network: continue without it
            print(f"[{i}/{len(sols)}] sol {sol}: no data ({e.__class__.__name__})")
            continue
        try:
            dose = sol_dose(rad, sol)
        except Exception as e:  # sol without a RAD file: continue with REMS only
            print(f"   sol {sol}: no RAD ({e.__class__.__name__})")
            dose = None
        climate[sol] = {"sol": sol, "ls": round(ls(sol_date(sol)), 1), **sample_summary(readings), "dose_ugy_day": dose}
        print(f"[{i}/{len(sols)}] sol {sol}: {climate[sol]}")
        # writes after each sol: long download, resumable
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"source": "MSL REMS RNV (PDS Atmospheres), 180 readings per sol; MSL RAD RDR (PDS-PPI), detector E dose; Ls by Mars24",
                       "step_sols": STEP, "sols": sorted(climate.values(), key=lambda c: c["sol"])},
                      f, ensure_ascii=False, indent=1)
    print(f"\n{len(climate)} sols in {OUT}")


if __name__ == "__main__":
    main()
