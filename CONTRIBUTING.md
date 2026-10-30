# Порядок работы

Проект ведётся как продукт: задача в issue, работа в ветке, проверка в pull request, слияние в `main`. Прямой push в `main` не используется. Обоснование правил: [ADR-0003](docs/adr/0003-versioning-and-releases.md).

## Задачи

- Каждая задача заводится как issue по одному из шаблонов: ошибка, новая возможность, проблема с данными.
- Issue привязывается к milestone версии (см. [дорожную карту](docs/roadmap.md)) и получает метки `area:*`, `type:*`, `priority:*`.

## Ветки

```bash
git checkout main && git pull origin main
git checkout -b feat/city-boundaries
```

| Префикс | Когда |
|---|---|
| `feat/` | новая возможность |
| `fix/` | исправление ошибки |
| `data/` | изменение артефактов в `data/processed/` или `analytics/exports/` |
| `docs/` | только документация |
| `refactor/` | изменение кода без изменения поведения |
| `test/` | только тесты |
| `ci/` | CI и автоматизация |
| `chore/` | служебные изменения, релизы |

## Коммиты

Формат [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/):

```
<тип>(<область>): <что сделано>
```

Типы совпадают с префиксами веток. Области: `vnl`, `pop`, `process`, `metrics`, `cli`, `web`, `docs`, `ci`. Примеры:

```
feat(pop): нормализация ОКТМО и проверка формата
fix(process): корректная обработка nodata при делении шкалы
docs: архитектура и дорожная карта
```

Несовместимое изменение помечается `!` после области и описывается в теле коммита: `feat(cli)!: ...`.

## Pull request

- PR открывается в `main`, заголовок в формате Conventional Commits.
- Описание по шаблону; связь с задачей через `Closes #N`.
- CI зелёный: `ruff`, `pytest`, проверка CLI.
- Изменения, заметные пользователю или влияющие на данные, записаны в `CHANGELOG.md` в разделе `[Unreleased]`.
- Слияние способом squash, ветка удаляется.

## Версии

| Изменение до v1.0.0 | Версия |
|---|---|
| несовместимое изменение CLI или схемы артефакта | MINOR |
| новая возможность без поломки | MINOR |
| исправление, документация, CI | PATCH |

Версия хранится в двух местах и меняется синхронно: `version` в `pyproject.toml` (например `0.2.0.dev0`) и `__version__` в `analytics/citiesneversleep/__init__.py` (например `0.2.0-dev`).

## Релиз

1. Ветка `chore/release-vX.Y.Z`: записи из `[Unreleased]` переносятся в раздел `[X.Y.Z] - ГГГГ-ММ-ДД`, версия в коде без суффикса `dev`.
2. PR `chore(release): vX.Y.Z`, слияние.
3. Тег на коммите слияния и GitHub Release:
   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. Следующим коммитом версия в коде поднимается до следующей с суффиксом `dev`.

## Локальная проверка

```bash
uv sync --all-extras
uv run ruff check analytics tests scripts
uv run pytest -q
uv run cns version
uv run cns fetch-vnl --dry-run --years 2013
uv run cns fetch-pop --dry-run
```

## Пробный прогон

Полный прогон загрузки и обрезки за один год запускается на раннере GitHub: Actions → smoke → Run workflow, параметр `year`. Сводка появляется в отчёте запуска и в артефакте `smoke-report-<год>`. Прогон обязателен перед выпуском минорной версии.

## Архитектурные правила

- Поток данных: `analytics/` → артефакты → `web/`. Расчёты во фронтенде запрещены.
- Сырые и промежуточные данные (`data/raw/`, `data/interim/`) не коммитятся.
- Новая зависимость или смена стека оформляется через ADR в `docs/adr/`.

Подробности в [docs/architecture.md](docs/architecture.md).
