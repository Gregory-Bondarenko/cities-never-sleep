"""Нормализация и проверка кодов ОКТМО.

Допустимые формы кода:

* 11 цифр: населённый пункт или поселение (основной случай для городов);
* 8 цифр: муниципальное образование верхнего уровня; так кодируются
  Москва (45000000) и Санкт-Петербург (40000000).

Некорректные коды не отбрасываются, а помечаются статусом ``invalid``:
город остаётся в выборке, ключом служит ``city_id``.
"""

from __future__ import annotations

import re
from enum import StrEnum

import pandas as pd

_DIGITS_ONLY = re.compile(r"\d+")
_SEPARATORS = re.compile(r"[\s\-.]")


class OktmoStatus(StrEnum):
    OK = "ok"  # 11 цифр
    SHORT = "short"  # 8 цифр, верхний уровень
    INVALID = "invalid"  # иное
    MISSING = "missing"  # пусто


def normalize_oktmo(value: object) -> tuple[str | None, OktmoStatus]:
    """Вернуть нормализованный код и его статус.

    Убираются пробелы, дефисы и точки. Код с иными символами или иной длины
    считается некорректным и возвращается как есть для разбора вручную.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, OktmoStatus.MISSING
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "<na>"}:
        return None, OktmoStatus.MISSING
    code = _SEPARATORS.sub("", raw)
    if not _DIGITS_ONLY.fullmatch(code):
        return raw, OktmoStatus.INVALID
    if len(code) == 11:
        return code, OktmoStatus.OK
    if len(code) == 8:
        return code, OktmoStatus.SHORT
    return raw, OktmoStatus.INVALID


def add_oktmo_status(df: pd.DataFrame, column: str = "oktmo") -> pd.DataFrame:
    """Нормализовать столбец ОКТМО и добавить столбец ``oktmo_status``."""
    out = df.copy()
    pairs = [normalize_oktmo(v) for v in out[column]]
    out[column] = pd.Series([p[0] for p in pairs], index=out.index, dtype="string")
    out["oktmo_status"] = pd.Series([str(p[1]) for p in pairs], index=out.index, dtype="string")
    return out
