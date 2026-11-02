"""Convert radar reflectivity into the reflectivity of animals and bird densities.

Weather radars report the reflectivity factor in dBZ, a quantity defined for raindrops. For
birds and other animals the useful quantity is the reflectivity eta, the radar cross-section
per unit volume, from which a bird density follows by dividing by the cross-section of one bird:

.. code-block:: text

    Z   = 10 ** (dBZ / 10)                          [mm^6 m^-3]
    eta = 1e3 * pi**5 * |K|**2 / lambda**4 * Z      [cm^2 km^-3], lambda in cm
    rho = eta / sigma                               [birds km^-3]

All functions accept a Python number (and return a ``float``) or a NumPy array (and return a
``float64`` array of the same shape). NaN propagates; ``-inf`` dBZ means no echo and maps to 0.

References
----------
Dokter, A. M., et al. (2011). Bird migration flight altitudes studied by a network of
operational weather radars. Journal of the Royal Society Interface 8(54), 30-43.
doi:10.1098/rsif.2010.0116

Dokter, A. M., et al. (2019). bioRad: biological analysis and visualization of weather radar
data. Ecography 42(5), 852-860. doi:10.1111/ecog.04028
"""

from __future__ import annotations

import math
from typing import Final, overload

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "DEFAULT_RCS_CM2",
    "WATER_K_SQUARED",
    "dbz_from_eta",
    "dbz_to_z",
    "density_from_eta",
    "eta_from_dbz",
    "eta_from_density",
    "z_to_dbz",
]

type FloatArray = NDArray[np.float64]

WATER_K_SQUARED: Final = 0.93
"""Dielectric factor |K|² of liquid water used by weather radars to define dBZ."""

DEFAULT_RCS_CM2: Final = 11.0
"""Conventional radar cross-section of one bird, in cm² (Dokter et al. 2011)."""

_ETA_PER_Z_AT_ONE_CM: Final = 1e3 * math.pi**5
"""eta / (|K|² Z) for a 1 cm wavelength: converts mm⁶ m⁻³ into cm² km⁻³."""


def _check_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        msg = f"{name} must be a finite number greater than 0, got {value!r}"
        raise ValueError(msg)


def _check_k_squared(k_squared: float) -> None:
    if not math.isfinite(k_squared) or not 0 < k_squared <= 1:
        msg = f"k_squared must be in (0, 1], got {k_squared!r}"
        raise ValueError(msg)


def _eta_per_z(wavelength_cm: float, k_squared: float) -> float:
    _check_positive("wavelength_cm", wavelength_cm)
    _check_k_squared(k_squared)
    return _ETA_PER_Z_AT_ONE_CM * k_squared / wavelength_cm**4


def _like(result: FloatArray, template: float | FloatArray) -> float | FloatArray:
    """Return a float for scalar input and an array for array input."""
    if isinstance(template, np.ndarray):
        return result
    return float(result)


@overload
def dbz_to_z(dbz: float) -> float: ...
@overload
def dbz_to_z(dbz: FloatArray) -> FloatArray: ...
def dbz_to_z(dbz: float | FloatArray) -> float | FloatArray:
    """Convert a reflectivity factor from dBZ to linear units.

    Parameters
    ----------
    dbz
        Reflectivity factor in dBZ.

    Returns
    -------
    float or numpy.ndarray
        Reflectivity factor Z in mm⁶ m⁻³.

    Examples
    --------
    >>> dbz_to_z(20.0)
    100.0
    """
    return _like(np.power(10.0, np.asarray(dbz, dtype=np.float64) / 10.0), dbz)


