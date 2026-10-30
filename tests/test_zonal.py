"""Зональная статистика на синтетическом растре 1/240° вокруг 55,75° с. ш."""

import math

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from citiesneversleep.metrics.zonal import (
    COLUMNS,
    build_city_lights,
    storage_cap,
    zonal_for_year,
)

RES = 1 / 240
LAT0, LON0 = 55.75, 37.6


def _write(path, data):
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(37.0, 56.5, RES, RES),
        "nodata": float("nan"),
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


@pytest.fixture
def cities():
    return pd.DataFrame(
        {
            "city_id": ["Q1", "Q2", "Q3"],
            "lat": [LAT0, LAT0, 10.0],
            "lon": [LON0, LON0, 10.0],
            "population_latest": pd.array([10_000, 1_000_000, 10_000], dtype="Int64"),
        }
    )


def test_uniform_field_gives_circle_area(tmp_path, cities):
    path = tmp_path / "vnl_russia_2022.tif"
    _write(path, np.full((360, 480), 10.0))
    df = zonal_for_year(path, cities, 2022).set_index("city_id")

    q1 = df.loc["Q1"]
    assert q1["radius_km"] == pytest.approx(3.0)
    assert q1["sol"] == pytest.approx(10 * math.pi * 9, rel=0.05)
    assert q1["sol_r2"] / q1["sol"] == pytest.approx(4, rel=0.05)
    assert q1["sol_r05"] / q1["sol"] == pytest.approx(0.25, rel=0.1)
    assert q1["mean_radiance"] == pytest.approx(10, rel=1e-3)
    assert q1["lit_area_km2"] == pytest.approx(math.pi * 9, rel=0.05)
    assert not q1["flag_nan"] and not q1["flag_near_cap"]

    q2 = df.loc["Q2"]
    assert q2["radius_km"] == pytest.approx(15.0)
    assert q2["sol"] == pytest.approx(10 * math.pi * 225, rel=0.03)

    assert pd.isna(df.loc["Q3", "sol"])  # вне растра


def test_nan_share_and_near_cap(tmp_path, cities):
    data = np.full((360, 480), 5.0)
    center_col = round((LON0 - 37.0) / RES)  # 144
    data[:, :center_col] = np.nan  # западная половина круга
    data[180, center_col + 6] = 3300.0  # в 1,5 км к востоку, выше 90% предела 2013 года
    path = tmp_path / "vnl_russia_2013.tif"
    _write(path, data)
    q1 = zonal_for_year(path, cities.iloc[:1], 2013).iloc[0]
    assert 0.4 < q1["share_nan"] < 0.6
    assert q1["flag_nan"]
    assert q1["n_near_cap"] == 1 and q1["flag_near_cap"]
    assert q1["max_radiance"] == pytest.approx(3300.0)
    assert q1["sol_unclipped"] > q1["sol"]  # яркий пиксель обрезан общим порогом


def test_storage_cap():
    assert storage_cap(2021) == pytest.approx(3276.7)
    assert storage_cap(2022) == 32767


def test_build_city_lights(tmp_path, cities):
    interim = tmp_path / "interim"
    interim.mkdir()
    for year in (2013, 2022):
        _write(interim / f"vnl_russia_{year}.tif", np.full((360, 480), 1.0))
    cities_path = tmp_path / "cities.parquet"
    cities.to_parquet(cities_path)

    out, df = build_city_lights(
        [2013, 2022], cities_path=cities_path, interim_dir=interim, dest_dir=tmp_path / "out"
    )
    assert list(df.columns) == COLUMNS
    assert len(df) == 6
    assert (tmp_path / "out" / "city_lights.meta.json").exists()
    with pytest.raises(FileNotFoundError):
        build_city_lights([2014], cities_path=cities_path, interim_dir=interim)
