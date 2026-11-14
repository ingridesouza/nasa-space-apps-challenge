"""Testes pedidos no plano: ponto de pouso no PLACES (tarefa 3) e parada
conhecida devolvendo o próprio panorama a menos de 10 m (tarefa 8).

Rodar a partir de h2g2-f03/:  python -m pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.geo import bearing, haversine, photo_azimuth, yaw_inicial  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
PUB = CFG["public"]


def test_um_grau_de_latitude():
    # 1° de latitude na esfera de Marte ≈ 59.274 m (valor usado na M3)
    assert haversine(0, 137, 1, 137) == pytest.approx(59274.6, abs=1)


def test_yaw_inicial_e_mast_az():
    # Rumo 65° com centro do panorama em 65° -> abre no centro
    assert yaw_inicial(65, 65) == 0
    assert yaw_inicial(10, 350) == pytest.approx(20)
    # M6: azimute real = mast_az + yaw do rover
    assert photo_azimuth(343.12, 65.13) == pytest.approx(48.25)
    assert bearing(0, 137, 1, 137) == pytest.approx(0)


@pytest.mark.skipif(not (ROOT / PUB["places_file"]).exists(), reason="PLACES não baixado")
def test_ponto_de_pouso_no_places():
    from etl.sources.public import PublicPositions

    pos = PublicPositions(ROOT / PUB["waypoints_file"], ROOT / PUB["places_file"])
    pouso = pos.places(1, 0)
    assert pouso is not None
    assert pouso.lat == pytest.approx(-4.58947, abs=1e-5)  # planetocêntrica
    assert pouso.lon == pytest.approx(137.44163, abs=1e-5)


@pytest.mark.skipif(not (ROOT / "bundle" / "h2g2.db").exists(), reason="pacote não montado")
def test_parada_conhecida_devolve_o_proprio_panorama():
    from fastapi.testclient import TestClient

    from api.main import app

    c = TestClient(app)
    # Parada 118_2028 (sol 4643) no MMGIS
    r = c.get("/panoramas/nearest", params={"lat": -4.80679651, "lon": 137.3794121}).json()
    assert r["found"] and r["rmc"] == "118_2028"
    assert r["distancia_m"] < 10
    fotos = c.get("/photos/near", params={"lat": -4.80679651, "lon": 137.3794121}).json()
    assert fotos["total"] > 0
    assert c.get("/orbital/crop", params={"lat": -4.80679651, "lon": 137.3794121}).status_code == 200


@pytest.mark.skipif(not (ROOT / "bundle" / "h2g2.db").exists(), reason="pacote não montado")
def test_longitude_negativa_e_fora_da_janela():
    from fastapi.testclient import TestClient

    from api.main import app

    c = TestClient(app)
    r = c.get("/panoramas/nearest", params={"lat": -4.80679651, "lon": 137.3794121 - 360}).json()
    assert r["found"] and r["rmc"] == "118_2028"
    fora = c.get("/panoramas/nearest", params={"lat": 10, "lon": 10}).json()
    assert fora["found"] is False and fora["dentro_da_janela"] is False


# --------------------------------------------------------------------------- #
# F04 · ficha científica (tarefa 1: contrato + mock)
# --------------------------------------------------------------------------- #

DB = ROOT / "bundle" / "h2g2.db"


@pytest.mark.skipif(not DB.exists(), reason="pacote não gerado")
def test_ficha_do_mojo_na_parada_118_2028():
    import sqlite3
    from api.main import R_CARD, science_card

    lat, lon = sqlite3.connect(DB).execute(
        "SELECT lat, lon FROM waypoints WHERE rmc = '118_2028'").fetchone()
    j = science_card(lat, lon, R_CARD)
    assert j["alvo"]["nome"] == "Mojo"
    assert j["alvo"]["distancia_m"] < 10
    assert j["aviso_posicao"] == "posição aproximada pela parada do sol 4643"
    assert any(l["secao"] == "quimica" for l in j["linhas"])
    assert j["mastcam"]["img"].startswith("/bundle/")  # offline: nunca URL externa
    assert all(l["fonte_url"] or l["fonte_arquivo"] for l in j["linhas"] + j["contexto"])


@pytest.mark.skipif(not DB.exists(), reason="pacote não gerado")
def test_ficha_sem_alvo_perto_e_fora_da_janela():
    from api.main import R_CARD, science_card

    longe = science_card(-4.8100, 137.3770, R_CARD)
    assert longe["alvo"] is None and "nenhum alvo estudado a menos de 150 m" in longe["mensagem"]
    # CRISM (tarefa 5) ainda não ligado: a fonte public não inventa linha de órbita
    assert not any(l["secao"] == "orbita" and l["confianca"] == "mock" for l in longe["linhas"])
    fora = science_card(-10.0, 137.38, R_CARD)
    assert fora["alvo"] is None and fora["dentro_da_janela"] is False and fora["linhas"] == []


# --------------------------------------------------------------------------- #
# F04 · tarefas 3 e 4: medições reais do PDS (science_source: public)
# --------------------------------------------------------------------------- #


def test_resumo_por_regra_do_pds():
    from etl.sources.science_public import summary_apxs, summary_chemin

    assert summary_chemin([("Plagioclase", 51, 0), ("Quartz", 1.6, 0)]) == \
        "Fração cristalina: plagioclásio 51,0% · quartzo 1,6%."
    assert summary_apxs({"SiO2": (43.17, 0.1), "Br": (0.0088, 0)}) == "Óxidos principais: SiO2 43,2%."


@pytest.mark.skipif(not DB.exists(), reason="pacote não gerado")
def test_ficha_da_altadena_com_chemin_real():
    import sqlite3
    from api.main import R_CARD, science_card

    lat, lon = sqlite3.connect(DB).execute(
        "SELECT lat, lon FROM waypoints WHERE rmc = '116_1944'").fetchone()
    j = science_card(lat, lon, R_CARD)
    assert j["alvo"]["nome"] == "Altadena"
    assert any(l["instrumento"] == "CheMin" and l["confianca"] == "medido"
               and l["fonte_arquivo"].startswith("cmb_") for l in j["linhas"])
    assert not any(l["confianca"] == "mock" for l in j["linhas"])
