"""Testa o acréscimo de margem de O2 (Fase 3, route_planning.py) ao
rótulo/contras que sugestao_rotas.py (Hugo) já calculava por terreno e
alertas. Ver _contras_margem_de_volta/_rotulo_margem em sugestao_rotas.py
pros critérios -- combinado com o Hugo pra ele validar/ajustar depois.

Rodar: cd api && python test_sugestao_margem_o2.py
Usa rotas sintéticas (não precisa do DTM nem do banco)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sugestao_rotas import sugerir


def _rota(tipo, margem_pct=None, pior_sem_volta=False, distancia_m=100.0, tempo_min=30.0):
    margem_minima = None if margem_pct is None else {"litros": 1.0, "pct": margem_pct, "distancia_m": distancia_m}
    pior_trecho_emergencia = {
        "lat": 0, "lon": 0, "distancia_m": distancia_m,
        "tempo_volta_min": None if pior_sem_volta else 5.0,
        "o2_volta_l": None if pior_sem_volta else 0.5,
    }
    return {
        "tipo": tipo,
        "distancia_m": distancia_m,
        "tempo_estimado_min": tempo_min,
        "trechos_risco": [{"slope_status": "seguro", "status_previsto": "seguro"}],
        "perfil_elevacao": [{"distancia_acumulada_m": 0.0}, {"distancia_acumulada_m": distancia_m}],
        "alertas": [],
        "margem_minima": margem_minima,
        "pior_trecho_emergencia": pior_trecho_emergencia,
        "alvo_cientifico": None,
    }


def test_rota_sem_terreno_de_risco_mas_margem_negativa_vira_perigo():
    rotas = [_rota("mais_rapida", margem_pct=-20.0)]
    sugerir(rotas)
    assert rotas[0]["sugestao"]["rotulo"] == "perigo"
    assert "margem de O2" in rotas[0]["sugestao"]["contras"][0]["texto"]


def test_margem_entre_15_e_30_vira_atencao_nao_perigo():
    rotas = [_rota("mais_rapida", margem_pct=25.0)]
    sugerir(rotas)
    assert rotas[0]["sugestao"]["rotulo"] == "atencao"


def test_margem_acima_de_30_nao_mexe_no_rotulo_seguro():
    rotas = [_rota("mais_rapida", margem_pct=80.0)]
    sugerir(rotas)
    assert rotas[0]["sugestao"]["rotulo"] == "ok"
    textos = [p["texto"] for p in rotas[0]["sugestao"]["pros"]]
    assert any("margem de O2" in t for t in textos)


def test_sem_o2_informado_nao_forca_rotulo_pra_baixo():
    rotas = [_rota("mais_rapida", margem_pct=None)]
    sugerir(rotas)
    assert rotas[0]["sugestao"]["rotulo"] == "ok"
    assert rotas[0]["sugestao"]["contras"] == []


def test_ponto_sem_volta_calculavel_vira_perigo_mesmo_com_margem_boa():
    rotas = [_rota("mais_rapida", margem_pct=90.0, pior_sem_volta=True)]
    sugerir(rotas)
    assert rotas[0]["sugestao"]["rotulo"] == "perigo"
    assert "não é calculável" in rotas[0]["sugestao"]["contras"][0]["texto"]


def test_margem_e_terreno_o_pior_dos_dois_vence_o_rotulo():
    # trecho "perigo" por terreno, mas margem de O2 boa -- rotulo ainda
    # tem que ser perigo (o pior dos dois critérios vence).
    rota = _rota("mais_rapida", margem_pct=90.0)
    rota["trechos_risco"] = [{"slope_status": "perigo", "status_previsto": "perigo"}]
    sugerir([rota])
    assert rota["sugestao"]["rotulo"] == "perigo"


def test_duas_rotas_perigo_por_terreno_desempatam_pela_maior_margem():
    rotas = [
        _rota("mais_segura", margem_pct=20.0),
        _rota("mais_rapida", margem_pct=50.0),
    ]
    for r in rotas:
        r["trechos_risco"] = [{"slope_status": "perigo", "status_previsto": "perigo"}]
    resultado = sugerir(rotas)
    assert resultado["ordem"][0] == "mais_rapida"  # maior margem entre as duas em perigo


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
