"""Vertical integration of bird profiles and migration traffic over time.

With layer thickness ``dh`` in km and ground speed ``ff`` converted to km/h (``x 3.6``), and each
layer weighted by its overlap ``w`` with the altitude band (:mod:`flocklake_core.bands`):

.. code-block:: text

    VID = sum w * dens * dh                    birds km-2
    VIR = sum w * eta * dh                     cm2 km-2
    MTR = sum w * dens * ff' * 3.6 * dh        birds km-1 h-1
    RTR = sum w * eta * ff' * 3.6 * dh         cm2 km-1 h-1
    height_mean = sum w * dens * h_mid / sum w * dens      m (layer midpoints)
    MT  = sum MTR_i * dt_i                     birds km-1 (over a night)

``ff'`` is ``ff`` for traffic through a line perpendicular to the birds' own movement, or
``ff * cos(dd - alpha)`` for net traffic in direction ``alpha`` (as in bioRad's
``integrate_profile``): birds moving the opposite way subtract.

Rules for gaps and missing values
---------------------------------
1. A layer is **missing** when it is flagged as a gap, or when its ``dens`` or ``eta`` is not
   finite. Missing layers contribute nothing. ``coverage`` reports the share of the band's
   thickness (inside the grid) with valid layers, so 1.0 means nothing was missing. When every
   layer in the band is missing, all integrals are NaN.
2. A layer with zero density has zero traffic, even when ``ff`` or ``dd`` is missing (vol2bird
   leaves the speed of empty layers undefined).
3. A layer with birds but no ``ff`` (or no ``dd`` when ``alpha`` is given) is missing for MTR and
   RTR only; ``traffic_coverage`` reports the share of the band usable for traffic.
4. ``height_mean`` is NaN when the band holds no birds.
5. In MT, each profile's MTR applies until the next profile, but for at most ``max_interval``.
   The last profile applies for the median interval of the others (capped the same way). Profiles
   with a NaN MTR contribute nothing and their time is reported as ``missing_hours``.

References
----------
Dokter, A. M., et al. (2019). bioRad: biological analysis and visualization of weather radar
data. Ecography 42(5), 852-860. doi:10.1111/ecog.04028
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final

import numpy as np

from flocklake_core.bands import band_weights
from flocklake_core.domain import DEFAULT_GRID, ProfileGrid

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from numpy.typing import ArrayLike, NDArray

    from flocklake_core.bands import AltitudeBand

__all__ = [
    "DEFAULT_MAX_INTERVAL",
    "MigrationTraffic",
    "ProfileIntegrals",
    "height_quantiles",
    "integrate_profile",
    "migration_traffic",
]

_MPS_TO_KMH: Final = 3.6
DEFAULT_MAX_INTERVAL: Final = timedelta(hours=1)
"""Longest time one profile's MTR is assumed to last in MT."""


@dataclass(frozen=True, slots=True)
class ProfileIntegrals:
    """Vertically integrated quantities; arrays have the profiles' leading shape.

    Attributes
    ----------
    vid
        Vertically integrated density, birds km-2.
    vir
        Vertically integrated reflectivity, cm2 km-2.
    mtr
        Migration traffic rate, birds km-1 h-1.
    rtr
        Reflectivity traffic rate, cm2 km-1 h-1.
    height_mean_m
        Density-weighted mean height of the layer midpoints, m.
    coverage
        Share of the band thickness with valid density, in [0, 1].
    traffic_coverage
        Share of the band thickness usable for traffic, in [0, 1].

    """

    vid: NDArray[np.float64]
    vir: NDArray[np.float64]
    mtr: NDArray[np.float64]
    rtr: NDArray[np.float64]
    height_mean_m: NDArray[np.float64]
    coverage: NDArray[np.float64]
    traffic_coverage: NDArray[np.float64]


def _layers(values: ArrayLike | None, shape: tuple[int, ...], name: str) -> NDArray[np.float64]:
    if values is None:
        return np.full(shape, np.nan)
    array = np.asarray(values, dtype=np.float64)
    if array.shape[-1:] != shape[-1:]:
        msg = f"{name} must have {shape[-1]} layers on its last axis, got shape {array.shape}"
        raise ValueError(msg)
    return np.broadcast_to(array, shape)


