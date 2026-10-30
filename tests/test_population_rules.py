"""Выбор одного значения населения на город и год и справочник городов."""

import pandas as pd
import pytest

from citiesneversleep.process.boundaries import R_MAX_KM, R_MIN_KM, radius_km
from citiesneversleep.sources.wikidata_pop import (
    CITIES_COLUMNS,
    cities_from_rows,
    rows_to_dataframe,
)

E = "http://www.wikidata.org/entity/"
RANK = "http://wikiba.se/ontology#"


def _pop(qid, pop, date, rank="Normal", method=None, oktmo="01614101001"):
    row = {
        "city": E + qid,
        "cityLabel": qid,
        "oktmo": oktmo,
        "pop": str(pop),
        "date": date,
        "rank": f"{RANK}{rank}Rank",
    }
    if method:
        row["method"] = E + method
    return row


def _primary(df, qid, year):
    sel = df[(df["city_id"] == qid) & (df["year"] == year) & df["is_primary"]]
    assert len(sel) == 1
    return int(sel["population"].iloc[0])


def test_preferred_rank_wins():
    df = rows_to_dataframe(
        [
            _pop("Q1", 100, "2020-01-01T00:00:00Z", rank="Normal"),
            _pop("Q1", 110, "2020-01-01T00:00:00Z", rank="Preferred"),
        ]
    )
    assert _primary(df, "Q1", 2020) == 110
    assert df["is_conflict"].all()
    assert (df["n_values"] == 2).all()


def test_census_beats_estimate_and_deprecated_ignored():
    df = rows_to_dataframe(
        [
            _pop("Q1", 100, "2021-01-01T00:00:00Z"),
            _pop("Q1", 105, "2021-10-01T00:00:00Z", method="Q39825"),
            _pop("Q1", 999, "2021-12-01T00:00:00Z", rank="Deprecated"),
        ]
    )
    assert _primary(df, "Q1", 2021) == 105
    deprecated = df[df["rank"] == "deprecated"]
    assert not deprecated["is_primary"].any()
    assert (df.loc[df["rank"] != "deprecated", "n_values"] == 2).all()


def test_later_date_then_larger_value():
    df = rows_to_dataframe(
        [
            _pop("Q1", 100, "2019-01-01T00:00:00Z"),
            _pop("Q1", 101, "2019-07-01T00:00:00Z"),
            _pop("Q2", 50, "2019-01-01T00:00:00Z"),
            _pop("Q2", 60, "2019-01-01T00:00:00Z"),
        ]
    )
    assert _primary(df, "Q1", 2019) == 101
    assert _primary(df, "Q2", 2019) == 60


def test_no_conflict_for_duplicates_and_no_year():
    df = rows_to_dataframe(
        [
            _pop("Q1", 100, "2018-01-01T00:00:00Z"),
            _pop("Q1", 100, "2018-01-01T00:00:00Z"),
            _pop("Q1", 90, None),
        ]
    )
    assert _primary(df, "Q1", 2018) == 100
    assert not df["is_conflict"].any()
    assert not df.loc[df["year"].isna(), "is_primary"].any()


def test_cities_from_rows():
    population = rows_to_dataframe(
        [
            _pop("Q1", 100, "2020-01-01T00:00:00Z"),
            _pop("Q1", 120, "2024-01-01T00:00:00Z"),
        ]
    )
    rows = [
        {
            "city": E + "Q1",
            "cityLabel": "Город",
            "oktmo": "019u4y4992",
            "coord": "Point(37.6 55.7)",
        },
        {
            "city": E + "Q1",
            "cityLabel": "Город",
            "oktmo": "45000000000",
            "coord": "Point(37.5 55.8)",
        },
        {"city": E + "Q2", "cityLabel": "Без координат", "oktmo": "45000000"},
    ]
    cities = cities_from_rows(rows, population)
    assert list(cities.columns) == CITIES_COLUMNS
    assert len(cities) == 2
    q1 = cities.set_index("city_id").loc["Q1"]
    assert q1["oktmo_status"] == "ok"  # корректный ОКТМО предпочтён
    assert (q1["lat"], q1["lon"]) == (55.8, 37.5)
    assert (q1["population_latest"], q1["population_latest_year"]) == (120, 2024)
    q2 = cities.set_index("city_id").loc["Q2"]
    assert pd.isna(q2["lat"]) and pd.isna(q2["population_latest"])


@pytest.mark.parametrize(
    ("pop", "expected"),
    [
        (10_000, R_MIN_KM),
        (100_000, 4.743),
        (1_000_000, 15.0),
        (13_000_000, R_MAX_KM),
        (None, R_MIN_KM),
    ],
)
def test_radius_km(pop, expected):
    assert radius_km(pop) == pytest.approx(expected, abs=1e-3)


def test_radius_km_series():
    r = radius_km(pd.Series([1_000_000, None]))
    assert r.tolist() == pytest.approx([15.0, R_MIN_KM])
