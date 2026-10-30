"""Контуры городов первой версии: круг вокруг координаты (ADR-0005)."""

from __future__ import annotations

import numpy as np
import pandas as pd

BOUNDARY_METHOD = "circle_v1"
R_COEF_KM = 1.5
R_REF_POP = 10_000
R_MIN_KM = 3.0
R_MAX_KM = 30.0


def radius_km(population: pd.Series | float) -> pd.Series | float:
    """r = clip(1,5 · √(N / 10 000), 3, 30) км; без населения берётся нижняя граница."""
    is_series = isinstance(population, pd.Series)
    pop = pd.to_numeric(population if is_series else pd.Series([population]), errors="coerce")
    pop = pop.astype("float64")
    r = R_COEF_KM * np.sqrt(pop / R_REF_POP)
    r = r.fillna(R_MIN_KM).clip(R_MIN_KM, R_MAX_KM)
    return r if is_series else float(r.iloc[0])
