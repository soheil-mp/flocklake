"""Typed domain model: radar sites, radar bands, profile grids and quantities with units.

Everything here is a small immutable value type with validation, so wrong identifiers, swapped
coordinates or a wavelength in metres instead of centimetres fail at construction.

Identifiers follow the networks that publish the data:

* **ODIM node** (OPERA): two-letter country code plus three characters, for example ``nldhl``
  (Den Helder). Aloft and OPERA files are named by it.
* **WIGOS station identifier** (WMO): ``series-issuer-issue number-local id``, for example
  ``0-20000-0-06234``.
* **ICAO-style station id** (NEXRAD): four upper-case letters, for example ``KBOX``.
"""

from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = [
    "DEFAULT_GRID",
    "QUANTITIES",
    "Band",
    "ProfileGrid",
    "Quantity",
    "RadarSite",
]

_ODIM = re.compile(r"^[a-z]{2}[a-z0-9]{3}$")
_WIGOS = re.compile(r"^[0-9]-[0-9]{1,5}-[0-9]{1,5}-[A-Za-z0-9]{1,16}$")
_ICAO = re.compile(r"^[A-Z]{4}$")


class Band(enum.StrEnum):
    """Radar frequency band (IEEE letter designations) of a weather radar.

    The wavelength limits follow from the band's frequency range, ``lambda = c / f``.
    """

    S = "S"
    C = "C"
    X = "X"

    @property
    def wavelength_range_cm(self) -> tuple[float, float]:
        """Half-open wavelength range ``[shortest, longest)`` of the band in centimetres."""
        return _BAND_WAVELENGTHS_CM[self]

    @classmethod
    def from_wavelength(cls, wavelength_cm: float) -> Band:
        """Band of a radar with the given wavelength.

        Examples
        --------
        >>> Band.from_wavelength(5.3)
        <Band.C: 'C'>
        >>> Band.from_wavelength(10.7)
        <Band.S: 'S'>

        """
        for band, (shortest, longest) in _BAND_WAVELENGTHS_CM.items():
            if shortest <= wavelength_cm < longest:
                return band
        msg = f"wavelength {wavelength_cm} cm is outside the S, C and X bands (2.5-15 cm)"
        raise ValueError(msg)


_BAND_WAVELENGTHS_CM: Final = {
    Band.X: (2.5, 3.75),  # 8-12 GHz
    Band.C: (3.75, 7.5),  # 4-8 GHz
    Band.S: (7.5, 15.0),  # 2-4 GHz
}


@dataclass(frozen=True, slots=True, kw_only=True)
class RadarSite:
    """One weather radar.

    Attributes
    ----------
    odim_code
        ODIM node, for example ``nldhl``.
    name
        Human-readable name of the site.
    latitude_deg, longitude_deg
        WGS 84 position of the antenna.
    antenna_height_m
        Height of the antenna above mean sea level.
    wavelength_cm
        Radar wavelength; also determines :attr:`band`.
    wigos_id
        WIGOS station identifier, if the radar has one.
    icao
        Four-letter station id (NEXRAD), if the radar has one.

    Examples
    --------
    >>> site = RadarSite(
    ...     odim_code="nldhl",
    ...     name="Den Helder",
    ...     latitude_deg=52.953,
    ...     longitude_deg=4.791,
    ...     antenna_height_m=51.0,
    ...     wavelength_cm=5.3,
    ... )
    >>> site.band
    <Band.C: 'C'>

    """

    odim_code: str
    name: str
    latitude_deg: float
    longitude_deg: float
    antenna_height_m: float
    wavelength_cm: float
    wigos_id: str | None = None
    icao: str | None = None
    band: Band = field(init=False)

    def __post_init__(self) -> None:
        """Validate the identifiers, the position and the wavelength."""
        if not _ODIM.match(self.odim_code):
            msg = f"odim_code must be two letters and three characters, got {self.odim_code!r}"
            raise ValueError(msg)
        if self.wigos_id is not None and not _WIGOS.match(self.wigos_id):
            msg = f"wigos_id is not a WIGOS station identifier: {self.wigos_id!r}"
            raise ValueError(msg)
        if self.icao is not None and not _ICAO.match(self.icao):
            msg = f"icao must be four upper-case letters, got {self.icao!r}"
            raise ValueError(msg)
        if not self.name.strip():
            msg = "name must not be empty"
            raise ValueError(msg)
        if not -90 <= self.latitude_deg <= 90 or not -180 <= self.longitude_deg <= 180:  # noqa: PLR2004
            msg = f"position ({self.latitude_deg}, {self.longitude_deg}) is not a WGS 84 position"
            raise ValueError(msg)
        height = self.antenna_height_m
        if not math.isfinite(height) or not -500 < height < 9_000:  # noqa: PLR2004
            msg = f"antenna_height_m must be a plausible height in metres, got {height}"
            raise ValueError(msg)
        object.__setattr__(self, "band", Band.from_wavelength(self.wavelength_cm))


