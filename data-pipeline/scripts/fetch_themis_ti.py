"""Baixa só a janela do boxwork do mosaico THEMIS de inércia térmica
quantitativa (USGS Astropedia) e grava um GeoTIFF local pequeno.

Uso:
    python scripts/fetch_themis_ti.py

O .cub tem 2,5 GB; o rasterio lê por /vsicurl/ só os blocos da janela
(HTTP Range). Saída em data/local/tiles/themis_ti/ti_100m.tif, já com
transform em graus (lon/lat) -- a eqc com lat_ts=0 é linear em graus,
então é só trocar a escala do transform, sem reamostrar nenhum pixel.
"""

import math
import os
import sys

import numpy as np
import rasterio
import yaml
from rasterio.transform import Affine
from rasterio.windows import from_bounds

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", "themis_ti", "ti_100m.tif")
MARGEM_DEG = 0.01  # um pouco além do bbox, pra borda do recorte não ficar sem célula


def main() -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["layers"]["themis_ti"]
    b = cfg["bbox_teste"]

    with rasterio.open("/vsicurl/" + cfg["url"]) as ds:
        raio = ds.crs.to_dict().get("R")
        if not raio:
            raise SystemExit(f"CRS inesperado (sem esfera R): {ds.crs}")
        m_por_grau = math.pi * raio / 180

        def xy(lon, lat):
            return lon * m_por_grau, lat * m_por_grau

        x0, y0 = xy(b["min_lon"] - MARGEM_DEG, b["min_lat"] - MARGEM_DEG)
        x1, y1 = xy(b["max_lon"] + MARGEM_DEG, b["max_lat"] + MARGEM_DEG)
        janela = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
        print(f"[1/2] Lendo janela {janela} de {cfg['url']}")
        dados = ds.read(1, window=janela)
        t = ds.window_transform(janela)
        nodata = ds.nodata

    validos = dados[(dados != nodata) & np.isfinite(dados)] if nodata is not None else dados[np.isfinite(dados)]
    if validos.size == 0:
        raise SystemExit("Janela sem nenhum valor válido -- não grava nada (sem dado inventado)")

    graus = Affine(t.a / m_por_grau, 0, t.c / m_por_grau, 0, t.e / m_por_grau, t.f / m_por_grau)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with rasterio.open(
        OUT_PATH, "w", driver="GTiff", width=dados.shape[1], height=dados.shape[0], count=1,
        dtype="float32", transform=graus, nodata=nodata,
        crs=f"+proj=longlat +a={raio} +b={raio} +no_defs",
    ) as dst:
        dst.write(dados.astype("float32"), 1)
        dst.update_tags(fonte="THEMIS Global Thermal Inertia Mosaic, quantitativo 32-bit (USGS Astropedia)",
                        url=cfg["url"], unidade="J m-2 K-1 s-1/2", resolucao_m="100")

    print(f"[2/2] {dados.shape} células -> {OUT_PATH}")
    print(f"      TI min/mediana/max: {validos.min():.0f} / {np.median(validos):.0f} / {validos.max():.0f}")


if __name__ == "__main__":
    main()
