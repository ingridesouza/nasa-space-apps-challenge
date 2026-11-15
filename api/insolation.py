"""Direct insolation and shade per hour, computed from the relief (inferred, not measured).

For a sol and a local solar hour:
- Sun position by Mars24 (mars_time.py);
- light incidence on each pixel from the slope/aspect of the HiRISE DTM (2 m,
  downsampled from the native 1 m);
- near shade: a walk toward the Sun over the same DTM;
- far shade: regional MOLA horizon (Mount Sharp outside the crop).

What is NOT included: dust attenuation and diffuse light (the day's opacity is not
known offline). The value is the DIRECT top-of-atmosphere irradiance projected
onto the terrain: an upper bound. In the shade there is still diffuse sky light.
Relief smaller than ~2-3 m (thin boxwork ridges) does not show up."""

import functools
import math
import os

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from geo import MARS_METERS_PER_DEGREE
from mars_time import ls, sol_date, sun_declination, sun_distance_au, sun_position

TILES = os.path.join(os.path.dirname(__file__), "..", "data", "local", "tiles")
DTM = os.path.join(TILES, "dtm_hirise_1m_native", "dem_3011x2999.tif")
MOLA = os.path.join(TILES, "mola_regional_topography", "dem_256x256.tif")
FACTOR = 2  # 1 m -> 2 m: computed in ~2 s per hour instead of ~8
SOLAR_CONSTANT = 1361.0  # W/m² at 1 AU
LAT_REF = -4.80  # crop center; the latitude variation over 3 km is negligible for the Sun
SOURCE = "Inferred: Sun by Mars24 + HiRISE Gale DTM (2 m, from native 1 m) + regional MOLA (distant horizon)"


