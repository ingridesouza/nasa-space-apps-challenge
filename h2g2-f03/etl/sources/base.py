"""Contrato de dados do ETL.

O ETL só conversa com estas interfaces. Cada fonte (mock, public, official)
implementa as três; trocar de fonte não muda o resto da feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class Position:
    """Uma parada do rover (linha da tabela `waypoints`)."""

    rmc: str            # "site_drive", ex. "118_2028"
    site: int
    drive: int
    sol: int | None
    lat: float          # planetocêntrica, graus
    lon: float          # leste positivo, 0–360
    elev: float | None
    yaw: float | None   # rumo da frente do rover, 0–360 a partir do norte
    source: str         # "mmgis" | "places" | "mock"


@dataclass
class PanoMeta:
    """Um panorama Navcam (linha da tabela `panoramas`, antes da posição)."""

    id: str
    sol: int
    site: int
    drive: int
    center_az: float        # azimute do centro da imagem, a partir do norte
    image: str              # caminho local ou URL do arquivo original
    page_url: str = ""
    credit: str = "NASA/JPL-Caltech"
    date: str = ""          # data terrestre da captura (ISO), se conhecida


@dataclass
class PhotoMeta:
    """Uma foto Navcam estática (linha da tabela `photos`, antes da posição)."""

    id: str
    instrument: str
    sol: int
    site: int
    drive: int
    date_taken: str
    mast_az: float          # medido a partir da frente do rover (M6)
    mast_el: float
    image: str              # URL ou caminho do JPG
    credit: str = "NASA/JPL-Caltech"
    source: str = ""


class PositionSource(Protocol):
    def locate(self, site: int, drive: int, sol: int | None) -> Position | None: ...

    def list_stops(self, sol_min: int, sol_max: int) -> Iterable[Position]: ...


class PanoSource(Protocol):
    def list_panoramas(self, sol_min: int, sol_max: int) -> Iterable[PanoMeta]: ...


class PhotoSource(Protocol):
    def list_photos(self, sol_min: int, sol_max: int, stops: list[Position]) -> Iterable[PhotoMeta]: ...
