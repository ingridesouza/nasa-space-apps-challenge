"""Lê o resumo de condições (REMS+RAD) já cacheado em
data/local/conditions/sol_<n>.json -- gerado por
data-pipeline/scripts/cache_conditions.py. Sem chamada de rede aqui:
roda 100% offline, como o resto do projeto."""

import json
import os

CONDITIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "local", "conditions")


def get_cached_conditions(sol: int) -> dict | None:
    path = os.path.join(CONDITIONS_DIR, f"sol_{sol}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
