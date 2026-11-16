# Feature 09 (extension) · Simulated Earth-Mars sync

2026-11-15 · Requested by a teammate's mentor: the original proposal promises
Earth-Mars synchronization (P2/pitch tier), but nothing was ever built for
it -- "não tem nem a base". This closes that gap with a small, honest
simulation: real data, fake transport.

## 1. The idea, in one sentence

Simulate the arrival of a real data packet from Earth (with the real kind
of wait a relay pass implies), without ever making a network call while
the system is running -- CLAUDE.md forbids that outside the ETL/build
step, and this feature respects it exactly.

## 2. How Mars-Earth contact actually works (the real thing being simulated)

Mars missions do not have continuous contact with Earth, not even NASA's
own. The real mechanism:

- A rover/lander does not talk to Earth directly most of the time. It
  relays through orbiters already circling Mars (Mars Reconnaissance
  Orbiter, Mars Odyssey) during **scheduled UHF passes** -- windows that
  open when one of those orbiters is overhead, roughly twice per sol in
  JPL's own mission-planning estimate (~250 Mb/sol via MRO, recorded and
  played back to Earth later; ~75 Mb/sol via Odyssey, closer to real
  time). Source: spaceflightnow.com, 2012-07-31, citing a JPL relay
  planning briefing for MSL.
- Outside those passes: no contact at all. Terrain can also block a pass
  (a NASA science blog noted buttes partially blocking the Curiosity-MRO
  line of sight).
- On top of that, every ~26 months Mars passes behind the Sun (solar
  conjunction), and radio contact is unsafe for commands for about two
  weeks. In the November 2023 conjunction, NASA held commands from Nov 11
  to Nov 25, after pre-loading both active rovers with two weeks' worth of
  commands to run on their own. Source: NASA public statements covered by
  multiple outlets (e.g. theweathernetwork.com, accuweather.com,
  2023-11).
