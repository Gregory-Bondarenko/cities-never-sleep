"""Общие фикстуры тестов.

Тесты не должны обращаться к сети: реальный HTTP-транспорт httpx заблокирован,
внешние сервисы подменяются через ``httpx.MockTransport``.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _deny(self, request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"Сетевой запрос в тестах запрещён: {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _deny)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Повторные попытки загрузчиков не должны замедлять тесты."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
