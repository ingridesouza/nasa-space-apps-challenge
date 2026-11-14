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


def test_parada_ingreme_entre_25_e_100_m_vira_atencao():
    a = tipos(alertas_do_ponto(-4.7863, 137.4076, MAPA_SEGURO))  # ~50 m da parada de 22,4° (sol 4309)
    assert a["terreno_historico"]["nivel"] == "atencao" and "22,4°" in a["terreno_historico"]["mensagem"]


def test_area_sem_historico_do_rover():
    inexplorado = (-4.8150, 137.3750)  # dentro do mapa, longe da trilha do Curiosity
    a = tipos(alertas_do_ponto(*inexplorado, MAPA_SEGURO))
    assert a["sem_historico"]["nivel"] == "atencao" and "100 m" in a["sem_historico"]["mensagem"]
    assert "sem_historico" not in tipos(alertas_do_ponto(*SOL_4309, MAPA_SEGURO))  # na trilha do rover
    sem_mapa = {"slope_deg": None, "slope_status": None, "classe_ai4mars": None}
    assert "sem_historico" not in tipos(alertas_do_ponto(*inexplorado, sem_mapa))  # "sem inclinação" já avisa


def test_ordem_por_gravidade():
    niveis = [a["nivel"] for a in alertas_do_ponto(*SOL_4309, MAPA_SEGURO)]
    assert niveis == sorted(niveis, key=["perigo", "atencao", "info"].index)


def test_sem_arquivo_de_paradas():
    alertas = alertas_do_ponto(*SOL_4309, MAPA_SEGURO, waypoints_path="/nao/existe.json")
    assert any("Histórico do rover indisponível" in a["mensagem"] for a in alertas)



def test_tempo_marte_contra_referencias():
    from datetime import datetime, timezone

    from tempo_marte import data_do_sol, ls, sol_msl

    # exemplo resolvido do Mars24: 6/jan/2000 0h UTC -> Ls 277,18758°
    assert abs(ls(datetime(2000, 1, 6, tzinfo=timezone.utc)) - 277.18758) < 0.001
    # datas reais de panoramas do pacote F03 (só a data, sem hora: tolera 1 dia)
    for sol, data in ((4552, "2025-05-27"), (4647, "2025-09-02"), (4816, "2026-02-22")):
        assert abs((data_do_sol(sol).date() - datetime.fromisoformat(data).date()).days) <= 1
        assert abs(sol_msl(datetime.fromisoformat(data + "T12:00+00:00")) - sol) <= 1


def test_modo_sem_terra_idade_e_poeira():
    from datetime import datetime, timezone

    from alertas import tempo_e_alertas_do_sol
    from tempo_marte import data_do_sol

    tempo, alertas = tempo_e_alertas_do_sol(4650, agora=data_do_sol(4650))
    assert tempo["idade_do_dado_sols"] == 0 and not any(a["tipo"] == "dado_antigo" for a in alertas)
    _, alertas = tempo_e_alertas_do_sol(4650, agora=data_do_sol(4660))
    assert any(a["tipo"] == "dado_antigo" and "10 sols" in a["mensagem"] for a in alertas)
    # 2026-11-14: Ls ~22° (fora da temporada); sol 4650 (set/2025): Ls ~135° (fora também)
    _, alertas = tempo_e_alertas_do_sol(4650, agora=datetime(2026, 11, 14, tzinfo=timezone.utc))
    assert not any(a["tipo"] == "temporada_poeira" for a in alertas)
    _, alertas = tempo_e_alertas_do_sol(4650, agora=datetime(2026, 5, 1, tzinfo=timezone.utc))
    assert any(a["tipo"] == "temporada_poeira" for a in alertas)


if __name__ == "__main__":
    testes = [f for nome, f in sorted(globals().items()) if nome.startswith("test_")]
    for t in testes:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(testes)} testes passaram")
