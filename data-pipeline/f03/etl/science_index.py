"""F04 task 2: PDS inventory over the boxwork sol window.

Reads the official PDS Geosciences lists and writes `data/science_index.csv`:

    sol, site, drive, instrument, target, file, url, n_obs

- ChemCam: master list `document/msl_ccam_obs.csv` (target, sol, RMC site/drive).
  One row per (sol, stop, target, LIBS|RMI); `n_obs` counts the observations.
- APXS: `index/index.tab`; the RWP name carries sol, site and drive. The APXS
  label does not carry the target name (TARGET_NAME = MARS): `target` stays empty and
  the link to the target is made by sol/stop in task 3.
- CheMin: `index/index.tab` of the RDR volume; only the MIN products (mineral
  abundance). The name carries sol, site and drive.

Run from data-pipeline/f03/:
    python etl/science_index.py            # downloads (or uses the cache) and writes
    python etl/science_index.py --offline  # only uses data/local/f03-cache/pds/

The raw lists stay in data/local/f03-cache/pds/ so the ETL runs without internet.
The count per instrument goes into the `pds_inventory` of MANIFEST.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
PDS = "https://pds-geosciences.wustl.edu"
CCAM = f"{PDS}/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx"
APXS = f"{PDS}/msl/msl-m-apxs-4_5-rdr-v1/mslapx_1xxx"
CMIN = f"{PDS}/msl/msl-m-chemin-4-rdr-v1/mslcmn_1xxx"

LISTS = {
    "ccam_obs.csv": f"{CCAM}/document/msl_ccam_obs.csv",
    "apxs_index.tab": f"{APXS}/index/index.tab",
    "chemin_index.tab": f"{CMIN}/index/index.tab",
}
# "Type of Product" of the master list -> instrument (darks and no-laser are left out)
CCAM_TYPES = {"1-D Single laser": "ChemCam LIBS", "Statistics": "ChemCam LIBS",
              "Image": "ChemCam RMI"}
NAME_RE = re.compile(r"(RWP|MIN)(\d{4})(\d{3})(\d{4})", re.I)
COLUMNS = ["sol", "site", "drive", "instrument", "target", "file", "url", "n_obs"]


def fetch(cache: Path, offline: bool) -> dict[str, Path]:
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, url in LISTS.items():
        dest = cache / name
        if not offline:
            print(f"downloading {url}", flush=True)
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            dest.write_bytes(r.content)
        elif not dest.exists():
            sys.exit(f"--offline without cache: missing {dest}")
        out[name] = dest
    return out


def chemcam_rows(path: Path, smin: int, smax: int) -> list[dict]:
    groups: dict[tuple, dict] = {}
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            try:
                sol, site, drive = int(r["Sol"]), int(r["RMC Site"]), int(r["RMC Drive"])
            except (ValueError, KeyError):
                continue
            inst = CCAM_TYPES.get(r["Type of Product"].strip())
            if inst is None or not smin <= sol <= smax:
                continue
            target = r["Target"].strip()
            g = groups.setdefault((sol, site, drive, inst, target), {
                "sol": sol, "site": site, "drive": drive, "instrument": inst, "target": target,
                "file": r["EDR Filename"].strip(),
                "url": f"{CCAM}/data/sol{sol:05d}/", "n_obs": 0})
            g["n_obs"] += 1
    return list(groups.values())


def index_rows(path: Path, kind: str, instrument: str, base: str, smin: int, smax: int) -> list[dict]:
    """APXS (RWP) or CheMin (MIN): rows of the volume's index.tab."""
    rows = []
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        for cols in csv.reader(f):
            cols = [c.strip() for c in cols]
            if len(cols) < 4:
                continue
            pid = cols[3]
            m = NAME_RE.search(pid)
            if not m or m.group(1).upper() != kind:
                continue
            sol, site, drive = int(m.group(2)), int(m.group(3)), int(m.group(4))
            if not smin <= sol <= smax:
                continue
            folder = cols[1].lower().rstrip("/")
            ext = ".csv"
            rows.append({"sol": sol, "site": site, "drive": drive, "instrument": instrument,
                         "target": "", "file": pid.lower() + ext,
                         "url": f"{base}/{folder}/{pid.lower()}{ext}", "n_obs": 1})
    return rows


def update_manifest(bundle: Path, counts: dict, smin: int, smax: int) -> bool:
    mf = bundle / "MANIFEST.json"
    if not mf.exists():
        return False
    data = json.loads(mf.read_text(encoding="utf-8"))
    data["pds_inventory"] = {"sol_window": {"min": smin, "max": smax},
                             "file": "data/science_index.csv", "rows_per_instrument": counts}
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--cache", default=str(ROOT.parent.parent / "data" / "local" / "f03-cache" / "pds"))
    ap.add_argument("--out", default=str(ROOT / "data" / "science_index.csv"))
    ap.add_argument("--bundle", default=str(ROOT.parent.parent / "data" / "local" / "f03"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    smin, smax = cfg["sols"]["min"], cfg["sols"]["max"]
    files = fetch(Path(args.cache), args.offline)

    rows = chemcam_rows(files["ccam_obs.csv"], smin, smax)
    rows += index_rows(files["apxs_index.tab"], "RWP", "APXS", APXS, smin, smax)
    rows += index_rows(files["chemin_index.tab"], "MIN", "CheMin", CMIN, smin, smax)
    rows.sort(key=lambda r: (r["sol"], r["instrument"], r["target"], r["file"]))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows(rows)

    counts = Counter(r["instrument"] for r in rows)
    sols = {k: len({r["sol"] for r in rows if r["instrument"] == k}) for k in counts}
    print(f"{len(rows)} rows in {out}")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]} rows · {sols[k]} sols")
    noted = update_manifest(Path(args.bundle), dict(counts), smin, smax)
    print("MANIFEST.json updated" if noted else "MANIFEST.json not found (run the build first)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
