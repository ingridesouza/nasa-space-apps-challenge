"""Testes do agente local (feature 08, fase 2).

Rodar: make test   (ou: cd api && python test_agente.py)
Os testes com modelo só rodam se o Ollama estiver no ar com o modelo de agente.MODELO (gemma4:e2b)."""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agente
from fastapi import HTTPException
from main import Pergunta, ask

SOL_4309 = (-4.78679146, 137.4076395)  # perigo: histórico 22,4° e 2.029 m da base


class Req:  # get_point só usa base_url para montar link de foto
    base_url = "http://local/"


def test_contexto_alertas_primeiro_e_sem_dado():
    ponto = {"point": {"lat": 0, "lon": 0}, "raster_values": {"slope_deg": None}, "science_target": None,
             "nearby_photos": [], "alertas": [{"nivel": "perigo", "mensagem": "X", "fonte": "F"}]}
    txt = agente.contexto_em_texto(agente.montar_contexto(ponto, None))
    assert txt.splitlines()[1] == "- PERIGO: X (fonte: F)"
    assert "INCLINAÇÃO DO MAPA: sem dado" in txt and "CONDIÇÕES AMBIENTAIS: sem dado" in txt


def test_ollama_fora_do_ar_da_503_com_alertas():
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, "http://127.0.0.1:9"
    try:
        ask(Pergunta(pergunta="oi", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
        raise AssertionError("devia falhar")
    except HTTPException as e:
        assert e.status_code == 503 and e.detail["alertas"]
    finally:
        agente.OLLAMA_URL = url


def test_socorro_responde_por_regra_sem_modelo():
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, "http://127.0.0.1:9"  # prova que o modelo não é chamado
    try:
        r = ask(Pergunta(pergunta="Ei guia, acabei caindo num buraco, e agora?", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
    finally:
        agente.OLLAMA_URL = url
    assert r["socorro"] and r["resposta"].startswith("Pare") and "A base fica a" in r["resposta"], r
    assert not agente.SOCORRO.search("a temperatura cai à noite?")
    assert agente.SOCORRO.search("apareceu um gás muito tóxico")  # frase da demo (test_voz.py)
    assert agente.SOCORRO.search("acho que tem gás tóxico entrando") and agente.SOCORRO.search("o traje está vazando")
    assert not agente.SOCORRO.search("que gás tem na atmosfera?")
    # inglês: a voz manda o idioma do Whisper, e o procedimento sai nele
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, "http://127.0.0.1:9"
    try:
        r = ask(Pergunta(pergunta="I fell and my suit is leaking", idioma="en", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
    finally:
        agente.OLLAMA_URL = url
    assert r["socorro"] and r["resposta"].startswith("Stop") and "The base is" in r["resposta"], r
    assert agente.SOCORRO.search("I have a toxic gas warning") and agente.SOCORRO.search("mayday")
    assert not agente.SOCORRO.search("the temperature is falling") and not agente.SOCORRO.search("can you help me plan a route?")


def test_idioma_da_pergunta():
    assert agente.idioma_da_pergunta("qual o seu nome?") == "pt"
    assert agente.idioma_da_pergunta("Which route should I take, and why?") == "en"
    assert agente.idioma_da_pergunta("Me leva até o alvo Altadena.") == "pt"
    assert agente.idioma_da_pergunta("Who is the president of Brazil?") == "en"


def test_alvo_citado_por_nome_e_pedido_de_caminho():
    from db import get_connection
    from vector_queries import todos_alvos_cientificos
    from voz import destino_citado, pede_caminho
    alvos = todos_alvos_cientificos(get_connection())
    nome = lambda t: (destino_citado(t, alvos) or {}).get("nome")  # noqa: E731
    assert nome("eu quero estudar o nevado Sarjama e mostra as opções de caminho") == "Nevado Sajama"
    assert nome("o que foi medido no alvo Altadena?") == "Altadena"
    assert nome("onde fica o monte grande e qual rota é mais segura?") == "Monte Grande"
    assert nome("a inclinação aqui é muito grande?") is None  # "grande" sozinho não é o Monte Grande
    assert pede_caminho("como eu chego até ele?") and pede_caminho("how do I get there?")
    assert not pede_caminho("o que foi medido no alvo Altadena?")
    from voz import pede_alvo_perto
    assert pede_alvo_perto("Which science target is closest to me?") and pede_alvo_perto("qual o alvo mais perto daqui?")
    assert not pede_alvo_perto("estou perto da base?")
    assert agente.sem_url("SiO2 41% (https://pds-geosciences.wustl.edu/a/b_p1.csv, sol 4634)") == "SiO2 41% (PDS, sol 4634)"


def test_rota_ate_alvo_citado_sai_por_regra():
    srv, pedidos = _ollama_falso([{"role": "assistant", "content": "Sugiro a mais segura."}])
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    try:
        r = ask(Pergunta(pergunta="quero estudar o nevado Sarjama, como eu chego lá?"), Req())
    finally:
        agente.OLLAMA_URL = url
        srv.shutdown()
    assert r["acoes"] and abs(r["acoes"][0]["lat"] - -4.80801) < 1e-4, r["acoes"]  # Nevado Sajama
    assert "ALVO CITADO: Nevado Sajama" in pedidos[0]["messages"][1]["content"]


def test_replanejar_classifica_e_desvia_do_obstaculo():
    from geo import haversine_m
    from main import get_replanejar
    from replanejar import classificar
    assert classificar("tem uma rocha grande à frente") == "obstaculo" and classificar("There is a big rock ahead") == "obstaculo"
    assert classificar("está muito íngreme") == "ingreme" and classificar("estou cansado") == "cansaco"
    assert classificar("meu oxigênio está baixo") == "oxigenio"
    assert classificar("vem poeira") == "poeira" and classificar("aconteceu um problema") == "outro"
    assert classificar("qual o seu nome?") is None
    assert classificar("apareceu uma cratera enorme na minha frente") == "obstaculo"
    assert classificar("o que tem na cratera Gale?") is None
    assert classificar("qual a melhor hora para fazer essa caminhada?") is None
    meio, monte_grande = (-4.80460, 137.38397), (-4.80784, 137.38104)
    r = get_replanejar(*meio, "tem uma rocha grande à frente", *monte_grande)
    ob = r["obstaculo"]
    for x in r["rotas"]:  # nenhuma opção passa por dentro do obstáculo
        assert min(haversine_m(ob["lat"], ob["lon"], *p) for p in x["pontos"]) > ob["raio_m"], x["tipo"]
    assert r["sugestao"]["sugerida"] in [x["tipo"] for x in r["rotas"]]
    volta = get_replanejar(*meio, "meu oxigênio está baixo")  # sem destino: só voltar à base
    assert volta["rotas"] and all(x["tipo"].startswith("volta") for x in volta["rotas"])
    cansado = get_replanejar(*meio, "estou cansado", *monte_grande)  # cansaço não manda voltar
    assert cansado["rotas"] and all(x["tipo"].startswith("seguir") for x in cansado["rotas"])


def test_problema_relatado_com_rota_aberta_vira_acao_replanejar():
    from main import RotaDaPergunta
    srv, _ = _ollama_falso([{"role": "assistant", "content": "Sugiro o desvio seguro."}])
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    rota = RotaDaPergunta(origin_lat=-4.80460, origin_lon=137.38397, dest_lat=-4.80784, dest_lon=137.38104)
    try:
        r = ask(Pergunta(pergunta="tem uma rocha grande à frente", lat=-4.80784, lon=137.38104,  # lat/lon = destino aberto
                         pos_lat=-4.80460, pos_lon=137.38397, rota=rota), Req())
    finally:
        agente.OLLAMA_URL = url
        srv.shutdown()
    acao = next(a for a in r["acoes"] if a["tipo"] == "replanejar")
    assert r["replanejamento"] and r["resposta"].startswith("Obstáculo à frente") and "quem decide é você" in r["resposta"]
    assert not any(a["tipo"] == "abrir_rota" for a in r["acoes"])  # nada reabre a rota normal por cima das opções
    assert acao["resultado"]["problema"] == "obstaculo" and acao["origem"] == {"lat": -4.80460, "lon": 137.38397}


def test_tira_perigo_que_o_modelo_repetiu():
    a = {"mensagem": "Inclinação de 37,8° neste ponto.", "fonte": "DTM HiRISE (Mars Trek)"}
    r = "PERIGO: Inclinação de 37,8° neste ponto. (fonte: DTM HiRISE (Mars Trek)) Não sei: não tenho esse dado aqui."
    assert agente.tirar_perigo_repetido(r, [a]) == "Não sei: não tenho esse dado aqui."
    assert agente.tirar_perigo_repetido("English: The closest target is Mojo.", []) == "The closest target is Mojo."


def test_sugestao_ordena_por_risco_e_nao_esconde_rota():
    from sugestao_rotas import sugerir
    def rota(tipo, status, tempo):  # noqa: E306
        return {"tipo": tipo, "distancia_m": tempo * 10, "tempo_estimado_min": tempo, "alertas": [],
                "perfil_elevacao": [{"distancia_acumulada_m": 0}, {"distancia_acumulada_m": 50}],
                "trechos_risco": [{"slope_status": status, "status_previsto": status, "slope_deg": 1}]}
    rotas = [rota("mais_rapida", "perigo", 5), rota("mais_segura", "seguro", 9)]
    sg = sugerir(rotas)
    assert sg["sugerida"] == "mais_segura" and sg["ordem"] == ["mais_segura", "mais_rapida"]
    assert rotas[0]["sugestao"]["rotulo"] == "perigo" and "50 m em perigo" in rotas[0]["sugestao"]["contras"][0]["texto"]
    assert "_chave" not in rotas[0]["sugestao"] and len(sg["resumo"]) == 2


def test_sugestao_com_rota_real():
    from main import BASE_LAT_LON, get_route
    r = get_route(BASE_LAT_LON[0], BASE_LAT_LON[1], *SOL_4309, [], [])
    assert r["sugestao"]["sugerida"] in [x["tipo"] for x in r["rotas"]]
    assert all(x["sugestao"]["rotulo"] in ("ok", "atencao", "perigo") for x in r["rotas"])
    print(r["sugestao"]["motivo"], r["sugestao"]["resumo"])


def _ollama_falso(respostas):
    """Servidor local que devolve `respostas` em ordem (dict = 200 com message; str = erro 400) e guarda os pedidos."""
    import http.server, threading  # noqa: E401
    pedidos = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            pedidos.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            r = respostas.pop(0)
            corpo = json.dumps({"error": r} if isinstance(r, str) else {"message": r}).encode()
            self.send_response(400 if isinstance(r, str) else 200)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, pedidos


def test_ferramenta_planejar_rota_abre_rota_e_fala_perigo():
    chamada = {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "planejar_rota", "arguments": {"dest_lat": SOL_4309[0], "dest_lon": SOL_4309[1]}}}]}
    srv, pedidos = _ollama_falso([chamada, {"role": "assistant", "content": "Sugiro a rota indicada."}])
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    agente._ollama_sem_ferramentas = False
    try:
        r = ask(Pergunta(pergunta="route to sol 4309?"), Req())
    finally:
        agente.OLLAMA_URL = url
        srv.shutdown()
    assert pedidos[0]["tools"] and pedidos[1]["messages"][-1]["role"] == "tool"
    assert "SUGESTÃO DO SISTEMA" in pedidos[1]["messages"][-1]["content"]
    assert r["acoes"] == [{"tipo": "abrir_rota", "lat": SOL_4309[0], "lon": SOL_4309[1]}]
    assert r["resposta"].startswith("Danger:"), r["resposta"]  # perigo da rota planejada vem por regra, no idioma da pergunta


def test_ollama_sem_tools_cai_no_modo_contexto():
    srv, pedidos = _ollama_falso(["registry.ollama.ai/library/gemma4:e4b does not support tools",
                                  {"role": "assistant", "content": "ok"}])
    url, agente.OLLAMA_URL = agente.OLLAMA_URL, f"http://127.0.0.1:{srv.server_port}"
    agente._ollama_sem_ferramentas = False
    try:
        assert agente.perguntar("oi", agente.montar_contexto(
            {"point": {"lat": 0, "lon": 0}, "raster_values": {}, "science_target": None, "nearby_photos": [], "alertas": []}, None),
            executar=lambda n, a: "") == "ok"
    finally:
        agente.OLLAMA_URL = url
        srv.shutdown()
    assert "tools" in pedidos[0] and "tools" not in pedidos[1] and agente._ollama_sem_ferramentas
    agente._ollama_sem_ferramentas = False


def ollama_no_ar():
    try:
        urllib.request.urlopen(f"{agente.OLLAMA_URL}/api/tags", timeout=2)
        return True
    except OSError:
        return False


def test_modelo_fora_do_contexto_e_perigo_primeiro():
    if not ollama_no_ar():
        print("pulado: Ollama fora do ar")
        return
    r = ask(Pergunta(pergunta="Qual o nome do presidente do Brasil?", lat=SOL_4309[0], lon=SOL_4309[1]), Req())
    assert r["resposta"].startswith("Perigo: O Curiosity mediu 22,4°"), r["resposta"]
    assert "Não sei" in r["resposta"], r["resposta"]

def test_terreno_da_rota_metros_por_chance_e_pior_trecho():
    from previsao_rota import terreno
    rota = {"perfil_elevacao": [{"distancia_acumulada_m": d} for d in (0, 10, 30, 60)],
            "trechos_risco": [{"chance_pct": 0, "slope_deg": 3}, {"chance_pct": 27, "slope_deg": 12},
                              {"chance_pct": None, "slope_deg": 30}]}
    t = terreno(rota)
    assert t["metros_por_chance"] == {"baixa": 10, "media": 20, "alta": 0, "sem_dado": 30}
    assert t["pior_trecho"]["distancia_m"] == 10 and t["pior_trecho"]["chance_pct"] == 27


def test_texto_da_rota_agrupa_mesma_parada_e_diz_sem_previsao():
    a = lambda d, m: {"nivel": "atencao", "mensagem": m, "fonte": "F", "distancia_m": d}  # noqa: E731
    pr = {"tipo": "mais_segura", "sol_eva": 5000, "distancia_m": 100, "tempo_estimado_min": 3,
          "terreno": {"metros_por_chance": {"baixa": 100, "media": 0, "alta": 0, "sem_dado": 0},
                      "pior_trecho": None, "limite_deg": 15},
          "alertas": [a(0, "mediu 17,5° a 56 m daqui (sol 4634)."), a(40, "mediu 17,5° a 75 m daqui (sol 4634).")],
          "clima": None, "dose": None}
    txt = agente.rota_em_texto(pr)
    assert sum("sol 4634" in linha for linha in txt) == 1 and "sem dado" in txt[-1]
    assert agente.rota_em_texto({"erro": "x"}) == ["PREVISÃO DA ROTA: sem previsão (x)"]
    assert agente.rota_em_texto(None) == []


def test_ferramenta_prever_rota_com_dado_real():
    from main import BASE_LAT_LON, get_previsao_rota
    pr = get_previsao_rota(BASE_LAT_LON[0], BASE_LAT_LON[1], *SOL_4309, sol=5000)
    assert pr["sol_eva"] == 5000 and pr["tempo_estimado_min"] > 0
    assert pr["terreno"]["pior_trecho"] and any(a["nivel"] == "perigo" for a in pr["alertas"])
    assert pr["clima"]["janela_eva"] and pr["dose"]["valor_ugy"] > 0


if __name__ == "__main__":
    for nome, t in list(globals().items()):
        if nome.startswith("test_"):
            t()
            print(f"ok  {nome}")
