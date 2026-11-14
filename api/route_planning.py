"""A* real sobre a grade do DTM, para a feature 02 (rota inteligente +
indicadores de risco). Ver docs/H2G2_Proposta_Projeto_Planejamento.md,
seção "02", item 2.

Desvio consciente da spec original: ela pede AI4Mars para custo de
areia/rugosidade por pixel, mas a auditoria da feature 01 confirmou que
o AI4Mars não cobre a época/região do boxwork (dataset para em ~sol
2579, campanha do boxwork é sol 4564+). Custo aqui usa só inclinação
real (DTM); o risco de areia nas depressões é um aviso textual fixo
(ver AVISO_AREIA), não um fator numérico -- decisão tomada com o
usuário, não gerar dado por pixel que não existe.

Grade de custo é o DTM de verdade (512x512px, ~5.88m/px -- não é 1m
apesar do nome da camada), carregado inteiro uma vez e cacheado em
memória: amostragem ponto-a-ponto (raster_sampling.py) não serve pra
A*, que precisa do array completo como grafo.

Radiação (RAD, PDS) entra como dose acumulada real na duração da
caminhada (ver `_monta_rota`), não como custo espacial: é uma leitura
por sol do instrumento no rover, não varia por pixel no nosso dado,
então não influencia qual caminho o A* escolhe -- só o quanto essa
caminhada específica expõe o astronauta, de verdade."""

import functools
import heapq
import math
import sqlite3

import numpy as np
import rasterio

from geo import MARS_METERS_PER_DEGREE, haversine_m
from vector_queries import todos_alvos_cientificos

# Mesmos limites da feature 01 (raster_sampling.py) -- um único "limite
# Artemis" em todo o sistema, não dois valores que podem divergir.
LIMITE_SLOPE_ATENCAO_DEG = 15.0
LIMITE_SLOPE_PERIGO_DEG = 20.0

#: peso extra aplicado à faixa "atenção" (15-20°) na variante "mais
#: segura" -- penaliza mais forte que na variante "mais rápida", que só
#: evita o que é realmente impassável (>=20°).
PESO_ATENCAO = {"mais_segura": 6.0, "mais_rapida": 1.8}

#: desvio máximo (em metros) que vale a pena pra passar por um alvo
#: científico -- bbox inteiro tem ~5.6km de lado, então 600m é um
#: desvio real mas não absurdo. Se nenhum dos alvos cabe nisso, a
#: variante "mais_ciencia" nem aparece na resposta (nunca força passar
#: por algo longe demais só pra "ter ciência").
MAIS_CIENCIA_DESVIO_MAX_M = 600.0

#: aviso fixo, citando a fonte real (não é cálculo por pixel -- ver
#: docstring do módulo). Texto é pra exibição direta ao usuário final,
#: por isso não cita caminho de arquivo interno do repositório --
#: isso vai só no comentário do código, não no texto do aviso.
AVISO_AREIA = (
    "Risco de areia fofa nas depressões entre as cristas do boxwork, "
    "relatado pelos operadores do Curiosity (rodas do rover patinaram "
    "nessas áreas). Sem dado de textura por pixel pra essa região "
    "(AI4Mars não cobre a época da campanha) -- trate como aviso "
    "qualitativo do terreno, não como um custo já calculado na rota."
)

# Modelo de O2/tempo: estimativa simples e declarada como tal (a própria
# spec diz "na demo, o nível do traje é simulado", não há telemetria
# real de traje). Velocidade base em terreno plano ~0.8 m/s é a faixa
# citada em estudos de EVA lunar/Apollo pra caminhada cautelosa com
# traje pressurizado; cai conforme a inclinação sobe.
# VELOCIDADE_BASE_M_S: segue sem fonte real confirmada pra caminhada em
# gravidade marciana (ver levantamento em PROXIMOS-PASSOS.md, seção
# "Feature 02 (rota)") -- mantido o valor anterior até existir
# referência melhor.
VELOCIDADE_BASE_M_S = 0.8

