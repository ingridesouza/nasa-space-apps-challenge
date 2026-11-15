# Next steps — feature 01 (hyperlocal boxwork map)

## Status of the 12 sources (feature 01 table, section 1)

| # | Source | Status | `product_id` / source |
|---|---|---|---|
| 1 | Optical detail — HiRISE 25cm | ✅ confirmed | `curiosity_hirise_mosaic` (WMTS) |
| 2 | Optical context — CTX ~6m | ✅ confirmed | `Gale_CTX_BlockAdj_dd` (WMTS) |
| 3 | Regional topography — MOLA | ✅ confirmed | `mola128_mola64_merge_90Nto90S_SimpleC_clon0` (ArcGIS) |
| 4 | Thermal — THEMIS | ✅ confirmed (visual only) | `THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018` (WMTS) |
| 5 | Mineralogy — CRISM | ⚠️ blocked | only 3 observations in all of Gale, none in the bbox (see below) |
| 6 | Local 1m topography — HiRISE DTM | ✅ confirmed | `Gale_DEM_SMG_1m` (ArcGIS) + visual hillshade |
| 7 | Weather — REMS | ✅ confirmed | PDS Atmospheres Node, RNV product per sol |
| 8 | Radiation — RAD | ✅ confirmed | PDS-PPI (UCLA), detector E dose |
| 9 | Rover photos — MSL | ✅ confirmed | 200 real photos, position via MMGIS |
| 10 | Terrain class — AI4Mars | ❌ unavailable (dataset does not cover the period) | tested up to sol 2579 (2019) |
| 11 | Position/traverse — MMGIS | ✅ confirmed | official `MSL_waypoints.json`, 1388 points (sol 3-5070) |
| 12 | Nomenclature — USGS/IAU | ✅ confirmed | USGS webmap on ArcGIS, 13 features in Gale |

**9 of 12 resolved.** Only CRISM (no real coverage) and AI4Mars
(dataset too old) are left out — not for lack of effort, they are
real limitations of the existing data.

---

## ⚠️ Important correction (2026-11-13): the bbox changed

The test bbox used until then (`137.40-137.48, -4.61~-4.57`) was a
guess near Curiosity's **landing site** (sol 3). With the real MMGIS
(see item 11), we found that the rover position during the boxwork
campaign (sol ~4500-4684) is **13.3 km away** from there.

**Real bbox now in use** (3x3km, centered on the real rover position
during the boxwork campaign):
```
min_lon: 137.3586   min_lat: -4.8263
max_lon: 137.4094   max_lat: -4.7757
```
Already propagated to `data-pipeline/config/layers.yaml`,
`db/populate_raster_registry.py` and `frontend/src/map/style.ts`. All
visual layers (CTX/HiRISE/DTM/MOLA/THEMIS/hillshade) and the 3 science
targets were re-downloaded/recomputed for the new bbox.

---

## MMGIS (item 11) resolved ✅ — and it unlocked item 9 too

Found via DevTools at `https://science.nasa.gov/mission/msl-curiosity/location-map/`
(`json` filter in Network): the official, public endpoint is

```
https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json
```

GeoJSON with no authentication, 1388 points, from sol 3 to sol 5070
(current at query time). Each point has `sol`, `site`, `drive`, real
`lat`/`lon`, `elev_geoid`. Downloaded and cached by
`data-pipeline/scripts/fetch_rover_waypoints.py` into
`data/local/rover_waypoints.json`.

**This solved item 9 (rover photos) for free**: the photo API
(`mars.nasa.gov/api/v1/raw_image_items/`) gives each photo's `sol`, it
just did not give a position. Now we join with the nearest-sol waypoint
to get the real lat/lon. `db/seed_rover_images.py` populated **200 real
photos** from sols 4560-4609 (start of the boxwork campaign), each with
the real rover position on that sol — `nearby_photos` in `/api/point`
now returns real distance/direction, no longer an empty list.

**Honest limitation:** the position is "where the rover was at the end
of the drive sol", not the exact spot each photo was taken within that
sol — but it is a real, verifiable position, granular enough for the
radius search to make sense.

---

## Nomenclature (item 12) resolved ✅

Found via public search on the ArcGIS Online API
(`arcgis.com/sharing/rest/search`) — USGS "Mars High-Resolution
Mosaic Viewer" webmap (owner `thare@usgs.gov_USGS`) with 5 IAU
nomenclature layers embedded as `featureCollection` in the item's own
JSON.

`data-pipeline/scripts/fetch_nomenclature.py` downloads and filters to
the Gale region: 13 real features, including **Aeolis Mons** (official
name of "Mount Sharp"), **Aeolis Palus**, **Gediz Vallis** and
**Yellowknife** crater. Exposed via `GET /api/nomenclature`; the
frontend shows the feature nearest the click with a link to the
official Gazetteer.

