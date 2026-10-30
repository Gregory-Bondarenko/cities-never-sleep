"""Население городов РФ с ОКТМО из Wikidata (SPARQL)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from citiesneversleep import __version__
from citiesneversleep.meta import build_meta, write_meta
from citiesneversleep.paths import POP_PROCESSED_DIR, ensure_data_dirs
from citiesneversleep.validate.oktmo import add_oktmo_status

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    f"CitiesNeverSleep/{__version__} "
    "(https://github.com/Gregory-Bondarenko/cities-never-sleep; educational)"
)

# Запрос из плана: города РФ с ОКТМО и рядом населения
SPARQL_QUERY_PLAN = """
SELECT ?city ?cityLabel ?oktmo ?pop ?date WHERE {
  ?city wdt:P31 wd:Q7930989 ;
        wdt:P17 wd:Q159 ;
        wdt:P764 ?oktmo ;
        p:P1082 ?popStmt .
  ?popStmt ps:P1082 ?pop .
  OPTIONAL { ?popStmt pq:P585 ?date . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". }
}
"""


def fetch_sparql(
    query: str = SPARQL_QUERY_PLAN,
    *,
    client: httpx.Client | None = None,
    timeout: float = 180.0,
    retries: int = 4,
) -> list[dict]:
    """Выполнить SPARQL (POST) и вернуть список bindings как словари."""
    own = client is None
    client = client or httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        follow_redirects=True,
    )
    last_exc: Exception | None = None
    try:
        for attempt in range(retries):
            try:
                resp = client.post(
                    WIKIDATA_SPARQL,
                    data={"query": query, "format": "json"},
                )
                resp.raise_for_status()
                bindings = resp.json()["results"]["bindings"]
                rows: list[dict] = []
                for b in bindings:
                    rows.append({k: v.get("value") for k, v in b.items()})
                return rows
            except (httpx.HTTPError, httpx.RemoteProtocolError, ValueError) as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc
    finally:
        if own:
            client.close()


COLUMNS = ["city_id", "name", "oktmo", "oktmo_status", "population", "date", "year"]
SCHEMA_VERSION = "1.0.0"
LICENSE_NOTE = "Wikidata: CC0; значения населения происходят из бюллетеней Росстата"


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Привести ответ SPARQL к схеме набора ``population`` (см. docs/architecture.md).

    Ключ города ``city_id`` равен идентификатору Wikidata. ОКТМО нормализуется,
    его корректность отражается в ``oktmo_status``; строки с некорректным кодом
    не отбрасываются.
    """
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    df = df.rename(columns={"city": "city_id", "cityLabel": "name", "pop": "population"})
    df["city_id"] = df["city_id"].str.replace(
        "http://www.wikidata.org/entity/", "", regex=False
    )
    df = add_oktmo_status(df)
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        df["year"] = df["date"].dt.year.astype("Int64")
    else:
        df["date"] = pd.NaT
        df["year"] = pd.Series([pd.NA] * len(df), dtype="Int64")
    df = df.dropna(subset=["population"])
    df = df.sort_values(["city_id", "year", "population"], na_position="last")
    return df[COLUMNS].reset_index(drop=True)


def population_meta(df: pd.DataFrame, *, fetched_at: str | None = None) -> dict:
    """Метаданные набора по контракту артефактов."""
    years = df["year"].dropna()
    status_counts = (
        df.drop_duplicates("city_id")["oktmo_status"].value_counts().sort_index().to_dict()
        if len(df)
        else {}
    )
    return build_meta(
        schema_version=SCHEMA_VERSION,
        source="Wikidata SPARQL",
        n_rows=len(df),
        license_note=LICENSE_NOTE,
        endpoint=WIKIDATA_SPARQL,
        fetched_at=fetched_at,
        n_cities=int(df["city_id"].nunique()) if len(df) else 0,
        year_min=int(years.min()) if len(years) else None,
        year_max=int(years.max()) if len(years) else None,
        n_years=int(years.nunique()),
        oktmo_status_by_city={str(k): int(v) for k, v in status_counts.items()},
        query=SPARQL_QUERY_PLAN.strip(),
    )


def save_population(
    df: pd.DataFrame,
    *,
    dest_dir: Path | None = None,
    fetched_at: str | None = None,
) -> tuple[Path, Path]:
    """Сохранить Parquet, CSV и метаданные в data/processed/population/."""
    ensure_data_dirs()
    dest_dir = dest_dir or POP_PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = dest_dir / "ru_cities_population.parquet"
    csv_path = dest_dir / "ru_cities_population.csv"
    meta_path = dest_dir / "ru_cities_population.meta.json"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    write_meta(meta_path, population_meta(df, fetched_at=fetched_at))
    return parquet_path, csv_path


def fetch_and_save(*, dest_dir: Path | None = None) -> tuple[Path, Path, pd.DataFrame]:
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = fetch_sparql()
    df = rows_to_dataframe(rows)
    parquet_path, csv_path = save_population(df, dest_dir=dest_dir, fetched_at=fetched_at)
    return parquet_path, csv_path, df
