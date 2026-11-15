"""Feature 11 -- visor por voz: texto do astronauta -> UM comando do catálogo
web/comandos.json ({alvo, acao, args}), que o front executa.

Duas camadas: regras (instantâneo, cobre o grosso: "Alfa, aproxima dois")
e, só se as regras não entenderem e a frase tiver cara de comando, o Gemma
local com a saída presa a um JSON schema (enum dos ids e ações). Tudo que
sai daqui passa por validar(): ação ou argumento fora do catálogo não chega
à tela. Plano: docs/feature-11-visor-por-voz.md."""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from agente import MODELO, OLLAMA_URL
from voz import _parecida, palavras

CATALOGO_PATH = Path(__file__).resolve().parent.parent / "web" / "comandos.json"
CATALOGO = json.loads(CATALOGO_PATH.read_text(encoding="utf-8"))
MODAIS = {m["id"]: m for m in CATALOGO["modais"]}
TIMEOUT_S = 60
MAX_PALAVRAS_MODELO = 12  # relato longo é pergunta, não comando: vai direto ao agente

# Somem antes de casar as frases: "aumentar o zoom do mapa" casa com "aumentar zoom".
# "um"/"uma" ficam: são número ("aproxima um").
VAZIAS = {"o", "a", "os", "as", "do", "da", "dos", "das", "no", "na", "nos", "nas", "de", "em",
          "para", "pra", "pro", "por", "favor", "me", "e", "ai", "isso", "esse", "essa", "este", "esta",
          "guia", "ei", "oi", "ola", "bloco", "modal", "card", "pagina"}
NUMEROS = {"zero": 0, "um": 1, "uma": 1, "primeira": 1, "primeiro": 1, "dois": 2, "duas": 2, "segunda": 2,
           "segundo": 2, "tres": 3, "terceira": 3, "terceiro": 3, "quatro": 4, "quarta": 4, "cinco": 5,
           "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30,
           "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
           "cem": 100, "cento": 100}


def _limpas(texto: str) -> list[str]:
    return [w for w in palavras(texto) if w not in VAZIAS]


def _casa(frase: list[str], p: list[str], exato: bool) -> bool:
    """Frase contígua dentro de p (palavra a palavra, exata ou parecida)."""
    n = len(frase)
    igual = (lambda a, b: a == b) if exato else (lambda a, b: a == b or _parecida(a, {b}))
    return any(all(igual(p[i + k], frase[k]) for k in range(n)) for i in range(len(p) - n + 1))


def _alvos_citados(p: list[str], exato: bool) -> list[str]:
    citados = []
    for m in CATALOGO["modais"]:
        nomes = [palavras(x) for x in m["falado"] + m["sinonimos"]]
        if any(_casa(n, p, exato) for n in nomes if n):
            citados.append(m["id"])
    return citados


def _melhor_acao(modal: dict, p: list[str], exato: bool) -> tuple[int, str | None]:
    """Maior frase casada vence ("proximo sol" ganha de "proximo")."""
    melhor = (0, None)
    for nome, a in modal["acoes"].items():
        for f in a["falado"]:
            fp = [w for w in palavras(f) if w not in VAZIAS]
            if fp and _casa(fp, p, exato) and len(fp) > melhor[0]:
                melhor = (len(fp), nome)
    return melhor


def _inteiro(texto: str, p: list[str]) -> int | None:
    d = re.search(r"\d+", texto)
    if d:
        return int(d.group())
    total, achou = 0, False
    for w in p:
        if w in NUMEROS:
            total, achou = total + NUMEROS[w], True
        elif achou:
            break  # "quarenta e cinco": o "e" já saiu em VAZIAS
    return total if achou else None


def _numeros(texto: str) -> list[float]:
    """'-4,808 e 137,381' ou 'menos 4.808 ...' -> [-4.808, 137.381]."""
    t = texto.lower()
    return [float(n.replace(",", ".")) * (-1 if s else 1)
            for s, n in re.findall(r"(menos\s+|-)?(\d+(?:[.,]\d+)?)", t)]


