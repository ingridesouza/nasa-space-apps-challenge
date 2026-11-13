"""API da feature 01 -- ver feature-01-mapa-hiperlocal-boxwork.md,
seção 3.2.

Rodar localmente:
    cd api
    python -m uvicorn main:app --reload

Testar:
    http://127.0.0.1:8000/api/point?lat=-4.59&lon=137.44
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from alertas import alertas_do_ponto, paradas_no_bbox
from conditions import get_cached_conditions
from db import get_connection
from mosaics import build_hillshade_png, build_mosaic_png
from nomenclature import get_cached_nomenclature
from raster_sampling import sample_all_rasters
from vector_queries import nearby_photos, nearest_science_target

# Sol de referência da missão -- dado real cacheado (não é "hoje",
# é o mesmo sol usado nos testes de REMS/RAD, ver PROXIMOS-PASSOS.md).
# Quando o recorte final do boxwork sair, troca por um sol relevante
# daquela área.
REFERENCE_SOL = 4650

app = FastAPI(title="H2G2 API -- feature 01")

# Frontend roda em porta separada (Vite, :5173) durante o desenvolvimento.
# Liberado para qualquer origem -- é uma API local de hackathon, sem dado
# sensível, sem auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/point")
def get_point(lat: float, lon: float):
    """Combina busca vetorial (fotos próximas, alvo científico) e
    sampling de raster (elevação/slope) num único ponto -- contrato
    reaproveitado pela feature 02 (rota/A*) e feature 08 (voz)."""
    conn = get_connection()
    try:
        fotos = nearby_photos(conn, lat, lon)
        alvo = nearest_science_target(conn, lat, lon)
        rasters = sample_all_rasters(conn, lat, lon)
    finally:
        conn.close()

    return {
        "point": {"lat": lat, "lon": lon},
        "nearby_photos": fotos,
        "science_target": alvo,
        "raster_values": rasters,
        # feature 08: acréscimo ao contrato, nenhuma chave acima mudou
        "alertas": alertas_do_ponto(lat, lon, rasters),
    }


@app.get("/layers")
def get_layers():
    """Metadados das camadas já confirmadas -- o frontend usa isto (e
    não uma cópia hardcoded) pra saber bbox/categoria de cada uma, uma
    única fonte de verdade (raster_registry)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT layer_name, min_lon, min_lat, max_lon, max_lat, categoria, tipo_acesso FROM raster_registry"
        ).fetchall()
    finally:
        conn.close()

    return [dict(r) for r in rows]


@app.get("/mosaics/{layer_name}.png")
def get_mosaic(layer_name: str):
    """Imagem única pra exibir uma camada no mapa -- stitch de tiles
    (`tiles_wmts`) ou hillshade gerado na hora a partir de um DTM
    (`hillshade_derivado`). Ver mosaics.py pra entender por que isto
    substitui uma fonte `tiles` XYZ padrão do MapLibre (nossa grade de
    tiles do Mars Trek não é Web Mercator)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT local_tile_path, tipo_acesso FROM raster_registry WHERE layer_name = ?",
            (layer_name,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Camada não encontrada")

    if row["tipo_acesso"] == "hillshade_derivado":
        png_bytes = build_hillshade_png(row["local_tile_path"])
    elif row["tipo_acesso"] == "tiles_wmts":
        png_bytes = build_mosaic_png(row["local_tile_path"])
    else:
        raise HTTPException(status_code=404, detail=f"tipo_acesso {row['tipo_acesso']!r} não vira mosaico")

    if png_bytes is None:
        raise HTTPException(status_code=404, detail="Dado local não encontrado para esta camada")

    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/conditions")
def get_conditions(sol: int = REFERENCE_SOL):
    """Clima (REMS) + radiação (RAD) resumidos de um sol -- não é por
    coordenada (ver feature-01-mapa-hiperlocal-boxwork.md, seção 2.3:
    "não é uma camada de mapa", é valor amarrado ao sol). Lê só do
    cache local (data/local/conditions/), sem chamada de rede."""
    dados = get_cached_conditions(sol)
    if dados is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sol {sol} não cacheado ainda -- rodar data-pipeline/scripts/cache_conditions.py {sol}",
        )
    return dados


@app.get("/api/nomenclature")
def get_nomenclature():
    """Feições com nome oficial IAU/USGS na região de Gale (item 12 da
    feature 01) -- cacheado por
    data-pipeline/scripts/fetch_nomenclature.py, sem chamada de rede
    aqui."""
    dados = get_cached_nomenclature()
    if dados is None:
        raise HTTPException(
            status_code=404,
            detail="Nomenclatura não cacheada -- rodar data-pipeline/scripts/fetch_nomenclature.py",
        )
    return dados


@app.get("/api/rover-track")
def get_rover_track():
    """Paradas do Curiosity dentro do bbox das camadas, com a inclinação
    medida pelo rover já classificada (feature 08, memória do terreno).
    O bbox vem do raster_registry, mesma fonte única do /layers."""
    conn = get_connection()
    try:
        bbox = conn.execute(
            "SELECT MIN(min_lon), MIN(min_lat), MAX(max_lon), MAX(max_lat) FROM raster_registry"
        ).fetchone()
    finally:
        conn.close()

    paradas = paradas_no_bbox(*bbox) if bbox[0] is not None else None
    if paradas is None:
        raise HTTPException(
            status_code=404,
            detail="Trilha não disponível -- rodar data-pipeline/scripts/fetch_rover_waypoints.py e populate_raster_registry.py",
        )
    return paradas


@app.get("/health")
def health():
    return {"status": "ok"}
