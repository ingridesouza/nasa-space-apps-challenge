"""Global dust storm alert -- same pattern as solar_events.py: instead of
simulating a live dust-opacity feed (the system is offline, CLAUDE.md),
this module replays a REAL dust storm already measured on the ground by
MSL REMS, the 2018 global dust storm (the most severe category NASA
tracks -- not a regional storm).

Signature used: the diurnal air-temperature range (Tmax - Tmin) collapses
during a global dust storm, because airborne dust blocks sunlight during
the day and traps heat at night (both REMS BOOM1_AIR_TEMP). Confirmed by
fetching two real sols ourselves (data-pipeline/adapters/pds_rems.py),
not copied from a secondary summary:

  sol 2082 (during the storm, within the Guzewich et al. 2019 onset window):
    Tmax -10.9 C, Tmin -56.7 C -> diurnal range 45.8 C
    mean pressure 770.7 Pa
  sol 2060 (22 sols earlier, same Mars year/season, pre-storm baseline):
    Tmax 3.9 C, Tmin -71.9 C -> diurnal range 75.8 C
    mean pressure 738.4 Pa

That is a 40% collapse of the diurnal range and a +4.4% rise in mean
pressure during the storm -- both consistent with the literature
(Guzewich et al. 2019, "MSL Observations of the 2018 Global Dust Storm";
Viudez-Moreiras et al. 2019, "Effects of the 2018 Global Dust Storm as
Measured by REMS" -- both cited in docs/feature-08-agente-local.md).

Only this one real, confirmed event is catalogued. No generic rule
compares an arbitrary sol's diurnal range against a "normal" value: the
range varies a lot by season even with no dust at all, and we have no
declared, source-backed baseline for every season -- a generic ratio
rule here would risk false alarms, which this module avoids (same
principle as "no data, no number").
"""

# Real sol range the literature attributes to the 2018 global dust storm
# reaching Gale (Guzewich et al. 2019): onset around sol 2074, tapering off
# by about sol 2140. CONFIRMED_SOL is the one this session fetched directly.
EVENT_SOL_RANGE = (2074, 2140)
CONFIRMED_SOL = 2082

KNOWN_EVENTS = {
    "range": EVENT_SOL_RANGE,
    "date": "2018-06 to 2018-09",
    "diurnal_range_c": 45.8,
    "background_diurnal_range_c": 75.8,
    "mean_pressure_pa": 770.7,
    "background_mean_pressure_pa": 738.4,
    "source": (
        "MSL REMS, PDS Atmospheres Node: sol 2082 (during the 2018 global dust "
        "storm) fetched directly via data-pipeline/adapters/pds_rems.py -- "
        "diurnal range 45.8 C (Tmax -10.9, Tmin -56.7), vs. 75.8 C on sol 2060 "
        "(pre-storm baseline, same Mars year). Guzewich et al. 2019 and "
        "Viudez-Moreiras et al. 2019 document the same storm at Gale."
    ),
}


def known_event(sol: int) -> dict | None:
    """The real catalogued 2018 global dust storm, if `sol` falls inside the
    sol range the literature attributes to it at Gale -- never invents an
    event for a sol that was not actually part of it."""
    lo, hi = KNOWN_EVENTS["range"]
    return KNOWN_EVENTS if lo <= sol <= hi else None


def alert_level(sol: int) -> str | None:
    """"danger" for any sol inside the real 2018 global dust storm window,
    None otherwise. No intermediate "caution" tier: a GLOBAL dust storm is
    already the most severe category NASA tracks for Mars dust events, so a
    single tier is the honest one -- grading it further would need a second
    real event of lesser severity, which this session has not confirmed
    (see the module docstring)."""
    return "danger" if known_event(sol) is not None else None
