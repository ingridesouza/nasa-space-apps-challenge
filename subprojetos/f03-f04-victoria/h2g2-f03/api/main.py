"""API local da Feature 03. Lê bundle/h2g2.db em modo somente leitura.

Rodar (a partir de h2g2-f03/):
    uvicorn api.main:app --port 8000
e abrir http://localhost:8000/
"""

from __future__ import annotations

import io
import json
import sqlite3
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

from .geo import bbox, bearing, compass, haversine, yaw_inicial

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "bundle"
WEB = ROOT / "web"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
R_PANO = CFG["radius_m"]["panorama"]
R_PHOTO = CFG["radius_m"]["photos"]
PHOTO_LIMIT = CFG["photos"]["limit"]
CROP_M = CFG["orbital_crop_m"]
R_CARD = CFG["card_radius_m"]

Image.MAX_IMAGE_PIXELS = None
app = FastAPI(title="H2G2 · Feature 03 · Panorama no ponto")


@lru_cache(maxsize=1)
def db() -> sqlite3.Connection:
    path = BUNDLE / "h2g2.db"
    if not path.exists():
        raise HTTPException(503, "Pacote não encontrado: rode `python etl/build.py` primeiro.")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@lru_cache(maxsize=1)
def map_info() -> dict:
    p = BUNDLE / "map.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# --------------------------------------------------------------------------- #
# Utilidades de texto (regras de honestidade da interface)
# --------------------------------------------------------------------------- #


def fmt_dist(d: float) -> str:
    """Arredondada para 10 m, sempre com '~'."""
    return "a menos de 10 m" if d < 5 else f"a ~{int(round(d / 10.0) * 10)} m"


