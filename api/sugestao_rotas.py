"""F02 + F08: ordena as variantes do /api/route e diz por quê.

Regra fixa, não o modelo (um 4B erra conta e omite perigo): o rótulo vem do
pior status previsto dos trechos (F06) e dos alertas do agente na rota (F08);
prós e contras só com número da própria rota. Nenhuma rota é escondida nem
trocada sozinha: a sugestão é a ordem, quem decide é o astronauta."""

from datetime import datetime, timezone

from agente import agrupar_alertas
from alertas import LS_POEIRA
from tempo_marte import ls

ORDEM = ["ok", "atencao", "perigo"]
NOME = {"mais_segura": "mais segura", "mais_rapida": "mais rápida", "mais_ciencia": "mais ciência"}
FONTE_TERRENO = "DTM HiRISE (Mars Trek) × histórico do Curiosity (MMGIS)"
FONTE_ROTA = "A* sobre o DTM HiRISE (route_planning.py)"
FONTE_MARGEM = "margem de O2 pessimista, pior ponto da rota (route_planning.py -- Fases 1-3)"

# Limite de folga de O2 pra rebaixar o rótulo -- sem fonte oficial (ver
# docs/feature-02-sugestao-rotas-plano-execucao.md, Fase 0: "em aberto,
# precisa de fonte ou de ser proposta H2G2"). Mesmos números de exemplo
# do próprio plano: abaixo de 30% vira atenção, abaixo de 15% vira perigo.
LIMITE_MARGEM_ATENCAO_PCT = 30.0
LIMITE_MARGEM_PERIGO_PCT = 15.0


def _contras_margem_de_volta(rota: dict) -> list[dict]:
    """Fase 3 (margem_minima/pior_trecho_emergencia, route_planning.py)
    ainda não entrava nesta avaliação -- rotulo/contras consideravam só
    terreno e alertas, nunca "você tem oxigênio pra voltar?". Um ponto
    sem volta calculável é tratado como perigo mesmo que o resto da
    rota pareça segura (mesmo critério de route_planning.custo_ate_base:
    nunca ignorado em silêncio)."""
    pior = rota.get("pior_trecho_emergencia")
    if pior is not None and pior["tempo_volta_min"] is None:
        return [{
            "texto": "há um ponto nesta rota de onde a volta até a base não é calculável",
            "fonte": FONTE_MARGEM,
        }]

    margem = rota.get("margem_minima")
    if margem is None:
        return []
    pct = margem["pct"]
    if pct < LIMITE_MARGEM_PERIGO_PCT:
        return [{
            "texto": f"margem de O2 no pior ponto seria de {pct:.0f}% (abaixo do limite de segurança)",
            "fonte": FONTE_MARGEM,
        }]
    if pct < LIMITE_MARGEM_ATENCAO_PCT:
        return [{"texto": f"margem de O2 no pior ponto fica em {pct:.0f}%", "fonte": FONTE_MARGEM}]
    return []


def _rotulo_margem(rota: dict) -> str | None:
    """None quando margem/pior_trecho não dizem nada (sem O2 informado
    e sem mapa de custo de volta) -- não entra na conta, não puxa o
    rótulo pra baixo por falta de dado."""
    pior = rota.get("pior_trecho_emergencia")
    if pior is not None and pior["tempo_volta_min"] is None:
        return "perigo"
    margem = rota.get("margem_minima")
    if margem is None:
        return None
    if margem["pct"] < LIMITE_MARGEM_PERIGO_PCT:
        return "perigo"
    if margem["pct"] < LIMITE_MARGEM_ATENCAO_PCT:
        return "atencao"
    return None


def _metros_por_status(rota: dict) -> dict:
    perfil = rota["perfil_elevacao"]  # perfil[i + 1] fecha o trecho i
    m = {"seguro": 0.0, "atencao": 0.0, "perigo": 0.0}
    for i, t in enumerate(rota["trechos_risco"]):
        m[t.get("status_previsto", t["slope_status"])] += (
            perfil[i + 1]["distancia_acumulada_m"] - perfil[i]["distancia_acumulada_m"])
    return {k: round(v) for k, v in m.items()}


