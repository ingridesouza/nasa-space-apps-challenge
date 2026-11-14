"""Testes das regras de api/alertas.py com pontos reais do repo.

Rodar: make test   (ou: cd api && python test_alertas.py)
Precisa de data/local/rover_waypoints.json (make build)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alertas import alertas_do_ponto

# O mapa diz "seguro" e não sabe de areia -- é o caso que a memória do
# terreno existe pra pegar.
MAPA_SEGURO = {"slope_deg": 11.0, "slope_status": "seguro", "classe_ai4mars": None}
SOL_4309 = (-4.78679146, 137.4076395)  # rover mediu 22,37°, a 2.029 m da base provisória
SOL_4970 = (-4.82096424, 137.3856038)  # rover mediu 24,02°, a 901 m da base provisória


def tipos(alertas):
    return {a["tipo"]: a for a in alertas}


def test_memoria_do_terreno_e_volta_base():
    a = tipos(alertas_do_ponto(*SOL_4309, MAPA_SEGURO))
    assert a["terreno_historico"]["nivel"] == "perigo"
    assert "22,4°" in a["terreno_historico"]["mensagem"] and "sol 4309" in a["terreno_historico"]["mensagem"]
    assert a["volta_base"]["nivel"] == "perigo"
    assert "inclinacao" not in a  # o mapa disse 11°: quem avisa é o histórico


def test_terreno_sem_volta_base():
    a = tipos(alertas_do_ponto(*SOL_4970, MAPA_SEGURO))
    assert "24,0°" in a["terreno_historico"]["mensagem"]
    assert "volta_base" not in a


def test_inclinacao_do_mapa():
    perto_da_base = (-4.8068928, 137.3798418)
    atencao = tipos(alertas_do_ponto(*perto_da_base, {"slope_deg": 15.0, "slope_status": "atencao"}))
    perigo = tipos(alertas_do_ponto(*perto_da_base, {"slope_deg": 20.0, "slope_status": "perigo"}))
    assert atencao["inclinacao"]["nivel"] == "atencao"
    assert perigo["inclinacao"]["nivel"] == "perigo"


def test_fora_do_bbox_sem_dado():
    alertas = alertas_do_ponto(-4.59, 137.44, {"slope_deg": None, "slope_status": None, "classe_ai4mars": None})
    assert any(a["tipo"] == "sem_dado" and "inclinação" in a["mensagem"] for a in alertas)
    assert any("areia" in a["mensagem"] for a in alertas)


def test_ordem_por_gravidade():
    niveis = [a["nivel"] for a in alertas_do_ponto(*SOL_4309, MAPA_SEGURO)]
    assert niveis == sorted(niveis, key=["perigo", "atencao", "info"].index)


def test_sem_arquivo_de_paradas():
    alertas = alertas_do_ponto(*SOL_4309, MAPA_SEGURO, waypoints_path="/nao/existe.json")
    assert any("Histórico do rover indisponível" in a["mensagem"] for a in alertas)


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
