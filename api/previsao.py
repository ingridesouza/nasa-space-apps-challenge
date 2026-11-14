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
CAMPOS = ("temp_min_c", "temp_max_c", "pressao_pa")
JANELA_LS = 15.0
MESMO_PERIODO_SOLS = 100  # fica fora da climatologia: é o "agora" da anomalia


@lru_cache(maxsize=1)
def carregar_clima(path: str = CLIMA_PATH) -> list[dict] | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["sols"]


def _dist_ls(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _climatologia(clima: list[dict], ls_alvo: float, campo: str, base: int) -> list[float]:
    """Valores de outros períodos na mesma estação, só com dado conhecido no sol base."""
    return [c[campo] for c in clima
            if c[campo] is not None and c["sol"] <= base - MESMO_PERIODO_SOLS
            and _dist_ls(c["ls"], ls_alvo) <= JANELA_LS]


def prever(clima: list[dict], sol: int, base: dict) -> dict:
    """Previsão de `sol` a partir da linha `base` da climatologia (o último dado)."""
    ls_sol = ls(data_do_sol(sol))
    out = {}
    for campo in CAMPOS:
        alvo = _climatologia(clima, ls_sol, campo, base["sol"])
        na_base = _climatologia(clima, base["ls"], campo, base["sol"])
        if not alvo or not na_base or base[campo] is None:
            out[campo] = None  # sem ano anterior nessa estação: não inventa
            continue
        anomalia = base[campo] - mean(na_base)
        out[campo] = {"valor": round(mean(alvo) + anomalia, 1),
                      "desvio": round(pstdev(alvo), 1) if len(alvo) > 1 else None}
    return {"sol": sol, "ls": round(ls_sol, 1), **out}


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
    erros = {k: [] for k in CAMPOS}
    ingenuo = {k: [] for k in CAMPOS}
    for c in clima:
        base = _base_para(clima, c["sol"] - horizonte)
        if base is None:
            continue
        p = prever(clima, c["sol"], base)
        for k in CAMPOS:
            if p[k] and c[k] is not None:
                erros[k].append(abs(p[k]["valor"] - c[k]))
                ingenuo[k].append(abs(base[k] - c[k]))
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
        return None
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


def previsao_do_sol(sol: int, duracao_min: float | None = None) -> dict | None:
    clima = carregar_clima()
    if not clima:
        return None
    base = _base_para(clima, sol - 1)  # nunca olha o próprio sol: dá pra comparar com o medido
    if base is None:
        return None
    horizonte = sol - base["sol"]
    medido = next((c for c in clima if c["sol"] == sol), None)
    return {
        **prever(clima, sol, base),
        "medido": {k: medido[k] for k in CAMPOS} if medido else None,
        "janela_eva": janela_eva(clima, sol, base, duracao_min) if duracao_min else None,
        "sol_base": base["sol"], "horizonte_sols": horizonte,
        "erro_backtest": backtest(max(horizonte, 1)),
        "confianca": "estimado",
        "metodo": "climatologia REMS por estação (Ls ±15°) + anomalia do último sol medido",
        "fonte": "MSL REMS (PDS Atmospheres) + Ls pelo Mars24",
    }
