"""Fonte de teste: poucas paradas inventadas perto do boxwork, sem imagens.

Serve para rodar o ETL e a API sem internet e sem os arquivos públicos.
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
# F04 · ficha científica (valores de exemplo, marcados confidence = "mock")
# --------------------------------------------------------------------------- #

import csv
import json
from pathlib import Path

from .base import Measurement, OrbitalLabel, Target

_KIND = (("furo", "furo"), ("crista", "crista"), ("hollow", "hollow"),
         ("contato", "contato"), ("feição", "feição"))
_MAST_CREDIT = "NASA/JPL-Caltech/MSSS"


def _kind(tipo: str) -> str:
    t = tipo.lower()
    return next((v for k, v in _KIND if k in t), "feição")


class MockScience:
    """Os 10 alvos curados na M8 com medições de exemplo.

    A posição vem da parada citada em `parada_panorama_proxima`; sem parada
    citada, usa a parada mais próxima em sol. Em ambos os casos é por sol
    (`pos_quality = "por_sol"`): o vínculo exato é a tarefa 3.
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
            rmc = (r["parada_panorama_proxima"] or "").split(" ")[0]
            p = by_rmc.get(rmc) or min(
                (s for s in stops if s.sol is not None), key=lambda s: abs(s.sol - sol), default=None)
            if p is None:
                continue
            blog = (r["posts_blog"] or "").split(" | ")[0]
            out.append(Target(
                id=f"t{int(r['id']):02d}", name=r["alvo"], kind=_kind(r["tipo"]), sol=sol,
                site=p.site, drive=p.drive, lat=p.lat, lon=p.lon, pos_quality="por_sol",
                why_it_matters=r["o_que_foi_feito"], safety_note="", blog_url=blog,
                mastcam_path=r["mastcam_link"], mastcam_credit=_MAST_CREDIT))
        return out

    def list_measurements(self, sol_min, sol_max):
        out = []
        for r in self._rows():
            sol = int(r["sol_ref"])
            if not sol_min <= sol <= sol_max:
                continue
            tid = f"t{int(r['id']):02d}"
            # exemplo para a UI: APXS e ChemCam em todo alvo, CheMin só em furo
            insts = ("APXS", "ChemCam") + (("CheMin",) if _kind(r["tipo"]) == "furo" else ())
            for inst in insts:
                out.append(Measurement(
                    id=f"{tid}_{inst.lower()}", target_id=tid, instrument=inst, sol=sol,
                    site=None, drive=None,
                    summary=f"[exemplo] {inst}: valores de teste, não são medições reais.",
                    values_json=json.dumps({"mock": True}), confidence="mock",
                    source_url="https://pds-geosciences.wustl.edu/missions/msl/"
                               f"{inst.lower()}.htm", source_file="mock"))
        return out


class MockOrbital:
    def sample(self, lat, lon):
        return OrbitalLabel(
            "sem dado de órbita no mock", "mock",
            "exemplo: média de uma área de ~18 m",
            "https://ode.rsl.wustl.edu/mars/", "Orbital Data Explorer (CRISM)")
