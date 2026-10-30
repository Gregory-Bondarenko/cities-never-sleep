"""Тренды яркости и населения по городам.

Тренд оценивается на логарифме ряда, поэтому наклон Сена переводится
в относительное изменение за год: exp(β) − 1. Значимость проверяется
тестом Манна–Кендалла с поправкой на совпадающие значения.
Реализация на numpy, без дополнительных зависимостей.

Классы яркости строятся по относительному ряду: логарифм яркости города
минус национальный индекс (медиана по городам центрированных логарифмов
за год). Так снимаются сдвиги, общие для всех городов, в том числе
ступенька 2021 года в наборе VNL (ADR-0007). Класс «растёт» означает
рост быстрее типичного города России.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_YEARS = 8  # меньше точек: тренд не оценивается
ALPHA = 0.05
STABLE_BAND = 0.01  # |изменение| < 1% в год считается стабильностью
SEAM_LAST_YEAR = 2021  # последний год до смены шкалы VNL (#10)
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class Trend:
    n: int
    slope: float  # наклон Сена ln(y) за год
    pct_per_year: float  # exp(slope) − 1
    p_value: float

    @property
    def significant(self) -> bool:
        return self.p_value < ALPHA


NO_TREND = Trend(0, float("nan"), float("nan"), float("nan"))


def sen_slope(x: np.ndarray, y: np.ndarray) -> float:
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    ok = dx != 0
    return float(np.median((y[j] - y[i])[ok] / dx[ok]))


def mann_kendall_p(y: np.ndarray) -> float:
    """Двусторонний p-value теста Манна–Кендалла.

    Нормальное приближение с поправкой на совпадающие значения.
    """
    n = len(y)
    i, j = np.triu_indices(n, k=1)
    s = float(np.sign(y[j] - y[i]).sum())
    _, counts = np.unique(y, return_counts=True)
    ties = float(np.sum(counts * (counts - 1) * (2 * counts + 5)))
    var = (n * (n - 1) * (2 * n + 5) - ties) / 18
    if var <= 0:
        return 1.0
    z = (s - np.sign(s)) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def log_trend(years: pd.Series, values: pd.Series, min_years: int = MIN_YEARS) -> Trend:
    """Тренд ln(values) по годам; нулевые, отрицательные и пропущенные значения отбрасываются."""
    df = pd.DataFrame({"x": years, "y": values}).dropna()
    df = df[df["y"] > 0]
    if len(df) < min_years:
        return Trend(len(df), float("nan"), float("nan"), float("nan"))
    x = df["x"].to_numpy(dtype="float64")
    y = np.log(df["y"].to_numpy(dtype="float64"))
    slope = sen_slope(x, y)
    return Trend(len(df), slope, math.exp(slope) - 1, mann_kendall_p(y))


def classify(trend: Trend) -> str:
    """Класс динамики: растёт, гаснет, стабилен или недостаточно данных."""
    if trend.n == 0 or math.isnan(trend.slope):
        return "мало данных"
    if trend.significant and trend.pct_per_year >= STABLE_BAND:
        return "растёт"
    if trend.significant and trend.pct_per_year <= -STABLE_BAND:
        return "гаснет"
    return "стабилен"


def national_index(lights: pd.DataFrame, column: str = "sol") -> pd.Series:
    """Национальный индекс яркости в логарифмах по годам (ADR-0007).

    Для каждого города логарифм ряда центрируется по его среднему, затем по
    каждому году берётся медиана по городам. Учитываются только города с
    положительными значениями во все годы.
    """
    piv = lights.pivot(index="city_id", columns="year", values=column)
    piv = piv[(piv > 0).all(axis=1)]
    logs = np.log(piv.astype("float64"))
    centered = logs.sub(logs.mean(axis=1), axis=0)
    idx = centered.median(axis=0)
    return idx - idx.iloc[0]


def city_trends(lights: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Тренды по каждому городу.

    ``lights``: набор city_lights; ``population``: основные значения населения
    (``is_primary``) за те же годы.
    """
    years = sorted(lights["year"].unique())
    y0, y1 = years[0], years[-1]
    pop = population[population["is_primary"] & population["year"].between(y0, y1)][
        ["city_id", "year", "population"]
    ]
    pop_by_city = dict(tuple(pop.groupby("city_id")))

    index = np.exp(national_index(lights))
    lights = lights.assign(sol_rel=lights["sol"] / lights["year"].map(index))
    lights = lights.assign(
        sol_r2_rel=lights["sol_r2"] / lights["year"].map(np.exp(national_index(lights, "sol_r2")))
    )

    rows = []
    for city_id, g in lights.groupby("city_id"):
        g = g.sort_values("year")
        t_raw = log_trend(g["year"], g["sol"])
        t_all = log_trend(g["year"], g["sol_rel"])
        pre = g[g["year"] <= SEAM_LAST_YEAR]
        t_pre = log_trend(pre["year"], pre["sol_rel"])
        t_r2 = log_trend(g["year"], g["sol_r2_rel"])
        p = pop_by_city.get(city_id)
        t_pop = log_trend(p["year"], p["population"]) if p is not None else NO_TREND
        rows.append(
            {
                "city_id": city_id,
                "n_years_lights": t_all.n,
                "lights_rel_pct_per_year": t_all.pct_per_year,
                "lights_rel_p_value": t_all.p_value,
                "lights_class": classify(t_all),
                "lights_raw_pct_per_year": t_raw.pct_per_year,
                "lights_rel_pct_per_year_pre2022": t_pre.pct_per_year,
                "lights_class_pre2022": classify(t_pre),
                "lights_rel_pct_per_year_r2": t_r2.pct_per_year,
                "n_years_population": t_pop.n,
                "population_pct_per_year": t_pop.pct_per_year,
                "population_p_value": t_pop.p_value,
                "population_class": classify(t_pop),
                "any_flag_nan": bool(g["flag_nan"].fillna(False).any()),
                "any_flag_near_cap": bool(g["flag_near_cap"].fillna(False).any()),
            }
        )
    out = pd.DataFrame(rows)
    out["quadrant"] = [
        quadrant(a, b) for a, b in zip(out["lights_class"], out["population_class"], strict=True)
    ]
    return out