# TAXA_O2_L_POR_MIN: taxa metabólica média assumida pra traje de EVA de
# Marte é 350 W (1194 BTU/hr), NASA, "Mars Exploration Portable Life
# Support System Schematic Study: Architecture Down-Selection"
# (ICES-2026-158, NTRS 20260002884) -- valor fixo usado pros estudos de
# esquemático do PLSS em EVAs de 2 a 8h (não é um número "pra 8h",
# é usado pra qualquer duração nessa faixa). Convertido pra L/min de O2
# pela equivalência calórica padrão do O2 (~5 kcal/L = ~20,92 kJ/L):
#   350 W * 60 s/min / 20920 J/L = ~1.00 L/min
# Substitui o valor antigo (0.84), que só tinha um comentário vago
# ("EVA Apollo") sem fonte verificável.
TAXA_O2_L_POR_MIN = 1.00

# Faixa otimista-pessimista do consumo de O2 por trecho (Fase 1, F02+F08).
# A velocidade cai com a inclinação do jeito que já era (ver
# VELOCIDADE_BASE_M_S acima): otimista não reduz, pessimista usa a
# mesma queda que o módulo já tinha antes dessa fase. O quanto o
# CONSUMO de O2 por minuto cresce com a inclinação, porém, não é mais
# um fator arbitrário -- vem da equação de Pandolf (Pandolf, Givoni &
# Goldman, 1977), na forma que a NASA/JSC usa hoje pra estimar custo
# metabólico de caminhada em EVA, inclusive pra Marte:
#   Kim, K.J., Hoffmann, B., Estep, P., Marshall-Goebel, K., Buckland, D.
#   "Improving Metabolic Workload Estimation Accuracy for Planning and
#   Analyzing Exploration Traverses". IEEE EMBC 2024. Financiado pelo
#   NASA Mars Campaign Office. Equação (2) do artigo:
#     MP = 1.5*W + 2.0*(W+L)*(L/W)^2 + eta*(W+L)*(1.5*V^2 + 0.35*V*G)
#   W = massa corporal (kg), L = carga externa/traje (kg), V = velocidade
#   (m/s), G = inclinação em % (100*tan do ângulo do trecho), eta =
#   coeficiente de terreno (adimensional).
# Ver PANDOLF_* logo abaixo pra fonte de cada constante usada na equação.
FATOR_VELOCIDADE_OTIMISTA = 0.0   # otimista: velocidade não cai com a inclinação
FATOR_VELOCIDADE_PESSIMISTA = 0.6  # pessimista: mesma queda de VELOCIDADE_BASE_M_S de antes

# W (massa corporal, 82 kg = 180 lbm) e L (massa do traje+PLSS, 104 kg
# = 230 lbm, meta inicial de orçamento de massa pra traje de Marte):
# NASA, "Mars Suit Mass Considerations" (NTRS 20260003038, ICES 2026).
# eta=1.0 (asfalto/esteira): Soule & Goldman (1972), valor-base da
# tabela de terreno usada com a equação de Pandolf -- não variamos eta
# por pixel, mesma decisão já tomada nesse módulo pra textura do solo
# (ver AVISO_AREIA: risco de areia é aviso qualitativo, não fator
# numérico, por falta de dado de textura por pixel pra essa região).
PANDOLF_MASSA_CORPO_KG = 82.0
PANDOLF_MASSA_TRAJE_KG = 104.0
PANDOLF_COEF_TERRENO = 1.0
PANDOLF_COEF_GRADE = 0.35


def _metabolismo_pandolf_w(velocidade_m_s: float, grade_pct: float) -> float:
    """Taxa metabólica (watts) pela equação de Pandolf -- ver comentário
    de FATOR_VELOCIDADE_PESSIMISTA acima pra fonte da equação e das
    constantes PANDOLF_*.

    Limitação conhecida e aceita: a equação não impõe teto de esforço
    sustentável (VO2 máx). Isso faz o lado "otimista" (velocidade sem
    redução) poder sair, numa rota real de terreno misto, ABAIXO do
    antigo `o2_estimado_l` -- não porque suba menos oxigênio por
    inclinação, mas porque o tempo total de exposição cai mais do que
    a taxa sobe. É um resultado aceito do modelo, não um bug: o
    "pessimista" (usado em toda decisão de segurança) continua
    crescente com a inclinação em qualquer terreno. Corrigir isso
    exigiria um limite de VO2 máx sustentado -- não impomos um valor
    sem fonte; ver docs/fontes-de-dados.md."""
    w, l = PANDOLF_MASSA_CORPO_KG, PANDOLF_MASSA_TRAJE_KG
    return (
        1.5 * w
        + 2.0 * (w + l) * (l / w) ** 2
        + PANDOLF_COEF_TERRENO
        * (w + l)
        * (1.5 * velocidade_m_s**2 + PANDOLF_COEF_GRADE * velocidade_m_s * grade_pct)
    )


