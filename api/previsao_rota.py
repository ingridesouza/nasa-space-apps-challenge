"""Ferramenta "prever rota" (F02 + F06 + F08): análise preditiva de uma rota já
calculada, só com dado histórico da NASA no disco. O backend a chama quando há
rota em jogo e entrega o resultado ao agente; o Gemma 3 4B não faz tool-calling.

Junta, por rota e sol da EVA:
- terreno: chance de o chão real passar de 15° em cada trecho (tilt do Curiosity × DTM);
- histórico do rover perto do caminho e raio de volta à base (alertas_da_rota);
- clima previsto no sol da EVA e a melhor janela para a duração da caminhada (REMS);
- dose prevista na caminhada (RAD do último sol medido × tempo).
Tudo é estimativa: cada bloco leva método, fonte e erro medido no passado."""

from previsao import backtest, previsao_do_sol
from tempo_marte import SOL_S

FAIXAS_CHANCE = (("baixa", 0, 20), ("media", 20, 50), ("alta", 50, 101))  # mesmos cortes de status_previsto


def terreno(rota: dict) -> dict:
    """Metros da rota por faixa de chance e o pior trecho, com a distância do início."""
    perfil = rota["perfil_elevacao"]  # perfil[i + 1] fecha o trecho i
    metros = {nome: 0.0 for nome, _, _ in FAIXAS_CHANCE} | {"sem_dado": 0.0}
    pior = None
    for i, t in enumerate(rota["trechos_risco"]):
        d = perfil[i + 1]["distancia_acumulada_m"] - perfil[i]["distancia_acumulada_m"]
        c = t.get("chance_pct")
        faixa = "sem_dado" if c is None else next(n for n, lo, hi in FAIXAS_CHANCE if lo <= c < hi)
        metros[faixa] += d
        if c is not None and (pior is None or (c, t["slope_deg"]) > (pior["chance_pct"], pior["slope_mapa_deg"])):
            pior = {"chance_pct": c, "slope_mapa_deg": t["slope_deg"], "status_previsto": t.get("status_previsto"),
                    "distancia_m": round(perfil[i]["distancia_acumulada_m"])}
    return {"metros_por_chance": {k: round(v) for k, v in metros.items()}, "pior_trecho": pior,
            "limite_deg": 15, "confianca": "estimado",
            "metodo": "frequência, nas paradas do Curiosity, de o rover medir ≥15° com o mapa na mesma faixa",
            "fonte": "MMGIS MSL_waypoints (tilt do rover) × DTM HiRISE (Mars Trek)"}


def dose(rota: dict, prev: dict | None) -> dict | None:
    d = prev and prev.get("dose_ugy_dia")
    if not d:
        return None  # sem RAD no cache: não finge zero
    horas = rota["tempo_estimado_min"] / 60
    erro = (backtest(max(prev["horizonte_sols"], 1)) or {}).get("dose_ugy_dia")
    por_hora = d["valor"] / (SOL_S / 3600)
    return {"valor_ugy": round(por_hora * horas, 1), "horas": round(horas, 2),
            "erro_ugy": round(erro["erro_medio"] / (SOL_S / 3600) * horas, 1) if erro else None,
            "confianca": "estimado", "metodo": f"dose do dia ({d['metodo']}) × tempo de caminhada",
            "fonte": "MSL RAD (PDS)"}


def prever_rota(rota: dict, sol: int) -> dict:
    """`rota`: uma variante do /api/route (já com chance_pct e alertas por trecho)."""
    prev = previsao_do_sol(sol, rota["tempo_estimado_min"])
    clima = prev and {
        "sol_base": prev["sol_base"], "horizonte_sols": prev["horizonte_sols"],
        **{k: prev[k] for k in ("temp_min_c", "temp_max_c", "pressao_pa", "solo_meio_dia_c")},
        "janela_eva": prev["janela_eva"], "erro_backtest": prev["erro_backtest"],
        "metodo": prev["metodo"], "fonte": prev["fonte"], "confianca": "estimado"}
    return {"tipo": rota["tipo"], "sol_eva": sol, "distancia_m": rota["distancia_m"],
            "tempo_estimado_min": rota["tempo_estimado_min"],
            "terreno": terreno(rota), "alertas": rota.get("alertas", []),
            "clima": clima, "dose": dose(rota, prev)}
