"""Сборка витрины для GitHub Pages: страница и выгрузки analytics/exports в web/dist.

    python3 web/build.py            # сборка
    python3 -m http.server -d web/dist 8000   # локальный просмотр

Витрина ничего не пересчитывает (ADR-0001): сборка только копирует файлы.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
EXPORTS = ROOT / "analytics" / "exports"
DIST = WEB / "dist"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "data").mkdir(parents=True)
    shutil.copy2(WEB / "src" / "index.html", DIST / "index.html")
    for name in ("cities.json", "coastline.json"):
        shutil.copy2(EXPORTS / name, DIST / "data" / name)
    lightmaps = sorted(EXPORTS.glob("lightmap_*.png"))
    if lightmaps:
        shutil.copy2(lightmaps[-1], DIST / "data" / "lightmap.png")
        shutil.copy2(lightmaps[-1].with_suffix(".meta.json"), DIST / "data" / "lightmap.meta.json")
    (DIST / ".nojekyll").touch()
    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    data = json.loads((DIST / "data" / "cities.json").read_text(encoding="utf-8"))
    print(f"web/dist: {len(data['cities'])} городов, {size // 1024} КБ")


if __name__ == "__main__":
    main()