def _args(modal: dict, acao: str, texto: str, p: list[str]) -> tuple[dict, str | None]:
    """Extrai os argumentos da ação. Devolve (args, falta) -- falta = nome do arg obrigatório ausente."""
    spec = modal["acoes"][acao].get("args", {})
    args, numeros = {}, _numeros(texto)
    for nome, s in spec.items():
        v = None
        if s["tipo"] == "enum":
            for exato in (True, False):
                v = next((k for k, aliases in s["valores"].items()
                          if any(_casa(palavras(a), p, exato) for a in aliases)), None)
                if v is not None:
                    break
        elif s["tipo"] == "inteiro":
            v = _inteiro(texto, p)
        elif s["tipo"] == "numero":
            v = numeros.pop(0) if numeros else None
        if v is None:
            v = s.get("padrao")
        if v is None and s.get("opcional"):
            continue
        if v is None:
            return args, nome
        args[nome] = v
    return args, None


def validar(cmd: dict) -> dict:
    """Comando -> comando normalizado, ou ValueError. Nada fora do catálogo passa."""
    modal = MODAIS.get(cmd.get("alvo"))
    if not modal:
        raise ValueError(f"bloco desconhecido: {cmd.get('alvo')}")
    acao = modal["acoes"].get(cmd.get("acao"))
    if not acao:
        raise ValueError(f"{modal['id']} não tem a ação {cmd.get('acao')}")
    dados, args = cmd.get("args") or {}, {}
    for nome, s in acao.get("args", {}).items():
        v = dados.get(nome, s.get("padrao"))
        if v is None and s.get("opcional"):
            continue
        if v is None:
            raise ValueError(f"falta {nome}")
        if s["tipo"] == "enum":
            v = str(v)
            if v not in s["valores"]:
                raise ValueError(f"{nome} inválido: {v}")
        else:
            v = int(v) if s["tipo"] == "inteiro" else float(v)
            if not s["min"] <= v <= s["max"]:
                raise ValueError(f"{nome} fora de {s['min']}..{s['max']}: {v}")
        args[nome] = v
    return {"alvo": modal["id"], "acao": cmd["acao"], "args": args}


def _resposta(cmd: dict, origem: str) -> dict:
    modal = MODAIS[cmd["alvo"]]
    acao = modal["acoes"][cmd["acao"]]
    confirmar = bool(acao.get("confirmar"))
    nome = f"{modal['falado'][0].capitalize()}, {modal['nome']}"
    # na confirmação os valores são repetidos: número mal ouvido fica audível antes de valer
    valores = ", ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}" for k, v in cmd["args"].items())
    fala = (f"Entendi: {nome}, {acao['desc']}{f': {valores}' if valores else ''}. Confirma?"
            if confirmar else f"{nome}: {acao['desc']}.")
    return {"comando": cmd, "origem": origem, "confirmar": confirmar, "fala": fala}


def _desempatar(achados: list[tuple[int, str, str]], foco: str | None) -> tuple[str, str] | list[str]:
    topo = max(a[0] for a in achados)
    empatados = [a for a in achados if a[0] == topo]
    if len(empatados) == 1:
        return empatados[0][1], empatados[0][2]
    em_foco = [a for a in empatados if a[1] == foco]
    if em_foco:
        return em_foco[0][1], em_foco[0][2]
    return [a[1] for a in empatados]


def por_regras(texto: str, abertos: list[str] | None = None, foco: str | None = None) -> dict | None:
    """None = as regras não entenderam. Dict com 'comando' None = entendeu, mas falta algo (fala diz o quê)."""
    p = _limpas(texto)
    if not p:
        return None
    for exato in (True, False):  # exato primeiro: no aproximado "aproxima" casaria com "proxima"
        citados = _alvos_citados(p, exato)
        grupos = [citados] if citados else [[i for i in (abertos or []) if i in MODAIS], list(MODAIS)]
        for grupo in grupos:
            achados = [(s, m, a) for m in grupo for s, a in [_melhor_acao(MODAIS[m], p, exato)] if a]
            if not achados:
                continue
            escolha = _desempatar(achados, foco)
            if isinstance(escolha, list):
                nomes = " ou ".join(f"{MODAIS[i]['falado'][0].capitalize()} ({MODAIS[i]['nome']})" for i in escolha)
                return {"comando": None, "origem": "regras", "confirmar": False, "ambiguo": escolha,
                        "fala": f"Qual bloco? {nomes}."}
            modal_id, acao = escolha
            modal = MODAIS[modal_id]
            args, falta = _args(modal, acao, texto, p)
            if falta:
                s = modal["acoes"][acao]["args"][falta]
                opcoes = f" Opções: {', '.join(v[0] for v in s['valores'].values())}." if s["tipo"] == "enum" else ""
                return {"comando": None, "origem": "regras", "confirmar": False, "falta": falta,
                        "fala": f"{modal['nome']}: falta {falta}.{opcoes}"}
            try:
                return _resposta(validar({"alvo": modal_id, "acao": acao, "args": args}), "regras")
            except ValueError as e:
                return {"comando": None, "origem": "regras", "confirmar": False, "fala": f"{modal['nome']}: {e}."}
    return None


