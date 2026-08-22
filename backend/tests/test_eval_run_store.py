"""``run_store._ensure_chat_reachable`` — der Preflight vor jedem Eval-Start.

Nachlauf zum Review 2026-08-22: ein Studio-Lauf gegen ein totes
``EVAL_CHAT_URL`` (Backend auf 8100, Default zeigt auf 8000) verbrannte alle
44 Züge in "(chat error: All connection attempts failed)" und stand danach
als „fertig" in der Liste. Der Preflight bricht den START ab und nennt URL
und Stellschraube — bevor ein Lauf-Datensatz entsteht oder Kosten anfallen.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from boerdi.services.eval import run_store


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeClient:
    """Nachbau der einen benutzten httpx-Naht: async context + get."""

    def __init__(self, *, exc: Exception | None = None, status: int = 200) -> None:
        self._exc = exc
        self._status = status
        self.urls: list[str] = []

    def __call__(self, **_kwargs):  # httpx.AsyncClient(timeout=...)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, url: str):
        self.urls.append(url)
        if self._exc is not None:
            raise self._exc
        return _Resp(self._status)


def test_erreichbarer_chat_laesst_den_start_durch(monkeypatch) -> None:
    fake = _FakeClient(status=200)
    monkeypatch.setattr(run_store.httpx, "AsyncClient", fake)
    monkeypatch.setenv("EVAL_CHAT_URL", "http://127.0.0.1:8100/api/chat")

    asyncio.run(run_store._ensure_chat_reachable())

    assert fake.urls == ["http://127.0.0.1:8100/api/health"]


def test_auch_ein_404_zaehlt_als_erreichbar(monkeypatch) -> None:
    """Nur Transportfehler blocken: ein fremdes Backend ohne /api/health
    antwortet trotzdem — erreichbar ist erreichbar."""
    monkeypatch.setattr(run_store.httpx, "AsyncClient", _FakeClient(status=404))
    monkeypatch.setenv("EVAL_CHAT_URL", "http://127.0.0.1:8100/api/chat")

    asyncio.run(run_store._ensure_chat_reachable())


def test_toter_chat_bricht_mit_502_und_nennt_die_stellschraube(monkeypatch) -> None:
    monkeypatch.setattr(
        run_store.httpx, "AsyncClient", _FakeClient(exc=ConnectionError("refused"))
    )
    monkeypatch.delenv("EVAL_CHAT_URL", raising=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run_store._ensure_chat_reachable())

    assert exc.value.status_code == 502
    assert "http://localhost:8000/api/chat" in exc.value.detail
    assert "EVAL_CHAT_URL" in exc.value.detail
