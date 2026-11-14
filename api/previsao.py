"""Feature 06: previsão local offline do clima de Gale (REMS).

Método (base citada no plano: de Cabo-García et al. 2019; aqui a versão
mínima): clima de Marte se repete muito de ano a ano na mesma estação.
  previsto(sol) = climatologia(Ls do sol) + anomalia do último dado
  anomalia      = observado(sol base) - climatologia(Ls do sol base)
Climatologia = média dos sols de outros anos com Ls a até JANELA_LS graus.
A anomalia também absorve a subida do rover no Monte Sharp (pressão cai
com a altitude). Faixa = desvio padrão da climatologia. Erro medido por
backtest nos próprios dados, com o mesmo horizonte.

Lê só data/local/conditions/climatologia.json (cache_climatologia.py)."""

import json
import math
import os
from functools import lru_cache
from statistics import mean, pstdev

from tempo_marte import data_do_sol, ls

CLIMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "local", "conditions", "climatologia.json")
CAMPOS = ("temp_min_c", "temp_max_c", "pressao_pa")  # clima do ar: definem o sol base
# Também previstos pelo mesmo método: chão ao meio-dia (REMS/GTS) e dose do dia (RAD).
# A dose muda com a estação (coluna de ar) e com o ciclo solar (lento: a anomalia carrega).
# Tempestade solar (SPE) não se prevê: é pico de horas, sem aviso nos dados locais.
PREVISTOS = CAMPOS + ("solo_meio_dia_c", "dose_ugy_dia")
# Backtest (231 sols): para a dose, estação + anomalia erra MAIS que repetir o último sol
# (20 sols: 9,5 × 7,5 µGy/dia; 330 sols: 32,8 × 24,2). Quem manda é o ciclo solar de 11 anos,
# não a estação de Marte -- então a dose prevista é a do último sol medido.
PERSISTENCIA = ("dose_ugy_dia",)
JANELA_LS = 15.0
MESMO_PERIODO_SOLS = 100  # fica fora da climatologia: é o "agora" da anomalia


@lru_cache(maxsize=4)
def carregar_clima(path: str = CLIMA_PATH, locais_path: str | None = None) -> list[dict] | None:
    """Série do PDS + medições locais (sensor do habitat/traje). A local manda no mesmo sol."""
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        por_sol = {c["sol"]: c for c in json.load(f)["sols"]}
    for m in carregar_locais(locais_path or LOCAL_PATH):
        por_sol[m["sol"]] = {**por_sol.get(m["sol"], {}), **m}
    return [por_sol[s] for s in sorted(por_sol)]


# --------------------------------------------------------------------------- #
# Medições locais: em Marte o dado novo vem do sensor do habitat, não da Terra.
# Cada uma vira o "último sol medido" e a previsão se corrige sozinha, offline.
# --------------------------------------------------------------------------- #
LOCAL_PATH = os.path.join(os.path.dirname(CLIMA_PATH), "medicoes_locais.json")


def carregar_locais(path: str = LOCAL_PATH) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _gravar_locais(locais: list[dict], path: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(locais, key=lambda m: m["sol"]), f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)  # troca atômica: nunca deixa o arquivo pela metade
    carregar_clima.cache_clear()
    backtest.cache_clear()


def registrar_medicao(m: dict, path: str = LOCAL_PATH) -> dict:
    entrada = {"sol": m["sol"], "ls": round(ls(data_do_sol(m["sol"])), 1), "origem": "local",
               **{k: m[k] for k in PREVISTOS if m.get(k) is not None}}
    _gravar_locais([x for x in carregar_locais(path) if x["sol"] != m["sol"]] + [entrada], path)
    return entrada


def apagar_medicao(sol: int, path: str = LOCAL_PATH) -> bool:
    locais = carregar_locais(path)
    restantes = [x for x in locais if x["sol"] != sol]
    if len(restantes) == len(locais):
        return False
    _gravar_locais(restantes, path)
    return True


