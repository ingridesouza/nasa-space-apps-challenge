"""Feature 11, visor por voz: testes com assert (python test_comandos.py), sem o modelo."""

import json
import re
from pathlib import Path

from comandos import CATALOGO, MODAIS, interpretar, tem_pista, validar


def cmd(texto, abertos=None, foco=None):
    return interpretar(texto, abertos, foco, usar_modelo=False)["comando"]


def ok(texto, alvo, acao, args=None, **kw):
    c = cmd(texto, **kw)
    assert c and (c["alvo"], c["acao"]) == (alvo, acao), (texto, c)
    if args is not None:
        assert c["args"] == args, (texto, c)


# catálogo: ids únicos e na sequência m-A, m-B…; todo bloco tem nome falado e ação
ids = [m["id"] for m in CATALOGO["modais"] if m["seletor"]]  # "sis" não tem bloco na tela
assert ids == [f"m-{chr(65 + i)}" for i in range(len(ids))], ids
assert all(m["falado"] and m["acoes"] for m in CATALOGO["modais"])

# o front registra handler para toda ação do catálogo (mesmo arquivo nos dois lados)
app = (Path(__file__).resolve().parent.parent / "web" / "app.js").read_text(encoding="utf-8")
for m in CATALOGO["modais"]:
    bloco = re.search(rf"registrar\('{m['id']}', \{{(.*?)\n\}}\)", app, re.S)
    assert bloco, f"sem registrar('{m['id']}')"
    for a in m["acoes"]:
        assert re.search(rf"\b{a}:", bloco.group(1)), f"{m['id']}.{a} sem handler em app.js"

# por nome do bloco, alfabeto fonético ou sinônimo
ok("Guia, diminuir o zoom do mapa", "m-A", "afastar", {"niveis": 1})
ok("Alfa, aproxima dois", "m-A", "aproximar", {"niveis": 2})
ok("move o mapa para o norte", "m-A", "mover", {"direcao": "norte"})
ok("liga o relevo", "m-B", "ligar", {"camada": "relevo_hillshade"})
ok("Bravo opacidade risco 40", "m-B", "opacidade", {"camada": "risco_previsto", "valor": 40})
ok("Charlie, rota mais rápida", "m-C", "tipo", {"tipo": "mais_rapida"})
ok("charlie próximo sol", "m-C", "sol", {"delta": "1"})  # frase maior vence "próximo"
ok("Delta gira para a esquerda 90 graus", "m-D", "girar", {"direcao": "esquerda", "graus": 90})
ok("Eco abre a segunda", "m-E", "abrir", {"n": 2})
ok("fecha o visor", "m-H", "fechar")
ok("India latitude menos 4,808 longitude 137,381", "m-I", "definir", {"lat": -4.808, "lon": 137.381})
ok("Alfa, qual a elevação aqui", "m-A", "ler")
ok("Charlie, adicionar parada", "m-C", "parada")
ok("Charlie, remover parada dois", "m-C", "remover_parada", {"n": 2})
ok("Charlie, sol 1200", "m-C", "ir_sol", {"sol": 1200})
ok("Charlie, oxigênio 350", "m-C", "o2", {"litros": 350})
ok("Charlie, registrar medição sol 4600 menos 80 menos 10 870", "m-C", "medicao",
   {"sol": 4600.0, "minima": -80.0, "maxima": -10.0, "pressao": 870.0})  # dose é opcional
ok("Charlie, apagar medição", "m-C", "apagar_medicao")
ok("Delta, olhar para o ponto", "m-D", "centralizar")
ok("recolher imagens", "m-E", "recolher")
ok("Golf, repete", "m-G", "ouvir")
ok("Juliet, ler", "m-J", "ler")
ok("silêncio", "sis", "silencio")
ok("fechar tudo", "sis", "voltar")
ok("desligar microfone", "sis", "microfone")
ok("ajuda", "sis", "ajuda")

# "aproxima" não pode virar "próxima página" (casamento exato vem antes do aproximado)
ok("Delta aproxima", "m-D", "aproximar")

# sem bloco citado: decide pelos blocos abertos, depois pelo foco; empate pergunta
ok("próxima", "m-E", "proxima", abertos=["m-E"])
ok("próxima", "m-F", "proxima", abertos=["m-E", "m-F"], foco="m-F")
r = interpretar("próxima página", ["m-E", "m-F"], None, usar_modelo=False)
assert r["comando"] is None and r["ambiguo"] == ["m-E", "m-F"] and "Qual bloco" in r["fala"], r

# ação destrutiva pede confirmação
r = interpretar("cancelar rota", usar_modelo=False)
assert r["comando"]["acao"] == "cancelar" and r["confirmar"] and r["fala"].endswith("Confirma?"), r

# argumento obrigatório ausente: não chuta, pergunta
r = interpretar("liga a camada", usar_modelo=False)
assert r["comando"] is None and "falta camada" in r["fala"], r
assert cmd("India definir destino") is None  # sem coordenada dita, nada de coordenada inventada

r = interpretar("Charlie, registrar medição sol 4600 menos 80 menos 10 870", usar_modelo=False)
assert "sol 4600, minima -80, maxima -10, pressao 870. Confirma?" in r["fala"], r["fala"]

# pergunta não é comando
assert interpretar("qual a temperatura hoje?", usar_modelo=False) == {"comando": None, "origem": None, "confirmar": False, "fala": None}
assert not tem_pista("qual a temperatura hoje?")
assert tem_pista("tira esse mapa da frente")

# validar barra o que o modelo inventar
for ruim in ({"alvo": "m-Z", "acao": "abrir"}, {"alvo": "m-A", "acao": "voar"},
             {"alvo": "m-B", "acao": "ligar", "args": {"camada": "lava"}},
             {"alvo": "m-A", "acao": "aproximar", "args": {"niveis": 40}},
             {"alvo": "m-I", "acao": "definir", "args": {"lat": -4.8}}):
    try:
        validar(ruim)
        raise AssertionError(f"passou: {ruim}")
    except ValueError:
        pass
assert validar({"alvo": "m-A", "acao": "aproximar"}) == {"alvo": "m-A", "acao": "aproximar", "args": {"niveis": 1}}
assert json.dumps(MODAIS["m-A"])  # catálogo serializável (vai inteiro ao front)

print("ok: comandos")