def quadrant(lights_class: str, population_class: str) -> str:
    """Сопоставление динамики света и населения."""
    if "мало данных" in (lights_class, population_class):
        return "мало данных"
    return f"свет {lights_class}, население {population_class}"


def build_city_trends(dest_dir=None):
    """Собрать ``trends/city_trends`` из city_lights, населения и справочника городов."""
    from citiesneversleep.meta import build_meta, write_meta
    from citiesneversleep.paths import (
        CITIES_PROCESSED_DIR,
        LIGHTS_PROCESSED_DIR,
        POP_PROCESSED_DIR,
        TRENDS_PROCESSED_DIR,
    )

    lights = pd.read_parquet(LIGHTS_PROCESSED_DIR / "city_lights.parquet")
    population = pd.read_parquet(POP_PROCESSED_DIR / "ru_cities_population.parquet")
    cities = pd.read_parquet(CITIES_PROCESSED_DIR / "ru_cities.parquet")
    trends = city_trends(lights, population)
    trends = cities[["city_id", "name", "lat", "lon", "population_latest"]].merge(
        trends, on="city_id", how="right"
    )

    dest_dir = dest_dir or TRENDS_PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "city_trends.parquet"
    trends.to_parquet(out, index=False)
    trends.to_csv(dest_dir / "city_trends.csv", index=False)
    meta = build_meta(
        schema_version=SCHEMA_VERSION,
        source=["lights/city_lights", "population/ru_cities_population", "cities/ru_cities"],
        n_rows=len(trends),
        license_note="VNL: CC-BY 4.0; Wikidata: CC0",
        method="наклон Сена по ln(ряда), тест Манна–Кендалла с поправкой на совпадения",
        lights_class_basis="относительно национального индекса (ADR-0007)",
        national_index={
            int(k): round(float(v), 4) for k, v in np.exp(national_index(lights)).items()
        },
        min_years=MIN_YEARS,
        alpha=ALPHA,
        stable_band_pct_per_year=STABLE_BAND * 100,
        lights_class_counts=trends["lights_class"].value_counts().to_dict(),
        population_class_counts=trends["population_class"].value_counts().to_dict(),
    )
    write_meta(dest_dir / "city_trends.meta.json", meta)
    return out, trends
