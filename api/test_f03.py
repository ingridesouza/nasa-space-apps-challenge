"""F03 (panorama/photos at the point) and F04 (science card) in the main API.

Run: make test   (or: cd api && python -m pytest -q test_f03.py)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))

from db import DB_PATH  # noqa: E402
from geo import bearing, haversine, initial_yaw, photo_azimuth  # noqa: E402

F03_PIPELINE = Path(__file__).resolve().parent.parent / "data-pipeline" / "f03"
sys.path.append(str(F03_PIPELINE))  # F03 etl package
CFG = yaml.safe_load((F03_PIPELINE / "config.yaml").read_text(encoding="utf-8"))
PUB = CFG["public"]


def _bundle_built() -> bool:
    if not Path(DB_PATH).exists():
        return False
    con = sqlite3.connect(DB_PATH)
    try:
        return con.execute("SELECT 1 FROM sqlite_master WHERE name = 'targets'").fetchone() is not None
    finally:
        con.close()


BUNDLE_BUILT = _bundle_built()
F03_ROUTES = {"/map", "/panoramas/nearest", "/photos/near", "/science/card", "/orbital/crop", "/bundle"}


def test_f03_routes_before_the_front_mount():
    from main import app

    paths = []
    for r in app.routes:  # include_router groups the router's routes into a single item
        sub = getattr(r, "original_router", None)
        paths += [x.path for x in sub.routes] if sub else [r.path]
    assert F03_ROUTES <= set(paths), F03_ROUTES - set(paths)
    # the "/" mount (web/) swallows everything that comes after it
    assert paths[-1] == "" and paths.count("") == 1, paths[-3:]


@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_card_never_points_outside():
    from science_card import science_card

    card = science_card(lat=-4.8036, lon=137.3805, radius=150)
    assert card["mastcam"] is None or card["mastcam"]["img"].startswith("/bundle/")


def test_one_degree_of_latitude():
    # 1° of latitude on the Mars sphere ≈ 59,274 m (value used in M3)
    assert haversine(0, 137, 1, 137) == pytest.approx(59274.6, abs=1)


def test_initial_yaw_and_mast_az():
    # Bearing 65° with the panorama center at 65° -> opens at the center
    assert initial_yaw(65, 65) == 0
    assert initial_yaw(10, 350) == pytest.approx(20)
    # M6: true azimuth = mast_az + rover yaw
    assert photo_azimuth(343.12, 65.13) == pytest.approx(48.25)
    assert bearing(0, 137, 1, 137) == pytest.approx(0)


@pytest.mark.skipif(not (F03_PIPELINE / PUB["places_file"]).exists(), reason="PLACES not downloaded")
def test_landing_site_in_places():
    from etl.sources.public import PublicPositions

    pos = PublicPositions(F03_PIPELINE / PUB["waypoints_file"], F03_PIPELINE / PUB["places_file"])
    landing = pos.places(1, 0)
    assert landing is not None
    assert landing.lat == pytest.approx(-4.58947, abs=1e-5)  # planetocentric
    assert landing.lon == pytest.approx(137.44163, abs=1e-5)


@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_known_stop_returns_its_own_panorama():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    # Stop 118_2028 (sol 4643) in MMGIS
    r = c.get("/panoramas/nearest", params={"lat": -4.80679651, "lon": 137.3794121}).json()
    assert r["found"] and r["rmc"] == "118_2028"
    assert r["distance_m"] < 10
    photos = c.get("/photos/near", params={"lat": -4.80679651, "lon": 137.3794121}).json()
    assert photos["total"] > 0
    assert c.get("/orbital/crop", params={"lat": -4.80679651, "lon": 137.3794121}).status_code == 200


@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_negative_longitude_and_outside_window():
    from fastapi.testclient import TestClient

    from main import app

    c = TestClient(app)
    r = c.get("/panoramas/nearest", params={"lat": -4.80679651, "lon": 137.3794121 - 360}).json()
    assert r["found"] and r["rmc"] == "118_2028"
    outside = c.get("/panoramas/nearest", params={"lat": 10, "lon": 10}).json()
    assert outside["found"] is False and outside["inside_window"] is False


# --------------------------------------------------------------------------- #
# F04 · science card (task 1: contract + mock)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_mojo_card_at_stop_118_2028():
    import sqlite3
    from science_card import science_card
    from panorama import R_CARD

    lat, lon = sqlite3.connect(DB_PATH).execute(
        "SELECT lat, lon FROM waypoints WHERE rmc = '118_2028'").fetchone()
    j = science_card(lat, lon, R_CARD)
    assert j["target"]["name"] == "Mojo"
    assert j["target"]["distance_m"] < 10
    assert j["position_warning"] == "position approximated by the stop of sol 4643"
    assert any(l["section"] == "chemistry" for l in j["rows"])
    assert j["mastcam"]["img"].startswith("/bundle/")  # offline: never an external URL
    assert all(l["source_url"] or l["source_file"] for l in j["rows"] + j["context"])


@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_card_without_nearby_target_and_outside_window():
    from science_card import science_card
    from panorama import R_CARD

    far = science_card(-4.8100, 137.3770, R_CARD)
    assert far["target"] is None and "no studied target within 150 m" in far["message"]
    # CRISM (task 5) not wired yet: the public source does not invent an orbit row
    assert not any(l["section"] == "orbit" and l["confidence"] == "mock" for l in far["rows"])
    outside = science_card(-10.0, 137.38, R_CARD)
    assert outside["target"] is None and outside["inside_window"] is False and outside["rows"] == []


# --------------------------------------------------------------------------- #
# F04 · tasks 3 and 4: real PDS measurements (science_source: public)
# --------------------------------------------------------------------------- #


def test_rule_based_pds_summary():
    from etl.sources.science_public import summary_apxs, summary_chemin

    assert summary_chemin([("Plagioclase", 51, 0), ("Quartz", 1.6, 0)]) == \
        "Crystalline fraction: plagioclase 51.0% · quartz 1.6%."
    assert summary_apxs({"SiO2": (43.17, 0.1), "Br": (0.0088, 0)}) == "Major oxides: SiO2 43.2%."


@pytest.mark.skipif(not BUNDLE_BUILT, reason="bundle not built")
def test_altadena_card_shows_only_the_latest_measurement():
    import sqlite3
    from science_card import science_card
    from panorama import R_CARD

    lat, lon = sqlite3.connect(DB_PATH).execute(
        "SELECT lat, lon FROM waypoints WHERE rmc = '116_1944'").fetchone()
    j = science_card(lat, lon, R_CARD)
    assert j["target"]["name"] == "Altadena"
    measured = [l for l in j["rows"] if l["section"] in ("chemistry", "mineralogy")]
    assert len(measured) == 1 and measured[0]["confidence"] == "measured"  # latest only, not one per sol
    assert measured[0]["sol"] == 4570 and measured[0]["instrument"] == "APXS"
    assert not any(l["confidence"] == "mock" for l in j["rows"])