# Normaliza a equação de Pandolf pelo caso-base (terreno plano, velocidade
# base) pra converter em RAZÃO sobre TAXA_O2_L_POR_MIN -- assim a chave
# antiga o2_estimado_l (que usa só TAXA_O2_L_POR_MIN) não muda, e a razão
# dá exatamente 1.0 em terreno plano nos dois casos (otimista e
# pessimista têm a mesma velocidade quando a inclinação é zero).
_METABOLISMO_BASE_W = _metabolismo_pandolf_w(VELOCIDADE_BASE_M_S, 0.0)


class SemCaminhoError(Exception):
    pass


class ForaDoGridError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def _load_dtm(local_tile_path: str):
    """Carrega o DTM inteiro uma vez (array + transform), cacheado em
    memória -- diferente de raster_sampling.sample_point, que abre o
    arquivo a cada chamada (ok pra ponto único, ruim pra grid inteiro)."""
    with rasterio.open(local_tile_path) as dataset:
        elevacao = dataset.read(1).astype(np.float64)
        transform = dataset.transform
        bounds = dataset.bounds
        nodata = dataset.nodata
    return elevacao, transform, bounds, nodata


def _dtm_path(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT local_tile_path FROM raster_registry WHERE layer_name = 'dtm_hirise_1m'"
    ).fetchone()
    if row is None:
        raise RuntimeError("Camada dtm_hirise_1m não registrada em raster_registry")
    return row["local_tile_path"]


def _slope_grid_deg(elevacao: np.ndarray, pixel_size_m: float) -> np.ndarray:
    """Inclinação por pixel pra grade inteira (np.gradient vetorizado) --
    mesma física da janela 3x3 usada em raster_sampling.sample_point,
    só que calculada de uma vez pra todos os pixels em vez de ponto a
    ponto."""
    dz_dy, dz_dx = np.gradient(elevacao, pixel_size_m)
    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    return np.degrees(slope_rad)


def _latlon_to_rc(transform, lat: float, lon: float) -> tuple[int, int]:
    col, row = ~transform * (lon, lat)
    return int(round(row)), int(round(col))


def _rc_to_latlon(transform, row: int, col: int) -> tuple[float, float]:
    lon, lat = transform * (col + 0.5, row + 0.5)
    return lat, lon


_VIZINHOS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

#: raio de tolerância (em pixels) pra "encostar" o clique no pixel
#: caminhável mais próximo -- um só pixel de inclinação ruidosa (ex.
#: borda de uma crista do boxwork) não deveria travar um clique que
#: visualmente parece estar em terreno razoável. ~3 pixels * 5.88m/px
#: ~= 17m de tolerância, pequeno o bastante pra não mudar o sentido do
#: clique do usuário.
RAIO_SNAP_PX = 3


def _snap_para_passavel(r, c, n_rows, n_cols, passavel):
    """Procura em espiral o pixel caminhável mais próximo de (r, c)
    dentro de RAIO_SNAP_PX. Devolve None se não achar nenhum."""
    if passavel(r, c):
        return r, c
    for raio in range(1, RAIO_SNAP_PX + 1):
        candidatos = []
        for dr in range(-raio, raio + 1):
            for dc in range(-raio, raio + 1):
                if max(abs(dr), abs(dc)) != raio:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < n_rows and 0 <= cc < n_cols and passavel(rr, cc):
                    candidatos.append((rr, cc))
        if candidatos:
            return min(candidatos, key=lambda p: math.hypot(p[0] - r, p[1] - c))
    return None


