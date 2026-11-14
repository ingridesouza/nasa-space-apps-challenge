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


def make_science_sources(name: str, cfg: dict, base_dir: Path):
    """Fábrica da F04: devolve (ScienceSource, OrbitalMineralSource)."""
    if name == "mock":
        from .mock import MockOrbital, MockScience
        return MockScience(base_dir / cfg["science"]["targets_csv"]), MockOrbital()
    if name == "public":
        # CRISM (tarefa 5) ainda não existe: sem órbita em vez de órbita de exemplo
        from .science_public import PublicScience
        sci = cfg["science"]
        return (PublicScience(base_dir / sci["targets_csv"], base_dir / sci["index_csv"],
                              base_dir / ".cache" / "pds" / "rdr"), None)
    if name == "official":
        raise NotImplementedError(
            f"science_source '{name}' ainda não implementada (tarefas 3 a 5 da F04). "
            "Use science_source: mock no config.yaml.")
    raise ValueError(f"science_source desconhecida: {name!r} (use mock | public | official)")
