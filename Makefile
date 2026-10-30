.PHONY: help install fetch fetch-vnl fetch-pop process process-vnl lint test clean

UV ?= uv
YEARS ?= 2012-2024
VNL_YEAR ?=

help:
	@echo "Города не спят / Cities Never Sleep — команды:"
	@echo "  make install       — установить зависимости (uv sync)"
	@echo "  make fetch         — скачать VNL (Zenodo) + население (Wikidata)"
	@echo "  make fetch-vnl     — только VIIRS VNL с Zenodo (YEARS=2012-2024)"
	@echo "  make fetch-pop     — только население из Wikidata SPARQL"
	@echo "  make process       — обрезка VNL по России"
	@echo "  make lint          — ruff check"
	@echo "  make test          — pytest"
	@echo "  make clean         — удалить сырые/interim данные (не processed)"

install:
	$(UV) sync --all-extras

fetch: fetch-vnl fetch-pop

fetch-vnl:
	$(UV) run cns fetch-vnl --years $(YEARS) $(if $(VNL_YEAR),--year $(VNL_YEAR),)

fetch-pop:
	$(UV) run cns fetch-pop

process process-vnl:
	$(UV) run cns process-vnl --years $(YEARS) $(if $(VNL_YEAR),--year $(VNL_YEAR),)

lint:
	$(UV) run ruff check analytics tests scripts

test:
	$(UV) run pytest -q

clean:
	rm -rf data/raw/vnl data/interim/vnl
	@echo "Удалены data/raw/vnl и data/interim/vnl; data/processed сохранён."
