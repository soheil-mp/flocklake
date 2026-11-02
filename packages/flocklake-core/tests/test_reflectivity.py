import math

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from flocklake_core.reflectivity import (
    DEFAULT_RCS_CM2,
    WATER_K_SQUARED,
    dbz_from_eta,
    dbz_to_z,
    density_from_eta,
    eta_from_dbz,
    eta_from_density,
    z_to_dbz,
)

pytestmark = pytest.mark.unit

C_BAND_CM = 5.3
S_BAND_CM = 10.7

dbz_values = st.floats(min_value=-40.0, max_value=70.0, allow_nan=False)
positive_values = st.floats(min_value=1e-6, max_value=1e9, allow_nan=False)
wavelengths = st.floats(min_value=0.8, max_value=12.0, allow_nan=False)


def test_reproduces_a_real_aloft_profile() -> None:
    # Aloft (aloftdata.eu, CC BY 4.0): radar nldhl, 2026-10-15T00:00:00Z, height 0 m.
    # The file stores dbz, eta and dens; the formulas must reproduce eta and dens from dbz.
    dbz, eta_in_file, dens_in_file = -19.555999755859375, 3.992086887359619, 0.3629169762134552

    eta = eta_from_dbz(dbz, wavelength_cm=C_BAND_CM)
    density = density_from_eta(eta, rcs_cm2=11.0)

    assert eta == pytest.approx(eta_in_file, rel=2e-3)
    assert density == pytest.approx(dens_in_file, rel=2e-3)


def test_zero_dbz_at_c_band() -> None:
    expected = 1e3 * math.pi**5 * WATER_K_SQUARED / C_BAND_CM**4
    assert eta_from_dbz(0.0, wavelength_cm=C_BAND_CM) == pytest.approx(expected)
    assert expected == pytest.approx(360.69, abs=0.01)


def test_eta_scales_with_inverse_fourth_power_of_wavelength() -> None:
    at_c = eta_from_dbz(10.0, wavelength_cm=C_BAND_CM)
    at_double = eta_from_dbz(10.0, wavelength_cm=2 * C_BAND_CM)
    assert at_c / at_double == pytest.approx(16.0)


def test_scalar_in_float_out() -> None:
    assert type(dbz_to_z(10.0)) is float
    assert type(eta_from_dbz(10, wavelength_cm=S_BAND_CM)) is float
    assert type(density_from_eta(5)) is float


def test_array_in_array_out_keeps_shape() -> None:
    dbz = np.array([[-10.0, 0.0], [10.0, 20.0]])
    eta = eta_from_dbz(dbz, wavelength_cm=C_BAND_CM)
    assert isinstance(eta, np.ndarray)
    assert eta.shape == dbz.shape
    assert eta.dtype == np.float64
    np.testing.assert_allclose(dbz_from_eta(eta, wavelength_cm=C_BAND_CM), dbz)


def test_no_echo_and_missing_values() -> None:
    assert eta_from_dbz(-math.inf, wavelength_cm=C_BAND_CM) == 0.0
    assert dbz_from_eta(0.0, wavelength_cm=C_BAND_CM) == -math.inf
    assert math.isnan(eta_from_dbz(math.nan, wavelength_cm=C_BAND_CM))
    assert math.isnan(z_to_dbz(-1.0))


def test_default_cross_section_is_eleven_square_centimetres() -> None:
    assert DEFAULT_RCS_CM2 == 11.0
    assert density_from_eta(110.0) == pytest.approx(10.0)


@pytest.mark.parametrize("wavelength", [0.0, -5.3, math.nan, math.inf])
def test_rejects_invalid_wavelengths(wavelength: float) -> None:
    with pytest.raises(ValueError, match="wavelength_cm"):
        eta_from_dbz(0.0, wavelength_cm=wavelength)
    with pytest.raises(ValueError, match="wavelength_cm"):
        dbz_from_eta(1.0, wavelength_cm=wavelength)


@pytest.mark.parametrize("k_squared", [0.0, -0.93, 1.5, math.nan])
def test_rejects_invalid_dielectric_factor(k_squared: float) -> None:
    with pytest.raises(ValueError, match="k_squared"):
        eta_from_dbz(0.0, wavelength_cm=C_BAND_CM, k_squared=k_squared)


@pytest.mark.parametrize("rcs", [0.0, -11.0, math.nan])
def test_rejects_invalid_cross_section(rcs: float) -> None:
    with pytest.raises(ValueError, match="rcs_cm2"):
        density_from_eta(1.0, rcs_cm2=rcs)
    with pytest.raises(ValueError, match="rcs_cm2"):
        eta_from_density(1.0, rcs_cm2=rcs)


@given(dbz=dbz_values)
def test_dbz_and_linear_z_round_trip(dbz: float) -> None:
    assert z_to_dbz(dbz_to_z(dbz)) == pytest.approx(dbz, abs=1e-9)


@given(dbz=dbz_values, wavelength=wavelengths)
def test_dbz_and_eta_round_trip(dbz: float, wavelength: float) -> None:
    eta = eta_from_dbz(dbz, wavelength_cm=wavelength)
    assert dbz_from_eta(eta, wavelength_cm=wavelength) == pytest.approx(dbz, abs=1e-9)


@given(density=positive_values, rcs=st.floats(min_value=0.1, max_value=1000.0))
def test_density_and_eta_round_trip(density: float, rcs: float) -> None:
    eta = eta_from_density(density, rcs_cm2=rcs)
    assert density_from_eta(eta, rcs_cm2=rcs) == pytest.approx(density, rel=1e-12)


@given(low=dbz_values, high=dbz_values, wavelength=wavelengths)
def test_eta_increases_with_dbz(low: float, high: float, wavelength: float) -> None:
    assume(high - low > 1e-6)
    assert eta_from_dbz(low, wavelength_cm=wavelength) < eta_from_dbz(
        high, wavelength_cm=wavelength
    )
