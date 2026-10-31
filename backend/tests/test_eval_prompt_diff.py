"""Paket 13 (D4): Text-Unterschied zweier Prompt-Fassungen (``GET /api/eval/prompt-diff``).

Der Vergleich nennt geänderte Prompt-Bausteine mit beiden Prüfsummen; diese Route liest die
Fassungen aus ``prompt_versions`` und liefert den Unterschied als Unified-Diff-Zeilen.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from boerdi.api.deps import get_session
from boerdi.db.models import PromptVersion
from boerdi.main import create_app
from boerdi.services.eval import prompt_diff
from boerdi.settings import get_settings

_ZEIT = datetime(2026, 10, 17, tzinfo=UTC)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _Result(self.rows)


def _fassung(h: str, text: str, art: str = "agent.kopf") -> PromptVersion:
    return PromptVersion(hash=h, art=art, text=text, erstmals=_ZEIT, zuletzt=_ZEIT)


def test_text_diff_zeigt_geaenderte_zeilen() -> None:
    zeilen = prompt_diff.text_diff("eins\nzwei\ndrei", "eins\nZWEI\ndrei")
    assert "-zwei" in zeilen and "+ZWEI" in zeilen
    assert prompt_diff.text_diff("gleich", "gleich") == []


def test_diff_zweier_fassungen() -> None:
    rows = [_fassung("aaaaaaaaaaaa", "Sie siezen.\nKurz."),
            _fassung("bbbbbbbbbbbb", "Du duzt.\nKurz.")]
    out = asyncio.run(prompt_diff.prompt_diff(_Session(rows), "aaaaaaaaaaaa", "bbbbbbbbbbbb"))
    assert out["a"] == {"hash": "aaaaaaaaaaaa", "art": "agent.kopf",
                        "erstmals": _ZEIT.isoformat(), "zuletzt": _ZEIT.isoformat()}
    assert out["gleiche_art"] is True
    assert "-Sie siezen." in out["diff"] and "+Du duzt." in out["diff"]


def test_unbekannte_fassung_ist_404() -> None:
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(prompt_diff.prompt_diff(_Session([_fassung("aaaaaaaaaaaa", "x")]),
                                            "aaaaaaaaaaaa", "bbbbbbbbbbbb"))
    assert fehler.value.status_code == 404


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: "S"
    return TestClient(app)


def test_route_reicht_beide_pruefsummen_weiter(client, monkeypatch) -> None:
    import boerdi.api.eval as eval_api

    aufrufe: list[tuple] = []

    async def fake(*args):
        aufrufe.append(args)
        return {"diff": []}

    monkeypatch.setattr(eval_api, "prompt_diff", fake)
    r = client.get("/api/eval/prompt-diff", params={"a": "aaaaaaaaaaaa", "b": "bbbbbbbbbbbb"},
                   headers={"X-Studio-Key": "k-studio-testkey"})
    assert r.status_code == 200 and aufrufe == [("S", "aaaaaaaaaaaa", "bbbbbbbbbbbb")]


@pytest.mark.parametrize("a", ["zu-kurz", "AAAAAAAAAAAA", "aaaaaaaaaaaa'--"])
def test_route_nimmt_nur_pruefsummen(client, a) -> None:
    r = client.get("/api/eval/prompt-diff", params={"a": a, "b": "bbbbbbbbbbbb"},
                   headers={"X-Studio-Key": "k-studio-testkey"})
    assert r.status_code == 422


def test_route_verlangt_den_studio_schluessel(client) -> None:
    r = client.get("/api/eval/prompt-diff", params={"a": "aaaaaaaaaaaa", "b": "bbbbbbbbbbbb"})
    assert r.status_code == 401
