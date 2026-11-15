"""Feature 08, fase 2 -- agente local: responde perguntas só com o
contexto do ponto (o mesmo JSON do /api/point + condições REMS/RAD).

Sem tool-calling, embeddings nem SDK: o contexto cabe em ~2 KB e vai
inteiro no prompt. O modelo roda no próprio hardware (Ollama), sem rede
externa. Os alertas vêm das regras de alertas.py, nunca do modelo."""

import json
import os
import re
import urllib.error
import urllib.request

from geo import bearing, compass, haversine_m
from previsao_rota import FAIXAS_CHANCE

OLLAMA_URL = os.environ.get("H2G2_OLLAMA_URL", "http://127.0.0.1:11434")
# gemma4:e4b tem tool calling nativo, mas precisa de Ollama novo (0.12.11 do Fedora nem carrega o modelo):
# H2G2_MODELO=gemma4:e4b. O gemma3:4b não tem ferramentas: perguntar() cai sozinho no modo só contexto.
MODELO = os.environ.get("H2G2_MODELO", "gemma3:4b")
TIMEOUT_S = 120  # CPU (i5-8600) pode levar dezenas de segundos na primeira chamada

INSTRUCOES = """Você é o H2G2, assistente de um astronauta na cratera Gale, em Marte.
Responda em português, em no máximo 3 frases curtas, para ser lida em voz alta.
Use SOMENTE os dados do CONTEXTO abaixo. Cite a fonte e o sol quando houver.
Se o contexto não tiver o dado pedido, responda exatamente: "Não sei: não tenho esse dado aqui."
Nunca invente número, nome ou posição. Nunca diga que um lugar é seguro só porque não há alerta.
Não repita os alertas PERIGO: o sistema já os fala antes da sua resposta. Nunca contradiga, crie ou cancele um alerta.
Se houver PREVISÃO DA ROTA, use-a para perguntas sobre a rota: diga que é estimativa pelo histórico
e dê o porquê (trecho, chance, distância do início). Se perguntarem qual rota pegar, repita a SUGESTÃO DO SISTEMA
com o porquê, sem trocar a ordem. Nunca escolha nem aprove a rota por conta própria: quem decide é o astronauta.
PONTO é onde o astronauta está agora; a PREVISÃO DA ROTA vale para o caminho inteiro. Não misture os dois na mesma frase."""


# Pedido de socorro não passa pelo modelo: resposta por regra, na hora, só com dado do mapa.
# por extenso: a resposta é falada ("O" vira "ó" na voz)
RUMO_FALADO = {"N": "norte", "NE": "nordeste", "L": "leste", "SE": "sudeste", "S": "sul", "SO": "sudoeste", "O": "oeste", "NO": "noroeste"}
# "cai" sem acento fica de fora ("a temperatura cai?").
SOCORRO = re.compile(r"\b(caí|caindo|cair|socorro|buraco|pres[oa]|machuc\w*|emerg[eê]ncia|acidente|escorreg\w*|atolad[oa])\b", re.I)


def resposta_de_socorro(ponto: dict, base: tuple[float, float]) -> str:
    """Procedimento fixo + posição, chão e caminho de volta. shortcut: procedimento escrito pelo time,
    sem fonte NASA citada; trocar pelo checklist de EVA quando houver."""
    lat, lon = ponto["point"]["lat"], ponto["point"]["lon"]
    r = ponto["raster_values"]
    frases = ["Pare e não se mova até checar o traje.", f"Você está em lat {lat:.5f}, lon {lon:.5f}."]
    if r.get("slope_deg") is None:
        frases.append("Não tenho a inclinação deste local.")
    else:
        frases.append(f"O chão aqui tem {r['slope_deg']:.0f}° pelo mapa"
                      + (": acima de 20°, não tente subir sozinho." if r.get("slope_status") == "perigo" else "."))
    frases += [a["mensagem"] for a in agrupar_alertas(ponto["alertas"]) if a["nivel"] == "perigo"]
    frases.append(f"A base fica a {round(haversine_m(lat, lon, *base))} m, direção {RUMO_FALADO[compass(bearing(lat, lon, *base))]}.")
    frases.append("Avise a base agora.")
    return " ".join(frases)


