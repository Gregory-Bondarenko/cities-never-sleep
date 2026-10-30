# Журнал изменений

Все заметные изменения проекта «Города не спят» (Cities Never Sleep) фиксируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии следуют [Semantic Versioning](https://semver.org/lang/ru/). Правила выпуска описаны в [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- Workflow `release`: тег и GitHub Release создаются автоматически при попадании в `main` релизной версии; текст берётся из `CHANGELOG.md` (`scripts/release_notes.py`).
- Проверка ОКТМО (`validate/oktmo.py`): коды нормализуются, некорректные помечаются статусом и не отбрасываются. В текущей выгрузке некорректный код у одного города (Дмитриев), 8-значные коды у Москвы и Санкт-Петербурга (#6).
- Общий модуль метаданных артефактов `meta.py` (#8).
- ADR-0005: сквозной результат раньше поправок методики, круговые контуры городов до v0.6.0.
- Справочник городов `cities/ru_cities` (схема 1.0.0): координаты P625, последнее население; команда `cns fetch-pop` выгружает оба набора.
- Выбор одного значения населения на город и год (#7): столбцы `rank`, `method`, `is_primary`, `n_values`, `is_conflict`; схема набора населения 1.1.0.
- Радиус кругового контура города `process/boundaries.radius_km` (ADR-0005).
- Workflow `data-refresh`: выгрузка данных на раннере GitHub с пушем в отдельную ветку для PR.

### Changed

- **Несовместимо:** набор `population/ru_cities_population` переведён на схему 1.0.0. Столбец `wikidata_id` переименован в `city_id`, добавлен `oktmo_status`, метаданные приведены к контракту (`schema_version`, `built_at`, `package_version`, `fetched_at`); вместо полного списка лет хранятся `year_min`, `year_max`, `n_years` (#6, #8).
- Версия в коде поднята до `0.2.0.dev0`.
- Дорожная карта: порядок вех изменён на «города → статистика → анализ → витрина → методика», добавлены ориентировочные даты.
- Actions обновлены до версий на Node 24: `actions/checkout@v7`, `actions/upload-artifact@v7`, `astral-sh/setup-uv@v10.3.3` (закреплён на точной версии, так как мажорные теги больше не публикуются) (#18).

## [0.1.0] - 2026-10-30

Первый выпуск: каркас, загрузчики данных, обрезка VNL по России, процесс разработки. Пробный прогон за 2013 год пройден на раннере GitHub (#4).

### Added

- Каркас репозитория: `pyproject.toml` (uv), лицензия MIT, `.gitignore`, `Makefile`, CLI `cns` (typer).
- Раскладка «аналитика → артефакты → витрина»: `analytics/`, `data/processed/` и `analytics/exports/`, `web/`.
- Загрузчик годовых VIIRS VNL с Zenodo [17294744](https://zenodo.org/records/17294744) (`cns fetch-vnl`).
- Обрезка COG по прямоугольнику России и окну Чукотки, деление на 10 для 2012–2021 (`cns process-vnl`).
- Загрузчик населения городов РФ из Wikidata SPARQL с ОКТМО (`cns fetch-pop`), результат в `data/processed/population/`.
- Документация: README, `docs/data-sources.md`, `docs/stack-proposal.md`, CONTRIBUTING, минимальный CI.
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

[Unreleased]: https://github.com/Gregory-Bondarenko/cities-never-sleep/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Gregory-Bondarenko/cities-never-sleep/releases/tag/v0.1.0
