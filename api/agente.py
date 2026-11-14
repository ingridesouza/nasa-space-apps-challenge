"""Feature 08, fase 2 -- agente local: responde perguntas só com o
contexto do ponto (o mesmo JSON do /api/point + condições REMS/RAD).

Sem tool-calling, embeddings nem SDK: o contexto cabe em ~2 KB e vai
inteiro no prompt. O modelo roda no próprio hardware (Ollama), sem rede
externa. Os alertas vêm das regras de alertas.py, nunca do modelo."""

import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("H2G2_OLLAMA_URL", "http://127.0.0.1:11434")
MODELO = os.environ.get("H2G2_MODELO", "gemma3:4b")  # Gemma 3 4B (Google)
TIMEOUT_S = 120  # CPU (i5-8600) pode levar dezenas de segundos na primeira chamada

INSTRUCOES = """Você é o H2G2, assistente de um astronauta na cratera Gale, em Marte.
Responda em português, em no máximo 3 frases curtas, para ser lida em voz alta.
Use SOMENTE os dados do CONTEXTO abaixo. Cite a fonte e o sol quando houver.
Se o contexto não tiver o dado pedido, responda exatamente: "Não sei: não tenho esse dado aqui."
Nunca invente número, nome ou posição. Nunca diga que um lugar é seguro só porque não há alerta.
Se houver alerta PERIGO, comece a resposta por ele. Nunca contradiga, crie ou cancele um alerta."""


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
    return "\n".join(linhas)


def perguntar(pergunta: str, ctx: dict) -> str:
    corpo = json.dumps({
        "model": MODELO,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": f"CONTEXTO:\n{contexto_em_texto(ctx)}\n\nPERGUNTA: {pergunta}"},
        ],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corpo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)["message"]["content"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        raise AgenteIndisponivel(f"agente local indisponível ({MODELO} em {OLLAMA_URL}): {e}") from e
