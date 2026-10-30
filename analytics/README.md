# analytics/: исследовательское ядро

Загрузка данных, обработка, метрики, ноутбуки и методика.

| Путь | Назначение |
|---|---|
| `citiesneversleep/sources/` | загрузчики внешних источников |
| `citiesneversleep/process/` | обработка растров |
| `citiesneversleep/cli.py` | CLI `cns` |
| `notebooks/` | разведочный анализ |
| `exports/` | облегчённые выгрузки для `web/` |

Поток данных: аналитика → артефакты (`data/processed/`, `exports/`) → витрина. Подробности в [docs/architecture.md](../docs/architecture.md).
