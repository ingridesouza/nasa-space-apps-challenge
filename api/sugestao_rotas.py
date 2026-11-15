"""Fase 4 do plano de sugestão de rotas (F02+F08) -- ver
docs/feature-02-sugestao-rotas-plano-execucao.md.

O agente ajuda a decidir; ele não decide no lugar do astronauta.
`sugerir()` devolve rótulo, prós/contras (com fonte) e uma ordem
sugerida pra cada rota de /api/route -- NENHUMA rota é escondida ou
removida, a ⛔ aparece igual às outras, só com o aviso.

Campos e critérios definidos agora (por quem trabalha na feature 02)
pra desbloquear o Hugo -- combinado explicitamente: ele valida e ajusta
o que precisar depois que `sugestao_rotas.py`/`agente.py` consumirem de
verdade. Não é contrato fechado."""

# Limite de folga de O2 pra rebaixar o rótulo -- sem fonte oficial (ver
# docs/feature-02-sugestao-rotas-plano-execucao.md, Fase 0: "em aberto,
# precisa de fonte ou de ser proposta H2G2"). Usa os números de exemplo
# do próprio plano: abaixo de 30% vira ⚠️, abaixo de 15% vira ⛔.
LIMITE_MARGEM_ATENCAO_PCT = 30.0
LIMITE_MARGEM_PERIGO_PCT = 15.0


def _contagem_trechos(rota: dict) -> dict:
    cont = {"seguro": 0, "atencao": 0, "perigo": 0}
    for t in rota["trechos_risco"]:
        cont[t["slope_status"]] += 1
    return cont


def _tem_alerta_perigo(rota: dict) -> bool:
    return any(a["nivel"] == "perigo" for a in rota.get("alertas", []))


def _rotulo(rota: dict, contexto: dict | None) -> str:
    contexto = contexto or {}
    cont = _contagem_trechos(rota)
    margem = rota.get("margem_minima")
    margem_pct = margem["pct"] if margem else None

    perigo = (
        cont["perigo"] > 0
        or _tem_alerta_perigo(rota)
        or (margem_pct is not None and margem_pct < LIMITE_MARGEM_PERIGO_PCT)
        or rota.get("pior_trecho_emergencia") is not None and rota["pior_trecho_emergencia"]["tempo_volta_min"] is None
    )
    if perigo:
        return "⛔"

    atencao = (
        cont["atencao"] > 0
        or (margem_pct is not None and margem_pct < LIMITE_MARGEM_ATENCAO_PCT)
        or contexto.get("temporada_poeira") is True
        or contexto.get("fora_da_janela_eva") is True
    )
    if atencao:
        return "⚠️"

    return "✅"


def _pros_contras(rota: dict, rotas: list[dict]) -> list[dict]:
    frases = []
    cont = _contagem_trechos(rota)
    margem = rota.get("margem_minima")

    if margem is not None:
        frases.append({
            "texto": f"No pior ponto, você volta com {margem['pct']:.0f}% de folga de O2.",
            "fonte": "Consumo Apollo/Pandolf, pior caso (api/route_planning.py)",
        })
    else:
        frases.append({
            "texto": "Sem oxigênio informado: não dá pra saber se você volta.",
            "fonte": "CLAUDE.md: sem dado, sem número",
        })

    if cont["atencao"] or cont["perigo"]:
        partes = []
        if cont["atencao"]:
            partes.append(f"{cont['atencao']} trecho(s) entre 15° e 20°")
        if cont["perigo"]:
            partes.append(f"{cont['perigo']} trecho(s) acima de 20°")
        frases.append({
            "texto": f"Passa por {' e '.join(partes)}.",
            "fonte": "DTM HiRISE (Mars Trek)",
        })

    mais_rapida = next((r for r in rotas if r["tipo"] == "mais_rapida"), None)
    if mais_rapida is not None and rota["tipo"] != "mais_rapida":
        diferenca_min = rota["tempo_estimado_min"] - mais_rapida["tempo_estimado_min"]
        if diferenca_min > 0.5:
            frases.append({
                "texto": f"{diferenca_min:.0f} min mais devagar que a rota mais rápida.",
                "fonte": "api/route_planning.py (modelo de velocidade por inclinação)",
            })

    alvo = rota.get("alvo_cientifico")
    if alvo is not None:
        frases.append({
            "texto": f"Passa pelo alvo científico {alvo['nome']}.",
            "fonte": alvo["fonte_url"] or "vector_queries.todos_alvos_cientificos",
        })

    pior = rota.get("pior_trecho_emergencia")
    if pior is not None:
        if pior["tempo_volta_min"] is None:
            frases.append({
                "texto": "Tem um ponto nesta rota de onde a volta até a base não é calculável.",
                "fonte": "api/route_planning.py (custo_ate_base -- Fase 2)",
            })
        else:
            frases.append({
                "texto": f"No pior ponto pra voltar, a caminhada de volta leva {pior['tempo_volta_min']:.0f} min.",
                "fonte": "api/route_planning.py (custo_ate_base -- Fase 2)",
            })

    return frases


