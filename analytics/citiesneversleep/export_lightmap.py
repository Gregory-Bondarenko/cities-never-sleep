"""Ночной снимок для витрины: обрезанный растр VNL, уменьшенный максимумом по блокам.

Максимум, а не среднее, сохраняет видимость небольших городов при уменьшении
в 10 раз (около 4,6 км на пиксель). Яркость переводится в логарифмическую
шкалу и сохраняется в 8-битный PNG в проекции EPSG:4326; витрина натягивает
его на ту же сетку, что и столбы городов (ADR-0001: витрина ничего не считает).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from citiesneversleep.meta import build_meta, write_meta
from citiesneversleep.metrics.zonal import HARMONIZED_CAP
from citiesneversleep.paths import EXPORTS_DIR, VNL_INTERIM_DIR

SCHEMA_VERSION = "1.0.0"
FACTOR = 10
DISPLAY_MAX = 120.0  # нВт/см²/ср: выше этого значения пиксель полностью белый
STRIP_ROWS = 400  # строк растра за одно чтение, кратно FACTOR


def block_max(data: np.ndarray, factor: int) -> np.ndarray:
    """Максимум по блокам factor × factor; хвосты, не кратные factor, отбрасываются."""
    h, w = (data.shape[0] // factor) * factor, (data.shape[1] // factor) * factor
    d = np.nan_to_num(data[:h, :w], nan=0.0)
    return d.reshape(h // factor, factor, w // factor, factor).max(axis=(1, 3))


def to_uint8(values: np.ndarray) -> np.ndarray:
    """Логарифмическая шкала 0…DISPLAY_MAX → 0…255."""
    v = np.clip(values, 0, min(DISPLAY_MAX, HARMONIZED_CAP))
    scaled = np.log1p(v) / np.log1p(DISPLAY_MAX)
    return np.round(scaled * 255).astype(np.uint8)


def build_lightmap(year: int, dest_dir: Path | None = None, interim_dir: Path | None = None):
    src_path = (interim_dir or VNL_INTERIM_DIR) / f"vnl_russia_{year}.tif"
    if not src_path.exists():
        raise FileNotFoundError(f"Нет {src_path}. Сначала: cns process-vnl --year {year}")
    with rasterio.open(src_path) as src:
        rows = (src.height // FACTOR) * FACTOR
        strips = []
        for r0 in range(0, rows, STRIP_ROWS):
            n = min(STRIP_ROWS, rows - r0)
            window = rasterio.windows.Window(0, r0, src.width, n)
            strips.append(block_max(src.read(1, window=window).astype("float32"), FACTOR))
        small = np.vstack(strips)
        b = src.bounds
        res_x, res_y = src.transform.a * FACTOR, -src.transform.e * FACTOR
    img = to_uint8(small)

    dest_dir = dest_dir or EXPORTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"lightmap_{year}.png"
    profile = {
        "driver": "PNG",
        "dtype": "uint8",
        "count": 1,
        "height": img.shape[0],
        "width": img.shape[1],
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(img, 1)
    for aux in dest_dir.glob(f"lightmap_{year}.png.aux.xml"):
        aux.unlink()
    write_meta(
        dest_dir / f"lightmap_{year}.meta.json",
        build_meta(
            schema_version=SCHEMA_VERSION,
            source="VNL V2.1 OpenGeoHub (Zenodo 17294744)",
            n_rows=int(img.shape[0]),
            license_note="VNL: CC-BY 4.0",
            year=year,
            width=int(img.shape[1]),
            height=int(img.shape[0]),
            bounds={
                "west": b.left,
                "south": b.top - res_y * img.shape[0],
                "east": b.left + res_x * img.shape[1],
                "north": b.top,
            },
            crs="EPSG:4326",
            downsample=f"максимум по блокам {FACTOR}×{FACTOR}",
            scale=f"log1p(min(L, {DISPLAY_MAX})) / log1p({DISPLAY_MAX}) · 255",
        ),
    )
    return out, img
