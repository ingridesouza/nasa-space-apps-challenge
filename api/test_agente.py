"""Testes do agente local (feature 08, fase 2).

Rodar: make test   (ou: cd api && python test_agente.py)
Os testes com modelo só rodam se o Ollama estiver no ar com o gemma3:4b."""

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


if __name__ == "__main__":
    for nome, t in list(globals().items()):
        if nome.startswith("test_"):
            t()
            print(f"ok  {nome}")