- On top of both: the one-way radio delay itself is 4 to 24 minutes,
  depending on where Earth and Mars are in their orbits (already cited in
  this project's `docs/Plano_Produto_Completo.md` and `CLAUDE.md`).

So "sync with Earth" in real life means: *wait for the next scheduled
relay pass (not continuous), accept the 4-24 min delay once it happens,
and expect it to stop completely for weeks during conjunction.* This
feature's button represents one such pass delivering a packet.

## 3. The architecture problem this creates, and how it is solved

CLAUDE.md requires: no network call anywhere except the ETL (build step),
never in the API or the front. A literal "contact Earth" simulation would
need network at runtime to be convincing -- which is exactly what is
banned.

**Resolution:** at build time (when network IS allowed), a real, newer sol
is fetched ahead of the demo and stored separately from the active cache,
untouched. At runtime, "syncing" is just **revealing that one local file**
-- a file move, not a transmission. The data is 100% real (fetched from
the same PDS sources as every other sol in this project); only the
*timing* of when it becomes visible to the running system is staged.

```
build time (network allowed):
  fetch_earth_sync_package.py --> data/local/earth_sync/pending.json
    (a real sol newer than REFERENCE_SOL, not yet in data/local/conditions/)

demo time (no network at all):
  GET  /api/earth-sync/status  --> {"pending": true, "sol": 4800, ...}
  [UI: "Sync with Earth" button, simulated wait -- see below]
  POST /api/earth-sync/apply   --> moves pending.json into
                                    data/local/conditions/sol_4800.json
                                    (same folder/format as any other sol)
                                --> returns what that sol's real alerts say
```

Once applied, `/api/conditions?sol=4800` and everything downstream (the
route card's EVA window, `/api/ask`) read it exactly like any other
cached sol -- no special case needed there, by design.

## 4. Sources (every number traced to where it came from)

| Value | Status | Source |
|---|---|---|
| ~2 relay passes/sol, ~250 Mb via MRO + ~75 Mb via Odyssey | Real, a JPL mission-planning estimate (not a live current figure -- this session could not find a current per-sol count) | spaceflightnow.com, 2012-07-31, citing JPL |
| Nov 2023 solar conjunction: commands held 2023-11-11 to 2023-11-25, ~2 weeks of pre-loaded commands | Real, that specific event | NASA public communications, covered 2023-11 (theweathernetwork.com, accuweather.com) |
| Conjunction recurs about every 26 months | Real | same coverage |
| One-way delay 4 to 24 minutes | Real, already used elsewhere in this project | `docs/Plano_Produto_Completo.md`, `CLAUDE.md` |
| Sol 4800 REMS/RAD readings used in the demo package | **Real, primary** -- fetched directly via `data-pipeline/adapters/pds_rems.py` / `pds_rad.py`, same adapters as every other cached sol | PDS Atmospheres Node + PDS-PPI, sol 4800 |
| The 3-second simulated wait in the UI | **Declared stand-in**, not a real delay -- a demo cannot wait up to 24 real minutes; the UI says so explicitly, citing the real range | H2G2, this feature |

## 5. What changed (backend)

- `data-pipeline/scripts/fetch_earth_sync_package.py` (new, ETL only): fetches
  one real sol (default 4800) via the existing REMS/RAD adapters, reusing
  `cache_conditions.py`'s own summary functions, and writes it to
  `data/local/earth_sync/pending.json` -- deliberately outside
  `data/local/conditions/`, so the running system cannot see it until asked.
- `api/earth_sync.py` (new): `GET /api/earth-sync/status` (is a package
  waiting? which sol? -- never the content, that would spoil the "what
  changed" reveal) and `POST /api/earth-sync/apply` (reveals it: writes it
  into `data/local/conditions/`, in the exact format `api/conditions.py`
  already reads, and returns the real alerts that sol produces). No
  network call in this module, ever -- see the module docstring.
  One-shot: applying it consumes the pending file, like a pass that
  already happened.
- `api/main.py`: registers the new router, same pattern as `panorama`/`science_card`.
- `api/test_earth_sync.py` (6 tests): status with/without a pending package,
  the documented delay range, applying with nothing pending (clear 404),
  applying for real (writes the cache file, real alert rule fires, the
  pending file is consumed), and applying safely when the sol was somehow
  already cached (no silent overwrite/crash).

## 6. What changed (frontend)

- `web/api.js`: `getEarthSyncStatus()`, `applyEarthSync()`.
- `web/app.js`: on load, checks `/api/earth-sync/status` alongside the
  existing conditions check. If a package is waiting, the `#c-status`
  panel (the same one used for solar-event/dust-storm/dust-season alerts)
  shows a **"Sync with Earth · sol N waiting"** button. Clicking it runs a
  3-second simulated wait (explicitly labeled "simulating transmission
  delay (real Earth-Mars one-way range: 4-24 min, NASA/JPL)"), then calls
  `apply` and shows what the real reading says -- the first non-`stale_data`
  alert if there is one, or an honest "no hazard in this one" if not.

## 7. What is deliberately out of scope

- **Live orbital-mechanics delay calculation.** The 4-24 min figure is
  shown as a fixed, cited range, not computed from the actual Earth-Mars
  distance at a given moment -- that would need real ephemeris data this
  project does not load, disproportionate for what this feature needs to
  demonstrate.
- **Photo/panorama/science-target sync.** The original proposal's own
  priority order is "alerts first, then climate, then images" -- this
  extension only does the first tier. Images are a larger, separate task.
- **A queue of several pending packages.** Only "one waiting / none
  waiting" -- matches the proposal's own demo framing ("a sync button with
  simulated delay and a list of what changed"), without over-building for
  a hackathon demo.
- **Multiple relay-pass outcomes** (a pass that fails due to geometry/
  terrain, as real missions do experience). Documented here as a real,
  sourced phenomenon, but not modeled -- this feature only demonstrates a
  successful pass.