def _astar(elevacao, slope_deg, transform, pixel_size_m, origem_rc, destino_rc, tipo: str):
    n_rows, n_cols = elevacao.shape
    peso_atencao = PESO_ATENCAO[tipo]

    def passavel(r, c):
        return 0 <= r < n_rows and 0 <= c < n_cols and slope_deg[r, c] < LIMITE_SLOPE_PERIGO_DEG

    def custo_aresta(r1, c1, r2, c2):
        dist = pixel_size_m * math.hypot(r2 - r1, c2 - c1)
        s = max(slope_deg[r1, c1], slope_deg[r2, c2])
        if s >= LIMITE_SLOPE_ATENCAO_DEG:
            return dist * peso_atencao
        return dist

    def heuristica(r, c):
        dr, dc = destino_rc[0] - r, destino_rc[1] - c
        return pixel_size_m * math.hypot(dr, dc)

    origem_ok = _snap_para_passavel(*origem_rc, n_rows, n_cols, passavel)
    destino_ok = _snap_para_passavel(*destino_rc, n_rows, n_cols, passavel)
    if origem_ok is None and destino_ok is None:
        raise ForaDoGridError("Origem e destino caem em terreno acima do limite de 20° (mesmo no pixel mais próximo caminhável)")
    if origem_ok is None:
        raise ForaDoGridError("Origem cai em terreno acima do limite de 20° -- clique num ponto um pouco diferente")
    if destino_ok is None:
        raise ForaDoGridError("Destino cai em terreno acima do limite de 20° -- clique num ponto um pouco diferente")
    origem_rc, destino_rc = origem_ok, destino_ok

    aberto = [(heuristica(*origem_rc), origem_rc)]
    veio_de: dict = {}
    g_score = {origem_rc: 0.0}
    visitado = set()

    while aberto:
        _, atual = heapq.heappop(aberto)
        if atual in visitado:
            continue
        if atual == destino_rc:
            caminho = [atual]
            while atual in veio_de:
                atual = veio_de[atual]
                caminho.append(atual)
            caminho.reverse()
            return caminho
        visitado.add(atual)

        for dr, dc in _VIZINHOS_8:
            viz = (atual[0] + dr, atual[1] + dc)
            if viz in visitado or not passavel(*viz):
                continue
            novo_g = g_score[atual] + custo_aresta(atual[0], atual[1], viz[0], viz[1])
            if novo_g < g_score.get(viz, math.inf):
                g_score[viz] = novo_g
                veio_de[viz] = atual
                heapq.heappush(aberto, (novo_g + heuristica(*viz), viz))

    raise SemCaminhoError("Nenhum caminho possível sem cruzar inclinação >= 20°")


