"""Script de teste do adaptador Mars Trek WMTS.

Uso:
    python scripts/fetch_ctx_test.py                 # smoke test (produto confirmado)
    python scripts/fetch_ctx_test.py ctx_optica       # tenta o CTX real (pendente)

Lê a camada de data-pipeline/config/layers.yaml, busca o GetCapabilities
real do produto, escolhe o TileMatrix de maior zoom disponível e baixa os
tiles que cobrem o bbox de teste para data/local/tiles/<camada>/.

Por padrão roda `smoke_test`: um produto que já confirmamos existir no
Mars Trek, usado só para provar que o adaptador (parsing de
GetCapabilities, conversão lat/lon -> tile, download) funciona de
ponta a ponta com dado real. O `product_id` de `ctx_optica` ainda é um
placeholder -- ver pendência na seção 5 do
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
        disponiveis = ", ".join(config["layers"])
        raise SystemExit(f"Camada '{layer_key}' não existe em layers.yaml. Disponíveis: {disponiveis}")

    layer_cfg = config["layers"][layer_key]
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", layer_key)

    adapter = MarsTrekWMTSAdapter(product_id=layer_cfg["product_id"], region=layer_cfg["region"])

    print(f"[1/3] Camada: {layer_key} (product_id={layer_cfg['product_id']!r})")
    print(f"      Buscando GetCapabilities: {adapter.capabilities_url()}")
    caps = adapter.get_capabilities()
    print(f"      style={caps['style']!r} tile_matrix_set={caps['tile_matrix_set']!r}")
    print(f"      {len(caps['matrices'])} níveis de zoom disponíveis")

    # maior zoom disponível = tile mais detalhado para o teste
    tile_matrix = max(caps["matrices"], key=lambda k: caps["matrices"][k].matrix_width)
    print(f"[2/3] Usando TileMatrix de maior resolução para o teste: {tile_matrix}")

    bbox = BBox(**layer_cfg["bbox_teste"])
    results = adapter.fetch_tiles(bbox=bbox, tile_matrix=tile_matrix, out_dir=out_dir)

    print(f"[3/3] {len(results)} tiles baixados em {out_dir}")
    for r in results[:5]:
        print(f"      row={r.row} col={r.col} -> {r.local_path}")
    if len(results) > 5:
        print(f"      ... e mais {len(results) - 5}")

    entry = adapter.to_raster_registry_entry(layer_key, results, out_dir)
    print("\nEntrada normalizada para raster_registry:")
    print(entry)


if __name__ == "__main__":
    main()
