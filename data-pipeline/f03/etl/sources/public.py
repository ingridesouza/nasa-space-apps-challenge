"""Fonte pública: MMGIS, PLACES, páginas de panorama do science.nasa.gov e o
feed de imagens brutas do MSL.

As respostas da API ficam em cache (data/local/f03-cache/), então um segundo build roda sem
internet.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import time
from pathlib import Path

import requests

from .base import PanoMeta, PhotoMeta, Position

USER_AGENT = "H2G2-DETON8/1.0 (NASA Space Apps Salvador 2026; uso educacional)"


def _norm_az(a: float) -> float:
    return (a % 360 + 360) % 360


def _iso_date(texto: str) -> str:
    """'May 27, 2025' -> '2025-05-27'; devolve '' se não reconhecer."""
    try:
        return dt.datetime.strptime(texto.strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""


class PublicPositions:
    """MMGIS primeiro (busca exata do RMC); PLACES como reserva para drives
    intermediários. Latitude sempre planetocêntrica (M3)."""

    def __init__(self, waypoints_file: Path, places_file: Path):
        feats = json.loads(waypoints_file.read_text(encoding="utf-8"))["features"]
        self._mmgis: dict[str, Position] = {}
        for f in feats:
            p = f["properties"]
            if p.get("site") is None or p.get("drive") is None:
                continue
            self._mmgis[p["RMC"]] = Position(
                rmc=p["RMC"], site=int(p["site"]), drive=int(p["drive"]),
                sol=p.get("sol"), lat=float(p["lat"]), lon=float(p["lon"]) % 360,
                elev=p.get("elev_geoid"),
                yaw=_norm_az(p["yaw"]) if p.get("yaw") is not None else None,
                source="mmgis",
            )
        self._places_file = places_file
        self._places: dict[tuple[int, int], Position] | None = None

    def _load_places(self) -> dict[tuple[int, int], Position]:
        if self._places is None:
            self._places = {}
            if self._places_file.exists():
                with open(self._places_file, newline="", encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        if r["frame"] != "ROVER":
                            continue
                        site, drive = int(r["site"]), int(r["drive"])
                        self._places[(site, drive)] = Position(
                            rmc=f"{site}_{drive}", site=site, drive=drive,
                            sol=int(r["sol"]) if r["sol"] not in ("", "-1") else None,
                            lat=float(r["planetocentric_latitude"]),
                            lon=float(r["longitude"]) % 360,
                            elev=float(r["elevation"]) if r["elevation"] else None,
                            yaw=_norm_az(float(r["yaw"])) if r["yaw"] else None,
                            source="places",
                        )
        return self._places

    def locate(self, site, drive, sol=None):
        return self._mmgis.get(f"{site}_{drive}") or self._load_places().get((site, drive))

    def places(self, site, drive):
        return self._load_places().get((site, drive))

    def list_stops(self, sol_min, sol_max):
        return sorted(
            (p for p in self._mmgis.values() if p.sol is not None and sol_min <= p.sol <= sol_max),
            key=lambda p: (p.sol, p.site, p.drive),
        )


class PublicPanos:
    """Lê o panoramas.csv gerado por coletar_panoramas.py (M4/M5).
    Só entram as linhas baixadas (selecionado = sim)."""

    def __init__(self, csv_file: Path, root: Path):
        self.csv_file, self.root = csv_file, root

    def list_panoramas(self, sol_min, sol_max):
        out = []
        with open(self.csv_file, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("selecionado") != "sim" or not r.get("arquivo_local"):
                    continue
                if not r.get("rmc") or not r.get("azimute_central"):
                    continue
                sol = int(r["sol"])
                if not sol_min <= sol <= sol_max:
                    continue
                site, drive = (int(x) for x in r["rmc"].split("_"))
                out.append(PanoMeta(
                    id=f"{sol}_{site}_{drive}", sol=sol, site=site, drive=drive,
                    center_az=_norm_az(float(r["azimute_central"])),
                    image=str(self.root / r["arquivo_local"]),
                    page_url=r.get("page_url", ""),
                    credit=r.get("credito") or "NASA/JPL-Caltech",
                    date=_iso_date(r.get("data_captura", "")),
                ))
        return out


class PublicPhotos:
    """Feed de imagens brutas do MSL. Consulta por sol de cada parada e fica só
    com fotos tiradas na própria parada (mesmo site/drive), de corpo inteiro,
    olhando perto do horizonte e com azimutes espaçados."""

    CAMERAS = ("NAV_LEFT_B", "NAV_RIGHT_B")

    def __init__(self, api_url: str, cache_dir: Path, delay: float, per_stop: int,
                 el_min: float, el_max: float, min_az_sep: float):
        self.api_url, self.cache_dir, self.delay = api_url, cache_dir, delay
        self.per_stop, self.el_min, self.el_max, self.min_az_sep = per_stop, el_min, el_max, min_az_sep
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _query(self, sol: int, camera: str) -> list[dict]:
        cache = self.cache_dir / f"raw_{sol}_{camera}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        items, page = [], 0
        while True:
            r = self.session.get(self.api_url, timeout=60, params={
                "order": "sol desc", "per_page": 100, "page": page,
                "condition_1": "msl:mission", "condition_2": f"{sol}:sol:eq",
                "search": camera, "extended": "thumbnail::sample_type::noteq",
            })
            r.raise_for_status()
            batch = r.json().get("items", [])
            items += batch
            time.sleep(self.delay)
            if len(batch) < 100:
                break
            page += 1
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(items), encoding="utf-8")
        return items

    def _candidates(self, stop: Position) -> list[PhotoMeta]:
        out = []
        for cam in self.CAMERAS:
            for it in self._query(stop.sol, cam):
                ext = it.get("extended") or {}
                if (it.get("site"), it.get("drive")) != (stop.site, stop.drive):
                    continue
                if ext.get("sample_type") != "full" or it.get("is_thumbnail"):
                    continue
                if ext.get("mast_az") in (None, "") or ext.get("mast_el") in (None, ""):
                    continue
                if it.get("subframe_rect") != "(1,1,1024,1024)":
                    continue  # só quadros inteiros; recortes confundem a faixa de fotos
                el = float(ext["mast_el"])
                if not self.el_min <= el <= self.el_max:
                    continue
                out.append(PhotoMeta(
                    id=it["imageid"], instrument=it["instrument"], sol=it["sol"],
                    site=it["site"], drive=it["drive"],
                    date_taken=(it.get("date_taken") or "")[:10],
                    mast_az=float(ext["mast_az"]), mast_el=el,
                    image=it.get("https_url") or it.get("url"),
                    credit=it.get("image_credit") or "NASA/JPL-Caltech",
                    source="msl_raw_images",
                ))
        return out

    def _spread(self, cands: list[PhotoMeta]) -> list[PhotoMeta]:
        """Escolhe até per_stop fotos com azimutes separados, preferindo as mais
        perto do horizonte e a câmera esquerda (a da M6)."""
        cands = sorted(cands, key=lambda p: (abs(p.mast_el + 5), p.instrument != "NAV_LEFT_B"))
        picked: list[PhotoMeta] = []
        for c in cands:
            if all(abs(((c.mast_az - p.mast_az + 180) % 360) - 180) >= self.min_az_sep for p in picked):
                picked.append(c)
            if len(picked) == self.per_stop:
                break
        return picked

    def list_photos(self, sol_min, sol_max, stops):
        out = []
        for stop in stops:
            if stop.sol is None or not sol_min <= stop.sol <= sol_max:
                continue
            out += self._spread(self._candidates(stop))
        return out


def refresh_waypoints(url: str, dest_dir: Path) -> Path:
    """Baixa o MSL_waypoints.json e salva com a data no nome (tarefa 2)."""
    r = requests.get(url, timeout=120, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    dest = dest_dir / f"waypoints_{dt.date.today().isoformat()}.json"
    dest.write_bytes(r.content)
    return dest
