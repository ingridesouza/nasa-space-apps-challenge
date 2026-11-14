"""Lê a nomenclatura IAU/USGS já cacheada em data/local/nomenclature.json
-- gerada por data-pipeline/scripts/fetch_nomenclature.py. Sem chamada
de rede aqui, mesmo padrão do conditions.py."""

import json
import os

NOMENCLATURE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "nomenclature.json")


def get_cached_nomenclature() -> list[dict] | None:
    if not os.path.isfile(NOMENCLATURE_PATH):
        return None
    with open(NOMENCLATURE_PATH, encoding="utf-8") as f:
        return json.load(f)
