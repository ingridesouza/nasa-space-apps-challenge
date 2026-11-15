"""Testes da Fase 3 (F02+F08): margem_minima, ponto_nao_retorno,
pior_trecho_emergencia, volta_minutos_max -- ver docstring de
route_planning._perfil_margem_de_volta pros critérios e decisões de
formato (a confirmar/ajustar com o Hugo, seção 8.0 do doc de
arquitetura).

Rodar: cd api && python test_margem_de_volta.py
Usa grids sintéticos (não precisa do DTM real)."""

import sys
from pathlib import Path

import numpy as np
from affine import Affine

sys.path.insert(0, str(Path(__file__).parent))

from route_planning import _monta_rota

TRANSFORM = Affine(0.00005, 0, 137.0, 0, -0.00005, -4.8)
ELEVACAO_PLANA = np.zeros((5, 5))
SLOPE_PLANA = np.zeros((5, 5))
CAMINHO_RETO = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]

# mapa de custo de volta sintético: custo cresce de forma constante por
# pixel de distância em linha reta a partir de (0,0) -- fácil de prever
# o ponto exato onde cada critério deveria disparar.
MAPA_CUSTO_CRESCENTE = {
    (0, 0): {"tempo_volta_s": 0.0, "o2_volta_l": 0.0},
    (0, 1): {"tempo_volta_s": 10.0, "o2_volta_l": 0.1},
    (0, 2): {"tempo_volta_s": 20.0, "o2_volta_l": 0.2},
    (0, 3): {"tempo_volta_s": 30.0, "o2_volta_l": 0.3},
    (0, 4): {"tempo_volta_s": 40.0, "o2_volta_l": 0.4},
}


def _rota(mapa_custo_base, o2_disponivel_l=None):
    return _monta_rota(
        "mais_rapida", CAMINHO_RETO, ELEVACAO_PLANA, SLOPE_PLANA, TRANSFORM, 5.0, None,
        mapa_custo_base, o2_disponivel_l,
    )


def test_sem_mapa_de_custo_todos_os_campos_ficam_null():
    r = _rota(mapa_custo_base=None, o2_disponivel_l=10.0)
    assert r["margem_minima"] is None
    assert r["ponto_nao_retorno"] is None
    assert r["pior_trecho_emergencia"] is None
    assert r["volta_minutos_max"] is None


def test_sem_o2_informado_margem_fica_null_mas_resto_continua():
    r = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=None)
    assert r["margem_minima"] is None
    assert r["ponto_nao_retorno"] is not None
    assert r["pior_trecho_emergencia"] is not None
    assert r["volta_minutos_max"] is not None


def test_ponto_nao_retorno_e_o_primeiro_onde_voltar_fica_mais_caro_que_seguir():
    r = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=10.0)
    # tempo total pessimista ~25s (4 trechos de 5m a 0.8m/s); o custo de
    # volta passa o tempo restante exatamente no 3o ponto (índice 2,
    # 10m de distância) -- ver cálculo à mão na sessão de implementação.
    assert r["ponto_nao_retorno"]["distancia_m"] == 10.0


def test_pior_trecho_emergencia_e_o_de_maior_custo_de_volta():
    r = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=10.0)
    assert r["pior_trecho_emergencia"]["distancia_m"] == 20.0  # último ponto, maior tempo_volta_s
    assert r["pior_trecho_emergencia"]["tempo_volta_min"] == round(40.0 / 60, 1)
    assert r["pior_trecho_emergencia"]["o2_volta_l"] == 0.4


def test_ponto_inalcancavel_vence_como_pior_caso_mesmo_com_voltas_finitas_maiores():
    mapa = dict(MAPA_CUSTO_CRESCENTE)
    del mapa[(0, 3)]  # esse ponto não tem caminho de volta até a base
    r = _rota(mapa, o2_disponivel_l=10.0)
    assert r["pior_trecho_emergencia"]["distancia_m"] == 15.0  # índice 3, não o índice 4 (40s, maior valor finito)
    assert r["pior_trecho_emergencia"]["tempo_volta_min"] is None
    assert r["pior_trecho_emergencia"]["o2_volta_l"] is None
    # volta_minutos_max e margem_minima ignoram o ponto sem volta --
    # ele já foi sinalizado em pior_trecho_emergencia, não duplicado
    # aqui. O maior valor VÁLIDO que sobra é o do índice 4 (40s), não
    # o do índice 2 (20s) -- remover (0,3) não afeta os outros pontos.
    assert r["volta_minutos_max"] == round(40.0 / 60, 1)


def test_margem_minima_e_o_pior_ponto_e_bate_com_a_conta_a_mao():
    r = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=10.0)
    # litros/pct calculados à mão (ver sessão de implementação): o pior
    # ponto é o último (índice 4): 10 - (o2 gasto até lá + o2 de volta).
    assert r["margem_minima"]["litros"] == 9.18
    assert r["margem_minima"]["pct"] == 91.8
    assert r["margem_minima"]["distancia_m"] == 20.0


def test_margem_minima_cresce_se_o2_disponivel_for_maior():
    r_pouco = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=1.0)
    r_muito = _rota(MAPA_CUSTO_CRESCENTE, o2_disponivel_l=100.0)
    assert r_muito["margem_minima"]["litros"] > r_pouco["margem_minima"]["litros"]


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
