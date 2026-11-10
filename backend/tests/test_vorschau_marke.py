"""Plan 2026-11-10, TB-E2 (Nutzer-Entscheid N3): Gespräche aus der Studio-Vorschau zählen nicht als
Betrieb — auch die ohne Probe (Trockenlauf).

Das Widget der Vorschau schickt ``vorschau: true``. Wie bei der Probe gilt das nur mit gültigem
Studio-Cookie (``api/probe_anfrage``); dann merkt ``setup`` die Sitzung (``entities._vorschau``).
Anders als die Probe schränkt die Vorschau nichts ein: der Zug läuft echt, er zählt nur nicht mit.
Ein Flag ohne gültiges Cookie bleibt wirkungslos — **kein** 403, denn es ändert am Zug nichts.
"""

from __future__ import annotations

import pytest
from sqlalchemy import column
from sqlalchemy.dialects.postgresql import asyncpg
from starlette.requests import Request

from boerdi.api import probe_anfrage
from boerdi.api.chat import turn_kontext
from boerdi.api.schemas import ChatRequest
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.services import probe
from boerdi.services.session_origin import PROBE_SITZUNGEN_SQL, scope_clause
from boerdi.settings import get_settings

_PASSWORT = "ein-langes-studio-passwort"


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setenv("STUDIO_PASSWORD", _PASSWORT)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    marke = probe._merker.set(None)
    yield
    probe._merker.reset(marke)
    get_settings.cache_clear()


def _anfrage(cookie: str | None) -> Request:
    kopf = ([(b"cookie", f"{COOKIE_NAME}={cookie}".encode("latin-1"))]
            if cookie is not None else [])
    return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": kopf,
                    "client": ("127.0.0.1", 5000), "query_string": b""})


def _chat(**flags: bool) -> ChatRequest:
    return ChatRequest(session_id="sitzung-0123456789", message="hallo", **flags)


def test_vorschau_mit_gueltigem_cookie_gilt():
    assert probe_anfrage.vorschau_erlaubt(_anfrage(studio_token(_PASSWORT)), _chat(vorschau=True))


@pytest.mark.parametrize("cookie", [None, "", "falsch"])
def test_vorschau_ohne_gueltiges_cookie_bleibt_wirkungslos_ohne_403(cookie):
    assert probe_anfrage.vorschau_erlaubt(_anfrage(cookie), _chat(vorschau=True)) is False


def test_ohne_flag_wird_das_cookie_gar_nicht_gelesen(monkeypatch):
    gelesen: list = []
    monkeypatch.setattr(probe_anfrage, "authorize_request", lambda *a: gelesen.append(a))
    assert probe_anfrage.vorschau_erlaubt(_anfrage(studio_token(_PASSWORT)), _chat()) is False
    assert gelesen == []


def test_der_zug_kontext_traegt_die_vorschau():
    assert turn_kontext(_chat(), False, vorschau=True).vorschau is True
    assert turn_kontext(_chat(), False).vorschau is False


def test_eine_vorschau_merkt_sich_die_sitzung_ohne_trockenlauf():
    probe.binde(False, vorschau=True)
    entities: dict = {}
    assert probe.uebernehmen(entities) is True       # neu gesetzt — der Aufrufer schreibt fest
    assert entities[probe.VORSCHAU_KEY] is True and probe.ENTITY_KEY not in entities
    assert probe.aktiv() is False                    # die Vorschau schränkt nichts ein
    assert probe.uebernehmen(entities) is False      # schon gemerkt


def test_eine_probe_ist_auch_vorschau_aber_nicht_umgekehrt():
    # Review TB-E2, Befund 5: beide Richtungen
    probe.binde(True)
    entities: dict = {}
    probe.uebernehmen(entities)
    assert entities[probe.ENTITY_KEY] is True and entities[probe.VORSCHAU_KEY] is True
    probe.binde(False, vorschau=True)
    nur_vorschau: dict = {}
    probe.uebernehmen(nur_vorschau)
    assert probe.ENTITY_KEY not in nur_vorschau and probe.aktiv() is False


def test_der_herkunftsfilter_liest_die_spalte():
    """Review TB-E2, Befund 1: die Marke in ``entities`` leert die Aufbewahrung — der Filter liest
    die Spalte ``sessions.vorschau`` (Migration 0022)."""
    assert "probe_s.vorschau" in PROBE_SITZUNGEN_SQL and "entities" not in PROBE_SITZUNGEN_SQL
    sql = str(scope_clause("production", column("session_id")).compile(
        dialect=asyncpg.dialect(), compile_kwargs={"literal_binds": True}))
    assert "probe_s.vorschau" in sql
