import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from flocklake_core.circular import (
    angular_difference,
    circular_summary,
    direction_from,
    direction_towards,
    from_to_towards,
    movement_components,
    towards_to_from,
    wind_components,
)

angles = st.floats(-720.0, 720.0, allow_nan=False)
speeds = st.floats(0.1, 60.0)


def test_reproduces_the_aloft_record_in_the_science_note() -> None:
    u, v = 5.864, 10.163
    assert float(np.hypot(u, v)) == pytest.approx(11.733, abs=1e-3)
    assert float(direction_towards(u, v)) == pytest.approx(29.99, abs=0.01)


@pytest.mark.parametrize(
    ("towards", "u", "v"),
    [(0.0, 0.0, 1.0), (90.0, 1.0, 0.0), (180.0, 0.0, -1.0), (270.0, -1.0, 0.0)],
)
def test_movement_components_point_where_birds_go(towards: float, u: float, v: float) -> None:
    got = movement_components(1.0, towards)
    assert (float(got[0]), float(got[1])) == pytest.approx((u, v), abs=1e-12)


@pytest.mark.parametrize(
    ("wind_from", "u", "v"),
    [(0.0, 0.0, -1.0), (90.0, -1.0, 0.0), (180.0, 0.0, 1.0), (270.0, 1.0, 0.0)],
)
def test_wind_components_point_away_from_the_source(wind_from: float, u: float, v: float) -> None:
    got = wind_components(1.0, wind_from)
    assert (float(got[0]), float(got[1])) == pytest.approx((u, v), abs=1e-12)


@given(speed=speeds, direction=angles)
def test_component_round_trips(speed: float, direction: float) -> None:
    wrapped = direction % 360.0
    u, v = movement_components(speed, direction)
    assert float(angular_difference(direction_towards(u, v), wrapped)) == pytest.approx(0, abs=1e-6)
    u, v = wind_components(speed, direction)
    assert float(angular_difference(direction_from(u, v), wrapped)) == pytest.approx(0, abs=1e-6)


@given(angles)
def test_from_and_towards_are_opposite_and_inverse(direction: float) -> None:
    towards = from_to_towards(direction)
    assert abs(float(angular_difference(towards, direction))) == pytest.approx(180.0)
    assert float(angular_difference(towards_to_from(towards), direction)) == pytest.approx(
        0, abs=1e-9
    )


@given(angles)
def test_directions_are_wrapped_into_0_360(direction: float) -> None:
    for value in (
        from_to_towards(direction),
        direction_towards(*movement_components(1, direction)),
    ):
        assert 0.0 <= float(value) < 360.0


def test_wrapping_never_returns_360() -> None:
    assert float(from_to_towards(-180.0 - 1e-14)) < 360.0


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (10.0, 350.0, 20.0),
        (350.0, 10.0, -20.0),
        (180.0, 0.0, 180.0),
        (0.0, 180.0, 180.0),
        (5.0, 5.0, 0.0),
    ],
)
def test_angular_difference(a: float, b: float, expected: float) -> None:
    assert float(angular_difference(a, b)) == pytest.approx(expected)


class TestSummary:
    def test_mean_across_the_wrap(self) -> None:
        summary = circular_summary([350.0, 10.0, 0.0])
        assert float(angular_difference(summary.mean_deg, 0.0)) == pytest.approx(0.0, abs=1e-9)
        assert summary.count == 3

    def test_identical_directions_have_no_spread(self) -> None:
        summary = circular_summary([200.0] * 5)
        assert summary.mean_deg == pytest.approx(200.0)
        assert summary.resultant_length == pytest.approx(1.0)
        assert summary.angular_deviation_deg == pytest.approx(0.0, abs=1e-5)

    def test_opposite_directions_cancel(self) -> None:
        summary = circular_summary([90.0, 270.0])
        assert math.isnan(summary.mean_deg)
        assert summary.resultant_length == pytest.approx(0.0, abs=1e-12)
        assert summary.angular_deviation_deg == pytest.approx(math.degrees(math.sqrt(2)))

    def test_weights_pull_the_mean(self) -> None:
        summary = circular_summary([0.0, 90.0], weights=[3.0, 1.0])
        assert summary.mean_deg == pytest.approx(math.degrees(math.atan2(1, 3)))

    def test_ignores_missing_and_zero_weight_entries(self) -> None:
        summary = circular_summary([10.0, math.nan, 50.0, 30.0], weights=[1.0, 1.0, 0.0, 1.0])
        assert summary.count == 2
        assert summary.mean_deg == pytest.approx(20.0)

    def test_empty_input(self) -> None:
        summary = circular_summary([])
        assert summary.count == 0
        assert math.isnan(summary.mean_deg)

    @pytest.mark.parametrize(
        ("weights", "message"), [([1.0], "must match"), ([1.0, -1.0], "negative")]
    )
    def test_rejects_bad_weights(self, weights: list[float], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            circular_summary([1.0, 2.0], weights=weights)

    @given(
        st.lists(st.floats(0, 360), min_size=1, max_size=50),
        st.floats(-360.0, 360.0),
    )
    def test_rotating_every_direction_rotates_the_mean(
        self, directions: list[float], shift: float
    ) -> None:
        before = circular_summary(directions)
        after = circular_summary(np.asarray(directions) + shift)
        assert after.resultant_length == pytest.approx(before.resultant_length, abs=1e-9)
        if before.resultant_length > 1e-6:
            moved = angular_difference(after.mean_deg, before.mean_deg + shift)
            assert float(moved) == pytest.approx(0.0, abs=1e-4)
        assert 0.0 <= before.resultant_length <= 1.0
