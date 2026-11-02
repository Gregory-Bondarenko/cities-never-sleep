"""Выгрузка для витрины: один JSON с городами, классами и рядами (ADR-0001).

Витрина ничего не пересчитывает: относительный ряд яркости, классы и флаги
берутся отсюда как есть.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from citiesneversleep.meta import build_meta, write_meta
from citiesneversleep.metrics.trends import brightness_strata, relative_series
from citiesneversleep.paths import (
    CITIES_PROCESSED_DIR,
    EXPORTS_DIR,
    LIGHTS_PROCESSED_DIR,
    POP_PROCESSED_DIR,
    TRENDS_PROCESSED_DIR,
)

SCHEMA_VERSION = "1.1.0"
# Пары лет для главы о скачке 2021 года: обычный год и год скачка.
JUMP_PAIRS = ((2019, 2020), (2020, 2021))


def _num(x, digits: int = 4):
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), digits)


def year_over_year(sol: pd.DataFrame, pairs=JUMP_PAIRS) -> pd.DataFrame:
    """ln(sol_b / sol_a) по городам для пар лет; нули и пропуски дают NaN."""
    out = {}
    for a, b in pairs:
        va, vb = sol[a], sol[b]
        ok = (va > 0) & (vb > 0)
        out[f"{a}_{b}"] = np.where(ok, np.log(vb.where(ok) / va.where(ok)), np.nan)
    return pd.DataFrame(out, index=sol.index)


def jump_summary(yoy: pd.DataFrame) -> dict:
    """Медианное изменение и доля растущих городов для каждой пары лет."""
    res = {}
    for col in yoy.columns:
        v = yoy[col].dropna()
        res[col] = {
            "median_pct": round(float(np.expm1(v.median())), 4),
            "share_up": round(float((v > 0).mean()), 4),
            "n": int(len(v)),
        }
    return res


def build_web_export(dest_dir: Path | None = None) -> tuple[Path, dict]:
    lights = pd.read_parquet(LIGHTS_PROCESSED_DIR / "city_lights.parquet")
    trends = pd.read_parquet(TRENDS_PROCESSED_DIR / "city_trends.parquet")
    population = pd.read_parquet(POP_PROCESSED_DIR / "ru_cities_population.parquet")
    cities = pd.read_parquet(CITIES_PROCESSED_DIR / "ru_cities.parquet")

    years = sorted(int(y) for y in lights["year"].unique())
    strata = brightness_strata(lights)
    lights = lights.assign(sol_rel=relative_series(lights, "sol", strata))
    # относительный ряд нормируется на среднее города, чтобы линии были сопоставимы
    lights["rel_norm"] = lights["sol_rel"] / lights.groupby("city_id")["sol_rel"].transform("mean")
    rel = lights.pivot(index="city_id", columns="year", values="rel_norm").reindex(columns=years)
    sol = lights.pivot(index="city_id", columns="year", values="sol").reindex(columns=years)
    pop = (
        population[population["is_primary"] & population["year"].between(years[0], years[-1])]
        .pivot(index="city_id", columns="year", values="population")
        .reindex(columns=years)
    )
    coverage = cities.set_index("city_id")["coverage"]
    yoy = year_over_year(sol)

    out_cities = []
    for _, r in trends.sort_values("city_id").iterrows():
        cid = r["city_id"]
        out_cities.append(
            {
                "id": cid,
                "name": r["name"],
                "lat": _num(r["lat"], 5),
                "lon": _num(r["lon"], 5),
                "population": None
                if pd.isna(r["population_latest"])
                else int(r["population_latest"]),
                "coverage": coverage.get(cid),
                "decile": int(r["brightness_decile"]),
                "lights_class": r["lights_class"],
                "lights_pct": _num(r["lights_rel_pct_per_year"]),
                "lights_class_national": r["lights_class_national"],
                "population_class": r["population_class"],
                "population_pct": _num(r["population_pct_per_year"]),
                "flags": [
                    name
                    for name, on in (
                        ("point_source", r["flag_point_source"]),
                        ("near_cap", r["any_flag_near_cap"]),
                        ("nan", r["any_flag_nan"]),
                    )
                    if bool(on)
                ],
                "yoy": [_num(v) for v in yoy.loc[cid]] if cid in yoy.index else None,
                "series": {
                    "lights_rel": [_num(v, 3) for v in rel.loc[cid]] if cid in rel.index else None,
                    "sol": [_num(v, 1) for v in sol.loc[cid]] if cid in sol.index else None,
                    "population": [None if pd.isna(v) else int(v) for v in pop.loc[cid]]
                    if cid in pop.index
                    else None,
                },
            }
        )

    trends_meta = json.loads(
        (TRENDS_PROCESSED_DIR / "city_trends.meta.json").read_text(encoding="utf-8")
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "years": years,
        "national_index": trends_meta.get("national_index"),
        "story": {"jump_pairs": [f"{a}_{b}" for a, b in JUMP_PAIRS], "jump": jump_summary(yoy)},
        "cities": out_cities,
    }
    dest_dir = dest_dir or EXPORTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "cities.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_meta(
        dest_dir / "cities.meta.json",
        build_meta(
            schema_version=SCHEMA_VERSION,
            source=["trends/city_trends", "lights/city_lights", "population", "cities"],
            n_rows=len(out_cities),
            license_note="VNL: CC-BY 4.0; Wikidata: CC0",
            size_bytes=out.stat().st_size,
            lights_rel_note="сумма излучения к индексу децили яркости, среднее города = 1",
        ),
    )
    return out, payload
