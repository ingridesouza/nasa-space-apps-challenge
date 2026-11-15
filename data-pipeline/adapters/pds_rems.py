"""Adapter for REMS (weather) data from the PDS Atmospheres Node -- item 7
of the feature 01 table.

Unlike Mars Trek (tiled raster), REMS is a tabular series per
sol: one sol = one `SOL<nnnn>/` folder with an ENVRDR table (calibrated
environmental) in comma-delimited text, with a PDS4 XML label that
describes the 71 columns (pressure, air temperature, UV, humidity, etc).

Confirmed on 2026-11-11 against the real sol 4650: pressure ~709 Pa,
air temperature ~-69.5°C (pre-dawn), plausible values for Mars.

Real file structure (not documented publicly, discovered
by browsing the directory):
  https://atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated/
    SOL_<lo>_<hi>/SOL<sol>/RME_<sclk>RNV<sol>0000000_______P1.{xml,TAB}
  -- the SOL_<lo>_<hi> buckets cover ranges of ~90-135 sols each.
"""

import csv
import io
import re

import requests

BASE_URL = "https://atmos.nmsu.edu/PDS/data/PDS4/msl_rems_bundle/data_calibrated"

#: most useful columns for the conditions panel (feature 05) -- the real
#: table has 71 columns, most of them uncertainty/housekeeping.
RELEVANT_FIELDS = {
    "TIMESTAMP": None,
    "LMST": None,
    "BOOM1_AIR_TEMP": "kelvin",
    "BOOM2_AIR_TEMP": "kelvin",
    "BAROCAP_PRESSURE_1": "pascal",
    "BAROCAP_PRESSURE_2": "pascal",
    "UV_A": "W/m2",
    "UV_B": "W/m2",
    "UV_C": "W/m2",
    "UV_ABC": "W/m2",
    "HUMIDITY_CHANNEL_A": "%",
    "BRIGHTNESS_TEMP_B": "kelvin",  # ground sensor (GTS), channel B: ground temperature
    "GTS_CONFIDENCE_LEVEL": None,   # 6 bytes "0/1"; comes as a number (leading zeros are lost)
}


class PDSRemsAdapter:
    category = "atmospheric"

    def _find_bucket(self, sol: int) -> str:
        r = requests.get(f"{BASE_URL}/", timeout=20)
        r.raise_for_status()
        folders = re.findall(r'href="(SOL_\d+_\d+)/"', r.text)
        for f in folders:
            lo, hi = (int(v) for v in f.replace("SOL_", "").split("_"))
            if lo <= sol <= hi:
                return f
        raise ValueError(f"No bucket found for sol {sol}")

    def _find_product_prefix(self, sol: int, bucket: str) -> str:
        """Finds the name of the RNV product (calibrated environmental) of that sol --
        the numeric prefix (spacecraft clock) changes every sol."""
        url = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        m = re.search(r'href="([^"]+RNV\d+_+P\d)\.TAB"', r.text)  # P1 on new sols, P3 on old ones
        if not m:
            raise ValueError(f"RNV product not found at {url}")
        return m.group(1)

    def fetch_sol(self, sol: int) -> dict:
        """Downloads the environmental table (RNV) of a sol and returns a list
        of readings already filtered to the relevant fields (invalid
        instrument sections come as -999/-999.00, discarded here)."""
        bucket = self._find_bucket(sol)
        prefix = self._find_product_prefix(sol, bucket)
        base = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"

        xml = requests.get(base + prefix + ".xml", timeout=20).text
        field_blocks = re.findall(r"<Field_Character>.*?</Field_Character>", xml, re.S)
        names = [re.search(r"<name>([^<]+)</name>", f).group(1) for f in field_blocks]

        tab = requests.get(base + prefix + ".TAB", timeout=60)
        text = tab.content.decode("ascii", errors="replace")
        return {"sol": sol, "product_id": prefix, "readings": self._read_rows(text, names)}

    def fetch_sol_sample(self, sol: int, n: int = 180) -> dict:
        """Same as fetch_sol, but downloads only n rows spread over the sol in a
        single HTTP request with several Ranges (~120 KB instead of ~20 MB). The PDS
        Apache returns the whole file above 200 ranges (MaxRanges). The
        table is Table_Character: every row has record_length bytes."""
        bucket = self._find_bucket(sol)
        prefix = self._find_product_prefix(sol, bucket)
        base = f"{BASE_URL}/{bucket}/SOL{sol:05d}/"

        xml = requests.get(base + prefix + ".xml", timeout=20).text
        field_blocks = re.findall(r"<Field_Character>.*?</Field_Character>", xml, re.S)
        names = [re.search(r"<name>([^<]+)</name>", f).group(1) for f in field_blocks]
        size = int(re.search(r"<record_length[^>]*>(\d+)<", xml).group(1))
        total = int(re.search(r"<records>(\d+)</records>", xml).group(1))
        starts = sorted({i * total // n * size for i in range(n)})
        ranges = ",".join(f"{o}-{o + size - 1}" for o in starts)
        tab = requests.get(base + prefix + ".TAB", headers={"Range": f"bytes={ranges}"}, timeout=60)
        tab.raise_for_status()
        # multipart response: only the data rows remain (they start with the spacecraft clock)
        rows = [l for l in tab.content.decode("ascii", errors="replace").splitlines()
                if re.match(r"\s*\d+,\"\d{5}M", l)]
        return {"sol": sol, "product_id": prefix, "readings": self._read_rows("\n".join(rows), names)}

    @staticmethod
    def _read_rows(text: str, names: list[str]) -> list[dict]:
        reader = csv.reader(io.StringIO(text), skipinitialspace=True)
        readings = []
        for row in reader:
            row = [v.strip() for v in row]
            full = dict(zip(names, row))
            reading = {}
            for field in RELEVANT_FIELDS:
                val = full.get(field, "")
                if val in ("-999.00", "-999.000", "-9.990E+02", ""):
                    reading[field] = None
                else:
                    try:
                        reading[field] = float(val)
                    except ValueError:
                        reading[field] = val.strip('"')
            readings.append(reading)
        return readings