@overload
def z_to_dbz(z: float) -> float: ...
@overload
def z_to_dbz(z: FloatArray) -> FloatArray: ...
def z_to_dbz(z: float | FloatArray) -> float | FloatArray:
    """Convert a linear reflectivity factor to dBZ.

    Parameters
    ----------
    z
        Reflectivity factor in mm⁶ m⁻³. Zero gives ``-inf``; negative values give NaN.

    Returns
    -------
    float or numpy.ndarray
        Reflectivity factor in dBZ.
    """
    values = np.asarray(z, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = 10.0 * np.log10(values)
    return _like(result, z)


@overload
def eta_from_dbz(dbz: float, wavelength_cm: float, k_squared: float = WATER_K_SQUARED) -> float: ...
@overload
def eta_from_dbz(
    dbz: FloatArray, wavelength_cm: float, k_squared: float = WATER_K_SQUARED
) -> FloatArray: ...
def eta_from_dbz(
    dbz: float | FloatArray, wavelength_cm: float, k_squared: float = WATER_K_SQUARED
) -> float | FloatArray:
    """Convert a reflectivity factor in dBZ into the reflectivity eta.

    Parameters
    ----------
    dbz
        Reflectivity factor in dBZ.
    wavelength_cm
        Radar wavelength in cm (about 5.3 for C-band, 10.7 for S-band).
    k_squared
        Dielectric factor |K|² the radar used to compute dBZ. Defaults to liquid water, 0.93.

    Returns
    -------
    float or numpy.ndarray
        Reflectivity eta in cm² km⁻³.

    Raises
    ------
    ValueError
        If the wavelength is not a positive finite number or ``k_squared`` is not in (0, 1].

    Examples
    --------
    At C-band, 0 dBZ corresponds to about 361 cm² km⁻³:

    >>> round(eta_from_dbz(0.0, wavelength_cm=5.3), 1)
    360.7
    """
    factor = _eta_per_z(wavelength_cm, k_squared)
    z = np.power(10.0, np.asarray(dbz, dtype=np.float64) / 10.0)
    return _like(factor * z, dbz)


@overload
def dbz_from_eta(eta: float, wavelength_cm: float, k_squared: float = WATER_K_SQUARED) -> float: ...
@overload
def dbz_from_eta(
    eta: FloatArray, wavelength_cm: float, k_squared: float = WATER_K_SQUARED
) -> FloatArray: ...
def dbz_from_eta(
    eta: float | FloatArray, wavelength_cm: float, k_squared: float = WATER_K_SQUARED
) -> float | FloatArray:
    """Convert a reflectivity eta into the equivalent reflectivity factor in dBZ.

    This is the inverse of :func:`eta_from_dbz`.

    Parameters
    ----------
    eta
        Reflectivity in cm² km⁻³. Zero gives ``-inf``; negative values give NaN.
    wavelength_cm
        Radar wavelength in cm.
    k_squared
        Dielectric factor |K|² the radar uses to compute dBZ.

    Returns
    -------
    float or numpy.ndarray
        Reflectivity factor in dBZ.

    Raises
    ------
    ValueError
        If the wavelength is not a positive finite number or ``k_squared`` is not in (0, 1].
    """
    factor = _eta_per_z(wavelength_cm, k_squared)
    values = np.asarray(eta, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = 10.0 * np.log10(values / factor)
    return _like(result, eta)


@overload
def density_from_eta(eta: float, rcs_cm2: float = DEFAULT_RCS_CM2) -> float: ...
@overload
def density_from_eta(eta: FloatArray, rcs_cm2: float = DEFAULT_RCS_CM2) -> FloatArray: ...
def density_from_eta(
    eta: float | FloatArray, rcs_cm2: float = DEFAULT_RCS_CM2
) -> float | FloatArray:
    """Convert a reflectivity eta into a bird density.

    Parameters
    ----------
    eta
        Reflectivity in cm² km⁻³.
    rcs_cm2
        Radar cross-section of one bird in cm². Store it with every result: densities scale
        directly with it.

    Returns
    -------
    float or numpy.ndarray
        Bird density in birds km⁻³.

    Raises
    ------
    ValueError
        If the radar cross-section is not a positive finite number.

    Examples
    --------
    >>> density_from_eta(110.0)
    10.0
    """
    _check_positive("rcs_cm2", rcs_cm2)
    return _like(np.asarray(eta, dtype=np.float64) / rcs_cm2, eta)


@overload
def eta_from_density(density: float, rcs_cm2: float = DEFAULT_RCS_CM2) -> float: ...
@overload
def eta_from_density(density: FloatArray, rcs_cm2: float = DEFAULT_RCS_CM2) -> FloatArray: ...
def eta_from_density(
    density: float | FloatArray, rcs_cm2: float = DEFAULT_RCS_CM2
) -> float | FloatArray:
    """Convert a bird density into the reflectivity it produces.

    This is the inverse of :func:`density_from_eta`, used for example to build synthetic radar
    volumes from a known profile.

    Parameters
    ----------
    density
        Bird density in birds km⁻³.
    rcs_cm2
        Radar cross-section of one bird in cm².

    Returns
    -------
    float or numpy.ndarray
        Reflectivity in cm² km⁻³.

    Raises
    ------
    ValueError
        If the radar cross-section is not a positive finite number.
    """
    _check_positive("rcs_cm2", rcs_cm2)
    return _like(np.asarray(density, dtype=np.float64) * rcs_cm2, density)
