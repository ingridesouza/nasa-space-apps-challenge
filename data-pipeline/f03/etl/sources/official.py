"""Official source (hackathon Resources). Written on Friday, after M11.

Same interface as the other sources; until the Resources arrive,
any call warns instead of returning invented data.
"""

from __future__ import annotations


class _NotYet:
    def _fail(self, *_args, **_kwargs):
        raise NotImplementedError(
            "Source 'official' not implemented yet: depends on the Resources (M11). "
            "Use source: public in config.yaml."
        )

    locate = list_stops = list_panoramas = list_photos = _fail


OfficialPositions = OfficialPanos = OfficialPhotos = _NotYet
