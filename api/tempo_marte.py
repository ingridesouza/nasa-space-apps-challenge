"""Feature 08, fase 3 (modo sem Terra): tempo marciano sem rede.

Ls e Mars Sol Date pelo algoritmo do Mars24 (NASA GISS, Allison & McEwen 2000):
https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
Sol do Curiosity = dias solares médios em Gale desde o pouso (sol 0)."""

import math
from datetime import datetime, timedelta, timezone

TT_MENOS_UTC_S = 69.184  # 37 s de leap seconds + 32,184 s; vale desde 2017
POUSO_MSL = datetime(2012, 8, 6, 5, 17, 57, tzinfo=timezone.utc)
LON_GALE_E = 137.4
SOL_S = 88775.244  # 1,0274912517 dia terrestre

# termos periódicos das perturbações planetárias (tabela 5 do Mars24)
_PBS = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528),
        (0.0018, 32.8493, 49.095)]


def _dt_j2000(t: datetime) -> float:
    """Dias (TT) desde J2000."""
    jd_ut = 2440587.5 + t.timestamp() / 86400
    return jd_ut + TT_MENOS_UTC_S / 86400 - 2451545.0


def ls(t: datetime) -> float:
    """Longitude solar de Marte (graus, 0–360): a estação do ano marciano."""
    d = _dt_j2000(t)
    m = math.radians(19.3871 + 0.52402073 * d)
    alfa = 270.3871 + 0.524038496 * d
    pbs = sum(a * math.cos(math.radians(0.985626 * d / tau + fi)) for a, tau, fi in _PBS)
    v_m = ((10.691 + 3.0e-7 * d) * math.sin(m) + 0.623 * math.sin(2 * m) + 0.050 * math.sin(3 * m)
           + 0.005 * math.sin(4 * m) + 0.0005 * math.sin(5 * m) + pbs)
    return (alfa + v_m) % 360


def _msd_gale(t: datetime) -> float:
    """Mars Sol Date no horário médio local de Gale."""
    return (_dt_j2000(t) - 4.5) / 1.0274912517 + 44796.0 - 0.0009626 + LON_GALE_E / 360


def sol_msl(t: datetime) -> int:
    return math.floor(_msd_gale(t)) - math.floor(_msd_gale(POUSO_MSL))


def data_do_sol(sol: int) -> datetime:
    """Meio-dia local (Gale) do sol pedido, em UTC."""
    alvo = math.floor(_msd_gale(POUSO_MSL)) + sol + 0.5
    return POUSO_MSL + timedelta(seconds=(alvo - _msd_gale(POUSO_MSL)) * SOL_S)
