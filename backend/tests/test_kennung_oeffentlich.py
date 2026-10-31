"""Paket 19 (Audit 2026-10-31): die Sitzungskennung an den öffentlichen Eingängen.

M-5: Ob eine Sitzung als Betrieb oder als Eval/Lasttest/Studio-Probe zählt, liest die Anlage am
Präfix der Kennung (``services/session_origin``) — und die Kennung wählt der Client. Wer
``eval-…`` schickte, verschwand aus „production“ (Kosten, Nutzung, Qualität, Sitzungsliste).
Jetzt weisen ``/api/chat`` und ``/api/chat/stream`` die reservierten Präfixe ab (422), außer für
Züge der Anlage (``darf_diagnose``: Studio-Proxy, gültiger Studio-Schlüssel, reiner
Entwicklungsmodus). ``/api/agent`` kennt keine Sitzungskennung.

N-9: Die Kennung ist am offenen Lese-Endpunkt ``GET /api/sessions/{id}/messages`` der einzige
Schlüssel. Kürzer als 16 Zeichen antwortet er wie für eine unbekannte Sitzung (leere Liste), ohne
die Datenbank zu fragen — nur für öffentliche Aufrufer; das Studio liest auch alte kurze Kennungen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
import boerdi.api.sessions as sessions_api
from boerdi.api.deps import get_session, get_session_factory
from boerdi.api.schemas import ChatResponse
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.main import create_app
from boerdi.settings import get_settings

_SCHLUESSEL = "studio-schluessel-fuer-kennungen"
_PASSWORT = "studio-passwort-fuer-kennungen"


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", _SCHLUESSEL)
    monkeypatch.setenv("STUDIO_PASSWORD", _PASSWORT)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    class _Graph:
        async def ainvoke(self, state):
            return {"response": ChatResponse(session_id="x", content="OK")}

    async def _pp(req, resp, *a, **k):
        return resp

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _pp)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_session_factory] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


def _chat(client: TestClient, sid: str, pfad: str = "/api/chat", **koepfe: str):
    return client.post(pfad, json={"session_id": sid, "message": "hallo"}, headers=koepfe)


# ── M-5: reservierte Präfixe ───────────────────────────────────────────────


@pytest.mark.parametrize("sid", ["eval-abc123", "loadtest-run-s0-1", "studio-0123"])
@pytest.mark.parametrize("pfad", ["/api/chat", "/api/chat/stream"])
def test_reservierte_praefixe_werden_oeffentlich_abgewiesen(client, sid, pfad):
    r = _chat(client, sid, pfad)
    assert r.status_code == 422
    assert "reserved" in r.json()["detail"]


@pytest.mark.parametrize("sid", ["bb-0123456789abcdef", "Eval-gross-0123456789",
                                 "evaluation-0123456789", "mein-eval-0123456789"])
def test_andere_kennungen_bleiben_offen(client, sid):
    assert _chat(client, sid).status_code == 200


def test_mit_studio_schluessel_erlaubt(client):
    assert _chat(client, "eval-abc123", **{"X-Studio-Key": _SCHLUESSEL}).status_code == 200
    assert _chat(client, "loadtest-x-s0-1", **{"X-Studio-Key": _SCHLUESSEL}).status_code == 200


def test_mit_falschem_schluessel_abgewiesen(client):
    assert _chat(client, "eval-abc123", **{"X-Studio-Key": "falsch"}).status_code == 422


def test_ueber_den_studio_proxy_erlaubt(client):
    """Die Chat-Probe im Studio schickt ``studio-<uuid>`` über ``/studio/api/chat``."""
    client.cookies.set(COOKIE_NAME, studio_token(_PASSWORT))
    r = client.post("/studio/api/chat", json={"session_id": "studio-0123", "message": "x"},
                    headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200


def test_im_reinen_entwicklungsmodus_erlaubt(client, monkeypatch):
    """Lokal ohne Schlüssel (``BOERDI_ALLOW_OPEN_ADMIN``) laufen Lasttest und Eval weiter."""
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    get_settings.cache_clear()
    assert _chat(client, "loadtest-x-s0-1").status_code == 200


# ── N-9 am Chat (Review, Punkt 1) ──────────────────────────────────────────
# Der Chat lädt den Verlauf der Kennung in den Prompt („wiederhole unser Gespräch“) — eine kurze
# Kennung wäre dort derselbe Schlüssel wie am Lese-Endpunkt.


@pytest.mark.parametrize("pfad", ["/api/chat", "/api/chat/stream"])
@pytest.mark.parametrize("sid", ["a", "bb-1", "bb-0123456789ab"])
def test_kurze_kennungen_am_chat_abgewiesen(client, pfad, sid):
    r = _chat(client, sid, pfad)
    assert r.status_code == 422
    assert "16" in r.json()["detail"]


def test_sechzehn_zeichen_am_chat_genuegen(client):
    assert _chat(client, "bb-0123456789abc").status_code == 200


def test_kurze_kennung_fuer_zuege_der_anlage(client):
    assert _chat(client, "bb-1", **{"X-Studio-Key": _SCHLUESSEL}).status_code == 200


# ── N-9: Mindestlänge am offenen Lese-Endpunkt ─────────────────────────────


@pytest.fixture()
def gelesen(monkeypatch) -> list[str]:
    aufrufe: list[str] = []

    async def _messages(_session, sid, *_a, **_k):
        aufrufe.append(sid)
        return [{"id": 1, "role": "user", "content": "hallo", "debug": {}}]

    monkeypatch.setattr(sessions_api, "get_messages", _messages)
    return aufrufe


def test_kurze_kennung_antwortet_wie_unbekannt(client, gelesen):
    r = client.get("/api/sessions/bb-kurz-1234/messages")
    assert r.status_code == 200
    assert r.json() == []
    assert gelesen == []  # die Datenbank wurde nicht gefragt
    assert r.headers["cache-control"] == "private, no-store"


def test_sechzehn_zeichen_genuegen(client, gelesen):
    sid = "bb-0123456789abc"
    assert len(sid) == 16
    r = client.get(f"/api/sessions/{sid}/messages")
    assert r.status_code == 200
    assert gelesen == [sid]


def test_das_studio_liest_auch_kurze_kennungen(client, gelesen):
    r = client.get("/api/sessions/eval-1/messages", headers={"X-Studio-Key": _SCHLUESSEL})
    assert r.status_code == 200
    assert gelesen == ["eval-1"]


def test_lasttest_kennungen_sind_lang_und_zufaellig():
    import re

    from boerdi.services.loadtest import lasttest_kennung

    a, b = lasttest_kennung("0123456789ab", 2), lasttest_kennung("0123456789ab", 2)
    assert a != b
    assert re.fullmatch(r"loadtest-01234567-s2-[0-9a-f]{32}", a)
