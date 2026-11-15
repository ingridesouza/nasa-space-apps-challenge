#!/usr/bin/env python3
"""Builds the offline F03/F04 bundle: tables in the project's single SQLite
(data/local/h2g2.sqlite) and files in data/local/f03/ (served at /bundle).

Usage (from data-pipeline/f03/):
    python etl/build.py                    # source from config.yaml
    python etl/build.py --source mock      # no internet, test data
    python etl/build.py --refresh-waypoints   # downloads today's MMGIS first

Steps: waypoints (task 2) -> MMGIS x PLACES check (3) -> panoramas (5)
-> static photos (7) -> HiRISE orbital base (9) -> R-trees and MANIFEST (10).
Running again reuses images and API responses already downloaded.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

import requests
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT.parent.parent / "api"))  # geo.py: the only haversine/bearing implementation

from geo import R_MARS, haversine, photo_azimuth  # noqa: E402
from etl.science import SCHEMA_SCIENCE, build_science, copy_science_files, publish  # noqa: E402
from etl.sources import make_science_sources, make_sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None  # panoramas and the HiRISE crop are large

SCHEMA = """
CREATE TABLE waypoints(rmc TEXT PRIMARY KEY, site INT, drive INT, sol INT,
  lat REAL, lon REAL, elev REAL, yaw REAL, source TEXT);
CREATE TABLE panoramas(id TEXT PRIMARY KEY, sol INT, site INT, drive INT,
  lat REAL, lon REAL, center_az REAL, haov REAL, vaov REAL, voffset REAL,
  img_path TEXT, page_url TEXT, credit TEXT, pos_quality TEXT,
  date TEXT, rover_yaw REAL, width INT, height INT, camera TEXT);
CREATE TABLE photos(id TEXT PRIMARY KEY, instrument TEXT, sol INT, site INT, drive INT,
  date_taken TEXT, lat REAL, lon REAL, mast_az REAL, mast_el REAL,
  img_path TEXT, thumb_path TEXT, credit TEXT, pos_quality TEXT, source TEXT,
  rover_yaw REAL, true_az REAL);
