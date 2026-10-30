"""Сводка пробного прогона: размеры файлов, время шагов, статистика растров и населения.

Пишет report.json и report.md в каталог --out; при запуске в GitHub Actions
дублирует Markdown в сводку запуска ($GITHUB_STEP_SUMMARY).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from citiesneversleep.paths import POP_PROCESSED_DIR, VNL_INTERIM_DIR, VNL_RAW_DIR


def _mb(path: Path) -> float:
    return round(path.stat().st_size / 1e6, 1)


DECIMATE = 4  # статистика по прореженной сетке 1:4, чтобы не держать весь растр в памяти


def raster_stats(path: Path) -> dict:
    with rasterio.open(path) as src:
        shape = (max(src.height // DECIMATE, 1), max(src.width // DECIMATE, 1))
        data = src.read(1, out_shape=shape).astype("float32")
        tags = src.tags()
        info = {
            "file": path.name,
            "size_mb": _mb(path),
            "shape": [src.height, src.width],
            "bounds": [round(v, 4) for v in src.bounds],
            "dtype": src.dtypes[0],
            "scale_note": tags.get("scale_note"),
        }
    valid = data[np.isfinite(data)]
    lit = valid[valid > 0]
    info.update(
        {
            "share_nan": round(1 - valid.size / data.size, 4),
            "share_lit": round(lit.size / max(valid.size, 1), 4),
            "min": round(float(valid.min()), 3) if valid.size else None,
            "p50_lit": round(float(np.median(lit)), 3) if lit.size else None,
            "p99_lit": round(float(np.percentile(lit, 99)), 3) if lit.size else None,
            "max": round(float(valid.max()), 3) if valid.size else None,
        }
    )
    return info


def population_stats() -> dict:
    df = pd.read_parquet(POP_PROCESSED_DIR / "ru_cities_population.parquet")
    recent = df[(df["year"] >= 2012) & (df["year"] <= 2024)]
    return {
        "rows": len(df),
        "cities": int(df["city_id"].nunique()),
        "cities_2012_2024": int(recent["city_id"].nunique()),
        "bad_oktmo": int((df["oktmo_status"] == "invalid").sum()),
    }


def to_markdown(report: dict) -> str:
    lines = [f"## Пробный прогон, VNL {report['year']}", ""]
    lines += [
        f"- загрузка: {report['fetch_sec']} с, обрезка: {report['process_sec']} с",
        f"- сырой файл: {report['raw']['file']}, {report['raw']['size_mb']} МБ",
        "",
        "Статистика по прореженной сетке 1:4.",
        "",
        "| Файл | МБ | Размер | Шкала | NaN | Освещено | p50 | p99 | max |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["interim"]:
        lines.append(
            f"| {r['file']} | {r['size_mb']} | {r['shape'][0]}×{r['shape'][1]} | "
            f"{r['scale_note']} | {r['share_nan']:.2%} | {r['share_lit']:.2%} | "
            f"{r['p50_lit']} | {r['p99_lit']} | {r['max']} |"
        )
    p = report["population"]
    lines += [
        "",
        f"Население: {p['rows']} строк, {p['cities']} городов, "
        f"{p['cities_2012_2024']} с данными за 2012–2024, "
        f"строк с некорректным ОКТМО: {p['bad_oktmo']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--out", type=Path, default=Path("smoke-report"))
    args = parser.parse_args()

    raw = sorted(VNL_RAW_DIR.glob(f"*_s_{args.year}0101_*.tif"))[0]
    interim = sorted(VNL_INTERIM_DIR.glob(f"vnl_russia_{args.year}*.tif"))
    report = {
        "year": args.year,
        "fetch_sec": int(os.environ.get("FETCH_SEC", -1)),
        "process_sec": int(os.environ.get("PROCESS_SEC", -1)),
        "raw": {"file": raw.name, "size_mb": _mb(raw)},
        "interim": [raster_stats(p) for p in interim],
        "population": population_stats(),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = to_markdown(report)
    (args.out / "report.md").write_text(md, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