def _avaliar(rota: dict, rotas: list[dict]) -> dict:
    m = _metros_por_status(rota)
    alertas = agrupar_alertas(rota.get("alertas", []))
    rotulo_margem = _rotulo_margem(rota)

    # margem de O2 entra ANTES do terreno: ficar sem oxigênio pra voltar
    # é pelo menos tão urgente quanto um trecho íngreme, e quem lê só o
    # 1º contra (motivo falado) precisa ver isso primeiro quando for o
    # caso -- ver _contras_margem_de_volta.
    contras = list(_contras_margem_de_volta(rota))
    for nivel, texto in (("perigo", "em perigo (20° ou mais, ou chance alta pelo histórico)"),
                         ("atencao", "em atenção (15 a 20°, ou chance média pelo histórico)")):
        if m[nivel]:
            contras.append({"texto": f"{m[nivel]} m {texto}", "fonte": FONTE_TERRENO})
        contras += [{"texto": a["mensagem"], "fonte": a["fonte"]} for a in alertas if a["nivel"] == nivel]

    pros = []
    if rota["distancia_m"] == min(r["distancia_m"] for r in rotas):
        pros.append({"texto": f"a mais curta: {round(rota['distancia_m'])} m", "fonte": FONTE_ROTA})
    if rota["tempo_estimado_min"] == min(r["tempo_estimado_min"] for r in rotas):
        pros.append({"texto": f"a mais rápida: ~{round(rota['tempo_estimado_min'])} min só de ida", "fonte": FONTE_ROTA})
    if not m["perigo"] and not m["atencao"]:
        pros.append({"texto": "nenhum trecho acima de 15° no mapa nem com chance alta no histórico", "fonte": FONTE_TERRENO})
    if rota.get("alvo_cientifico"):
        pros.append({"texto": f"passa pelo alvo {rota['alvo_cientifico']['nome']}", "fonte": "alvos científicos (F04)"})
    margem = rota.get("margem_minima")
    if margem is not None and rotulo_margem is None:
        pros.append({"texto": f"margem de O2 de {margem['pct']:.0f}% no pior ponto da rota", "fonte": FONTE_MARGEM})

    niveis = {a["nivel"] for a in alertas}
    rotulo_terreno = "perigo" if m["perigo"] or "perigo" in niveis else "atencao" if m["atencao"] or "atencao" in niveis else "ok"
    rotulo = max((rotulo_terreno, rotulo_margem or "ok"), key=ORDEM.index)
    # margem_pct entra no desempate logo depois do rótulo (maior margem
    # primeiro); None (sem O2 informado) fica neutro, não derruba nem
    # favorece a rota só por falta de dado.
    margem_pct_ordenacao = -(margem["pct"]) if margem is not None else 0.0
    return {
        "rotulo": rotulo,
        "pros": pros,
        "contras": contras,
        "_chave": (ORDEM.index(rotulo), margem_pct_ordenacao, m["perigo"], m["atencao"], rota["tempo_estimado_min"]),
    }


def sugerir(rotas: list[dict], agora: datetime | None = None) -> dict:
    """Escreve rota["sugestao"] em cada variante e devolve a sugestão geral (campo novo do /api/route)."""
    for r in rotas:
        r["sugestao"] = _avaliar(r, rotas)
    ordem = sorted(rotas, key=lambda r: r["sugestao"].pop("_chave"))
    melhor = ordem[0]
    s, nome = melhor["sugestao"], NOME.get(melhor["tipo"], melhor["tipo"])
    if s["rotulo"] == "ok":
        motivo = f"Sugiro a rota {nome}: " + (s["pros"][0]["texto"] if s["pros"] else "sem trecho de risco") + "."
    else:
        todas = all(r["sugestao"]["rotulo"] == "perigo" for r in rotas)
        motivo = (f"Todas as {len(rotas)} rotas têm perigo; a {nome} tem menos. " if todas and len(rotas) > 1 else
                  f"Sugiro a rota {nome}, a de menor risco entre as {len(rotas)}. ") + f"Atenção: {s['contras'][0]['texto']}"
    ls_agora = ls(agora or datetime.now(timezone.utc))
    poeira = (f"Temporada de tempestades de poeira (Ls {ls_agora:.0f}°): vale para todas as rotas."
              if LS_POEIRA[0] <= ls_agora < LS_POEIRA[1] else None)
    return {"sugerida": melhor["tipo"], "ordem": [r["tipo"] for r in ordem], "motivo": motivo, "aviso_poeira": poeira,
            "resumo": [{"tipo": r["tipo"], "rotulo": r["sugestao"]["rotulo"],
                        "por_que": (r["sugestao"]["contras"] or r["sugestao"]["pros"] or [{"texto": "sem dado"}])[0]["texto"]}
                       for r in ordem],
            "metodo": "regra fixa H2G2: pior trecho previsto + alertas do agente; empate pelo tempo",
            "quem_decide": "astronauta"}
