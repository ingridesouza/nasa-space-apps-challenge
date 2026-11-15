"""Test script for the RAD adapter (radiation, PDS-PPI/UCLA).

Usage:
    python scripts/fetch_rad_test.py [sol]

Without an argument, uses sol 4650 (same example as REMS, for comparison).
Downloads the real file of the sol, extracts the detector E dose per
observation (unit: µGy/h) and prints the first readings, plus the
estimated daily dose (mean of the readings × 24h) to compare with the
known Mars range (~200-250 µGy/day).
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rad import PDSRadAdapter


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650

    adapter = PDSRadAdapter()
    print(f"[1/2] Fetching RAD file for sol {sol}...")
    result = adapter.fetch_sol(sol)
    print(f"      file: {result['product_filename']}")
    print(f"      {len(result['readings'])} readings with full dosimetry on the sol")

    print("[2/2] First readings:")
    doses = []
    for reading in result["readings"][:5]:
        dose = reading["dose_e_ugy_per_hour"]
        print(
            f"      obs {reading['index']:>3} | {reading['lmst']} (LMST) | "
            f"duration {reading['duration_s']:.0f}s | dose_E = {dose:.4f} µGy/h"
        )

    for reading in result["readings"]:
        if reading["dose_e_ugy_per_hour"] is not None:
            doses.append(reading["dose_e_ugy_per_hour"])

    if doses:
        mean = sum(doses) / len(doses)
        print(f"\n      mean dose of the sol: {mean:.4f} µGy/h -> ~{mean * 24:.1f} µGy/day estimated")


if __name__ == "__main__":
    main()
