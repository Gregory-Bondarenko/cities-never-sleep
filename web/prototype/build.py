"""Сборка прототипа: данные из analytics/exports/cities.json встраиваются в страницу.

    python3 web/prototype/build.py
"""

import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLS = {"растёт": 1, "стабилен": 0, "гаснет": -1, "мало данных": 9}


def main() -> None:
    d = json.loads((ROOT / "analytics/exports/cities.json").read_text(encoding="utf-8"))
    rows = []
    for c in d["cities"]:
        if c["lat"] is None:
            continue
        s = c["series"]
        rows.append([
            c["id"], c["name"], c["lat"], c["lon"], c["population"] or 0,
            CLS[c["lights_class"]], c["lights_pct"], CLS[c["population_class"]], c["population_pct"],
            1 if "point_source" in c["flags"] else 0,
            [None if v is None else round(v) for v in s["sol"]], s["lights_rel"], s["population"],
            c["decile"], CLS[c["lights_class_national"]],
        ])
    data = {"years": d["years"], "index": [d["national_index"][str(y)] for y in d["years"]], "c": rows}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    land = (HERE / "land_lines.json").read_text(encoding="utf-8")
    lm = {}
    lm_png = sorted((ROOT / "analytics/exports").glob("lightmap_*.png"))
    if lm_png:
        meta = json.loads(lm_png[-1].with_suffix(".meta.json").read_text(encoding="utf-8"))
        b64 = base64.b64encode(lm_png[-1].read_bytes()).decode()
        lm = {"src": f"data:image/png;base64,{b64}", "bounds": meta["bounds"], "year": meta["year"]}
    html = (
        (HERE / "template.html").read_text(encoding="utf-8")
        .replace("__DATA__", payload)
        .replace("__LAND__", land)
        .replace("__LIGHTMAP__", json.dumps(lm))
    )
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"{len(rows)} городов, {len(html) // 1024} КБ")


if __name__ == "__main__":
    main()
