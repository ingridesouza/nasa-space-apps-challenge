#!/usr/bin/env python3
"""
collect_panoramas.py · H2G2 · Feature 03 · Tasks M4 + M5

Scans the "Sol XXXX: Right/Left Navigation Camera, Cylindrical Projection" pages
of science.nasa.gov over the boxwork sol window, extracts the metadata of each
Navcam panorama (sol, site, drive, center azimuth...), downloads the full-resolution
PNG and writes everything into a CSV where each row points to its image file.

Usage:
    pip install requests beautifulsoup4 pillow
    python collect_panoramas.py                         # sols 4550 to 4845
    python collect_panoramas.py --sol-start 4640 --sol-end 4660   # quick test
    python collect_panoramas.py --urls extras.txt       # + pages found on Google
    python collect_panoramas.py --no-images             # CSV only
    python collect_panoramas.py --max-images 50         # changes the download cap

Default window: sols 4550 to 4845, the same as the feature plan (tasks 2, 4 and 7),
which covers the approach to and the crossing of the boxwork. The CSV lists all panoramas
found; only up to 100 images (--max-images) are downloaded, chosen like this:
  1. only panoramas with a center azimuth and site/drive (without that they cannot
     be positioned or oriented on the map);
  2. one per rover stop (rmc), preferring the right camera;
  3. if still above the cap, a sample spaced along the sols, to
     cover the whole traverse instead of piling up at the start.

Output (--out folder, default ./panorama_data):
    panoramas.csv        one row per panorama
    panos/*.png          one PNG per selected row (local_file column)

The script can be interrupted and run again: pages already in the CSV and
images already downloaded are skipped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None  # panoramas are wide; turns off the "bomb" warning
except ImportError:  # without Pillow, it just does not compute width/height/vaov
    Image = None

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PAGE_URL = (
    "https://science.nasa.gov/resource/"
    "sol-{sol}-{camera}-navigation-camera-cylindrical-projection{suffix}/"
)
CAMERAS = ("right", "left")
SUFFIXES = ("", "-2", "-3")  # WordPress appends -2, -3 when the title repeats
USER_AGENT = "H2G2-DETON8/1.0 (NASA Space Apps Salvador 2026; educational collection)"
CREDIT = "NASA/JPL-Caltech"

# --------------------------------------------------------------------------- #
# Regular expressions (based on the standard text of the pages, e.g. sol 4653):
# "Curiosity took 31 images ... Right Navigation Camera (Navcam) ... centered at
#  185 degrees azimuth (measured clockwise from north). Curiosity took the images
#  on September 08, 2025, Sol 4653 of the Mars Science Laboratory mission at
#  drive 2466, site number 118. The local mean solar time for the image
#  exposures was 3 PM."
# --------------------------------------------------------------------------- #

RE_TITLE_SOL = re.compile(r"Sol\s+(\d{3,5})\s*:", re.I)
RE_CAMERA = re.compile(r"\b(Right|Left)\s+Navigation\s+Camera", re.I)
RE_N_IMAGES = re.compile(r"took\s+(\d+)\s+images", re.I)
RE_AZIMUTH = re.compile(r"centered\s+at\s+([\d.]+)\s+degrees?\s+azimuth", re.I)
RE_SOLS = re.compile(r"Sols?\s+(\d{3,5}(?:\s*[-–]\s*\d{3,5})?)\s+of\s+the\s+Mars", re.I)
RE_DRIVE = re.compile(r"at\s+drive\s+(\d+)", re.I)
RE_SITE = re.compile(r"site\s+number\s+(\d+)", re.I)
RE_LMST = re.compile(
    r"local\s+mean\s+solar\s+time\s+for\s+the\s+image\s+exposures\s+was\s+(.+?)\.", re.I
)
RE_CAPTURE_DATE = re.compile(r"took\s+the\s+images\s+on\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.I)
RE_PNG = re.compile(r"https://assets\.science\.nasa\.gov/content/dam/[^\s\"'<>()]+?\.png", re.I)
# Mosaic name: N_R000_4653_EDR118CYLASB2466_AUTOLM1.PNG
#   R = right camera (L = left), 4653 = sol, 118 = site, 2466 = drive
RE_FILE_NAME = re.compile(r"N_([RL])\d{3}_(\d{4})_EDR(\d{3})CYL[A-Z0-9]*?(\d{4})_", re.I)

# --------------------------------------------------------------------------- #
# Data model: one CSV row
# --------------------------------------------------------------------------- #


@dataclass
class Panorama:
    sol: int | None = None             # sol from the page title
    sols_text: str = ""                # as it appears in the text (may be "4693-4687")
    site: int | None = None
    drive: int | None = None
    rmc: str = ""                      # "site_drive", key to cross with MMGIS
    center_azimuth: float | None = None   # degrees, clockwise from north
    camera: str = ""                   # right | left
    n_images: int | None = None
    capture_date: str = ""             # Earth capture date
    lmst: str = ""                     # local mean solar time
    png_url: str = ""
    png_original_file: str = ""
    local_file: str = ""               # path of the downloaded PNG (links image -> row)
    width_px: int | None = None
    height_px: int | None = None
    vaov_deg: float | None = None      # vertical field of view = 360 * height / width
    size_bytes: int | None = None
    sha256: str = ""
    page_url: str = ""
    credit: str = CREDIT
    check: str = ""                    # "ok" or a list of warnings separated by ";"
    selected: str = ""                 # "yes" if it was among the up to 100 downloaded images


CSV_FIELDS = [f.name for f in fields(Panorama)]

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get(session: requests.Session, url: str, delay: float, attempts: int = 3, **kw):
    """Polite GET: waits `delay` seconds, retries on network error/5xx.
    Returns the response, or None if the page does not exist (404)."""
    for i in range(attempts):
        try:
            r = session.get(url, timeout=60, **kw)
        except requests.RequestException as e:
            print(f"   ! network error ({e.__class__.__name__}), attempt {i + 1}/{attempts}")
            time.sleep(delay * (2 ** (i + 1)))
            continue
        time.sleep(delay)
        if r.status_code == 404:
            return None
        if r.status_code >= 500 or r.status_code == 429:
            print(f"   ! HTTP {r.status_code}, attempt {i + 1}/{attempts}")
            time.sleep(delay * (2 ** (i + 1)))
            continue
        r.raise_for_status()
        return r
    print(f"   ! gave up on {url}")
    return None


def same_url(a: str, b: str) -> bool:
    return a.rstrip("/").lower() == b.rstrip("/").lower()

# --------------------------------------------------------------------------- #
# Reading a page
# --------------------------------------------------------------------------- #


def _int(m: re.Match | None) -> int | None:
    return int(m.group(1)) if m else None


def extract_png_url(soup: BeautifulSoup, html: str) -> str:
    """Link to the full-resolution PNG (the one in the Downloads section), not the thumbnails."""
    candidates = [a["href"] for a in soup.find_all("a", href=True) if RE_PNG.fullmatch(a["href"])]
    candidates += RE_PNG.findall(html)
    for url in candidates:
        if "jcr:content" not in url and "renditions" not in url:
            return url
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):  # .../X.PNG/jcr:content/renditions/... -> .../X.PNG
        return og["content"].split("/jcr:content")[0]
    return ""


def read_page(html: str, url: str) -> Panorama | None:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", property="og:title")
    title = og_title["content"] if og_title and og_title.get("content") else ""
    if not title and soup.h1:
        title = soup.h1.get_text(" ", strip=True)
    if "cylindrical projection" not in title.lower():
        return None

    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    p = Panorama(page_url=url)
    p.sol = _int(RE_TITLE_SOL.search(title))
    m = RE_CAMERA.search(title) or RE_CAMERA.search(text)
    p.camera = m.group(1).lower() if m else ""
    p.n_images = _int(RE_N_IMAGES.search(text))
    m = RE_AZIMUTH.search(text)
    p.center_azimuth = float(m.group(1)) if m else None
    m = RE_SOLS.search(text)
    p.sols_text = re.sub(r"\s+", "", m.group(1)) if m else ""
    p.drive = _int(RE_DRIVE.search(text))
    p.site = _int(RE_SITE.search(text))
    m = RE_LMST.search(text)
    p.lmst = m.group(1).strip() if m else ""
    m = RE_CAPTURE_DATE.search(text)
    p.capture_date = m.group(1) if m else ""
    p.png_url = extract_png_url(soup, html)
    p.png_original_file = p.png_url.rsplit("/", 1)[-1] if p.png_url else ""

    verify(p)
    return p


def verify(p: Panorama) -> None:
    """Checks the text against the file name and fills in what is missing."""
    warnings = []
    m = RE_FILE_NAME.search(p.png_original_file)
    if m:
        cam_n, sol_n, site_n, drive_n = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if p.site is None or p.drive is None:
            p.site = p.site if p.site is not None else site_n
            p.drive = p.drive if p.drive is not None else drive_n
            warnings.append("site_drive_from_name")
        elif (p.site, p.drive) != (site_n, drive_n):
            warnings.append(f"name_mismatch(text={p.site}_{p.drive},name={site_n}_{drive_n})")
        if p.sol is not None and sol_n != p.sol:
            warnings.append(f"name_sol={sol_n}")
        if not p.camera:
            p.camera = "right" if cam_n.upper() == "R" else "left"
    else:
        warnings.append("nonstandard_name")
    if p.center_azimuth is None:
        warnings.append("no_azimuth")
    if p.site is None or p.drive is None:
        warnings.append("no_site_drive")
    if not p.png_url:
        warnings.append("no_png")
    p.rmc = f"{p.site}_{p.drive}" if p.site is not None and p.drive is not None else ""
    p.check = ";".join(warnings) or "ok"

# --------------------------------------------------------------------------- #
# Selection and download (links image -> row through the local_file column)
# --------------------------------------------------------------------------- #


def _sol(l: dict) -> int:
    return int(l["sol"]) if str(l.get("sol", "")).isdigit() else 10**9


def select(rows: dict[str, dict], maximum: int) -> list[dict]:
    """Chooses up to `maximum` panoramas to download (rules at the top of the file)."""
    valid = [l for l in rows.values()
             if l.get("png_url") and l.get("rmc") and l.get("center_azimuth")]
    by_stop: dict[str, dict] = {}
    for l in sorted(valid, key=lambda l: (l["camera"] != "right", l["page_url"])):
        by_stop.setdefault(l["rmc"], l)
    unique = sorted(by_stop.values(), key=lambda l: (_sol(l), l["rmc"]))
    if len(unique) <= maximum:
        return unique
    step = len(unique) / maximum
    return [unique[int(i * step)] for i in range(maximum)]


def local_name(l: dict) -> str:
    cam = (l.get("camera") or "x")[0].upper()
    if l.get("rmc"):
        site, drive = (int(x) for x in l["rmc"].split("_"))
        return f"pano_{l['sol']}_{site:03d}_{drive:04d}_{cam}.png"
    return f"pano_{l['sol']}_{Path(l['png_original_file']).stem}.png"


def download_image(session, l: dict, folder: Path, delay: float) -> bool:
    dest = folder / local_name(l)
    if not dest.exists():
        r = get(session, l["png_url"], delay, stream=True)
        if r is None:
            if "download_failed" not in l["check"]:
                l["check"] += ";download_failed"
            return False
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for block in r.iter_content(1 << 16):
                f.write(block)
        tmp.replace(dest)
    l["local_file"] = dest.as_posix()
    data = dest.read_bytes()
    l["size_bytes"] = str(len(data))
    l["sha256"] = hashlib.sha256(data).hexdigest()
    if Image is not None:
        with Image.open(dest) as im:
            w, h = im.size
        l["width_px"], l["height_px"] = str(w), str(h)
        l["vaov_deg"] = str(round(360 * h / w, 2))
    return True

# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #


def load_csv(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["page_url"]: {k: row.get(k, "") for k in CSV_FIELDS}
                for row in csv.DictReader(f)}


def save_csv(path: Path, rows: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in sorted(rows.values(), key=lambda l: (_sol(l), l["page_url"])):
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    tmp.replace(path)

# --------------------------------------------------------------------------- #
# Page discovery (phase 1: metadata only, no images)
# --------------------------------------------------------------------------- #


def candidate_urls(sol_start: int, sol_end: int):
    """Yields (sol, camera, list of URLs in suffix order)."""
    for sol in range(sol_start, sol_end + 1):
        for camera in CAMERAS:
            yield sol, camera, [PAGE_URL.format(sol=sol, camera=camera, suffix=s) for s in SUFFIXES]


def process(r, rows, args, csv_path) -> bool:
    """Reads the already-downloaded page and writes the row to the CSV; True if it was a panorama."""
    final_url = r.url
    if final_url in rows and not args.redo:
        return True
    p = read_page(r.text, final_url)
    if p is None:
        return False
    if p.sol is not None and not (args.sol_start <= p.sol <= args.sol_end) and not args.accept_outside:
        print(f"   - {final_url} is from sol {p.sol}, outside the window; ignored")
        return True
    rows[final_url] = {k: "" if v is None else str(v) for k, v in asdict(p).items()}
    save_csv(csv_path, rows)  # saves after each page: can be interrupted and resumed
    print(f"   + sol {p.sol} · {p.camera} · site {p.site} drive {p.drive} · "
          f"az {p.center_azimuth} · {p.check}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sol-start", type=int, default=4550)
    ap.add_argument("--sol-end", type=int, default=4845)
    ap.add_argument("--max-images", type=int, default=100, help="cap of downloaded PNGs")
    ap.add_argument("--out", default="panorama_data")
    ap.add_argument("--urls", help=".txt file with extra page URLs (one per line)")
    ap.add_argument("--delay", type=float, default=0.7, help="seconds between requests")
    ap.add_argument("--no-images", action="store_true", help="only builds the CSV")
    ap.add_argument("--redo", action="store_true", help="reprocesses pages already in the CSV")
    ap.add_argument("--accept-outside", action="store_true", help="accepts sols outside the window")
    args = ap.parse_args()

    out = Path(args.out)
    img_folder = out / "panos"
    img_folder.mkdir(parents=True, exist_ok=True)
    csv_path = out / "panoramas.csv"
    rows = load_csv(csv_path)
    session = new_session()
    print(f"Current CSV: {len(rows)} panoramas · sol window {args.sol_start}–{args.sol_end}")

    # Phase 1a) Extra URLs (e.g. found on Google in task M4)
    if args.urls:
        for url in Path(args.urls).read_text(encoding="utf-8").split():
            print(f"> {url}")
            r = get(session, url, args.delay)
            if r is None or not process(r, rows, args, csv_path):
                print("   - not a panorama page")

    # Phase 1b) Sweep by sol: tries the default URL; if it exists, tries -2 and -3
    for sol, camera, candidates in candidate_urls(args.sol_start, args.sol_end):
        for url in candidates:
            r = get(session, url, args.delay)
            if r is None:
                break  # without the base page, there is no -2 or -3
            if not same_url(r.url, url):
                # WordPress sometimes redirects a nonexistent address to another
                # similar page; use the destination page only if it is a panorama
                process(r, rows, args, csv_path)
                break
            print(f"> sol {sol} · {camera} · {url}")
            if not process(r, rows, args, csv_path):
                break

    # Phase 2) Selection of up to --max-images and download
    chosen = select(rows, args.max_images)
    ids = {id(l) for l in chosen}
    for l in rows.values():
        l["selected"] = "yes" if id(l) in ids else "no"
    if not args.no_images:
        print(f"\nDownloading {len(chosen)} panoramas (cap {args.max_images})...")
        for i, l in enumerate(chosen, 1):
            ok = download_image(session, l, img_folder, args.delay)
            print(f"  [{i}/{len(chosen)}] sol {l['sol']} · {l['rmc']} · {'ok' if ok else 'FAILED'}")
            save_csv(csv_path, rows)
    save_csv(csv_path, rows)

    warned = [l for l in rows.values() if l["check"] != "ok"]
    print(f"\nDone: {len(rows)} panoramas in the CSV, {len(chosen)} selected · {csv_path}")
    print(f"Images in {img_folder}/")
    if warned:
        print(f"{len(warned)} row(s) with a warning in the 'check' column — check them by hand:")
        for l in warned:
            print(f"  sol {l['sol']}: {l['check']}  {l['page_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