CREATE VIRTUAL TABLE pano_rtree  USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
CREATE VIRTUAL TABLE photo_rtree USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
"""


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


def build_waypoints(db, positions, cfg):
    s = cfg["sols"]
    stops = list(positions.list_stops(s["min"], s["max"]))
    db.executemany(
        "INSERT INTO waypoints VALUES (?,?,?,?,?,?,?,?,?)",
        [(p.rmc, p.site, p.drive, p.sol, p.lat, p.lon, p.elev, p.yaw, p.source) for p in stops],
    )
    log(f"[2] waypoints: {len(stops)} stops in sols {s['min']}–{s['max']}")
    return stops


def compute_window(stops, cfg):
    m = cfg["window"]["margin_deg"]
    if not stops:
        return dict(cfg["window"])
    win = {
        "lon_min": round(min(p.lon for p in stops) - m, 6),
        "lon_max": round(max(p.lon for p in stops) + m, 6),
        "lat_min": round(min(p.lat for p in stops) - m, 6),
        "lat_max": round(max(p.lat for p in stops) + m, 6),
    }
    conf = cfg["window"]
    diff = max(abs(win[k] - conf[k]) for k in win)
    if diff > 1e-5:
        log(f"   ! computed window differs from config.yaml by {diff:.6f}°: {win}")
    return win


def check_places(positions, stops, n=10):
    """Task 3: crosses n MMGIS stops with PLACES (planetocentric)."""
    if not hasattr(positions, "places") or not stops:
        return None
    step = max(1, len(stops) // n)
    pairs = []
    for p in stops[::step][:n]:
        q = positions.places(p.site, p.drive)
        if q is None:
            continue
        pairs.append({"rmc": p.rmc, "sol": p.sol, "dist_m": round(haversine(p.lat, p.lon, q.lat, q.lon), 4)})
    if not pairs:
        return None
    res = {"pairs": pairs, "max_dist_m": max(x["dist_m"] for x in pairs),
           "latitude": "planetocentric_latitude"}
    log(f"[3] MMGIS x PLACES: {len(pairs)} stops, largest difference {res['max_dist_m']} m")
    return res


def prepare_pano_image(src: Path, dest: Path, max_w: int) -> tuple[int, int]:
    """Converts to JPEG (≤ max_w px wide) and returns (width, height)."""
    if dest.exists():
        with Image.open(dest) as im:
            return im.size
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        im.save(tmp, "JPEG", quality=85, optimize=True, progressive=True)
        tmp.replace(dest)
        return im.size


def build_panoramas(db, panos_src, positions, cfg, bundle):
    s = cfg["sols"]
    n_ok = n_skip = 0
    hz = {}
    hz_file = Path(__file__).with_name("horizons.csv")
    if hz_file.exists():
        for ln in hz_file.read_text().splitlines()[1:]:
            if ln.strip():
                a, b = ln.split(",")
                hz[int(a)] = float(b)
    for pm in panos_src.list_panoramas(s["min"], s["max"]):
        pos = positions.locate(pm.site, pm.drive, pm.sol)
        if pos is None:
            log(f"   ! panorama {pm.id}: stop {pm.site}_{pm.drive} without position; ignored")
            n_skip += 1
            continue
        w = h = None
        img_rel = ""
        if pm.image and Path(pm.image).exists():
            img_rel = f"panos/pano_{pm.id}.jpg"
            w, h = prepare_pano_image(Path(pm.image), bundle / img_rel, cfg["pano_max_width"])
        vaov = round(360 * h / w, 3) if w else None
        # horizon read visually (fraction of the height); above the center -> negative vOffset
        voff = round(-(0.5 - hz[int(pm.sol)]) * vaov, 2) if vaov and int(pm.sol) in hz else 0.0
        db.execute(
            "INSERT OR REPLACE INTO panoramas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pm.id, pm.sol, pm.site, pm.drive, pos.lat, pos.lon, pm.center_az, 360.0, vaov, voff,
             img_rel, pm.page_url, pm.credit, f"{pos.source}_exact", pm.date, pos.yaw, w, h, "Navcam"),
        )
        n_ok += 1
    n_ok += build_color_panoramas(db, positions, cfg, bundle)
    log(f"[5] panoramas: {n_ok} written, {n_skip} without position")
    return n_ok


def build_color_panoramas(db, positions, cfg, bundle) -> int:
    """Mastcam color panoramas (config.yaml: color_panos). They go in as a special
    row: stop position, haov 360, vaov from the image aspect ratio."""
    n = 0
    for c in cfg.get("color_panos") or []:
        src = (ROOT / c["image"]).resolve()
        pos = positions.locate(c["site"], c["drive"], c["sol"])
        if pos is None or not src.exists():
            log(f"   ! color panorama {c['id']}: stop {c['site']}_{c['drive']} or image missing; ignored")
            continue
        img_rel = f"panos/{c['id']}.jpg"
        w, h = prepare_pano_image(src, bundle / img_rel, c.get("max_width", cfg["pano_max_width"]))
        vaov = round(360 * h / w, 3)
        voff = round(-(0.5 - c["horizon_frac"]) * vaov, 2) if "horizon_frac" in c else 0.0
        db.execute(
            "INSERT OR REPLACE INTO panoramas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{c['sol']}_{c['site']}_{c['drive']}_color", c["sol"], c["site"], c["drive"],
             pos.lat, pos.lon, c["center_az"], 360.0, vaov, voff, img_rel, c.get("page_url", ""),
             c["credit"], c.get("pos_quality", "estimated"), None, pos.yaw, w, h, c.get("camera", "Mastcam")),
        )
        n += 1
    return n


def download(session, url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"   ! failed to download {url}: {e.__class__.__name__}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return True


def build_photos(db, photos_src, positions, stops, cfg, bundle):
    s = cfg["sols"]
    session = requests.Session()
    session.headers["User-Agent"] = "H2G2-DETON8/1.0 (educational use)"
    n = 0
    for ph in photos_src.list_photos(s["min"], s["max"], stops):
        pos = positions.locate(ph.site, ph.drive, ph.sol)
        if pos is None:
            continue
        img_rel = thumb_rel = ""
        if ph.image:
            img_rel, thumb_rel = f"img/{ph.id}.jpg", f"thumbs/{ph.id}.jpg"
            if not download(session, ph.image, bundle / img_rel):
                continue
            if not (bundle / thumb_rel).exists():
                with Image.open(bundle / img_rel) as im:
                    im = im.convert("RGB")
                    im.thumbnail((320, 320))
                    (bundle / thumb_rel).parent.mkdir(parents=True, exist_ok=True)
                    im.save(bundle / thumb_rel, "JPEG", quality=80)
        db.execute(
            "INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ph.id, ph.instrument, ph.sol, ph.site, ph.drive, ph.date_taken, pos.lat, pos.lon,
             ph.mast_az, ph.mast_el, img_rel, thumb_rel, ph.credit, f"{pos.source}_exact",
             ph.source, pos.yaw, photo_azimuth(ph.mast_az, pos.yaw)),
        )
        n += 1
    log(f"[7] photos: {n} written")
    return n


def localize_mastcam(db, bundle) -> int:
    """Downloads each target's Mastcam into the bundle; the API never serves an external URL."""
    session = requests.Session()
    session.headers["User-Agent"] = "H2G2-DETON8/1.0 (educational use)"
    n = 0
    for tid, url in db.execute("SELECT id, mastcam_path FROM targets WHERE mastcam_path LIKE 'http%'").fetchall():
        rel = f"mastcam/{tid}.jpg"
        db.execute("UPDATE targets SET mastcam_path = ? WHERE id = ?",
                   (rel if download(session, url, bundle / rel) else "", tid))
        n += (bundle / rel).exists()
    return n


