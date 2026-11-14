"""Baixa a nomenclatura oficial IAU/USGS (item 12 da feature 01) pra
área de Gale, a partir do webmap "Mars High-Resolution Mosaic Viewer"
da USGS no ArcGIS Online -- descoberto em 2026-11-13 via busca na API
pública do ArcGIS (ver PROXIMOS-PASSOS.md).

As camadas de nomenclatura desse webmap vêm como `featureCollection`
embutida no próprio JSON do item (não é uma FeatureServer separada
consultável por bbox) -- por isso baixamos tudo uma vez e filtramos
localmente pelas features que tocam nosso bbox de interesse.

Uso:
    python scripts/fetch_nomenclature.py
"""

import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import requests

WEBMAP_ITEM_ID = "b164957a19544f55a8d6a001c952a590"  # USGS: Mars High-Resolution Mosaic Viewer
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "local", "nomenclature.json")

# bbox generoso ao redor de Gale (cobre a cratera inteira + Aeolis Mons/Palus),
# bem maior que o bbox de teste de 3x3km -- nomenclatura é esparsa, vale
# pegar um raio maior pra não perder feições próximas relevantes.
GALE_REGION_BBOX = (135.0, -8.0, 141.0, -2.0)  # min_lon, min_lat, max_lon, max_lat


def bbox_intersects(a: tuple[float, float, float, float], b_attrs: dict) -> bool:
    a_min_lon, a_min_lat, a_max_lon, a_max_lat = a
    b_min_lon = b_attrs.get("min_lon")
    b_max_lon = b_attrs.get("max_lon")
    b_min_lat = b_attrs.get("min_lat")
    b_max_lat = b_attrs.get("max_lat")
    if None in (b_min_lon, b_max_lon, b_min_lat, b_max_lat):
        return False
    return not (b_max_lon < a_min_lon or b_min_lon > a_max_lon or b_max_lat < a_min_lat or b_min_lat > a_max_lat)


def main() -> None:
    print("Buscando webmap de nomenclatura da USGS...")
    resp = requests.get(
        f"https://www.arcgis.com/sharing/rest/content/items/{WEBMAP_ITEM_ID}/data",
        params={"f": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    resultado = []
    for layer in data.get("operationalLayers", []):
        titulo = layer.get("title") or ""
        if "Nomenclature" not in titulo:
            continue
        for sub in layer.get("featureCollection", {}).get("layers", []):
            for feat in sub.get("featureSet", {}).get("features", []):
                attrs = feat.get("attributes", {})
                if bbox_intersects(GALE_REGION_BBOX, attrs):
                    resultado.append(
                        {
                            "nome": attrs.get("name"),
                            "tipo": attrs.get("type"),
                            "categoria_camada": titulo,
                            "lat": attrs.get("center_lat"),
                            "lon": attrs.get("center_lon"),
                            "diametro_km": attrs.get("diameter"),
                            "aprovado_iau": attrs.get("approval"),
                            "fonte_url": attrs.get("link"),
                        }
                    )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"{len(resultado)} feições encontradas na região de Gale:")
    for item in resultado:
        print(f"  - {item['nome']} ({item['tipo']}) -- {item['lat']:.3f}, {item['lon']:.3f}")
    print(f"\nSalvo em {OUT_PATH}")


if __name__ == "__main__":
    main()
