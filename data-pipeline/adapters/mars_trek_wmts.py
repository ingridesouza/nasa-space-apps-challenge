"""Adaptador para qualquer produto servido pelo Mars Trek via WMTS
(CTX, HiRISE, MOLA, THEMIS -- ver feature-01-mapa-hiperlocal-boxwork.md,
tabela da seção 1, itens 1-4).

Fluxo:
  1. baixa e parseia o `GetCapabilities` XML do produto
  2. localiza o template de tile e a definição do TileMatrixSet
     (nunca chuta `{Style}`/`{TileMatrixSet}`/`{TileMatrix}` -- vem do XML)
  3. converte lat/lon -> row/col de tile usando a definição do matrix
  4. baixa os tiles que cobrem o bbox pedido

Doc oficial: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars
"""

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .base import BBox, LayerAdapter, TileResult

# Raio equatorial de Marte (IAU), em metros -- usado só para produtos
# cujo TileMatrixSet está num CRS projetado (TopLeftCorner em metros).
MARS_RADIUS_M = 3_396_190.0

# Constante OGC para "metros por grau" em CRS geográficos (graus) --
# confirmada batendo contra o XML real do produto msss_atlas_simp_clon:
# a convenção de pixel de 0.28mm do WMTS usa o raio médio terrestre
# (6 371 000 m) mesmo para corpos não-Terra; é um artefato de como o
# Mars Trek gera seus tile sets "default028mm", não um erro nosso.
OGC_METERS_PER_DEGREE = (2 * math.pi * 6_371_000.0) / 360.0

NS = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
}


@dataclass
class TileMatrix:
    identifier: str
    scale_denominator: float
    top_left_corner: tuple[float, float]  # (x, y) em metros
    tile_width: int
    tile_height: int
    matrix_width: int
    matrix_height: int


class MarsTrekWMTSAdapter(LayerAdapter):
    categoria = "optica"  # sobrescrito por config quando o produto for outro (topografica, termica...)

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
            raise ValueError(f"Nenhum Layer encontrado em {url} -- produto '{self.product_id}' existe?")

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
            # alguns produtos publicam esses campos como float ("2.0")
            # mesmo sendo inteiros por definição do schema WMTS
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
        """Heurística: TileMatrixSet em CRS geográfico tem TopLeftCorner
        dentro do range de graus (ex. -180/90); um CRS projetado em
        metros tem valores na casa dos milhões."""
        x, y = matrix.top_left_corner
        return abs(x) <= 180 and abs(y) <= 90

    @staticmethod
    def _pixel_span(scale_denominator: float, degree_based: bool) -> float:
        # 0.28 mm/pixel é a constante padrão do OGC WMTS para converter
        # escala -> resolução no solo. Em CRS geográfico o resultado
        # sai em metros e precisa ser convertido de volta pra grau
        # (ver OGC_METERS_PER_DEGREE); em CRS projetado já fica em
        # metros, mesma unidade do TopLeftCorner.
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
        """Retorna (row_min, row_max, col_min, col_max) cobrindo o bbox."""
        row_a, col_a = self.lonlat_to_tile(bbox.min_lon, bbox.max_lat, matrix)  # canto NO
        row_b, col_b = self.lonlat_to_tile(bbox.max_lon, bbox.min_lat, matrix)  # canto SE
        row_min, row_max = sorted((row_a, row_b))
        col_min, col_max = sorted((col_a, col_b))
        return row_min, row_max, col_min, col_max

    def tile_range_to_bbox(self, row_min: int, row_max: int, col_min: int, col_max: int, matrix: TileMatrix) -> BBox:
        """Inverso de `bbox_to_tile_range`: bbox geográfico REAL coberto
        pelo conjunto de tiles baixado (quantizado à grade própria do
        TileMatrix -- quase sempre MAIOR que o bbox originalmente
        pedido, já que um tile não pode ser baixado "pela metade").

        É este bbox, não o pedido, que precisa ir pro raster_registry:
        usar o bbox pedido como coordenada de canto do ImageSource no
        frontend estica/desloca a imagem (cada produto quantiza
        diferente, então CTX e HiRISE acabavam desalinhados entre si --
        bug real encontrado em 2026-11-14, não só estético)."""
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
            disponiveis = ", ".join(sorted(caps["matrices"]))
            raise ValueError(f"TileMatrix '{tile_matrix}' não existe. Disponíveis: {disponiveis}")

        row_min, row_max, col_min, col_max = self.bbox_to_tile_range(bbox, matrix)
        os.makedirs(out_dir, exist_ok=True)

        # bbox REAL coberto pelo lote de tiles (não o bbox pedido acima --
        # ver docstring de tile_range_to_bbox) -- é isto que deve virar a
        # coordenada de canto do mosaico no raster_registry/frontend.
        cobertura_real = self.tile_range_to_bbox(row_min, row_max, col_min, col_max, matrix)

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
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    continue  # tile fora da cobertura do produto; normal nas bordas
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                results.append(
                    TileResult(row=row, col=col, tile_matrix=tile_matrix, local_path=local_path, bbox=cobertura_real)
                )

        return results
