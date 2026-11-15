"""Testes da Fase 4 (F02+F08): rótulo, prós/contras e ordem sugerida --
ver docstring de sugestao_rotas.py pros critérios (definidos agora pra
desbloquear o Hugo, a confirmar/ajustar com ele depois).

Rodar: cd api && python test_sugestao_rotas.py
Usa rotas sintéticas (dicts), não precisa do DTM real nem do banco."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sugestao_rotas import sugerir


def _rota(tipo, trechos_status=(), alertas_nivel=(), margem_pct=None, tempo_min=30.0,
          pior_trecho_sem_volta=False, alvo_cientifico=None):
    margem_minima = None if margem_pct is None else {"litros": 10.0, "pct": margem_pct, "distancia_m": 100.0}
    pior_trecho_emergencia = None
    if pior_trecho_sem_volta:
        pior_trecho_emergencia = {"lat": 0, "lon": 0, "distancia_m": 0, "tempo_volta_min": None, "o2_volta_l": None}
    elif trechos_status or margem_pct is not None:
        pior_trecho_emergencia = {"lat": 0, "lon": 0, "distancia_m": 0, "tempo_volta_min": 10.0, "o2_volta_l": 1.0}
    return {
        "tipo": tipo,
        "tempo_estimado_min": tempo_min,
        "trechos_risco": [{"slope_status": s} for s in trechos_status],
        "alertas": [{"nivel": n} for n in alertas_nivel],
        "margem_minima": margem_minima,
        "pior_trecho_emergencia": pior_trecho_emergencia,
        "alvo_cientifico": alvo_cientifico,
    }


def test_rotulo_perigo_por_trecho_acima_de_20_graus():
    rotas = [_rota("mais_rapida", trechos_status=["seguro", "perigo"])]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⛔"


def test_rotulo_perigo_por_alerta_perigo():
    rotas = [_rota("mais_rapida", alertas_nivel=["perigo"])]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⛔"


def test_rotulo_perigo_por_margem_abaixo_do_limite():
    rotas = [_rota("mais_rapida", margem_pct=10.0)]  # abaixo de LIMITE_MARGEM_PERIGO_PCT (15)
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⛔"


def test_rotulo_perigo_por_ponto_sem_volta_calculavel():
    rotas = [_rota("mais_rapida", pior_trecho_sem_volta=True)]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⛔"


def test_rotulo_atencao_por_trecho_entre_15_e_20():
    rotas = [_rota("mais_rapida", trechos_status=["seguro", "atencao"])]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⚠️"


def test_rotulo_atencao_por_margem_abaixo_do_limite_de_atencao():
    rotas = [_rota("mais_rapida", margem_pct=25.0)]  # entre 15 e 30
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "⚠️"


def test_rotulo_seguro_sem_nenhum_gatilho():
    rotas = [_rota("mais_rapida", trechos_status=["seguro", "seguro"], margem_pct=80.0)]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "✅"


def test_sem_o2_informado_rotulo_nao_vira_perigo_so_por_isso():
    rotas = [_rota("mais_rapida", trechos_status=["seguro"], margem_pct=None)]
    sugerir(rotas)
    assert rotas[0]["rotulo"] == "✅"
    assert "Sem oxigênio informado" in rotas[0]["pros_contras"][0]["texto"]


def test_ordem_por_maior_margem_primeiro():
    rotas = [
        _rota("mais_segura", margem_pct=40.0),
        _rota("mais_rapida", margem_pct=80.0),
    ]
    resultado = sugerir(rotas)
    assert resultado["ordem"][0] == "mais_rapida"
    assert "80%" in resultado["motivo"]


def test_ordem_empate_de_margem_desempata_por_menos_trechos_de_risco():
    rotas = [
        _rota("mais_segura", margem_pct=50.0, trechos_status=["atencao", "atencao"]),
        _rota("mais_rapida", margem_pct=50.0, trechos_status=["atencao"]),
    ]
    resultado = sugerir(rotas)
    assert resultado["ordem"][0] == "mais_rapida"


def test_ordem_empate_total_prefere_ciencia_como_ultimo_desempate():
    rotas = [
        _rota("mais_segura", margem_pct=50.0, tempo_min=30.0),
        _rota("mais_ciencia", margem_pct=50.0, tempo_min=30.0, alvo_cientifico={"nome": "X", "fonte_url": "https://example.com"}),
    ]
    resultado = sugerir(rotas)
    assert resultado["ordem"][0] == "mais_ciencia"


def test_sugestao_aviso_sempre_presente():
    rotas = [_rota("mais_rapida", margem_pct=50.0)]
    resultado = sugerir(rotas)
    assert resultado["aviso"] == "a decisão é sua"


def test_todas_as_rotas_continuam_na_lista_mesmo_a_perigo():
    rotas = [_rota("mais_rapida", trechos_status=["perigo"]), _rota("mais_segura", margem_pct=80.0)]
    resultado = sugerir(rotas)
    assert set(resultado["ordem"]) == {"mais_rapida", "mais_segura"}
    assert len(rotas) == 2  # nenhuma rota removida da lista original


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