def tirar_perigo_repetido(resposta: str, perigos: list[dict]) -> str:
    """O sistema já fala o perigo antes da resposta; o modelo de 4B às vezes o copia mesmo proibido."""
    for a in perigos:
        resposta = re.sub(rf"(perigo:\s*)?{re.escape(a['mensagem'])}(\s*\(fonte: {re.escape(a['fonte'])}\))?\s*",
                          "", resposta, flags=re.I)
    return resposta.strip()


INSTRUCOES_FERRAMENTAS = """
Você tem ferramentas para buscar dado que NÃO está no CONTEXTO: outro ponto, os alvos científicos, uma rota até um destino.
Para ir a um alvo: chame listar_alvos_cientificos e depois planejar_rota com a lat/lon exata do alvo da lista.
Nunca invente coordenada. Ao explicar uma rota, repita a sugestão do sistema com o porquê; quem decide é o astronauta."""

FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "listar_alvos_cientificos",
        "description": "Alvos científicos reais medidos pelo Curiosity perto do boxwork: nome, lat, lon e o que foi medido.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "consultar_ponto",
        "description": "Inclinação, elevação, alertas e alvo científico de um ponto do mapa.",
        "parameters": {"type": "object", "required": ["lat", "lon"], "properties": {
            "lat": {"type": "number", "description": "latitude em graus"},
            "lon": {"type": "number", "description": "longitude leste em graus"}}}}},
    {"type": "function", "function": {
        "name": "planejar_rota",
        "description": "Calcula as rotas da posição atual do astronauta até o destino e devolve a ordem sugerida com o porquê. A rota abre no mapa.",
        "parameters": {"type": "object", "required": ["dest_lat", "dest_lon"], "properties": {
            "dest_lat": {"type": "number", "description": "latitude do destino"},
            "dest_lon": {"type": "number", "description": "longitude leste do destino"}}}}},
]
MAX_RODADAS = 3  # sem limite, um modelo pequeno pode chamar ferramenta em loop
_ollama_sem_ferramentas = False  # Ollama antigo recusa `tools` (ex.: 0.12.11 com gemma4): cai no modo só contexto


class AgenteIndisponivel(Exception):
    """Ollama fora do ar ou sem o modelo: os alertas continuam valendo."""


def montar_contexto(ponto: dict, condicoes: dict | None) -> dict:
    """Recorta o /api/point ao que o modelo precisa (fotos viram contagem)."""
    return {
        "ponto": ponto["point"],
        "terreno": {k: v for k, v in ponto["raster_values"].items() if k != "fontes"},
        "alvo_cientifico": ponto["science_target"],
        "fotos_proximas": len(ponto["nearby_photos"]),
        "alertas": ponto["alertas"],
        "previsao_inclinacao": ponto.get("previsao_inclinacao"),
        "condicoes_ambientais": condicoes,  # None = sem dado em cache para o sol
    }


def fontes_do_contexto(ctx: dict) -> list[str]:
    fontes = [a["fonte"] for a in ctx["alertas"]]
    if ctx["terreno"].get("slope_deg") is not None:
        fontes.append("DTM HiRISE (inclinação)")
    if (ctx.get("previsao_rota") or {}).get("terreno"):
        fontes.append("previsão da rota (tilt do Curiosity × DTM, REMS, RAD)")
    if ctx["condicoes_ambientais"]:
        fontes.append(f"REMS/RAD sol {ctx['condicoes_ambientais']['sol']}")
    return list(dict.fromkeys(fontes))  # sem repetição, na ordem


