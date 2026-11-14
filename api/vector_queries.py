"""Consultas vetoriais do /api/point (feature 01, seção 3.2, passos 1-2),
/api/photos e da rota "mais ciência".

Fonte única: tabelas do F03/F04 no banco local (`photos`, `targets`,
`measurements`), geradas por data-pipeline/f03/etl/build.py. As chaves de
resposta são as do contrato original de /api/point -- não renomear."""

import sqlite3

from geo import bbox_radius_degrees, bearing_cardinal, haversine_m


def _photo_url(img_path: str, base_url: str) -> str:
    """Arquivo local do pacote F03, servido em /bundle pela própria API."""
    return f"{base_url}/bundle/{img_path}"


def all_photos(conn: sqlite3.Connection, base_url: str) -> list[dict]:
    """Todas as fotos com posição real -- usado pela camada "rastro do
    rover" no mapa (pins clicáveis nas posições reais onde cada foto
    foi tirada), diferente de nearby_photos que é por raio ao redor de
    um clique."""
    rows = conn.execute(
        "SELECT lat, lon, sol, instrument, img_path FROM photos WHERE img_path != '' ORDER BY sol, id"
    ).fetchall()
    return [
        {
            "lat": r["lat"],
            "lon": r["lon"],
            "sol": r["sol"],
            "camera": r["instrument"],
            "url": _photo_url(r["img_path"], base_url),
        }
        for r in rows
    ]


def nearby_photos(conn: sqlite3.Connection, lat: float, lon: float, base_url: str, radius_m: float = 200) -> list[dict]:
    dlat, dlon = bbox_radius_degrees(lat, radius_m)

    candidatos = conn.execute(
        """
        SELECT photos.*
        FROM photo_rtree
        JOIN photos ON photos.rowid = photo_rtree.rid
        WHERE photo_rtree.min_lon <= ? AND photo_rtree.max_lon >= ?
          AND photo_rtree.min_lat <= ? AND photo_rtree.max_lat >= ?
          AND photos.img_path != ''
        """,
        (lon + dlon, lon - dlon, lat + dlat, lat - dlat),
    ).fetchall()

    resultado = []
    for foto in candidatos:
        distancia = haversine_m(lat, lon, foto["lat"], foto["lon"])
        if distancia <= radius_m:
            resultado.append(
                {
                    "distance_m": round(distancia),
                    "bearing": bearing_cardinal(lat, lon, foto["lat"], foto["lon"]),
                    "sol": foto["sol"],
                    "camera": foto["instrument"],
                    "url": _photo_url(foto["img_path"], base_url),
                }
            )

    resultado.sort(key=lambda f: f["distance_m"])
    return resultado


def _medicoes_em_texto(conn: sqlite3.Connection, target_id: str) -> tuple[str | None, str | None]:
    """Resumo das medições do alvo ("APXS: ... · CheMin: ...") e a URL da
    primeira fonte. (None, None) se o alvo não tem medição publicada."""
    meds = conn.execute(
        "SELECT instrument, summary, source_url FROM measurements WHERE target_id = ? ORDER BY instrument",
        (target_id,),
    ).fetchall()
    if not meds:
        return None, None
    return " · ".join(f"{m['instrument']}: {m['summary']}" for m in meds), meds[0]["source_url"]


def todos_alvos_cientificos(conn: sqlite3.Connection) -> list[dict]:
    """Alvos para a rota "mais ciência": nome, lat, lon, medicao_curiosity, fonte_url."""
    alvos = []
    for t in conn.execute("SELECT id, name, lat, lon, blog_url FROM targets").fetchall():
        medicao, fonte = _medicoes_em_texto(conn, t["id"])
        alvos.append({"nome": t["name"], "lat": t["lat"], "lon": t["lon"],
                      "medicao_curiosity": medicao, "fonte_url": fonte or t["blog_url"]})
    return alvos


def nearest_science_target(conn: sqlite3.Connection, lat: float, lon: float, max_radius_m: float = 500) -> dict | None:
    dlat, dlon = bbox_radius_degrees(lat, max_radius_m)

    candidatos = conn.execute(
        """
        SELECT targets.*
        FROM target_rtree
        JOIN targets ON targets.rowid = target_rtree.rid
        WHERE target_rtree.min_lon <= ? AND target_rtree.max_lon >= ?
          AND target_rtree.min_lat <= ? AND target_rtree.max_lat >= ?
        """,
        (lon + dlon, lon - dlon, lat + dlat, lat - dlat),
    ).fetchall()

    melhor = None
    menor_distancia = None
    for alvo in candidatos:
        distancia = haversine_m(lat, lon, alvo["lat"], alvo["lon"])
        if distancia <= max_radius_m and (menor_distancia is None or distancia < menor_distancia):
            menor_distancia = distancia
            melhor = alvo

    if melhor is None:
        return None

    medicao, fonte = _medicoes_em_texto(conn, melhor["id"])
    return {
        "nome": melhor["name"],
        "mineral_crism": None,  # CRISM por pixel vem na ficha (/science/card, seção "orbita")
        "classe_terreno": melhor["terrain_class"] or None,
        "medicao_curiosity": medicao,
        "confianca": "medido" if medicao else "contexto",
        "fonte": fonte or melhor["blog_url"],
        "distance_m": round(menor_distancia),
    }
