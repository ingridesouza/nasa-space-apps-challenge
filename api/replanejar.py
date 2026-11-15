"""F02 + F08: replanejar no meio da caminhada a partir de um problema relatado.

O astronauta diz o que aconteceu ("tem uma rocha à frente", "está íngreme", "estou
cansado", "vem poeira"); a regra classifica o problema e monta opções novas a partir
do ponto marcado (não há GPS). As opções são calculadas pelo mesmo A* (route_planning),
nunca pelo modelo; a sugestão é só a ordem, quem escolhe é o astronauta."""

from geo import haversine_m
from voz import _parecida, palavras

# ordem = prioridade: voltar (poeira, cansaço) vem antes de desviar
PROBLEMAS = {
    "poeira": {"poeira", "tempestade", "vento", "dust", "storm", "wind"},
    "cansaco": {"cansado", "cansada", "exausto", "exausta", "oxigenio", "o2", "folego", "tired", "exhausted", "oxygen"},
    "obstaculo": {"obstaculo", "buraco", "rocha", "pedra", "areia", "duna", "fenda", "vala", "bloqueado", "bloqueada",
                  "obstacle", "hole", "rock", "boulder", "sand", "blocked", "crack"},
    "ingreme": {"ingreme", "inclinado", "inclinada", "subida", "ladeira", "steep", "slope", "uphill"},
}
GERAL = {"problema", "problemas", "dificuldade", "problem", "trouble"}
TEXTO = {
    "poeira": "Poeira chegando: opções de volta à base.",
    "cansaco": "Cansaço ou oxigênio: opções de volta à base.",
    "obstaculo": "Obstáculo à frente: desvio de {raio} m ao redor do ponto a {frente} m daqui, ou volta à base.",
    "ingreme": "Terreno mais íngreme que o previsto: seguir pelo mais suave ou voltar à base.",
    "outro": "Problema relatado: seguir pela mais segura ou voltar à base.",
}
# (id, título, vai para "destino" ou "base", tipo do A*, desvia do obstáculo?)
OPCOES = {
    "poeira": [("volta_curta", "volta curta à base", "base", "mais_rapida", False),
               ("volta_segura", "volta segura à base", "base", "mais_segura", False)],
    "cansaco": [("volta_curta", "volta curta à base", "base", "mais_rapida", False),
                ("volta_suave", "volta suave à base", "base", "mais_suave", False)],
    "obstaculo": [("desvio_seguro", "desvio seguro", "destino", "mais_segura", True),
                  ("desvio_rapido", "desvio rápido", "destino", "mais_rapida", True),
                  ("volta_curta", "volta curta à base", "base", "mais_rapida", True)],
    "ingreme": [("seguir_suave", "seguir pelo terreno suave", "destino", "mais_suave", False),
                ("volta_suave", "volta suave à base", "base", "mais_suave", False)],
    "outro": [("seguir_seguro", "seguir pela mais segura", "destino", "mais_segura", False),
              ("volta_curta", "volta curta à base", "base", "mais_rapida", False)],
}
OBSTACULO_A_FRENTE_M = 25  # shortcut: "à frente" sem distância falada vira 25 m na rota; ler "a 10 metros" depois
RAIO_OBSTACULO_M = 20  # ~3 pixels do DTM (5,9 m): o desvio passa longe o bastante para se ver
JA_NA_BASE_M = 30  # mais perto que isso, "voltar à base" não é opção


def classificar(texto: str) -> str | None:
    """Tipo do problema relatado, ou None se a fala não relata problema."""
    p = palavras(texto)
    for tipo, chaves in PROBLEMAS.items():
        if any(_parecida(w, chaves) for w in p):
            return tipo
    return "outro" if any(w in GERAL for w in p) else None


def ponto_a_frente(pontos: list, lat: float, lon: float, metros: float) -> tuple[float, float]:
    """Ponto da rota `metros` adiante do ponto da rota mais perto de (lat, lon)."""
    i = min(range(len(pontos)), key=lambda k: haversine_m(lat, lon, *pontos[k]))
    andado = 0.0
    while i + 1 < len(pontos) and andado < metros:
        andado += haversine_m(*pontos[i], *pontos[i + 1])
        i += 1
    return tuple(pontos[i])


def opcoes(problema: str, origem: tuple, destino: tuple | None, base: tuple, rota_atual: list | None, planejar) -> dict:
    """planejar(destino, tipo, evitar) -> uma rota do A* (ou exceção). Devolve {rotas, obstaculo, texto}."""
    obstaculo = None
    if problema == "obstaculo" and rota_atual:
        obstaculo = (*ponto_a_frente(rota_atual, *origem, OBSTACULO_A_FRENTE_M), RAIO_OBSTACULO_M)
    longe_da_base = haversine_m(*origem, *base) > JA_NA_BASE_M
    rotas, erros = [], []
    for id_, titulo, para, tipo, desvia in OPCOES[problema]:
        alvo = destino if para == "destino" else (base if longe_da_base else None)
        if alvo is None:
            continue
        try:
            r = planejar(alvo, tipo, [obstaculo] if desvia and obstaculo else None)
        except Exception as e:  # noqa: BLE001 -- sem caminho para uma opção não derruba as outras
            erros.append(f"{titulo}: {getattr(e, 'detail', e)}")
            continue
        igual = next((x for x in rotas if x["pontos"] == r["pontos"]), None)
        if igual:  # o A* deu o mesmo caminho para os dois pesos: uma opção só, com os dois nomes
            igual["titulo"] += f" (= {titulo})"
            continue
        rotas.append({**r, "tipo": id_, "titulo": titulo})
    texto = TEXTO[problema].format(raio=RAIO_OBSTACULO_M, frente=OBSTACULO_A_FRENTE_M)
    return {"rotas": rotas, "erros": erros, "texto": texto,
            "obstaculo": obstaculo and {"lat": obstaculo[0], "lon": obstaculo[1], "raio_m": obstaculo[2]}}
