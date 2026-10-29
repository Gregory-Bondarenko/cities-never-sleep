"""Загрузка годовых VIIRS VNL (OpenGeoHub) с Zenodo record 17294744."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path

import httpx
from tqdm import tqdm

from citiesneversleep.paths import VNL_RAW_DIR, ensure_data_dirs

ZENODO_RECORD_ID = "17294744"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"

# Годовые COG OpenGeoHub / EOG VNL V2.1, 500 м, EPSG:4326
# Год берём из стартовой даты; суффикс версии допускаем любой vYYYYMMDD.
VNL_FILENAME_RE = re.compile(
    r"^nightlights\.average_viirs\.v21_m_500m_s_(\d{4})0101_\d{4}1231"
    r"_go_epsg4326_v\d+\.tif$"
)

DEFAULT_YEARS = range(2012, 2025)  # 2012–2024 включительно


def parse_years_spec(spec: str) -> list[int]:
    """Разбор '2012-2024' или '2013,2015,2020'."""
    years: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            years.update(range(int(a), int(b) + 1))
        else:
            years.add(int(part))
    return sorted(years)


def list_vnl_files(client: httpx.Client | None = None) -> dict[int, dict]:
    """Вернуть {year: file_meta} для годовых average_viirs COG."""
    own = client is None
    client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        resp = client.get(ZENODO_API)
        resp.raise_for_status()
        files = resp.json().get("files", [])
        by_year: dict[int, dict] = {}
        for f in files:
            key = f.get("key") or f.get("filename") or ""
            m = VNL_FILENAME_RE.search(key)
            if not m:
                continue
            year = int(m.group(1))
            by_year[year] = f
        return by_year
    finally:
        if own:
            client.close()


def _file_download_url(meta: dict) -> str:
    links = meta.get("links") or {}
    # Zenodo API: content / download / self
    for k in ("content", "download", "self"):
        if links.get(k):
            return links[k]
    raise KeyError(f"Нет ссылки на скачивание в meta: {meta.get('key')}")


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def download_year(
    year: int,
    *,
    dest_dir: Path | None = None,
    client: httpx.Client | None = None,
    force: bool = False,
    meta_by_year: dict[int, dict] | None = None,
) -> Path:
    """Скачать один годовой GeoTIFF в data/raw/vnl/. Идемпотентно."""
    ensure_data_dirs()
    dest_dir = dest_dir or VNL_RAW_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    own = client is None
    client = client or httpx.Client(timeout=120.0, follow_redirects=True)
    try:
        catalog = meta_by_year or list_vnl_files(client)
        if year not in catalog:
            available = ", ".join(str(y) for y in sorted(catalog))
            raise ValueError(f"Год {year} не найден в Zenodo {ZENODO_RECORD_ID}. Есть: {available}")

        meta = catalog[year]
        filename = meta.get("key") or meta.get("filename")
        dest = dest_dir / filename
        expected_size = int(meta.get("size") or 0)
        checksums = meta.get("checksum") or ""
        # формат "md5:...."
        expected_md5 = checksums.split(":", 1)[1] if checksums.startswith("md5:") else None

        if dest.exists() and not force:
            if expected_size and dest.stat().st_size == expected_size:
                return dest
            # размер не совпал — перекачаем
            force = True

        url = _file_download_url(meta)
        partial = dest.with_suffix(dest.suffix + ".part")
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or expected_size or 0)
            with (
                partial.open("wb") as out,
                tqdm(
                    total=total or None,
                    unit="B",
                    unit_scale=True,
                    desc=f"VNL {year}",
                    leave=False,
                ) as bar,
            ):
                for chunk in resp.iter_bytes(1 << 20):
                    out.write(chunk)
                    bar.update(len(chunk))
        partial.replace(dest)

        if expected_size and dest.stat().st_size != expected_size:
            raise RuntimeError(
                f"Размер {dest.name}: ожидали {expected_size}, получили {dest.stat().st_size}"
            )
        if expected_md5:
            import hashlib as _hl

            h = _hl.md5()
            with dest.open("rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
            got = h.hexdigest()
            if got != expected_md5:
                raise RuntimeError(f"MD5 {dest.name}: ожидали {expected_md5}, получили {got}")

        _write_manifest_entry(dest_dir, year, dest, meta)
        return dest
    finally:
        if own:
            client.close()


def _write_manifest_entry(dest_dir: Path, year: int, path: Path, meta: dict) -> None:
    manifest_path = dest_dir / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[str(year)] = {
        "filename": path.name,
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "zenodo_checksum": meta.get("checksum"),
        "zenodo_record": ZENODO_RECORD_ID,
        "source": ZENODO_API,
    }
    payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    manifest_path.write_text(payload, encoding="utf-8")


def download_years(
    years: Iterable[int],
    *,
    dest_dir: Path | None = None,
    force: bool = False,
) -> list[Path]:
    """Скачать несколько лет; возвращает пути к файлам."""
    ensure_data_dirs()
    years = list(years)
    paths: list[Path] = []
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        catalog = list_vnl_files(client)
        for year in years:
            paths.append(
                download_year(
                    year,
                    dest_dir=dest_dir,
                    client=client,
                    force=force,
                    meta_by_year=catalog,
                )
            )
    return paths
