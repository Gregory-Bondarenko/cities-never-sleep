"""Загрузчик населения из Wikidata на подменённом HTTP."""

from __future__ import annotations

import json

import httpx
import pytest

from citiesneversleep.sources.wikidata_pop import (
    COLUMNS,
    SCHEMA_VERSION,
    fetch_sparql,
    rows_to_dataframe,
    save_population,
)


def _binding(qid: str, label: str, oktmo: str, pop: str, date: str | None) -> dict:
    b = {
        "city": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
        "cityLabel": {"type": "literal", "value": label},
        "oktmo": {"type": "literal", "value": oktmo},
        "pop": {"type": "literal", "value": pop},
    }
    if date:
        b["date"] = {"type": "literal", "value": date}
    return b


SPARQL_RESPONSE = {
    "head": {"vars": ["city", "cityLabel", "oktmo", "pop", "date"]},
    "results": {
        "bindings": [
            _binding("Q1", "Город А", "01614101001", "11702", "2020-01-01T00:00:00Z"),
            _binding("Q1", "Город А", "01614101001", "11500", "2013-01-01T00:00:00Z"),
            _binding("Q2", "Город Б", "45000000", "не число", "2020-01-01T00:00:00Z"),
            _binding("Q3", "Город В", "71100000001", "500", None),
        ]
    },
}


def _client(responses: list[httpx.Response]) -> httpx.Client:
    queue = iter(responses)
    return httpx.Client(transport=httpx.MockTransport(lambda request: next(queue)))


def test_fetch_sparql_flattens_bindings():
    with _client([httpx.Response(200, json=SPARQL_RESPONSE)]) as client:
        rows = fetch_sparql(client=client)
    assert len(rows) == 4
    assert rows[0]["cityLabel"] == "Город А"
    assert "date" not in rows[3]


def test_fetch_sparql_retries_after_server_error():
    responses = [httpx.Response(503), httpx.Response(200, json=SPARQL_RESPONSE)]
    with _client(responses) as client:
        rows = fetch_sparql(client=client, retries=2)
    assert len(rows) == 4


def test_fetch_sparql_raises_after_retries():
    with _client([httpx.Response(503)] * 2) as client, pytest.raises(httpx.HTTPStatusError):
        fetch_sparql(client=client, retries=2)


def test_rows_to_dataframe():
    with _client([httpx.Response(200, json=SPARQL_RESPONSE)]) as client:
        df = rows_to_dataframe(fetch_sparql(client=client))

    assert set(df["city_id"]) == {"Q1", "Q3"}  # нечисловое население отброшено
    q1 = df[df["city_id"] == "Q1"]
    assert q1["year"].tolist() == [2013, 2020]  # сортировка по году
    assert df.loc[df["city_id"] == "Q3", "year"].isna().all()
    assert list(df.columns) == COLUMNS
    assert set(df["oktmo_status"]) == {"ok"}


def test_rows_to_dataframe_empty():
    df = rows_to_dataframe([])
    assert df.empty
    assert "population" in df.columns


def test_save_population(tmp_path):
    with _client([httpx.Response(200, json=SPARQL_RESPONSE)]) as client:
        df = rows_to_dataframe(fetch_sparql(client=client))
    parquet_path, csv_path = save_population(df, dest_dir=tmp_path)

    assert parquet_path.exists() and csv_path.exists()
    meta = json.loads((tmp_path / "ru_cities_population.meta.json").read_text(encoding="utf-8"))
    assert meta["schema_version"] == SCHEMA_VERSION
    assert meta["n_rows"] == len(df)
    assert meta["n_cities"] == 2
    assert (meta["year_min"], meta["year_max"], meta["n_years"]) == (2013, 2020, 2)
    assert meta["oktmo_status_by_city"] == {"ok": 2}
    assert "built_at" in meta and "package_version" in meta
