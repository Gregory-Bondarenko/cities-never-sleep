# Журнал изменений

Все заметные изменения проекта «Города не спят» (Cities Never Sleep) фиксируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии следуют [Semantic Versioning](https://semver.org/lang/ru/). Правила выпуска описаны в [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- Документация продукта: архитектура и контракт артефактов (`docs/architecture.md`), дорожная карта по версиям (`docs/roadmap.md`), методика с известными ограничениями данных (`docs/methodology.md`).
- Реестр архитектурных решений `docs/adr/` с ADR-0001…0004.
- Инструкции для ИИ-агентов `AGENTS.md` и `CLAUDE.md`.
- Шаблоны pull request и issues (ошибка, новая возможность, проблема с данными).
- Тесты загрузчиков VNL и Wikidata на подменённом HTTP, тесты обрезки и нормализации шкалы на синтетическом растре; сетевые запросы в тестах заблокированы (#14).
- Workflow `network`: еженедельная и ручная проверка доступности Zenodo и Wikidata (#14).
- Workflow `smoke`: ручной пробный прогон загрузки и обрезки VNL за выбранный год и загрузки населения на раннере GitHub; сводка в отчёте запуска (`scripts/smoke_report.py`).

### Changed

- Обязательный CI больше не обращается к сети: только `ruff`, `pytest` и проверка CLI; зависимости ставятся строго по `uv.lock` (#14).
- `CONTRIBUTING.md`: префиксы веток, Conventional Commits, squash merge, порядок релиза; исправлен путь к `__init__.py`.
- `README.md`: навигация по документации, значок CI.

## [0.1.0-dev] - 2026-10-29

Каркас первой недели, без тега.

### Added

- Каркас репозитория: `pyproject.toml` (uv), лицензия MIT, `.gitignore`, `Makefile`, CLI `cns` (typer).
- Раскладка «аналитика → артефакты → витрина»: `analytics/`, `data/processed/` и `analytics/exports/`, `web/`.
- Загрузчик годовых VIIRS VNL с Zenodo [17294744](https://zenodo.org/records/17294744) (`cns fetch-vnl`).
- Обрезка COG по прямоугольнику России и окну Чукотки, деление на 10 для 2012–2021 (`cns process-vnl`).
- Загрузчик населения городов РФ из Wikidata SPARQL с ОКТМО (`cns fetch-pop`), результат в `data/processed/population/`.
- Документация: README, `docs/data-sources.md`, `docs/stack-proposal.md`, CONTRIBUTING, минимальный CI.

[Unreleased]: https://github.com/Gregory-Bondarenko/cities-never-sleep/commits/main
