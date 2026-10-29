"""Paket 18C/D (2.4): eine eigene Zugriffszeile statt Uvicorns.

Uvicorns Zeile trug je Anfrage die IP und den rohen Pfad — beim Verlaufsabruf mit der
Sitzungs-ID, die wie ein Schlüssel zum Verlauf wirkt. Die eigene Zeile nennt Methode,
Pfad-Vorlage, Status und Dauer; die Trace-ID steht ohnehin in jeder Zeile. Ausgelieferte
Dateien (Widget, Studio-Oberfläche) und die Liveness-Probe stehen nur auf DEBUG.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

import boerdi.api.sessions as sessions_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_SID = "bb-0123456789abcdef0123456789abcdef"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()

    async def _leer(*_a, **_k):
        return []

    monkeypatch.setattr(sessions_api, "get_messages", _leer)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    yield TestClient(app)
    get_settings.cache_clear()


def _zeilen(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "boerdi.zugriff"]


def test_der_verlaufsabruf_ohne_sitzungs_id_ip_und_abfrage(client, caplog):
    with caplog.at_level(logging.DEBUG, logger="boerdi.zugriff"):
        client.get(f"/api/sessions/{_SID}/messages?limit=5")
    (zeile,) = _zeilen(caplog)
    text = zeile.getMessage()
    assert zeile.levelno == logging.INFO
    assert "route=/api/sessions/{session_id}/messages" in text
    assert "methode=GET" in text and "status=200" in text and "dauer_ms=" in text
    assert _SID not in text and "limit" not in text and "testclient" not in text


def test_dateien_nur_auf_debug(client, caplog):
    with caplog.at_level(logging.DEBUG, logger="boerdi.zugriff"):
        client.get("/widget/boerdi-widget.js")
        client.get("/health")
    assert [r.levelno for r in _zeilen(caplog)] == [logging.DEBUG, logging.DEBUG]


@pytest.mark.parametrize("pfad,erwartet", [
    ("/studio/api/sessions/x/messages", "/studio/api/sessions/{session_id}/messages"),
    ("/studio/index.html", "/studio"),
])
def test_studio_aufrufe_mit_vorlage(client, caplog, pfad, erwartet):
    with caplog.at_level(logging.DEBUG, logger="boerdi.zugriff"):
        client.get(pfad)
    assert f"route={erwartet} " in _zeilen(caplog)[0].getMessage()


def test_uvicorns_zugriffszeile_ist_aus():
    from boerdi.serve import baue_server

    haupt, intern = baue_server(create_app(), create_app())
    assert haupt.config.access_log is False and intern.config.access_log is False