def build_rtrees(db):
    for table, tree in (("panoramas", "pano_rtree"), ("photos", "photo_rtree")):
        db.execute(f"DELETE FROM {tree}")
        db.execute(f"INSERT INTO {tree} SELECT rowid, lon, lon, lat, lat FROM {table}")


def build_orbital(cfg, bundle, win):
    """Task 9: local HiRISE base. Converts the boxwork.tif crop (M7) into a JPEG
    with the bounds in degrees, for the map and for the 100 m crop."""
    tif = (ROOT / cfg["public"]["hirise_tif"]).resolve()
    if not tif.exists():
        log("[9] orbital base: boxwork.tif not found; map without background image")
        return None
    try:
        import rasterio
    except ImportError:
        log("[9] orbital base: rasterio not installed; map without background image")
        return None

    with rasterio.open(tif) as src:
        d2m = R_MARS * 3.141592653589793 / 180
        b = src.bounds
        bounds = {"lon_min": b.left / d2m, "lon_max": b.right / d2m,
                  "lat_min": b.bottom / d2m, "lat_max": b.top / d2m,
                  "res_m": src.res[0], "width": src.width, "height": src.height}
        dest = bundle / "tiles" / "boxwork.jpg"
        if not dest.exists():
            data = src.read([1, 2, 3])
            dest.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(data.transpose(1, 2, 0)).save(dest, "JPEG", quality=90)
    bounds["image"] = "tiles/boxwork.jpg"
    log(f"[9] orbital base: {bounds['width']}×{bounds['height']} px, {bounds['res_m']} m/px")
    return bounds


