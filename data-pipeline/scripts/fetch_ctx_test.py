"""Test script for the Mars Trek WMTS adapter.

Usage:
    python scripts/fetch_ctx_test.py                 # smoke test (confirmed product)
    python scripts/fetch_ctx_test.py ctx_optical      # tries the real CTX (pending)

Reads the layer from data-pipeline/config/layers.yaml, fetches the product's real
GetCapabilities, picks the highest available zoom TileMatrix and downloads the
tiles covering the test bbox into data/local/tiles/<layer>/.

By default it runs `smoke_test`: a product we already confirmed exists on
Mars Trek, used only to prove that the adapter (GetCapabilities
parsing, lat/lon -> tile conversion, download) works end to end
with real data. The `product_id` of `ctx_optical` is still a
placeholder -- see the pending item in section 5 of
feature-01-mapa-hiperlocal-boxwork.md.
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.base import BBox
from adapters.mars_trek_wmts import MarsTrekWMTSAdapter

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")


def main() -> None:
    layer_key = sys.argv[1] if len(sys.argv) > 1 else "smoke_test"

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if layer_key not in config["layers"]:
        available = ", ".join(config["layers"])
        raise SystemExit(f"Layer '{layer_key}' does not exist in layers.yaml. Available: {available}")

    layer_cfg = config["layers"][layer_key]
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", layer_key)

    adapter = MarsTrekWMTSAdapter(product_id=layer_cfg["product_id"], region=layer_cfg["region"])

    print(f"[1/3] Layer: {layer_key} (product_id={layer_cfg['product_id']!r})")
    print(f"      Fetching GetCapabilities: {adapter.capabilities_url()}")
    caps = adapter.get_capabilities()
    print(f"      style={caps['style']!r} tile_matrix_set={caps['tile_matrix_set']!r}")
    print(f"      {len(caps['matrices'])} zoom levels available")

    # highest available zoom = most detailed tile for the test
    tile_matrix = max(caps["matrices"], key=lambda k: caps["matrices"][k].matrix_width)
    print(f"[2/3] Using the highest resolution TileMatrix for the test: {tile_matrix}")

    bbox = BBox(**layer_cfg["test_bbox"])
    results = adapter.fetch_tiles(bbox=bbox, tile_matrix=tile_matrix, out_dir=out_dir)

    print(f"[3/3] {len(results)} tiles downloaded to {out_dir}")
    for r in results[:5]:
        print(f"      row={r.row} col={r.col} -> {r.local_path}")
    if len(results) > 5:
        print(f"      ... and {len(results) - 5} more")

    entry = adapter.to_raster_registry_entry(layer_key, results, out_dir)
    print("\nNormalized entry for raster_registry:")
    print(entry)


if __name__ == "__main__":
    main()
