# Города не спят / Cities Never Sleep

[![ci](https://github.com/Gregory-Bondarenko/cities-never-sleep/actions/workflows/ci.yml/badge.svg)](https://github.com/Gregory-Bondarenko/cities-never-sleep/actions/workflows/ci.yml)

Какие города России гаснут, а какие становятся ярче ночью, по спутниковым снимкам VIIRS за 2012–2024 годы, и как это соотносится с динамикой населения.

Основа продукта: воспроизводимый исследовательский конвейер. Сайт на GitHub Pages служит витриной поверх готовых артефактов.

**Версия:** `0.1.0`. Статус вех и план: [docs/roadmap.md](docs/roadmap.md).

## Как устроено

```
analytics/            data/processed/            web/
загрузка,             analytics/exports/         только визуализация
обработка,      →     небольшие Parquet,    →    (GitHub Pages)
метрики,              JSON, PMTiles
ноутбуки              с метаданными
```

Фронтенд ничего не рассчитывает и читает только экспорт. Подробности: [docs/architecture.md](docs/architecture.md).

## Быстрый старт

Нужны [uv](https://docs.astral.sh/uv/) и Python 3.12 или новее.

```bash
uv sync --all-extras
uv run cns version

# Каталог Zenodo без скачивания
uv run cns fetch-vnl --dry-run --years 2012-2024

# Население из Wikidata (несколько секунд, файлы в data/processed/)
uv run cns fetch-pop

# Один год VNL и обрезка по России (полный ряд занимает около 0,9 ГБ)
uv run cns fetch-vnl --year 2013
uv run cns process-vnl --year 2013
```

Те же действия через Make: `make install`, `make fetch-pop`, `make fetch-vnl YEARS=2013`, `make process VNL_YEAR=2013`.

## Структура

```
analytics/
  citiesneversleep/   Python-пакет и CLI cns
  notebooks/          разведочный анализ
  exports/            выгрузки для сайта
data/
  raw/ interim/       локально, в git не попадают
  processed/          агрегаты с метаданными
  manual/             ручные выгрузки Росстата
web/                  витрина (стек на согласовании)
scripts/              служебные скрипты (отчёт пробного прогона)
docs/                 архитектура, методика, источники, ADR
```

## Документация

| Документ | О чём |
|---|---|
| [docs/architecture.md](docs/architecture.md) | слои, контракты артефактов, целевая модель данных |
| [docs/methodology.md](docs/methodology.md) | допущения и известные ограничения данных |
| [docs/data-sources.md](docs/data-sources.md) | источники и лицензии |
| [docs/roadmap.md](docs/roadmap.md) | вехи и версии |
| [docs/adr/](docs/adr/) | принятые архитектурные решения |
| [CONTRIBUTING.md](CONTRIBUTING.md) | ветки, коммиты, PR, релизы |
| [CHANGELOG.md](CHANGELOG.md) | журнал изменений |

## Разработка

Изменения вносятся только через ветку и pull request в `main`. Версии по SemVer, журнал по Keep a Changelog.

```bash
uv run ruff check analytics tests scripts
uv run pytest -q
```

## Лицензия

Код распространяется по лицензии [MIT](LICENSE). Данные третьих сторон под своими лицензиями: VNL под CC-BY 4.0, Wikidata под CC0.
