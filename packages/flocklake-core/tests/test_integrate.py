import math
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from flocklake_core.bands import ROTOR_BAND, AltitudeBand
from flocklake_core.domain import ProfileGrid
from flocklake_core.integrate import height_quantiles, integrate_profile, migration_traffic
from flocklake_core.reflectivity import DEFAULT_RCS_CM2

LAYERS = 25
ONES = np.ones(LAYERS)


class Profile(TypedDict):
    dens: np.ndarray
    eta: np.ndarray
    ff: np.ndarray
    dd: np.ndarray


def profile(dens: float = 10.0, ff: float = 10.0, dd: float = 180.0) -> Profile:
    density = ONES * dens
    return {"dens": density, "eta": density * DEFAULT_RCS_CM2, "ff": ONES * ff, "dd": ONES * dd}


class TestIntegrateProfile:
    def test_uniform_profile(self) -> None:
        result = integrate_profile(**profile())
        assert float(result.vid) == pytest.approx(50.0)
        assert float(result.vir) == pytest.approx(50.0 * DEFAULT_RCS_CM2)
        assert float(result.mtr) == pytest.approx(1_800.0)
        assert float(result.rtr) == pytest.approx(1_800.0 * DEFAULT_RCS_CM2)
        assert float(result.height_mean_m) == pytest.approx(2_500.0)
        assert float(result.coverage) == float(result.traffic_coverage) == 1.0

    def test_birds_in_one_layer(self) -> None:
        dens = np.zeros(LAYERS)
        dens[3] = 100.0  # 600-800 m
        result = integrate_profile(dens, dens * 11, ONES * 15.0, ONES * 45.0)
        assert float(result.vid) == pytest.approx(20.0)
        assert float(result.mtr) == pytest.approx(100 * 15 * 3.6 * 0.2)
        assert float(result.height_mean_m) == pytest.approx(700.0)

    def test_rotor_band_uses_overlap_weights(self) -> None:
        result = integrate_profile(**profile(), band=ROTOR_BAND)
        assert float(result.vid) == pytest.approx(10.0 * 0.275)
        assert float(result.height_mean_m) == pytest.approx((0.875 * 100 + 0.5 * 300) / 1.375)

    @pytest.mark.parametrize(
        ("alpha", "factor"), [(180.0, 1.0), (0.0, -1.0), (90.0, 0.0), (120.0, 0.5)]
    )
    def test_direction_specific_traffic(self, alpha: float, factor: float) -> None:
        result = integrate_profile(**profile(dd=180.0), alpha_deg=alpha)
        assert float(result.mtr) == pytest.approx(1_800.0 * factor, abs=1e-9)

    def test_vectorised_over_time(self) -> None:
        dens = np.stack([ONES * 1.0, ONES * 2.0, ONES * 4.0])
        result = integrate_profile(dens, dens * 11, ONES * 10, ONES * 0)
        np.testing.assert_allclose(result.vid, [5.0, 10.0, 20.0])
        assert result.mtr.shape == (3,)

    def test_other_grids(self) -> None:
        grid = ProfileGrid(layer_thickness_m=100.0, layers=3)
        result = integrate_profile(
            [10.0, 0.0, 0.0], [110.0, 0.0, 0.0], [1.0] * 3, [0.0] * 3, grid=grid
        )
        assert float(result.vid) == pytest.approx(1.0)
        assert float(result.height_mean_m) == pytest.approx(50.0)


class TestMissingValueRules:
    def test_rule_1_missing_layers_contribute_nothing_and_lower_coverage(self) -> None:
        values = profile()
        values["dens"] = values["dens"].copy()
        values["dens"][:5] = np.nan
        gap = np.zeros(LAYERS, dtype=bool)
        gap[5] = True
        result = integrate_profile(**values, gap=gap)
        assert float(result.vid) == pytest.approx(10.0 * 0.2 * 19)
        assert float(result.coverage) == pytest.approx(19 / 25)

    def test_rule_1_all_missing_gives_nan(self) -> None:
        result = integrate_profile(ONES * np.nan, ONES, ONES, ONES)
        assert math.isnan(float(result.vid))
        assert math.isnan(float(result.mtr))
        assert float(result.coverage) == 0.0

    def test_rule_2_empty_layers_have_zero_traffic_without_speed(self) -> None:
        dens = np.zeros(LAYERS)
        dens[0] = 5.0
        ff = np.full(LAYERS, np.nan)
        ff[0] = 10.0
        result = integrate_profile(dens, dens * 11, ff, ONES * 0.0)
        assert float(result.mtr) == pytest.approx(5 * 36 * 0.2)
        assert float(result.traffic_coverage) == 1.0

    def test_rule_3_birds_without_speed_are_missing_for_traffic_only(self) -> None:
        values = profile()
        values["ff"] = values["ff"].copy()
        values["ff"][10] = np.nan
        result = integrate_profile(**values)
        assert float(result.vid) == pytest.approx(50.0)
        assert float(result.mtr) == pytest.approx(1_800.0 * 24 / 25)
        assert float(result.traffic_coverage) == pytest.approx(24 / 25)

    def test_rule_3_traffic_without_any_speed_is_nan(self) -> None:
        result = integrate_profile(ONES * 3.0, ONES * 33.0)
        assert float(result.vid) == pytest.approx(15.0)
        assert math.isnan(float(result.mtr))

    def test_rule_4_no_birds_no_height(self) -> None:
        assert math.isnan(float(integrate_profile(**profile(dens=0.0)).height_mean_m))

    def test_band_outside_the_grid_is_nan(self) -> None:
        result = integrate_profile(**profile(), band=AltitudeBand(6_000.0, 7_000.0))
        assert math.isnan(float(result.vid))

    def test_rejects_wrong_layer_counts(self) -> None:
        with pytest.raises(ValueError, match="25 layers"):
            integrate_profile(np.ones(24), np.ones(24))
        with pytest.raises(ValueError, match="eta must have 25 layers"):
            integrate_profile(ONES, np.ones(3))


