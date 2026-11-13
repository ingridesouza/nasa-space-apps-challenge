#!/usr/bin/env python3
"""Monta o pacote offline da Feature 03 em bundle/.

Uso (a partir de h2g2-f03/):
    python etl/build.py                    # fonte do config.yaml
    python etl/build.py --source mock      # sem internet, dados de teste
    python etl/build.py --refresh-waypoints   # baixa o MMGIS do dia antes

Etapas: waypoints (tarefa 2) -> conferência MMGIS x PLACES (3) -> panoramas (5)
-> fotos estáticas (7) -> base orbital HiRISE (9) -> R-trees e MANIFEST (10).
Rodar de novo reaproveita imagens e respostas da API já baixadas.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import requests
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.geo import R_MARS, haversine  # noqa: E402
from etl.sources import make_sources  # noqa: E402

Image.MAX_IMAGE_PIXELS = None  # panoramas e o recorte HiRISE são grandes

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
# Etapas
# --------------------------------------------------------------------------- #


def build_waypoints(db, positions, cfg):
    s = cfg["sols"]
    stops = list(positions.list_stops(s["min"], s["max"]))
    db.executemany(
        "INSERT INTO waypoints VALUES (?,?,?,?,?,?,?,?,?)",
        [(p.rmc, p.site, p.drive, p.sol, p.lat, p.lon, p.elev, p.yaw, p.source) for p in stops],
    )
    log(f"[2] waypoints: {len(stops)} paradas nos sols {s['min']}–{s['max']}")
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
        log(f"   ! janela calculada difere do config.yaml em {diff:.6f}°: {win}")
    return win


def check_places(positions, stops, n=10):
    """Tarefa 3: cruza n paradas do MMGIS com o PLACES (planetocêntrica)."""
    if not hasattr(positions, "places") or not stops:
        return None
    step = max(1, len(stops) // n)
    pares = []
    for p in stops[::step][:n]:
        q = positions.places(p.site, p.drive)
        if q is None:
            continue
        pares.append({"rmc": p.rmc, "sol": p.sol, "dist_m": round(haversine(p.lat, p.lon, q.lat, q.lon), 4)})
    if not pares:
        return None
    res = {"pares": pares, "max_dist_m": max(x["dist_m"] for x in pares),
           "latitude": "planetocentric_latitude"}
    log(f"[3] MMGIS x PLACES: {len(pares)} paradas, maior diferença {res['max_dist_m']} m")
    return res


def prepare_pano_image(src: Path, dest: Path, max_w: int) -> tuple[int, int]:
    """Converte para JPEG (≤ max_w px de largura) e devolve (largura, altura)."""
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
            log(f"   ! panorama {pm.id}: parada {pm.site}_{pm.drive} sem posição; ignorado")
            n_skip += 1
            continue
        w = h = None
        img_rel = ""
        if pm.image and Path(pm.image).exists():
            img_rel = f"panos/pano_{pm.id}.jpg"
            w, h = prepare_pano_image(Path(pm.image), bundle / img_rel, cfg["pano_max_width"])
        vaov = round(360 * h / w, 3) if w else None
        # horizonte lido visualmente (fração da altura); acima do centro -> vOffset negativo
        voff = round(-(0.5 - hz[int(pm.sol)]) * vaov, 2) if vaov and int(pm.sol) in hz else 0.0
        db.execute(
            "INSERT OR REPLACE INTO panoramas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pm.id, pm.sol, pm.site, pm.drive, pos.lat, pos.lon, pm.center_az, 360.0, vaov, voff,
             img_rel, pm.page_url, pm.credit, f"{pos.source}_exato", pm.date, pos.yaw, w, h, "Navcam"),
        )
        n_ok += 1
    n_ok += build_color_panoramas(db, positions, cfg, bundle)
    log(f"[5] panoramas: {n_ok} gravados, {n_skip} sem posição")
    return n_ok


def build_color_panoramas(db, positions, cfg, bundle) -> int:
    """Panoramas Mastcam coloridos (config.yaml: color_panos). Entram como linha
    especial: posição da parada, haov 360, vaov pela proporção da imagem."""
    n = 0
    for c in cfg.get("color_panos") or []:
        src = (ROOT / c["image"]).resolve()
        pos = positions.locate(c["site"], c["drive"], c["sol"])
        if pos is None or not src.exists():
            log(f"   ! panorama colorido {c['id']}: parada {c['site']}_{c['drive']} ou imagem ausente; ignorado")
            continue
        img_rel = f"panos/{c['id']}.jpg"
        w, h = prepare_pano_image(src, bundle / img_rel, c.get("max_width", cfg["pano_max_width"]))
        vaov = round(360 * h / w, 3)
        voff = round(-(0.5 - c["horizon_frac"]) * vaov, 2) if "horizon_frac" in c else 0.0
        db.execute(
            "INSERT OR REPLACE INTO panoramas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{c['sol']}_{c['site']}_{c['drive']}_color", c["sol"], c["site"], c["drive"],
             pos.lat, pos.lon, c["center_az"], 360.0, vaov, voff, img_rel, c.get("page_url", ""),
             c["credit"], c.get("pos_quality", "estimada"), None, pos.yaw, w, h, c.get("camera", "Mastcam")),
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
        log(f"   ! falha ao baixar {url}: {e.__class__.__name__}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return True


def build_photos(db, photos_src, positions, stops, cfg, bundle):
    from api.geo import photo_azimuth

    s = cfg["sols"]
    session = requests.Session()
    session.headers["User-Agent"] = "H2G2-DETON8/1.0 (uso educacional)"
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
             ph.mast_az, ph.mast_el, img_rel, thumb_rel, ph.credit, f"{pos.source}_exato",
             ph.source, pos.yaw, photo_azimuth(ph.mast_az, pos.yaw)),
        )
        n += 1
    log(f"[7] fotos: {n} gravadas")
    return n


def build_rtrees(db):
    for table, tree in (("panoramas", "pano_rtree"), ("photos", "photo_rtree")):
        db.execute(f"DELETE FROM {tree}")
        db.execute(f"INSERT INTO {tree} SELECT rowid, lon, lon, lat, lat FROM {table}")


def build_orbital(cfg, bundle, win):
    """Tarefa 9: base HiRISE local. Converte o recorte boxwork.tif (M7) num JPEG
    com os limites em graus, para o Leaflet e para o recorte de 100 m."""
    tif = (ROOT / cfg["public"]["hirise_tif"]).resolve()
    if not tif.exists():
        log("[9] base orbital: boxwork.tif não encontrado; mapa sem imagem de fundo")
        return None
    try:
        import rasterio
    except ImportError:
        log("[9] base orbital: rasterio não instalado; mapa sem imagem de fundo")
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
    log(f"[9] base orbital: {bounds['width']}×{bounds['height']} px, {bounds['res_m']} m/px")
    return bounds


def write_track(db, bundle, win, orbital, cfg):
    stops = [dict(zip(("rmc", "sol", "lat", "lon"), r))
             for r in db.execute("SELECT rmc, sol, lat, lon FROM waypoints ORDER BY sol, site, drive")]
    with_pano = {r[0] for r in db.execute("SELECT site || '_' || drive FROM panoramas")}
    for s in stops:
        s["pano"] = s["rmc"] in with_pano
    examples = [{"nome": f"Parada {s['rmc']} (sol {s['sol']})", "lat": s["lat"], "lon": s["lon"]}
                for s in stops if s["rmc"] in ("118_2028", "120_538", "116_1596")]
    alvos = ROOT.parent / "dados" / "m7_alvos.csv"
    if alvos.exists():
        import csv
        with open(alvos, newline="", encoding="utf-8") as f:
            examples += [{"nome": r["nome"], "lat": float(r["lat"]), "lon": float(r["lon"])}
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
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "fonte": source,
        "janela_sols": cfg["sols"],
        "contagens": {"paradas": count("waypoints"), "panoramas": count("panoramas"),
                      "fotos": count("photos")},
        "tamanho_bytes": {d: size(d) for d in ("panos", "img", "thumbs", "tiles")},
        "conferencia_mmgis_places": places_check,
        "referencias": {
            "latitude": "planetocêntrica (M3)",
            "longitude": "leste positivo, 0–360",
            "raio_marte_m": cfg["mars_radius_m"],
            "mast_az": "a partir da frente do rover; azimute real = mast_az + yaw (M6)",
            "panorama_center_az": "azimute do centro da imagem, do texto da página NASA",
        },
        "fontes": [] if source != "public" else [
            {"nome": "Waypoints MMGIS do MSL", "url": pub["waypoints_url"],
             "arquivo": str(waypoints_file), "credito": "NASA/JPL-Caltech"},
            {"nome": "PLACES (localized_interp.csv)", "arquivo": pub["places_file"],
             "credito": "NASA/JPL-Caltech, PDS Imaging Node"},
            {"nome": "Panoramas Navcam (science.nasa.gov)", "arquivo": pub["panoramas_csv"],
             "credito": "NASA/JPL-Caltech"},
            {"nome": "Feed de imagens brutas do MSL", "url": pub["raw_images_api"],
             "credito": "NASA/JPL-Caltech"},
            {"nome": "Mosaico HiRISE colorido de Gale (USGS)", "url": pub["hirise_cog"],
             "credito": "NASA/JPL/University of Arizona/USGS"},
        ],
    }
    (bundle / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    db.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)",
                   [("fonte", source), ("gerado_em", manifest["gerado_em"])])
    return manifest


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="mock | public | official (padrão: config.yaml)")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--bundle", default=str(ROOT / "bundle"))
    ap.add_argument("--refresh-waypoints", action="store_true",
                    help="baixa o MSL_waypoints.json do dia antes de montar")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    source = args.source or cfg["source"]
    bundle = Path(args.bundle)
    bundle.mkdir(parents=True, exist_ok=True)

    waypoints_file = None
    if args.refresh_waypoints and source == "public":
        from etl.sources.public import refresh_waypoints
        waypoints_file = refresh_waypoints(cfg["public"]["waypoints_url"], (ROOT / "../dados").resolve())
        log(f"[2] MMGIS baixado: {waypoints_file}")

    positions, panos_src, photos_src = make_sources(source, cfg, ROOT, ROOT / ".cache", waypoints_file)
    log(f"Fonte: {source} · pacote em {bundle}")

    db_path = bundle / "h2g2.db"
    tmp_path = bundle / "h2g2.db.part"
    tmp_path.unlink(missing_ok=True)
    db = sqlite3.connect(tmp_path)
    db.executescript(SCHEMA)

    stops = build_waypoints(db, positions, cfg)
    win = compute_window(stops, cfg)
    places_check = check_places(positions, stops)
    build_panoramas(db, panos_src, positions, cfg, bundle)
    build_photos(db, photos_src, positions, stops, cfg, bundle)
    build_rtrees(db)
    orbital = build_orbital(cfg, bundle, win) if source != "mock" else None
    write_track(db, bundle, win, orbital, cfg)
    wp_file = waypoints_file or cfg["public"]["waypoints_file"]
    manifest = write_manifest(db, bundle, cfg, source, places_check, wp_file)
    db.commit()
    db.close()
    shutil.move(tmp_path, db_path)

    c = manifest["contagens"]
    log(f"Pronto: {c['paradas']} paradas, {c['panoramas']} panoramas, {c['fotos']} fotos · {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
