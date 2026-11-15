"""Feature 08, voz: transcrição local (faster-whisper) do áudio que o
navegador já manda bruto em 16 kHz mono float32.

Não decodifica arquivo: o PyAV deste ambiente (19) é incompatível com o
faster-whisper 1.2.1, e o WebM do MediaRecorder era o caminho que falhava.
Plano: docs/feature-08-voz-plano-execucao.md."""

import math
import os
import re
import threading
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

import numpy as np

PASTA_MODELOS = Path(__file__).resolve().parent.parent / "data" / "local" / "whisper"
# large-v3: 8,7 s por frase nesta CPU e ouviu "rota"; o turbo (6,8 s) ouviu "hota" -- a CPU
# pesa no codificador, igual nos dois. O "sim/não" da confirmação vai no small (rápido).
MODELO = os.environ.get("H2G2_WHISPER", "large-v3")
MODELO_CONFIRMACAO = os.environ.get("H2G2_WHISPER_CONFIRMACAO", "small")
# "auto": o small detecta o idioma (rápido) e o grande transcreve nele. Fixo num idioma, o Whisper
# TRADUZ a fala dos outros. Detectar com o próprio grande custava 16,9 s em vez de 8,7 s.
IDIOMA = os.environ.get("H2G2_IDIOMA", "auto")
PADRAO = "en"  # idioma quando a detecção fica indecisa
TAXA_HZ = 16000
# Palavras que o Whisper deve favorecer: ativação, domínio e destinos aceitos por voz.
# "EVA" saiu: puxava "Ei guia" para "EVA". A ativação entra inteira, não só "Guia".
# Outro idioma usa o inglês: os nomes próprios (Altadena, boxwork…) são o que mais importa.
VOCABULARIO = {
    "en": ("Hey guide, route, base, habitat, boxwork, Curiosity, Altadena, Totoral, Sillar, "
           "Gale crater, sol, slope, radiation, science target, safety, climb, "
           "emergency, toxic gas, leak, oxygen, suit, pressure, dust"),
    "pt": ("Ei guia, rota, base, habitat, boxwork, Curiosity, Altadena, Totoral, Sillar, "
           "cratera Gale, sol, inclinação, radiação, alvo científico, segurança, subir, "
           "emergência, gás tóxico, vazamento, oxigênio, traje, pressão, poeira"),
}
# Falas fixas da voz, no idioma de quem falou (outro idioma: inglês).
FALAS = {
    "en": {"nao_entendi": "I didn't understand.", "confirma": "Got it: route to {}. Confirm?",
           "marque": "Mark where you are on the map so I can plan the route.", "base": "the base", "ponto": "the marked point"},
    "pt": {"nao_entendi": "Não entendi.", "confirma": "Entendi: rota até {}. Confirma?",
           "marque": "Marque no mapa onde você está para eu calcular a rota.", "base": "a base", "ponto": "o ponto marcado"},
}


def falas(idioma: str | None) -> dict:
    return FALAS.get(idioma, FALAS[PADRAO])
MAX_SEM_FALA = 0.6    # no_speech_prob acima disso: trecho é silêncio/ruído
# avg_logprob abaixo disso: o modelo está chutando. -0,6 = confiança 0,55; na 1ª gravação real
# (14/11, microfone de notebook) as frases inventadas vieram com 0,50-0,55 e as boas com 0,61+.
# shortcut: calibrado com 10 frases de uma pessoa, recalibrar com make voz-medir e mais vozes.
MIN_LOGPROB = -0.6


def escolher_idioma(probs: dict[str, float]) -> str:
    """O idioma que dominar (> 50%); indeciso, inglês. Em frase curta a detecção
    fica indecisa ("Guia, rota até Altadena" deu en 0,22 x pt 0,13)."""
    melhor = max(probs, key=probs.get, default=PADRAO)
    return melhor if probs.get(melhor, 0) > 0.5 else PADRAO


