"""Fábrica de fontes: devolve (posições, panoramas, fotos) para o nome pedido."""

from __future__ import annotations

from pathlib import Path


def make_sources(name: str, cfg: dict, base_dir: Path, cache_dir: Path, waypoints_file: Path | None = None):
    if name == "mock":
        from .mock import MockPanos, MockPhotos, MockPositions
        return MockPositions(), MockPanos(), MockPhotos()
    if name == "official":
        from .official import OfficialPanos, OfficialPhotos, OfficialPositions
        return OfficialPositions(), OfficialPanos(), OfficialPhotos()
    if name == "public":
        from .public import PublicPanos, PublicPhotos, PublicPositions
        pub, ph = cfg["public"], cfg["photos"]
        positions = PublicPositions(
            waypoints_file or base_dir / pub["waypoints_file"], base_dir / pub["places_file"]
        )
        panos = PublicPanos(base_dir / pub["panoramas_csv"], base_dir / pub["panoramas_root"])
        photos = PublicPhotos(
            pub["raw_images_api"], cache_dir, pub["request_delay_s"], ph["per_stop"],
            ph["el_min"], ph["el_max"], ph["min_az_sep"],
        )
        return positions, panos, photos
    raise ValueError(f"fonte desconhecida: {name!r} (use mock | public | official)")
