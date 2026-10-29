# Как участвовать

Проект ведётся «по правилам»: ветки → pull request → ревью → merge в `main`. Прямой push в `main` не используется.

## Ветки

1. Обновите `main`: `git checkout main && git pull origin main`
2. Создайте ветку от `main`:
   - фича: `feat/<кратко>` (напр. `feat/week1-scaffold`)
   - инфраструктура: `chore/<кратко>`
   - исправление: `fix/<кратко>`
3. Коммитьте осмысленными сообщениями; не коммитьте секреты и сырые растры (`data/raw/`, `data/interim/`).

## Pull request

- Открывайте PR **в `main`**.
- CI должен быть зелёным (lint + dry-run CLI).
- Merge — после ревью/проверки (squash или merge commit — на усмотрение владельца).

## Версии (SemVer)

| Метка | Когда |
|---|---|
| `0.1.0-dev` / `v0.1.0-dev` | Каркас недели 1 (текущая разработка) |
| `v0.1.0` | После merge недели 1 и смоук-прогона `fetch`/`process` |
| `0.x.y` | Инкременты до конца MVP (пайплайн, анализ, сайт) |
| `v1.0.0` | Готовый MVP (конец 6-недельного плана) |

Правила:

- **MAJOR** — несовместимые изменения публичного CLI/схемы мартов или релиз MVP `v1.0.0`.
- **MINOR** — новая функциональность без ломания CLI.
- **PATCH** — багфиксы, доки, CI.

Версия в коде: поле `version` в `pyproject.toml` и `__version__` в `src/citiesneversleep/__init__.py` (для pre-release используем `0.1.0.dev0` / отображение `0.1.0-dev`).

Каждый релиз: обновите `CHANGELOG.md` (перенос из Unreleased), тег `vX.Y.Z` на merge-коммите в `main`.

## Локальная проверка

```bash
uv sync --all-extras
uv run ruff check analytics tests
uv run pytest -q
uv run cns version
uv run cns fetch-vnl --dry-run --years 2013
uv run cns fetch-pop --dry-run
```

Раскладка репозитория: **analytics → артефакты → сайт**. Тяжёлую логику добавляйте в `analytics/`, не во `web/`. Стек — proposal до отдельного утверждения (`docs/stack-proposal.md`).
