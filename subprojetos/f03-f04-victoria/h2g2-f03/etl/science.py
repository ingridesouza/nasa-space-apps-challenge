"""F04: grava `targets`, `measurements` e `target_rtree` no h2g2.db.

Hoje (tarefa 1) os dados vêm do MockScience. As tarefas 3 e 4 trocam a fonte
(public) sem mexer aqui: esta etapa só grava o que a ScienceSource devolve.
"""

from __future__ import annotations

import argparse
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
  mastcam_path TEXT, mastcam_credit TEXT, terrain_class TEXT);
CREATE TABLE measurements(id TEXT PRIMARY KEY, target_id TEXT, instrument TEXT,
  sol INT, site INT, drive INT, summary TEXT, values_json TEXT,
  confidence TEXT, source_url TEXT, source_file TEXT);
CREATE VIRTUAL TABLE target_rtree USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
"""


def build_science(db, science, stops, cfg) -> tuple[int, int]:
    targets = list(science.list_targets(stops))
    for t in targets:
        d = asdict(t)
        db.execute(f"INSERT INTO targets ({','.join(d)}) VALUES ({','.join('?' * len(d))})",
                   list(d.values()))
    ids = {t.id for t in targets}
    n_med = 0
    for m in science.list_measurements(cfg["sols"]["min"], cfg["sols"]["max"]):
        if m.target_id not in ids:
            continue
        d = asdict(m)
        db.execute(f"INSERT INTO measurements ({','.join(d)}) VALUES ({','.join('?' * len(d))})",
                   list(d.values()))
        n_med += 1
    db.execute("DELETE FROM target_rtree")
    db.execute("INSERT INTO target_rtree SELECT rowid, lon, lon, lat, lat FROM targets")
    return len(targets), n_med


def main() -> int:
    """Refaz só as tabelas da F04 num h2g2.db existente (sem rodar o ETL todo)."""
    from etl.sources import make_science_sources
    from etl.sources.base import Position

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--bundle", default=str(ROOT / "bundle"))
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db = sqlite3.connect(Path(args.bundle) / "h2g2.db")
    for t in ("target_rtree", "measurements", "targets"):
        db.execute(f"DROP TABLE IF EXISTS {t}")
    db.executescript(SCHEMA_SCIENCE)
    stops = [Position(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in db.execute(
        "SELECT rmc, site, drive, sol, lat, lon, elev, yaw, source FROM waypoints")]
    science, _ = make_science_sources(cfg["science_source"], cfg, ROOT)
    n_t, n_m = build_science(db, science, stops, cfg)
    db.commit()
    db.close()
    print(f"F04: {n_t} alvos, {n_m} medições (science_source: {cfg['science_source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
