"""Пути к каталогам данных относительно корня репозитория."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"

VNL_RAW_DIR = RAW_DIR / "vnl"
VNL_INTERIM_DIR = INTERIM_DIR / "vnl"
POP_PROCESSED_DIR = PROCESSED_DIR / "population"
CITIES_PROCESSED_DIR = PROCESSED_DIR / "cities"
LIGHTS_PROCESSED_DIR = PROCESSED_DIR / "lights"
TRENDS_PROCESSED_DIR = PROCESSED_DIR / "trends"
EXPORTS_DIR = REPO_ROOT / "analytics" / "exports"


def ensure_data_dirs() -> None:
    for path in (
        VNL_RAW_DIR,
        VNL_INTERIM_DIR,
        POP_PROCESSED_DIR,
        CITIES_PROCESSED_DIR,
        LIGHTS_PROCESSED_DIR,
        TRENDS_PROCESSED_DIR,
        MANUAL_DIR,
        PROCESSED_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