def _monta_rota(tipo: str, caminho_rc, elevacao, slope_deg, transform, pixel_size_m, dose_rad_ugy_por_hora) -> dict:
    pontos = [_rc_to_latlon(transform, r, c) for r, c in caminho_rc]

    distancia_m = 0.0
    perfil = [{"distancia_acumulada_m": 0.0, "elevacao_m": float(elevacao[caminho_rc[0]])}]
    trechos_risco = []
    tempo_s = 0.0
    o2_otimista_l = 0.0
    o2_pessimista_l = 0.0
    for i in range(1, len(caminho_rc)):
        r1, c1 = caminho_rc[i - 1]
        r2, c2 = caminho_rc[i]
        d = pixel_size_m * math.hypot(r2 - r1, c2 - c1)
        distancia_m += d

        s = max(slope_deg[r1, c1], slope_deg[r2, c2])
        if s >= LIMITE_SLOPE_PERIGO_DEG:
            status = "perigo"
        elif s >= LIMITE_SLOPE_ATENCAO_DEG:
            status = "atencao"
        else:
            status = "seguro"

        # velocidade decresce com a inclinação -- modelo simples e
        # declarado (ver VELOCIDADE_BASE_M_S acima), não sensor real.
        velocidade = VELOCIDADE_BASE_M_S * max(1 - (s / LIMITE_SLOPE_PERIGO_DEG) * 0.6, 0.25)
        tempo_s += d / velocidade

        # Faixa otimista-pessimista do trecho (Fase 1): mesma forma da
        # velocidade/tempo acima, com os fatores declarados no topo do
        # arquivo -- ver FATOR_VELOCIDADE_*.
        velocidade_otimista = VELOCIDADE_BASE_M_S * max(1 - (s / LIMITE_SLOPE_PERIGO_DEG) * FATOR_VELOCIDADE_OTIMISTA, 0.25)
        velocidade_pessimista = VELOCIDADE_BASE_M_S * max(1 - (s / LIMITE_SLOPE_PERIGO_DEG) * FATOR_VELOCIDADE_PESSIMISTA, 0.25)
        tempo_min_otimista_trecho = (d / velocidade_otimista) / 60.0
        tempo_min_pessimista_trecho = (d / velocidade_pessimista) / 60.0

        # Razão da equação de Pandolf (ver _metabolismo_pandolf_w acima)
        # entre o trecho real (com a inclinação e a velocidade de cada
        # caso) e o caso-base plano -- é isso que faz a taxa de O2 subir
        # com a inclinação, com fonte declarada.
        grade_pct = 100.0 * math.tan(math.radians(s))
        taxa_o2_otimista = TAXA_O2_L_POR_MIN * (
            _metabolismo_pandolf_w(velocidade_otimista, grade_pct) / _METABOLISMO_BASE_W
        )
        taxa_o2_pessimista = TAXA_O2_L_POR_MIN * (
            _metabolismo_pandolf_w(velocidade_pessimista, grade_pct) / _METABOLISMO_BASE_W
        )
        o2_otimista_l += taxa_o2_otimista * tempo_min_otimista_trecho
        o2_pessimista_l += taxa_o2_pessimista * tempo_min_pessimista_trecho

        perfil.append({
            "distancia_acumulada_m": round(distancia_m, 1),
            "elevacao_m": float(elevacao[r2, c2]),
        })
        trechos_risco.append({
            "de": [pontos[i - 1][0], pontos[i - 1][1]],
            "para": [pontos[i][0], pontos[i][1]],
            "slope_status": status,
            "slope_deg": round(float(s), 2),
        })

    tempo_min = tempo_s / 60.0
    o2_l = TAXA_O2_L_POR_MIN * tempo_min

    # Radiação (RAD) real por sol -- não varia por posição no nosso
    # dado (é uma leitura do instrumento no rover, não um raster
    # espacial), então não muda QUAL caminho o A* escolhe, mas é uma
    # dose real acumulada de verdade pelo tempo que a caminhada leva.
    # None (não 0) quando o sol de referência não está cacheado -- ver
    # api/main.py REFERENCE_SOL -- pra não fingir "zero radiação".
    dose_rad_ugy = round(dose_rad_ugy_por_hora * (tempo_min / 60.0), 2) if dose_rad_ugy_por_hora is not None else None

    return {
        "tipo": tipo,
        "pontos": [[lat, lon] for lat, lon in pontos],
        "distancia_m": round(distancia_m, 1),
        "tempo_estimado_min": round(tempo_min, 1),
        "o2_estimado_l": round(o2_l, 2),
        "o2_estimado_l_faixa": {
            "otimista": round(o2_otimista_l, 2),
            "pessimista": round(o2_pessimista_l, 2),
        },
        "dose_rad_estimada_ugy": dose_rad_ugy,
        "perfil_elevacao": perfil,
        "trechos_risco": trechos_risco,
    }


def _melhor_alvo_cientifico(origin_lat, origin_lon, dest_lat, dest_lon, alvos: list[dict]) -> dict | None:
    """Alvo científico com menor desvio real (em metros) em relação à
    linha reta origem-destino, entre os que cabem em
    MAIS_CIENCIA_DESVIO_MAX_M. None se nenhum coube -- nunca força
    passar por um alvo longe demais só pra existir uma 3a opção."""
    direta = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon)
    melhor, menor_desvio = None, None
    for alvo in alvos:
        via_alvo = haversine_m(origin_lat, origin_lon, alvo["lat"], alvo["lon"]) + haversine_m(
            alvo["lat"], alvo["lon"], dest_lat, dest_lon
        )
        desvio = via_alvo - direta
        if desvio <= MAIS_CIENCIA_DESVIO_MAX_M and (menor_desvio is None or desvio < menor_desvio):
            melhor, menor_desvio = alvo, desvio
    return melhor


