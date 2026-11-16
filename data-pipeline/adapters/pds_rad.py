"""Adapter for RAD (radiation) data from the PDS-PPI (UCLA) -- item 8 of
the feature 01 table.

Real format (not clearly documented publicly, confirmed
on 2026-11-11 against RAD_RDR_SIS.HTM and the real sol 4650 file):
a single .TXT file per sol, with **1306 sections** in the format
`[SECTION_NAME: NN]` followed by free-form body lines. Most of them
(COUNTERS, HISTOGRAMS, PHA, LET...) are fine engineering/science data,
out of scope for this adapter -- here we extract only what feature 05
(conditions panel) needs: the total dose per observation.

How to put the pieces together:
  - `[OBSERVATION: NN]` exists for every observation of the sol (NN =
    00, 01, 02, 03...) and has `START_OBS_MARS`/`START_OBS_UTC` (start
    time, LMST and UTC) and `OBS_DURATION` (seconds).
  - `[DOSIMETRY_TOTAL_DOSE_E: NN]` only exists at EVEN indices (not
    every observation downlinks full dosimetry telemetry) and carries a
    single numeric value: the dose of detector E, in microGy/hour
    (confirmed in RAD_RDR_SIS.HTM, section 4.2.1.6 -- unit recorded
    as "microGray/hour" although the note is not 100% explicit about
    whether it is a rate or the dose accumulated over the window).
  - The "join" between the two sections is by the same index NN.

Validated against sol 4650: dose ~6.6 µGy/h -> ~158 µGy/day, same
order of magnitude as the known daily dose on the surface of Mars
(~200-250 µGy/day).

Directory structure (same bucket convention as REMS, different
host):
  https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/
    SOL_<lo>_<hi>/RAD_RDR_<year>_<doy>_<hh>_<mm>_<sol>_V00.TXT
"""

import re

import requests

BASE_URL = "https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA"

SECTION_HEADER_RE = re.compile(r"^\[([A-Z_0-9]+): (\d+)\]$")


class PDSRadAdapter:
    category = "radiation"

    def _find_bucket(self, sol: int) -> str:
        r = requests.get(f"{BASE_URL}/", timeout=20)
        r.raise_for_status()
        folders = re.findall(r'href="(SOL_\d+_\d+)/"', r.text)
        for f in folders:
            lo, hi = (int(v) for v in f.replace("SOL_", "").split("_"))
            if lo <= sol <= hi:
                return f
        raise ValueError(f"No bucket found for sol {sol}")

    def _find_filename(self, sol: int, bucket: str) -> str:
        url = f"{BASE_URL}/{bucket}/"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        # The sol in the real filename is zero-padded to 4 digits (e.g.
        # "..._0242_V00.TXT" for sol 242) -- found and fixed while fetching
        # an early-mission sol (sol 242 < 1000) for the first time; sol
        # 4650 (the only one fetched before) happened to already have 4
        # digits, which hid this bug.
        m = re.search(rf'href="(RAD_RDR_[^"]*_{sol:04d}_V\d+\.TXT)"', r.text)
        if not m:
            raise ValueError(f"RAD_RDR file for sol {sol} not found at {url}")
        return m.group(1)

    @staticmethod
    def _split_sections(text: str) -> dict[tuple[str, int], list[str]]:
        """Splits the whole file into {(section_name, index): [body_lines]}."""
        lines = text.splitlines()
        sections: dict[tuple[str, int], list[str]] = {}
        current_key = None
        current_body: list[str] = []

        for line in lines:
            m = SECTION_HEADER_RE.match(line.strip())
            if m:
                if current_key is not None:
                    sections[current_key] = current_body
                current_key = (m.group(1), int(m.group(2)))
                current_body = []
            elif current_key is not None:
                current_body.append(line)

        if current_key is not None:
            sections[current_key] = current_body

        return sections

    @staticmethod
    def _parse_observation_body(body: list[str]) -> dict:
        text = "\n".join(body)
        fields = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', text, re.M))
        return {
            "start_obs_mars": fields.get("START_OBS_MARS", "").strip('"'),
            "start_obs_utc": fields.get("START_OBS_UTC", "").strip('"'),
            "obs_duration_s": float(fields["OBS_DURATION"]) if "OBS_DURATION" in fields else None,
        }

    @staticmethod
    def _parse_dose_body(body: list[str]) -> float | None:
        for line in body:
            stripped = line.strip()
            if stripped:
                try:
                    return float(stripped)
                except ValueError:
                    return None
        return None

    def fetch_sol(self, sol: int) -> dict:
        bucket = self._find_bucket(sol)
        filename = self._find_filename(sol, bucket)

        resp = requests.get(f"{BASE_URL}/{bucket}/{filename}", timeout=60)
        resp.encoding = "latin-1"
        sections = self._split_sections(resp.text)

        observations = {
            idx: self._parse_observation_body(body)
            for (name, idx), body in sections.items()
            if name == "OBSERVATION"
        }
        doses_e = {
            idx: self._parse_dose_body(body)
            for (name, idx), body in sections.items()
            if name == "DOSIMETRY_TOTAL_DOSE_E"
        }

        readings = []
        for idx in sorted(doses_e):
            obs = observations.get(idx, {})
            readings.append(
                {
                    "index": idx,
                    "lmst": obs.get("start_obs_mars"),
                    "utc": obs.get("start_obs_utc"),
                    "duration_s": obs.get("obs_duration_s"),
                    "dose_e_ugy_per_hour": doses_e[idx],
                }
            )

        return {"sol": sol, "product_filename": filename, "readings": readings}
