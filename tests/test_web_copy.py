"""Цифры в тексте витрины совпадают с выгрузками.

Если данные пересобраны, а текст web/src/index.html не обновлён, тест падает
и показывает, какое число разошлось.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "src" / "index.html"
EXPORTS = ROOT / "analytics" / "exports"
PROCESSED = ROOT / "data" / "processed"

pytestmark = pytest.mark.skipif(not PAGE.exists(), reason="витрина не собрана")


def page_text() -> str:
    html = PAGE.read_text(encoding="utf-8")
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", "", html)


def pct(x: float) -> str:
    return f"{round(abs(x) * 100)}%"


@pytest.fixture(scope="module")
def facts() -> dict:
    trends = pd.read_parquet(PROCESSED / "trends" / "city_trends.parquet")
    lights = pd.read_parquet(PROCESSED / "lights" / "city_lights.parquet")
    cities = json.loads((EXPORTS / "cities.json").read_text(encoding="utf-8"))
    meta = json.loads((PROCESSED / "trends" / "city_trends.meta.json").read_text(encoding="utf-8"))
    jump = cities["story"]["jump"]
    cls = trends["lights_class"].value_counts()
    shrinking = trends[trends["population_class"] == "гаснет"]
    v = trends.dropna(subset=["lights_rel_pct_per_year", "population_pct_per_year"])
    rho = (
        v[["lights_rel_pct_per_year", "population_pct_per_year"]].corr(method="spearman").iloc[0, 1]
    )
    names = pd.read_parquet(PROCESSED / "cities" / "ru_cities.parquet")[["city_id", "name"]]
    volzh = lights.merge(names, on="city_id").query("name == 'Волжский'").sort_values("year")
    index = meta["national_index"]
    return {
        "рост индекса": pct(index[max(index)] - 1),
        "доля растущих без поправки": pct((trends["lights_raw_pct_per_year"] > 0).mean()),
        "медиана 2019-2020": pct(jump["2019_2020"]["median_pct"]),
        "медиана 2020-2021": pct(jump["2020_2021"]["median_pct"]),
        "доля растущих 2021": pct(jump["2020_2021"]["share_up"]),
        "светлеют": str(cls["растёт"]),
        "темнеют": str(cls["гаснет"]),
        "на уровне": str(cls["стабилен"]),
        "население сокращается": str(len(shrinking)),
        "из них стабильны": str(int((shrinking["lights_class"] == "стабилен").sum())),
        "корреляция": f"{rho:.2f}".replace(".", ","),
        "точечные источники": str(int(trends["flag_point_source"].sum())),
        "Волжский было": f"{volzh['max_radiance'].iloc[0]:,.0f}".replace(",", " "),
        "Волжский стало": f"{volzh['max_radiance'].iloc[-1]:,.0f}".replace(",", " "),
    }


def test_numbers_on_page_match_data(facts):
    text = page_text()
    missing = {k: v for k, v in facts.items() if v not in text}
    assert not missing, f"числа из данных не найдены в тексте витрины: {missing}"


def test_no_long_dashes_in_copy():
    text = page_text()
    assert "—" not in text, "длинное тире в тексте витрины"
    assert not np.any([s.startswith(" –") for s in text.split("\n")])
