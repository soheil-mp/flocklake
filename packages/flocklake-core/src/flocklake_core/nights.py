"""Night calendar: when it is night at a radar, and which partition a moment belongs to.

FlockLake partitions data by **night date**, the local evening date at the radar (ADR 0008). A
partition is a fixed 24-hour UTC window starting at a cut-off hour on the night date: 12:00 UTC
for radars in Europe and Africa, 17:00 UTC for radars far west of Greenwich such as the US
network. Inside it, the night runs from sunset (or the end of civil dusk) on the night date to
sunrise (or the start of civil dawn) the next morning.

The night date is a *local* date. Sun events are computed for local mean solar time at the
radar (UTC plus longitude / 15 hours), so a US radar's sunset at 22:00 UTC still belongs to the
evening date, not to the next UTC day. All results are aware UTC datetimes.

Polar regions:

* **Polar day** (the sun stays up all night): the night is empty and flagged ``polar_day``.
* **Polar night** (the sun stays down all day): the night fills the whole partition and is
  flagged ``polar_night``.
* On the days in between, a missing sunset or sunrise is replaced by the partition boundary.

Sun positions come from astral (Apache-2.0), which follows the NOAA solar calculator and
includes standard atmospheric refraction.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Final

from astral import Observer
from astral.sun import dawn, dusk, elevation, sunrise, sunset

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "NightWindow",
    "Twilight",
    "night_date_of",
    "night_window",
    "partition_cutoff_hour",
    "partition_window",
]

_WEST_CUTOFF_LONGITUDE: Final = -30.0
"""Radars west of this longitude use the 17:00 UTC cut-off."""


class Twilight(enum.StrEnum):
    """Which sun position marks the start and end of the night."""

    SUN = "sun"
    """Sunset to sunrise (upper limb on the horizon, with refraction): the default."""

    CIVIL = "civil"
    """End of civil dusk to start of civil dawn (sun 6 degrees below the horizon)."""


def partition_cutoff_hour(longitude_deg: float) -> int:
    """UTC hour at which a radar's night partitions start.

    Examples
    --------
    >>> partition_cutoff_hour(4.79), partition_cutoff_hour(-71.14)
    (12, 17)

    """
    return 17 if longitude_deg < _WEST_CUTOFF_LONGITUDE else 12


def partition_window(night_date: date, cutoff_hour: int = 12) -> tuple[datetime, datetime]:
    """Return the 24-hour UTC window ``[start, end)`` of the partition for ``night_date``."""
    if not 0 <= cutoff_hour < 24:  # noqa: PLR2004
        msg = f"cutoff_hour must be in 0..23, got {cutoff_hour}"
        raise ValueError(msg)
    start = datetime.combine(night_date, time(cutoff_hour), tzinfo=UTC)
    return start, start + timedelta(days=1)


def night_date_of(moment: datetime, cutoff_hour: int = 12) -> date:
    """Night date of the partition that contains an aware ``moment``.

    Examples
    --------
    >>> night_date_of(datetime(2026, 10, 16, 3, 0, tzinfo=UTC))
    datetime.date(2026, 10, 15)

    """
    if moment.tzinfo is None:
        msg = "moment must be timezone-aware"
        raise ValueError(msg)
    shifted = moment.astimezone(UTC) - timedelta(hours=cutoff_hour)
    return shifted.date()


@dataclass(frozen=True, slots=True)
class NightWindow:
    """The night inside one partition.

    Attributes
    ----------
    night_date
        Local evening date at the radar.
    start, end
        Start and end of the night in UTC; equal for polar day.
    sunset, sunrise
        The sun events behind ``start`` and ``end``; ``None`` where the sun did not set or rise.
    polar_day, polar_night
        Whether the sun stayed above or below the twilight limit for the whole night.
    twilight
        Which sun position defines the night.

    """

    night_date: date
    start: datetime
    end: datetime
    sunset: datetime | None
    sunrise: datetime | None
    polar_day: bool
    polar_night: bool
    twilight: Twilight

    @property
    def length(self) -> timedelta:
        """Duration of the night (zero for polar day)."""
        return self.end - self.start

    def contains(self, moment: datetime) -> bool:
        """Whether an aware ``moment`` falls inside the night ``[start, end)``."""
        return self.start <= moment < self.end


def _evening_event(observer: Observer, day: date, tz: timezone, twilight: Twilight) -> datetime:
    if twilight is Twilight.SUN:
        return sunset(observer, day, tzinfo=tz)
    return dusk(observer, day, tzinfo=tz)


def _morning_event(observer: Observer, day: date, tz: timezone, twilight: Twilight) -> datetime:
    if twilight is Twilight.SUN:
        return sunrise(observer, day, tzinfo=tz)
    return dawn(observer, day, tzinfo=tz)


def _try(event: Callable[[], datetime]) -> datetime | None:
    """Return the event in UTC, or ``None`` when astral reports that the sun never crosses."""
    try:
        return event().astimezone(UTC)
    except ValueError:
        return None


def night_window(
    latitude_deg: float,
    longitude_deg: float,
    night_date: date,
    *,
    twilight: Twilight = Twilight.SUN,
    cutoff_hour: int | None = None,
) -> NightWindow:
    """Compute the night at a radar on a night date.

    Parameters
    ----------
    latitude_deg, longitude_deg
        WGS 84 position of the radar.
    night_date
        Local evening date.
    twilight
        Sunset-to-sunrise (default) or civil dusk to civil dawn.
    cutoff_hour
        Partition cut-off in UTC hours; derived from the longitude when ``None``.

    Examples
    --------
    >>> night = night_window(52.953, 4.791, date(2026, 10, 15))  # Den Helder
    >>> night.start.strftime("%H:%M"), night.end.strftime("%H:%M"), str(night.length)[:5]
    ('16:45', '06:08', '13:23')

    """
    observer = Observer(latitude=latitude_deg, longitude=longitude_deg)
    solar = timezone(timedelta(hours=longitude_deg / 15.0))
    cutoff = partition_cutoff_hour(longitude_deg) if cutoff_hour is None else cutoff_hour
    window_start, window_end = partition_window(night_date, cutoff)
    next_day = night_date + timedelta(days=1)
    evening = _try(lambda: _evening_event(observer, night_date, solar, twilight))
    morning = _try(lambda: _morning_event(observer, next_day, solar, twilight))

    if evening is None and morning is None:
        # No crossing at all: decide by the sun at local solar midnight.
        midnight = datetime.combine(next_day, time(0), tzinfo=solar)
        limit = 0.0 if twilight is Twilight.SUN else -6.0
        polar_day = elevation(observer, midnight) > limit
        return NightWindow(
            night_date=night_date,
            start=window_start,
            end=window_start if polar_day else window_end,
            sunset=None,
            sunrise=None,
            polar_day=polar_day,
            polar_night=not polar_day,
            twilight=twilight,
        )
    return NightWindow(
        night_date=night_date,
        start=max(evening or window_start, window_start),
        end=min(morning or window_end, window_end),
        sunset=evening,
        sunrise=morning,
        polar_day=False,
        polar_night=False,
        twilight=twilight,
    )
