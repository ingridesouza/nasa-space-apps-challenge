"""Downloads the official IAU/USGS nomenclature (item 12 of feature 01) for
the Gale area, from the USGS "Mars High-Resolution Mosaic Viewer" webmap
on ArcGIS Online -- discovered on 2026-11-13 via a search on the public
ArcGIS API (see NEXT-STEPS.md).

The nomenclature layers of this webmap come as a `featureCollection`
embedded in the item's own JSON (it is not a separate FeatureServer
queryable by bbox) -- so we download everything once and filter
locally by the features that touch our bbox of interest.

Usage:
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

# generous bbox around Gale (covers the whole crater + Aeolis Mons/Palus),
# much larger than the 3x3km test bbox -- nomenclature is sparse, it is worth
# taking a larger radius so as not to miss relevant nearby features.
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
    print("Fetching the USGS nomenclature webmap...")
    resp = requests.get(
        f"https://www.arcgis.com/sharing/rest/content/items/{WEBMAP_ITEM_ID}/data",
        params={"f": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    result = []
    for layer in data.get("operationalLayers", []):
        title = layer.get("title") or ""
        if "Nomenclature" not in title:
            continue
        for sub in layer.get("featureCollection", {}).get("layers", []):
            for feat in sub.get("featureSet", {}).get("features", []):
                attrs = feat.get("attributes", {})
                if bbox_intersects(GALE_REGION_BBOX, attrs):
                    result.append(
                        {
                            "name": attrs.get("name"),
                            "type": attrs.get("type"),
                            "layer_category": title,
                            "lat": attrs.get("center_lat"),
                            "lon": attrs.get("center_lon"),
                            "diameter_km": attrs.get("diameter"),
                            "iau_approved": attrs.get("approval"),
                            "source_url": attrs.get("link"),
                        }
                    )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"{len(result)} features found in the Gale region:")
    for item in result:
        print(f"  - {item['name']} ({item['type']}) -- {item['lat']:.3f}, {item['lon']:.3f}")
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
