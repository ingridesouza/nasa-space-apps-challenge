"""Adapter for any product served by Mars Trek via WMTS
(CTX, HiRISE, MOLA, THEMIS -- see feature-01-mapa-hiperlocal-boxwork.md,
table in section 1, items 1-4).

Flow:
  1. downloads and parses the product's `GetCapabilities` XML
  2. finds the tile template and the TileMatrixSet definition
     (never guesses `{Style}`/`{TileMatrixSet}`/`{TileMatrix}` -- it comes from the XML)
  3. converts lat/lon -> tile row/col using the matrix definition
  4. downloads the tiles covering the requested bbox

Official doc: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars
"""

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .base import BBox, LayerAdapter, TileResult

# Mars equatorial radius (IAU), in meters -- used only for products
# whose TileMatrixSet is in a projected CRS (TopLeftCorner in meters).
MARS_RADIUS_M = 3_396_190.0

# OGC constant for "meters per degree" in geographic CRSs (degrees) --
# confirmed against the real XML of the msss_atlas_simp_clon product:
# the WMTS 0.28mm pixel convention uses the mean Earth radius
# (6,371,000 m) even for non-Earth bodies; it is an artifact of how
# Mars Trek generates its "default028mm" tile sets, not our mistake.
OGC_METERS_PER_DEGREE = (2 * math.pi * 6_371_000.0) / 360.0

NS = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
}


@dataclass
class TileMatrix:
    identifier: str
    scale_denominator: float
    top_left_corner: tuple[float, float]  # (x, y) in meters
    tile_width: int
    tile_height: int
    matrix_width: int
    matrix_height: int


