"""Source factory: returns (positions, panoramas, photos) for the requested name."""

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
    raise ValueError(f"unknown source: {name!r} (use mock | public | official)")


def make_science_sources(name: str, cfg: dict, base_dir: Path):
    """F04 factory: returns (ScienceSource, OrbitalMineralSource)."""
    if name == "mock":
        from .mock import MockOrbital, MockScience
        return MockScience(base_dir / cfg["science"]["targets_csv"]), MockOrbital()
    if name == "public":
        from .science_public import PublicOrbital, PublicScience
        sc = cfg["science"]
        return (PublicScience(base_dir / sc["targets_csv"], base_dir / sc["index_csv"],
                              base_dir / sc["pds_dir"], base_dir / sc["mastcam_dir"]),
                PublicOrbital(base_dir / cfg["crism"]["crop_json"]))
    if name == "official":
        raise NotImplementedError(
            f"science_source '{name}' not implemented yet (depends on the Resources tab, M1). "
            "Use science_source: public in config.yaml.")
    raise ValueError(f"unknown science_source: {name!r} (use mock | public | official)")