def write_track(db, bundle, win, orbital, cfg):
    stops = [dict(zip(("rmc", "sol", "lat", "lon"), r))
             for r in db.execute("SELECT rmc, sol, lat, lon FROM waypoints ORDER BY sol, site, drive")]
    with_pano = {r[0] for r in db.execute("SELECT site || '_' || drive FROM panoramas")}
    for s in stops:
        s["pano"] = s["rmc"] in with_pano
    examples = [{"name": f"Stop {s['rmc']} (sol {s['sol']})", "lat": s["lat"], "lon": s["lon"]}
                for s in stops if s["rmc"] in ("118_2028", "120_538", "116_1596")]
    targets = ROOT / "data" / "m7_targets.csv"
    if targets.exists():
        import csv
        with open(targets, newline="", encoding="utf-8") as f:
            examples += [{"name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
                         for r in csv.DictReader(f)]
    (bundle / "map.json").write_text(json.dumps({
        "window": win, "orbital": orbital, "stops": stops, "examples": examples,
        "radius_m": cfg["radius_m"],
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def write_manifest(db, bundle, cfg, source, places_check, waypoints_file):
    def count(t):
        return db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    def size(d):
        p = bundle / d
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

    pub = cfg["public"]
    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "sol_window": cfg["sols"],
        "counts": {"stops": count("waypoints"), "panoramas": count("panoramas"),
                   "photos": count("photos")},
        "size_bytes": {d: size(d) for d in ("panos", "img", "thumbs", "tiles")},
        "mmgis_places_check": places_check,
        "references": {
            "latitude": "planetocentric (M3)",
            "longitude": "east positive, 0–360",
            "mars_radius_m": cfg["mars_radius_m"],
            "mast_az": "from the rover's front; true azimuth = mast_az + yaw (M6)",
            "panorama_center_az": "azimuth of the image center, from the NASA page text",
        },
        "sources": [] if source != "public" else [
            {"name": "MSL MMGIS waypoints", "url": pub["waypoints_url"],
             "file": str(waypoints_file), "credit": "NASA/JPL-Caltech"},
            {"name": "PLACES (localized_interp.csv)", "file": pub["places_file"],
             "credit": "NASA/JPL-Caltech, PDS Imaging Node"},
            {"name": "Navcam panoramas (science.nasa.gov)", "file": pub["panoramas_csv"],
             "credit": "NASA/JPL-Caltech"},
            {"name": "MSL raw images feed", "url": pub["raw_images_api"],
             "credit": "NASA/JPL-Caltech"},
            {"name": "Gale HiRISE color mosaic (USGS)", "url": pub["hirise_cog"],
             "credit": "NASA/JPL/University of Arizona/USGS"},
        ],
    }
    old = bundle / "MANIFEST.json"
    if old.exists():  # keeps the PDS inventory (etl/science_index.py)
        prev = json.loads(old.read_text(encoding="utf-8"))
        if "pds_inventory" in prev:
            manifest["pds_inventory"] = prev["pds_inventory"]
    manifest["counts"].update({"targets": count("targets"), "measurements": count("measurements")})
    manifest["science_source"] = cfg["science_source"]
    if cfg["science_source"] == "public":
        sc, cr = cfg["science"], cfg["crism"]
        manifest["f04_sources"] = [
            {"name": "Curated targets (M8)", "file": sc["targets_csv"], "credit": "Curiosity blog, NASA"},
            {"name": "PDS inventory (task 2)", "file": sc["index_csv"], "credit": "PDS Geosciences"},
            {"name": "APXS RDR (RWP)", "file": f"{sc['pds_dir']}/apxs/",
             "url": "https://pds-geosciences.wustl.edu/missions/msl/apxs.htm",
             "credit": "PDS Geosciences / Canadian Space Agency"},
            {"name": "ChemCam LIBS RDR (MOC)", "file": f"{sc['pds_dir']}/chemcam/",
             "url": "https://pds-geosciences.wustl.edu/missions/msl/chemcam.htm",
             "credit": "PDS Geosciences / LANL / CNES"},
            {"name": "CheMin RDR (mineral abundance)", "file": f"{sc['pds_dir']}/chemin/",
             "url": "https://pds-geosciences.wustl.edu/missions/msl/chemin.htm",
             "credit": "PDS Geosciences / NASA Ames"},
            {"name": f"CRISM MTRDR {cr['product']} (SU parameters)", "file": cr["crop_json"],
             "url": cr["page_url"], "credit": "NASA/JPL/JHUAPL, PDS Geosciences"},
            {"name": "Mastcam photos of the targets", "file": sc["mastcam_dir"], "credit": "NASA/JPL-Caltech/MSSS"},
            {"name": "Terrain polygons (M6)", "file": sc["terrain_geojson"],
             "credit": "H2G2 team", "present": (bundle / "terrain.geojson").exists()},
        ]
    old.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    db.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)",
                   [("source", source), ("generated_at", manifest["generated_at"])])
    return manifest


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="mock | public | official (default: config.yaml)")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--bundle", help="folder of the files served at /bundle (default: config.yaml)")
    ap.add_argument("--db", help="the project's single SQLite (default: config.yaml)")
    ap.add_argument("--refresh-waypoints", action="store_true",
                    help="downloads today's MSL_waypoints.json before building")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    source = args.source or cfg["source"]
    bundle = Path(args.bundle) if args.bundle else (ROOT / cfg["paths"]["bundle"]).resolve()
    bundle.mkdir(parents=True, exist_ok=True)

    waypoints_file = None
    if args.refresh_waypoints and source == "public":
        from etl.sources.public import refresh_waypoints
        waypoints_file = refresh_waypoints(cfg["public"]["waypoints_url"], ROOT / "data")
        log(f"[2] MMGIS downloaded: {waypoints_file}")

    cache = (ROOT / cfg["paths"]["cache"]).resolve()
    positions, panos_src, photos_src = make_sources(source, cfg, ROOT, cache, waypoints_file)
    log(f"Source: {source} · bundle at {bundle}")

    # Builds into a separate file and only at the end swaps the tables in the single database:
    # a build that fails midway does not leave the team's database half-done.
    db_path = Path(args.db) if args.db else (ROOT / cfg["paths"]["db"]).resolve()
    tmp_path = bundle / "f03.db.part"
    tmp_path.unlink(missing_ok=True)
    db = sqlite3.connect(tmp_path)
    db.executescript(SCHEMA + SCHEMA_SCIENCE)

    stops = build_waypoints(db, positions, cfg)
    win = compute_window(stops, cfg)
    places_check = check_places(positions, stops)
    build_panoramas(db, panos_src, positions, cfg, bundle)
    build_photos(db, photos_src, positions, stops, cfg, bundle)
    build_rtrees(db)
    n_targets, n_meas = build_science(db, make_science_sources(cfg["science_source"], cfg, ROOT)[0],
                                   stops, cfg)
    log(f"F04: {n_targets} targets, {n_meas} measurements (science_source: {cfg['science_source']})")
    log(f"F04: files in the bundle: {len(copy_science_files(cfg, ROOT, bundle))}")
    orbital = build_orbital(cfg, bundle, win) if source != "mock" else None
    write_track(db, bundle, win, orbital, cfg)
    wp_file = waypoints_file or cfg["public"]["waypoints_file"]
    manifest = write_manifest(db, bundle, cfg, source, places_check, wp_file)
    db.commit()
    db.close()
    publish(tmp_path, db_path, SCHEMA + SCHEMA_SCIENCE)
    tmp_path.unlink()

    c = manifest["counts"]
    log(f"Done: {c['stops']} stops, {c['panoramas']} panoramas, {c['photos']} photos · {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
