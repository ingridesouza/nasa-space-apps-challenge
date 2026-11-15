"""F04 · public source: M8 targets + PDS measurements (APXS, ChemCam, CheMin) + CRISM.

Target position (task 3):
- `exact`: the target name appears in a ChemCam target in the PDS; the stop of that record applies.
- `by_sol`: the name does not appear; the stop the PDS records on the reference sol applies
  (or on the closest sol within the M8 range).

Measurements (task 4): the target gets what was measured at the same stop, within the M8
sol range. Each row carries the target name in the PDS, the sol and the source file.
Sentences by a fixed rule (the 3 largest values + highlights), never free text.

Downloaded files stay in `data/pds/` so the ETL runs without internet.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

from .base import Measurement, OrbitalLabel, Target

PDS = "https://pds-geosciences.wustl.edu"
MOC_URL = f"{PDS}/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/data/moc/"
MOC_FILES = ("moc_4489_4612.csv", "moc_4613_4709.csv", "moc_4710_4843.csv")
MOC_OXIDES = ("SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O", "MnO")
MOC_NAME = re.compile(r"F(\d{3})(\d{4})CCAM", re.I)
MAST_CREDIT = "NASA/JPL-Caltech/MSSS"
MAX_PER_INSTRUMENT = {"APXS": 3, "ChemCam": 4, "CheMin": 2}

MINERAL_NAMES = {
    "plagioclase": "plagioclase", "pyroxene": "pyroxene", "anhydrite": "anhydrite",
    "bassanite": "bassanite", "gypsum": "gypsum", "hematite": "hematite",
    "goethite": "goethite", "magnetite": "magnetite", "siderite": "siderite",
    "quartz": "quartz", "jarosite": "jarosite", "olivine": "olivine",
    "sanidine": "sanidine", "akaganeite": "akaganeite", "calcite": "calcite",
    "dolomite": "dolomite", "smectite": "smectite", "phyllosilicate": "phyllosilicate",
    "starkeyite": "starkeyite", "kieserite": "kieserite", "halite": "halite",
    "opal-ct": "opal-CT", "cristobalite": "cristobalite", "tridymite": "tridymite",
}
SULFATES = {"anhydrite", "bassanite", "gypsum", "jarosite", "starkeyite", "kieserite"}
CARBONATES = {"siderite", "calcite", "dolomite"}
CLAYS = {"smectite", "phyllosilicate"}
FE_OXIDES = {"hematite", "goethite", "magnetite", "akaganeite"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s)


def _pct(v: float) -> str:
    return f"{v:.1f}%"


# the "type" column of m8_targets.csv is curated text: substring -> kind
_KIND = (("drill", "drill_hole"), ("ridge", "ridge"), ("hollow", "hollow"), ("contact", "contact"))


def _kind(type_text: str) -> str:
    t = type_text.lower()
    return next((v for k, v in _KIND if k in t), "feature")


def _download(url: str, dest: Path, offline: bool) -> Path | None:
    if dest.exists() and dest.stat().st_size:
        return dest
    if offline:
        return None
    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest


# --------------------------------------------------------------------------- #
# Reading the PDS files
# --------------------------------------------------------------------------- #


def read_apxs(path: Path) -> dict[str, tuple[float, float]]:
    """APXS RWP: oxide -> (weight %, uncertainty)."""
    out = {}
    with path.open(encoding="utf-8", errors="replace") as f:
        for cols in csv.reader(f):
            if len(cols) < 3:
                continue
            try:
                out[cols[0].strip()] = (float(cols[1]), float(cols[2]))
            except ValueError:
                continue
    return out


def read_chemin(path: Path) -> list[tuple[str, float, float]]:
    """CheMin MIN: (mineral, %, error), in decreasing order."""
    out = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["MINERAL"].strip(), float(r["PERCENT"]), float(r["ERROR"])))
            except (KeyError, ValueError):
                continue
    return sorted(out, key=lambda x: -x[1])


def read_moc(paths: list[Path]) -> dict[tuple[int, int, str], list[dict[str, float]]]:
    """ChemCam MOC table: (site, drive, target) -> list of points {oxide: %}."""
    out: dict[tuple[int, int, str], list[dict[str, float]]] = defaultdict(list)
    for p in paths:
        with p.open(encoding="utf-8", errors="replace") as f:
            for cols in csv.reader(f):
                if not cols or not cols[0].upper().startswith("CL5_"):
                    continue
                m = MOC_NAME.search(cols[0])
                if not m:
                    continue
                try:
                    vals = {ox: float(cols[2 + 4 * i]) for i, ox in enumerate(MOC_OXIDES)}
                except (ValueError, IndexError):
                    continue
                out[(int(m.group(1)), int(m.group(2)), cols[1].strip())].append(vals)
    return out


# --------------------------------------------------------------------------- #
# Fixed-rule sentences
# --------------------------------------------------------------------------- #


def summary_apxs(ox: dict[str, tuple[float, float]]) -> str:
    oxides = {k: v for k, v in ox.items() if k not in ("Ni", "Zn", "Br", "Cl")}
    top = sorted(oxides.items(), key=lambda kv: -kv[1][0])[:3]
    txt = "Major oxides: " + " · ".join(f"{k} {_pct(v[0])}" for k, v in top) + "."
    so3, cao = ox.get("SO3", (0, 0))[0], ox.get("CaO", (0, 0))[0]
    if so3 >= 8 and cao >= 8:
        txt += f" High calcium and sulfur together (CaO {_pct(cao)}, SO3 {_pct(so3)}), consistent with calcium sulfate."
    elif so3 >= 8:
        txt += f" Elevated sulfur (SO3 {_pct(so3)}), consistent with sulfates."
    return txt


def summary_chemcam(pds_name: str, pts: list[dict[str, float]]) -> tuple[str, dict]:
    mean = {ox: round(sum(p[ox] for p in pts) / len(pts), 2) for ox in MOC_OXIDES}
    top = sorted(mean.items(), key=lambda kv: -kv[1])[:3]
    txt = (f"Mean of {len(pts)} laser point(s) on target {pds_name}: "
           + " · ".join(f"{k} {_pct(v)}" for k, v in top) + ".")
    if mean["CaO"] >= 8:
        txt += f" High calcium (CaO {_pct(mean['CaO'])})."
    return txt, mean


def summary_chemin(mins: list[tuple[str, float, float]]) -> str:
    def nm(n):
        return MINERAL_NAMES.get(n.lower(), n)

    txt = ("Crystalline fraction: " + " · ".join(f"{nm(n)} {_pct(v)}" for n, v, _ in mins[:3]) + ".")
    for name, group in (("Sulfates", SULFATES), ("Carbonates", CARBONATES), ("Clays", CLAYS),
                        ("Iron oxides", FE_OXIDES)):
        found = [f"{nm(n)} {_pct(v)}" for n, v, _ in mins if n.lower() in group]
        if found:
            txt += f" {name}: {', '.join(found)}."
    return txt


# --------------------------------------------------------------------------- #
# Source
# --------------------------------------------------------------------------- #


class PublicScience:
    def __init__(self, targets_csv: Path, index_csv: Path, pds_dir: Path, mastcam_dir: Path,
                 offline: bool = False):
        self.targets_csv, self.index_csv = Path(targets_csv), Path(index_csv)
        self.pds_dir, self.mastcam_dir, self.offline = Path(pds_dir), Path(mastcam_dir), offline
        self._picked: list[tuple[Target, dict, set[str]]] = []

    def _rows(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _mastcam(self, url: str) -> str:
        """Downloads the photo once into data/mastcam/; the card only uses the local file."""
        if not url:
            return ""
        dest = self.mastcam_dir / url.rsplit("/", 1)[-1]
        try:
            return dest.name if _download(url, dest, self.offline) else ""
        except requests.RequestException:
            return ""

    def list_targets(self, stops):
        by_rmc = {p.rmc: p for p in stops}
        idx = [r for r in self._rows(self.index_csv) if r["instrument"] != "ChemCam RMI"]
        self._picked = []
        out = []
        for r in self._rows(self.targets_csv):
            a, b = (int(x) for x in r["sol_range"].split("-"))
            ref = int(r["sol_ref"])
            in_range = [x for x in idx if a <= int(x["sol"]) <= b]
            key = _norm(r["target"]).split("_")[0]
            names = [x for x in in_range if x["target"] and len(key) >= 4 and key in _norm(x["target"])]
            if names:
                rmc = Counter(f"{x['site']}_{x['drive']}" for x in names).most_common(1)[0][0]
                quality = "exact"
            elif in_range:
                x = min(in_range, key=lambda x: (abs(int(x["sol"]) - ref), int(x["sol"])))
                rmc, quality = f"{x['site']}_{x['drive']}", "by_sol"
            else:
                continue
            p = by_rmc.get(rmc)
            if p is None:
                continue
            blog = (r["blog_posts"] or "").split(" | ")[0]
            t = Target(
                id=f"t{int(r['id']):02d}", name=r["target"], kind=_kind(r["type"]), sol=ref,
                site=p.site, drive=p.drive, lat=p.lat, lon=p.lon, pos_quality=quality,
                why_it_matters=(r.get("why_it_matters") or "").strip(),
                safety_note=(r.get("safety_note") or "").strip(),
                blog_url=(r.get("phrases_source") or "").strip() or blog,
                mastcam_path=self._mastcam(r.get("mastcam_link", "")),
                mastcam_credit=MAST_CREDIT if r.get("mastcam_link") else "",
                what_was_done=(r.get("what_was_done") or "").strip(),
                what_was_done_url=blog,
            )
            self._picked.append((t, {"a": a, "b": b}, {_norm(x["target"]) for x in names}))
            out.append(t)
        return out

    def list_measurements(self, sol_min, sol_max):
        idx = self._rows(self.index_csv)
        moc = read_moc([p for p in (_download(MOC_URL + f, self.pds_dir / "chemcam" / f, self.offline)
                                    for f in MOC_FILES) if p])
        out: list[Measurement] = []
        for t, sol_range, names in self._picked:
            ref = t.sol
            here = [x for x in idx if int(x["site"]) == t.site and int(x["drive"]) == t.drive
                    and sol_range["a"] <= int(x["sol"]) <= sol_range["b"] and sol_min <= int(x["sol"]) <= sol_max]
            here.sort(key=lambda x: (abs(int(x["sol"]) - ref), x["file"]))
            out += self._apxs(t, [x for x in here if x["instrument"] == "APXS"])
            out += self._chemin(t, [x for x in here if x["instrument"] == "CheMin"])
            out += self._chemcam(t, [x for x in here if x["instrument"] == "ChemCam LIBS"], moc, names)
        return out

    def _meas(self, t, inst, n, sol, summary, values, url, file):
        return Measurement(
            id=f"{t.id}_{inst.lower()}_{n}", target_id=t.id, instrument=inst, sol=sol,
            site=t.site, drive=t.drive, summary=summary,
            values_json=json.dumps(values, ensure_ascii=False), confidence="measured",
            source_url=url, source_file=file)

    def _apxs(self, t, rows):
        out = []
        for x in rows:
            p = _download(x["url"], self.pds_dir / "apxs" / x["file"], self.offline)
            ox = read_apxs(p) if p else {}
            if not ox:
                continue
            out.append(self._meas(t, "APXS", len(out), int(x["sol"]), summary_apxs(ox),
                                  {k: {"pct": v, "uncertainty": e} for k, (v, e) in ox.items()},
                                  x["url"], x["file"]))
            if len(out) == MAX_PER_INSTRUMENT["APXS"]:
                break
        return out

    def _chemin(self, t, rows):
        out = []
        for x in rows[:MAX_PER_INSTRUMENT["CheMin"]]:
            p = _download(x["url"], self.pds_dir / "chemin" / x["file"], self.offline)
            mins = read_chemin(p) if p else []
            if mins:
                out.append(self._meas(t, "CheMin", len(out), int(x["sol"]), summary_chemin(mins),
                                      [{"mineral": n, "pct": v, "error": e} for n, v, e in mins],
                                      x["url"], x["file"]))
        return out

    def _chemcam(self, t, rows, moc, names):
        # one record per PDS target; a name matching the M8 target comes first
        seen, out = set(), []
        rows = sorted(rows, key=lambda x: (_norm(x["target"]) not in names,
                                           abs(int(x["sol"]) - t.sol)))
        for x in rows:
            if x["target"] in seen:
                continue
            seen.add(x["target"])
            pts = moc.get((t.site, t.drive, x["target"]))
            if not pts:
                continue
            txt, mean = summary_chemcam(x["target"], pts)
            out.append(self._meas(t, "ChemCam", len(out), int(x["sol"]), txt,
                                  {"pds_target": x["target"], "points": len(pts), "mean_pct": mean},
                                  MOC_URL, x["file"]))
            if len(out) == MAX_PER_INSTRUMENT["ChemCam"]:
                break
        return out


# --------------------------------------------------------------------------- #
# CRISM (task 5): crop precomputed by etl/crism.py
# --------------------------------------------------------------------------- #

# Conservative thresholds chosen by the H2G2 team (not official values).
# Below them the pixel is "no strong mineral signal".
CRISM_PARAMS = {
    "SINDEX2": ("polyhydrated sulfate", 0.02),
    "BD2100_2": ("monohydrated sulfate", 0.01),
    "BD1900_2": ("hydrated mineral", 0.01),
    "D2300": ("Fe/Mg clay", 0.01),
    "BD2210_2": ("Al-OH clay or silica", 0.01),
}


class PublicOrbital:
    def __init__(self, crop_json: Path):
        self.path = Path(crop_json)
        self._d = None

    def _data(self):
        if self._d is None and self.path.exists():
            self._d = json.loads(self.path.read_text(encoding="utf-8"))
        return self._d

    def sample(self, lat, lon):
        d = self._data()
        if not d:
            return None
        col = int((lon - d["lon_min"]) / d["deg_px_lon"])
        row = int((d["lat_max"] - lat) / d["deg_px_lat"])
        if not (0 <= row < d["rows"] and 0 <= col < d["cols"]):
            return None
        vals = {k: d["bands"][k][row][col] for k in CRISM_PARAMS}
        if any(v is None for v in vals.values()):
            return None
        above = [(v / CRISM_PARAMS[k][1], k) for k, v in vals.items() if v >= CRISM_PARAMS[k][1]]
        fmt = lambda v: f"{v:.3f}"  # noqa: E731
        if above:
            _, k = max(above)
            label = f"sign of {CRISM_PARAMS[k][0]} ({k} = {fmt(vals[k])})"
        else:
            k = max(vals, key=lambda k: vals[k] / CRISM_PARAMS[k][1])
            label = (f"no strong mineral signal in this pixel; highest index: {CRISM_PARAMS[k][0]} "
                     f"({k} = {fmt(vals[k])}, below the threshold {fmt(CRISM_PARAMS[k][1])})")
        product = d["product"]
        return OrbitalLabel(label, "inferred from orbit",
                            f"mean of an area of ~{d['res_m']:.0f} m; product {product}",
                            d["url"], f"CRISM MTRDR {product} (PDS Geosciences)")
