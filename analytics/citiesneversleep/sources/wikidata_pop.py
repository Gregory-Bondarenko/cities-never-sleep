"""Население городов РФ с ОКТМО из Wikidata (SPARQL)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from citiesneversleep import __version__
from citiesneversleep.meta import build_meta, write_meta
from citiesneversleep.paths import CITIES_PROCESSED_DIR, POP_PROCESSED_DIR, ensure_data_dirs
from citiesneversleep.validate.oktmo import add_oktmo_status

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    f"CitiesNeverSleep/{__version__} "
    "(https://github.com/Gregory-Bondarenko/cities-never-sleep; educational)"
)

# Классы, которыми в Wikidata размечены города России. Крупные города часто
# отмечены не классом «город» (Q7930989), а «городом России», «большим городом»
# или общим «городом» (#48: Екатеринбург, Владивосток, Иркутск, Кемерово).
CITY_CLASSES = (
    "Q7930989",  # город (city/town)
    "Q515",  # город
    "Q106389302",  # город России
    "Q1549591",  # большой город
    "Q1637706",  # город-миллионер
    "Q5123997",  # город регионального значения в субъектах РФ
)
_CLASS_VALUES = " ".join(f"wd:{q}" for q in CITY_CLASSES)

# Отбор городов (ADR-0006). Класс проверяется по всем утверждениям P31, кроме
# устаревших, а не только по лучшему рангу (wdt:P31): у Краснодара класс «город»
# имеет обычный ранг, а предпочтительный у «мегаполиса» (#48). Две ветви:
#   p17_russia: один из CITY_CLASSES, страна Россия (Q159), есть ОКТМО;
#   oktmo_only: класс «город» или его подкласс, есть ОКТМО, но в Wikidata не указана
#                 страна Россия. Так в выборку попадают города Республики Крым,
#                 Севастополя, ДНР, ЛНР, Запорожской и Херсонской областей, учтённые
#                 в российском классификаторе ОКТМО.
CITY_FILTER = (
    """
  hint:Query hint:optimizer "None" .
  {
    VALUES ?cls { """
    + _CLASS_VALUES
    + """ }
    ?st ps:P31 ?cls .
    ?city p:P31 ?st .
    FILTER NOT EXISTS { ?st wikibase:rank wikibase:DeprecatedRank . }
    ?city wdt:P17 wd:Q159 ;
          wdt:P764 ?oktmo .
    BIND("p17_russia" AS ?coverage)
  } UNION {
    ?city wdt:P764 ?oktmo .
    FILTER NOT EXISTS { ?city wdt:P17 wd:Q159 . }
    ?city p:P31/ps:P31/wdt:P279* wd:Q7930989 .
    BIND("oktmo_only" AS ?coverage)
  }
"""
)
# Порядок троек важен: оптимизатор отключён, поэтому во второй ветви движок
# сначала берёт объекты с ОКТМО без страны Россия (их немного) и только для них
# проверяет класс по цепочке подклассов. С оптимизатором запрос начинался
# с обхода всех подклассов «города» и падал по таймауту Wikidata.

# Контроль полноты: административные центры, которые обязаны попасть в выборку.
# Пропуск любого из них означает ошибку отбора (#48).
CONTROL_CITIES = {
    "Q649": "Москва",
    "Q656": "Санкт-Петербург",
    "Q887": "Екатеринбург",
    "Q3646": "Краснодар",
    "Q959": "Владивосток",
    "Q6576": "Иркутск",
    "Q6066": "Кемерово",
    "Q883": "Новосибирск",
    "Q5196": "Грозный",
    "Q7525": "Севастополь",
}


def missing_control_cities(city_ids) -> dict[str, str]:
    """Контрольные города, которых нет среди ``city_ids``."""
    have = set(city_ids)
    return {q: n for q, n in CONTROL_CITIES.items() if q not in have}


# Объекты с кодом ОКТМО, которые не являются территорией субъектов РФ (ADR-0006).
EXCLUDED_CITIES = {
    "Q165413": "Байконур: территория Республики Казахстан, арендованная Российской Федерацией",
}

# Ряд численности: каждое утверждение P1082 с рангом, датой (P585)
# и способом определения (P459), чтобы выбрать одно значение на город и год.
POPULATION_QUERY = (
    """
