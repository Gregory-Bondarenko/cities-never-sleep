"""Цифры для docs/findings.md: каждое число документа воспроизводится этим скриптом.

uv run python scripts/findings.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from citiesneversleep.metrics.trends import log_trend
from citiesneversleep.paths import CITIES_PROCESSED_DIR, LIGHTS_PROCESSED_DIR, TRENDS_PROCESSED_DIR


def main() -> None:
    t = pd.read_parquet(TRENDS_PROCESSED_DIR / "city_trends.parquet")
    lights = pd.read_parquet(LIGHTS_PROCESSED_DIR / "city_lights.parquet")
    cities = pd.read_parquet(CITIES_PROCESSED_DIR / "ru_cities.parquet")
    meta = json.loads((TRENDS_PROCESSED_DIR / "city_trends.meta.json").read_text(encoding="utf-8"))
    pct = lambda s: f"{s * 100:.1f}%"  # noqa: E731

    print("## Охват")
    print("городов:", len(cities), "| по ветвям:", cities["coverage"].value_counts().to_dict())
    print("годы яркости:", lights["year"].min(), "-", lights["year"].max())

    print("\n## Национальный индекс")
    print(meta["national_index"])

    piv = lights.pivot(index="city_id", columns="year", values="sol")
    up21 = (piv[2021] > piv[2020]).mean()
    print("доля городов с ростом суммы 2020→2021:", pct(up21))

    print("\n## Классы яркости (по децилям) и населения")
    print(t["lights_class"].value_counts().to_dict())
    print("по национальному индексу:", t["lights_class_national"].value_counts().to_dict())
    print("население:", t["population_class"].value_counts().to_dict())
    print("медиана тренда населения:", pct(t.population_pct_per_year.median()))
    print(
        "совпадение децили/национальный:", pct((t.lights_class == t.lights_class_national).mean())
    )
    print("совпадение полный ряд/до 2022:", pct((t.lights_class == t.lights_class_pre2022).mean()))
    print("медиана тренда без поправки:", pct(t.lights_raw_pct_per_year.median()))
    print("доля положительных без поправки:", pct((t.lights_raw_pct_per_year > 0).mean()))

    print("\n## Свет и население")
    print(pd.crosstab(t.lights_class, t.population_class, margins=True).to_string())
    v = t.dropna(subset=["lights_rel_pct_per_year", "population_pct_per_year"])
    rho = (
        v[["lights_rel_pct_per_year", "population_pct_per_year"]].corr(method="spearman").iloc[0, 1]
    )
    big = v[v.population_latest > 100_000]
    rho_big = big[["lights_rel_pct_per_year", "population_pct_per_year"]].corr(method="spearman")
    print(
        f"Спирмен все: {rho:.3f} (n={len(v)}); >100 тыс.: {rho_big.iloc[0, 1]:.3f} (n={len(big)})"
    )
    shrinking = t[t.population_class == "гаснет"]
    print(
        "города с сокращением населения, классы света:",
        shrinking.lights_class.value_counts().to_dict(),
    )

    print("\n## Крупные города (>500 тыс.)")
    cols = [
        "name",
        "lights_rel_pct_per_year",
        "lights_class",
        "population_pct_per_year",
        "population_class",
    ]
    print(
        t[t.population_latest > 500_000]
        .sort_values("lights_rel_pct_per_year")[cols]
        .round(3)
        .to_string()
    )

    print("\n## Города >100 тыс.: крайние по относительному тренду")
    b = t[(t.population_latest > 100_000) & t.lights_class.isin(["растёт", "гаснет"])]
    print(b.sort_values("lights_rel_pct_per_year")[cols].round(3).to_string())

    print("\n## Крым и Севастополь")
    print(
        t[t.city_id.isin(cities[cities.coverage == "oktmo_only"].city_id)][cols]
        .round(3)
        .to_string()
    )

    print("\n## Чувствительность к радиусу (тренды без поправки)")
    rows = []
    for _, g in lights.groupby("city_id"):
        rows.append([log_trend(g.year, g[c]).pct_per_year for c in ("sol", "sol_r05", "sol_r2")])
    r = pd.DataFrame(rows, columns=["r", "r05", "r2"]).dropna()
    sp = r.corr(method="spearman")
    agree = lambda a, b: pct((np.sign(r[a]) == np.sign(r[b])).mean())  # noqa: E731
    print(
        f"Спирмен r/2r {sp.at['r', 'r2']:.2f}, r/0.5r {sp.at['r', 'r05']:.2f};",
        "совпадение знака r/2r",
        agree("r", "r2"),
        "r/0.5r",
        agree("r", "r05"),
    )

    print("\n## Флаги")
    print("городов с пикселями у предела хранения:", int(t.any_flag_near_cap.sum()))
    ps = t[t.flag_point_source]
    print("точечный источник:", len(ps), ps.lights_class.value_counts().to_dict())
    grow = t[t.lights_class == "растёт"]
    print("«растёт» без точечных источников:", int((~grow.flag_point_source).sum()), "из", len(grow))


if __name__ == "__main__":
    main()
