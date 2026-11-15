"""Compara modelos do agente (F08) nas perguntas da demo: ferramenta certa, tempo e RAM.

  python medir_agente.py gemma4:e2b granite4 phi4-mini

Usa o mesmo /api/ask da demo. O socorro não entra: é regra, não passa pelo modelo.
Descarrega cada modelo antes do próximo (dois juntos na RAM travaram a máquina)."""

import json
import sys
import time
import urllib.request

import agente
from main import BASE_LAT_LON, Pergunta, RotaDaPergunta, ask, get_route

DESTINO = (-4.80311, 137.39202)  # o da demo do print
ROTA = RotaDaPergunta(origin_lat=BASE_LAT_LON[0], origin_lon=BASE_LAT_LON[1], dest_lat=DESTINO[0], dest_lon=DESTINO[1])
SUGERIDA = get_route(*BASE_LAT_LON, *DESTINO, [], [])["sugestao"]["sugerida"]
PALAVRAS_TIPO = {"mais_segura": ("safe", "segur"), "mais_rapida": ("fast", "quick", "rápid"), "mais_ciencia": ("scien", "ciênc")}
NAO_SEI = ("não sei", "don't know", "do not know", "no data", "não tenho", "not in", "cannot", "can't")


class Req:
    base_url = "http://local/"


# (pergunta, rota aberta, o que conta como acerto, descrição)
CASOS = [
    ("Take me to the nearest science target.", None,
     lambda r: r["acoes"] and "alvos científicos (F04)" in r["fontes"], "lista alvos e planeja rota"),
    ("Me leva até o alvo Altadena.", None, lambda r: bool(r["acoes"]), "planeja rota até alvo pelo nome"),
    ("Which route should I take, and why?", ROTA,
     lambda r: any(p in r["resposta"].lower() for p in PALAVRAS_TIPO[SUGERIDA]), f"repete a sugerida ({SUGERIDA})"),
    ("What is the terrain slope at lat -4.787, lon 137.408?", None,
     lambda r: "ponto consultado (DTM HiRISE)" in r["fontes"], "consulta o ponto"),
    ("Who is the president of Brazil?", None,
     lambda r: not r["acoes"] and any(p in r["resposta"].lower() for p in NAO_SEI), "não sabe, sem ferramenta"),
    ("qual o seu nome?", None, lambda r: " o " in f" {r['resposta'].lower()} " or "sou" in r["resposta"].lower(),
     "pergunta em português, responde em português"),
    ("Is it safe to walk here today?", None,
     lambda r: " the " in f" {r['resposta'].lower()} " and " não " not in f" {r['resposta'].lower()} ", "responde em inglês"),
]


def ollama(rota: str, corpo: dict | None = None) -> dict:
    req = urllib.request.Request(f"{agente.OLLAMA_URL}{rota}", data=corpo and json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def ram_livre_gb() -> float:
    linha = next(x for x in open("/proc/meminfo") if x.startswith("MemAvailable"))
    return int(linha.split()[1]) / 2**20


def medir(modelo: str) -> None:
    carregado = any(m["name"].startswith(modelo) for m in ollama("/api/ps")["models"])
    if not carregado and ram_livre_gb() < 4:  # e2b ~2-3 GB; o vigia do make cobre o resto
        print(f"{modelo}: pulado, só {ram_livre_gb():.1f} GB livres (feche programas)")
        return
    agente.MODELO, agente._ollama_sem_ferramentas = modelo, False
    acertos, ram = 0, None
    print(f"\n== {modelo}")
    for pergunta, rota, ok, descr in CASOS:
        t = time.time()
        try:
            r = ask(Pergunta(pergunta=pergunta, rota=rota), Req())
        except Exception as e:  # noqa: BLE001 -- modelo fora do ar conta como erro, segue para o próximo
            r = {"resposta": f"ERRO {getattr(e, 'detail', e)}", "acoes": [], "fontes": []}
        acerto = bool(ok(r))
        acertos += acerto
        ram = ram or next((m["size"] / 2**30 for m in ollama("/api/ps")["models"] if m["name"].startswith(modelo)), None)
        print(f"{'ok ' if acerto else 'X  '} {time.time() - t:5.1f}s  {descr}: {r['resposta'][:140]!r}")
    print(f"-> {modelo}: {acertos}/{len(CASOS)} acertos, RAM do modelo {ram and f'{ram:.1f} GB'}"
          + ("" if not agente._ollama_sem_ferramentas else " (SEM tool calling)"))
    ollama("/api/generate", {"model": modelo, "keep_alive": 0})  # descarrega antes do próximo


if __name__ == "__main__":
    for m in sys.argv[1:] or ["gemma4:e2b"]:
        medir(m)
