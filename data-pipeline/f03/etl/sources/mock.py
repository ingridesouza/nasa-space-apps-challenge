"""Test source: a few invented stops near the boxwork, no images.

Used to run the ETL and the API without internet and without the public files.
"""

from __future__ import annotations

from .base import PanoMeta, PhotoMeta, Position

_STOPS = [
    Position("900_0", 900, 0, 4600, -4.8040, 137.3800, None, 90.0, "mock"),
    Position("900_100", 900, 100, 4650, -4.8070, 137.3800, None, 180.0, "mock"),
    Position("900_200", 900, 200, 4700, -4.8080, 137.3810, None, 270.0, "mock"),
]


class MockPositions:
    def locate(self, site, drive, sol):
        return next((p for p in _STOPS if (p.site, p.drive) == (site, drive)), None)

    def list_stops(self, sol_min, sol_max):
        return [p for p in _STOPS if sol_min <= (p.sol or 0) <= sol_max]


class MockPanos:
    def list_panoramas(self, sol_min, sol_max):
        return [
            PanoMeta(f"mock_{p.rmc}", p.sol, p.site, p.drive, p.yaw or 0.0, image="")
            for p in _STOPS
        ]


class MockPhotos:
    def list_photos(self, sol_min, sol_max, stops):
        return [
            PhotoMeta(f"mock_photo_{p.rmc}", "NAV_LEFT_B", p.sol, p.site, p.drive,
                      "", 0.0, -10.0, image="", source="mock")
            for p in _STOPS
        ]


# --------------------------------------------------------------------------- #
# F04 · science card (example values, marked confidence = "mock")
# --------------------------------------------------------------------------- #

import csv
import json
from pathlib import Path

from .base import Measurement, OrbitalLabel, Target

# the "type" column of m8_targets.csv is curated text in Portuguese: substring -> kind
_KIND = (("furo", "drill_hole"), ("crista", "ridge"), ("hollow", "hollow"),
         ("contato", "contact"), ("feição", "feature"))
_MAST_CREDIT = "NASA/JPL-Caltech/MSSS"


def _kind(type_text: str) -> str:
    t = type_text.lower()
    return next((v for k, v in _KIND if k in t), "feature")


class MockScience:
    """The 10 targets curated in M8 with example measurements.

    The position comes from the stop cited in `nearest_panorama_stop`; with no stop
    cited, it uses the stop closest in sol. In both cases it is by sol
    (`pos_quality = "by_sol"`): the exact link is task 3.
    """

    def __init__(self, targets_csv: Path):
        self.csv = Path(targets_csv)

    def _rows(self):
        with self.csv.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def list_targets(self, stops):
        by_rmc = {p.rmc: p for p in stops}
        out = []
        for r in self._rows():
            sol = int(r["sol_ref"])
            rmc = (r["nearest_panorama_stop"] or "").split(" ")[0]
            p = by_rmc.get(rmc) or min(
                (s for s in stops if s.sol is not None), key=lambda s: abs(s.sol - sol), default=None)
            if p is None:
                continue
            blog = (r["blog_posts"] or "").split(" | ")[0]
            out.append(Target(
                id=f"t{int(r['id']):02d}", name=r["target"], kind=_kind(r["type"]), sol=sol,
                site=p.site, drive=p.drive, lat=p.lat, lon=p.lon, pos_quality="by_sol",
                why_it_matters=r["what_was_done"], safety_note="", blog_url=blog,
                mastcam_path=r["mastcam_link"], mastcam_credit=_MAST_CREDIT))
        return out

    def list_measurements(self, sol_min, sol_max):
        out = []
        for r in self._rows():
            sol = int(r["sol_ref"])
            if not sol_min <= sol <= sol_max:
                continue
            tid = f"t{int(r['id']):02d}"
            # example for the UI: APXS and ChemCam on every target, CheMin only on drill holes
            insts = ("APXS", "ChemCam") + (("CheMin",) if _kind(r["type"]) == "drill_hole" else ())
            for inst in insts:
                out.append(Measurement(
                    id=f"{tid}_{inst.lower()}", target_id=tid, instrument=inst, sol=sol,
                    site=None, drive=None,
                    summary=f"[example] {inst}: test values, not real measurements.",
                    values_json=json.dumps({"mock": True}), confidence="mock",
                    source_url="https://pds-geosciences.wustl.edu/missions/msl/"
                               f"{inst.lower()}.htm", source_file="mock"))
        return out


class MockOrbital:
    def sample(self, lat, lon):
        return OrbitalLabel(
            "no orbital data in the mock", "mock",
            "example: mean of an area of ~18 m",
            "https://ode.rsl.wustl.edu/mars/", "Orbital Data Explorer (CRISM)")
