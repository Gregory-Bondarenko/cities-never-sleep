import math

import numpy as np
import pandas as pd
import pytest

from citiesneversleep.metrics.trends import (
    city_trends,
    classify,
    log_trend,
    mann_kendall_p,
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


def test_city_trends():
    lights = pd.DataFrame(
        {
            "city_id": ["Q1"] * 13,
            "year": YEARS,
            "sol": 100 * 1.05 ** (YEARS - 2012),
            "sol_r2": 300 * 1.04 ** (YEARS - 2012),
            "flag_nan": False,
            "flag_near_cap": [False] * 12 + [True],
        }
    )
    population = pd.DataFrame(
        {
            "city_id": ["Q1"] * 13,
            "year": YEARS,
            "population": (50_000 * 0.98 ** (YEARS - 2012)).round(),
            "is_primary": True,
        }
    )
    t = city_trends(lights, population).iloc[0]
    assert t["lights_class"] == "растёт"
    assert t["lights_class_pre2022"] == "растёт"
    assert t["lights_pct_per_year_r2"] == pytest.approx(0.04, rel=1e-6)
    assert t["population_class"] == "гаснет"
    assert t["quadrant"] == "свет растёт, население гаснет"
    assert t["any_flag_near_cap"] and not t["any_flag_nan"]