def _weights(grid: ProfileGrid, band: AltitudeBand | None) -> NDArray[np.float64]:
    return np.ones(grid.layers) if band is None else band_weights(band, grid)


def integrate_profile(  # noqa: PLR0913 - one argument per profile quantity
    dens: ArrayLike,
    eta: ArrayLike,
    ff: ArrayLike | None = None,
    dd: ArrayLike | None = None,
    *,
    grid: ProfileGrid = DEFAULT_GRID,
    band: AltitudeBand | None = None,
    alpha_deg: float | None = None,
    gap: ArrayLike | None = None,
) -> ProfileIntegrals:
    """Integrate one or many vertical profiles over altitude.

    Parameters
    ----------
    dens, eta
        Density (birds km-3) and reflectivity (cm2 km-3), shape ``(..., layers)``.
    ff, dd
        Ground speed (m/s) and direction of movement (degrees, towards), same shape.
    grid
        Altitude layers of the profiles.
    band
        Altitude band to integrate over; the whole grid when ``None``.
    alpha_deg
        Direction for net traffic; traffic perpendicular to the movement when ``None``.
    gap
        Boolean gap flags per layer; ``True`` marks a missing layer.

    Examples
    --------
    >>> result = integrate_profile([10.0] * 25, [110.0] * 25, [10.0] * 25, [180.0] * 25)
    >>> float(result.vid), float(result.mtr), float(result.height_mean_m)
    (50.0, 1800.0, 2500.0)

    """
    density = np.asarray(dens, dtype=np.float64)
    shape = density.shape
    if shape[-1:] != (grid.layers,):
        msg = f"dens must have {grid.layers} layers on its last axis, got shape {shape}"
        raise ValueError(msg)
    reflectivity = _layers(eta, shape, "eta")
    speed = _layers(ff, shape, "ff")
    direction = _layers(dd, shape, "dd")
    gaps = (
        np.zeros(shape, dtype=bool)
        if gap is None
        else np.broadcast_to(np.asarray(gap, bool), shape)
    )

    weight = _weights(grid, band)
    dh_km = grid.layer_thickness_m / 1000.0
    in_band = weight.sum()
    valid = ~gaps & np.isfinite(density) & np.isfinite(reflectivity)
    w_valid = np.where(valid, weight, 0.0)

    effective = speed if alpha_deg is None else speed * np.cos(np.radians(direction - alpha_deg))
    empty = valid & (density == 0)
    traffic_ok = valid & (np.isfinite(effective) | empty)
    w_traffic = np.where(traffic_ok, weight, 0.0)
    effective = np.where(empty, 0.0, effective)

    with np.errstate(invalid="ignore"):
        rho = np.where(valid, density, 0.0)
        eta_v = np.where(valid, reflectivity, 0.0)
        speed_kmh = np.where(traffic_ok, effective, 0.0) * _MPS_TO_KMH
        vid = (w_valid * rho).sum(axis=-1) * dh_km
        vir = (w_valid * eta_v).sum(axis=-1) * dh_km
        mtr = (w_traffic * rho * speed_kmh).sum(axis=-1) * dh_km
        rtr = (w_traffic * eta_v * speed_kmh).sum(axis=-1) * dh_km
        weighted = (w_valid * rho).sum(axis=-1)
        height = np.where(
            weighted > 0, (w_valid * rho * grid.midpoints_m).sum(axis=-1) / weighted, np.nan
        )
    coverage = w_valid.sum(axis=-1) / in_band if in_band > 0 else np.zeros(shape[:-1])
    traffic_coverage = w_traffic.sum(axis=-1) / in_band if in_band > 0 else np.zeros(shape[:-1])
    nothing = coverage == 0
    no_traffic = traffic_coverage == 0
    return ProfileIntegrals(
        vid=np.where(nothing, np.nan, vid),
        vir=np.where(nothing, np.nan, vir),
        mtr=np.where(no_traffic, np.nan, mtr),
        rtr=np.where(no_traffic, np.nan, rtr),
        height_mean_m=np.asarray(height, dtype=np.float64),
        coverage=np.asarray(coverage, dtype=np.float64),
        traffic_coverage=np.asarray(traffic_coverage, dtype=np.float64),
    )