@lru_cache(maxsize=2)
def _carregar(nome: str):
    from faster_whisper import WhisperModel  # import tardio: a API sobe sem o modelo
    return WhisperModel(nome, device="cpu", compute_type="int8",
                        download_root=str(PASTA_MODELOS), local_files_only=True)


_trava_carga = threading.Lock()


def _modelo(nome: str):
    # sem a trava, o pré-carregamento e a 1ª fala carregavam duas cópias do large-v3 (estourou a RAM)
    with _trava_carga:
        return _carregar(nome)


def transcrever(audio: np.ndarray, modelo: str = MODELO, idioma: str | None = None) -> dict:
    """audio: float32 mono 16 kHz. Devolve {texto, idioma, confianca};
    texto None quando não há fala clara -- nunca uma frase inventada."""
    m = _modelo(modelo)
    idioma = idioma or (escolher_idioma(dict(_modelo(MODELO_CONFIRMACAO).detect_language(audio, vad_filter=True)[2]))
              if IDIOMA == "auto" else IDIOMA)
    segmentos, _ = m.transcribe(
        audio, language=idioma, beam_size=5, hotwords=VOCABULARIO.get(idioma, VOCABULARIO[PADRAO]),
        condition_on_previous_text=False, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 600, "speech_pad_ms": 400})
    bons = [s for s in segmentos if s.no_speech_prob < MAX_SEM_FALA and s.avg_logprob > MIN_LOGPROB]
    texto = " ".join(s.text.strip() for s in bons).strip()
    if not texto:
        return {"texto": None, "idioma": idioma, "confianca": None}
    confianca = math.exp(sum(s.avg_logprob for s in bons) / len(bons))
    return {"texto": texto, "idioma": idioma, "confianca": round(confianca, 2)}


# ---- fase 2: entender o comando (regras, sem modelo: 5 destinos cabem numa lista) ----

# Comandos em inglês e português (pt e en juntos: a pessoa pode misturar). Outro idioma vai ao modelo.
ATIVACAO = {"guia", "gia", "quia", "guias", "guide", "guides"}  # grafias curtas que o Whisper produz
ATE_PALAVRA_ATIVACAO = 3  # "Olá guia, ..." / "Hey, guide, ..." / "Oi, ô guia, ..."
# Comando de rota é curto ("Guia, me leva até as cristas de boxwork" = 7). Relato longo
# ("to no meio de uma rota e apareceu um gás") vai inteiro ao modelo, mesmo citando "rota".
MAX_PALAVRAS_COMANDO = 8
ROTA = {"rota", "caminho", "leva", "levar", "ir", "vai", "va", "route", "take", "go", "lead", "navigate"}
VOLTA = {"voltar", "volta", "retornar", "back", "return"}  # "home" não: "hole" casa com ele no aproximado
# "si"/"c"/"sin": como o Whisper small escreve um "sim" curto; só vale na janela do "Confirma?"
SIM = {"sim", "si", "c", "sin", "confirmo", "confirma", "pode", "isso", "positivo",
       "yes", "yeah", "yep", "ok", "okay", "sure", "confirm", "confirmed", "affirmative", "correct"}
NAO = {"nao", "cancela", "cancelar", "negativo", "no", "pare", "nope", "cancel", "negative", "stop", "abort"}
_PALAVRAS_SOLTAS = {"de", "da", "do", "por", "vs", "furo", "crista", "depressao", "perfuracao", "cimentacao", "sulfato"}


