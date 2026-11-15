"""Сравнение выгрузки после полного прогона с закоммиченной (workflow reproduce).

Печатает аннотации GitHub Actions. Расхождения допустимы: данные Wikidata
меняются между прогонами. Ошибкой считается только непригодный результат:
нет выгрузки, слишком мало городов или сильный сдвиг классов.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

EXPORT = Path("analytics/exports/cities.json")
MAX_CLASS_SHIFT = 0.05  # доля городов, сменивших класс яркости


def main() -> int:
    new = json.loads(EXPORT.read_text(encoding="utf-8"))
    old = json.loads(
        subprocess.run(
            ["git", "show", f"HEAD:{EXPORT}"], check=True, capture_output=True, text=True
        ).stdout
    )
    a = {c["id"]: c for c in old["cities"]}
    b = {c["id"]: c for c in new["cities"]}
    common = a.keys() & b.keys()
    changed = [i for i in common if a[i]["lights_class"] != b[i]["lights_class"]]
    drift = max(
        (abs((a[i]["lights_pct"] or 0) - (b[i]["lights_pct"] or 0)) for i in common),
        default=0.0,
    )
    counts = Counter(c["lights_class"] for c in new["cities"])
    print(
        f"::notice title=reproduce::городов {len(b)} (в репозитории {len(a)}), "
        f"добавлено {len(b.keys() - a.keys())}, пропало {len(a.keys() - b.keys())}; "
        f"класс яркости сменили {len(changed)}; "
        f"наибольшее расхождение тренда {drift * 100:.2f} п. п. в год; классы {dict(counts)}"
    )
    share = len(changed) / max(1, len(common))
    if len(b) < 0.95 * len(a) or share > MAX_CLASS_SHIFT:
        print(f"::error title=reproduce::результат расходится с репозиторием: {share:.1%} классов")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
