import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "release_notes", Path(__file__).resolve().parents[1] / "scripts" / "release_notes.py"
)
rn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rn)

CHANGELOG = """# Журнал

## [Unreleased]

## [0.2.0] - 2026-11-10

### Added

- Новое.

## [0.1.0] - 2026-10-30

### Added

- Старое.

[Unreleased]: https://example/compare
[0.1.0]: https://example/v0.1.0
"""


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.1.0", True), ("1.12.3", True), ("0.2.0.dev0", False), ("0.2.0-dev", False)],
)
def test_is_release(version, expected):
    assert rn.is_release(version) is expected


def test_changelog_section(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG, encoding="utf-8")
    assert rn.changelog_section("0.2.0", path) == "### Added\n\n- Новое.\n"
    assert rn.changelog_section("0.1.0", path) == "### Added\n\n- Старое.\n"
    with pytest.raises(SystemExit):
        rn.changelog_section("9.9.9", path)


def test_repo_version_has_changelog_section():
    version = rn.package_version()
    if rn.is_release(version):
        assert rn.changelog_section(version).strip()
