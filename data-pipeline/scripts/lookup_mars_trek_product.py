"""Busca produtos no índice interno do Mars Trek por palavra-chave, sem
precisar abrir o navegador e inspecionar o DevTools manualmente.

Descoberto em 2026-11-11 inspecionando `jpl/config/config.json` do
próprio site (`searchAutoLayerItemsUrl`) e confirmado contra uma request
real do painel de busca (ver PROXIMOS-PASSOS.md).

Uso:
    python scripts/lookup_mars_trek_product.py "HiRISE Gale"
    python scripts/lookup_mars_trek_product.py "Gale Crater" --details

Sem `--details`, só lista título/instrumento/uuid de cada resultado.
Com `--details`, também chama `getLayerServices` pra cada um e mostra o
`layerId`/`endPoint` real (o que vira `product_id` no `layers.yaml`).
"""

import argparse
import sys

import requests

SEARCH_URL = "https://trek.nasa.gov/mars/TrekServices/ws/index/eq/searchItems"
LAYER_SERVICES_URL = "https://trek.nasa.gov/mars/TrekServices/ws/index/getLayerServices"


def search(keyword: str, rows: int = 30) -> list[dict]:
    params = {
        "key": keyword,
        "proj": "urn:ogc:def:crs:EPSG::104905",
        "start": 0,
        "rows": rows,
        "resolutionMin": "",
        "resolutionMax": "",
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()["response"]["docs"]


def layer_services(uuid: str) -> list[dict]:
    resp = requests.get(LAYER_SERVICES_URL, params={"uuid": uuid}, timeout=20)
    resp.raise_for_status()
    return resp.json()["response"]["docs"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", help="termo de busca, ex: 'HiRISE Gale'")
    parser.add_argument("--details", action="store_true", help="também busca os serviços/product_id de cada resultado")
    args = parser.parse_args()

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    results = search(args.keyword)
    print(f"{len(results)} resultado(s) para {args.keyword!r}:\n")

    for doc in results:
        title = doc.get("title", "(sem título)")
        instrument = doc.get("instrument", "-")
        mission = doc.get("mission", "-")
        uuid = doc.get("item_UUID")
        print(f"- {title}  [{instrument} | {mission}]  uuid={uuid}")

        if args.details and uuid:
            for svc in layer_services(uuid):
                proto = svc.get("protocol")
                layer_id = svc.get("layerId") or svc.get("item_DBID")
                endpoint = svc.get("endPoint")
                print(f"    -> {proto}: layerId={layer_id!r}  endPoint={endpoint}")


if __name__ == "__main__":
    main()