def contexto_em_texto(ctx: dict) -> str:
    """Texto curto, alertas primeiro: modelo de 3B se perde em JSON aninhado."""
    linhas = ["ALERTAS (regras fixas, valem acima de tudo):"]
    linhas += [f"- {a['nivel'].upper()}: {a['mensagem']} (fonte: {a['fonte']})" for a in ctx["alertas"]] or ["- nenhum (isso NÃO quer dizer seguro)"]
    t = ctx["terreno"]
    linhas.append(f"PONTO: lat {ctx['ponto']['lat']}, lon {ctx['ponto']['lon']}")
    linhas.append(f"INCLINAÇÃO DO MAPA: {t.get('slope_deg')}° ({t.get('slope_status')}) · elevação {t.get('elevacao_m')} m (fonte: DTM HiRISE)"
                  if t.get("slope_deg") is not None else "INCLINAÇÃO DO MAPA: sem dado")
    pi = ctx.get("previsao_inclinacao")
    if pi:
        linhas.append(f"CHANCE DE O TERRENO REAL PASSAR DE {pi['limite_deg']}° (ESTIMADA pelo histórico do rover): "
                      f"{pi['chance_pct']}% ({pi['acima']} de {pi['n']} paradas com o mapa em {pi['faixa_mapa']})")
    alvo = ctx["alvo_cientifico"]
    linhas.append(f"ALVO CIENTÍFICO PRÓXIMO: {json.dumps(alvo, ensure_ascii=False)}" if alvo else "ALVO CIENTÍFICO PRÓXIMO: nenhum")
    linhas.append(f"FOTOS DO ROVER POR PERTO: {ctx['fotos_proximas']}")
    c = ctx["condicoes_ambientais"]
    if c:
        r, d = c.get("rems") or {}, c.get("rad") or {}
        linhas.append(f"CONDIÇÕES DO SOL {c['sol']} (fonte: REMS e RAD do Curiosity, sol {c['sol']}): "
                      f"temperatura mínima {r.get('temp_min_c')} °C, máxima {r.get('temp_max_c')} °C, "
                      f"pressão {r.get('pressao_pa')} Pa, UV pico {r.get('uv_pico')}, umidade {r.get('umidade_pct')} %, "
                      f"radiação {d.get('dose_estimada_ugy_por_dia')} µGy por dia")
        linhas += [f"- {a['nivel'].upper()}: {a['mensagem']} (fonte: {a['fonte']})" for a in c.get("alertas", [])]
        pv = c.get("previsao_hoje")
        if pv and pv["temp_min_c"] and pv["temp_max_c"]:
            linhas.append(f"PREVISÃO PARA HOJE, SOL {pv['sol']} (ESTIMADA, não medida; {pv['metodo']}): "
                          f"mínima {pv['temp_min_c']['valor']} °C, máxima {pv['temp_max_c']['valor']} °C"
                          + (f", pressão {pv['pressao_pa']['valor']} Pa" if pv["pressao_pa"] else "")
                          + (f", chão ao meio-dia {pv['solo_meio_dia_c']['valor']} °C" if pv.get("solo_meio_dia_c") else "")
                          + (f", radiação {pv['dose_ugy_dia']['valor']} µGy por dia" if pv.get("dose_ugy_dia") else ""))
    else:
        linhas.append("CONDIÇÕES AMBIENTAIS: sem dado")
    linhas += rota_em_texto(ctx.get("previsao_rota"))
    return "\n".join(linhas)


def _v(campo: dict | None, unidade: str) -> str:
    return "sem dado" if not campo else f"{campo['valor']} {unidade}"


def agrupar_alertas(alertas: list[dict]) -> list[dict]:
    """A mesma parada do rover (ou o limite da base) volta a cada amostra do caminho: fica a 1ª."""
    vistos = {}
    for a in alertas:
        vistos.setdefault((a["nivel"], re.sub(r"[\d.,]+ m (daqui|da base)", "", a["mensagem"])), a)
    return list(vistos.values())


FAIXA_TEXTO = {"alta": "chance alta (≥50%)", "media": "chance média (20–49%)", "baixa": "chance baixa (<20%)", "sem_dado": "sem dado"}