def fmt_date(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return ""
    y, m, d = iso[:10].split("-")
    return f" ({d}/{m}/{y})"


def norm_point(lat: float, lon: float) -> tuple[float, float, bool]:
    """Longitude negativa vira 0–360; diz se o ponto está dentro da janela."""
    lon = lon % 360
    w = map_info().get("window") or CFG["window"]
    inside = w["lat_min"] <= lat <= w["lat_max"] and w["lon_min"] <= lon <= w["lon_max"]
    return lat, lon, inside


def candidates(table: str, tree: str, lat: float, lon: float, radius: float):
    """R-tree pela caixa em graus, depois haversine exato e filtro d ≤ r."""
    lo0, lo1, la0, la1 = bbox(lat, lon, radius)
    rows = db().execute(
        f"SELECT t.* FROM {table} t JOIN {tree} r ON t.rowid = r.rid "
        "WHERE r.min_lon <= ? AND r.max_lon >= ? AND r.min_lat <= ? AND r.max_lat >= ?",
        (lo1, lo0, la1, la0),
    ).fetchall()
    out = []
    for r in rows:
        d = haversine(lat, lon, r["lat"], r["lon"])
        if d <= radius:
            out.append((d, r))
    # empate de distância (mesma parada): o colorido Mastcam vem primeiro
    out.sort(key=lambda x: (round(x[0], 3), "camera" in x[1].keys() and x[1]["camera"] != "Mastcam", x[1]["sol"]))
    return out


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@app.get("/health")
def health():
    meta = dict(db().execute("SELECT key, value FROM meta").fetchall())
    counts = {t: db().execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("waypoints", "panoramas", "photos", "targets", "measurements")}
    return {"status": "ok", "fonte": meta.get("fonte"), "snapshot": meta.get("gerado_em"),
            "contagens": counts, "raios_m": {"panorama": R_PANO, "fotos": R_PHOTO}}


@app.get("/map")
def get_map():
    return map_info()


@app.get("/panoramas/nearest")
def panorama_nearest(lat: float = Query(..., ge=-90, le=90), lon: float = Query(...),
                     radius: float = Query(R_PANO, gt=0, le=5000)):
    lat, lon, inside = norm_point(lat, lon)
    found = candidates("panoramas", "pano_rtree", lat, lon, radius)
    if not found:
        return {"found": False, "dentro_da_janela": inside,
                "mensagem": f"nenhum panorama a menos de {int(radius)} m"}
    d, p = found[0]
    rumo_ponto_parada = bearing(lat, lon, p["lat"], p["lon"])
    rumo_parada_ponto = bearing(p["lat"], p["lon"], lat, lon)
    yaw = 0.0 if d < 1 else yaw_inicial(rumo_parada_ponto, p["center_az"])
    cor = p["camera"] == "Mastcam"
    sufixo = "Mastcam · cor · posição estimada" if cor else "Navcam"
    rotulo = (f"panorama tirado {fmt_dist(d)} daqui, a {compass(rumo_ponto_parada)}"
              f" · sol {p['sol']}{fmt_date(p['date'])} · {sufixo}")
    return {
        "found": True, "dentro_da_janela": inside,
        "id": p["id"], "sol": p["sol"], "date": p["date"], "rmc": f"{p['site']}_{p['drive']}",
        "lat": p["lat"], "lon": p["lon"], "distancia_m": round(d, 1),
        "rumo_ponto_para_parada": round(rumo_ponto_parada, 1),
        "rumo_parada_para_ponto": round(rumo_parada_ponto, 1),
        "rotulo": rotulo, "credito": p["credit"], "page_url": p["page_url"],
        "pos_quality": p["pos_quality"],
        "pannellum": {"type": "equirectangular", "panorama": f"/bundle/{p['img_path']}",
                      "haov": p["haov"], "vaov": p["vaov"], "vOffset": p["voffset"],
                      "northOffset": p["center_az"], "yaw": round(yaw, 2), "pitch": 0,
                      "hfov": 90, "autoLoad": True, "compass": True},
    }


@app.get("/photos/near")
def photos_near(lat: float = Query(..., ge=-90, le=90), lon: float = Query(...),
                radius: float = Query(R_PHOTO, gt=0, le=5000),
                limit: int = Query(PHOTO_LIMIT, gt=0, le=100)):
    lat, lon, inside = norm_point(lat, lon)
    found = candidates("photos", "photo_rtree", lat, lon, radius)[:limit]
    fotos, paradas = [], {}
    for d, r in found:
        rmc = f"{r['site']}_{r['drive']}"
        rumo = bearing(lat, lon, r["lat"], r["lon"])
        olhando = f", olhando para {compass(r['true_az'])}" if r["true_az"] is not None else ""
        fotos.append({
            "id": r["id"], "rmc": rmc, "sol": r["sol"], "date_taken": r["date_taken"],
            "instrument": r["instrument"], "distancia_m": round(d, 1),
            "azimute_real": None if r["true_az"] is None else round(r["true_az"], 1),
            "mast_el": r["mast_el"], "img": f"/bundle/{r['img_path']}",
            "thumb": f"/bundle/{r['thumb_path']}", "credito": r["credit"],
            "rotulo": (f"foto tirada {fmt_dist(d)} daqui, a {compass(rumo)}{olhando}"
                       f" · sol {r['sol']}{fmt_date(r['date_taken'])} · Navcam"),
        })
        paradas.setdefault(rmc, []).append(r["id"])
    return {"dentro_da_janela": inside, "total": len(fotos), "fotos": fotos,
            "por_parada": [{"rmc": k, "fotos": v} for k, v in paradas.items()]}


@lru_cache(maxsize=1)
def orbital_source():
    """OrbitalMineralSource da F04; None enquanto a fonte configurada não existe."""
    from etl.sources import make_science_sources
    try:
        return make_science_sources(CFG["science_source"], CFG, ROOT)[1]
    except NotImplementedError:
        return None


CONFIANCA = {"medido": "medido", "mock": "exemplo (dado de teste)",
             "inferido de órbita": "inferido de órbita", "contexto": "contexto"}
GAZETTEER = "https://planetarynames.wr.usgs.gov/"
KIND_PT = {"furo": "furo de perfuração", "crista": "crista", "hollow": "hollow (depressão)",
           "contato": "contato geológico", "feição": "feição"}


def _linha(secao: str, texto: str, confianca: str, instrumento: str | None,
           fonte_url: str, fonte_arquivo: str = "") -> dict | None:
    """Regra de honestidade: linha sem fonte não existe."""
    if not texto or not (fonte_url or fonte_arquivo):
        return None
    return {"secao": secao, "texto": texto, "instrumento": instrumento,
            "confianca": confianca, "confianca_rotulo": CONFIANCA.get(confianca, confianca),
            "fonte_url": fonte_url, "fonte_arquivo": fonte_arquivo}


@app.get("/science/card")
def science_card(lat: float = Query(..., ge=-90, le=90), lon: float = Query(...),
                 radius: float = Query(R_CARD, gt=0, le=5000)):
    lat, lon, inside = norm_point(lat, lon)
    found = candidates("targets", "target_rtree", lat, lon, radius)
    out = {"dentro_da_janela": inside, "raio_m": radius, "alvo": None, "linhas": [],
           "contexto": [], "mastcam": None, "aviso_posicao": None, "mensagem": None}
    linhas = []

    if found:
        d, t = found[0]
        out["alvo"] = {
            "id": t["id"], "nome": t["name"], "rotulo_nome": "nome do alvo (equipe Curiosity)",
            "tipo": t["kind"], "tipo_rotulo": KIND_PT.get(t["kind"], t["kind"]),
            "sol": t["sol"], "rmc": None if t["site"] is None else f"{t['site']}_{t['drive']}",
            "lat": t["lat"], "lon": t["lon"], "distancia_m": round(d, 1),
            "distancia_rotulo": f"{fmt_dist(d)} daqui", "pos_quality": t["pos_quality"],
        }
        if t["pos_quality"] != "exata":
            out["aviso_posicao"] = f"posição aproximada pela parada do sol {t['sol']}"
        meds = db().execute("SELECT * FROM measurements WHERE target_id = ? ORDER BY instrument",
                            (t["id"],)).fetchall()
        for m in meds:
            sec = "mineralogia" if m["instrument"] == "CheMin" else "quimica"
            linhas.append(_linha(sec, m["summary"], m["confidence"], m["instrument"],
                                 m["source_url"], m["source_file"]))
        if not meds:
            linhas.append(_linha("sem_medicao", "sem medição publicada para este alvo",
                                 "contexto", None, t["blog_url"]))
        for sec, txt in (("por_que_importa", t["why_it_matters"]), ("seguranca", t["safety_note"])):
            out["contexto"].append(_linha(sec, txt, "contexto", None, t["blog_url"]))
        if t["terrain_class"]:
            linhas.append(_linha("terreno", t["terrain_class"], "contexto", "classificação da equipe H2G2",
                                 t["blog_url"]))
        if t["mastcam_path"]:
            out["mastcam"] = {"img": t["mastcam_path"], "credito": t["mastcam_credit"],
                              "rotulo": f"foto Mastcam do sol {t['sol']}"}
    else:
        out["mensagem"] = f"nenhum alvo estudado a menos de {int(radius)} m"

    orb = orbital_source().sample(lat, lon) if inside and orbital_source() else None
    if orb:
        linhas.append(_linha("orbita", f"{orb.label} ({orb.note})", orb.confidence,
                             "CRISM", orb.source_url))
    if inside:
        linhas.append(_linha("nome", "Cratera Gale · Monte Sharp (Aeolis Mons)", "contexto", None,
                             GAZETTEER))
    elif out["mensagem"]:
        out["mensagem"] += " e o ponto está fora da janela do boxwork"
    out["linhas"] = [l for l in linhas if l]
    out["contexto"] = [l for l in out["contexto"] if l]
    out["fontes"] = [{"secao": l["secao"], "url": l["fonte_url"], "arquivo": l["fonte_arquivo"]}
                     for l in out["linhas"] + out["contexto"]]
    return out


@lru_cache(maxsize=1)
def _orbital_image():
    o = map_info().get("orbital")
    if not o:
        return None, None
    return Image.open(BUNDLE / o["image"]).convert("RGB"), o


@app.get("/orbital/crop")
def orbital_crop(lat: float = Query(..., ge=-90, le=90), lon: float = Query(...)):
    lat, lon, _ = norm_point(lat, lon)
    im, o = _orbital_image()
    if im is None:
        raise HTTPException(404, "Base orbital não incluída no pacote.")
    x = (lon - o["lon_min"]) / (o["lon_max"] - o["lon_min"]) * im.width
    y = (o["lat_max"] - lat) / (o["lat_max"] - o["lat_min"]) * im.height
    if not (0 <= x < im.width and 0 <= y < im.height):
        raise HTTPException(404, "Ponto fora do recorte HiRISE.")
    half = CROP_M / o["res_m"] / 2
    crop = im.crop((int(x - half), int(y - half), int(x + half), int(y + half)))
    dr = ImageDraw.Draw(crop)
    c = crop.width / 2
    for a, b in (((c - 12, c), (c - 4, c)), ((c + 4, c), (c + 12, c)),
                 ((c, c - 12), (c, c - 4)), ((c, c + 4), (c, c + 12))):
        dr.line((a, b), fill=(255, 230, 0), width=2)
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"X-Credito": "NASA/JPL/University of Arizona/USGS",
                             "X-Lado-m": str(CROP_M)})


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/bundle", StaticFiles(directory=BUNDLE, check_dir=False), name="bundle")
app.mount("/web", StaticFiles(directory=WEB), name="web")
