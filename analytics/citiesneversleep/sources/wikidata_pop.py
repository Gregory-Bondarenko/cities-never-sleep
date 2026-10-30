"""Население городов РФ с ОКТМО из Wikidata (SPARQL)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pandas as pd

from citiesneversleep import __version__
from citiesneversleep.paths import POP_PROCESSED_DIR, ensure_data_dirs

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


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["wikidata_id", "name", "oktmo", "population", "date", "year"]
        )
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "city": "wikidata_id",
            "cityLabel": "name",
            "pop": "population",
        }
    )
    df["wikidata_id"] = df["wikidata_id"].str.replace(
        "http://www.wikidata.org/entity/", "", regex=False
    )
    df["oktmo"] = df["oktmo"].astype(str).str.strip()
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        df["year"] = df["date"].dt.year.astype("Int64")
    else:
        df["date"] = pd.NaT
        df["year"] = pd.Series([pd.NA] * len(df), dtype="Int64")
    df = df.dropna(subset=["population"])
    df = df.sort_values(["oktmo", "year", "name"], na_position="last")
    return df.reset_index(drop=True)


def save_population(
    df: pd.DataFrame,
    *,
    dest_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Сохранить parquet + csv в data/processed/population/."""
    ensure_data_dirs()
    dest_dir = dest_dir or POP_PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = dest_dir / "ru_cities_population.parquet"
    csv_path = dest_dir / "ru_cities_population.csv"
    meta_path = dest_dir / "ru_cities_population.meta.json"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    n_cities = df["oktmo"].nunique() if len(df) else 0
    years = (
        sorted(int(y) for y in df["year"].dropna().unique().tolist()) if len(df) else []
    )
    meta = {
        "source": "Wikidata SPARQL",
        "endpoint": WIKIDATA_SPARQL,
        "license_note": (
            "Wikidata: CC0; значения населения происходят из бюллетеней Росстата"
        ),
        "n_rows": int(len(df)),
        "n_oktmo": int(n_cities),
        "years": years,
        "query": SPARQL_QUERY_PLAN.strip(),
    }
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return parquet_path, csv_path


def fetch_and_save(*, dest_dir: Path | None = None) -> tuple[Path, Path, pd.DataFrame]:
    rows = fetch_sparql()
    df = rows_to_dataframe(rows)
    parquet_path, csv_path = save_population(df, dest_dir=dest_dir)
    return parquet_path, csv_path, df
