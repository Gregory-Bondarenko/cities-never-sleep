import numpy as np
import pandas as pd

from citiesneversleep.reference.regions import region_of
from citiesneversleep.story import (
    cumulative_change,
    decile_percentile,
    highlights,
    quadrant_counts,
    region_summary,
)


def test_region_of():
    assert region_of("32701000001") == "Кемеровская область"
    assert region_of("71701000001") == "Тюменская область"
    assert region_of("71874000001") == "Ханты-Мансийский АО"
    assert region_of("71800000000") == "Ханты-Мансийский АО"
    assert region_of("71951000001") == "Ямало-Ненецкий АО"
    assert region_of("67000000001") == "Севастополь"
    assert region_of(None) is None and region_of("x") is None


def test_cumulative_change_baseline_and_smoothing():
    years = list(range(2012, 2019))
    rel = pd.DataFrame([np.exp(0.1 * np.arange(7))], index=["a"], columns=years)
    ch = cumulative_change(rel).loc["a"]
    # опора: среднее ln первых трёх лет = 0,1; сглаженное 2015 = 0,3
    assert abs(ch[2015] - 0.2) < 1e-9
    rel.loc["a", 2014] = 0
    assert cumulative_change(rel).loc["a"].notna().sum() >= 5


def _trends():
    return pd.DataFrame(
        {
            "city_id": list("abcdef"),
            "brightness_decile": [1, 1, 1, 2, 2, 2],
            "lights_rel_pct_per_year": [-0.05, 0.0, 0.05, 0.02, 0.03, np.nan],
            "lights_class": ["гаснет", "стабилен", "растёт", "растёт", "растёт", "мало данных"],
            "population_class": ["гаснет", "гаснет", "гаснет", "растёт", "стабилен", "гаснет"],
            "population_pct_per_year": [-0.02, -0.01, -0.02, 0.01, 0.0, np.nan],
            "population_latest": [60_000, 40_000, 2_000_000, 80_000, 10_000, 5_000],
            "flag_point_source": [False, False, False, True, False, False],
            "region": ["A", "A", "A", "B", "B", None],
        }
    )


def test_percentile_within_decile():
    p = decile_percentile(_trends())
    assert p["a"] < p["b"] < p["c"] and "f" not in p.index


def test_highlights_and_quadrants():
    t = _trends()
    h = highlights(t)
    assert h["rising"] == ["c"]  # d исключён как точечный источник
    assert h["fading"] == ["a"]
    assert h["brighter_while_shrinking"] == ["c"]
    assert h["millions"] == ["c"]
    q = quadrant_counts(t)
    assert q["lights_down_people_down"] == 1 and q["lights_up_people_down"] == 1


def test_region_summary_min_cities():
    r = region_summary(_trends(), min_cities=2)
    assert [x["region"] for x in r] == ["A"] and r[0]["n"] == 3  # d исключён: точечный источник
    assert region_summary(_trends()) == []


def test_capitals_summary():
    from citiesneversleep.story import capitals_summary

    t = pd.DataFrame(
        {
            "city_id": ["g", "k", "m", "x"],
            "name": ["Грозный", "Кемерово", "Москва", "Новокузнецк"],
            "region": ["Чечня", "Кемеровская область", "Москва", "Кемеровская область"],
            "lights_rel_pct_per_year": [0.12, -0.02, 0.0, -0.05],
            "lights_class": ["растёт", "гаснет", "стабилен", "гаснет"],
            "flag_point_source": [False, False, False, False],
        }
    )
    s = capitals_summary(t)
    assert s["republics"]["n"] == 1 and s["republics"]["up"] == 1
    assert s["other"]["n"] == 2 and s["other"]["down"] == 1  # Новокузнецк не центр
