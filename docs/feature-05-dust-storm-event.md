# Feature 05 (extension) · Global dust storm alert

2026-11-15 · Second hazard added to the "replay a real event" pattern started
with the solar particle event (`docs/feature-05-solar-particle-event.md`).
Same architecture, same honesty rules, different instrument signature.

## 1. The idea, in one sentence

Instead of simulating live dust-opacity sensing (the system is offline,
CLAUDE.md), the system replays the REAL 2018 global dust storm already
measured on the ground by MSL REMS, and raises the alert it would raise
if that storm were happening on the sol being viewed.

## 2. Sources

| Value | Status | Source |
|---|---|---|
| The 2018 event was a *global* dust storm (the most severe category NASA tracks) | Real, documented | Guzewich et al. 2019, "MSL Observations of the 2018 Global Dust Storm"; Viudez-Moreiras et al. 2019, "Effects of the 2018 Global Dust Storm as Measured by REMS" — both already cited in `docs/feature-08-agente-local.md` |
| Sol range at Gale: ~2074 to ~2140 | Real, from the literature above | same papers |
| Sol 2082 (during the storm): diurnal air-temp range 45.8 C (Tmax -10.9, Tmin -56.7), mean pressure 770.7 Pa | **Real, primary** — fetched directly from PDS Atmospheres by this session (`data-pipeline/adapters/pds_rems.py`), not copied from a secondary summary | PDS Atmospheres Node, MSL REMS calibrated data, sol 2082 |
| Sol 2060 (pre-storm baseline, same Mars year, 22 sols earlier): diurnal range 75.8 C (Tmax 3.9, Tmin -71.9), mean pressure 738.4 Pa | **Real, primary** — fetched the same way | PDS Atmospheres Node, MSL REMS, sol 2060 |

**Why the diurnal temperature range, and why only one severity tier:**
airborne dust blocks sunlight during the day and traps heat at night, so the
gap between the day's max and min air temperature collapses during a global
storm — exactly what the two real sols above show (75.8 C down to 45.8 C, a
40% collapse). Unlike the solar event (which has graded real data for a
caution and a danger tier), this session only confirmed ONE real dust storm.
Since it is already the most severe kind NASA classifies, a single "danger"
tier is the honest choice — inventing a "caution" threshold without a second,
less-severe real event to anchor it would not meet this project's sourcing
bar (see `docs/fontes-de-dados.md`).

**No generic ratio rule.** The solar event module also has a ratio rule that
can fire on any sol, not just the catalogued one (peak dose vs. background).
This module does not: the diurnal temperature range varies a lot by season
even with zero dust, and no declared, source-backed seasonal baseline exists
for every Ls in this project yet. A generic threshold here would risk false
alarms on an ordinary cold/dry sol — so the alert only fires for the sol
range of this one confirmed, real storm.

## 3. What changed (backend)

- `api/dust_storm_events.py` (new): the event, the real sol range, and
  `alert_level()`/`known_event()`, same shape as `solar_events.py`.
- `api/alerts.py`: new `_dust_storm_rule()`, wired into `sol_time_and_alerts()`
  additively, next to the existing `_solar_event_rule()`. Distinct from the
  pre-existing `DUST_LS` seasonal rule (a generic "dust season" caution for
  any sol in the right Ls window) — this one fires only for the specific,
  confirmed real storm.
- `api/replan.py` already had a `"dust"` problem category (keywords: dust,
  storm, wind) reusing the return-to-base pattern — no change needed there;
  it already covers "I am reporting dust right now" during the walk. This
  extension adds the planning-time, sol-specific prediction side that was
  missing (the same gap the solar event closed for radiation).

## 4. What changed (frontend)

- `web/ui/route.js`: the EVA window banner (previously hardcoded to
  "Solar particle event") now shows either hazard by its real label
  (`HAZARD_LABEL = {solar_event: "Solar particle event", dust_storm_event:
  "Dust storm"}`), picking whichever one the viewed sol's conditions carry.
  The "Radiation" row highlight stays specific to `solar_event` (a dust
  storm has no dose number to color).
- `web/app.js`'s `renderConditions()` needed no change: it already renders
  any alert in `/api/conditions` generically.

## 5. Why this one, and not landslide / suit failure

The same research pass that found the solar event also raised landslide and
suit-failure (leak/toxic gas) as candidate hazards. They were not built as a
third "replay a real historical event" module, for a concrete reason each:

- **Suit failure / leak / toxic gas:** already handled, just not by a
  sol-specific predictive alert — `api/agent.py`'s `DISTRESS` regex answers
  these immediately with a fixed procedure, and `api/replan.py`'s `"oxygen"`
  category already offers return-to-base options. There is no real dataset
  of past Mars suit-failure sensor readings to replay the way RAD/REMS let
  us replay a real radiation or dust event.
- **Landslide / loose terrain:** already covered, as a qualitative warning,
  not a numeric prediction — `route_planning.py`'s `SAND_WARNING`, sourced to
  the real Curiosity operators' account of wheel slip in the boxwork
  hollows (cited in `docs/feature-08-agente-local.md`). AI4Mars (the dataset
  that could make this a per-pixel numeric risk) does not cover the boxwork
  campaign period, so a numeric alert here would need data we do not have.

So the dust storm was the only remaining candidate with the same kind of
primary, fetchable, graded real data the solar event already used.
