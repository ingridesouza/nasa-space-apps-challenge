"""Test script for the REMS adapter (weather, PDS Atmospheres Node).

Usage:
    python scripts/fetch_rems_test.py [sol]

Without an argument, uses sol 4650 (same example cited in the feature
01 doc, section 3.2). Downloads the real environmental table of that sol
and prints some readings with a valid value (discards -999 = no data).
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.pds_rems import PDSRemsAdapter


def main() -> None:
    sol = int(sys.argv[1]) if len(sys.argv) > 1 else 4650

    adapter = PDSRemsAdapter()
    print(f"[1/2] Fetching environmental table for sol {sol}...")
    result = adapter.fetch_sol(sol)
    print(f"      product_id: {result['product_id']}")
    print(f"      {len(result['readings'])} readings on the sol")

    print("[2/2] First readings with a valid pressure and temperature value:")
    count = 0
    for reading in result["readings"]:
        pressure = reading.get("BAROCAP_PRESSURE_1")
        temp = reading.get("BOOM1_AIR_TEMP")
        if pressure is not None and temp is not None:
            temp_c = temp - 273.15
            print(
                f"      {reading['LMST']}: "
                f"pressure={pressure:.2f} Pa | "
                f"air_temp={temp_c:.1f}°C | "
                f"UV_A={reading.get('UV_A')} | "
                f"humidity={reading.get('HUMIDITY_CHANNEL_A')}%"
            )
            count += 1
        if count >= 5:
            break


if __name__ == "__main__":
    main()
