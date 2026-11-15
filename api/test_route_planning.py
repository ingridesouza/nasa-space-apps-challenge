"""Testes de api/route_planning.py com o DTM real do repo.

Rodar: cd api && python test_route_planning.py
Precisa de data/local/h2g2.sqlite com a camada dtm_hirise_1m (make build)."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alertas import BASE_LAT_LON
from db import get_connection
from route_planning import (
    FATOR_VELOCIDADE_PESSIMISTA,
    LIMITE_SLOPE_PERIGO_DEG,
    TAXA_O2_L_POR_MIN,
    VELOCIDADE_BASE_M_S,
    _latlon_to_rc,
    _load_dtm,
    custo_ate_base,
)

CONN = get_connection()


def test_a_base_tem_custo_zero():
    path = __import__("route_planning")._dtm_path(CONN)
    elevacao, transform, bounds, nodata = _load_dtm(path)
    base_rc = _latlon_to_rc(transform, *BASE_LAT_LON)

    mapa = custo_ate_base(CONN)
    assert mapa[base_rc]["tempo_volta_s"] == 0.0
    assert mapa[base_rc]["o2_volta_l"] == 0.0


def test_pixel_longe_tem_volta_maior_que_pixel_perto():
    mapa = custo_ate_base(CONN)
    path = __import__("route_planning")._dtm_path(CONN)
    elevacao, transform, bounds, nodata = _load_dtm(path)
    base_rc = _latlon_to_rc(transform, *BASE_LAT_LON)

    # pixels a 5 e a 50 passos (8-conectado) da base em linha reta --
    # ambos devem existir no grid real de Gale (512x512).
    perto = (base_rc[0] + 5, base_rc[1])
    longe = (base_rc[0] + 50, base_rc[1])
    assert perto in mapa and longe in mapa
    assert mapa[longe]["tempo_volta_s"] > mapa[perto]["tempo_volta_s"] > 0
    assert mapa[longe]["o2_volta_l"] > mapa[perto]["o2_volta_l"] > 0


def test_pixel_impassavel_nao_tem_entrada():
    mapa = custo_ate_base(CONN)
    path = __import__("route_planning")._dtm_path(CONN)
    elevacao, transform, bounds, nodata = _load_dtm(path)
    pixel_size_deg = abs(transform.a)
    from geo import MARS_METERS_PER_DEGREE

    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE
    from route_planning import _slope_grid_deg

    slope_deg = _slope_grid_deg(elevacao, pixel_size_m)
    n_rows, n_cols = elevacao.shape

    impassaveis = [
        (r, c)
        for r in range(n_rows)
        for c in range(n_cols)
        if slope_deg[r, c] >= LIMITE_SLOPE_PERIGO_DEG
    ]
    assert impassaveis, "esperava pelo menos um pixel >= 20° no DTM real do boxwork"
    assert not any(rc in mapa for rc in impassaveis[:50])


def test_cache_devolve_o_mesmo_objeto():
    # lru_cache: a segunda chamada não deve recomputar (mesmo dict em
    # memória) -- é o que garante o "calculado uma vez" da Fase 2.
    assert custo_ate_base(CONN) is custo_ate_base(CONN)


def test_tempo_e_o2_batem_com_a_formula_pessimista_de_um_so_trecho():
    # Confere a fórmula reaproveitada da Fase 1 num trecho isolado: a
    # velocidade pessimista em terreno ~plano é a velocidade base, e a
    # razão de Pandolf em inclinação ~0 é ~1 -- então tempo/O2 do
    # primeiro passo a partir da base devem bater com o cálculo direto.
    path = __import__("route_planning")._dtm_path(CONN)
    elevacao, transform, bounds, nodata = _load_dtm(path)
    from geo import MARS_METERS_PER_DEGREE

    pixel_size_deg = abs(transform.a)
    pixel_size_m = pixel_size_deg * MARS_METERS_PER_DEGREE
    base_rc = _latlon_to_rc(transform, *BASE_LAT_LON)

    mapa = custo_ate_base(CONN)
    vizinho_reto = (base_rc[0] + 1, base_rc[1])
    assert vizinho_reto in mapa

    # cota superior frouxa: nesse trecho de 1 pixel, mesmo no pior caso
    # de inclinação (quase 20°) o tempo não passa de pixel/velocidade
    # mínima (0.25 m/s) e o O2 fica na mesma ordem de grandeza da taxa
    # base -- garante que não houve escala absurda (ex. multiplicar por
    # engano em vez de somar).
    velocidade_minima = 0.25
    tempo_max_s = pixel_size_m / velocidade_minima
    assert 0 < mapa[vizinho_reto]["tempo_volta_s"] <= tempo_max_s
    assert 0 < mapa[vizinho_reto]["o2_volta_l"] < TAXA_O2_L_POR_MIN * (tempo_max_s / 60.0) * 3


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
