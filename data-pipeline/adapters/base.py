"""Common interface every data source adapter must implement.

Each source (Mars Trek, PDS, MSL images API, AI4Mars, MMGIS...) gets
an adapter that knows how to fetch and normalize its own data. The rest of the
pipeline (and the API) only knows the normalized format -- never the raw
format of each source. That is what allows swapping `product_id`/URL on Friday
without rewriting ingestion logic.
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
    """A downloaded tile already located in the working CRS."""

    row: int
    col: int
    tile_matrix: str
    local_path: str
    bbox: BBox


class LayerAdapter(ABC):
    """Adapter for a data layer (raster served as tiles)."""

    #: filled in by the subclasses, used in `raster_registry`
    category: str

    @abstractmethod
    def fetch_tiles(self, bbox: BBox, tile_matrix: str, out_dir: str) -> list[TileResult]:
        """Downloads the tiles covering `bbox` at level `tile_matrix` and
        returns where each one was saved locally."""
        raise NotImplementedError

    def to_raster_registry_entry(self, layer_name: str, tiles: list[TileResult], out_dir: str) -> dict:
        """Normalizes the result of `fetch_tiles` to the
        `raster_registry` schema described in feature 01 (section 3.1)."""
        return {
            "layer_name": layer_name,
            "local_tile_path": out_dir,
            "bbox": tiles[0].bbox.__dict__ if tiles else None,
            "minzoom": None,
            "maxzoom": None,
            "category": self.category,
        }
