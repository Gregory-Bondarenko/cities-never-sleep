"""Обрезка VNL по России и нормализация шкалы на синтетическом растре."""

from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from citiesneversleep.process.crop import (
    RU_EAST,
    RU_WEST,
    _normalize_radiance,
    crop_file,
    find_raw_for_year,
)

NODATA = -32768
RES = 1.0  # градус на пиксель: глобальный растр 360 × 180


def _write_global(path, value: int = 50) -> None:
    """Глобальный int16-растр в EPSG:4326 с постоянной яркостью и служебными пикселями."""
    data = np.full((180, 360), value, dtype=np.int16)
    data[0, :] = NODATA  # строка 89…90° с. ш.: nodata
    data[1, :] = -5  # строка 88…89° с. ш.: отрицательные значения
    profile = {
        "driver": "GTiff",
        "height": 180,
        "width": 360,
        "count": 1,
        "dtype": "int16",
        "crs": "EPSG:4326",
        "transform": from_origin(-180.0, 90.0, RES, RES),
        "nodata": NODATA,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


@pytest.fixture
def raw_tif(tmp_path):
    path = tmp_path / "raw.tif"
    _write_global(path)
    return path


def _bounds_close(actual, expected) -> bool:
    return all(abs(a - e) < 1e-6 for a, e in zip(actual, expected, strict=True))


def test_crop_writes_west_and_east(raw_tif, tmp_path):
    out_dir = tmp_path / "out"
    primary = crop_file(raw_tif, year=2022, dest_dir=out_dir)

    assert primary.name == "vnl_russia_2022.tif"
    with rasterio.open(primary) as src:
        assert _bounds_close(tuple(src.bounds), RU_WEST)
        assert src.dtypes[0] == "float32"
    with rasterio.open(out_dir / "vnl_russia_2022_east.tif") as src:
        assert _bounds_close(tuple(src.bounds), RU_EAST)


def test_scale_fix_divides_until_2021(raw_tif, tmp_path):
    for year, expected, note in ((2021, 5.0, "divided_by_10"), (2022, 50.0, "raw_nW")):
        out = crop_file(raw_tif, year=year, dest_dir=tmp_path / str(year))
        with rasterio.open(out) as src:
            data = src.read(1)
            tags = src.tags()
        assert np.nanmax(data) == pytest.approx(expected)
        assert tags["scale_note"] == note
        assert tags["year"] == str(year)
        assert tuple(json.loads(tags["bbox"])) == RU_WEST


def test_nodata_and_negative_become_nan(raw_tif, tmp_path):
    out = crop_file(raw_tif, year=2013, dest_dir=tmp_path)
    with rasterio.open(out) as src:
        data = src.read(1)
    # верхняя граница окна 82° с. ш., служебные строки 88–90° в окно не попадают
    assert np.isfinite(data).all()

    raw = np.array([[NODATA, -5, 0, 30]], dtype=np.int16)
    norm, updates = _normalize_radiance(raw, 2013, NODATA)
    assert np.isnan(norm[0, 0]) and np.isnan(norm[0, 1])
    assert norm[0, 2] == 0.0
    assert norm[0, 3] == pytest.approx(3.0)
    assert updates["dtype"] == "float32"


def test_no_scale_fix_keeps_values(raw_tif, tmp_path):
    out = crop_file(raw_tif, year=2013, dest_dir=tmp_path, apply_scale_fix=False)
    with rasterio.open(out) as src:
        assert src.dtypes[0] == "int16"
        assert src.read(1).max() == 50
        assert src.tags()["scale_note"] == "unchanged"


def test_find_raw_for_year(tmp_path):
    name = "nightlights.average_viirs.v21_m_500m_s_20130101_20131231_go_epsg4326_v20250904.tif"
    (tmp_path / name).touch()
    assert find_raw_for_year(2013, raw_dir=tmp_path).name == name
    with pytest.raises(FileNotFoundError, match="2014"):
        find_raw_for_year(2014, raw_dir=tmp_path)