**The same technique (public ArcGIS search) also found the USGS global
geologic map** (Tanaka et al. 2014) with a layer queryable by
coordinate — real geologic context but at global scale (1:20M), not a
substitute for hyperlocal data.

---

## Remaining real blocker: CRISM (mineralogy, item 5)

CRISM **has no ready-made per-pixel mineral raster** on Mars Trek —
it is an index of point observations
(`mars_mro_crism_mtrdr_c0a_humex_frt_sites`, `ArcGISFeature`). Only **3
observations** in all of Gale Crater, none covering the current bbox.

- [x] Re-queried with the corrected real bbox
      (`137.3586,-4.8263,137.4094,-4.7757`) on 2026-11-13: direct query
      on `MapServer/0` returned `"features": []` — zero CRISM
      observations in this area, confirmed. Real blocker, not lack of
      trying.
- [x] No coverage: `curiosity_measurement` (already populated for the 3
      science targets) is the mineralogy source used; `crism_mineral`
      stays `None` in `/api/point` (never invented).

## Real blocker: AI4Mars (item 10) — unavailable, not pending

Dataset published in 2021, covers only up to ~sol 2579 (Nov 2019) —
almost 2000 sols before the boxwork campaign (sol 4564+, 2025). There
is no (and cannot be any) AI4Mars classification for this region. Item
closed as unavailable.

---

## REMS (weather, item 7) ✅ and RAD (radiation, item 8) ✅

`adapters/pds_rems.py` and `adapters/pds_rad.py` download real data per
sol (PDS Atmospheres Node / PDS-PPI UCLA). Tested with sol 4650:
pressure ~709 Pa, temp -69.5°C to -8.1°C, dose ~157 µGy/day — plausible
for Mars. Cached locally by `cache_conditions.py`, with no network call
at request time (offline requirement).

**Note:** the reference sol (4650) used in the cache is within the real
boxwork bbox — no need to re-cache.

---

## Local database + API ✅

`data-pipeline/db/schema.sql`: `rover_images`, `science_targets`,
`raster_registry` + SQLite native R-Tree (no SpatiaLite/GDAL).

`api/main.py`: `GET /api/point`, `/layers`, `/mosaics/{layer}.png`,
`/api/conditions`, `/api/nomenclature`. Safety verdict (slope vs. the
Artemis 20° limit) in `raster_sampling.classify_slope`.

---

## Frontend ✅

`frontend/` (React + Vite + TS + MapLibre GL), HUD theme. Map with
CTX/HiRISE/Relief/THEMIS (toggle+opacity each), click on a point →
safety briefing + real nearby photos + science card + official name of
the nearest feature. `ConditionsPanel` with REMS/RAD for the reference
sol.

**Technical note:** Mars Trek tiles are not Web Mercator, so they become
a single mosaic (`api/mosaics.py`) served as an `ImageSource`, not
standard MapLibre XYZ `tiles`. "Continuous zoom" is by overzooming one
sample per layer, not a full pyramid.

---

## General to-dos

- [x] Re-query CRISM with the real bbox — done on 2026-11-13, zero
      coverage confirmed (see section above).
- [x] Check everything against the Resources tab as soon as it opens —
      **already verified on 2026-11-12**: Mars Trek (our base) matches
      the official one; the official photo gallery points to
      Jezero/Perseverance, we kept Gale with the Curiosity API (already
      validated).