SELECT DISTINCT ?city ?cityLabel ?oktmo ?pop ?date ?rank ?method WHERE {"""
    + CITY_FILTER
    + """  ?city p:P1082 ?popStmt .
  ?popStmt ps:P1082 ?pop ;
           wikibase:rank ?rank .
  OPTIONAL { ?popStmt pq:P585 ?date . }
  OPTIONAL { ?popStmt pq:P459 ?method . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". }
}
"""
)

# Справочник городов: координаты (P625).
CITIES_QUERY = (
    """
SELECT DISTINCT ?city ?cityLabel ?oktmo ?coverage ?coord WHERE {"""
    + CITY_FILTER
    + """  OPTIONAL { ?city wdt:P625 ?coord . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". }
}
"""
)

def fetch_sparql(
    query: str = POPULATION_QUERY,
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


ENTITY_PREFIX = "http://www.wikidata.org/entity/"
RANK_PREFIX = "http://wikiba.se/ontology#"
CENSUS_QID = "Q39825"  # перепись населения (P459)

COLUMNS = [
    "city_id",
    "name",
    "oktmo",
    "oktmo_status",
    "population",
    "date",
    "year",
    "rank",
    "method",
    "is_primary",
    "n_values",
    "is_conflict",
]
SCHEMA_VERSION = "1.1.0"
CITIES_COLUMNS = [
    "city_id",
    "name",
    "oktmo",
    "oktmo_status",
    "coverage",
    "lat",
    "lon",
    "population_latest",
    "population_latest_year",
]
CITIES_SCHEMA_VERSION = "1.1.0"
LICENSE_NOTE = "Wikidata: CC0; значения населения происходят из бюллетеней Росстата"
_RANK_ORDER = {"preferred": 0, "normal": 1, "deprecated": 2}
_POINT = r"Point\(\s*(?P<lon>-?[\d.]+)\s+(?P<lat>-?[\d.]+)\s*\)"


def _strip(series: pd.Series, prefix: str) -> pd.Series:
    return series.astype("string").str.replace(prefix, "", regex=False)


def select_primary(df: pd.DataFrame) -> pd.DataFrame:
    """Отметить одно значение населения на город и год (#7).

    Правило выбора среди утверждений одного года, кроме устаревших (deprecated):

    1. ранг preferred раньше normal;
    2. перепись (P459 = Q39825) раньше оценки;
    3. более поздняя дата внутри года;
    4. при полном совпадении признаков берётся большее значение,
       чтобы результат не зависел от порядка строк.

    ``n_values`` хранит число различных значений года, ``is_conflict`` отмечает
    годы, где они расходятся. Строки без года основными не считаются.
    """
    out = df.copy()
    out["is_primary"] = False
    eligible = out["year"].notna() & (out["rank"] != "deprecated")
    keyed = out[eligible].assign(
        _rank=lambda d: d["rank"].map(_RANK_ORDER).fillna(1).astype(int),
        _census=lambda d: d["method"].eq(CENSUS_QID).fillna(False).astype(int),
    )
    keyed = keyed.sort_values(
        ["city_id", "year", "_rank", "_census", "date", "population"],
        ascending=[True, True, True, False, False, False],
        na_position="last",
    )
    primary_idx = keyed.groupby(["city_id", "year"], sort=False).head(1).index
    out.loc[primary_idx, "is_primary"] = True

    n_values = keyed.groupby(["city_id", "year"])["population"].nunique().rename("n_values")
    out = out.join(n_values, on=["city_id", "year"])
    out["n_values"] = out["n_values"].fillna(0).astype("Int64")
    out["is_conflict"] = out["n_values"] > 1
    return out


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Привести ответ запроса населения к схеме набора ``population``.

    Ключ города ``city_id`` равен идентификатору Wikidata. ОКТМО нормализуется,
    его корректность отражается в ``oktmo_status``; строки с некорректным кодом
    не отбрасываются. Одно значение на город и год отмечается ``is_primary``.
    """
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    df = df.rename(columns={"city": "city_id", "cityLabel": "name", "pop": "population"})
    for col in ("date", "rank", "method"):
        if col not in df.columns:
            df[col] = pd.NA
    df["city_id"] = _strip(df["city_id"], ENTITY_PREFIX)
    df["rank"] = _strip(df["rank"], RANK_PREFIX).str.replace("Rank", "").str.lower()
    df["rank"] = df["rank"].fillna("normal")
    df["method"] = _strip(df["method"], ENTITY_PREFIX)
    df = df[~df["city_id"].isin(EXCLUDED_CITIES)]
    df = add_oktmo_status(df)
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["year"] = df["date"].dt.year.astype("Int64")
    df = df.dropna(subset=["population"])
    df["population"] = df["population"].round().astype("int64")
    df = select_primary(df)
    df = df.sort_values(["city_id", "year", "population"], na_position="last")
    return df[COLUMNS].reset_index(drop=True)


def cities_from_rows(rows: list[dict], population: pd.DataFrame) -> pd.DataFrame:
    """Справочник городов: одна строка на ``city_id`` с координатами и последним населением.

    При нескольких ОКТМО предпочитается корректный код, при нескольких
    координатах берётся первая в лексикографическом порядке, чтобы результат
    был воспроизводимым.
    """
    if not rows:
        return pd.DataFrame(columns=CITIES_COLUMNS)
    df = pd.DataFrame(rows).rename(columns={"city": "city_id", "cityLabel": "name"})
    for col in ("coord", "coverage"):
        if col not in df.columns:
            df[col] = pd.NA
    df["coverage"] = df["coverage"].fillna("p17_russia")
    df["city_id"] = _strip(df["city_id"], ENTITY_PREFIX)
    df = df[~df["city_id"].isin(EXCLUDED_CITIES)]
    df = add_oktmo_status(df)
    coords = df["coord"].astype("string").str.extract(_POINT)
    df["lat"] = pd.to_numeric(coords["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(coords["lon"], errors="coerce")
    df["_ok"] = (df["oktmo_status"] != "ok").astype(int)
    df = df.sort_values(["city_id", "_ok", "coord"], na_position="last")
    df = df.drop_duplicates("city_id")

    primary = population[population["is_primary"]].sort_values(["city_id", "year"])
    latest = primary.groupby("city_id").tail(1).set_index("city_id")
    df["population_latest"] = df["city_id"].map(latest["population"]).astype("Int64")
    df["population_latest_year"] = df["city_id"].map(latest["year"]).astype("Int64")
    return df[CITIES_COLUMNS].sort_values("city_id").reset_index(drop=True)


def population_meta(df: pd.DataFrame, *, fetched_at: str | None = None) -> dict:
    """Метаданные набора населения по контракту артефактов."""
    years = df["year"].dropna()
    status_counts = (
        df.drop_duplicates("city_id")["oktmo_status"].value_counts().sort_index().to_dict()
        if len(df)
        else {}
    )
    primary = df[df["is_primary"]] if len(df) else df
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
        n_primary=int(len(primary)),
        n_conflict_city_years=int(primary["is_conflict"].sum()) if len(primary) else 0,
        selection_rule="preferred > normal; перепись > оценка; поздняя дата; большее значение",
        oktmo_status_by_city={str(k): int(v) for k, v in status_counts.items()},
        query=POPULATION_QUERY.strip(),
    )


def cities_meta(df: pd.DataFrame, *, fetched_at: str | None = None) -> dict:
    """Метаданные справочника городов."""
    return build_meta(
        schema_version=CITIES_SCHEMA_VERSION,
        source="Wikidata SPARQL",
        n_rows=len(df),
        license_note="Wikidata: CC0",
        endpoint=WIKIDATA_SPARQL,
        fetched_at=fetched_at,
        n_without_coords=int(df["lat"].isna().sum()) if len(df) else 0,
        n_without_population=int(df["population_latest"].isna().sum()) if len(df) else 0,
        coverage_counts=df["coverage"].value_counts().to_dict() if len(df) else {},
        excluded=EXCLUDED_CITIES,
        query=CITIES_QUERY.strip(),
    )


def _save(df: pd.DataFrame, dest_dir: Path, stem: str, meta: dict) -> tuple[Path, Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = dest_dir / f"{stem}.parquet"
    csv_path = dest_dir / f"{stem}.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    write_meta(dest_dir / f"{stem}.meta.json", meta)
    return parquet_path, csv_path


def save_population(
    df: pd.DataFrame,
    *,
    dest_dir: Path | None = None,
    fetched_at: str | None = None,
) -> tuple[Path, Path]:
    """Сохранить Parquet, CSV и метаданные в data/processed/population/."""
    ensure_data_dirs()
    meta = population_meta(df, fetched_at=fetched_at)
    return _save(df, dest_dir or POP_PROCESSED_DIR, "ru_cities_population", meta)


def save_cities(
    df: pd.DataFrame,
    *,
    dest_dir: Path | None = None,
    fetched_at: str | None = None,
) -> tuple[Path, Path]:
    """Сохранить справочник городов в data/processed/cities/."""
    ensure_data_dirs()
    meta = cities_meta(df, fetched_at=fetched_at)
    return _save(df, dest_dir or CITIES_PROCESSED_DIR, "ru_cities", meta)


def fetch_and_save(
    *, dest_dir: Path | None = None, cities_dir: Path | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Выгрузить население и справочник городов, сохранить оба набора."""
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    population = rows_to_dataframe(fetch_sparql(POPULATION_QUERY))
    cities = cities_from_rows(fetch_sparql(CITIES_QUERY), population)
    save_population(population, dest_dir=dest_dir, fetched_at=fetched_at)
    save_cities(cities, dest_dir=cities_dir, fetched_at=fetched_at)
    return population, cities
