# Feature 05 (extension) · Solar particle event (SPE) alert

2026-11-15 · Added while surveying real NASA/Apollo emergency-procedure data for
a mid-walk hazard-response differentiator (see `replan.py`). Of the new hazard
categories found in that survey, this one was picked first: real data exists,
it reuses the RAD pipeline the project already has, and it is small to build.

## 1. The idea, in one sentence

Instead of simulating a live solar-wind feed (the system runs 100% offline,
CLAUDE.md), the system replays a REAL solar particle event already measured
on the ground by MSL RAD, and raises the same alert it would raise if that
event were happening today.

## 2. Sources (every number traced to where it came from)

| Value | Status | Source |
|---|---|---|
| Sol 242 (12-13 Apr 2013) had a hard solar energetic particle (SEP) event | Real, documented | RAD team literature: "RAD's one hard SEP event" in its first ~300 sols on the surface |
| Peak dose during the event: **260.9 µGy/hour-equivalent (10.87 µGy/h × 24)** | **Real, primary** — fetched directly from the PDS-PPI archive by this session (`data-pipeline/adapters/pds_rad.py`, file `RAD_RDR_2013_101_07_02_0242_V00.TXT`), not copied from a secondary summary | PDS-PPI (UCLA), MSL RAD RDR, sol 242 |
| Background reference: **168.5 µGy/day-equivalent (7.02 µGy/h × 24)** | **Real** — this project's own cached reference sol (4650), same instrument, same pipeline | PDS-PPI (UCLA), MSL RAD RDR, sol 4650 |
| Danger-tier ratio: **3× background** | Real anchor, not arbitrary — set to the same relative elevation as the largest surface SEP NASA has documented to date (the Sept-2017 RAD event, "peak dose rate nearly 3x the galactic cosmic ray level") | RAD team reporting on the Sept-2017 event (exact sol/dose not yet pinned by this session — see §6) |
| Caution-tier ratio: **1.5× background** | **Declared H2G2 proposal** — no official surface-EVA alert threshold was found in this session's research | — |
| Per-event dose ceiling cited in the alert message: **250 mSv** | Real, documented | NASA-STD-3001, short-term effective dose limit for a single SPE |
| "Two-tier alert" concept (monitor vs. shelter) | Real concept, but documented for the Orion vehicle (Artemis II), not for a surface EVA suit — borrowed the concept, not a surface-specific number | NASA Artemis II public material on solar monitoring |

**Why the peak reading, not the day's mean:** the first attempt used `estimated_dose_ugy_per_day` (the sol's 24h mean, already used everywhere else in the project) and got 233.2 µGy/day for sol 242 — only 1.49× background, just under the caution threshold. A solar particle event is a short-duration rate spike; averaging it over a full day (which includes non-event hours) dilutes it away. The sol's **peak** hourly reading (10.87 µGy/h) matches the literature's cited "~260 µGy/day" almost exactly. `data-pipeline/scripts/cache_conditions.py` was extended with a new field, `peak_dose_ugy_per_hour`, to capture this (additive -- the existing `mean_dose_ugy_per_hour` / `estimated_dose_ugy_per_day` fields are unchanged, still used by everything else).

**Bug found and fixed along the way:** `data-pipeline/adapters/pds_rad.py` could not fetch any sol below 1000 — the real PDS filenames zero-pad the sol to 4 digits (`..._0242_V00.TXT`), but the adapter's regex expected the bare number. Sol 4650 (the only sol ever fetched before this session) happened to already have 4 digits, which hid the bug. Fixed by zero-padding the sol in the regex.

## 3. Design decisions

- **No live voice announcement.** Discussed and explicitly dropped: voice recognition is the fragile part of a live pitch demo (and does not even run in this dev environment -- `faster_whisper` is not installed), so this feature stays fully visual/textual.
- **One real event cataloged for now (sol 242).** Two more candidates were found in research (Sept 2017, "largest SEP so far observed by RAD"; May 2024, "biggest RAD surge since landing") but their exact sol + dose were not pinned down this session. `solar_events.KNOWN_EVENTS` is built to add them the same way (fetch the real PDS file, read the peak, cite it) once confirmed.
- **`"radiation"` reuses the `dust`/`oxygen` response pattern in `replan.py`** (both return-to-base options, no detour) -- same priority as an environmental hazard that should not be navigated around, only retreated from.

## 4. What changed (backend)

- `api/solar_events.py` (new): the event catalog and the `alert_level()` ratio logic, all constants sourced per §2.
- `api/alerts.py`: `_solar_event_rule()`, wired into `sol_time_and_alerts()` via a new optional `peak_dose_ugy_per_day` parameter (default `None` -- existing callers unaffected).
- `api/main.py`: `/api/conditions` and the `/api/ask` agent context both now pass the sol's peak dose through.
- `api/replan.py`: new `"radiation"` problem category (keywords: radiation, solar, flare, particle), reusing the existing A*-based option-generation mechanics -- no new routing logic.
- `data-pipeline/scripts/cache_conditions.py`: `peak_dose_ugy_per_hour` field added to the RAD summary (additive).
- `data-pipeline/adapters/pds_rad.py`: zero-padding bugfix (see §2).

## 5. What changed (frontend)

- `web/app.js`: new `renderConditions()`, fetching `/api/conditions` on load and rendering any alerts (dust season, stale data, solar event) into the existing `#c-status` panel, reusing the route card's own `.suggestion-reason.v-safe/.v-caution/.v-danger` styling -- no new visual language introduced.
- `web/api.js`: `getConditions(sol)` now accepts an optional sol (previously always the reference sol).
- **Not done, scoped out for time:** a UI control to switch which sol `#c-status` shows (e.g., live-reusing the route card's EVA sol-stepper). Today, viewing the sol-242 demo requires requesting `/api/conditions?sol=242` directly (e.g., by URL) rather than a button in the UI. Flagged here so it is not mistaken for forgotten -- it is a deliberate cut, open to revisit.

## 6. Open follow-ups

- Pin the exact sol + dose for the Sept-2017 and May-2024 RAD-measured events (same method as §2), to extend `KNOWN_EVENTS`.
- Decide whether `#c-status` should get a sol selector of its own, or hook into the route card's existing stepper.
