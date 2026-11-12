"""Показатели сюжета витрины: накопленное изменение, место среди похожих,
регионы и подборки городов (ADR-0001: витрина только показывает эти числа).

Все отборы заданы правилами здесь, а не в тексте страницы, чтобы при
пересборке данных подборки обновлялись вместе с ними.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from citiesneversleep.reference.regions import CAPITALS, REPUBLICS

BASE_YEARS = 3  # опорный уровень: среднее первых трёх лет
SMOOTH = 3  # окно скользящего среднего, лет
MIN_POP_HIGHLIGHT = 50_000
MIN_POP_QUADRANT = 30_000
TOP_N = 8
MIN_REGION_CITIES = 5


def cumulative_change(rel: pd.DataFrame) -> pd.DataFrame:
    """Накопленное изменение относительного ряда к опорному уровню, ln.

    ``rel``: города × годы, относительный ряд (к децили, без региональной
    составляющей). Ряд логарифмируется и сглаживается скользящим средним
    по SMOOTH лет с центром; опорный уровень: среднее логарифма первых
    BASE_YEARS лет. Нули и пропуски дают NaN.
    """
    log = np.log(rel.where(rel > 0).astype(float))
    smooth = log.T.rolling(SMOOTH, center=True, min_periods=2).mean().T
    base = log.iloc[:, :BASE_YEARS].mean(axis=1)
    return smooth.sub(base, axis=0)


def decile_percentile(trends: pd.DataFrame) -> pd.Series:
    """Доля городов той же децили яркости с меньшим относительным трендом, 0..1."""
    t = trends.dropna(subset=["lights_rel_pct_per_year"])
    pct = t.groupby("brightness_decile")["lights_rel_pct_per_year"].rank(pct=True, method="average")
    n = t.groupby("brightness_decile")["lights_rel_pct_per_year"].transform("size")
    # rank(pct) даёт (k)/n; доля строго меньших: (k - 0.5)/n для середины ранга
    share = (pct * n - 0.5) / n
    return pd.Series(share.to_numpy(), index=t["city_id"].to_numpy(), name="pctile")


def region_summary(trends: pd.DataFrame, min_cities: int = MIN_REGION_CITIES) -> list[dict]:
    """Сводка по субъектам РФ с не менее чем ``min_cities`` городами с трендом.

    Точечные источники исключены: один новый объект в маленьком городе
    сдвигает медиану региона с пятью-семью городами.
    """
    t = trends[~trends["flag_point_source"].astype(bool)].dropna(
        subset=["region", "lights_rel_pct_per_year"]
    )
    out = []
    for name, g in t.groupby("region"):
        if len(g) < min_cities:
            continue
        out.append(
            {
                "region": name,
                "n": int(len(g)),
                "median_pct": round(float(g["lights_rel_pct_per_year"].median()), 4),
                "share_up": round(float((g["lights_class"] == "растёт").mean()), 3),
                "share_down": round(float((g["lights_class"] == "гаснет").mean()), 3),
                "population_median_pct": None
                if g["population_pct_per_year"].isna().all()
                else round(float(g["population_pct_per_year"].median()), 4),
            }
        )
    return sorted(out, key=lambda r: r["median_pct"], reverse=True)


def _ids(df: pd.DataFrame) -> list[str]:
    return df["city_id"].head(TOP_N).tolist()


def highlights(trends: pd.DataFrame) -> dict[str, list[str]]:
    """Подборки городов для глав сюжета. Точечные источники исключены."""
    t = trends[~trends["flag_point_source"].astype(bool)].dropna(subset=["lights_rel_pct_per_year"])
    pop = t["population_latest"].fillna(0)
    big = t[pop >= MIN_POP_HIGHLIGHT]
    mid = t[pop >= MIN_POP_QUADRANT]
    by_pop = lambda d: d.sort_values("population_latest", ascending=False)  # noqa: E731
    return {
        "rising": _ids(
            big[big["lights_class"] == "растёт"].sort_values(
                "lights_rel_pct_per_year", ascending=False
            )
        ),
        "fading": _ids(big[big["lights_class"] == "гаснет"].sort_values("lights_rel_pct_per_year")),
        "fading_with_people": _ids(
            by_pop(mid[(mid["lights_class"] == "гаснет") & (mid["population_class"] == "гаснет")])
        ),
        "brighter_while_shrinking": _ids(
            by_pop(mid[(mid["lights_class"] == "растёт") & (mid["population_class"] == "гаснет")])
        ),
        "millions": trends[trends["population_latest"].fillna(0) >= 1_000_000]
        .sort_values("lights_rel_pct_per_year", ascending=False)["city_id"]
        .tolist(),
    }


def quadrant_counts(trends: pd.DataFrame) -> dict[str, int]:
    """Число городов в сочетаниях классов света и населения (без «мало данных»)."""
    t = trends[
        (trends["lights_class"] != "мало данных") & (trends["population_class"] != "мало данных")
    ]
    return {
        "lights_down_people_down": int(
            ((t["lights_class"] == "гаснет") & (t["population_class"] == "гаснет")).sum()
        ),
        "lights_up_people_down": int(
            ((t["lights_class"] == "растёт") & (t["population_class"] == "гаснет")).sum()
        ),
        "lights_down_people_up": int(
            ((t["lights_class"] == "гаснет") & (t["population_class"] == "растёт")).sum()
        ),
        "lights_up_people_up": int(
            ((t["lights_class"] == "растёт") & (t["population_class"] == "растёт")).sum()
        ),
    }


def capitals_summary(trends: pd.DataFrame) -> dict[str, dict]:
    """Административные центры: столицы республик против центров остальных субъектов.

    Точечные источники не исключаются: у центра субъекта новый крупный объект
    сам по себе часть динамики города; число таких центров приводится отдельно.
    """
    t = trends.dropna(subset=["region"])
    is_cap = np.array(
        [CAPITALS.get(r) == n for r, n in zip(t["region"], t["name"], strict=True)], dtype=bool
    )
    caps = t[is_cap]
    out = {}
    for key, g in (
        ("republics", caps[caps["region"].isin(REPUBLICS)]),
        ("other", caps[~caps["region"].isin(REPUBLICS)]),
    ):
        g = g.dropna(subset=["lights_rel_pct_per_year"])
        out[key] = {
            "n": int(len(g)),
            "up": int((g["lights_class"] == "растёт").sum()),
            "down": int((g["lights_class"] == "гаснет").sum()),
            "point_source": int(g["flag_point_source"].astype(bool).sum()),
            "median_pct": round(float(g["lights_rel_pct_per_year"].median()), 4),
            "ids": g.sort_values("lights_rel_pct_per_year", ascending=False)["city_id"].tolist(),
        }
    return out


RANKING_GROUPS = {"all": 0, "100k": 100_000, "1m": 1_000_000}
RANKING_N = 10
_NAME_PREFIXES = ("городской округ ", "городское поселение ")


def display_name(name: str) -> str:
    """Название для витрины без административной приставки из Wikidata."""
    for prefix in _NAME_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def ranks(trends: pd.DataFrame) -> pd.DataFrame:
    """Место города по относительному тренду: в стране и в своём субъекте.

    Место 1 у самого быстрого роста. Города без тренда места не получают.
    Точечные источники не исключаются, флаг показывается на карточке.
    """
    t = trends.dropna(subset=["lights_rel_pct_per_year"])
    out = pd.DataFrame(index=t["city_id"].to_numpy())
    out["rank"] = t["lights_rel_pct_per_year"].rank(ascending=False, method="min").to_numpy(int)
    reg = t.groupby("region", dropna=True)["lights_rel_pct_per_year"]
    out["rank_region"] = reg.rank(ascending=False, method="min").to_numpy()
    out["n_region"] = reg.transform("size").to_numpy()
    return out


def rankings(trends: pd.DataFrame) -> dict[str, dict[str, list[str]]]:
    """Первые RANKING_N светлеющих и гаснущих городов по группам размера.

    В списки входят только значимые тренды (класс «растёт» или «гаснет»)
    без точечных источников.
    """
    t = trends[~trends["flag_point_source"].astype(bool)].dropna(subset=["lights_rel_pct_per_year"])
    pop = t["population_latest"].fillna(0)
    out = {}
    for key, min_pop in RANKING_GROUPS.items():
        g = t[pop >= min_pop]
        up = g[g["lights_class"] == "растёт"].sort_values(
            "lights_rel_pct_per_year", ascending=False
        )
        down = g[g["lights_class"] == "гаснет"].sort_values("lights_rel_pct_per_year")
        out[key] = {
            "up": up["city_id"].head(RANKING_N).tolist(),
            "down": down["city_id"].head(RANKING_N).tolist(),
        }
    return out
