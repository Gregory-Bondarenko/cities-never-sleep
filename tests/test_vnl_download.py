"""Загрузчик VNL с Zenodo на подменённом HTTP."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from citiesneversleep.sources.vnl_zenodo import ZENODO_API, download_year, list_vnl_files

PAYLOAD = b"fake-cog-bytes" * 100
NAME_2013 = "nightlights.average_viirs.v21_m_500m_s_20130101_20131231_go_epsg4326_v20250904.tif"
NAME_DMSP = "nightlights.average_dmsp.v10_m_1km_s_19920101_20241231_go_epsg4326_v20251006.tif"
FILE_URL = "https://zenodo.example/files/2013.tif"


def _record(md5: str | None = None) -> dict:
    return {
        "files": [
            {
                "key": NAME_2013,
                "size": len(PAYLOAD),
                "checksum": f"md5:{md5 or hashlib.md5(PAYLOAD).hexdigest()}",
                "links": {"content": FILE_URL},
            },
            {"key": NAME_DMSP, "size": 1, "links": {"content": "https://zenodo.example/x"}},
        ]
    }


def _client(record: dict, calls: list[str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if str(request.url) == ZENODO_API:
            return httpx.Response(200, json=record)
        if str(request.url) == FILE_URL:
            return httpx.Response(200, content=PAYLOAD)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_list_vnl_files_keeps_only_viirs_annual():
    with _client(_record()) as client:
        catalog = list_vnl_files(client)
    assert list(catalog) == [2013]
    assert catalog[2013]["key"] == NAME_2013


def test_download_year_writes_file_and_manifest(tmp_path):
    with _client(_record()) as client:
        path = download_year(2013, dest_dir=tmp_path, client=client)

    assert path.read_bytes() == PAYLOAD
    assert not path.with_suffix(".tif.part").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["2013"]["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert manifest["2013"]["size"] == len(PAYLOAD)


def test_download_year_is_idempotent(tmp_path):
    with _client(_record()) as client:
        download_year(2013, dest_dir=tmp_path, client=client)

    calls: list[str] = []
    with _client(_record(), calls) as client:
        download_year(2013, dest_dir=tmp_path, client=client)
    assert FILE_URL not in calls


def test_download_year_rejects_md5_mismatch(tmp_path):
    with _client(_record(md5="0" * 32)) as client, pytest.raises(RuntimeError, match="MD5"):
        download_year(2013, dest_dir=tmp_path, client=client)


def test_download_year_unknown_year(tmp_path):
    with _client(_record()) as client, pytest.raises(ValueError, match="2030"):
        download_year(2030, dest_dir=tmp_path, client=client)
