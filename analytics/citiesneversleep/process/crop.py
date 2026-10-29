"""Обрезка глобальных VNL COG по охвату России (+ окно Чукотки)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.windows import transform as window_transform

from citiesneversleep.paths import VNL_INTERIM_DIR, VNL_RAW_DIR, ensure_data_dirs

# Основной прямоугольник РФ (без Чукотки за 180°)
RU_WEST = (19.0, 41.0, 180.0, 82.0)  # minx, miny, maxx, maxy
# Чукотка к востоку от 180-го меридиана
RU_EAST = (-180.0, 62.0, -168.0, 72.0)

# Шкала ×10 в файлах 2012–2021; с 2022 — исходные нВт (артефакт набора Zenodo).
SCALE_DIVISOR_UNTIL_YEAR = 2021


Bounds = tuple[float, float, float, float]
RussiaWindow = tuple[str, Window, Bounds]


def russia_windows(src: rasterio.DatasetReader) -> list[RussiaWindow]:
    """Окна чтения COG для двух bbox России."""
    out: list[RussiaWindow] = []
    for name, bounds in (("west", RU_WEST), ("east", RU_EAST)):
        win = from_bounds(*bounds, transform=src.transform)
        win = win.intersection(Window(0, 0, src.width, src.height))
        if win.width > 0 and win.height > 0:
            out.append((name, win.round_lengths().round_offsets(), bounds))
    return out


def _normalize_radiance(data: np.ndarray, year: int, nodata) -> tuple[np.ndarray, dict]:
    """Привести к float32 нВт/см²/ср; nodata → NaN."""
    profile_updates = {"dtype": "float32", "nodata": float("nan"), "count": 1}
    out = data.astype(np.float32)
    if nodata is not None:
        out = np.where(data == nodata, np.nan, out)
    out = np.where(data < 0, np.nan, out)
    if year <= SCALE_DIVISOR_UNTIL_YEAR:
        valid = np.isfinite(out) & (out > 0)
        out = out.copy()
        out[valid] = out[valid] / 10.0
        scale_note = "divided_by_10"
    else:
        scale_note = "raw_nW"
    return out, {**profile_updates, "_scale_note": scale_note}


def crop_file(
    src_path: Path,
    *,
    year: int,
    dest_dir: Path | None = None,
    apply_scale_fix: bool = True,
    compress: str = "zstd",
) -> Path:
    """Обрезать один годовой GeoTIFF и сохранить в data/interim/vnl/.

    Основной файл — западный bbox (`vnl_russia_{year}.tif`);
    Чукотка за 180° — `vnl_russia_{year}_east.tif`.
    """
    ensure_data_dirs()
    dest_dir = dest_dir or VNL_INTERIM_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    primary = dest_dir / f"vnl_russia_{year}.tif"

    with rasterio.open(src_path) as src:
        windows = russia_windows(src)
        if not windows:
            raise RuntimeError(f"Нет пересечения с bbox России: {src_path}")

        for name, win, bounds in windows:
            data = src.read(1, window=win, boundless=False)
            profile = src.profile.copy()
            profile.update(
                {
                    "height": int(win.height),
                    "width": int(win.width),
                    "transform": window_transform(win, src.transform),
                    "compress": compress,
                    "tiled": True,
                    "blockxsize": 256,
                    "blockysize": 256,
                    "driver": "GTiff",
                }
            )

            if apply_scale_fix:
                write_data, updates = _normalize_radiance(data, year, src.nodata)
                scale_note = updates.pop("_scale_note")
                profile.update(updates)
            else:
                write_data = data
                scale_note = "unchanged"

            out_path = primary if name == "west" else dest_dir / f"vnl_russia_{year}_{name}.tif"
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(write_data, 1)
                dst.update_tags(
                    source=str(src_path.name),
                    year=str(year),
                    region=name,
                    scale_note=scale_note,
                    bbox=json.dumps(bounds),
                )

    if not primary.exists():
        # только east — маловероятно
        east = dest_dir / f"vnl_russia_{year}_east.tif"
        return east if east.exists() else primary
    return primary


def find_raw_for_year(year: int, raw_dir: Path | None = None) -> Path:
    raw_dir = raw_dir or VNL_RAW_DIR
    pattern = f"nightlights.average_viirs.v21_m_500m_s_{year}0101_{year}1231_*.tif"
    matches = sorted(raw_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"Нет сырого VNL за {year} в {raw_dir}. Сначала: cns fetch-vnl --year {year}"
        )
    return matches[0]


def crop_years(
    years: list[int],
    *,
    raw_dir: Path | None = None,
    dest_dir: Path | None = None,
    apply_scale_fix: bool = True,
) -> list[Path]:
    paths: list[Path] = []
    for year in years:
        src = find_raw_for_year(year, raw_dir=raw_dir)
        paths.append(
            crop_file(
                src,
                year=year,
                dest_dir=dest_dir,
                apply_scale_fix=apply_scale_fix,
            )
        )
    return paths
