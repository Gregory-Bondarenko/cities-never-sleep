.PHONY: help install all derive fetch fetch-vnl fetch-pop process process-vnl rasters lights trends export site lint test clean

UV ?= uv
YEARS ?= 2012-2024
VNL_YEAR ?=
MAP_YEAR ?= 2024
KEEP_RAW ?=

help:
	@echo "Города не спят / Cities Never Sleep: команды"
	@echo "  make install    установить зависимости (uv sync)"
	@echo "  make all        полный прогон с нуля: данные, тренды, выгрузки, сайт"
	@echo "  make derive     тренды, выгрузка и сайт из готовых data/processed, без сети"
	@echo "  make fetch-pop  население и справочник городов из Wikidata"
	@echo "  make rasters    VNL по годам: скачать, обрезать по России (YEARS=2012-2024)"
	@echo "  make lights     яркость по городам"
	@echo "  make trends     тренды и классы"
	@echo "  make export     выгрузки для витрины"
	@echo "  make site       сборка web/dist"
	@echo "  make lint       ruff check"
	@echo "  make test       pytest"
	@echo "  make clean      удалить сырые и промежуточные данные (не processed)"

install:
	$(UV) sync --all-extras

# Полный прогон на чистой машине. Нужна сеть: Wikidata и Zenodo.
all: install fetch-pop rasters lights trends export site

# Без сети: всё, что считается из закоммиченных data/processed.
derive: trends
	$(UV) run cns export-web
	$(MAKE) site

fetch: fetch-vnl fetch-pop

fetch-vnl:
	$(UV) run cns fetch-vnl --years $(YEARS) $(if $(VNL_YEAR),--year $(VNL_YEAR),)

fetch-pop:
	$(UV) run cns fetch-pop

process process-vnl:
	$(UV) run cns process-vnl --years $(YEARS) $(if $(VNL_YEAR),--year $(VNL_YEAR),)

# По одному году: сырой растр удаляется после обрезки, чтобы не занимать диск
# (KEEP_RAW=1 оставляет его).
rasters:
	@set -e; for y in $$($(UV) run python -c "from citiesneversleep.sources.vnl_zenodo import parse_years_spec as p; print(*p('$(YEARS)'))"); do \
		$(UV) run cns fetch-vnl --year $$y; \
		$(UV) run cns process-vnl --year $$y; \
		if [ -z "$(KEEP_RAW)" ]; then rm -f data/raw/vnl/*_s_$${y}0101_*.tif; fi; \
	done

lights:
	$(UV) run cns build-lights --years $(YEARS)

trends:
	$(UV) run cns build-trends

export:
	$(UV) run cns export-web
	$(UV) run cns export-lightmap --year $(MAP_YEAR)

site:
	python3 web/build.py

lint:
	$(UV) run ruff check analytics tests scripts

test:
	$(UV) run pytest -q

clean:
	rm -rf data/raw/vnl data/interim/vnl
	@echo "Удалены data/raw/vnl и data/interim/vnl; data/processed сохранён."
