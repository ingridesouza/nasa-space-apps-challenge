"""Feature 08, voz: testes com assert (python test_voz.py), sem o modelo."""

from medir_voz import erro_palavras
from voz import escolher_idioma, interpretar, palavras

assert palavras("Marvin, rota até Altadena!") == ["marvin", "rota", "ate", "altadena"]
assert erro_palavras("Marvin, rota até a base.", "marvin rota ate a base") == (0, 5)
assert erro_palavras("rota até a base", "rota até base") == (1, 4)       # palavra faltando
assert erro_palavras("rota até a base", "nota até a casa") == (2, 4)     # duas trocadas
assert erro_palavras("sim", "") == (1, 1)                                # nada ouvido

assert escolher_idioma({"pt": 0.134, "en": 0.217, "es": 0.141}) == "pt"  # indeciso: português
assert escolher_idioma({"pt": 0.05, "en": 0.9}) == "en"                  # inglês claro
assert escolher_idioma({}) == "pt"

# nomes reais dos alvos do banco (science_targets)
BASE = {"nome": "a base", "lat": -4.8069, "lon": 137.3798, "chaves": {"base", "habitat"}, "base": True}
PONTO = {"nome": "o ponto marcado", "lat": -4.80, "lon": 137.38, "chaves": {"ponto", "marcado"}}
DESTINOS = [BASE, PONTO] + [{"nome": n, "lat": 0, "lon": 0} for n in (
    "Cristas de boxwork — cimentação por sulfato", "Altadena — furo de perfuração #43",
    "Totoral / Sillar — crista vs. depressão")]


def ok(texto, intencao, destino=None, **kw):
    r = interpretar(texto, DESTINOS, **kw)
    assert (r["intencao"], r["destino"] and r["destino"]["nome"]) == (intencao, destino), (texto, r)
    return r


ok("Marvin, qual a melhor rota até a base?", "rota", "a base")
ok("Marvin, hota até Altadena.", "rota", "Altadena — furo de perfuração #43")    # erro típico do Whisper
ok("Marvin, me leva até as cristas de boxwork.", "rota", "Cristas de boxwork — cimentação por sulfato")
ok("Marvim, rota até Totoral", "rota", "Totoral / Sillar — crista vs. depressão")  # ativação mal ouvida
ok("Marvin, quero voltar.", "rota", "a base")                                    # volta sem destino = base
ok("Marvin, rota até o ponto marcado", "rota", "o ponto marcado")
ok("Marvin, rota até Marte Central", "pergunta")                                 # destino fora da lista: ao modelo
# fala livre: relato vai inteiro ao modelo, mesmo citando "rota" ou "voltar"
r = ok("Olá marvin, to no meio de uma rota e apareceu um gás muito tóxico", "pergunta")
assert r["ativado"] and r["pergunta"] == "to no meio de uma rota e apareceu um gás muito tóxico", r
ok("Ei, marvin, o traje está perdendo pressão e eu acho que preciso voltar logo", "pergunta")
assert ok("Oi, ô marvin, rota até Altadena", "rota", "Altadena — furo de perfuração #43")["ativado"]
ok("Eu falei com o marvin ontem", "nenhuma")                                     # "marvin" depois da 3ª palavra
ok("Qual a melhor rota até a base?", "nenhuma")                                # sem "Marvin": ignorado
ok("Sim.", "sim", exigir_ativacao=False)                                       # janela de confirmação
ok("Não, cancela.", "nao", exigir_ativacao=False)
ok("C", "sim", exigir_ativacao=False)                                          # "Sim." pelo small
ok("NÃO, CANCELO!", "nao", exigir_ativacao=False)
ok("Obrigado por assistir.", "pergunta", exigir_ativacao=False)               # alucinação comum: não confirma
assert ok("Marvin, posso subir aqui com segurança?", "pergunta")["pergunta"] == "posso subir aqui com segurança?"
assert ok("Marvin quanta radiação vou receber hoje", "pergunta")["pergunta"] == "quanta radiação vou receber hoje"
assert ok("Ei Marvin, rota até a base", "rota", "a base")["ativado"]
assert ok("A marvin, posso subir aqui?", "pergunta")["pergunta"] == "posso subir aqui?"
print("test_voz: ok")