def _chave_ordenacao(rota: dict) -> tuple:
    margem = rota.get("margem_minima")
    # Sem O2 informado (margem None), não dá pra comparar margem entre
    # rotas -- entra como "pior possível" nesse critério, igual ao
    # pêso que _rotulo já dá (sem dado não vira "melhor" por omissão).
    margem_pct = margem["pct"] if margem else float("-inf")
    cont = _contagem_trechos(rota)
    trechos_risco_total = cont["atencao"] + cont["perigo"]
    # "por fim ciência" (plano original): único critério onde ciência
    # entra é o de MENOR prioridade, como desempate final -- decisão
    # minha: em empate total nos três critérios acima, prefere a rota
    # que passa por um alvo científico (não o contrário), já que os
    # outros três já garantem segurança/tempo antes de olhar ciência.
    eh_ciencia = 0 if rota.get("alvo_cientifico") is not None else 1
    return (-margem_pct, trechos_risco_total, rota["tempo_estimado_min"], eh_ciencia)


def sugerir(rotas: list[dict], contexto: dict | None = None) -> dict:
    """Função pública da Fase 4. `rotas` é a lista que /api/route já
    monta (mesmos itens, não filtrados/removidos). `contexto` é
    opcional -- hoje só usa `temporada_poeira`/`fora_da_janela_eva` se
    vierem (ninguém ainda calcula isso por rota; ver nota abaixo).

    Nota pro Hugo: o plano original cita "trecho fora da janela de EVA
    (F06 janela_eva)" e "temporada de poeira" como gatilhos de ⚠️.
    `janela_eva` (previsao.py) precisa de hora de início da EVA, que
    `/api/route` não recebe hoje -- não inventei isso. Se/quando a
    orquestração tiver essa hora, passa em `contexto` com essas duas
    chaves (bool) e o rótulo já considera."""
    for rota in rotas:
        rota["rotulo"] = _rotulo(rota, contexto)
        rota["pros_contras"] = _pros_contras(rota, rotas)

    ordenadas = sorted(rotas, key=_chave_ordenacao)
    ordem = [r["tipo"] for r in ordenadas]

    vencedora = ordenadas[0]
    margem = vencedora.get("margem_minima")
    if margem is not None:
        motivo = f"Maior margem de O2 no pior caso ({margem['pct']:.0f}%)."
    else:
        cont = _contagem_trechos(vencedora)
        if cont["atencao"] + cont["perigo"] == 0:
            motivo = "Sem trechos de atenção ou perigo, e é a mais rápida entre as seguras."
        else:
            motivo = "Menos trechos de risco entre as opções disponíveis."

    return {"ordem": ordem, "motivo": motivo, "aviso": "a decisão é sua"}
