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
