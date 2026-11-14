"""Testes da previsão local (feature 06).

Rodar: make test   (ou: cd api && python test_previsao.py)"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import previsao
from tempo_marte import data_do_sol, ls


def _clima_sintetico():
    """Estação pura (cosseno do Ls) + degrau de +5 a partir do sol 1500 (rover subiu)."""
    out = []
    for sol in range(20, 2001, 20):
        l = ls(data_do_sol(sol))
        t = -70 + 10 * math.cos(math.radians(l)) + (5 if sol >= 1500 else 0)
        # dia com pico às 14h (LMST), como o REMS mostra
        hora = {str(h): t + 30 + 30 * math.cos(2 * math.pi * (h - 14) / 24) for h in range(24)}
        out.append({"sol": sol, "ls": round(l, 1), "temp_min_c": t, "temp_max_c": t + 60,
                    "pressao_pa": 800 + 50 * math.cos(math.radians(l)), "temp_por_hora": hora})
    return out


def test_estacao_mais_anomalia_reproduz_o_sintetico():
    clima = _clima_sintetico()
    base = next(c for c in clima if c["sol"] == 1900)
    p = previsao.prever(clima, 1960, base)
    real = next(c for c in clima if c["sol"] == 1960)
    for k in previsao.CAMPOS:
        # janela de ±15° de Ls alisa a curva: até ~1% da amplitude sazonal
        assert abs(p[k]["valor"] - real[k]) < 2.0, (k, p[k], real[k])


def test_sem_ano_anterior_nao_inventa():
    clima = _clima_sintetico()
    base = next(c for c in clima if c["sol"] == 200)  # nada antes de 200 - 100 sols na mesma estação
    assert all(previsao.prever(clima, 220, base)[k] is None for k in previsao.CAMPOS)


def test_janela_eva_pega_as_horas_mais_quentes():
    clima = _clima_sintetico()
    base = next(c for c in clima if c["sol"] == 1900)
    j = previsao.janela_eva(clima, 1960, base, duracao_min=150)  # 2h30 -> 3 horas
    assert j["horas"] == 3 and j["inicio_lmst"] == "13:00" and j["fim_lmst"] == "16:00", j
    assert previsao.janela_eva(clima, 1960, {**base, "temp_por_hora": {}}, 60) is None  # sem curva: não inventa


def test_backtest_com_dado_real():
    if previsao.carregar_clima() is None:
        print("pulado: rodar data-pipeline/scripts/cache_climatologia.py")
        return
    # meio ano marciano à frente: a estação tem que vencer "repetir o último dado"
    b = previsao.backtest(330)
    for k in ("temp_min_c", "pressao_pa"):
        assert b[k]["erro_medio"] < b[k]["erro_repetindo_ultimo"], (k, b[k])


if __name__ == "__main__":
    for nome, t in list(globals().items()):
        if nome.startswith("test_"):
            t()
            print(f"ok  {nome}")
