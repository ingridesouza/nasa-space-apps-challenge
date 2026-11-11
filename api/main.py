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

from fastapi import FastAPI

from db import get_connection
from raster_sampling import sample_all_rasters
from vector_queries import nearby_photos, nearest_science_target

app = FastAPI(title="H2G2 API -- feature 01")


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
    }


@app.get("/health")
def health():
    return {"status": "ok"}
