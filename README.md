# H2G2 · Human-to-Ground Guide

**A hyperlocal field guide for a safe walk on Mars, in the boxwork of Mount Sharp, Gale crater. It runs entirely offline.**

Team **DETON8** · NASA Space Apps Challenge 2026, Salvador · challenge *Interplanetary Survival Guide: Martian Map*.

**Why "H2G2".**
- **Origin:** H2G2 is the classic shorthand for Douglas Adams's *The Hitchhiker's Guide to the Galaxy*. Its title, HHGG, has two H's and two G's, hence H2G2.
- **Same idea as the book:** a guide that fits in your hand and tells a traveler what they need to survive somewhere strange.
- **Backronym:** *Human-to-Ground Guide*, a guide from the human straight to the ground under their boots.
- **Inherited motto:** the landing page signs off with **"DON'T PANIC"**, printed on the book's cover.
- **Inherited character:** the voice assistant is called **Marvin**, after the book's android.

An astronaut about to walk ~3 km over boxwork ridges needs four answers fast:
- Which way is safe?
- What is that rock?
- Is there sun or shade there?
- How much oxygen does the walk cost?

Mars has no internet, and Earth is 4 to 24 minutes away. H2G2 answers on local hardware, from real NASA data, and every number says where it came from.

- **Useful.** It joins map, route, science, weather and voice in one screen, at the meter scale of a walk. Mars Trek and the USGS maps work at regional and global scale.
- **Fast.** On a laptop (Apple M1), once warm:

  | Operation | Time |
  |---|---|
  | Point lookup | ~40 ms |
  | 3 route variants over 3 km of real terrain | ~0.5 s |
  | A sun-and-shade tile for any hour | ~30 ms (2 ms when cached) |

  See [Performance](#performance).
- **Practical.**
  - Stack: Python + FastAPI + SQLite on the back, plain HTML/CSS/JS on the front.
  - No Docker, no database server, no bundler, no `npm install`.
  - `make build` once with internet, then `make run`, then open `http://localhost:8000`.
- **Honest by design.**
  - No data means "no data", never an invented value.
  - Every fact on screen and every spoken answer carries its instrument, its PDS source and a confidence level.
  - Safety verdicts come from fixed rules, never from the language model.

---

## What it does

Status: **Prototype** runs in this repo today · **Extra** goes beyond the challenge brief · **Proposal** is design only.

| # | Feature | Status | In short |
|---|---|---|---|
| 01 | Layered hyperlocal map | Prototype | ~3×3 km of the boxwork: HiRISE and CTX imagery, relief, slope risk, THEMIS thermal inertia, REMS along the traverse, sun and shade, IAU/USGS names |
| 02 | Route + risk | Prototype | A* over the HiRISE DTM with 3 variants and intermediate stops (details below) |
| 02+ | Rover-calibrated slope risk | Extra | The orbital DTM is checked against the tilt Curiosity measured at 293 stops |
| 01+ | Sun and shade, hour by hour | Extra | Direct-sun incidence and shade for any sol and solar hour (details below) |
| 03 | Photos and panoramas at the point | Prototype | 211 Navcam photos and 73 360° panoramas (72 Navcam, 1 Mastcam), all on disk, labeled "taken X m from here" |
| 04 | Science card → answer card | Prototype | 10 boxwork targets with 60 real PDS measurements (33 ChemCam, 23 APXS, 4 CheMin), plus CRISM when the target falls in the crop |
| 05/06 | Conditions + offline forecast | Prototype | Curiosity REMS and RAD; forecast of any sol from the seasonal climatology, plus the best EVA window |
| 08/11 | Marvin, offline voice assistant | Prototype | "Hey Marvin" → local Whisper → rule-based command or local LLM answer (details below) |
| 07 | Helmet visor | Proposal | The web UI is the visor's software; the helmet and AR hardware are a proposal (3D model on the landing page) |
| 09 | Earth–Mars sync | Input port ready | Runs with zero Earth contact and flags data age; new measurements enter through `POST /api/measurement` and the forecast recomputes. The Earth link itself is not built |

**Route + risk (02).**
- **Variants:** safest, fastest, most science.
- **Slope:** caution from 15°, danger at 20°, the Artemis walking limit.
- **Radiation:** the RAD dose is summed over the walk time.
- **O₂ estimate:** a 350 W NASA PLSS baseline (≈1 L/min), raised by the Pandolf equation on slopes, checked against the suit capacity you enter.
- **Replanning:** when you report a problem (rock, steep, tired, dust, O₂), the same A* builds new options and you choose.

**Rover-calibrated slope risk (02+).** In map cells shown as 10–15°, the rover measured ≥15° 27% of the time. The risk layer shows that historical chance, not a terrain forecast.

**Sun and shade (01+).**
- **How:** Sun position from Mars24, incidence and near shade from the 1 m DTM (computed at 2 m), and far shade from the MOLA horizon, which includes Mount Sharp.
- **Validated** against HiRISE image PSP_009294_1750.

**Offline forecast (05/06).** Backtest over 201 sols, 20 sols ahead: mean error 1.9 °C on the minimum, 3.7 °C on the maximum and 11.2 Pa on pressure.

**Marvin (08/11).**
- **Speech:** Whisper `large-v3`, with `small` for yes/no confirmations.
- **Answers:** `gemma4:e2b` via Ollama.
- **Voice viewer:** 11 blocks named after stars.
- **Rules, not the LLM:** alerts and distress calls (fall, leak, toxic gas) are answered by rule, immediately. Cited sources come from the system, never from the model's text.

Deep dives: [`docs/conteudo-pitch.md`](docs/conteudo-pitch.md) (verified facts, numbers and what not to claim) · `docs/feature-NN-*.md`.

## Performance

Measured on 2026-11-15 on an Apple M1 laptop. The API ran in-process through FastAPI's `TestClient`, with the local `data/local/` package and no network.

| Request | Cold (first call) | Warm (median) |
|---|---|---|
| `/api/point`: elevation, slope, alerts, nearest target and photos | ~6 s (one-time warm-up) | **~40 ms** |
| `/api/route`: 3 variants, ~500 m apart | 47 ms | **~22 ms** |
| `/api/route`: 3 variants, ~3 km apart | ~6.6 s (one-time warm-up) | **~0.5 s** |
| `/api/route-forecast`: terrain chance, weather, EVA window, dose | 95 ms | **~20 ms** |
| `/tiles/insolation/{z}/{x}/{y}.png`: sun and shade for an hour | 30–670 ms (new hour grid) | **~2 ms** |
| `/tiles/hirise_optical/…`, `/tiles/relief_hillshade/…` | 23–230 ms | **~2 ms** |
| `/api/forecast`, `/api/conditions`, `/api/photos` | ≤ 84 ms | **2–3 ms** |

- The first request loads the rasters and the science data into memory (~6 s, once per process).
- Voice and LLM are slower. Whisper `large-v3` took 5.8 s for a 2.3 s phrase on an i5-13420H (`docs/feature-08-voz-plano-execucao.md`). That is why route and map commands go through rules, not the LLM.
- Runtime data package: ~410 MB.

  | Contents | Size |
  |---|---|
  | Tiles and DTMs | 126 MB |
  | Photos, panoramas and science bundle | 282 MB |
  | SQLite database | 0.5 MB |

  This excludes the 181 MB build cache and the Whisper/LLM models (a few GB).
- Code size: ~4.6k lines of Python in the API, ~2.4k lines of JS in the front, 8 Python dependencies in the API, and 2 vendored front libraries (MapLibre, Pannellum).

## How it works

```
   build time (internet)                         runtime (offline)
 ┌──────────────────────────┐   data/local/   ┌──────────────────────────────┐
 │ data-pipeline/  ETL      │ ──────────────▶ │ api/  FastAPI                │
 │ Mars Trek · PDS · USGS   │  tiles, DTMs,   │  SQLite + R-tree, rasterio,  │
 │ MMGIS · MSL raw images   │  h2g2.sqlite,   │  A*, Mars24, forecast,       │
 │ science.nasa.gov         │  photos, panos  │  alerts, Whisper, Ollama     │
 └──────────────────────────┘                 │        ▲ serves  /           │
                                              │ web/  HTML + CSS + JS        │
                                              │  MapLibre, Pannellum (local) │
                                              └──────────────────────────────┘
```

- **Back end:** Python, FastAPI and SQLite with a native R-tree, in one database file. `api/geo.py` is the only geometry, using a Mars radius of 3,396,190 m.
- **Front end:** plain HTML/CSS/JS with native ES modules, served by the API at `/`. Libraries and fonts are vendored in `web/lib/` and `web/fonts/`.
- **Offline rule:** no external URL is called at runtime, not by the API and not by the front. The acceptance test is to turn Wi-Fi off and use the whole system.

## Data sources

All are downloaded at build time and served from disk.

| Data | Source | Used for |
|---|---|---|
| HiRISE mosaic of Curiosity's traverse (~0.6 m served), CTX Gale mosaic (~10 m) | Mars Trek (JPL); USGS | Map base, photo context |
| Gale HiRISE DTM (1 m native; ~6 m grid for route and risk) | Mars Trek | Relief, slope, route, sun and shade |
| MOLA (~463 m) | Mars Trek | Distant horizon for shade |
| THEMIS thermal inertia (100 m, quantitative) | USGS Astrogeology | Thermal layer |
| CRISM MTRDR FRT000058A3 (~18 m) | PDS Geosciences | Science card |
| APXS, ChemCam, CheMin | PDS Geosciences | Science card |
| REMS | PDS Atmospheres (NMSU) | Conditions, climatology, forecast |
| RAD | PDS PPI (UCLA) | Dose on conditions and route |
| Curiosity waypoints | MMGIS (mars.nasa.gov) | Position of photos, stops and atmosphere |
| Navcam/Mastcam photos | MSL raw images API | Photos at the point |
| 360° panoramas | science.nasa.gov | Panorama viewer |
| IAU/USGS nomenclature | USGS Astrogeology | Place names |
| Sun position, Ls, sol | Mars24 algorithm (Allison & McEwen 2000), implemented in `api/mars_time.py` | Time, season, insolation |

Per-layer decisions, calculations and validations: [`docs/feature-01-camadas-de-dados.md`](docs/feature-01-camadas-de-dados.md).

## Quick start

```bash
make build   # once, with internet: venv, Python deps, real data into data/local/, Whisper models, LLM
make run     # API + UI at http://localhost:8000
make test    # API tests (+ node test for the voice viewer, if node is installed)
```

**The assistant (`/api/ask`)** needs a recent [Ollama](https://ollama.com).
- Gemma 4 does not load on 0.12.x.
- Without `sudo`, extract the official release into `~/.local/ollama`; the Makefile uses it first.
- `make build` pulls `gemma4:e2b` into `data/local/ollama/`.
- Without Ollama, `/api/ask` returns 503. The map, route, alerts and answer-card rules keep working.

**Without `make` (Windows):**

```bash
cd api && pip install -r requirements.txt && python -m uvicorn main:app --port 8000
```

Then open http://localhost:8000. There is no front build.

**Simulated clock for demos:** `H2G2_CLOCK="SOL@HH:MM" make run`.

## Known limits

These are stated in the UI, the API and the pitch:

- **Relief:** the DTM source is 1 m, but route and slope run on a ~6 m grid. Boxwork ridges of 1–2 m are smoothed out, which is why the risk is calibrated by the rover.
- **HiRISE:** the imagery is black and white in Gale. The Martian tint on the map is cosmetic.
- **Not available for the area, so the system shows no data:**
  - sand or terrain class per pixel (AI4Mars does not cover the campaign), so sand risk is a fixed warning;
  - dust opacity;
  - wind (REMS wind sensor damaged).
- **CRISM:** shown only on the science card, not as a map layer.
- **Forecast:** a seasonal mean, not the weather of the day, and no dust storm prediction. The dust-season alert (Ls 180°–360°) covers that risk.
- **Ground temperature:** read from GTS channel B, which gives implausible noon values. Channel A has not been migrated yet ([F06](docs/feature-06-previsao-clima.md)).
- **O₂:** a route estimate. There is no suit telemetry, and the capacity is entered by hand.
- **Visor and Earth–Mars sync:** proposals. See the table above.
- **Portability:** the offline package is not portable yet. The raster registry stores absolute paths, so copying `data/local/` to another machine breaks the map ([`docs/raio-x-implementacao.md`](docs/raio-x-implementacao.md), item 5).

## Repository

| Path | What |
|---|---|
| `api/` | FastAPI app: endpoints in `main.py`, one flat module per feature (`route_planning.py`, `insolation.py`, `forecast.py`, `agent.py`, `voice.py`…). See [`api/README.md`](api/README.md) |
| `data-pipeline/` | Build-time ETL: adapters, `fetch_*`/`cache_*` scripts, `db/schema.sql`; `f03/` builds photos, panoramas and the science card. See [`data-pipeline/README.md`](data-pipeline/README.md) |
| `web/` | The only front end: full-screen viewer, expandable minimap, route card, answer card, voice viewer (`commands.json`) |
| `docs/` | Proposal, pitch, feature docs (Portuguese). See [`docs/README.md`](docs/README.md) |
| `NEXT-STEPS.md` | Status of every data source and feature, including what failed and why |
| `data/local/` | Generated offline package (gitignored) |

## Team

DETON8 · NASA Space Apps Challenge 2026 · Salvador, Brazil.
