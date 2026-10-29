from citiesneversleep.sources.vnl_zenodo import parse_years_spec


def test_parse_range():
    assert parse_years_spec("2012-2014") == [2012, 2013, 2014]


def test_parse_list():
    assert parse_years_spec("2013,2020,2022") == [2013, 2020, 2022]


def test_parse_mixed():
    assert parse_years_spec("2012-2013,2024") == [2012, 2013, 2024]
