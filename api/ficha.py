"""F04 · ficha científica do ponto (GET /science/card).

Lê `targets` e `measurements` do banco único e o recorte CRISM de
data/local/f03/, gerados por data-pipeline/f03/etl/build.py.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache

from fastapi import APIRouter, Query

from panorama import BUNDLE, CFG, F03_PIPELINE, R_CARD, candidates, db, fmt_dist, norm_point

sys.path.append(str(F03_PIPELINE))  # etl.sources: amostragem CRISM, mesma regra do ETL

router = APIRouter()


@lru_cache(maxsize=1)
def orbital_source():
    """OrbitalMineralSource da F04, lida do pacote; None se a fonte não existe."""
    if CFG["science_source"] == "public":
        from etl.sources.science_public import PublicOrbital
        return PublicOrbital(BUNDLE / "crism_boxwork.json")
    from etl.sources import make_science_sources
    try:
        return make_science_sources(CFG["science_source"], CFG, F03_PIPELINE)[1]
    except NotImplementedError:
        return None


@lru_cache(maxsize=1)
def terrain_polygons() -> list[tuple[list, dict]]:
    """Polígonos da M6 (terrain.geojson no pacote): [(anéis, propriedades)]."""
    p = BUNDLE / "terrain.geojson"
    if not p.exists():
        return []
    out = []
    for f in json.loads(p.read_text(encoding="utf-8")).get("features", []):
        g = f.get("geometry") or {}
        polys = [g["coordinates"]] if g.get("type") == "Polygon" else (
            g["coordinates"] if g.get("type") == "MultiPolygon" else [])
        out += [(rings, f.get("properties") or {}) for rings in polys]
    return out


def _in_ring(lon: float, lat: float, ring: list) -> bool:
    dentro = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def terrain_at(lat: float, lon: float) -> dict | None:
    """Ponto-no-polígono (anel externo menos buracos); longitude aceita −180–180 ou 0–360."""
    for rings, props in terrain_polygons():
        for x in (lon, lon - 360):
            if _in_ring(x, lat, [c[:2] for c in rings[0]]) and not any(
                    _in_ring(x, lat, [c[:2] for c in h]) for h in rings[1:]):
                return props
    return None


CONFIANCA = {"medido": "medido", "mock": "exemplo (dado de teste)",
             "inferido de órbita": "inferido de órbita", "contexto": "contexto"}
GAZETTEER = "https://planetarynames.wr.usgs.gov/"
KIND_PT = {"furo": "furo de perfuração", "crista": "crista", "hollow": "hollow (depressão)",
           "contato": "contato geológico", "feição": "feição"}


ESCALA = {"APXS": "medido nesta parada", "CheMin": "medido nesta parada",
          "ChemCam": "medido a até ~7 m desta parada"}


def _linha(secao: str, texto: str, confianca: str, instrumento: str | None,
           fonte_url: str, fonte_arquivo: str = "", **extra) -> dict | None:
    """Regra de honestidade: linha sem fonte não existe."""
    if not texto or not (fonte_url or fonte_arquivo):
        return None
    return {"secao": secao, "texto": texto, "instrumento": instrumento,
            "confianca": confianca, "confianca_rotulo": CONFIANCA.get(confianca, confianca),
            "fonte_url": fonte_url, "fonte_arquivo": fonte_arquivo, **extra}


@router.get("/science/card")
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
            "distancia_rotulo": f"{fmt_dist(d)} do ponto consultado", "pos_quality": t["pos_quality"],
        }
        if t["pos_quality"] != "exata":
            out["aviso_posicao"] = f"posição aproximada pela parada do sol {t['sol']}"
        meds = db().execute("SELECT * FROM measurements WHERE target_id = ? ORDER BY instrument",
                            (t["id"],)).fetchall()
        for m in meds:
            sec = "mineralogia" if m["instrument"] == "CheMin" else "quimica"
            linhas.append(_linha(sec, m["summary"], m["confidence"], m["instrument"],
                                 m["source_url"], m["source_file"], sol=m["sol"],
                                 escala=ESCALA.get(m["instrument"])))
        if not meds:
            linhas.append(_linha("sem_medicao", "sem medição publicada para este alvo",
                                 "contexto", None, t["blog_url"]))
        out["contexto"].append(_linha("o_que_foi_feito", t["what_was_done"], "contexto",
                                      "blog do Curiosity", t["what_was_done_url"]))
        for sec, txt in (("por_que_importa", t["why_it_matters"]), ("seguranca", t["safety_note"])):
            out["contexto"].append(_linha(sec, txt, "contexto", None, t["blog_url"]))
        if t["terrain_class"]:
            linhas.append(_linha("terreno", t["terrain_class"], "contexto", "classificação da equipe H2G2",
                                 t["blog_url"]))
        # só arquivo local (sistema offline): URL externa nunca vai para o card
        if t["mastcam_path"] and not t["mastcam_path"].startswith("http"):
            out["mastcam"] = {"img": f"/bundle/mastcam/{t['mastcam_path']}",
                              "credito": t["mastcam_credit"],
                              "rotulo": f"foto Mastcam do sol {t['sol']}"}
    else:
        out["mensagem"] = f"nenhum alvo estudado a menos de {int(radius)} m"

    orb = orbital_source().sample(lat, lon) if inside and orbital_source() else None
    if orb:
        linhas.append(_linha("orbita", f"{orb.label} ({orb.note})", orb.confidence,
                             "CRISM", orb.source_url, orb.source_name))
    ter = terrain_at(lat, lon) if inside else None
    if ter and ter.get("classe"):
        nota = ter.get("nota_seguranca")
        linhas.append(_linha("terreno", ter["classe"], "contexto", "classificação da equipe H2G2",
                             "", "terrain.geojson (polígonos sobre HiRISE)"))
        if nota:
            out["contexto"].append(_linha("seguranca_terreno", nota, "contexto",
                                          "classificação da equipe H2G2", "",
                                          "terrain.geojson (polígonos sobre HiRISE)"))
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