def rota_em_texto(pr: dict | None) -> list[str]:
    """Seção da ferramenta "prever rota" (previsao_rota.py). Nada quando não há rota aberta."""
    if pr is None:
        return []
    if "erro" in pr:
        return [f"PREVISÃO DA ROTA: sem previsão ({pr['erro']})"]
    out = []
    sg = pr.get("sugestao")
    if sg:  # as outras variantes também: sem isso o modelo não sabe comparar
        out.append(f"SUGESTÃO DO SISTEMA (regra fixa, não sua; quem decide é o astronauta): {sg['motivo']}")
        out += [f"- rota {r['tipo']}: {r['rotulo']} ({r['por_que']})" for r in sg["resumo"]]
        if sg["aviso_poeira"]:
            out.append(f"- {sg['aviso_poeira']} (fonte: Mars24 + MCS/MRO, NASA)")
    t = pr["terreno"]
    m = t["metros_por_chance"]
    out += [f"PREVISÃO DA ROTA ABERTA {pr['tipo']} PARA O SOL {pr['sol_eva']} (ESTIMADA pelo histórico da NASA, não medida):",
           f"- distância {pr['distancia_m']} m, tempo estimado {pr['tempo_estimado_min']} min",
           f"- terreno (chance de o chão real passar de {t['limite_deg']}°, pelo tilt do Curiosity): "
           + ", ".join(f"{v} m com {FAIXA_TEXTO[k]}" for k, v in m.items() if v)]  # faixa zerada confunde o modelo
    if t["pior_trecho"]:
        pt = t["pior_trecho"]
        faixa = next(FAIXA_TEXTO[n] for n, lo, hi in FAIXAS_CHANCE if lo <= pt["chance_pct"] < hi)
        out.append(f"- trecho de maior chance, a {pt['distancia_m']} m do início: mapa {pt['slope_mapa_deg']}°, "
                   f"{pt['chance_pct']}% ({faixa})")
    out += [f"- {a['nivel'].upper()} a partir de {round(a['distancia_m'])} m do início: {a['mensagem']} (fonte: {a['fonte']})"
            for a in agrupar_alertas(pr["alertas"])]
    c = pr["clima"]
    if c:
        out.append(f"- clima previsto (base sol {c['sol_base']}, {c['horizonte_sols']} sols antes): "
                   f"mínima {_v(c['temp_min_c'], '°C')}, máxima {_v(c['temp_max_c'], '°C')}, pressão {_v(c['pressao_pa'], 'Pa')}")
        j = c["janela_eva"]
        if j:
            out.append(f"- melhor janela para esta EVA: {j['inicio_lmst']}–{j['fim_lmst']} hora solar local, "
                       f"hora mais fria prevista {j['temp_mais_fria_na_janela_c']} °C")
    else:
        out.append("- clima previsto: sem dado")
    d = pr["dose"]
    out.append(f"- radiação prevista na caminhada: {d['valor_ugy']} µGy" + (f" (erro típico ±{d['erro_ugy']})" if d["erro_ugy"] else "")
               if d else "- radiação prevista na caminhada: sem dado")
    return out


def _chat(mensagens: list[dict], com_ferramentas: bool) -> dict:
    corpo = {"model": MODELO, "stream": False,
             "keep_alive": -1,  # o padrão (5 min) descarregava o gemma; recarregar junto do Whisper estourava a RAM
             "options": {"temperature": 0}, "messages": mensagens}
    if com_ferramentas:
        corpo["tools"] = FERRAMENTAS
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)["message"]


def perguntar(pergunta: str, ctx: dict, executar=None) -> str:
    """executar(nome, args) -> texto: roda uma ferramenta (vem de main.py). Sem ele, só o contexto."""
    global _ollama_sem_ferramentas
    com_ferramentas = executar is not None and not _ollama_sem_ferramentas
    mensagens = [{"role": "system", "content": INSTRUCOES + (INSTRUCOES_FERRAMENTAS if com_ferramentas else "")},
                 {"role": "user", "content": f"CONTEXTO:\n{contexto_em_texto(ctx)}\n\nPERGUNTA: {pergunta}"}]
    try:
        for _ in range(MAX_RODADAS):
            try:
                msg = _chat(mensagens, com_ferramentas)
            except urllib.error.HTTPError as e:
                if not (com_ferramentas and "does not support tools" in e.read().decode(errors="replace")):
                    raise
                _ollama_sem_ferramentas, com_ferramentas = True, False
                mensagens[0]["content"] = INSTRUCOES
                msg = _chat(mensagens, False)
            if not msg.get("tool_calls"):
                return msg["content"].strip()
            mensagens.append(msg)
            for c in msg["tool_calls"]:
                f = c["function"]
                mensagens.append({"role": "tool", "tool_name": f["name"], "content": executar(f["name"], f.get("arguments") or {})})
        return _chat(mensagens, False)["content"].strip()  # rodadas esgotadas: responde com o que já buscou
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        raise AgenteIndisponivel(f"agente local indisponível ({MODELO} em {OLLAMA_URL}): {e}") from e
