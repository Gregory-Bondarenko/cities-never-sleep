import json
from datetime import UTC, datetime

import pytest

from citiesneversleep import __version__
from citiesneversleep.meta import REQUIRED_FIELDS, build_meta, write_meta


def test_build_meta_has_contract_fields():
    meta = build_meta(
        schema_version="1.0.0",
        source="test",
        n_rows=3,
        license_note="CC0",
        built_at=datetime(2026, 10, 30, 8, 0, tzinfo=UTC),
        extra_field=1,
    )
    assert all(f in meta for f in REQUIRED_FIELDS)
    assert meta["built_at"] == "2026-10-30T08:00:00Z"
    assert meta["package_version"] == __version__
    assert meta["extra_field"] == 1


def test_write_meta_rejects_incomplete(tmp_path):
    with pytest.raises(ValueError, match="schema_version"):
        write_meta(tmp_path / "x.meta.json", {"source": "x"})


def test_write_meta_roundtrip(tmp_path):
    meta = build_meta(schema_version="1.0.0", source="s", n_rows=0, license_note="CC0")
    path = write_meta(tmp_path / "x.meta.json", meta)
    assert json.loads(path.read_text(encoding="utf-8")) == meta