def palavras(texto: str) -> list[str]:
    """Minúsculas, sem acento e sem pontuação: só o que a pessoa disse."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", sem_acento.lower())


def _parecida(palavra: str, conjunto) -> bool:
    """Tolera o erro típico do Whisper ("hota" por "rota") sem casar palavra curta à toa."""
    return palavra in conjunto or (len(palavra) >= 4 and bool(get_close_matches(palavra, conjunto, n=1, cutoff=0.75)))


def chaves_do_destino(nome: str) -> set[str]:
    """'Cristas de boxwork — cimentação por sulfato' -> {cristas, boxwork}: o nome antes do travessão."""
    return {p for p in palavras(nome.split("—")[0]) if len(p) >= 4 and p not in _PALAVRAS_SOLTAS}


CAMINHO = ROTA | {"chegar", "chego", "chega", "caminhos", "opcoes", "get", "path", "way"}


def destino_citado(texto: str, destinos: list[dict]) -> dict | None:
    """Destino citado numa frase de qualquer tamanho (pergunta ao agente): o de mais palavras do nome.
    Com 2+ palavras no nome, exige 2 ("grande" sozinho não é o Monte Grande)."""
    p = palavras(texto)
    melhor, n = None, 0
    for d in destinos:
        chaves = d.get("chaves") or chaves_do_destino(d["nome"])
        acertos = sum(any(_parecida(w, {c}) for w in p) for c in chaves)
        if acertos >= min(2, len(chaves)) and acertos > n:
            melhor, n = d, acertos
    return melhor


def pede_alvo_perto(texto: str) -> bool:
    """"qual o alvo mais perto?" / "closest science target": o mais próximo sai por conta, não pelo modelo."""
    p = set(palavras(texto))
    return bool(p & {"perto", "proximo", "proxima", "closest", "nearest", "near"}) and bool(
        p & {"alvo", "alvos", "target", "targets", "objetivo", "ciencia", "cientifico", "science"})


def pede_caminho(texto: str) -> bool:
    return any(_parecida(w, CAMINHO) for w in palavras(texto))


def interpretar(texto: str, destinos: list[dict], exigir_ativacao: bool = True) -> dict:
    """destinos: [{nome, lat, lon, chaves?, base?}] (base, alvos do banco, ponto marcado).
    Devolve {ativado, intencao: rota|sim|nao|pergunta|nenhuma, destino, pergunta}.
    Nunca devolve coordenada fora da lista: destino desconhecido vira None."""
    p = palavras(texto)
    # grafias curtas só exatas: no aproximado, "qual" casaria com "quia"
    i = next((i for i, w in enumerate(p[:ATE_PALAVRA_ATIVACAO]) if w in ATIVACAO or _parecida(w, {"guia", "guide"})), None)
    ativado = i is not None
    resto = p[i + 1:] if ativado else p
    # o que vem depois do "Guia", com acento e pontuação originais (mesma divisão em palavras)
    tokens = list(re.finditer(r"[^\W_]+", texto))
    pergunta = texto[tokens[i].end():].lstrip(" ,.!?;:") if ativado and i < len(tokens) else texto.strip()
    base = {"ativado": ativado, "destino": None, "pergunta": pergunta}
    if exigir_ativacao and not ativado:
        return {**base, "intencao": "nenhuma"}
    if not resto:
        return {**base, "intencao": "nenhuma"}
    if len(resto) <= 3 and any(_parecida(w, SIM) for w in resto):
        return {**base, "intencao": "sim"}
    if len(resto) <= 3 and any(_parecida(w, NAO) for w in resto):
        return {**base, "intencao": "nao"}
    volta = any(_parecida(w, VOLTA) for w in resto)
    if len(resto) > MAX_PALAVRAS_COMANDO or not (volta or any(_parecida(w, ROTA) for w in resto)):
        return {**base, "intencao": "pergunta"}
    for d in destinos:
        chaves = d.get("chaves") or chaves_do_destino(d["nome"])
        if any(_parecida(w, chaves) for w in resto):
            return {**base, "intencao": "rota", "destino": d}
    base_ = next((d for d in destinos if d.get("base")), None)
    if volta and base_:
        return {**base, "intencao": "rota", "destino": base_}
    return {**base, "intencao": "pergunta"}  # "rota" sem destino conhecido: o modelo responde
