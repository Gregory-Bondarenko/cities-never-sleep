import math

import numpy as np
import pandas as pd
import pytest

from citiesneversleep.metrics.trends import (
    city_trends,
    classify,
    log_trend,
    mann_kendall_p,
    national_index,
    sen_slope,
)

YEARS = pd.Series(range(2012, 2025))


def test_sen_slope_robust_to_outlier():
    x = np.arange(10, dtype=float)
    y = 2 * x
    y[5] = 1000
    assert sen_slope(x, y) == pytest.approx(2.0)


def test_mann_kendall():
    assert mann_kendall_p(np.arange(13, dtype=float)) < 0.001
    assert mann_kendall_p(np.ones(13)) == 1.0
    rng = np.random.default_rng(0)
    assert mann_kendall_p(rng.normal(size=13)) > 0.05


def test_log_trend_recovers_growth_rate():
    values = 100 * 1.05 ** (YEARS - 2012)
    t = log_trend(YEARS, values)
    assert t.n == 13
    assert t.pct_per_year == pytest.approx(0.05, rel=1e-6)
    assert t.significant
    assert classify(t) == "растёт"


def test_log_trend_decline_and_stable():
    assert classify(log_trend(YEARS, 100 * 0.97 ** (YEARS - 2012))) == "гаснет"
    flat = 100 * (1 + 0.001 * (YEARS - 2012))
    assert classify(log_trend(YEARS, flat)) == "стабилен"  # значимо, но меньше 1% в год


def test_log_trend_too_short():
    t = log_trend(YEARS[:5], pd.Series([1, 2, 3, 4, 5]))
    assert t.n == 5 and math.isnan(t.slope)
    assert classify(t) == "мало данных"


def _lights(city_id, base, growth, growth_r2=None):
    return pd.DataFrame(
        {
            "city_id": city_id,
            "year": YEARS,
            "sol": base * growth ** (YEARS - 2012),
            "sol_r2": 3 * base * (growth_r2 or growth) ** (YEARS - 2012),
            "flag_nan": False,
            "flag_near_cap": False,
        }
    )


def test_national_index_removes_common_shift():
    lights = pd.concat([_lights(f"Q{i}", 100 * (i + 1), 1.0) for i in range(5)])
    lights.loc[lights["year"] >= 2021, ["sol", "sol_r2"]] *= 1.3  # общая ступенька
    idx = national_index(lights)
    assert idx[2012] == 0
    assert math.exp(idx[2021]) == pytest.approx(1.3)


def test_city_trends_relative():
    lights = pd.concat(
        [
            _lights("Q1", 100, 1.06),  # быстрее остальных
            _lights("Q2", 200, 1.01),
            _lights("Q3", 300, 1.01),
            _lights("Q4", 400, 1.01),
            _lights("Q5", 500, 0.96),  # медленнее остальных
        ]
    )
    lights.loc[lights["year"] >= 2021, ["sol", "sol_r2"]] *= 1.3
    lights.loc[lights["city_id"] == "Q1", "flag_near_cap"] = True
    population = pd.DataFrame(
        {
            "city_id": "Q1",
            "year": YEARS,
            "population": (50_000 * 0.98 ** (YEARS - 2012)).round(),
            "is_primary": True,
        }
    )
    t = city_trends(lights, population).set_index("city_id")
    assert t.loc["Q1", "lights_class"] == "растёт"
    assert t.loc["Q1", "lights_rel_pct_per_year"] == pytest.approx(1.06 / 1.01 - 1, rel=1e-3)
    assert t.loc["Q3", "lights_class"] == "стабилен"
    assert t.loc["Q5", "lights_class"] == "гаснет"
    assert t.loc["Q3", "lights_raw_pct_per_year"] > 0.01  # без поправки ступенька даёт рост
    assert t.loc["Q1", "population_class"] == "гаснет"
    assert t.loc["Q1", "quadrant"] == "свет растёт, население гаснет"
    assert t.loc["Q2", "quadrant"] == "мало данных"
    assert t.loc["Q1", "any_flag_near_cap"]


def test_population_trend_needs_only_five_years():
    lights = pd.concat([_lights(f"Q{i}", 100 * (i + 1), 1.0) for i in range(3)])
    population = pd.DataFrame(
        {
            "city_id": "Q1",
            "year": [2016, 2017, 2018, 2019, 2020],
            "population": [100_000, 102_000, 104_000, 106_100, 108_200],
            "is_primary": True,
        }
    )
    t = city_trends(lights, population).set_index("city_id")
    assert t.loc["Q1", "n_years_population"] == 5
    assert t.loc["Q1", "population_class"] == "растёт"
