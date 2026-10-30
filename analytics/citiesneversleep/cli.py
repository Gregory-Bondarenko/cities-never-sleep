"""CLI: cns — загрузка и обработка данных «Города не спят»."""

from __future__ import annotations

import typer
from rich.console import Console

from citiesneversleep import __version__
from citiesneversleep.sources.vnl_zenodo import DEFAULT_YEARS, download_years, parse_years_spec

app = typer.Typer(
    name="cns",
    help="Города не спят / Cities Never Sleep — CLI пайплайна ночных огней.",
    no_args_is_help=True,
)
console = Console()


def _resolve_years(years: str | None, year: int | None) -> list[int]:
    if year is not None:
        return [year]
    if years:
        return parse_years_spec(years)
    return list(DEFAULT_YEARS)


def _pop_summary(df) -> str:
    if not len(df):
        return "0 строк"
    invalid = df.loc[df["oktmo_status"] == "invalid", "city_id"].nunique()
    return f"{len(df)} строк, {df['city_id'].nunique()} городов, некорректный ОКТМО у {invalid}"


@app.callback()
def main() -> None:
    """Пайплайн данных проекта «Города не спят»."""


@app.command("version")
def version_cmd() -> None:
    """Показать версию пакета."""
    console.print(f"cities-never-sleep {__version__}")


@app.command("fetch-vnl")
def fetch_vnl(
    years: str | None = typer.Option(
        "2012-2024",
        "--years",
        help="Диапазон или список лет, напр. 2012-2024 или 2013,2020",
    ),
    year: int | None = typer.Option(
        None, "--year", help="Один год (перекрывает --years)"
    ),
    force: bool = typer.Option(False, "--force", help="Перекачать, даже если файл есть"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Только показать, что будет скачано"
    ),
) -> None:
    """Скачать годовые VNL COG с Zenodo (OpenGeoHub, record 17294744)."""
    selected = _resolve_years(years, year)
    if dry_run:
        from citiesneversleep.sources.vnl_zenodo import list_vnl_files

        catalog = list_vnl_files()
        console.print(f"[bold]Zenodo 17294744[/bold]: в каталоге {len(catalog)} годовых COG")
        for y in selected:
            meta = catalog.get(y)
            if meta:
                size_mb = int(meta.get("size") or 0) / 1e6
                console.print(f"  {y}: {meta.get('key')} (~{size_mb:.0f} МБ)")
            else:
                console.print(f"  {y}: [red]нет в каталоге[/red]")
        return

    console.print(f"Скачиваю VNL за годы: {selected}")
    paths = download_years(selected, force=force)
    for p in paths:
        console.print(f"  ✓ {p}")


@app.command("fetch-pop")
def fetch_pop(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Проверить SPARQL, не писать файлы"
    ),
) -> None:
    """Скачать население городов РФ из Wikidata SPARQL."""
    from citiesneversleep.sources.wikidata_pop import (
        fetch_and_save,
        fetch_sparql,
        rows_to_dataframe,
    )

    if dry_run:
        rows = fetch_sparql()
        df = rows_to_dataframe(rows)
        console.print(f"[bold]Wikidata[/bold]: {_pop_summary(df)}")
        return

    parquet_path, csv_path, df = fetch_and_save()
    console.print(f"Сохранено: {_pop_summary(df)} →\n  {parquet_path}\n  {csv_path}")


@app.command("process-vnl")
def process_vnl(
    years: str | None = typer.Option("2012-2024", "--years"),
    year: int | None = typer.Option(None, "--year"),
    no_scale_fix: bool = typer.Option(
        False,
        "--no-scale-fix",
        help="Не делить 2012–2021 на 10 (оставить как в файле)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Проверить наличие сырых файлов"
    ),
) -> None:
    """Обрезать скачанные VNL по bbox России (+ Чукотка)."""
    from citiesneversleep.process.crop import crop_years, find_raw_for_year

    selected = _resolve_years(years, year)
    if dry_run:
        for y in selected:
            try:
                p = find_raw_for_year(y)
                console.print(f"  {y}: {p.name}")
            except FileNotFoundError as exc:
                console.print(f"  {y}: [red]{exc}[/red]")
        return

    console.print(f"Обрезаю VNL по России: {selected}")
    paths = crop_years(selected, apply_scale_fix=not no_scale_fix)
    for p in paths:
        console.print(f"  ✓ {p}")


@app.command("fetch")
def fetch_all(
    years: str | None = typer.Option("2012-2024", "--years"),
    year: int | None = typer.Option(None, "--year"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Скачать VNL и население (fetch-vnl + fetch-pop)."""
    fetch_vnl(years=years, year=year, force=False, dry_run=dry_run)
    fetch_pop(dry_run=dry_run)


if __name__ == "__main__":
    app()