@functools.lru_cache(maxsize=1)
def _relief():
    """(z[h,w] in m, transform, crs, pixel size in m) of the downsampled DTM."""
    with rasterio.open(DTM) as ds:
        z = ds.read(1).astype("float64")
        t, crs = ds.transform, ds.crs
    h, w = (z.shape[0] // FACTOR) * FACTOR, (z.shape[1] // FACTOR) * FACTOR
    z = z[:h, :w].reshape(h // FACTOR, FACTOR, w // FACTOR, FACTOR).mean(axis=(1, 3))
    t = t * rasterio.Affine.scale(FACTOR)
    return z, t, crs, abs(t.a) * MARS_METERS_PER_DEGREE


def sun_at_hour(sol: int, hour: float) -> dict:
    t = sol_date(sol)
    l = ls(t)
    el, az = sun_position(LAT_REF, sun_declination(l), hour)
    r = sun_distance_au(t)
    return {"sol": sol, "solar_hour": hour, "ls": round(l, 1), "sun_elevation": round(el, 1), "sun_azimuth": round(az, 1),
            "toa_irradiance_w_m2": round(SOLAR_CONSTANT / r**2), "distance_au": round(r, 3), "source": SOURCE,
            "confidence": "inferred"}


def _shift(z: np.ndarray, dl: int, dc: int) -> np.ndarray:
    """Shifted z: out[l, c] = z[l+dl, c+dc]; outside the grid = -inf (casts no shade)."""
    out = np.full_like(z, -np.inf)
    h, w = z.shape
    if abs(dl) >= h or abs(dc) >= w:
        return out
    out[max(0, -dl):h - max(0, dl), max(0, -dc):w - max(0, dc)] = z[max(0, dl):h - max(0, -dl), max(0, dc):w - max(0, -dc)]
    return out


def _near_shade(z: np.ndarray, px_m: float, el: float, az: float) -> np.ndarray:
    """True where the crop itself blocks the Sun. The step grows with distance (2% of it)."""
    tg = math.tan(math.radians(el))
    reach = min((z.max() - z.min()) / tg, math.hypot(*z.shape) * px_m)
    sine, cosine = math.sin(math.radians(az)), math.cos(math.radians(az))
    shade = np.zeros(z.shape, dtype=bool)
    d, seen = px_m, set()
    while d <= reach:
        dc, dl = round(d * sine / px_m), round(-d * cosine / px_m)  # east = +column, north = -row
        if (dl, dc) not in seen:
            seen.add((dl, dc))
            shade |= _shift(z, dl, dc) - z > d * tg
        d += max(px_m, 0.02 * d)
    return shade


@functools.lru_cache(maxsize=1)
def _mola():
    with rasterio.open(MOLA) as ds:
        return ds.read(1).astype("float64"), ds.transform


def _far_horizon(z: np.ndarray, t, el: float, az: float) -> np.ndarray:
    """True where the relief OUTSIDE the crop (MOLA, 2 to 60 km toward the Sun) blocks the Sun.
    Computed on an 8x coarser grid: the distant horizon changes slowly across the crop."""
    mz, mt = _mola()
    h, w = z.shape
    lon0, lat0 = t * (w / 2, h / 2)
    sine, cosine = math.sin(math.radians(az)), math.cos(math.radians(az))
    points = []
    for d in np.arange(2000, 60000, 400):
        lon = lon0 + d * sine / (MARS_METERS_PER_DEGREE * math.cos(math.radians(lat0)))
        lat = lat0 + d * cosine / MARS_METERS_PER_DEGREE
        c, l = ~mt * (lon, lat)
        if 0 <= int(l) < mz.shape[0] and 0 <= int(c) < mz.shape[1]:
            points.append((d, mz[int(l), int(c)]))
    if not points:
        return np.zeros(z.shape, dtype=bool)
    d_i, z_i = np.array(points).T
    step = 8
    zg = z[::step, ::step]
    ll, cc = np.mgrid[0:h:step, 0:w:step]
    px_m = abs(t.a) * MARS_METERS_PER_DEGREE
    proj = ((cc - w / 2) * sine - (ll - h / 2) * cosine) * px_m  # how much closer to the Sun the pixel is than the center
    tg_horiz = ((z_i[None, None, :] - zg[..., None]) / (d_i[None, None, :] - proj[..., None])).max(axis=-1)
    blocked = tg_horiz > math.tan(math.radians(el))
    return np.repeat(np.repeat(blocked, step, axis=0), step, axis=1)[:h, :w]


@functools.lru_cache(maxsize=16)
def insolation_grid(sol: int, hour: float):
    """(fraction[h,w] 0-1 = cos of incidence, 0 in shade; shade[h,w] bool; transform; crs)."""
    z, t, crs, px_m = _relief()
    info = sun_at_hour(sol, hour)
    el, az = info["sun_elevation"], info["sun_azimuth"]
    if el <= 0:
        return np.zeros(z.shape), np.ones(z.shape, dtype=bool), t, crs
    dzdl, dzdc = np.gradient(z, px_m)
    nx, ny = -dzdc, dzdl  # normal (east, north, up) not normalized; row grows southward
    sx = math.cos(math.radians(el)) * math.sin(math.radians(az))
    sy = math.cos(math.radians(el)) * math.cos(math.radians(az))
    sz = math.sin(math.radians(el))
    cos_i = np.clip((nx * sx + ny * sy + sz) / np.sqrt(nx**2 + ny**2 + 1), 0, 1)
    shade = (cos_i <= 0) | _near_shade(z, px_m, el, az) | _far_horizon(z, t, el, az)
    return np.where(shade, 0.0, cos_i), shade, t, crs


def insolation_grid_rgba(sol: int, hour: float):
    """Layer: shade in dark blue; lit from blue (grazing light) to yellow (Sun head-on)."""
    fraction, shade, t, crs = insolation_grid(sol, hour)
    rgba = np.zeros((4, *fraction.shape), dtype="uint8")
    for i, (a, b) in enumerate(((60, 245), (110, 205), (190, 70))):
        rgba[i] = (a + (b - a) * fraction).astype("uint8")
    rgba[3] = 140
    rgba[:3, shade] = np.array([15, 20, 60], dtype="uint8")[:, None]
    rgba[3, shade] = 190
    return rgba, t, crs


AREA_RADIUS_M = 20  # verdict by area: shade on a single pixel was not validated (docs/feature-01-camada-insolacao.md)


def at_point(sol: int, hour: float, lat: float, lon: float) -> dict | None:
    """Direct sun over the ~20 m area around the point: category 'sun' / 'partial' / 'shade'."""
    fraction, shade, t, _ = insolation_grid(sol, hour)
    c, l = ~t * (lon, lat)
    l, c = int(l), int(c)
    if not (0 <= l < fraction.shape[0] and 0 <= c < fraction.shape[1]):
        return None
    _, _, _, px_m = _relief()
    r = max(1, round(AREA_RADIUS_M / px_m))
    area_shade = shade[max(0, l - r):l + r + 1, max(0, c - r):c + r + 1]
    area_fraction = fraction[max(0, l - r):l + r + 1, max(0, c - r):c + r + 1]
    shade_pct = float(area_shade.mean())
    info = sun_at_hour(sol, hour)
    category = "shade" if info["sun_elevation"] <= 0 or shade_pct >= 0.8 else "partial" if shade_pct >= 0.2 else "sun"
    return {**info, "category": category, "shade_area_pct": round(100 * shade_pct), "area_radius_m": AREA_RADIUS_M,
            # upper bound, no dust: only in the endpoint, not in the interface
            "max_direct_irradiance_w_m2": round(float(area_fraction.mean()) * info["toa_irradiance_w_m2"])}
