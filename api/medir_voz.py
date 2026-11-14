"""Fase 0 da voz (F08): grava as frases de teste e mede cada modelo Whisper.

  python medir_voz.py --gravar               # grava as frases no microfone da demo
  python medir_voz.py large-v3 turbo small   # tempo e erro por modelo

Gravações em data/local/voz_teste/ (fora do git: é a voz de alguém)."""

import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

from voz import TAXA_HZ, interpretar, palavras, transcrever

PASTA = Path(__file__).resolve().parent.parent / "data" / "local" / "voz_teste"
SEGUNDOS = 6
# Destinos com os nomes reais do banco, para mostrar a ação que cada frase dispararia.
DESTINOS = [{"nome": "a base", "lat": 0, "lon": 0, "chaves": ["base", "habitat"], "base": True}] + [
    {"nome": n, "lat": 0, "lon": 0} for n in ("Cristas de boxwork", "Altadena", "Totoral / Sillar")]
FRASES = [
    "Guia, qual a melhor rota até a base?",
    "Guia, rota até Altadena.",
    "Guia, me leva até as cristas de boxwork.",
    "Guia, quero voltar para a base.",
    "Guia, rota até Totoral.",
    "Guia, posso subir aqui com segurança?",
    "Guia, quanta radiação vou receber hoje?",
    "Guia, tem alvo científico perto daqui?",
    "Sim.",
    "Não, cancela.",
]


def erro_palavras(esperado: str, obtido: str) -> tuple[int, int]:
    """(erros, palavras esperadas) pela distância de edição entre palavras."""
    a, b = palavras(esperado), palavras(obtido)
    linha = list(range(len(b) + 1))
    for i, pa in enumerate(a, 1):
        anterior, linha[0] = linha[0], i
        for j, pb in enumerate(b, 1):
            anterior, linha[j] = linha[j], min(linha[j] + 1, linha[j - 1] + 1, anterior + (pa != pb))
    return linha[-1], len(a)


def gravar():
    PASTA.mkdir(parents=True, exist_ok=True)
    for i, frase in enumerate(FRASES, 1):
        input(f"\n[{i}/{len(FRASES)}] Enter e diga em até {SEGUNDOS}s:  {frase}")
        subprocess.run(["arecord", "-q", "-f", "S16_LE", "-r", str(TAXA_HZ), "-c", "1",
                        "-d", str(SEGUNDOS), str(PASTA / f"{i:02d}.wav")], check=True)
    (PASTA / "esperado.txt").write_text("\n".join(FRASES) + "\n", encoding="utf-8")
    print(f"\nGravado em {PASTA}")


def ler_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (TAXA_HZ, 1, 2), \
            f"{caminho.name}: precisa de 16 kHz mono 16 bits (use --gravar)"
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def medir(modelos: list[str]):
    esperados = (PASTA / "esperado.txt").read_text(encoding="utf-8").splitlines()
    audios = [ler_wav(PASTA / f"{i:02d}.wav") for i in range(1, len(esperados) + 1)]
    resumo = []
    for modelo in modelos:
        t0 = time.perf_counter()
        transcrever(audios[0], modelo)  # aquece: carga do modelo não conta por frase
        carga = time.perf_counter() - t0
        erros = total = 0
        tempos = []
        print(f"\n== {modelo} (carga + 1ª frase {carga:.1f}s)")
        for esperado, audio in zip(esperados, audios):
            t = time.perf_counter()
            r = transcrever(audio, modelo)
            tempos.append(time.perf_counter() - t)
            e, n = erro_palavras(esperado, r["texto"] or "")
            erros, total = erros + e, total + n
            acao = interpretar(r["texto"], DESTINOS, exigir_ativacao=False) if r["texto"] else {"intencao": "não entendi"}
            alvo = acao.get("destino") and acao["destino"]["nome"].split("—")[0].strip()
            print(f"  {tempos[-1]:4.1f}s  {e} erro(s)  [{r['confianca']}]  {r['texto']!r}  → {acao['intencao']} {alvo or ''}")
        resumo.append((modelo, 100 * erros / total, sum(tempos) / len(tempos), max(tempos)))
    print("\nmodelo        erro%   média_s  pior_s")
    for m, wer, media, pior in resumo:
        print(f"{m:12s} {wer:6.1f}   {media:6.1f}  {pior:6.1f}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--gravar"]:
        gravar()
    else:
        medir(sys.argv[1:] or ["large-v3", "turbo"])