def _dist_ls(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _climatologia(clima: list[dict], ls_alvo: float, campo: str, base: int) -> list[float]:
    """Valores de outros períodos na mesma estação, só com dado conhecido no sol base."""
    return [c[campo] for c in clima
            if c.get(campo) is not None and c["sol"] <= base - MESMO_PERIODO_SOLS
            and _dist_ls(c["ls"], ls_alvo) <= JANELA_LS]


def prever(clima: list[dict], sol: int, base: dict) -> dict:
    """Previsão de `sol` a partir da linha `base` da climatologia (o último dado)."""
    ls_sol = ls(data_do_sol(sol))
    out = {}
    for campo in PREVISTOS:
        b = _ultimo_com(clima, campo, base["sol"])  # sensor pode faltar no sol base: usa o último com dado
        if campo in PERSISTENCIA:
            out[campo] = {"valor": round(b[campo], 1), "desvio": None, "metodo": "último sol medido"} if b else None
            continue
        alvo = _climatologia(clima, ls_sol, campo, b["sol"]) if b else []
        na_base = _climatologia(clima, b["ls"], campo, b["sol"]) if b else []
        if not alvo or not na_base:
            out[campo] = None  # sem ano anterior nessa estação: não inventa
            continue
        anomalia = b[campo] - mean(na_base)
        out[campo] = {"valor": round(mean(alvo) + anomalia, 1),
                      "desvio": round(pstdev(alvo), 1) if len(alvo) > 1 else None}
    return {"sol": sol, "ls": round(ls_sol, 1), **out}


def _ultimo_com(clima: list[dict], campo: str, ate_sol: int) -> dict | None:
    antes = [c for c in clima if c["sol"] <= ate_sol and c.get(campo) is not None]
    return antes[-1] if antes else None


def _base_para(clima: list[dict], sol: int) -> dict | None:
    """Último sol da climatologia antes de `sol` com todos os campos."""
    antes = [c for c in clima if c["sol"] <= sol and all(c[k] is not None for k in CAMPOS)]
    return antes[-1] if antes else None


@lru_cache(maxsize=32)
def backtest(horizonte: int, path: str = CLIMA_PATH) -> dict | None:
    """Erro médio absoluto prevendo sols já medidos com `horizonte` sols de antecedência,
    contra a persistência ingênua (repetir o último dado)."""
    clima = carregar_clima(path)
    if not clima:
        return None
    erros = {k: [] for k in PREVISTOS}
    ingenuo = {k: [] for k in PREVISTOS}
    for c in clima:
        base = _base_para(clima, c["sol"] - horizonte)
        if base is None:
            continue
        p = prever(clima, c["sol"], base)
        for k in PREVISTOS:
            if p[k] and c.get(k) is not None:
                erros[k].append(abs(p[k]["valor"] - c[k]))
                ingenuo[k].append(abs(_ultimo_com(clima, k, base["sol"])[k] - c[k]))
    if not erros["temp_min_c"]:
        return None
    return {"horizonte_sols": horizonte, "n": len(erros["temp_min_c"]),
            **{k: {"erro_medio": round(mean(v), 1), "erro_repetindo_ultimo": round(mean(ingenuo[k]), 1)}
               for k, v in erros.items() if v}}


def janela_eva(clima: list[dict], sol: int, base: dict, duracao_min: float) -> dict | None:
    """Melhor janela do dia para uma EVA de `duracao_min` (PDF da F06: "acoplar a previsão
    à rota"). Curva prevista por hora = climatologia horária + anomalia média do sol base.
    Melhor = janela cuja hora mais fria é a mais quente (o traje sofre no pior momento)."""
    ls_sol = ls(data_do_sol(sol))
    com_curva = [c for c in clima if c.get("temp_por_hora")]

    def clima_hora(ls_alvo: float, h: int) -> float | None:
        v = [c["temp_por_hora"][str(h)] for c in com_curva
             if c["sol"] <= base["sol"] - MESMO_PERIODO_SOLS and _dist_ls(c["ls"], ls_alvo) <= JANELA_LS
             and str(h) in c["temp_por_hora"]]
        return mean(v) if v else None

    curva_base = base.get("temp_por_hora") or {}
    difs = [curva_base[str(h)] - c for h in range(24)
            if str(h) in curva_base and (c := clima_hora(base["ls"], h)) is not None]
    if not difs:
        # medição do habitat não traz curva por hora: corrige pela média do dia (mín.+máx.)/2
        meio = lambda c: (c["temp_min_c"] + c["temp_max_c"]) / 2  # noqa: E731
        normal = [meio(c) for c in com_curva if c["sol"] <= base["sol"] - MESMO_PERIODO_SOLS
                  and _dist_ls(c["ls"], base["ls"]) <= JANELA_LS and c.get("temp_min_c") is not None]
        if not normal or base.get("temp_min_c") is None:
            return None
        difs = [meio(base) - mean(normal)]
    anomalia = mean(difs)
    curva = {h: round(c + anomalia, 1) for h in range(24) if (c := clima_hora(ls_sol, h)) is not None}
    n = min(24, max(1, math.ceil(duracao_min / 60)))
    janelas = [(min(curva[(i + k) % 24] for k in range(n)), i) for i in range(24)
               if all((i + k) % 24 in curva for k in range(n))]
    if not janelas:
        return None
    pior, inicio = max(janelas)
    return {"inicio_lmst": f"{inicio:02d}:00", "fim_lmst": f"{(inicio + n) % 24:02d}:00", "horas": n,
            "temp_mais_fria_na_janela_c": pior, "curva_por_hora": curva,
            "criterio": "janela cuja hora mais fria é a mais quente (temperatura do ar prevista)"}


FATOR_DIVERGENCIA = 3  # medição a mais de 3x o erro típico do prazo = fora do normal da estação


def divergencia(clima: list[dict], medida: dict) -> list[dict]:
    """Compara uma medição local com o que o modelo previa para aquele sol sem vê-la."""
    antes = _base_para([c for c in clima if c["sol"] != medida["sol"]], medida["sol"] - 1)
    if antes is None:
        return []
    p = prever([c for c in clima if c["sol"] != medida["sol"]], medida["sol"], antes)
    erro = backtest(max(medida["sol"] - antes["sol"], 1)) or {}
    out = []
    for k in PREVISTOS:
        if p.get(k) and medida.get(k) is not None and erro.get(k):
            limite = FATOR_DIVERGENCIA * erro[k]["erro_medio"]
            dif = medida[k] - p[k]["valor"]
            if abs(dif) > limite:
                out.append({"campo": k, "medido": medida[k], "esperado": p[k]["valor"],
                            "diferenca": round(dif, 1), "limite": round(limite, 1)})
    return out


def previsao_do_sol(sol: int, duracao_min: float | None = None) -> dict | None:
    clima = carregar_clima()
    if not clima:
        return None
    base = _base_para(clima, sol - 1)  # nunca olha o próprio sol: dá pra comparar com o medido
    if base is None:
        return None
    horizonte = sol - base["sol"]
    medido = next((c for c in clima if c["sol"] == sol), None)
    local = next((c for c in (medido, base) if c and c.get("origem") == "local"), None)
    return {
        **prever(clima, sol, base),
        "data_terra": data_do_sol(sol).date().isoformat(),
        "medido": {k: medido.get(k) for k in PREVISTOS} if medido else None,
        "janela_eva": janela_eva(clima, sol, base, duracao_min) if duracao_min else None,
        "sol_base": base["sol"], "horizonte_sols": horizonte,
        "base_origem": base.get("origem", "pds"),
        "medicao_local": local and {k: local.get(k) for k in ("sol", *PREVISTOS)},
        "divergencia": divergencia(clima, local) if local else [],
        "erro_backtest": backtest(max(horizonte, 1)),
        "confianca": "estimado",
        "metodo": "climatologia REMS por estação (Ls ±15°) + anomalia do último sol medido",
        "fonte": "MSL REMS (PDS Atmospheres) + Ls pelo Mars24",
    }


# --------------------------------------------------------------------------- #
# Inclinação real a partir do mapa, pelo histórico do rover
# --------------------------------------------------------------------------- #
# O DTM de órbita (~6 m/px) suaviza as cristas. Nas paradas do Curiosity temos os
# dois números no mesmo lugar: o do mapa e o que o rover mediu (atitude, "tilt").
# A frequência observada vira a chance de o terreno real passar de 15° (Artemis).
FAIXAS_MAPA = ((0, 7), (7, 10), (10, 15), (15, 90))
LIMITE_REAL_DEG = 15


def tabela_de(pares: list[tuple[float, float]]) -> list[dict]:
    """pares (inclinação do mapa, inclinação medida pelo rover) -> frequência por faixa do mapa."""
    out = []
    for lo, hi in FAIXAS_MAPA:
        medidos = [t for s, t in pares if lo <= s < hi]
        out.append({"de": lo, "ate": hi, "n": len(medidos),
                    "acima": sum(t >= LIMITE_REAL_DEG for t in medidos)})
    return out


@lru_cache(maxsize=1)
def tabela_inclinacao() -> list[dict] | None:
    from alertas import carregar_paradas
    from db import get_connection
    from raster_sampling import sample_all_rasters

    paradas = carregar_paradas()
    if not paradas:
        return None
    conn = get_connection()
    try:
        # shortcut: ~300 leituras do DTM na 1ª chamada (alguns segundos); pré-calcular no build se pesar
        pares = [(rv["slope_deg"], p["tilt"]) for p in paradas
                 if (rv := sample_all_rasters(conn, p["lat"], p["lon"])).get("slope_deg") is not None]
    finally:
        conn.close()
    return tabela_de(pares) if pares else None


def risco_inclinacao(slope_mapa: float | None, tabela: list[dict] | None = None) -> dict | None:
    tabela = tabela if tabela is not None else tabela_inclinacao()
    if slope_mapa is None or not tabela:
        return None
    f = next(f for f in tabela if f["de"] <= slope_mapa < f["ate"])
    if f["n"] == 0:
        return None
    return {"chance_pct": round(100 * f["acima"] / f["n"]), "acima": f["acima"], "n": f["n"],
            "faixa_mapa": f"{f['de']}–{f['ate']}°" if f["ate"] < 90 else f"≥{f['de']}°",
            "limite_deg": LIMITE_REAL_DEG, "confianca": "estimado",
            "metodo": "frequência nas paradas do Curiosity com a mesma faixa de inclinação no mapa",
            "fonte": "MMGIS MSL_waypoints (tilt do rover) × DTM HiRISE (Mars Trek)"}


def status_previsto(status_mapa: str, risco: dict | None) -> str:
    """Status que considera a previsão: chance >= 20% vira atenção; >= 50% vira perigo só com
    pelo menos MIN_PARADAS_PERIGO paradas na faixa (a faixa >= 15° tem só 5: fica em atenção)."""
    ordem = ["seguro", "atencao", "perigo"]
    if not risco or risco["chance_pct"] < 20:
        pela_chance = "seguro"
    elif risco["chance_pct"] >= 50 and risco["n"] >= MIN_PARADAS_PERIGO:
        pela_chance = "perigo"
    else:
        pela_chance = "atencao"
    return max(status_mapa, pela_chance, key=ordem.index)


MIN_PARADAS_PERIGO = 20
# cor por chance: transparente abaixo de 20% (não poluir o mapa), âmbar e vermelho dos vereditos
COR_RISCO = ((50, (232, 100, 63, 200)), (20, (242, 179, 61, 160)))


@lru_cache(maxsize=1)
def grade_risco_rgba(dtm_path: str):
    """Camada "risco de inclinação (previsto)": cada pixel do DTM pintado pela chance
    histórica de o terreno real passar de 15°. Devolve (rgba[4,h,w], transform, crs)."""
    import numpy as np
    import rasterio

    from geo import MARS_METERS_PER_DEGREE
    from route_planning import _load_dtm, _slope_grid_deg

    elevacao, transform, _, _ = _load_dtm(dtm_path)
    slope = _slope_grid_deg(elevacao, abs(transform.a) * MARS_METERS_PER_DEGREE)
    rgba = np.zeros((4, *slope.shape), dtype="uint8")
    for f in tabela_inclinacao() or []:
        if not f["n"]:
            continue
        pct = 100 * f["acima"] / f["n"]
        cor = next((c for limite, c in COR_RISCO if pct >= limite and (limite < 50 or f["n"] >= MIN_PARADAS_PERIGO)), None)
        if cor:
            rgba[:, (slope >= f["de"]) & (slope < f["ate"])] = np.array(cor, dtype="uint8")[:, None]
    with rasterio.open(dtm_path) as ds:
        crs = ds.crs
    return rgba, transform, crs
