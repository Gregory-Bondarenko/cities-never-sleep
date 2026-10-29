# Города не спят / Cities Never Sleep

**Версия:** `0.1.0-dev` (каркас недели 1; после merge — тег `v0.1.0`; готовый MVP — `v1.0.0`)

Какие города России гаснут и какие растут по ночным спутниковым снимкам VIIRS (2012–2024), в сравнении с населением. Главное в репозитории — **исследовательский пайплайн**; сайт на GitHub Pages — витрина поверх готовых артефактов.

## Аналитика → артефакты → сайт

```
analytics/          data/processed/          web/
загрузка,           + analytics/exports/     только визуализация
обработка,     →    лёгкие parquet/JSON/  →  (GitHub Pages),
метрики,            PMTiles                  без тяжёлой аналитики
ноутбуки
```

1. **`analytics/`** — ядро: скрипты загрузки (Zenodo VNL, Wikidata), обрезка растров, будущие метрики и ноутбуки.
2. **`data/processed/`** и **`analytics/exports/`** — воспроизводимые артефакты небольшого размера.
3. **`web/`** — фронт читает только экспорт; расчёты SOL/трендов во фронт не переносятся.

## Структура

```
analytics/
  citiesneversleep/   # Python-пакет и CLI `cns`
  notebooks/          # EDA (неделя 4+)
  exports/            # выгрузки для сайта
data/
  raw/ interim/       # локально, в git не коммитим
  processed/          # агрегаты (население и т.п.)
  manual/             # ручные выгрузки Росстата
web/                  # заготовка витрины (стек — proposal)
docs/                 # источники, proposal стека
```

## Стек — proposal

Предложенный стек (Python/uv, rasterio, DuckDB, MapLibre/deck.gl и др.) **не утверждён**. См. [docs/stack-proposal.md](docs/stack-proposal.md). На неделе 1 в зависимостях только минимум для загрузки и обрезки.

## Быстрый старт

Требуются [uv](https://docs.astral.sh/uv/) и Python ≥ 3.12.

```bash
uv sync --all-extras
uv run cns version

# Каталог Zenodo без скачивания (~ГБ):
uv run cns fetch-vnl --dry-run --years 2012-2024

# Население из Wikidata (секунды, ~МБ в data/processed/):
uv run cns fetch-pop

# Один год VNL + обрезка по России (для пробы; полный ряд ~0,9 ГБ сырых):
uv run cns fetch-vnl --year 2013
uv run cns process-vnl --year 2013
```

Или через Make: `make install`, `make fetch-pop`, `make fetch-vnl YEARS=2013`, `make process VNL_YEAR=2013`.

Подробнее об источниках и лицензиях: [docs/data-sources.md](docs/data-sources.md).

## Разработка

Прямой push в `main` не используется: ветка → PR → ревью → merge. Версии — SemVer, журнал — [CHANGELOG.md](CHANGELOG.md). Правила веток и релизов: [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
uv run ruff check analytics tests
uv run pytest -q
```

## Лицензия

Код — [MIT](LICENSE). Данные третьих сторон — свои лицензии (VNL: CC-BY 4.0; Wikidata: CC0).
