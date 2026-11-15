"""F04 · task 5: CRISM crop of the boxwork window.

Downloads once the SU file (summary spectral parameters) of the CRISM MTRDR
product chosen in the Orbital Data Explorer search, crops the boxwork window
(+ margin) and writes `data/crism_boxwork.json` with only the parameters the card
uses. The SU is raw binary (float32, band sequential) in equirectangular projection
on the 3,396.19 km sphere: numpy is enough, no GDAL.

Run from data-pipeline/f03/:
    python etl/crism.py            # downloads the SU (~136 MB) to data/local/f03-cache/crism/ if missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.sources.science_public import CRISM_PARAMS  # noqa: E402


def lbl_value(lbl: str, key: str) -> float:
    return float(re.search(rf"^\s*{key}\s*=\s*([-\d.]+)", lbl, re.M).group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--cache", default=str(ROOT.parent.parent / "data" / "local" / "f03-cache" / "crism"))
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    c = cfg["crism"]
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    base = c["su_url"].rsplit(".", 1)[0]
    files = {}
    for ext in ("lbl", "hdr", "img"):
        dest = cache / f"{Path(base).name}.{ext}"
        if not dest.exists():
            print(f"downloading {base}.{ext}", flush=True)
            with requests.get(f"{base}.{ext}", stream=True, timeout=600) as r:
                r.raise_for_status()
                with dest.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        files[ext] = dest

    lbl = files["lbl"].read_text(encoding="latin-1")
    hdr = files["hdr"].read_text(encoding="latin-1")
    names = [n.strip() for n in re.search(r"band names = \{([^}]*)\}", hdr, re.S).group(1).split(",")]
    lines, samples, bands = (int(lbl_value(lbl, k)) for k in ("LINES", "LINE_SAMPLES", "BANDS"))
    W, E = lbl_value(lbl, "WESTERNMOST_LONGITUDE"), lbl_value(lbl, "EASTERNMOST_LONGITUDE")
    S, N = lbl_value(lbl, "MINIMUM_LATITUDE"), lbl_value(lbl, "MAXIMUM_LATITUDE")
    dlon, dlat = (E - W) / samples, (N - S) / lines
    big = re.search(r"byte order\s*=\s*1", hdr) is not None
    cube = np.memmap(files["img"], dtype=">f4" if big else "<f4", mode="r", shape=(bands, lines, samples))

    w, m = cfg["window"], cfg["window"]["margin_deg"]
    c0, c1 = max(0, int((w["lon_min"] - m - W) / dlon)), min(samples, int((w["lon_max"] + m - W) / dlon) + 1)
    r0, r1 = max(0, int((N - (w["lat_max"] + m)) / dlat)), min(lines, int((N - (w["lat_min"] - m)) / dlat) + 1)

    out_bands = {}
    for k in CRISM_PARAMS:
        b = np.array(cube[names.index(k), r0:r1, c0:c1], dtype=float)
        bad = ~np.isfinite(b) | (b >= 65534) | (b <= -1e30)
        out_bands[k] = [[None if bad[i, j] else round(float(b[i, j]), 5) for j in range(b.shape[1])]
                        for i in range(b.shape[0])]

    out = {
        "product": c["product"], "url": c["page_url"], "file": Path(c["su_url"]).name,
        "res_m": lbl_value(lbl, "MAP_SCALE") * 1000,
        "lon_min": W + c0 * dlon, "lat_max": N - r0 * dlat, "deg_px_lon": dlon, "deg_px_lat": dlat,
        "rows": r1 - r0, "cols": c1 - c0, "thresholds": {k: v[1] for k, v in CRISM_PARAMS.items()},
        "bands": out_bands,
    }
    dest = (ROOT / c["crop_json"]).resolve()
    dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"CRISM {c['product']}: {out['rows']}×{out['cols']} px, ~{out['res_m']:.0f} m/px -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
