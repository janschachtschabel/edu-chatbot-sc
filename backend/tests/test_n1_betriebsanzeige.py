"""Plan 2026-11-19, N1: die Betriebsanzeige — welche b-api-Betriebsart der Chatbot zuletzt bei
einer Nutzeranfrage sah (Delegation, durchgereichter Schlüssel, direkt), mit Zeitpunkt, je Prozess.
Nie ein Wert. Sichtbar in ``/api/health`` (hinter dem Studio-Schlüssel), nicht in ``/health``.

Dass ``B_API_KEY_MODE`` ohne, leer oder unbekannt ``auto`` ist, pinnt schon
``test_llm_auth.test_ohne_gueltigen_modus_gilt_auto``."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from boerdi.api.turn_auth import uebernimm_zugang
from boerdi.main import create_app
from boerdi.services import b_api_betrieb, llm_auth
from boerdi.settings import get_settings

TOKEN = "bdt_" + "t" * 40
SCHLUESSEL = "k" * 36
STUDIO = "studio-schluessel-fuer-den-test-0123456789"


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example.org/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", "env-schluessel-der-anlage")
    monkeypatch.delenv("B_API_KEY_MODE", raising=False)
    get_settings.cache_clear()
    b_api_betrieb.zuruecksetzen()
    llm_auth.setze_llm_schluessel(None)
    yield monkeypatch
    b_api_betrieb.zuruecksetzen()
    llm_auth.setze_llm_schluessel(None)
    get_settings.cache_clear()


def _anfrage(kopf: dict[str, str]) -> Request:
    roh = [(k.lower().encode(), v.encode()) for k, v in kopf.items()]
    return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": roh,
                    "client": ("203.0.113.7", 1234)})


def _zug(kopf: dict[str, str]) -> None:
    asyncio.run(uebernimm_zugang(_anfrage(kopf)))


# ── Merken ───────────────────────────────────────────────────────────────────

def test_ohne_nutzerzug_ist_nichts_gesehen():
    stand = b_api_betrieb.stand()
    assert stand == {"modus": "auto", "zuletzt": None, "zuletzt_am": None, "abgewiesen": 0,
                     "warnungen": []}


@pytest.mark.parametrize(("kopf", "art"), [
    ({"Authorization": f"Bearer {TOKEN}"}, "delegation"),
    ({"Authorization": f"Bearer {SCHLUESSEL}"}, "schluessel"),
    ({}, "direkt"),
])
def test_ein_nutzerzug_setzt_art_und_zeit(kopf, art):
    _zug(kopf)
    stand = b_api_betrieb.stand()
    assert stand["zuletzt"] == art
    assert datetime.fromisoformat(stand["zuletzt_am"]).tzinfo is not None


def test_die_letzte_art_gilt():
    _zug({"Authorization": f"Bearer {TOKEN}"})
    _zug({})
    assert b_api_betrieb.stand()["zuletzt"] == "direkt"


def test_ein_zug_der_anlage_zaehlt_nicht(_frisch):
    _frisch.setenv("STUDIO_API_KEY", STUDIO)
    get_settings.cache_clear()
    _zug({"X-Studio-Key": STUDIO})
    assert b_api_betrieb.stand()["zuletzt"] is None


def test_im_static_modus_ist_jeder_zug_direkt(_frisch):
    _frisch.setenv("B_API_KEY_MODE", "static")
    get_settings.cache_clear()
    _zug({"Authorization": f"Bearer {TOKEN}"})
    assert b_api_betrieb.stand() | {"zuletzt_am": None} == {
        "modus": "static", "zuletzt": "direkt", "zuletzt_am": None, "abgewiesen": 0,
        "warnungen": []}


# ── Warnungen ────────────────────────────────────────────────────────────────

def test_forward_warnt_erst_nach_einer_abweisung(_frisch):
    """Review N1/N2, MINOR 1: direkt nach dem Start ist „kein Token“ kein Befund."""
    _frisch.setenv("B_API_KEY_MODE", "forward")
    get_settings.cache_clear()
    assert b_api_betrieb.stand()["warnungen"] == []
    with pytest.raises(HTTPException):
        _zug({})
    stand = b_api_betrieb.stand()
    assert stand["warnungen"] == ["forward_ohne_token"] and stand["abgewiesen"] == 1
    _zug({"Authorization": f"Bearer {SCHLUESSEL}"})
    assert b_api_betrieb.stand()["warnungen"] == []


def test_forward_ohne_b_api_weist_nicht_ab_und_warnt_nicht(_frisch):
    _frisch.setenv("B_API_KEY_MODE", "forward")
    _frisch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    _zug({})
    assert b_api_betrieb.stand()["abgewiesen"] == 0
    assert b_api_betrieb.stand()["warnungen"] == []


def _delegationszuege(anzahl: int, **kopf: str) -> None:
    for _ in range(anzahl):
        _zug({"Authorization": f"Bearer {TOKEN}", **kopf})


def test_zugangsblock_hinweis_erst_ab_zwanzig_delegationszuegen():
    """Review N1/N2, MINOR 4: bei rein anonymer Nutzung fehlt der Block immer — erst eine
    deutliche Zahl von Zügen ohne ihn ist ein Hinweis."""
    _delegationszuege(b_api_betrieb.ZUGANGSBLOCK_AB - 1)
    assert b_api_betrieb.stand()["warnungen"] == []
    _delegationszuege(1)
    assert b_api_betrieb.stand()["warnungen"] == ["zugangsblock_fehlt"]


def test_einmal_angekommen_genuegt():
    _delegationszuege(1, **{"WLO-Access-Block": "x" * 40})
    _delegationszuege(b_api_betrieb.ZUGANGSBLOCK_AB + 5)
    assert b_api_betrieb.stand()["warnungen"] == []


def test_ohne_delegation_kein_zugangsblock_hinweis():
    _zug({"Authorization": f"Bearer {SCHLUESSEL}"})
    _zug({})
    assert b_api_betrieb.stand()["warnungen"] == []


# ── Anzeige ──────────────────────────────────────────────────────────────────

def test_api_health_nennt_die_betriebsart_ohne_wert(_frisch):
    _frisch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    get_settings.cache_clear()
    _delegationszuege(b_api_betrieb.ZUGANGSBLOCK_AB)
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 200
    b_api = r.json()["b_api"]
    assert b_api["modus"] == "auto" and b_api["zuletzt"] == "delegation"
    assert b_api["zuletzt_am"] and b_api["warnungen"] == ["zugangsblock_fehlt"]
    assert "seit" not in b_api
    assert TOKEN not in r.text and "env-schluessel-der-anlage" not in r.text


def test_die_oeffentliche_liveness_bleibt_ohne_betriebsart():
    _zug({"Authorization": f"Bearer {TOKEN}"})
    r = TestClient(create_app()).get("/health")
    assert r.json() == {"status": "ok"}
