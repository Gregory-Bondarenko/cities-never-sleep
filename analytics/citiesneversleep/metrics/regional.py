"""Региональная составляющая межгодовых колебаний яркости (ADR-0010).

Относительные ряды (к индексу децили яркости, ADR-0008) сохраняют
региональные колебания: в отдельные годы соседние города синхронно
светлеют или тускнеют на десятки процентов. Узор колебаний повторяется
от года к году (2014, 2018, 2021, 2022), что может свидетельствовать о
внешней причине, общей для региона: снежный покров, облачность, обработка
годовых композитов.

Метод:

1. Для городов с полным положительным рядом берутся годовые приращения
   логарифма относительного ряда.
2. Приращения сглаживаются по пространству гауссовым ядром (по умолчанию
   400 км) без вклада самого города, чтобы собственная динамика города не
   попадала в региональную оценку.
3. Матрица сглаженных полей «годы × города» раскладывается по сингулярным
   векторам; первая компонента даёт пространственный узор и амплитуду
   по годам.
4. Приращение «амплитуда × узор» вычитается из ряда каждого города;
   узор для городов вне выборки интерполируется тем же ядром.

Удаляется только первая компонента. Если сумма амплитуд за период близка
к нулю, компонента не меняет накопленную динамику и снижает шум.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BANDWIDTH_KM = 400.0
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class RegionalMode:
    years: list[int]  # годы приращений (со второго года ряда)
    amplitude: np.ndarray  # амплитуда по годам, в единицах ln
    explained: float  # доля дисперсии сглаженных полей, объяснённая компонентой
    n_cities: int  # городов в оценке

    @property
    def cumulative(self) -> float:
        """Сумма амплитуд за период: накопленный вклад компоненты."""
        return float(self.amplitude.sum())


def _distances(lat_a, lon_a, lat_b, lon_b) -> np.ndarray:
    la, lo = np.radians(np.asarray(lat_a, float)), np.radians(np.asarray(lon_a, float))
    lb, lob = np.radians(np.asarray(lat_b, float)), np.radians(np.asarray(lon_b, float))
    cos = np.sin(la)[:, None] * np.sin(lb)[None] + np.cos(la)[:, None] * np.cos(lb)[None] * np.cos(
        lo[:, None] - lob[None]
    )
    return EARTH_RADIUS_KM * np.arccos(np.clip(cos, -1.0, 1.0))


def _kernel(dist: np.ndarray, bandwidth_km: float) -> np.ndarray:
    w = np.exp(-0.5 * (dist / bandwidth_km) ** 2)
    s = w.sum(axis=1, keepdims=True)
    return np.divide(w, s, out=np.zeros_like(w), where=s > 0)


def fit_regional_mode(
    log_rel: pd.DataFrame,
    coords: pd.DataFrame,
    bandwidth_km: float = BANDWIDTH_KM,
) -> tuple[RegionalMode, pd.Series]:
    """Оценить первую региональную компоненту.

    ``log_rel``: города × годы, логарифм относительного ряда без пропусков.
    ``coords``: индекс city_id, столбцы ``lat``, ``lon``.
    Возвращает компоненту и узор для городов выборки (норма узора 1 на город
    в смысле среднеквадратичного значения, амплитуда в единицах ln).
    """
    ids = log_rel.index.intersection(coords.dropna(subset=["lat", "lon"]).index)
    log_rel = log_rel.loc[ids]
    c = coords.loc[ids]
    x = np.diff(log_rel.to_numpy(float), axis=1).T  # годы × города
    x = x - np.median(x, axis=1, keepdims=True)
    dist = _distances(c["lat"], c["lon"], c["lat"], c["lon"])
    np.fill_diagonal(dist, np.inf)  # без вклада самого города
    fields = x @ _kernel(dist, bandwidth_km).T
    u, s, vt = np.linalg.svd(fields, full_matrices=False)
    pattern = vt[0]
    scale = np.sqrt(np.mean(pattern**2))
    pattern = pattern / scale
    amplitude = u[:, 0] * s[0] * scale
    # знак: положительная амплитуда означает посветление там, где узор > 0
    mode = RegionalMode(
        years=[int(y) for y in log_rel.columns[1:]],
        amplitude=amplitude,
        explained=float(s[0] ** 2 / np.sum(s**2)),
        n_cities=len(ids),
    )
    return mode, pd.Series(pattern, index=ids, name="regional_pattern")


def interpolate_pattern(
    pattern: pd.Series,
    coords: pd.DataFrame,
    targets: pd.Index,
    bandwidth_km: float = BANDWIDTH_KM,
) -> pd.Series:
    """Узор в точках ``targets``: города выборки берут своё значение, прочие ядро."""
    out = pd.Series(np.nan, index=targets, name="regional_pattern")
    inside = targets.intersection(pattern.index)
    out.loc[inside] = pattern.loc[inside]
    rest = targets.difference(pattern.index)
    rest = rest[coords.reindex(rest)[["lat", "lon"]].notna().all(axis=1).to_numpy()]
    if len(rest):
        src = coords.loc[pattern.index]
        dst = coords.loc[rest]
        w = _kernel(_distances(dst["lat"], dst["lon"], src["lat"], src["lon"]), bandwidth_km)
        out.loc[rest] = w @ pattern.to_numpy(float)
    return out


def regional_adjustment(
    lights: pd.DataFrame,
    rel_column: str,
    coords: pd.DataFrame,
    exclude: pd.Index | None = None,
    bandwidth_km: float = BANDWIDTH_KM,
) -> tuple[pd.Series, RegionalMode]:
    """Множитель поправки для каждой строки ``lights`` и оценённая компонента.

    Скорректированный ряд: ``lights[rel_column] * множитель``. ``exclude``:
    города, не участвующие в оценке (точечные источники); поправка к ним
    всё равно применяется. Города без координат получают множитель 1.
    """
    years = sorted(int(y) for y in lights["year"].unique())
    wide = lights.pivot(index="city_id", columns="year", values=rel_column).reindex(columns=years)
    full = wide[(wide > 0).all(axis=1)]
    if exclude is not None:
        full = full.drop(index=full.index.intersection(exclude))
    mode, pattern = fit_regional_mode(np.log(full.astype(float)), coords, bandwidth_km)
    pat = interpolate_pattern(pattern, coords, wide.index, bandwidth_km).fillna(0.0)
    cum = np.concatenate([[0.0], np.cumsum(mode.amplitude)])
    cum_by_year = dict(zip(years, cum, strict=True))
    shift = lights["city_id"].map(pat).fillna(0.0).to_numpy(float) * lights["year"].map(
        cum_by_year
    ).to_numpy(float)
    return pd.Series(np.exp(-shift), index=lights.index, name="regional_factor"), mode
