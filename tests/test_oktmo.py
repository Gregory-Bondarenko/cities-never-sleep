import pandas as pd
import pytest

from citiesneversleep.validate.oktmo import OktmoStatus, add_oktmo_status, normalize_oktmo


@pytest.mark.parametrize(
    ("value", "code", "status"),
    [
        ("01614101001", "01614101001", OktmoStatus.OK),
        (" 01 614-101.001 ", "01614101001", OktmoStatus.OK),
        ("45000000", "45000000", OktmoStatus.SHORT),
        ("019u4y4992", "019u4y4992", OktmoStatus.INVALID),  # реальный случай: Дмитриев
        ("1234", "1234", OktmoStatus.INVALID),
        ("", None, OktmoStatus.MISSING),
        (None, None, OktmoStatus.MISSING),
        (float("nan"), None, OktmoStatus.MISSING),
    ],
)
def test_normalize_oktmo(value, code, status):
    assert normalize_oktmo(value) == (code, status)


def test_add_oktmo_status_keeps_rows():
    df = pd.DataFrame({"oktmo": ["01614101001", "019u4y4992", None]})
    out = add_oktmo_status(df)
    assert len(out) == 3
    assert out["oktmo_status"].tolist() == ["ok", "invalid", "missing"]
    assert "oktmo_status" not in df.columns  # исходная таблица не меняется
