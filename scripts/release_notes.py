"""Версия пакета и текст раздела журнала для GitHub Release.

    python scripts/release_notes.py version       # 0.1.0
    python scripts/release_notes.py notes 0.1.0   # текст раздела [0.1.0]
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version(pyproject: Path = ROOT / "pyproject.toml") -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def is_release(version: str) -> bool:
    """Выпускаются только версии вида X.Y.Z без суффиксов dev, rc и т. п."""
    return re.fullmatch(r"\d+\.\d+\.\d+", version) is not None


def changelog_section(version: str, changelog: Path = ROOT / "CHANGELOG.md") -> str:
    text = changelog.read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)",
        text,
        flags=re.S | re.M,
    )
    if not match:
        raise SystemExit(f"В CHANGELOG.md нет раздела [{version}]")
    return match.group(1).strip() + "\n"


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "version":
        print(package_version())
    elif cmd == "notes" and len(sys.argv) == 3:
        sys.stdout.write(changelog_section(sys.argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