@dataclass(frozen=True, slots=True)
class ProfileGrid:
    """Altitude layers of a vertical profile.

    Attributes
    ----------
    layer_thickness_m
        Thickness of every layer.
    layers
        Number of layers.
    bottom_m
        Bottom of the lowest layer.

    Examples
    --------
    >>> DEFAULT_GRID.top_m
    5000.0
    >>> DEFAULT_GRID.midpoints_m[:2].tolist()
    [100.0, 300.0]

    """

    layer_thickness_m: float = 200.0
    layers: int = 25
    bottom_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate the grid."""
        if not self.layer_thickness_m > 0 or self.layers < 1:
            msg = "a grid needs a positive layer thickness and at least one layer"
            raise ValueError(msg)

    @property
    def bottoms_m(self) -> NDArray[np.float64]:
        """Bottom of each layer."""
        return self.bottom_m + self.layer_thickness_m * np.arange(self.layers, dtype=np.float64)

    @property
    def midpoints_m(self) -> NDArray[np.float64]:
        """Midpoint of each layer, used for density-weighted heights."""
        return self.bottoms_m + self.layer_thickness_m / 2

    @property
    def top_m(self) -> float:
        """Top of the highest layer."""
        return self.bottom_m + self.layer_thickness_m * self.layers


DEFAULT_GRID: Final = ProfileGrid()
"""The vol2bird grid: 25 layers of 200 m from 0 to 5 km (heights 0, 200, ..., 4800 m)."""


@dataclass(frozen=True, slots=True)
class Quantity:
    """A named quantity with its unit, as stored in tables and files."""

    name: str
    unit: str
    description: str


QUANTITIES: Final = {
    q.name: q
    for q in (
        Quantity("height", "m", "bottom of the altitude layer"),
        Quantity("dbz", "dBZ", "reflectivity factor"),
        Quantity("eta", "cm2 km-3", "animal reflectivity (cross-section per volume)"),
        Quantity("dens", "km-3", "bird density"),
        Quantity("rcs", "cm2", "radar cross-section of one bird used for dens"),
        Quantity("u", "m s-1", "ground speed component towards east"),
        Quantity("v", "m s-1", "ground speed component towards north"),
        Quantity("w", "m s-1", "vertical speed"),
        Quantity("ff", "m s-1", "horizontal ground speed"),
        Quantity("dd", "degree", "direction of movement, clockwise from north, towards"),
        Quantity("sd_vvp", "m s-1", "RMS of the radial-velocity fit residuals"),
        Quantity("vid", "km-2", "vertically integrated density"),
        Quantity("vir", "cm2 km-2", "vertically integrated reflectivity"),
        Quantity("mtr", "km-1 h-1", "migration traffic rate"),
        Quantity("rtr", "cm2 km-1 h-1", "reflectivity traffic rate"),
        Quantity("mt", "km-1", "migration traffic, MTR integrated over time"),
        Quantity("height_mean", "m", "density-weighted mean flight height"),
    )
}
"""Every quantity FlockLake stores, keyed by its column name, with units in UCUM-like form."""
