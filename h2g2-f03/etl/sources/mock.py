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
