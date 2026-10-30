"""Метаданные артефактов по контракту из docs/architecture.md."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from citiesneversleep import __version__

REQUIRED_FIELDS = (
    "schema_version",
    "source",
    "built_at",
    "package_version",
    "n_rows",
    "license_note",
)


def build_meta(
    *,
    schema_version: str,
    source: str | list[str],
    n_rows: int,
    license_note: str,
    built_at: datetime | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Собрать словарь метаданных с обязательными полями контракта."""
    built = (built_at or datetime.now(UTC)).astimezone(UTC)
    meta: dict[str, Any] = {
        "schema_version": schema_version,
        "source": source,
        "built_at": built.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "package_version": __version__,
        "n_rows": int(n_rows),
        "license_note": license_note,
    }
    meta.update(extra)
    return meta


def write_meta(path: Path, meta: dict[str, Any]) -> Path:
    """Проверить обязательные поля и записать ``*.meta.json``."""
    missing = [f for f in REQUIRED_FIELDS if f not in meta]
    if missing:
        raise ValueError(f"В метаданных нет обязательных полей: {missing}")
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
