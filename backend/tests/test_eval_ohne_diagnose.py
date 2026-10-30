"""Paket 18C/D (3.5): Auswertung und Golden-Läufe brauchen den Debug-Block.

Ab Phase 4 bekommt ihn nur, wer intern fragt (Studio-Proxy oder Studio-Schlüssel). Ohne ihn
zählten Runner und Golden-Lauf still nichts — kein Muster, keine Werkzeuge, keine Spur (Plan
R3). Deshalb: der Golden-Lauf schickt den Schlüssel an die eigene Anlage, wie der Runner seit
Review-Runde 3; und der Runner warnt, wenn eine Antwort ohne Debug-Block kommt.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path

import pytest

from boerdi.services.eval import runner

_EVALS = Path(__file__).resolve().parents[2] / "evals"
_spec = importlib.util.spec_from_file_location("run_golden", _EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


class _Antwort:
    def __init__(self, daten: dict) -> None:
        self._daten = daten

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._daten


def _client_mit(daten: dict):
    class _Client:
        def __init__(self, *_a, **_k) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a) -> None:
            return None

        async def post(self, *_a, **_k):
            return _Antwort(daten)

    return _Client


def test_der_runner_warnt_einmal_wenn_der_debug_block_fehlt(monkeypatch, caplog):
    runner._warne_ohne_diagnose.cache_clear()
    monkeypatch.setattr(runner.httpx, "AsyncClient", _client_mit({"content": "x"}))
    url = "https://fremd.example.org/api/chat"
    with caplog.at_level(logging.WARNING, logger=runner.logger.name):
        asyncio.run(runner._post_chat(url, "a"))
        asyncio.run(runner._post_chat(url, "b"))
    warnungen = [r for r in caplog.records if "Debug-Block" in r.getMessage()]
    assert len(warnungen) == 1


def test_mit_debug_block_keine_warnung(monkeypatch, caplog):
    runner._warne_ohne_diagnose.cache_clear()
    monkeypatch.setattr(runner.httpx, "AsyncClient",
                        _client_mit({"content": "x", "debug": {"pattern": "M04"}}))
    with caplog.at_level(logging.WARNING, logger=runner.logger.name):
        asyncio.run(runner._post_chat("http://127.0.0.1:8100/api/chat", "a"))
    assert not [r for r in caplog.records if "Debug-Block" in r.getMessage()]


@pytest.mark.parametrize("url,erwartet", [
    ("http://127.0.0.1:8100/api/chat", {"X-Studio-Key": "geheim"}),
    ("http://localhost:8000/api/chat", {"X-Studio-Key": "geheim"}),
    ("https://chat.example.org/api/chat", {}),
])
def test_golden_schickt_den_schluessel_nur_an_die_eigene_anlage(monkeypatch, url, erwartet):
    monkeypatch.setenv("STUDIO_API_KEY", "geheim")
    assert rg.mit_studio_schluessel({}, url) == erwartet


def test_golden_laesst_einen_ausdruecklichen_schluessel_stehen(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "geheim")
    koepfe = {"x-studio-key": "eigener"}
    assert rg.mit_studio_schluessel(koepfe, "http://127.0.0.1/api/chat") == koepfe


def test_golden_ohne_schluessel_bleibt_ohne(monkeypatch):
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    assert rg.mit_studio_schluessel({}, "http://127.0.0.1/api/chat") == {}


def test_golden_schickt_keinen_platzhalter(monkeypatch):
    # Review Phase 3: wie der Runner (``settings.studio_schluessel``) — ``CHANGE_ME`` zählt
    # als nicht gesetzt.
    monkeypatch.setenv("STUDIO_API_KEY", "CHANGE_ME_long_random")
    assert rg.mit_studio_schluessel({}, "http://127.0.0.1/api/chat") == {}
