# Предложение по стеку (не утверждено)

> **Статус:** предложение. Стек ниже служит рабочей гипотезой; решения по нему принимаются через [ADR-0004](adr/0004-stack.md) по мере наступления вех.
> В коде зафиксирован только минимальный набор для загрузки и обрезки данных.

## Аналитика / пайплайн (`analytics/`)

| Слой | Кандидаты | Зачем | Статус |
|---|---|---|---|
| Язык / env | **Python 3.12**, **uv** (`pyproject.toml` + lock) | воспроизводимость, быстрый sync | proposal (uv уже в каркасе) |
| CLI | **typer** (+ rich) | `cns fetch-*` / `process-*` | proposal |
| Растры | **rasterio** (+ при необходимости rioxarray) | чтение COG, окна, обрезка | proposal |
| Таблицы | **pandas** / polars, **pyarrow** (parquet) | население, марты | proposal |
| SQL / озеро | **DuckDB** (+ опционально dbt-duckdb) | raw → staging → marts | proposal (неделя 2+) |
| Гео / зоны | geopandas, shapely, **exactextract**, h3 | зональная статистика, сетка | proposal |
| Black Marble | earthaccess | NASA VNP46A4 | proposal (неделя 3) |
| OSM | quackosm / osmium | границы, ОКТМО | proposal (неделя 2) |
| Анализ | statsmodels, pymannkendall, ruptures, scikit-learn | тренды, кластеры | proposal (неделя 4) |
| Качество кода | ruff, pytest, GitHub Actions | lint + смоук | proposal (минимальный CI уже есть) |

## Витрина (`web/`)

| Слой | Кандидаты | Зачем | Статус |
|---|---|---|---|
| Сборка | Vite + TypeScript | статическая сборка под GitHub Pages | proposal |
| Карта | **MapLibre GL** | 2D-карта городов | proposal |
| 3D / гексы | **deck.gl** (`H3HexagonLayer`) | таймлапс на главной | proposal |
| Графики | Observable Plot или ECharts | карточка города, квадранты | proposal |
| Растр на сайте | PMTiles | «шторка» лет | proposal |

## Поток данных (инвариант раскладки)

```
analytics/  →  data/processed + analytics/exports/  →  web/
 (загрузка,       (лёгкие артефакты)                  (только визуализация)
  метрики, ноутбуки)
```

Фронт **не** считает SOL и тренды: только читает экспортированные JSON/Parquet/PMTiles.

## Что уже используется в коде

Минимально необходимое для MVP-загрузчиков: Python 3.12, uv, typer, httpx, rasterio, numpy, pandas, pyarrow. Остальные позиции из таблиц выше остаются кандидатами до утверждения стека.