@settings(max_examples=50)
@given(
    dens=hnp.arrays(np.float64, LAYERS, elements=st.floats(0.0, 1_000.0)),
    split=st.floats(1.0, 4_999.0),
)
def test_band_integrals_add_up_to_the_whole_profile(dens: np.ndarray, split: float) -> None:
    eta = dens * 11.0
    whole = integrate_profile(dens, eta, ONES * 12.0, ONES * 30.0)
    lower = integrate_profile(dens, eta, ONES * 12.0, ONES * 30.0, band=AltitudeBand(0.0, split))
    upper = integrate_profile(
        dens, eta, ONES * 12.0, ONES * 30.0, band=AltitudeBand(split, 5_000.0)
    )
    assert float(lower.vid) + float(upper.vid) == pytest.approx(
        float(whole.vid), rel=1e-9, abs=1e-9
    )
    assert float(lower.mtr) + float(upper.mtr) == pytest.approx(
        float(whole.mtr), rel=1e-9, abs=1e-9
    )


class TestHeightQuantiles:
    def test_uniform_profile_is_linear(self) -> None:
        np.testing.assert_allclose(
            height_quantiles(ONES, [0.0, 0.1, 0.5, 1.0]), [0, 500, 2_500, 5_000]
        )

    def test_single_layer(self) -> None:
        dens = np.zeros(LAYERS)
        dens[2] = 7.0  # 400-600 m
        np.testing.assert_allclose(height_quantiles(dens, [0.25, 0.5, 0.75]), [450, 500, 550])

    def test_band_clips_the_layers(self) -> None:
        np.testing.assert_allclose(
            height_quantiles(ONES, [0.0, 1.0], band=ROTOR_BAND), [25.0, 300.0]
        )

    def test_empty_profile_is_nan(self) -> None:
        assert np.all(np.isnan(height_quantiles(np.zeros(LAYERS))))

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(ValueError, match="shape"):
            height_quantiles(np.ones(3))
        with pytest.raises(ValueError, match="quantiles"):
            height_quantiles(ONES, [1.5])

    @given(hnp.arrays(np.float64, LAYERS, elements=st.floats(0.0, 100.0)))
    def test_quantiles_increase(self, dens: np.ndarray) -> None:
        heights = height_quantiles(dens, [0.1, 0.5, 0.9])
        if dens.sum() > 0:
            assert np.all(np.diff(heights) >= -1e-9)
            assert 0.0 <= heights[0] <= heights[-1] <= 5_000.0


class TestMigrationTraffic:
    start = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)

    def times(self, minutes: list[int]) -> list[datetime]:
        return [self.start + timedelta(minutes=m) for m in minutes]

    def test_constant_rate_over_a_night(self) -> None:
        times = self.times(list(range(0, 12 * 60, 5)))  # 12 h of 5-minute profiles
        result = migration_traffic(times, np.full(len(times), 500.0))
        assert result.mt == pytest.approx(6_000.0)
        assert result.covered_hours == pytest.approx(12.0)
        assert result.missing_hours == 0.0

    def test_long_gaps_are_capped(self) -> None:
        result = migration_traffic(self.times([0, 5, 300]), [100.0, 100.0, 100.0])
        # 5 min, then capped at 1 h, then the median step (2.5 h) capped at 1 h.
        assert result.covered_hours == pytest.approx(5 / 60 + 1 + 1)

    def test_missing_rates_are_reported(self) -> None:
        result = migration_traffic(self.times([0, 60, 120]), [100.0, np.nan, 100.0])
        assert result.mt == pytest.approx(200.0)
        assert result.missing_hours == pytest.approx(1.0)

    def test_edge_cases(self) -> None:
        assert migration_traffic([], []).mt == 0.0
        assert migration_traffic(self.times([0]), [100.0]).mt == 0.0
        assert math.isnan(migration_traffic(self.times([0, 5]), [np.nan, np.nan]).mt)

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(ValueError, match="one value per time"):
            migration_traffic(self.times([0, 5]), [1.0])
        with pytest.raises(ValueError, match="increasing"):
            migration_traffic(self.times([5, 0]), [1.0, 1.0])
