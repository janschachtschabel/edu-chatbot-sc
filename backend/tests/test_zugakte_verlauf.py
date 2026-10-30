"""Paket 18C/D, Phase 1: wer die Zugakte im Verlauf sieht.

Der Verlauf (``GET /api/sessions/{id}/messages``) ist öffentlich — das Widget stellt damit ohne
Anmeldung wieder her. Die Zugakte (Werkzeug-Argumente, Fehlertexte, umgeschriebene Entwürfe) ist
Diagnose: sie kommt nur mit, wenn die Anlage selbst fragt — das Studio über seinen Proxy (nach
der Anmeldung) oder ein Aufruf mit Studio-Schlüssel. Bei offenem Tor (``BOERDI_ALLOW_OPEN_ADMIN``
ohne Passwort) kommt jeder durch den Proxy; ist zugleich ein Schlüssel gesetzt, setzt der Proxy
ihn nicht ein, und der Durchgang ist keine Freigabe (Review Phase 1, Befund 3).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.sessions as sessions_api
from boerdi.api import ratelimit
from boerdi.api.deps import get_session
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.main import create_app
from boerdi.settings import get_settings

_PASSWORT = "geheim-studio-pw"
_SCHLUESSEL = "backend-key"
_SID = "bb-0123456789abcdef0123456789abcdef"


def _client(monkeypatch, *, passwort: str | None, schluessel: str | None, offen: bool):
    for name, wert in (("STUDIO_PASSWORD", passwort), ("STUDIO_API_KEY", schluessel),
                       ("BOERDI_ALLOW_OPEN_ADMIN", "1" if offen else None)):
        if wert is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, wert)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    return TestClient(app)


@pytest.fixture()
def gefragt(monkeypatch) -> list[bool]:
    """Ob ``get_messages`` die Zugakte mitgeben sollte — je Aufruf."""
    aufrufe: list[bool] = []

    async def fake(session, session_id, limit=50, *, zugakte=False):
        aufrufe.append(zugakte)
        return []

    monkeypatch.setattr(sessions_api, "get_messages", fake)
    yield aufrufe
    get_settings.cache_clear()
    ratelimit.limiter.reset()


def test_anonym_ohne_zugakte(monkeypatch, gefragt):
    c = _client(monkeypatch, passwort=_PASSWORT, schluessel=_SCHLUESSEL, offen=False)
    assert c.get(f"/api/sessions/{_SID}/messages").status_code == 200
    assert gefragt == [False]


def test_mit_studio_schluessel_mit_zugakte(monkeypatch, gefragt):
    c = _client(monkeypatch, passwort=_PASSWORT, schluessel=_SCHLUESSEL, offen=False)
    c.get(f"/api/sessions/{_SID}/messages", headers={"X-Studio-Key": _SCHLUESSEL})
    assert gefragt == [True]


def test_das_angemeldete_studio_ueber_den_proxy_mit_zugakte(monkeypatch, gefragt):
    c = _client(monkeypatch, passwort=_PASSWORT, schluessel=_SCHLUESSEL, offen=False)
    c.cookies.set(COOKIE_NAME, studio_token(_PASSWORT))
    assert c.get(f"/studio/api/sessions/{_SID}/messages").status_code == 200
    assert gefragt == [True]


def test_offenes_tor_mit_schluessel_ist_keine_freigabe(monkeypatch, gefragt):
    c = _client(monkeypatch, passwort=None, schluessel=_SCHLUESSEL, offen=True)
    assert c.get(f"/studio/api/sessions/{_SID}/messages").status_code == 200
    assert gefragt == [False]


def test_reiner_entwicklungsmodus_bleibt_offen(monkeypatch, gefragt):
    # Ohne Passwort und ohne Schlüssel ist das ganze Studio offen — wie bisher.
    c = _client(monkeypatch, passwort=None, schluessel=None, offen=True)
    c.get(f"/studio/api/sessions/{_SID}/messages")
    assert gefragt == [True]


def _verlauf_mit_debug(monkeypatch):
    async def fake(session, session_id, limit=50, *, zugakte=False):
        return [{"id": 1, "role": "assistant", "content": "a",
                 "debug": {"pattern": "M06", "_type_focus": "Video", "persona": "P-LEH"},
                 **({"trace_id": "4711abcdef01xyz"} if zugakte else {})}]

    monkeypatch.setattr(sessions_api, "get_messages", fake)


def test_der_oeffentliche_verlauf_traegt_nur_ui(monkeypatch):
    """Paket 18C/D: ``ui`` mit den Wiederherstellungsfeldern; seit Phase 4 kein Debug-Block
    mehr ohne Freigabe."""
    _verlauf_mit_debug(monkeypatch)
    c = _client(monkeypatch, passwort=_PASSWORT, schluessel=_SCHLUESSEL, offen=False)
    (nachricht,) = c.get(f"/api/sessions/{_SID}/messages").json()
    assert nachricht["ui"] == {"pattern": "M06", "type_focus": "Video"}
    assert "debug" not in nachricht and "trace_id" not in nachricht


def test_das_studio_bekommt_debug_und_trace_id(monkeypatch):
    """Die Trace-ID je Nachricht führt im Studio zur Fehlernummer der Antwort (4.6)."""
    _verlauf_mit_debug(monkeypatch)
    c = _client(monkeypatch, passwort=_PASSWORT, schluessel=_SCHLUESSEL, offen=False)
    c.cookies.set(COOKIE_NAME, studio_token(_PASSWORT))
    (nachricht,) = c.get(f"/studio/api/sessions/{_SID}/messages").json()
    assert nachricht["debug"]["persona"] == "P-LEH"
    assert nachricht["trace_id"] == "4711abcdef01xyz"
