"""Feature 08, phase 3 (no-Earth mode): Martian time without network.

Ls and Mars Sol Date by the Mars24 algorithm (NASA GISS, Allison & McEwen 2000):
https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
Curiosity sol = mean solar days at Gale since landing (sol 0)."""

import math
import os
import time
from datetime import datetime, timedelta, timezone

TT_MINUS_UTC_S = 69.184  # 37 s of leap seconds + 32.184 s; valid since 2017
MSL_LANDING = datetime(2012, 8, 6, 5, 17, 57, tzinfo=timezone.utc)
GALE_LON_E = 137.4
SOL_S = 88775.244  # 1.0274912517 Earth days

# periodic terms of the planetary perturbations (Mars24 table 5)
_PBS = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528),
        (0.0018, 32.8493, 49.095)]


def _dt_j2000(t: datetime) -> float:
    """Days (TT) since J2000."""
    jd_ut = 2440587.5 + t.timestamp() / 86400
    return jd_ut + TT_MINUS_UTC_S / 86400 - 2451545.0


def ls(t: datetime) -> float:
    """Solar longitude of Mars (degrees, 0–360): the Martian season."""
    return _ls_and_center(t)[0]


def _ls_and_center(t: datetime) -> tuple[float, float]:
    """(Ls, equation of center ν−M in degrees) -- Mars24 steps B-1 to B-5."""
    d = _dt_j2000(t)
    m = math.radians(19.3871 + 0.52402073 * d)
    alpha = 270.3871 + 0.524038496 * d
    pbs = sum(a * math.cos(math.radians(0.985626 * d / tau + phi)) for a, tau, phi in _PBS)
    v_m = ((10.691 + 3.0e-7 * d) * math.sin(m) + 0.623 * math.sin(2 * m) + 0.050 * math.sin(3 * m)
           + 0.005 * math.sin(4 * m) + 0.0005 * math.sin(5 * m) + pbs)
    return (alpha + v_m) % 360, v_m


def _msd_gale(t: datetime) -> float:
    """Mars Sol Date at Gale local mean time."""
    return (_dt_j2000(t) - 4.5) / 1.0274912517 + 44796.0 - 0.0009626 + GALE_LON_E / 360


def sol_msl(t: datetime) -> int:
    return math.floor(_msd_gale(t)) - math.floor(_msd_gale(MSL_LANDING))


def sol_date(sol: int) -> datetime:
    """Local noon (Gale) of the given sol, in UTC."""
    target = math.floor(_msd_gale(MSL_LANDING)) + sol + 0.5
    return MSL_LANDING + timedelta(seconds=(target - _msd_gale(MSL_LANDING)) * SOL_S)


# --------------------------------------------------------------------------- #
# Sun position (Mars24, steps B-1, C-2 and D-5 of the same algorithm)
# --------------------------------------------------------------------------- #
def sun_declination(ls_deg: float) -> float:
    """Declination of the Sun as seen from Mars (degrees), from Ls."""
    s = math.sin(math.radians(ls_deg))
    return math.degrees(math.asin(0.42565 * s)) + 0.25 * s


def sun_distance_au(t: datetime) -> float:
    """Heliocentric distance of Mars (AU)."""
    m = math.radians(19.3871 + 0.52402073 * _dt_j2000(t))
    return 1.52367934 * (1.00436 - 0.09309 * math.cos(m) - 0.004336 * math.cos(2 * m)
                         - 0.00031 * math.cos(3 * m) - 0.00003 * math.cos(4 * m))


def sun_position(lat_deg: float, declination: float, solar_hour: float) -> tuple[float, float]:
    """(elevation, azimuth) of the Sun in degrees; azimuth from north, clockwise.
    solar_hour = local true solar time (LTST), 12 = Sun on the meridian."""
    phi, de = math.radians(lat_deg), math.radians(declination)
    h = math.radians(15 * (solar_hour - 12))
    sin_el = math.sin(phi) * math.sin(de) + math.cos(phi) * math.cos(de) * math.cos(h)
    el = math.asin(max(-1.0, min(1.0, sin_el)))
    az = math.atan2(-math.cos(de) * math.sin(h), math.cos(phi) * math.sin(de) - math.sin(phi) * math.cos(de) * math.cos(h))
    return math.degrees(el), math.degrees(az) % 360


# --------------------------------------------------------------------------- #
# Local time at Gale and simulated clock
# --------------------------------------------------------------------------- #
MARS_HOUR_S = SOL_S / 24


def equation_of_time_h(t: datetime) -> float:
    """LTST − LMST in hours (Mars24 C-1): the true Sun runs ahead or behind by up to ~50 min."""
    l, center = _ls_and_center(t)
    r = math.radians(l)
    eot_deg = 2.861 * math.sin(2 * r) - 0.071 * math.sin(4 * r) + 0.002 * math.sin(6 * r) - center
    return eot_deg / 15


def local_time(t: datetime) -> dict:
    """Curiosity sol and local times at Gale: LMST (mean) and LTST (true solar, the Sun in the sky)."""
    lmst = (_msd_gale(t) % 1) * 24
    return {"sol": sol_msl(t), "lmst": round(lmst, 3), "ltst": round((lmst + equation_of_time_h(t)) % 24, 3)}


def sol_moment(sol: int, ltst: float) -> datetime:
    """Instant (UTC) when the true solar time at Gale equals `ltst` on the given sol."""
    noon = sol_date(sol)  # LMST 12h
    return noon + timedelta(seconds=(ltst - equation_of_time_h(noon) - 12) * MARS_HOUR_S)


# Simulated clock: there is no real mission clock. It starts at a fictional
# sol/solar hour (env H2G2_CLOCK="SOL@HH:MM", true solar time) and runs in
# real time since the API started. Without env: today's sol at 08:00.
_REAL_START = time.time()


def _simulated_start() -> datetime:
    cfg = os.environ.get("H2G2_CLOCK", "")
    if "@" in cfg:
        sol, hhmm = cfg.split("@")
        h, m = hhmm.split(":")
        return sol_moment(int(sol), int(h) + int(m) / 60)
    return sol_moment(sol_msl(datetime.now(timezone.utc)), 8.0)


_SIMULATED_START = _simulated_start()


def now() -> datetime:
    """Now on the simulated mission clock (UTC)."""
    return _SIMULATED_START + timedelta(seconds=time.time() - _REAL_START)
