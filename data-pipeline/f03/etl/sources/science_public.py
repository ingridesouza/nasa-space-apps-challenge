"""F04 · fonte pública: alvos da M8 + medições do PDS (APXS, ChemCam, CheMin) + CRISM.

Posição do alvo (tarefa 3):
- `exata`: o nome do alvo aparece num alvo do ChemCam no PDS; vale a parada desse registro.
- `por_sol`: o nome não aparece; vale a parada que o PDS registra no sol de referência
  (ou no sol mais próximo dentro da faixa da M8).

Medições (tarefa 4): o alvo recebe o que foi medido na mesma parada, dentro da faixa
de sols da M8. Cada linha leva o nome do alvo no PDS, o sol e o arquivo de origem.
Frases por regra fixa (os 3 maiores valores + destaques), nunca texto livre.

Os arquivos baixados ficam em `dados/pds/` para o ETL rodar sem internet.
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
MAX_POR_INSTRUMENTO = {"APXS": 3, "ChemCam": 4, "CheMin": 2}

MINERAIS_PT = {
    "plagioclase": "plagioclásio", "pyroxene": "piroxênio", "anhydrite": "anidrita",
    "bassanite": "bassanita", "gypsum": "gipsita", "hematite": "hematita",
    "goethite": "goethita", "magnetite": "magnetita", "siderite": "siderita",
    "quartz": "quartzo", "jarosite": "jarosita", "olivine": "olivina",
    "sanidine": "sanidina", "akaganeite": "akaganeíta", "calcite": "calcita",
    "dolomite": "dolomita", "smectite": "esmectita", "phyllosilicate": "filossilicato",
    "starkeyite": "starkeyíta", "kieserite": "kieserita", "halite": "halita",
    "opal-ct": "opala-CT", "cristobalite": "cristobalita", "tridymite": "tridimita",
}
SULFATOS = {"anhydrite", "bassanite", "gypsum", "jarosite", "starkeyite", "kieserite"}
CARBONATOS = {"siderite", "calcite", "dolomite"}
ARGILAS = {"smectite", "phyllosilicate"}
OXIDOS_FE = {"hematite", "goethite", "magnetite", "akaganeite"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s)


def _pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + "%"


def _kind(tipo: str) -> str:
    t = tipo.lower()
    return next((k for k in ("furo", "crista", "hollow", "contato") if k in t), "feição")


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
# Leitura dos arquivos do PDS
# --------------------------------------------------------------------------- #


def read_apxs(path: Path) -> dict[str, tuple[float, float]]:
    """RWP do APXS: óxido -> (% em peso, incerteza)."""
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
    """MIN do CheMin: (mineral, %, erro), em ordem decrescente."""
    out = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["MINERAL"].strip(), float(r["PERCENT"]), float(r["ERROR"])))
            except (KeyError, ValueError):
                continue
    return sorted(out, key=lambda x: -x[1])


def read_moc(paths: list[Path]) -> dict[tuple[int, int, str], list[dict[str, float]]]:
    """Tabela MOC do ChemCam: (site, drive, alvo) -> lista de pontos {óxido: %}."""
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
# Frases por regra fixa
# --------------------------------------------------------------------------- #


def summary_apxs(ox: dict[str, tuple[float, float]]) -> str:
    oxidos = {k: v for k, v in ox.items() if k not in ("Ni", "Zn", "Br", "Cl")}
    top = sorted(oxidos.items(), key=lambda kv: -kv[1][0])[:3]
    txt = "Óxidos principais: " + " · ".join(f"{k} {_pct(v[0])}" for k, v in top) + "."
    so3, cao = ox.get("SO3", (0, 0))[0], ox.get("CaO", (0, 0))[0]
    if so3 >= 8 and cao >= 8:
        txt += f" Cálcio e enxofre altos juntos (CaO {_pct(cao)}, SO3 {_pct(so3)}), compatível com sulfato de cálcio."
    elif so3 >= 8:
        txt += f" Enxofre elevado (SO3 {_pct(so3)}), compatível com sulfatos."
    return txt


def summary_chemcam(nome_pds: str, pts: list[dict[str, float]]) -> tuple[str, dict]:
    media = {ox: round(sum(p[ox] for p in pts) / len(pts), 2) for ox in MOC_OXIDES}
    top = sorted(media.items(), key=lambda kv: -kv[1])[:3]
    txt = (f"Média de {len(pts)} ponto(s) de laser no alvo {nome_pds}: "
           + " · ".join(f"{k} {_pct(v)}" for k, v in top) + ".")
    if media["CaO"] >= 8:
        txt += f" Cálcio alto (CaO {_pct(media['CaO'])})."
    return txt, media


def summary_chemin(mins: list[tuple[str, float, float]]) -> str:
    def pt(n):
        return MINERAIS_PT.get(n.lower(), n)

    txt = ("Fração cristalina: " + " · ".join(f"{pt(n)} {_pct(v)}" for n, v, _ in mins[:3]) + ".")
    for nome, grupo in (("Sulfatos", SULFATOS), ("Carbonatos", CARBONATOS), ("Argilas", ARGILAS),
                        ("Óxidos de ferro", OXIDOS_FE)):
        achados = [f"{pt(n)} {_pct(v)}" for n, v, _ in mins if n.lower() in grupo]
        if achados:
            txt += f" {nome}: {', '.join(achados)}."
    return txt


# --------------------------------------------------------------------------- #
# Fonte
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
        """Baixa a foto uma vez para dados/mastcam/; o card só usa o arquivo local."""
        if not url:
            return ""
        dest = self.mastcam_dir / url.rsplit("/", 1)[-1]
        try:
            return dest.name if _download(url, dest, self.offline) else ""
        except requests.RequestException:
            return ""

    def list_targets(self, stops):
        by_rmc = {p.rmc: p for p in stops}
        idx = [r for r in self._rows(self.index_csv) if r["instrumento"] != "ChemCam RMI"]
        self._picked = []
        out = []
        for r in self._rows(self.targets_csv):
            a, b = (int(x) for x in r["faixa_sols"].split("-"))
            ref = int(r["sol_ref"])
            faixa = [x for x in idx if a <= int(x["sol"]) <= b]
            chave = _norm(r["alvo"]).split("_")[0]
            nomes = [x for x in faixa if x["alvo"] and len(chave) >= 4 and chave in _norm(x["alvo"])]
            if nomes:
                rmc = Counter(f"{x['site']}_{x['drive']}" for x in nomes).most_common(1)[0][0]
                qual = "exata"
            elif faixa:
                x = min(faixa, key=lambda x: (abs(int(x["sol"]) - ref), int(x["sol"])))
                rmc, qual = f"{x['site']}_{x['drive']}", "por_sol"
            else:
                continue
            p = by_rmc.get(rmc)
            if p is None:
                continue
            blog = (r["posts_blog"] or "").split(" | ")[0]
            t = Target(
                id=f"t{int(r['id']):02d}", name=r["alvo"], kind=_kind(r["tipo"]), sol=ref,
                site=p.site, drive=p.drive, lat=p.lat, lon=p.lon, pos_quality=qual,
                why_it_matters=(r.get("por_que_importa") or "").strip(),
                safety_note=(r.get("nota_seguranca") or "").strip(),
                blog_url=(r.get("fonte_frases") or "").strip() or blog,
                mastcam_path=self._mastcam(r.get("mastcam_link", "")),
                mastcam_credit=MAST_CREDIT if r.get("mastcam_link") else "",
                what_was_done=(r.get("o_que_foi_feito") or "").strip(),
                what_was_done_url=blog,
            )
            self._picked.append((t, {"a": a, "b": b}, {_norm(x["alvo"]) for x in nomes}))
            out.append(t)
        return out

    def list_measurements(self, sol_min, sol_max):
        idx = self._rows(self.index_csv)
        moc = read_moc([p for p in (_download(MOC_URL + f, self.pds_dir / "chemcam" / f, self.offline)
                                    for f in MOC_FILES) if p])
        out: list[Measurement] = []
        for t, faixa, nomes in self._picked:
            ref = t.sol
            here = [x for x in idx if int(x["site"]) == t.site and int(x["drive"]) == t.drive
                    and faixa["a"] <= int(x["sol"]) <= faixa["b"] and sol_min <= int(x["sol"]) <= sol_max]
            here.sort(key=lambda x: (abs(int(x["sol"]) - ref), x["arquivo"]))
            out += self._apxs(t, [x for x in here if x["instrumento"] == "APXS"])
            out += self._chemin(t, [x for x in here if x["instrumento"] == "CheMin"])
            out += self._chemcam(t, [x for x in here if x["instrumento"] == "ChemCam LIBS"], moc, nomes)
        return out

    def _med(self, t, inst, n, sol, summary, values, url, arquivo):
        return Measurement(
            id=f"{t.id}_{inst.lower()}_{n}", target_id=t.id, instrument=inst, sol=sol,
            site=t.site, drive=t.drive, summary=summary,
            values_json=json.dumps(values, ensure_ascii=False), confidence="medido",
            source_url=url, source_file=arquivo)

    def _apxs(self, t, rows):
        out = []
        for x in rows:
            p = _download(x["url"], self.pds_dir / "apxs" / x["arquivo"], self.offline)
            ox = read_apxs(p) if p else {}
            if not ox:
                continue
            out.append(self._med(t, "APXS", len(out), int(x["sol"]), summary_apxs(ox),
                                 {k: {"pct": v, "incerteza": e} for k, (v, e) in ox.items()},
                                 x["url"], x["arquivo"]))
            if len(out) == MAX_POR_INSTRUMENTO["APXS"]:
                break
        return out

    def _chemin(self, t, rows):
        out = []
        for x in rows[:MAX_POR_INSTRUMENTO["CheMin"]]:
            p = _download(x["url"], self.pds_dir / "chemin" / x["arquivo"], self.offline)
            mins = read_chemin(p) if p else []
            if mins:
                out.append(self._med(t, "CheMin", len(out), int(x["sol"]), summary_chemin(mins),
                                     [{"mineral": n, "pct": v, "erro": e} for n, v, e in mins],
                                     x["url"], x["arquivo"]))
        return out

    def _chemcam(self, t, rows, moc, nomes):
        # um registro por alvo do PDS; nome que bate com o alvo da M8 vem primeiro
        vistos, out = set(), []
        rows = sorted(rows, key=lambda x: (_norm(x["alvo"]) not in nomes,
                                           abs(int(x["sol"]) - t.sol)))
        for x in rows:
            if x["alvo"] in vistos:
                continue
            vistos.add(x["alvo"])
            pts = moc.get((t.site, t.drive, x["alvo"]))
            if not pts:
                continue
            txt, media = summary_chemcam(x["alvo"], pts)
            out.append(self._med(t, "ChemCam", len(out), int(x["sol"]), txt,
                                 {"alvo_pds": x["alvo"], "pontos": len(pts), "media_pct": media},
                                 MOC_URL, x["arquivo"]))
            if len(out) == MAX_POR_INSTRUMENTO["ChemCam"]:
                break
        return out


# --------------------------------------------------------------------------- #
# CRISM (tarefa 5): recorte pré-calculado por etl/crism.py
# --------------------------------------------------------------------------- #

# Limiares conservadores escolhidos pela equipe H2G2 (não são valores oficiais).
# Abaixo deles o pixel é "sem sinal mineral forte".
CRISM_PARAMS = {
    "SINDEX2": ("sulfato poli-hidratado", 0.02),
    "BD2100_2": ("sulfato monoidratado", 0.01),
    "BD1900_2": ("mineral hidratado", 0.01),
    "D2300": ("argila Fe/Mg", 0.01),
    "BD2210_2": ("argila ou sílica com Al-OH", 0.01),
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
        acima = [(v / CRISM_PARAMS[k][1], k) for k, v in vals.items() if v >= CRISM_PARAMS[k][1]]
        fmt = lambda v: f"{v:.3f}".replace(".", ",")  # noqa: E731
        if acima:
            _, k = max(acima)
            label = f"indício de {CRISM_PARAMS[k][0]} ({k} = {fmt(vals[k])})"
        else:
            k = max(vals, key=lambda k: vals[k] / CRISM_PARAMS[k][1])
            label = (f"sem sinal mineral forte neste pixel; maior índice: {CRISM_PARAMS[k][0]} "
                     f"({k} = {fmt(vals[k])}, abaixo do limiar {fmt(CRISM_PARAMS[k][1])})")
        return OrbitalLabel(label, "inferido de órbita",
                            f"média de uma área de ~{d['res_m']:.0f} m; produto {d['produto']}",
                            d["url"], f"CRISM MTRDR {d['produto']} (PDS Geosciences)")
