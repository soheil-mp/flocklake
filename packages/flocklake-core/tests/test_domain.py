import dataclasses
import itertools

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from flocklake_core.domain import DEFAULT_GRID, QUANTITIES, Band, ProfileGrid, RadarSite


def site(**overrides: object) -> RadarSite:
    values: dict[str, object] = {
        "odim_code": "nldhl",
        "name": "Den Helder",
        "latitude_deg": 52.953,
        "longitude_deg": 4.791,
        "antenna_height_m": 51.0,
        "wavelength_cm": 5.3,
        "wigos_id": "0-20000-0-06234",
    }
    return RadarSite(**(values | overrides))  # type: ignore[arg-type]


class TestBand:
    @pytest.mark.parametrize(
        ("wavelength_cm", "band"),
        [(3.2, Band.X), (5.3, Band.C), (5.6, Band.C), (10.7, Band.S), (7.5, Band.S)],
    )
    def test_from_wavelength(self, wavelength_cm: float, band: Band) -> None:
        assert Band.from_wavelength(wavelength_cm) is band

    @pytest.mark.parametrize("wavelength_cm", [0.053, 1.0, 15.0, 530.0])
    def test_rejects_wavelengths_outside_weather_radar_bands(self, wavelength_cm: float) -> None:
        with pytest.raises(ValueError, match="outside"):
            Band.from_wavelength(wavelength_cm)

    def test_bands_tile_the_range_without_gaps(self) -> None:
        ranges = sorted(b.wavelength_range_cm for b in Band)
        assert all(a[1] == b[0] for a, b in itertools.pairwise(ranges))


class TestRadarSite:
    def test_derives_the_band(self) -> None:
        assert site().band is Band.C
        assert site(wavelength_cm=10.7, odim_code="uskbo", icao="KBOX").band is Band.S

    def test_is_immutable(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            site().name = "x"  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"odim_code": "NLDHL"}, "odim_code"),
            ({"odim_code": "nl-dhl"}, "odim_code"),
            ({"wigos_id": "06234"}, "wigos_id"),
            ({"icao": "kbox"}, "icao"),
            ({"name": "  "}, "name"),
            ({"latitude_deg": 95.0}, "position"),
            ({"longitude_deg": 4.791, "latitude_deg": -91.0}, "position"),
            ({"antenna_height_m": float("nan")}, "antenna_height_m"),
            ({"antenna_height_m": 51_000.0}, "antenna_height_m"),
            ({"wavelength_cm": 0.053}, "outside"),
        ],
    )
    def test_rejects_invalid_values(self, overrides: dict[str, object], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            site(**overrides)

    def test_optional_identifiers(self) -> None:
        bare = site(wigos_id=None)
        assert bare.wigos_id is None
        assert bare.icao is None


class TestProfileGrid:
    def test_default_grid_is_the_vol2bird_grid(self) -> None:
        assert DEFAULT_GRID.bottoms_m.tolist() == [200.0 * i for i in range(25)]
        assert DEFAULT_GRID.top_m == 5_000.0
        np.testing.assert_array_equal(DEFAULT_GRID.midpoints_m, DEFAULT_GRID.bottoms_m + 100)

    @given(
        thickness=st.floats(1.0, 1_000.0),
        layers=st.integers(1, 100),
        bottom=st.floats(-100.0, 100.0),
    )
    def test_layers_are_contiguous(self, thickness: float, layers: int, bottom: float) -> None:
        grid = ProfileGrid(thickness, layers, bottom)
        np.testing.assert_allclose(np.diff(grid.bottoms_m), thickness)
        assert grid.bottoms_m[-1] + thickness == pytest.approx(grid.top_m)

    @pytest.mark.parametrize(("thickness", "layers"), [(0.0, 25), (200.0, 0), (-1.0, 3)])
    def test_rejects_empty_grids(self, thickness: float, layers: int) -> None:
        with pytest.raises(ValueError, match="positive layer thickness"):
            ProfileGrid(thickness, layers)


def test_every_quantity_has_a_unit_and_a_description() -> None:
    assert {"dens", "eta", "ff", "dd", "mtr", "vid"} <= set(QUANTITIES)
    for name, quantity in QUANTITIES.items():
        assert quantity.name == name
        assert quantity.unit
        assert quantity.description
