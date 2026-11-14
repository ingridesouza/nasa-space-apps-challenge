"""F04 · tarefas 3 e 4: medições reais do PDS ligadas aos 10 alvos da M8.

Vínculo (tarefa 3), estrito de propósito: uma linha do `science_index.csv` só
vira medição de um alvo se foi feita na MESMA parada (site_drive) citada na M8
e dentro da faixa de sols do alvo. Parada citada "a N sol(s) de distância" é
aproximada e não liga nada: alvo sem vínculo mostra "sem medição publicada".

Valores (tarefa 4), sempre do arquivo do PDS, frase por regra fixa:
- APXS: óxidos em % de peso (RDR `apb_*.csv`).
- CheMin: minerais em % da fração cristalina (RDR `cmb_*min*.csv`).
- ChemCam LIBS: o RDR do índice é espectro, não composição; vira uma linha por
  alvo M8 com os alvos ChemCam analisados na parada, sem número.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import requests

from .base import Measurement
from .mock import MockScience

MINERAL_PT = {"Plagioclase": "plagioclásio", "Pyroxene": "piroxênio", "Anhydrite": "anidrita",
              "Bassanite": "bassanita", "Gypsum": "gipsita", "Hematite": "hematita",
              "Goethite": "goethita", "Magnetite": "magnetita", "Quartz": "quartzo",
              "Fe carbonate": "carbonato de ferro", "Siderite": "siderita", "Olivine": "olivina",
              "Sanidine": "sanidina", "Jarosite": "jarosita", "Akaganeite": "akaganeíta"}
TOP = 4  # maiores componentes citados na frase; o resto fica em values_json
CHEMCAM_RDR = "https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/"


def _num(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _parada_exata(campo: str) -> tuple[int, int] | None:
    """'116_1944 (sol 4564)' -> (116, 1944); parada 'a N sol(s) de distância' -> None."""
    m = re.match(r"(\d+)_(\d+)", campo or "")
    return None if not m or "distância" in campo else (int(m[1]), int(m[2]))


def ler_apxs(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as f:
        linhas = list(csv.reader(f))[1:]
    return {l[0].strip(): float(l[1]) for l in linhas if len(l) >= 2 and l[1].strip()}


def ler_chemin(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as f:
        return {r["MINERAL"].strip(): float(r["PERCENT"]) for r in csv.DictReader(f) if r["PERCENT"].strip()}


def frase_apxs(sol: int, ox: dict[str, float]) -> str:
    top = sorted(ox.items(), key=lambda kv: -kv[1])[:TOP]
    return f"APXS (sol {sol}): " + ", ".join(f"{k} {_num(v)}%" for k, v in top) + " (óxidos, % em peso)"


def frase_chemin(sol: int, mins: dict[str, float]) -> str:
    top = sorted(mins.items(), key=lambda kv: -kv[1])[:TOP]
    return (f"CheMin (sol {sol}): " + ", ".join(f"{MINERAL_PT.get(k, k)} {_num(v)}%" for k, v in top)
            + " (% da fração cristalina)")


class PublicScience(MockScience):
    """Mesmos alvos da M8 (herdados); medições lidas do PDS em vez de exemplo."""

    def __init__(self, targets_csv: Path, index_csv: Path, cache_dir: Path):
        super().__init__(targets_csv)
        self.index_csv = Path(index_csv)
        self.cache = Path(cache_dir)
        self.http = requests.Session()
        self.http.headers["User-Agent"] = "H2G2-DETON8/1.0 (uso educacional)"

    def _arquivo(self, url: str, nome: str) -> Path | None:
        """Baixa uma vez para o cache (build com internet); depois roda offline."""
        dest = self.cache / nome
        if not dest.exists():
            try:
                r = self.http.get(url, timeout=60)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"   ! F04: sem {nome} ({e.__class__.__name__}); medição fica de fora")
                return None
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
        return dest

    def list_measurements(self, sol_min, sol_max):
        with self.index_csv.open(encoding="utf-8", newline="") as f:
            indice = list(csv.DictReader(f))
        out = []
        for a in self._rows():
            parada = _parada_exata(a["parada_panorama_proxima"])
            if parada is None:
                continue
            s0, _, s1 = a["faixa_sols"].partition("-")
            s0, s1 = int(s0), int(s1 or s0)
            tid = f"t{int(a['id']):02d}"
            libs = []
            for r in indice:
                sol = int(r["sol"])
                if (int(r["site"]), int(r["drive"])) != parada or not (s0 <= sol <= s1 and sol_min <= sol <= sol_max):
                    continue
                inst = r["instrumento"]
                if inst == "APXS":
                    p = self._arquivo(r["url"], r["arquivo"])
                    if not p:
                        continue
                    vals = ler_apxs(p)
                    resumo, nome_inst = frase_apxs(sol, vals), "APXS"
                elif inst == "CheMin":
                    p = self._arquivo(r["url"], r["arquivo"])
                    if not p:
                        continue
                    vals = ler_chemin(p)
                    resumo, nome_inst = frase_chemin(sol, vals), "CheMin"
                elif inst == "ChemCam LIBS":
                    if not r["alvo"].startswith(("CCAM_", "Cal Target")):  # calibração a bordo, não é o chão
                        libs.append(r)
                    continue
                else:
                    continue  # ChemCam RMI é imagem, não medição
                out.append(Measurement(
                    id=f"{tid}_{r['arquivo']}", target_id=tid, instrument=nome_inst, sol=sol,
                    site=parada[0], drive=parada[1], summary=resumo,
                    values_json=json.dumps(vals, ensure_ascii=False), confidence="medido",
                    source_url=r["url"], source_file=r["arquivo"]))
            if libs:
                nomes = list(dict.fromkeys(r["alvo"] for r in libs))
                sols = sorted({int(r["sol"]) for r in libs})
                lista = ", ".join(nomes[:5]) + (f" e mais {len(nomes) - 5}" if len(nomes) > 5 else "")
                out.append(Measurement(
                    id=f"{tid}_chemcam", target_id=tid, instrument="ChemCam", sol=sols[0],
                    site=parada[0], drive=parada[1],
                    summary=(f"ChemCam LIBS ({f'sol {sols[0]}' if len(sols) == 1 else f'sols {sols[0]}–{sols[-1]}'}): "
                             f"{len(nomes)} alvo(s) analisados nesta parada: {lista}"),
                    values_json=json.dumps([{"alvo": r["alvo"], "sol": int(r["sol"]), "arquivo": r["arquivo"]} for r in libs],
                                           ensure_ascii=False),
                    confidence="medido", source_url=CHEMCAM_RDR, source_file=f"{len(libs)} arquivos LIBS"))
        return out
