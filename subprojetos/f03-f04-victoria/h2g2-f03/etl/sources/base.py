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


@dataclass
class Target:
    """Um alvo científico (linha da tabela `targets`). A posição é a da parada."""

    id: str
    name: str
    kind: str               # furo | crista | hollow | contato | feição
    sol: int
    site: int | None
    drive: int | None
    lat: float
    lon: float
    pos_quality: str        # exata | por_sol | estimada
    why_it_matters: str = ""
    safety_note: str = ""
    blog_url: str = ""
    mastcam_path: str = ""
    mastcam_credit: str = ""
    terrain_class: str = ""


@dataclass
class Measurement:
    """Uma medição do chão (linha da tabela `measurements`)."""

    id: str
    target_id: str
    instrument: str         # APXS | ChemCam | CheMin
    sol: int
    site: int | None
    drive: int | None
    summary: str            # uma frase, gerada por regra fixa
    values_json: str        # valores completos
    confidence: str         # medido | mock
    source_url: str = ""
    source_file: str = ""


@dataclass
class OrbitalLabel:
    """O que se vê de órbita num ponto (CRISM)."""

    label: str              # ex.: "sulfato monoidratado", "sem sinal"
    confidence: str         # "inferido de órbita" | "contexto" | "mock"
    note: str               # ressalva de escala
    source_url: str = ""
    source_name: str = ""


class PositionSource(Protocol):
    def locate(self, site: int, drive: int, sol: int | None) -> Position | None: ...

    def list_stops(self, sol_min: int, sol_max: int) -> Iterable[Position]: ...


class PanoSource(Protocol):
    def list_panoramas(self, sol_min: int, sol_max: int) -> Iterable[PanoMeta]: ...


class PhotoSource(Protocol):
    def list_photos(self, sol_min: int, sol_max: int, stops: list[Position]) -> Iterable[PhotoMeta]: ...


class ScienceSource(Protocol):
    def list_targets(self, stops: list[Position]) -> Iterable[Target]: ...

    def list_measurements(self, sol_min: int, sol_max: int) -> Iterable[Measurement]: ...


class OrbitalMineralSource(Protocol):
    def sample(self, lat: float, lon: float) -> OrbitalLabel | None: ...
