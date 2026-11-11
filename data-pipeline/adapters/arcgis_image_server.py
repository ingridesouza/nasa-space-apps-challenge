"""Adaptador para rasters servidos como ArcGIS ImageServer no Mars Trek
-- usado pelo DTM HiRISE de 1 m de Gale (item 6 da tabela da feature 01).

Diferente do WMTS (adapters/mars_trek_wmts.py), aqui não existe grade
fixa de tiles: o serviço exporta um recorte raster sob medida via
`exportImage`, com os valores reais de pixel (elevação em metros, não
uma imagem renderizada) -- confirmado batendo contra o DEM de Gale:
valores entre -4531 m e -4476 m, consistentes com o piso da cratera.

Descoberto via `scripts/lookup_mars_trek_product.py` (ver
PROXIMOS-PASSOS.md) a partir do resultado de busca "Gale Crater" no
Mars Trek, serviço `ArcGISImageService` do item "MRO HiRISE, Gale
Crater DEM".
"""

import os

import requests

from .base import BBox, LayerAdapter, TileResult


class ArcGISImageServerAdapter(LayerAdapter):
    categoria = "topografica"

    def __init__(self, image_server_url: str, spatial_ref_wkid: int = 104905):
        self.image_server_url = image_server_url.rstrip("/")
        self.spatial_ref_wkid = spatial_ref_wkid

    def get_service_info(self) -> dict:
        resp = requests.get(self.image_server_url, params={"f": "json"}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch_tiles(self, bbox: BBox, tile_matrix: str, out_dir: str) -> list[TileResult]:
        """`tile_matrix` aqui é reaproveitado para o tamanho de saída em
        pixels, no formato "LARGURAxALTURA" (ex. "512x512") -- não existe
        grade de tile neste serviço, é um recorte sob medida por bbox."""
        width, height = (int(v) for v in tile_matrix.lower().split("x"))

        os.makedirs(out_dir, exist_ok=True)
        params = {
            "bbox": f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}",
            "bboxSR": self.spatial_ref_wkid,
            "imageSR": self.spatial_ref_wkid,
            "size": f"{width},{height}",
            "format": "tiff",
            "pixelType": "F32",
            "noData": "",
            "interpolation": "RSP_BilinearInterpolation",
            "f": "image",
        }
        resp = requests.get(f"{self.image_server_url}/exportImage", params=params, timeout=60)
        resp.raise_for_status()

        local_path = os.path.join(out_dir, f"dem_{width}x{height}.tif")
        with open(local_path, "wb") as f:
            f.write(resp.content)

        return [TileResult(row=0, col=0, tile_matrix=tile_matrix, local_path=local_path, bbox=bbox)]