def height_quantiles(
    dens: ArrayLike,
    quantiles: Sequence[float] = (0.1, 0.5, 0.9),
    *,
    grid: ProfileGrid = DEFAULT_GRID,
    band: AltitudeBand | None = None,
) -> NDArray[np.float64]:
    """Heights below which the given shares of the birds fly, for one profile.

    Density is taken as uniform within each layer (clipped to the band), so the cumulative
    profile is piecewise linear and quantiles are interpolated within a layer. Missing layers
    count as empty.

    Examples
    --------
    >>> height_quantiles([1.0] * 25, [0.5]).tolist()
    [2500.0]

    """
    density = np.asarray(dens, dtype=np.float64)
    if density.shape != (grid.layers,):
        msg = f"dens must have shape ({grid.layers},), got {density.shape}"
        raise ValueError(msg)
    qs = np.asarray(quantiles, dtype=np.float64)
    if np.any((qs < 0) | (qs > 1)):
        msg = "quantiles must be in [0, 1]"
        raise ValueError(msg)
    weight = _weights(grid, band)
    low = grid.bottoms_m if band is None else np.clip(grid.bottoms_m, band.low_m, band.high_m)
    top = grid.bottoms_m + grid.layer_thickness_m
    high = top if band is None else np.clip(top, band.low_m, band.high_m)
    birds = np.where(np.isfinite(density), np.maximum(density, 0.0), 0.0) * weight
    total = float(birds.sum())
    if total == 0:
        return np.full(qs.shape, np.nan)
    cumulative = np.concatenate(([0.0], np.cumsum(birds))) / total
    out = np.empty(qs.shape)
    for i, q in enumerate(qs):
        k = int(np.searchsorted(cumulative[1:], q, side="left"))
        k = min(k, grid.layers - 1)
        share = birds[k] / total
        within = 0.0 if share == 0 else (q - cumulative[k]) / share
        out[i] = low[k] + min(max(within, 0.0), 1.0) * (high[k] - low[k])
    return out


@dataclass(frozen=True, slots=True)
class MigrationTraffic:
    """Migration traffic over a period.

    Attributes
    ----------
    mt
        Birds crossing a 1 km line during the period, birds km-1.
    covered_hours
        Time represented by profiles with a valid MTR.
    missing_hours
        Time represented by profiles whose MTR was NaN.

    """

    mt: float
    covered_hours: float
    missing_hours: float


def migration_traffic(
    times: Sequence[datetime],
    mtr: ArrayLike,
    *,
    max_interval: timedelta = DEFAULT_MAX_INTERVAL,
) -> MigrationTraffic:
    """Integrate a series of MTR values over time (rule 5 in the module notes).

    Examples
    --------
    >>> from datetime import UTC, datetime
    >>> t = [datetime(2026, 10, 1, h, tzinfo=UTC) for h in (20, 21, 22)]
    >>> migration_traffic(t, [100.0, 200.0, 300.0]).mt
    600.0

    """
    rates = np.asarray(mtr, dtype=np.float64)
    if rates.shape != (len(times),):
        msg = f"mtr must have one value per time, got {rates.shape} for {len(times)} times"
        raise ValueError(msg)
    if len(times) == 0:
        return MigrationTraffic(0.0, 0.0, 0.0)
    if any(b <= a for a, b in itertools.pairwise(times)):
        msg = "times must be strictly increasing"
        raise ValueError(msg)
    cap_h = max_interval.total_seconds() / 3600
    steps = np.array([(b - a).total_seconds() / 3600 for a, b in itertools.pairwise(times)])
    last = float(np.median(steps)) if steps.size else 0.0
    dt_h = np.minimum(np.append(steps, last), cap_h)
    ok = np.isfinite(rates)
    mt = float((rates[ok] * dt_h[ok]).sum())
    return MigrationTraffic(
        mt=mt if ok.any() else math.nan,
        covered_hours=float(dt_h[ok].sum()),
        missing_hours=float(dt_h[~ok].sum()),
    )
