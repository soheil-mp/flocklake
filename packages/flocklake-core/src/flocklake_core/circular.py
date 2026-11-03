"""Circular statistics and direction conventions.

Directions are degrees clockwise from north, in ``[0, 360)``. Two conventions meet in this
project, and mixing them up is a classic bug:

* **towards**: profile directions (``dd``) say where birds move to.
* **from**: meteorological wind directions say where the wind comes from.

Vector components are ``u`` (towards east) and ``v`` (towards north) in both cases:

.. code-block:: text

    movement:  u =  ff · sin(dd)   v =  ff · cos(dd)    dd = atan2(u, v)  mod 360
    wind:      u = -V · sin(wd)    v = -V · cos(wd)     wd = atan2(-u, -v) mod 360

Summary statistics follow Batschelet (1981) and Mardia & Jupp (2000): the mean direction is the
direction of the (optionally weighted) mean unit vector, its length ``R`` in ``[0, 1]`` measures
concentration, and the angular deviation is ``sqrt(2 · (1 - R))`` in degrees.

All functions accept Python numbers or NumPy arrays and broadcast like NumPy.

References
----------
Batschelet, E. (1981). Circular Statistics in Biology. Academic Press.

Mardia, K. V. & Jupp, P. E. (2000). Directional Statistics. Wiley.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import ArrayLike, NDArray

__all__ = [
    "CircularSummary",
    "angular_difference",
    "circular_summary",
    "direction_from",
    "direction_towards",
    "from_to_towards",
    "movement_components",
    "towards_to_from",
    "wind_components",
]


def _wrap(degrees: NDArray[np.float64]) -> NDArray[np.float64]:
    wrapped = np.mod(degrees, 360.0)
    # mod can return 360.0 for tiny negative inputs; fold it back to 0.
    return np.where(wrapped >= 360.0, 0.0, wrapped)  # noqa: PLR2004


def _float(values: ArrayLike) -> NDArray[np.float64]:
    return np.asarray(values, dtype=np.float64)


def direction_towards(u: ArrayLike, v: ArrayLike) -> NDArray[np.float64]:
    """Direction a vector points to, degrees clockwise from north.

    Examples
    --------
    >>> round(float(direction_towards(5.864, 10.163)), 1)  # north-north-east
    30.0

    """
    return _wrap(np.degrees(np.arctan2(_float(u), _float(v))))


def direction_from(u: ArrayLike, v: ArrayLike) -> NDArray[np.float64]:
    """Meteorological direction a flow comes from, degrees clockwise from north.

    Examples
    --------
    >>> float(direction_from(0.0, -5.0))  # flowing south, so coming from the north
    0.0

    """
    return _wrap(np.degrees(np.arctan2(-_float(u), -_float(v))))


def movement_components(
    speed: ArrayLike, towards_deg: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """``(u, v)`` of a movement with speed ``ff`` towards ``dd``."""
    rad = np.radians(_float(towards_deg))
    s = _float(speed)
    return s * np.sin(rad), s * np.cos(rad)


def wind_components(
    speed: ArrayLike, from_deg: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """``(u, v)`` of a wind with speed ``V`` coming from ``wd``.

    Examples
    --------
    >>> u, v = wind_components(10.0, 270.0)  # a westerly blows towards the east
    >>> round(float(u), 6), round(float(v), 6)
    (10.0, 0.0)

    """
    rad = np.radians(_float(from_deg))
    s = _float(speed)
    return -s * np.sin(rad), -s * np.cos(rad)


def from_to_towards(from_deg: ArrayLike) -> NDArray[np.float64]:
    """Turn a "from" direction into the "towards" direction of the same flow."""
    return _wrap(_float(from_deg) + 180.0)


def towards_to_from(towards_deg: ArrayLike) -> NDArray[np.float64]:
    """Turn a "towards" direction into the "from" direction of the same flow."""
    return _wrap(_float(towards_deg) + 180.0)


def angular_difference(a_deg: ArrayLike, b_deg: ArrayLike) -> NDArray[np.float64]:
    """Signed smallest rotation from ``b`` to ``a``, in ``(-180, 180]`` degrees.

    Examples
    --------
    >>> float(angular_difference(10.0, 350.0))
    20.0

    """
    difference = np.mod(_float(a_deg) - _float(b_deg) + 180.0, 360.0) - 180.0
    return np.where(difference == -180.0, 180.0, difference)  # noqa: PLR2004


@dataclass(frozen=True, slots=True)
class CircularSummary:
    """Summary of a set of directions.

    Attributes
    ----------
    mean_deg
        Mean direction; ``nan`` when the directions cancel out or there are none.
    resultant_length
        Length ``R`` of the mean unit vector, in ``[0, 1]``; 1 when all directions agree.
    angular_deviation_deg
        ``sqrt(2 · (1 - R))`` in degrees, from 0 (all equal) to about 81° (uniform).
    count
        Number of directions used (finite, with a positive weight).

    """

    mean_deg: float
    resultant_length: float
    angular_deviation_deg: float
    count: int


def circular_summary(
    directions_deg: ArrayLike, weights: ArrayLike | None = None
) -> CircularSummary:
    """Mean direction, resultant length and angular deviation of directions.

    Directions or weights that are not finite, and zero weights, are ignored. Weights, for
    example bird densities, must not be negative.

    Examples
    --------
    >>> s = circular_summary([350.0, 10.0])
    >>> round(s.mean_deg, 6) % 360, round(s.resultant_length, 4)
    (0.0, 0.9848)

    """
    directions = _float(directions_deg).ravel()
    w = np.ones_like(directions) if weights is None else _float(weights).ravel()
    if w.shape != directions.shape:
        msg = f"weights must match directions, got {w.shape} and {directions.shape}"
        raise ValueError(msg)
    if np.any(w < 0):
        msg = "weights must not be negative"
        raise ValueError(msg)
    use = np.isfinite(directions) & np.isfinite(w) & (w > 0)
    directions, w = directions[use], w[use]
    if directions.size == 0:
        return CircularSummary(math.nan, math.nan, math.nan, 0)
    rad = np.radians(directions)
    total = float(w.sum())
    east, north = float((w * np.sin(rad)).sum()) / total, float((w * np.cos(rad)).sum()) / total
    length = min(1.0, math.hypot(east, north))
    mean = float(direction_towards(east, north)) if length > 1e-12 else math.nan  # noqa: PLR2004
    deviation = math.degrees(math.sqrt(2.0 * (1.0 - length)))
    return CircularSummary(mean, length, deviation, int(directions.size))