class MarsTrekWMTSAdapter(LayerAdapter):
    category = "optical"  # overridden by config when the product is another kind (topographic, thermal...)

    def __init__(self, product_id: str, region: str = "Mars/EQ", base_url: str = "https://trek.nasa.gov/tiles"):
        self.product_id = product_id
        self.region = region
        self.base_url = base_url
        self._caps_cache: dict | None = None

    # ------------------------------------------------------------------
    # GetCapabilities
    # ------------------------------------------------------------------

    def capabilities_url(self) -> str:
        return f"{self.base_url}/{self.region}/{self.product_id}/1.0.0/WMTSCapabilities.xml"

    def get_capabilities(self) -> dict:
        if self._caps_cache is not None:
            return self._caps_cache

        url = self.capabilities_url()
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        layer = root.find(".//wmts:Contents/wmts:Layer", NS)
        if layer is None:
            raise ValueError(f"No Layer found in {url} -- does product '{self.product_id}' exist?")

        style_el = layer.find("wmts:Style/ows:Identifier", NS)
        style = style_el.text if style_el is not None else "default"

        resource = layer.find("wmts:ResourceURL", NS)
        tile_template = resource.get("template") if resource is not None else None

        tile_matrix_set_link = layer.find("wmts:TileMatrixSetLink/wmts:TileMatrixSet", NS)
        matrix_set_name = tile_matrix_set_link.text if tile_matrix_set_link is not None else None

        matrix_set_el = root.find(
            f".//wmts:Contents/wmts:TileMatrixSet[ows:Identifier='{matrix_set_name}']", NS
        )
        matrices = self._parse_tile_matrices(matrix_set_el) if matrix_set_el is not None else {}

        self._caps_cache = {
            "style": style,
            "tile_template": tile_template,
            "tile_matrix_set": matrix_set_name,
            "matrices": matrices,
        }
        return self._caps_cache

    @staticmethod
    def _parse_tile_matrices(matrix_set_el: ET.Element) -> dict[str, TileMatrix]:
        matrices: dict[str, TileMatrix] = {}
        for tm in matrix_set_el.findall("wmts:TileMatrix", NS):
            identifier = tm.find("ows:Identifier", NS).text
            scale = float(tm.find("wmts:ScaleDenominator", NS).text)
            top_left_raw = tm.find("wmts:TopLeftCorner", NS).text.split()
            top_left = (float(top_left_raw[0]), float(top_left_raw[1]))
            # some products publish these fields as float ("2.0")
            # even though they are integers by definition in the WMTS schema
            tile_w = int(float(tm.find("wmts:TileWidth", NS).text))
            tile_h = int(float(tm.find("wmts:TileHeight", NS).text))
            matrix_w = int(float(tm.find("wmts:MatrixWidth", NS).text))
            matrix_h = int(float(tm.find("wmts:MatrixHeight", NS).text))
            matrices[identifier] = TileMatrix(
                identifier=identifier,
                scale_denominator=scale,
                top_left_corner=top_left,
                tile_width=tile_w,
                tile_height=tile_h,
                matrix_width=matrix_w,
                matrix_height=matrix_h,
            )
        return matrices

    # ------------------------------------------------------------------
    # lat/lon -> row/col
    # ------------------------------------------------------------------

    @staticmethod
    def _is_degree_based(matrix: TileMatrix) -> bool:
        """Heuristic: a TileMatrixSet in a geographic CRS has TopLeftCorner
        within the degree range (e.g. -180/90); a CRS projected in
        meters has values in the millions."""
        x, y = matrix.top_left_corner
        return abs(x) <= 180 and abs(y) <= 90

    @staticmethod
    def _pixel_span(scale_denominator: float, degree_based: bool) -> float:
        # 0.28 mm/pixel is the standard OGC WMTS constant to convert
        # scale -> ground resolution. In a geographic CRS the result
        # comes out in meters and must be converted back to degrees
        # (see OGC_METERS_PER_DEGREE); in a projected CRS it is already in
        # meters, the same unit as TopLeftCorner.
        meters_per_pixel = scale_denominator * 0.00028
        if degree_based:
            return meters_per_pixel / OGC_METERS_PER_DEGREE
        return meters_per_pixel

    def lonlat_to_tile(self, lon: float, lat: float, matrix: TileMatrix) -> tuple[int, int]:
        degree_based = self._is_degree_based(matrix)
        pixel_span = self._pixel_span(matrix.scale_denominator, degree_based)
        top_left_x, top_left_y = matrix.top_left_corner

        if degree_based:
            x, y = lon, lat
        else:
            x = MARS_RADIUS_M * math.radians(lon)
            y = MARS_RADIUS_M * math.radians(lat)

        tile_span_x = pixel_span * matrix.tile_width
        tile_span_y = pixel_span * matrix.tile_height

        col = int((x - top_left_x) // tile_span_x)
        row = int((top_left_y - y) // tile_span_y)
        return row, col

    def bbox_to_tile_range(self, bbox: BBox, matrix: TileMatrix) -> tuple[int, int, int, int]:
        """Returns (row_min, row_max, col_min, col_max) covering the bbox."""
        row_a, col_a = self.lonlat_to_tile(bbox.min_lon, bbox.max_lat, matrix)  # NW corner
        row_b, col_b = self.lonlat_to_tile(bbox.max_lon, bbox.min_lat, matrix)  # SE corner
        row_min, row_max = sorted((row_a, row_b))
        col_min, col_max = sorted((col_a, col_b))
        return row_min, row_max, col_min, col_max

    def tile_range_to_bbox(self, row_min: int, row_max: int, col_min: int, col_max: int, matrix: TileMatrix) -> BBox:
        """Inverse of `bbox_to_tile_range`: REAL geographic bbox covered
        by the downloaded set of tiles (quantized to the TileMatrix's own
        grid -- almost always LARGER than the originally requested
        bbox, since a tile cannot be downloaded "by half").

        It is this bbox, not the requested one, that must go into raster_registry:
        using the requested bbox as the ImageSource corner coordinate in the
        frontend stretches/shifts the image (each product quantizes
        differently, so CTX and HiRISE ended up misaligned with each other --
        a real bug found on 2026-11-14, not just cosmetic)."""
        degree_based = self._is_degree_based(matrix)
        pixel_span = self._pixel_span(matrix.scale_denominator, degree_based)
        top_left_x, top_left_y = matrix.top_left_corner
        tile_span_x = pixel_span * matrix.tile_width
        tile_span_y = pixel_span * matrix.tile_height

        x_min = top_left_x + col_min * tile_span_x
        x_max = top_left_x + (col_max + 1) * tile_span_x
        y_max = top_left_y - row_min * tile_span_y
        y_min = top_left_y - (row_max + 1) * tile_span_y

        if degree_based:
            return BBox(min_lon=x_min, min_lat=y_min, max_lon=x_max, max_lat=y_max)

        return BBox(
            min_lon=math.degrees(x_min / MARS_RADIUS_M),
            min_lat=math.degrees(y_min / MARS_RADIUS_M),
            max_lon=math.degrees(x_max / MARS_RADIUS_M),
            max_lat=math.degrees(y_max / MARS_RADIUS_M),
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def fetch_tiles(self, bbox: BBox, tile_matrix: str, out_dir: str) -> list[TileResult]:
        caps = self.get_capabilities()
        matrix = caps["matrices"].get(tile_matrix)
        if matrix is None:
            available = ", ".join(sorted(caps["matrices"]))
            raise ValueError(f"TileMatrix '{tile_matrix}' does not exist. Available: {available}")

        row_min, row_max, col_min, col_max = self.bbox_to_tile_range(bbox, matrix)
        os.makedirs(out_dir, exist_ok=True)

        # REAL bbox covered by the batch of tiles (not the bbox requested above --
        # see the tile_range_to_bbox docstring) -- this is what must become the
        # mosaic corner coordinate in raster_registry/frontend.
        real_coverage = self.tile_range_to_bbox(row_min, row_max, col_min, col_max, matrix)

        results: list[TileResult] = []
        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):
                url = (
                    caps["tile_template"]
                    .replace("{Style}", caps["style"])
                    .replace("{TileMatrixSet}", caps["tile_matrix_set"])
                    .replace("{TileMatrix}", tile_matrix)
                    .replace("{TileRow}", str(row))
                    .replace("{TileCol}", str(col))
                )
                local_path = os.path.join(out_dir, f"{tile_matrix}_{row}_{col}.png")
                if not os.path.exists(local_path):  # reuse tile already downloaded
                    resp = requests.get(url, timeout=30)
                    if resp.status_code != 200:
                        continue  # tile outside the product coverage; normal at the edges
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                results.append(
                    TileResult(row=row, col=col, tile_matrix=tile_matrix, local_path=local_path, bbox=real_coverage)
                )

        return results
