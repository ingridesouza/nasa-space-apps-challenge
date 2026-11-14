"""Consultas vetoriais em rover_images e science_targets (feature 01,
seção 3.2, passos 1-2). As tabelas ainda estão vazias -- itens 9 e 4 do
PROXIMOS-PASSOS.md -- então estas funções sempre devolvem lista/valor
vazio por enquanto, mas já com a lógica pronta pra quando os dados
entrarem."""

import sqlite3

from geo import bbox_radius_degrees, bearing_cardinal, haversine_m


def all_photos(conn: sqlite3.Connection) -> list[dict]:
    """Todas as fotos com posição real -- usado pela camada "rastro do
    rover" no mapa (pins clicáveis nas posições reais onde cada foto
    foi tirada), diferente de nearby_photos que é por raio ao redor de
    um clique. Mesmas ~200 fotos, outra forma de descobrir."""
    rows = conn.execute("SELECT lat, lon, sol, camera, local_path FROM rover_images ORDER BY sol, id").fetchall()
    return [
        {"lat": r["lat"], "lon": r["lon"], "sol": r["sol"], "camera": r["camera"], "url": r["local_path"]}
        for r in rows
    ]


def nearby_photos(conn: sqlite3.Connection, lat: float, lon: float, radius_m: float = 200) -> list[dict]:
    dlat, dlon = bbox_radius_degrees(lat, radius_m)

    candidatos = conn.execute(
        """
        SELECT rover_images.*
        FROM rover_images_rtree
        JOIN rover_images ON rover_images.id = rover_images_rtree.id
        WHERE rover_images_rtree.min_lon <= ? AND rover_images_rtree.max_lon >= ?
          AND rover_images_rtree.min_lat <= ? AND rover_images_rtree.max_lat >= ?
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
                    "camera": foto["camera"],
                    "url": foto["local_path"],
                }
            )

    resultado.sort(key=lambda f: f["distance_m"])
    return resultado


def nearest_science_target(conn: sqlite3.Connection, lat: float, lon: float, max_radius_m: float = 500) -> dict | None:
    dlat, dlon = bbox_radius_degrees(lat, max_radius_m)

    candidatos = conn.execute(
        """
        SELECT science_targets.*
        FROM science_targets_rtree
        JOIN science_targets ON science_targets.id = science_targets_rtree.id
        WHERE science_targets_rtree.min_lon <= ? AND science_targets_rtree.max_lon >= ?
          AND science_targets_rtree.min_lat <= ? AND science_targets_rtree.max_lat >= ?
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

    return {
        "nome": melhor["nome"],
        "mineral_crism": melhor["mineral_crism"],
        "classe_terreno": melhor["classe_ai4mars"],
        "medicao_curiosity": melhor["medicao_curiosity"],
        "confianca": melhor["confianca"],
        "fonte": melhor["fonte_url"],
        "distance_m": round(menor_distancia),
    }
