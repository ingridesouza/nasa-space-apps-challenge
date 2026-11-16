"""Solar particle event (SPE) alert -- new hazard category, identified from
real NASA EVA abort/contingency research (full sources in
docs/feature-05-solar-particle-event.md). The system runs 100% offline
(CLAUDE.md): there is no live solar-wind feed here, and there should not
be one. Instead of simulating a live event, this module replays a REAL
event already measured on the ground by MSL RAD -- the same instrument
api/conditions.py already reads for every sol.

Every threshold below is labeled real or declared (H2G2 proposal) --
see the module docstring of each constant."""

# Real event catalog: sol and dose CONFIRMED by fetching the primary PDS-PPI
# RAD file ourselves (data-pipeline/adapters/pds_rad.py), not copied from a
# secondary summary. More can be added once their exact sol + dose are
# confirmed the same way (candidates found but not yet pinned: the Sept-2017
# event, described as "the largest SEP so far observed by RAD... peak dose
# rate nearly 3x the galactic cosmic ray level"; and a May-2024 event, "the
# biggest RAD surge since landing" -- see the planning doc).
#
# dose_ugy_per_day here is the sol's PEAK hourly reading x24, not the day's
# mean -- a solar particle event is a short-duration rate spike that a 24h
# mean dilutes away (confirmed while fetching this one: the day's mean came
# out to 233 uGy/day, well short of the event; the peak reading matched the
# literature's ~260 uGy/day almost exactly). See
# data-pipeline/scripts/cache_conditions.py, summarize_rad().
KNOWN_EVENTS = {
    242: {
        "date": "2013-04-12",
        "dose_ugy_per_day": 260.9,
        "source": (
            "MSL RAD, PDS-PPI (UCLA), sol 242 (12-13 Apr 2013): peak reading "
            "10.87 uGy/h (x24 = 260.9 uGy/day) -- fetched directly via "
            "data-pipeline/adapters/pds_rad.py. RAD's one hard SEP event in "
            "its first ~300 sols on the surface."
        ),
    },
}

# H2G2 proposal: no official surface-EVA alert threshold was found in this
# session's research (the real precedent found, NASA's Artemis II "two-tier"
# alert, is documented for the Orion vehicle, not for a surface EVA suit).
# The background reference below is OUR OWN cached REFERENCE_SOL peak
# reading (sol 4650: 7.02 uGy/h x24 = 168.5 uGy/day), not a published
# long-term average -- declared as such, not official. Same peak-based
# metric as the event above, so the ratio compares like with like.
BACKGROUND_DOSE_UGY_PER_DAY = 168.5
CAUTION_RATIO = 1.5

# Anchored to a real number, not arbitrary: the Sept-2017 RAD event (the
# largest surface SEP documented to date) is described as reaching "nearly
# 3x the galactic cosmic ray level" -- this sets the "danger/shelter" tier
# at the same relative elevation as the most significant surface SEP NASA
# has actually measured.
DANGER_RATIO = 3.0

# NASA-STD-3001: short-term effective dose limit for a single SPE (used
# for context in the alert message, not as the tier threshold itself --
# see the planning doc for why the two are different quantities).
EVENT_DOSE_LIMIT_MSV = 250


def known_event(sol: int) -> dict | None:
    """The real catalogued SPE at this sol, or None -- never invents an
    event for a sol that was not actually measured as one."""
    return KNOWN_EVENTS.get(sol)


def alert_level(dose_ugy_per_day: float | None) -> str | None:
    """None/"caution"/"danger" from a measured dose rate vs. the real
    background reference above. None whenever there is no dose to compare
    (CLAUDE.md: no data, no number -- never guesses a level)."""
    if dose_ugy_per_day is None or BACKGROUND_DOSE_UGY_PER_DAY <= 0:
        return None
    ratio = dose_ugy_per_day / BACKGROUND_DOSE_UGY_PER_DAY
    if ratio >= DANGER_RATIO:
        return "danger"
    if ratio >= CAUTION_RATIO:
        return "caution"
    return None
