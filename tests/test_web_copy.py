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
    cities = json.loads((EXPORTS / "cities.json").read_text(encoding="utf-8"))
    jump = cities["story"]["jump"]
    cls = trends["lights_class"].value_counts()
    v = trends.dropna(subset=["lights_rel_pct_per_year", "population_pct_per_year"])
    rho = (
        v[["lights_rel_pct_per_year", "population_pct_per_year"]].corr(method="spearman").iloc[0, 1]
    )
    q = cities["story"]["quadrants"]
    caps = cities["story"]["capitals"]
    return {
        "медиана 2019-2020": pct(jump["2019_2020"]["median_pct"]),
        "медиана 2020-2021": pct(jump["2020_2021"]["median_pct"]),
        "доля растущих 2021": pct(jump["2020_2021"]["share_up"]),
        "городов в выборке": f"{len(cities['cities']):,}".replace(",", " "),
        "светлеют": str(cls["растёт"]),
        "темнеют": str(cls["гаснет"]),
        "на уровне": str(cls["стабилен"]),
        "корреляция": f"{rho:.2f}".replace(".", ","),
        "гаснут вместе с жителями": str(q["lights_down_people_down"]),
        "светлеют при оттоке": str(q["lights_up_people_down"]),
        "обратные случаи": str(q["lights_down_people_up"]),
        "столиц республик": str(caps["republics"]["n"]),
        "из них светлеют": str(caps["republics"]["up"]),
        "центров остальных": str(caps["other"]["n"]),
        "из них светлеют ": str(caps["other"]["up"]),
        "из них темнеют": str(caps["other"]["down"]),
    }


CAUCASUS = {
    "Чечня",
    "Дагестан",
    "Ингушетия",
    "Ставропольский край",
    "Кабардино-Балкария",
    "Карачаево-Черкесия",
    "Северная Осетия",
    "Адыгея",
}


def test_claims_in_headings_match_data():
    """Утверждения в заголовках, которые не подставляются из данных."""
    data = json.loads((EXPORTS / "cities.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in data["cities"]}
    text = page_text()
    if "и только одна темнеет" in text:
        assert data["story"]["capitals"]["republics"]["down"] == 1
    if "Крым и Кавказ" in text or "Крым, Кавказ" in text:
        regions = [by_id[i]["region"] for i in data["story"]["highlights"]["rising"]]
        assert sum(r in ("Республика Крым", "Севастополь") for r in regions) >= 2
        assert sum(r in CAUCASUS for r in regions) >= 2
    html = PAGE.read_text(encoding="utf-8")
    if "включая Москву и Санкт-Петербург" in html:
        for name in ("Москва", "Санкт-Петербург"):
            city = next(c for c in data["cities"] if c["name"] == name)
            assert city["lights_class"] == "стабилен", name


def test_numbers_on_page_match_data(facts):
    text = page_text()
    missing = {k: v for k, v in facts.items() if v not in text}
    assert not missing, f"числа из данных не найдены в тексте витрины: {missing}"


def test_no_long_dashes_in_copy():
    text = page_text()
    assert "—" not in text, "длинное тире в тексте витрины"
    assert not np.any([s.startswith(" –") for s in text.split("\n")])
