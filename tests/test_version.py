import re

from citiesneversleep import __version__


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+(-dev)?", __version__)