- [ ] Structuring the full 8-10 science targets for the "pokédex" card
      is feature 4 work (Victoria) — we already have 3 real ones ready
      for her to reuse. **Real gap, acknowledged** (not a bug, it is
      another feature's scope).
- [ ] `docs/PITCH.md` has the central argument (Gale vs. Jezero: only
      Gale has co-located weather+radiation) ready for whoever builds
      the presentation.
- [ ] **Validate the O₂ and route time model** (route card, F02) —
      numbers with no cited source, currently shown as "simulated":
      - default suit capacity of 400 L (`web/ui/route.js`): no
        reference; looks like a suit spec on screen;
      - 0.84 L/min (`api/route_planning.py`): the comment says
        "rest/light walking", but it matches the average Apollo EVA
        work rate (~270 W); rest would be ~0.3 L/min — find the source;
      - base speed 0.8 m/s and the linear drop to 40% at 20°: no
        source;
      - the time shows as "~X min" without saying "estimated" (only O₂
        says "simulated").

## "Absolute certainty" audit against the original spec (2026-11-13)

Before starting feature 02 (route/A*) on top of this feature's
`GET /api/point`, a line-by-line audit was done against
`feature-01-mapa-hiperlocal-boxwork.md`, checking the system actually
running (not just the code/memory). Two real deviations from the
documented contract were found and **fixed**:

1. **`raster_values` did not match the spec.** It came nested by
   layer (`{"dtm_hirise_1m": {...}, "mola_regional_topography":
   {...}}`) instead of the documented flat format
   (`elevation_m`/`slope_deg`/`ai4mars_class`/`crism_mineral` as
   top-level keys). Fixed in `api/raster_sampling.py`
   (`sample_all_rasters`): it now returns exactly the spec keys,
   picking the most precise available layer (HiRISE 1m DTM before the
   coarser regional MOLA) as the source of
   `elevation_m`/`slope_deg`. `ai4mars_class` and `crism_mineral` stay
   `None` (not invented — see the AI4Mars/CRISM sections above). An
   extra `sources` field was kept (outside the original spec, but
   additive) with per-layer detail, used by the frontend's "other
   elevation sources" panel. **Tested live**: I restarted the API and
   confirmed via `curl /api/point?lat=-4.80689&lon=137.37984` that the
   shape matches the spec exactly. `frontend/src/api/types.ts` and
   `PointInfoPanel.tsx` were updated to the new format;
   `npx tsc --noEmit` clean.
2. **Photo grid missing.** `NearbyPhotosSection.tsx` rendered only a
   text list (distance/direction/sol/camera), never the image — the
   spec (section 4) explicitly asks for a "grid/lightbox of static
   photos, sorted by distance and direction". Fixed: 2-column grid
   with a real `<img>` (uses `p.url`, which the API already returned) +
   lightbox on click.

**Checked and OK, no change needed:**
- `nearby_photos` and `science_target`: shape already matched the spec.
- Real counts via SQLite: `rover_images` = 200 (matches the spec's "~200
  images"), `raster_registry` = 6 layers.
- "Geophysics" marked as out of scope in
  `frontend/src/map/layers.ts`, visible in the UI — the spec asks to
  communicate the exclusion, not hide it.
- `science_target.terrain_class` is an intentional rename of the
  database `ai4mars_class` column to match the exact JSON key name in
  the spec — not a bug.
- Continuous zoom via an always-rendered `ImageSource` (not
  minzoom/maxzoom-gated as the spec suggests) — simplification already
  documented, not a new surprise.

**Real gap, not a bug, it is another feature's scope:** only 3 of 8-10
science targets (the full "pokédex" card is feature 4/Victoria work).

## "Does it really run offline?" audit (2026-11-14)

Checked line by line after the direct question "will everything we
built run offline without being heavy" -- it is a requirement that, if
it fails, invalidates the whole demo at the event.

**Confirmed OK:**
- Zero network calls at runtime in `api/*.py` (checked via grep for
  `requests.get`/`urlopen`/`httpx` -- they only exist in the
  `data-pipeline/` fetch scripts, never called by the running API).
- `data/local/` (all cached real data -- tiles, DTM/MOLA, conditions,
  nomenclature, waypoints, photos) = **~130MB in total**. Light, not a
  weight/space concern.
- React/MapLibre/the whole frontend becomes a static bundle in the Vite
  build -- it fetches nothing from the network at runtime. The only
  prerequisite is that `npm install` ran once, with internet, before
  the event (same as `pip install -r requirements.txt` on the Python
  side) -- not a React quirk, it applies to any Node/Python project
  with dependencies.

**Real bug found and fixed:** `rover_images.local_path` stored the
remote `mars.nasa.gov` URL directly (despite the column name), not a
local file -- without internet, all ~200 photos (grid, lightbox, rover
trail pins) would break, showing a broken image icon. Fixed with
`data-pipeline/scripts/download_rover_photos.py` (actually downloads to
disk, 39MB) + `api/main.py` serving via `StaticFiles` at
`/rover-photos/...`. Reflected everywhere a photo is used
(`nearby_photos`, `all_photos` in `api/vector_queries.py`, now with a
`base_url` parameter to build the local URL instead of returning the
remote one).

**Known gap, not critical:** the fonts (Chakra Petch, IBM Plex Sans,
JetBrains Mono) load via Google's CDN in `frontend/index.html`.
Without internet, it falls back to the system default font -- nothing
breaks, it just loses the chosen typography. Self-hosting would fully
solve it; not done yet since it does not block the demo.

## Technical notes

- `adapters/mars_trek_wmts.py`: handles geographic (degrees) and
  projected (meters) CRS, detected by the magnitude of `TopLeftCorner`.
  Some numeric XML fields come as float (`"2.0"`) even though they are
  integers — already handled.
- `adapters/arcgis_image_server.py`: serves rasters with real pixel
  values via `exportImage` — always prefer it when an
  `ArcGISImageService` exists, it is better than the equivalent WMTS
  for sampling.
- Public search on ArcGIS Online (`arcgis.com/sharing/rest/search`,
  no auth) is a reusable technique to find USGS/Esri-hosted content
  outside Mars Trek (geology, nomenclature, traverses) — see session
  memory for details.
