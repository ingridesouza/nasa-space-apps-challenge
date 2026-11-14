"""Alertas por regra fixa da feature 08 -- ver
docs/feature-08-plano-implementacao.md (fase 1).

Nenhum modelo de linguagem aqui: o modelo local (fase 2) só explica o
que estas regras já decidiram, nunca cria nem cancela um alerta.
Lista vazia significa "nenhum alerta", nunca "seguro"."""

import json
import os
from functools import lru_cache

from geo import haversine_m
from raster_sampling import classify_slope

WAYPOINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "rover_waypoints.json")

# ponytail: base provisória = parada do Curiosity no sol 4650 (sol de
# referência da API, alvo "Cristas de boxwork"). O repo não tem posição
# de habitat; trocar aqui quando o time definir.
BASE_LAT_LON = (-4.8068928, 137.3798418)

# Escolhas nossas (listadas como decisão em aberto em
# docs/feature-08-agente-local.md): o raio cobre o erro de localização
# do MMGIS; 2 km é o limite de distância do módulo citado na proposta
# (Artemis).
RAIO_HISTORICO_M = 25
LIMITE_VOLTA_BASE_M = 2000

_ORDEM = {"perigo": 0, "atencao": 1, "info": 2}


def _num(valor: float) -> str:
    """22.37 -> "22,4" (mensagem vai pra tela e pra voz em português)."""
    return f"{valor:.1f}".replace(".", ",")


def _alerta(nivel: str, tipo: str, mensagem: str, fonte: str) -> dict:
    return {"nivel": nivel, "tipo": tipo, "mensagem": mensagem, "fonte": fonte}


@lru_cache(maxsize=4)
def carregar_paradas(path: str = WAYPOINTS_PATH) -> list[dict] | None:
    """Paradas do Curiosity (MMGIS), lidas uma vez. None se o arquivo
    não existe (make build não rodou fetch_rover_waypoints.py)."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _regras_inclinacao(raster_values: dict) -> list[dict]:
    slope = raster_values.get("slope_deg")
    status = raster_values.get("slope_status")
    if slope is None:
        return [_alerta("info", "sem_dado", "Sem dado de inclinação neste ponto.", "DTM HiRISE (Mars Trek)")]
    if status == "perigo":
        msg = f"Inclinação de {_num(slope)}° neste ponto, acima do limite de 20° do Artemis."
    elif status == "atencao":
        msg = f"Inclinação de {_num(slope)}° neste ponto, perto do limite de 20° do Artemis."
    else:
        return []
    return [_alerta(status, "inclinacao", msg + " Valor médio do mapa em cerca de 12 m.", "DTM HiRISE (Mars Trek)")]


def _regra_areia(raster_values: dict) -> list[dict]:
    if raster_values.get("classe_ai4mars") is not None:
        return []
    return [
        _alerta(
            "info",
            "sem_dado",
            "Sem dado de areia neste ponto: não dá para afirmar que não há areia.",
            "AI4Mars (sem cobertura no boxwork)",
        )
    ]


def _regra_terreno_historico(lat: float, lon: float, waypoints_path: str) -> list[dict]:
    paradas = carregar_paradas(waypoints_path)
    if paradas is None:
        return [
            _alerta(
                "info",
                "sem_dado",
                "Histórico do rover indisponível (rodar data-pipeline/scripts/fetch_rover_waypoints.py).",
                "MMGIS MSL_waypoints",
            )
        ]

    # Várias paradas perto: só a de maior inclinação vira alerta.
    pior = None
    for p in paradas:
        status = classify_slope(p["tilt"])
        if status == "seguro":
            continue
        dist = haversine_m(lat, lon, p["lat"], p["lon"])
        if dist <= RAIO_HISTORICO_M and (pior is None or p["tilt"] > pior[0]["tilt"]):
            pior = (p, dist, status)

    if pior is None:
        return []
    p, dist, status = pior
    msg = f"O Curiosity mediu {_num(p['tilt'])}° de inclinação a {dist:.0f} m daqui (sol {p['sol']})."
    return [_alerta(status, "terreno_historico", msg, "MMGIS MSL_waypoints")]


def _regra_volta_base(lat: float, lon: float) -> list[dict]:
    dist = haversine_m(lat, lon, *BASE_LAT_LON)
    if dist <= LIMITE_VOLTA_BASE_M:
        return []
    metros = f"{dist:,.0f}".replace(",", ".")  # 2029.4 -> "2.029": em km arredondaria pra "2,0", que lê como dentro do limite
    msg = f"A {metros} m da base: além do limite de 2.000 m de distância do módulo (Artemis)."
    return [_alerta("perigo", "volta_base", msg, "Proposta H2G2 (limite Artemis)")]


def alertas_do_ponto(lat: float, lon: float, raster_values: dict, waypoints_path: str = WAYPOINTS_PATH) -> list[dict]:
    """Todos os alertas de um ponto, do mais grave ao menos grave.
    `raster_values` é o mesmo dict que o /api/point já devolve."""
    alertas = (
        _regras_inclinacao(raster_values)
        + _regra_terreno_historico(lat, lon, waypoints_path)
        + _regra_volta_base(lat, lon)
        + _regra_areia(raster_values)
    )
    return sorted(alertas, key=lambda a: _ORDEM[a["nivel"]])


def paradas_no_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[dict] | None:
    """Trilha do Curiosity dentro do bbox, com a inclinação medida já
    classificada pelos mesmos limites do DTM (15° e 20°)."""
    paradas = carregar_paradas()
    if paradas is None:
        return None
    return [
        {"lat": p["lat"], "lon": p["lon"], "sol": p["sol"], "tilt": p["tilt"], "status": classify_slope(p["tilt"])}
        for p in paradas
        if min_lon <= p["lon"] <= max_lon and min_lat <= p["lat"] <= max_lat
    ]
