"""Inércia térmica (THEMIS, quantitativa, 100 m/px) -- camada colorida e
valor no ponto. Arquivo gerado por data-pipeline/scripts/fetch_themis_ti.py.

TI alta = material que guarda calor (rocha exposta, solo cimentado);
TI baixa = material solto (areia, poeira). Só essa leitura qualitativa é
dada aqui: cortes numéricos de classe exigiriam citação (Fergason et al.
2006) e ficam fora até serem verificados."""

import functools
import os
import sqlite3

import numpy as np
import rasterio

UNIDADE = "J m⁻² K⁻¹ s⁻½"
FONTE = "Mars Odyssey THEMIS · mosaico global de inércia térmica quantitativo (USGS Astropedia), 100 m/px"

#: faixa fixa da escala de cor (cobre 260–503 do recorte do boxwork com folga);
#: fixa para a cor significar o mesmo valor em qualquer tile
TI_MIN, TI_MAX = 200.0, 550.0
#: mesmas paradas de cor da legenda em web/layers.js (TI_LEGENDA)
PARADAS = ((0.0, (40, 30, 90)), (0.35, (60, 110, 190)), (0.65, (240, 200, 70)), (1.0, (220, 70, 40)))


def _cor(t: np.ndarray) -> np.ndarray:
    """t em [0,1] -> (3, ...) uint8 por interpolação linear entre PARADAS."""
    xs = [p for p, _ in PARADAS]
    return np.stack([np.interp(t, xs, [c[i] for _, c in PARADAS]) for i in range(3)]).astype("uint8")


@functools.lru_cache(maxsize=1)
def grade_ti_rgba(path: str):
    """(rgba[4,h,w], transform, crs) -- sem dado vira pixel transparente."""
    with rasterio.open(path) as ds:
        ti = ds.read(1).astype("float64")
        nodata, transform, crs = ds.nodata, ds.transform, ds.crs
    valido = np.isfinite(ti) if nodata is None else (ti != nodata) & np.isfinite(ti)
    t = np.clip((np.where(valido, ti, TI_MIN) - TI_MIN) / (TI_MAX - TI_MIN), 0, 1)
    rgba = np.zeros((4, *ti.shape), dtype="uint8")
    rgba[:3] = _cor(t)
    rgba[3] = np.where(valido, 255, 0)
    return rgba, transform, crs


def inercia_no_ponto(conn: sqlite3.Connection, lat: float, lon: float) -> dict | None:
    """Valor de TI na célula de 100 m que contém o ponto, ou None (sem dado)."""
    row = conn.execute(
        "SELECT local_tile_path FROM raster_registry WHERE tipo_acesso = 'termico_escalar'"
        " AND min_lon <= ? AND ? <= max_lon AND min_lat <= ? AND ? <= max_lat",
        (lon, lon, lat, lat),
    ).fetchone()
    if row is None or not os.path.isfile(row["local_tile_path"]):
        return None
    with rasterio.open(row["local_tile_path"]) as ds:
        r, c = ds.index(lon, lat)
        if not (0 <= r < ds.height and 0 <= c < ds.width):
            return None
        v = float(ds.read(1)[r, c])
        if (ds.nodata is not None and v == ds.nodata) or not np.isfinite(v):
            return None
    return {"valor": round(v), "unidade": UNIDADE, "resolucao_m": 100, "fonte": FONTE, "confianca": "medido"}
