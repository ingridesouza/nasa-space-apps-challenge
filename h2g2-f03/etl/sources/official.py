"""Fonte oficial (Resources do hackathon). Escrita na sexta, depois da M11.

Mesma interface das outras fontes; enquanto os Resources não chegam,
qualquer chamada avisa em vez de devolver dado inventado.
"""

from __future__ import annotations


class _NotYet:
    def _fail(self, *_args, **_kwargs):
        raise NotImplementedError(
            "Fonte 'official' ainda não implementada: depende dos Resources (M11). "
            "Use source: public no config.yaml."
        )

    locate = list_stops = list_panoramas = list_photos = _fail


OfficialPositions = OfficialPanos = OfficialPhotos = _NotYet
