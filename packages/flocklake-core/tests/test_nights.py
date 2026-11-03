from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from flocklake_core.nights import (
    Twilight,
    night_date_of,
    night_window,
    partition_cutoff_hour,
    partition_window,
)

DEN_HELDER = (52.953, 4.791)
BOSTON = (41.956, -71.137)
HASVIK = (70.6, 22.4)
UTAJARVI = (64.77, 26.32)


def test_den_helder_in_october() -> None:
    night = night_window(*DEN_HELDER, date(2026, 10, 15))
    assert night.start == night.sunset
    assert night.end == night.sunrise
    assert night.start.date() == date(2026, 10, 15)
    assert night.end.date() == date(2026, 10, 16)
    assert timedelta(hours=13) < night.length < timedelta(hours=14)
    assert not night.polar_day
    assert not night.polar_night
    assert night.contains(datetime(2026, 10, 16, 0, 0, tzinfo=UTC))
    assert not night.contains(datetime(2026, 10, 15, 12, 0, tzinfo=UTC))


def test_us_radar_keeps_its_local_evening_date() -> None:
    night = night_window(*BOSTON, date(2026, 10, 15))
    # Sunset is about 22:00 UTC on the 15th, sunrise about 11:00 UTC on the 16th.
    assert night.start.date() == date(2026, 10, 15)
    assert 21 <= night.start.hour <= 22
    assert night.end.date() == date(2026, 10, 16)
    start, end = partition_window(date(2026, 10, 15), partition_cutoff_hour(BOSTON[1]))
    assert start <= night.start < night.end <= end


def test_civil_twilight_shortens_the_night() -> None:
    sun = night_window(*DEN_HELDER, date(2026, 10, 15))
    civil = night_window(*DEN_HELDER, date(2026, 10, 15), twilight=Twilight.CIVIL)
    assert civil.start > sun.start
    assert civil.end < sun.end
    assert timedelta(minutes=50) < sun.length - civil.length < timedelta(minutes=90)


def test_polar_day_is_an_empty_flagged_night() -> None:
    night = night_window(*HASVIK, date(2026, 6, 21))
    assert night.polar_day
    assert not night.polar_night
    assert night.length == timedelta(0)
    assert night.sunset is None
    assert night.sunrise is None


def test_polar_night_fills_the_partition() -> None:
    night = night_window(*HASVIK, date(2026, 12, 21))
    assert night.polar_night
    assert (night.start, night.end) == partition_window(date(2026, 12, 21))
    assert night.length == timedelta(days=1)


def test_civil_twilight_can_be_polar_day_while_the_sun_sets() -> None:
    sun = night_window(*UTAJARVI, date(2026, 6, 21))
    civil = night_window(*UTAJARVI, date(2026, 6, 21), twilight=Twilight.CIVIL)
    assert not sun.polar_day
    assert sun.length < timedelta(hours=3)
    assert civil.polar_day


def test_night_is_always_inside_its_partition() -> None:
    for day in (date(2026, 3, 20), date(2026, 6, 21), date(2026, 9, 22), date(2026, 12, 21)):
        for lat, lon in (DEN_HELDER, BOSTON, HASVIK, UTAJARVI):
            night = night_window(lat, lon, day)
            start, end = partition_window(day, partition_cutoff_hour(lon))
            assert start <= night.start <= night.end <= end


@given(st.dates(date(2020, 1, 1), date(2035, 12, 31)), st.integers(0, 23))
def test_moments_map_to_the_partition_that_contains_them(day: date, cutoff: int) -> None:
    start, end = partition_window(day, cutoff)
    assert night_date_of(start, cutoff) == day
    assert night_date_of(end - timedelta(microseconds=1), cutoff) == day
    assert night_date_of(end, cutoff) == day + timedelta(days=1)


def test_partition_helpers_validate_input() -> None:
    with pytest.raises(ValueError, match="cutoff_hour"):
        partition_window(date(2026, 1, 1), 24)
    with pytest.raises(ValueError, match="timezone-aware"):
        night_date_of(datetime(2026, 1, 1))  # noqa: DTZ001 - testing the rejection
