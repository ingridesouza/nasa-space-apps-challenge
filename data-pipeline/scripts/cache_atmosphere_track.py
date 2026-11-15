"""Atmospheric layer: REMS (and RAD dose) for each sol the rover stopped inside
the boxwork crop, tied to its position on that sol.

REMS and RAD measure only where the rover is. There is no measured atmospheric map
at the meter scale; what can go on the map with real data is "what the rover
measured at each stop". The position of each sol is the last stop of that sol
(MSL_waypoints.json): REMS covers the whole sol, so readings taken before
the day's last leg are attributed to the final point.

Same summary definition as the F06 climatology (180 readings per sol, ground
only by day and with the PDS quality flag): reuses sample_summary and
sol_dose from cache_climatology.py.

Output: data/local/conditions/atmosphere_track.json (only sols with data).
Sols after the last PDS bucket are left out of the file; the API returns them
with null values.

Usage:
    python scripts/cache_atmosphere_track.py      # resumes where it stopped (~13 s per sol)
"""

import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from adapters.pds_rad import PDSRadAdapter  # noqa: E402
from adapters.pds_rems import PDSRemsAdapter  # noqa: E402
from cache_climatology import LAST_SOL, sample_summary, sol_dose  # noqa: E402
from mars_time import ls, sol_date  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
WAYPOINTS = os.path.join(ROOT, "data", "local", "rover_waypoints.json")
OUT = os.path.join(ROOT, "data", "local", "conditions", "atmosphere_track.json")
CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")
FIELDS = ("temp_min_c", "temp_max_c", "pressure_pa")  # ground (GTS) left out: wrong channel B, see docs/feature-06


def stops_by_sol() -> dict[int, dict]:
    """Last stop of each sol inside the crop (DTM bbox in layers.yaml)."""
    with open(CONFIG, encoding="utf-8") as f:
        b = yaml.safe_load(f)["layers"]["dtm_hirise_1m"]["test_bbox"]
    with open(WAYPOINTS, encoding="utf-8") as f:
        stops = json.load(f)
    last = {}
    for p in stops:
        if b["min_lon"] <= p["lon"] <= b["max_lon"] and b["min_lat"] <= p["lat"] <= b["max_lat"]:
            if p["sol"] not in last or (p["site"], p["drive"]) > (last[p["sol"]]["site"], last[p["sol"]]["drive"]):
                last[p["sol"]] = p
    return last


def save(track: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": "MSL REMS RNV (PDS Atmospheres), 180 readings per sol; MSL RAD RDR (PDS-PPI), detector E dose; "
                             "position = last stop of the sol (MSL_waypoints.json, MMGIS); Ls by Mars24",
                   "last_pds_sol": LAST_SOL, "sols": sorted(track.values(), key=lambda c: c["sol"])},
                  f, ensure_ascii=False, indent=1)


def main() -> None:
    track = {}
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as f:
            track = {c["sol"]: c for c in json.load(f)["sols"]}
    rems, rad = PDSRemsAdapter(), PDSRadAdapter()
    stops = {s: p for s, p in stops_by_sol().items() if s <= LAST_SOL}
    for i, (sol, p) in enumerate(sorted(stops.items()), 1):
        if sol in track:
            continue
        try:
            summary = sample_summary(rems.fetch_sol_sample(sol)["readings"])
        except Exception as e:  # sol without an RNV product in the PDS (gap) or network: no measured point
            print(f"[{i}/{len(stops)}] sol {sol}: no REMS ({e.__class__.__name__})")
            continue
        try:
            dose = sol_dose(rad, sol)
        except Exception as e:
            print(f"   sol {sol}: no RAD ({e.__class__.__name__})")
            dose = None
        track[sol] = {"sol": sol, "lat": p["lat"], "lon": p["lon"], "elev_m": p["elev_geoid"],
                      "ls": round(ls(sol_date(sol)), 1), **{k: summary[k] for k in FIELDS}, "dose_ugy_day": dose}
        print(f"[{i}/{len(stops)}] sol {sol}: {track[sol]}")
        save(track)  # writes after each sol: long download, resumable
    print(f"\n{len(track)} sols in {OUT}")


if __name__ == "__main__":
    main()