def tem_pista(texto: str) -> bool:
    """A frase cita algum bloco ou verbo do catálogo? Sem pista, nem chama o modelo (pergunta vai ao agente)."""
    p = set(_limpas(texto))
    vocab = {w for m in CATALOGO["modais"] for x in m["falado"] + m["sinonimos"] for w in palavras(x)}
    vocab |= {w for m in CATALOGO["modais"] for a in m["acoes"].values() for f in a["falado"] for w in palavras(f)}
    vocab -= VAZIAS
    return bool(p & vocab) and len(p) <= MAX_PALAVRAS_MODELO


def catalogo_em_texto() -> str:
    linhas = []
    for m in CATALOGO["modais"]:
        acoes = []
        for nome, a in m["acoes"].items():
            args = ", ".join(f"{k}: {'|'.join(s['valores']) if s['tipo'] == 'enum' else f'{s['tipo']} {s['min']}..{s['max']}'}"
                             for k, s in a.get("args", {}).items())
            acoes.append(f"{nome}({args}) = {a['desc']}")
        linhas.append(f"{m['id']} {m['nome']} (\"{m['falado'][0]}\"): " + "; ".join(acoes))
    return "\n".join(linhas)


INSTRUCOES = """Você traduz o pedido de um astronauta em UM comando de interface do catálogo abaixo.
Responda só o JSON {"alvo", "acao", "args"}. Use apenas blocos, ações e argumentos do catálogo.
Se o pedido for uma pergunta, um relato ou não couber em nenhuma ação, responda {"alvo": "nenhum", "acao": "nenhuma", "args": {}}.
Nunca invente coordenada: só use números que o astronauta disse."""


def por_modelo(texto: str, abertos: list[str] | None = None) -> dict | None:
    """Gemma local com saída presa a schema. None = não é comando (ou modelo fora do ar)."""
    acoes = sorted({a for m in CATALOGO["modais"] for a in m["acoes"]} | {"nenhuma"})
    schema = {"type": "object", "required": ["alvo", "acao", "args"], "properties": {
        "alvo": {"type": "string", "enum": [*MODAIS, "nenhum"]},
        "acao": {"type": "string", "enum": acoes},
        "args": {"type": "object"}}}
    corpo = json.dumps({
        "model": MODELO, "stream": False, "format": schema, "keep_alive": "30m",
        "options": {"temperature": 0, "num_predict": 80},
        "messages": [
            {"role": "system", "content": f"{INSTRUCOES}\n\nCATÁLOGO:\n{catalogo_em_texto()}"},
            {"role": "user", "content": f"Blocos abertos agora: {', '.join(abertos or []) or 'nenhum'}.\nPEDIDO: {texto}"},
        ],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corpo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            cmd = json.loads(json.load(r)["message"]["content"])
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None  # modelo fora: a frase segue como pergunta, e o agente avisa que está fora
    if cmd.get("alvo") == "nenhum":
        return None
    try:
        return _resposta(validar(cmd), "modelo")
    except ValueError:
        return None


def interpretar(texto: str, abertos: list[str] | None = None, foco: str | None = None,
                usar_modelo: bool = True) -> dict:
    """{comando|None, origem: regras|modelo|None, confirmar, fala}. comando None e fala None = não é comando."""
    r = por_regras(texto, abertos, foco)
    if r is None and usar_modelo and tem_pista(texto):
        r = por_modelo(texto, abertos)
    return r or {"comando": None, "origem": None, "confirmar": False, "fala": None}
