"""Зональная статистика ночной освещённости по круговым контурам городов (ADR-0005).

Для каждого города и года считается сумма излучения внутри круга радиуса r,
а также внутри кругов 0,5·r и 2·r для оценки чувствительности к радиусу.

Сумма излучения ``sol`` взвешивается площадью пикселя:
Σ L·A, где L в нВт/см²/ср, A в км². Площадь пикселя в EPSG:4326 убывает
с широтой, поэтому без взвешивания северные города систематически
недооценивались бы.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from citiesneversleep.process.boundaries import BOUNDARY_METHOD, radius_km
from citiesneversleep.process.crop import SCALE_DIVISOR_UNTIL_YEAR

KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQ = 111.320
INT16_MAX = 32767
NEAR_CAP_SHARE = 0.9  # значения выше 90% предела хранения считаются близкими к пределу
NAN_FLAG_SHARE = 0.1
RADIUS_FACTORS = {"r05": 0.5, "r1": 1.0, "r2": 2.0}
SCHEMA_VERSION = "1.0.0"

COLUMNS = [
    "city_id",
    "year",
    "radius_km",
    "sol",
    "sol_r05",
    "sol_r2",
    "lit_area_km2",
    "mean_radiance",
    "max_radiance",
    "n_pixels",
    "share_nan",
    "n_near_cap",
    "flag_nan",
    "flag_near_cap",
]


def storage_cap(year: int) -> float:
    """Предел значения после нормализации: int16 с делением на 10 до 2021 года."""
    return INT16_MAX / 10 if year <= SCALE_DIVISOR_UNTIL_YEAR else float(INT16_MAX)


def circle_window(
    transform: rasterio.Affine, lat: float, lon: float, r_km: float, width: int, height: int
) -> Window | None:
    """Окно растра, покрывающее круг радиуса r_km; None, если круг вне растра."""
    dlat = r_km / KM_PER_DEG_LAT
    dlon = r_km / (KM_PER_DEG_LON_EQ * max(math.cos(math.radians(lat)), 1e-6))
    inv = ~transform
    col0, row0 = inv @ (lon - dlon, lat + dlat)
    col1, row1 = inv @ (lon + dlon, lat - dlat)
    c0, r0 = max(int(math.floor(col0)), 0), max(int(math.floor(row0)), 0)
    c1, r1 = min(int(math.ceil(col1)), width), min(int(math.ceil(row1)), height)
    if c1 <= c0 or r1 <= r0:
        return None
    return Window(c0, r0, c1 - c0, r1 - r0)


def _pixel_geometry(transform, window: Window, lat0: float, lon0: float):
    """Расстояние от центра города до центров пикселей (км) и площадь пикселей (км²)."""
    rows = np.arange(window.row_off, window.row_off + window.height) + 0.5
    cols = np.arange(window.col_off, window.col_off + window.width) + 0.5
    lons = transform.c + cols * transform.a
    lats = transform.f + rows * transform.e
    lon_g, lat_g = np.meshgrid(lons, lats)
    coslat = np.cos(np.radians(lat_g))
    dx = (lon_g - lon0) * KM_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
    dy = (lat_g - lat0) * KM_PER_DEG_LAT
    dist = np.hypot(dx, dy)
    area = abs(transform.a) * KM_PER_DEG_LON_EQ * coslat * abs(transform.e) * KM_PER_DEG_LAT
    return dist, area


def city_stats(
    data: np.ndarray, dist: np.ndarray, area: np.ndarray, r_km: float, year: int
) -> dict:
    """Статистика по кругам 0,5·r, r, 2·r для одного города и года."""
    out: dict = {}
    for key, factor in RADIUS_FACTORS.items():
        inside = dist <= r_km * factor
        vals = data[inside]
        valid = np.isfinite(vals)
        sol = float(np.sum(vals[valid] * area[inside][valid]))
        out[{"r05": "sol_r05", "r1": "sol", "r2": "sol_r2"}[key]] = sol
        if key == "r1":
            n = int(inside.sum())
            lit = valid & (vals > 0)
            valid_area = float(area[inside][valid].sum())
            cap = storage_cap(year)
            n_near = int(np.sum(vals[valid] >= NEAR_CAP_SHARE * cap))
            share_nan = 1 - valid.sum() / n if n else 1.0
            out.update(
                n_pixels=n,
                lit_area_km2=float(area[inside][lit].sum()),
                mean_radiance=sol / valid_area if valid_area else float("nan"),
                max_radiance=float(vals[valid].max()) if valid.any() else float("nan"),
                share_nan=float(share_nan),
                n_near_cap=n_near,
                flag_nan=bool(share_nan > NAN_FLAG_SHARE),
                flag_near_cap=bool(n_near > 0),
            )
    return out


def zonal_for_year(raster_path: Path, cities: pd.DataFrame, year: int) -> pd.DataFrame:
    """Статистика по всем городам за один год из обрезанного растра."""
    radii = radius_km(cities["population_latest"])
    rows: list[dict] = []
    with rasterio.open(raster_path) as src:
        for (_, city), r in zip(cities.iterrows(), radii, strict=True):
            base = {"city_id": city["city_id"], "year": year, "radius_km": float(r)}
            if pd.isna(city["lat"]) or pd.isna(city["lon"]):
                rows.append(base)
                continue
            r_max = r * max(RADIUS_FACTORS.values())
            win = circle_window(
                src.transform, city["lat"], city["lon"], r_max, src.width, src.height
            )
            if win is None:
                rows.append(base)
                continue
            data = src.read(1, window=win).astype("float32")
            if src.nodata is not None and not np.isnan(src.nodata):
                data[data == src.nodata] = np.nan
            dist, area = _pixel_geometry(src.transform, win, city["lat"], city["lon"])
            rows.append({**base, **city_stats(data, dist, area, float(r), year)})
    df = pd.DataFrame(rows).reindex(columns=COLUMNS)
    df["year"] = df["year"].astype("int64")
    return df


def lights_meta_extra() -> dict:
    return {
        "boundary_method": BOUNDARY_METHOD,
        "radius_rule": "r = clip(1,5·√(N/10 000), 3, 30) км, N = population_latest (ADR-0005)",
        "sol_definition": "Σ L·A внутри круга, L в нВт/см²/ср, A площадь пикселя в км²",
        "near_cap_rule": f"L ≥ {NEAR_CAP_SHARE}·предел хранения (int16, /10 до "
        f"{SCALE_DIVISOR_UNTIL_YEAR})",
    }


def build_city_lights(
    years: list[int],
    *,
    cities_path: Path | None = None,
    interim_dir: Path | None = None,
    dest_dir: Path | None = None,
) -> tuple[Path, pd.DataFrame]:
    """Собрать набор ``lights/city_lights`` по обрезанным растрам за указанные годы."""
    from citiesneversleep.meta import build_meta, write_meta
    from citiesneversleep.paths import CITIES_PROCESSED_DIR, LIGHTS_PROCESSED_DIR, VNL_INTERIM_DIR

    cities = pd.read_parquet(cities_path or CITIES_PROCESSED_DIR / "ru_cities.parquet")
    interim_dir = interim_dir or VNL_INTERIM_DIR
    frames = []
    for year in years:
        path = interim_dir / f"vnl_russia_{year}.tif"
        if not path.exists():
            raise FileNotFoundError(f"Нет {path}. Сначала: cns process-vnl --year {year}")
        frames.append(zonal_for_year(path, cities, year))
    df = pd.concat(frames, ignore_index=True).sort_values(["city_id", "year"])
    df = df.reset_index(drop=True)

    dest_dir = dest_dir or LIGHTS_PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "city_lights.parquet"
    df.to_parquet(out, index=False)
    df.to_csv(dest_dir / "city_lights.csv", index=False)
    meta = build_meta(
        schema_version=SCHEMA_VERSION,
        source=["VNL V2.1 OpenGeoHub (Zenodo 17294744)", "cities/ru_cities"],
        n_rows=len(df),
        license_note="VNL: CC-BY 4.0; Wikidata: CC0",
        years=years,
        n_cities=int(df["city_id"].nunique()),
        n_flag_nan=int(df["flag_nan"].fillna(False).sum()),
        n_flag_near_cap=int(df["flag_near_cap"].fillna(False).sum()),
        **lights_meta_extra(),
    )
    write_meta(dest_dir / "city_lights.meta.json", meta)
    return out, df
