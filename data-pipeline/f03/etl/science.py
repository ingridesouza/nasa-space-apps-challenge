"""F04: writes `targets`, `measurements` and `target_rtree` into h2g2.sqlite.

This step only writes what the ScienceSource returns (mock or public) and copies
into the bundle the local files the card uses: Mastcam photos, CRISM crop and
`terrain.geojson` (M6), when they exist.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA_SCIENCE = """
CREATE TABLE targets(id TEXT PRIMARY KEY, name TEXT, kind TEXT, sol INT,
  site INT, drive INT, lat REAL, lon REAL, pos_quality TEXT,
  why_it_matters TEXT, safety_note TEXT, blog_url TEXT,
  mastcam_path TEXT, mastcam_credit TEXT, terrain_class TEXT,
  what_was_done TEXT, what_was_done_url TEXT);
CREATE TABLE measurements(id TEXT PRIMARY KEY, target_id TEXT, instrument TEXT,
  sol INT, site INT, drive INT, summary TEXT, values_json TEXT,
  confidence TEXT, source_url TEXT, source_file TEXT);
CREATE VIRTUAL TABLE target_rtree USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
"""


def publish(src: Path, dst: Path, schema: str) -> None:
    """Swaps, in a single transaction, the F03/F04 tables of the single database `dst`
    for the ones built in `src`. The other tables of the database (the team's) stay intact."""
    tables = re.findall(r"CREATE (?:VIRTUAL )?TABLE (\w+)", schema)
    dst.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(dst)
    con.execute("ATTACH DATABASE ? AS f", (str(src),))
    con.executescript(
        "BEGIN;\n"
        + "".join(f"DROP TABLE IF EXISTS main.{t};\n" for t in tables)
        + schema
        + "".join(f"INSERT INTO main.{t} SELECT * FROM f.{t};\n" for t in tables)
        + "COMMIT;"
    )
    con.execute("DETACH DATABASE f")
    con.close()


def build_science(db, science, stops, cfg) -> tuple[int, int]:
    targets = list(science.list_targets(stops))
    for t in targets:
        d = asdict(t)
        db.execute(f"INSERT INTO targets ({','.join(d)}) VALUES ({','.join('?' * len(d))})",
                   list(d.values()))
    ids = {t.id for t in targets}
    n_meas = 0
    for m in science.list_measurements(cfg["sols"]["min"], cfg["sols"]["max"]):
        if m.target_id not in ids:
            continue
        d = asdict(m)
        db.execute(f"INSERT INTO measurements ({','.join(d)}) VALUES ({','.join('?' * len(d))})",
                   list(d.values()))
        n_meas += 1
    db.execute("DELETE FROM target_rtree")
    db.execute("INSERT INTO target_rtree SELECT rowid, lon, lon, lat, lat FROM targets")
    return len(targets), n_meas


def copy_science_files(cfg, base_dir: Path, bundle: Path) -> list[str]:
    """Copies into the bundle what the API serves: Mastcam, CRISM, terrain."""
    sc, copied = cfg["science"], []
    mast = (base_dir / sc["mastcam_dir"]).resolve()
    if mast.exists():
        (bundle / "mastcam").mkdir(parents=True, exist_ok=True)
        for f in mast.glob("*.jpg"):
            shutil.copy2(f, bundle / "mastcam" / f.name)
            copied.append(f"mastcam/{f.name}")
    for src, name in ((cfg.get("crism", {}).get("crop_json"), "crism_boxwork.json"),
                      (sc.get("terrain_geojson"), "terrain.geojson")):
        p = (base_dir / src).resolve() if src else None
        if p and p.exists():
            shutil.copy2(p, bundle / name)
            copied.append(name)
        else:
            (bundle / name).unlink(missing_ok=True)
    return copied


def main() -> int:
    """Rebuilds only the F04 tables in the single database (without running the whole ETL)."""
    from etl.sources import make_science_sources
    from etl.sources.base import Position

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--bundle", help="default: paths.bundle from config.yaml")
    ap.add_argument("--db", help="default: paths.db from config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    args.bundle = args.bundle or str((ROOT / cfg["paths"]["bundle"]).resolve())
    db = sqlite3.connect(args.db or (ROOT / cfg["paths"]["db"]).resolve())
    for t in ("target_rtree", "measurements", "targets"):
        db.execute(f"DROP TABLE IF EXISTS {t}")
    db.executescript(SCHEMA_SCIENCE)
    stops = [Position(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in db.execute(
        "SELECT rmc, site, drive, sol, lat, lon, elev, yaw, source FROM waypoints")]
    science, _ = make_science_sources(cfg["science_source"], cfg, ROOT)
    n_t, n_m = build_science(db, science, stops, cfg)
    copy_science_files(cfg, ROOT, Path(args.bundle))
    db.commit()
    db.close()
    print(f"F04: {n_t} targets, {n_m} measurements (science_source: {cfg['science_source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
