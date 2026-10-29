from citiesneversleep import __version__


def test_version_is_dev():
    assert "0.1.0" in __version__
    assert "dev" in __version__
