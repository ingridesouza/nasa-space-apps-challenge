"""Script de teste do adaptador ArcGIS ImageServer (DTM HiRISE 1m de Gale).

Uso:
    python scripts/fetch_dtm_test.py

Baixa um recorte real do DEM (`dtm_hirise_1m` em config/layers.yaml) e
confirma, com rasterio, que os valores são elevação real em metros (não
uma imagem renderizada) -- esperado: piso da Cratera Gale, por volta de
-4500 m.
"""

import os
import sys

import rasterio
import yaml

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.arcgis_image_server import ArcGISImageServerAdapter
from adapters.base import BBox

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "layers.yaml")


def main() -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    layer_cfg = config["layers"]["dtm_hirise_1m"]
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "tiles", "dtm_hirise_1m")

    local_path = os.path.join(out_dir, "dem_512x512.tif")
    if os.path.exists(local_path):
        # já baixado: não depende do Mars Trek (lento/instável) a cada make build
        print(f"[1-2/3] DEM já existe em {local_path}; pulando download (apague para baixar de novo)")
    else:
        local_path = baixar(layer_cfg, out_dir)

    print("[3/3] Validando valores de elevação com rasterio...")
    with rasterio.open(local_path) as ds:
        band = ds.read(1)
        print(f"      crs={ds.crs} shape={ds.shape}")
        print(f"      elevação min/max: {band.min():.1f} m / {band.max():.1f} m")


def baixar(layer_cfg: dict, out_dir: str) -> str:
    adapter = ArcGISImageServerAdapter(
        image_server_url=layer_cfg["image_server_url"],
        spatial_ref_wkid=layer_cfg["spatial_ref_wkid"],
    )

    print("[1/3] Buscando metadados do serviço...")
    info = adapter.get_service_info()
    print(f"      pixelType={info['pixelType']!r} bandCount={info['bandCount']}")
    print(f"      extent: {info['extent']}")

    bbox = BBox(**layer_cfg["bbox_teste"])
    print(f"[2/3] Exportando recorte real (512x512) para {bbox}")
    results = adapter.fetch_tiles(bbox=bbox, tile_matrix="512x512", out_dir=out_dir)
    local_path = results[0].local_path
    print(f"      salvo em {local_path}")
    return local_path


if __name__ == "__main__":
    main()
