"""Alertas por regra fixa da feature 08 -- ver
docs/feature-08-plano-implementacao.md (fase 1).

Nenhum modelo de linguagem aqui: o modelo local (fase 2) só explica o
que estas regras já decidiram, nunca cria nem cancela um alerta.
Lista vazia significa "nenhum alerta", nunca "seguro"."""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache

from geo import haversine_m
from raster_sampling import classify_slope
from tempo_marte import data_do_sol, ls, sol_msl

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
# Escolha nossa: sem parada do rover nesse raio, o veredito depende só do DTM
# de órbita (~6 m/px), que pegou 4 de 25 paradas íngremes medidas pelo rover.
RAIO_SEM_HISTORICO_M = 100

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
        # até 25 m vale o nível medido; de 25 a 100 m (onde "sem histórico" não dispara) vira atenção
        if dist <= RAIO_SEM_HISTORICO_M and (pior is None or p["tilt"] > pior[0]["tilt"]):
            pior = (p, dist, status if dist <= RAIO_HISTORICO_M else "atencao")

    if pior is None:
        return []
    p, dist, status = pior
    msg = f"O Curiosity mediu {_num(p['tilt'])}° de inclinação a {dist:.0f} m daqui (sol {p['sol']})."
    return [_alerta(status, "terreno_historico", msg, "MMGIS MSL_waypoints")]


def _regra_sem_historico(lat: float, lon: float, raster_values: dict, waypoints_path: str) -> list[dict]:
    paradas = carregar_paradas(waypoints_path)
    if paradas is None or raster_values.get("slope_deg") is None:
        return []  # já avisado por outra regra (sem histórico / sem inclinação)
    if any(haversine_m(lat, lon, p["lat"], p["lon"]) <= RAIO_SEM_HISTORICO_M for p in paradas):
        return []
    msg = (f"Nenhuma parada do Curiosity a menos de {RAIO_SEM_HISTORICO_M} m: a inclinação vem só do mapa de órbita "
           "(cerca de 6 m por pixel), que não enxerga cristas de 1 a 2 m.")
    return [_alerta("atencao", "sem_historico", msg, "MMGIS MSL_waypoints + DTM HiRISE (Mars Trek)")]


def _regra_risco_previsto(raster_values: dict) -> list[dict]:
    from previsao import risco_inclinacao  # import tardio: previsao usa este módulo

    risco = risco_inclinacao(raster_values.get("slope_deg"))
    if not risco or risco["chance_pct"] < 20 or raster_values.get("slope_status") != "seguro":
        return []  # mapa já avisa (>= 15°) ou chance baixa
    msg = (f"O mapa diz {_num(raster_values['slope_deg'])}°, mas onde o mapa marca {risco['faixa_mapa']} "
           f"o rover mediu {risco['limite_deg']}° ou mais em {risco['chance_pct']}% das paradas.")
    return [_alerta("atencao", "risco_previsto", msg, "Previsão H2G2: histórico do rover × DTM")]


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
        + _regra_sem_historico(lat, lon, raster_values, waypoints_path)
        + _regra_risco_previsto(raster_values)
        + _regra_volta_base(lat, lon)
        + _regra_areia(raster_values)
    )
    return sorted(alertas, key=lambda a: _ORDEM[a["nivel"]])


# Tempestades regionais e globais se concentram na metade do ano com o periélio
# (primavera e verão do sul): Ls 180° a 360° (Mars24 / climatologia MCD).
LS_POEIRA = (180.0, 360.0)


def tempo_e_alertas_do_sol(sol_dado: int, agora: datetime | None = None) -> tuple[dict, list[dict]]:
    """Modo sem Terra (fase 3): estação de agora e idade do dado REMS/RAD.
    Vale pro planeta, não pro ponto: entra em /api/conditions."""
    agora = agora or datetime.now(timezone.utc)
    sol_agora, ls_agora = sol_msl(agora), ls(agora)
    idade = sol_agora - sol_dado
    tempo = {"sol_agora": sol_agora, "ls_agora": round(ls_agora, 1), "sol_do_dado": sol_dado,
             "data_do_dado": data_do_sol(sol_dado).date().isoformat(), "idade_do_dado_sols": idade,
             "fonte": "algoritmo Mars24 (NASA GISS) sobre o relógio local"}
    alertas = []
    if idade >= 1:
        alertas.append(_alerta("atencao", "dado_antigo",
                               f"Condições do sol {sol_dado}, de {idade} sols atrás: não é leitura de agora.",
                               f"REMS/RAD sol {sol_dado}"))
    if LS_POEIRA[0] <= ls_agora < LS_POEIRA[1]:
        alertas.append(_alerta("atencao", "temporada_poeira",
                               f"Temporada de tempestades de poeira (Ls {_num(ls_agora)}°, risco maior entre 180° e 360°).",
                               "Mars24 (Ls) + climatologia de poeira"))
    return tempo, alertas


#: ~5.88 m/px é o pixel do DTM (route_planning.py) -- amostrar 1 a cada
#: 5 pontos da rota já cobre a escala dos raios de alerta (25-100 m)
#: sem rodar a regra do histórico do rover ponto a ponto num caminho
#: com centenas de pixels.
PASSO_AMOSTRA_ROTA = 5


def alertas_da_rota(pontos: list[tuple[float, float]], waypoints_path: str = WAYPOINTS_PATH) -> list[dict]:
    """Alertas do agente (feature 08) cruzados com o caminho calculado
    pela feature 02 (route_planning.py): maior inclinação que o
    Curiosity já mediu perto da rota e trechos que saem do raio de
    volta da base. A inclinação em si já está em trechos_risco (mesmo
    limite do DTM que o A*); aqui só entra o que o agente sabe e o A*
    não usa pra escolher caminho.

    Cada alerta carrega `indice_ponto` (índice em `pontos`) -- quem
    chama (api/main.py) converte pra distância acumulada real usando o
    mesmo `perfil_elevacao` que já devolve pro gráfico, pra dizer EM
    QUE TRECHO da caminhada o alerta vale, não só que ele existe."""
    amostra_idx = list(range(0, len(pontos), PASSO_AMOSTRA_ROTA))
    if pontos and amostra_idx[-1] != len(pontos) - 1:
        amostra_idx.append(len(pontos) - 1)

    vistos = set()
    alertas = []
    for i in amostra_idx:
        lat, lon = pontos[i]
        for a in _regra_terreno_historico(lat, lon, waypoints_path) + _regra_volta_base(lat, lon):
            chave = (a["tipo"], a["mensagem"])
            if chave not in vistos:
                vistos.add(chave)
                alertas.append({**a, "indice_ponto": i})
    return alertas


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
