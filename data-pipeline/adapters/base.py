"""Interface comum que todo adaptador de fonte de dado precisa implementar.

Cada fonte (Mars Trek, PDS, API de imagens do MSL, AI4Mars, MMGIS...) ganha
um adaptador que sabe buscar e normalizar seus próprios dados. O resto do
pipeline (e a API) só conhece o formato normalizado -- nunca o formato
bruto de cada fonte. Isso é o que permite trocar `product_id`/URL na sexta
sem reescrever lógica de ingestão.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@dataclass
class TileResult:
    """Um tile baixado e já localizado no CRS de trabalho."""

    row: int
    col: int
    tile_matrix: str
    local_path: str
    bbox: BBox


class LayerAdapter(ABC):
    """Adaptador de uma camada de dado (raster servido em tiles)."""

    #: preenchido pelas subclasses, usado no `raster_registry`
    categoria: str

    @abstractmethod
    def fetch_tiles(self, bbox: BBox, tile_matrix: str, out_dir: str) -> list[TileResult]:
        """Baixa os tiles que cobrem `bbox` no nível `tile_matrix` e
        devolve onde cada um foi salvo localmente."""
        raise NotImplementedError

    def to_raster_registry_entry(self, layer_name: str, tiles: list[TileResult], out_dir: str) -> dict:
        """Normaliza o resultado de `fetch_tiles` para o schema de
        `raster_registry` descrito na feature 01 (seção 3.1)."""
        return {
            "layer_name": layer_name,
            "local_tile_path": out_dir,
            "bbox": tiles[0].bbox.__dict__ if tiles else None,
            "minzoom": None,
            "maxzoom": None,
            "categoria": self.categoria,
        }
