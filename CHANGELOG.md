# Changelog

Все заметные изменения проекта **«Города не спят» / Cities Never Sleep** фиксируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии следуют [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- Каркас репозитория: `pyproject.toml` (uv), MIT LICENSE, `.gitignore`, `Makefile`, CLI `cns` (typer).
- Раскладка **analytics → артефакты → сайт**: `analytics/` (ядро), `data/processed` + `analytics/exports`, `web/` (только витрина).
- Загрузчик годовых VIIRS VNL с Zenodo [17294744](https://zenodo.org/records/17294744) (`cns fetch-vnl`).
- Обрезка COG по bbox России (+ окно Чукотки), нормализация шкалы ×10 для 2012–2021 (`cns process-vnl`).
- Загрузчик населения городов РФ из Wikidata SPARQL с ОКТМО (`cns fetch-pop`) → parquet/csv в `data/processed/`.
- Документация: README (рус.), `docs/data-sources.md`, `docs/stack-proposal.md` (стек не утверждён), CONTRIBUTING, минимальный CI.
- SemVer `0.1.0-dev`, Keep a Changelog, ветки только через PR в `main`.

## [0.1.0-dev] — 2026-10-29

Предрелизная метка недели 1 (каркас + загрузчики). После merge в `main` и смоук-проверки планируется тег `v0.1.0`.
Мажор `v1.0.0` — к готовому MVP (конец 6-недельного плана).

[Unreleased]: https://github.com/Gregory-Bondarenko/cities-never-sleep/compare/v0.1.0-dev...HEAD
[0.1.0-dev]: https://github.com/Gregory-Bondarenko/cities-never-sleep/releases/tag/v0.1.0-dev