def _astar_encadeado(elevacao, slope_deg, transform, pixel_size_m, pontos_rc: list, tipo: str) -> list:
    """Encadeia A* por uma sequência de pontos (origem, paradas..., destino),
    uma chamada por perna, concatenando sem duplicar o pixel de junção
    entre pernas consecutivas. Generaliza o que "mais_ciencia" já fazia
    com 2 pernas (origem->alvo->destino) pra N pernas (paradas manuais)."""
    caminho = _astar(elevacao, slope_deg, transform, pixel_size_m, pontos_rc[0], pontos_rc[1], tipo)
    for i in range(1, len(pontos_rc) - 1):
        perna = _astar(elevacao, slope_deg, transform, pixel_size_m, pontos_rc[i], pontos_rc[i + 1], tipo)
        caminho += perna[1:]
    return caminho


def plan_route(
    conn: sqlite3.Connection, origin_lat, origin_lon, dest_lat, dest_lon, dose_rad_ugy_por_hora=None, paradas=None
) -> dict:
    """paradas: lista opcional de (lat, lon) -- pontos que a rota precisa
    visitar em ordem, entre a origem e o destino (gap "paradas
    intermediárias"). Com paradas, a variante "mais_ciencia" não entra:
    ela já é uma forma automática de visitar um ponto no meio do
    caminho, e duas lógicas de "ponto no meio" ao mesmo tempo só
    confundiriam qual rota passa por onde -- se o astronauta já está
    escolhendo os pontos manualmente, isso substitui a sugestão automática."""
    path = _dtm_path(conn)
    elevacao, transform, bounds, nodata = _load_dtm(path)

    pixel_size_deg = abs(transform.a)
    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE
    slope_deg = _slope_grid_deg(elevacao, pixel_size_m)

    def dentro_bbox(lat, lon):
        return bounds.left <= lon <= bounds.right and bounds.bottom <= lat <= bounds.top

    paradas = paradas or []
    todos_pontos = [(origin_lat, origin_lon), *paradas, (dest_lat, dest_lon)]
    if not all(dentro_bbox(lat, lon) for lat, lon in todos_pontos):
        raise ForaDoGridError("Origem, parada ou destino fora da área com dado DTM baixado")

    pontos_rc = [_latlon_to_rc(transform, lat, lon) for lat, lon in todos_pontos]
    origem_rc, destino_rc = pontos_rc[0], pontos_rc[-1]

    rotas = []
    for tipo in ("mais_segura", "mais_rapida"):
        caminho = _astar_encadeado(elevacao, slope_deg, transform, pixel_size_m, pontos_rc, tipo)
        rotas.append(_monta_rota(tipo, caminho, elevacao, slope_deg, transform, pixel_size_m, dose_rad_ugy_por_hora))

    # "mais_ciencia": passa pelo alvo científico real mais próximo do
    # caminho, só se o desvio for razoável (ver MAIS_CIENCIA_DESVIO_MAX_M)
    # -- com poucos alvos cadastrados (feature 4), nem sempre vai existir
    # um perto o bastante, e aí essa variante simplesmente não aparece
    # (melhor que forçar um desvio absurdo só pra "ter ciência").
    if not paradas:
        alvo = _melhor_alvo_cientifico(origin_lat, origin_lon, dest_lat, dest_lon, todos_alvos_cientificos(conn))
        if alvo is not None:
            alvo_rc = _latlon_to_rc(transform, alvo["lat"], alvo["lon"])
            try:
                caminho_completo = _astar_encadeado(
                    elevacao, slope_deg, transform, pixel_size_m, [origem_rc, alvo_rc, destino_rc], "mais_segura"
                )
                rota_ciencia = _monta_rota(
                    "mais_ciencia", caminho_completo, elevacao, slope_deg, transform, pixel_size_m, dose_rad_ugy_por_hora
                )
                rota_ciencia["alvo_cientifico"] = {
                    "nome": alvo["nome"],
                    "medicao_curiosity": alvo["medicao_curiosity"],
                    "fonte_url": alvo["fonte_url"],
                }
                rotas.append(rota_ciencia)
            except (SemCaminhoError, ForaDoGridError):
                pass  # alvo existe mas não tem caminho caminhável até ele -- sem essa variante, sem quebrar as outras duas

    return {"rotas": rotas, "avisos": [AVISO_AREIA]}
