from importlib.metadata import version
from importlib.resources import files

import pytest

import flocklake_core

pytestmark = pytest.mark.unit


def test_version_matches_installed_metadata() -> None:
    assert flocklake_core.__version__ == version("flocklake-core")


def test_package_ships_type_information() -> None:
    assert files("flocklake_core").joinpath("py.typed").is_file()
