import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from flocklake_core.bands import ROTOR_BAND, AltitudeBand, band_weights
from flocklake_core.domain import DEFAULT_GRID, ProfileGrid

heights = st.floats(-1_000.0, 6_000.0, allow_nan=False)


def test_rotor_band_matches_the_worked_example() -> None:
    weights = band_weights(ROTOR_BAND)
    assert weights[:2].tolist() == [175 / 200, 100 / 200]
    assert np.all(weights[2:] == 0.0)


def test_full_range_counts_every_layer_once() -> None:
    assert np.all(band_weights(AltitudeBand(0.0, 5_000.0)) == 1.0)
    assert np.all(band_weights(AltitudeBand(-500.0, 9_000.0)) == 1.0)


def test_band_outside_the_grid_has_no_weight() -> None:
    assert np.all(band_weights(AltitudeBand(5_000.0, 6_000.0)) == 0.0)


def test_other_grids() -> None:
    grid = ProfileGrid(layer_thickness_m=100.0, layers=4, bottom_m=50.0)
    assert band_weights(AltitudeBand(100.0, 260.0), grid).tolist() == [0.5, 1.0, 0.1, 0.0]


@pytest.mark.parametrize(("low", "high"), [(300.0, 25.0), (10.0, 10.0), (0.0, float("inf"))])
def test_rejects_invalid_bands(low: float, high: float) -> None:
    with pytest.raises(ValueError, match="band"):
        AltitudeBand(low, high)


@given(heights, heights)
def test_weights_are_fractions_and_add_up_to_the_overlap(a: float, b: float) -> None:
    low, high = min(a, b), max(a, b)
    if low == high:
        return
    weights = band_weights(AltitudeBand(low, high))
    assert np.all((weights >= 0.0) & (weights <= 1.0))
    covered = max(0.0, min(high, DEFAULT_GRID.top_m) - max(low, DEFAULT_GRID.bottom_m))
    assert float(weights.sum()) * DEFAULT_GRID.layer_thickness_m == pytest.approx(covered, abs=1e-6)


@given(st.lists(heights, min_size=3, max_size=3, unique=True))
def test_adjacent_bands_add_up(edges: list[float]) -> None:
    a, b, c = sorted(edges)
    joined = band_weights(AltitudeBand(a, c))
    split = band_weights(AltitudeBand(a, b)) + band_weights(AltitudeBand(b, c))
    np.testing.assert_allclose(split, joined, atol=1e-9)
