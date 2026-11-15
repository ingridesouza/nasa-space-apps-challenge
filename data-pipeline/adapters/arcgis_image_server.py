"""Adapter for rasters served as an ArcGIS ImageServer on Mars Trek
-- used by the Gale 1 m HiRISE DTM (item 6 of the feature 01 table).

Unlike WMTS (adapters/mars_trek_wmts.py), there is no fixed tile grid
here: the service exports a custom raster crop via
`exportImage`, with the real pixel values (elevation in meters, not
a rendered image) -- confirmed against the Gale DEM:
values between -4531 m and -4476 m, consistent with the crater floor.

Discovered via `scripts/lookup_mars_trek_product.py` (see
NEXT-STEPS.md) from the "Gale Crater" search result on
Mars Trek, `ArcGISImageService` service of the item "MRO HiRISE, Gale
Crater DEM".
"""

import os

import requests

from .base import BBox, LayerAdapter, TileResult


class ArcGISImageServerAdapter(LayerAdapter):
    category = "topographic"

    def __init__(self, image_server_url: str, spatial_ref_wkid: int = 104905):
        self.image_server_url = image_server_url.rstrip("/")
        self.spatial_ref_wkid = spatial_ref_wkid

    def get_service_info(self) -> dict:
        resp = requests.get(self.image_server_url, params={"f": "json"}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch_tiles(self, bbox: BBox, tile_matrix: str, out_dir: str) -> list[TileResult]:
        """`tile_matrix` is reused here for the output size in
        pixels, in the "WIDTHxHEIGHT" format (e.g. "512x512") -- there is no
        tile grid in this service, it is a custom crop by bbox."""
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
