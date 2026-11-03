"""Altitude bands over profile layers.

Products for an altitude band, such as traffic through the 25-300 m band swept by offshore
turbine rotors, count each profile layer with the fraction of it that lies inside the band. For
25-300 m on the 200 m grid, the 0-200 m layer counts 175/200 and the 200-400 m layer 100/200.

The lowest layers are the least reliable (ground clutter, beam blockage, beam height growing
with range), so band products built from them should carry a quality flag.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from flocklake_core.domain import DEFAULT_GRID, ProfileGrid

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = ["ROTOR_BAND", "AltitudeBand", "band_weights"]


@dataclass(frozen=True, slots=True)
class AltitudeBand:
    """A half-open altitude band ``[low_m, high_m)`` in metres.

    Examples
    --------
    >>> AltitudeBand(25.0, 300.0).thickness_m
    275.0

    """

    low_m: float
    high_m: float

    def __post_init__(self) -> None:
        """Reject empty, inverted or non-finite bands."""
        if not (math.isfinite(self.low_m) and math.isfinite(self.high_m)):
            msg = f"band limits must be finite, got [{self.low_m}, {self.high_m})"
            raise ValueError(msg)
        if self.low_m >= self.high_m:
            msg = f"band must satisfy low < high, got [{self.low_m}, {self.high_m})"
            raise ValueError(msg)

    @property
    def thickness_m(self) -> float:
        """Height of the band."""
        return self.high_m - self.low_m


ROTOR_BAND: Final = AltitudeBand(25.0, 300.0)
"""Altitude range swept by the rotors of current offshore wind turbines."""


def band_weights(band: AltitudeBand, grid: ProfileGrid = DEFAULT_GRID) -> NDArray[np.float64]:
    """Fraction of each layer of ``grid`` that lies inside ``band``, each in ``[0, 1]``.

    Parts of the band outside the grid are ignored.

    Examples
    --------
    >>> band_weights(AltitudeBand(25.0, 300.0))[:3].tolist()
    [0.875, 0.5, 0.0]

    """
    bottoms = grid.bottoms_m
    tops = bottoms + grid.layer_thickness_m
    overlap = np.minimum(tops, band.high_m) - np.maximum(bottoms, band.low_m)
    return np.clip(overlap / grid.layer_thickness_m, 0.0, 1.0)
