import json

import numpy as np
import pandas as pd

import citiesneversleep.export as export

YEARS = list(range(2012, 2025))


def test_build_web_export(tmp_path, monkeypatch):
    ids = [f"Q{i}" for i in range(3)]
    lights = pd.DataFrame(
        [
            {"city_id": c, "year": y, "sol": 100.0 * (i + 1) * (1.02 ** (y - 2012)), "sol_r2": 1.0}
            for i, c in enumerate(ids)
            for y in YEARS
        ]
    )
    trends = pd.DataFrame(
        {
            "city_id": ids,
            "name": ["А", "Б", "В"],
            "lat": [55.0, 56.0, np.nan],
            "lon": [37.0, 38.0, np.nan],
            "population_latest": pd.array([1000, 2000, None], dtype="Int64"),
            "brightness_decile": [1, 1, 1],
            "lights_class": ["растёт", "стабилен", "гаснет"],
            "lights_rel_pct_per_year": [0.02, 0.0, np.nan],
            "lights_class_national": ["растёт", "стабилен", "гаснет"],
            "population_class": ["стабилен", "мало данных", "мало данных"],
            "population_pct_per_year": [0.001, np.nan, np.nan],
            "flag_point_source": [True, False, False],
            "any_flag_near_cap": [False, False, False],
            "any_flag_nan": [False, False, True],
        }
    )
    population = pd.DataFrame(
        {"city_id": ["Q0"], "year": [2020], "population": [1000], "is_primary": [True]}
    )
    cities = pd.DataFrame({"city_id": ids, "coverage": ["p17_russia"] * 3})
    for name in ("lights", "trends", "population", "cities"):
        (tmp_path / name).mkdir()
    lights.to_parquet(tmp_path / "lights" / "city_lights.parquet")
    trends.to_parquet(tmp_path / "trends" / "city_trends.parquet")
    (tmp_path / "trends" / "city_trends.meta.json").write_text('{"national_index": {}}')
    population.to_parquet(tmp_path / "population" / "ru_cities_population.parquet")
    cities.to_parquet(tmp_path / "cities" / "ru_cities.parquet")
    monkeypatch.setattr(export, "LIGHTS_PROCESSED_DIR", tmp_path / "lights")
    monkeypatch.setattr(export, "TRENDS_PROCESSED_DIR", tmp_path / "trends")
    monkeypatch.setattr(export, "POP_PROCESSED_DIR", tmp_path / "population")
    monkeypatch.setattr(export, "CITIES_PROCESSED_DIR", tmp_path / "cities")

    out, payload = export.build_web_export(tmp_path / "out")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["years"] == YEARS
    a = data["cities"][0]
    assert a["flags"] == ["point_source"]
    assert len(a["series"]["lights_rel"]) == 13
    assert abs(np.mean(a["series"]["lights_rel"]) - 1) < 1e-2  # среднее города = 1
    assert a["series"]["population"][8] == 1000 and a["series"]["population"][0] is None
    c = data["cities"][2]
    assert c["lat"] is None and c["population"] is None and c["lights_pct"] is None
    assert (tmp_path / "out" / "cities.meta.json").exists()
    assert len(a["yoy"]) == 2 and abs(a["yoy"][0] - np.log(1.02)) < 1e-4
    jump = data["story"]["jump"]["2020_2021"]
    assert abs(jump["median_pct"] - 0.02) < 1e-3 and jump["share_up"] == 1.0
