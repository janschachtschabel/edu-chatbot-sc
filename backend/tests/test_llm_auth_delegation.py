"""Paket D (Plan 2026-11-17, E3/E4): das Delegations-Token der b-api durchreichen.

Seit dem 10.11. reicht der b-api-Proxy (``forwardDelegation``) statt eines Schlüssels ein
verschlüsseltes Token ``Authorization: Bearer bdt_…`` unbekannter Länge. Der Chatbot gibt es bei
jedem b-api-Aufruf unverändert weiter, nie zusammen mit ``X-API-KEY``, nie geloggt. Es gilt nur,
solange die eingehende Anfrage läuft. **Mit Delegation nie Rückfall auf ``B_API_KEY``**: ein still
verworfenes Token liefe sonst ohne Person.
"""

from __future__ import annotations

import logging

import pytest
from starlette.requests import Request

from boerdi.services import llm, llm_auth
from boerdi.services.llm_models import get_chat_model
from boerdi.settings import get_settings

ENV_SCHLUESSEL = "env-schluessel-der-anlage"
SCHLUESSEL = "k" * 36
TOKEN = "bdt_" + "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0." * 15  # 600 Zeichen, JWE-artig


@pytest.fixture
def b_api(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example.org/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", ENV_SCHLUESSEL)
    monkeypatch.delenv("B_API_KEY_MODE", raising=False)
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(None)
    yield monkeypatch
    llm_auth.setze_llm_schluessel(None)
    get_settings.cache_clear()


def _anfrage(kopf: dict[str, str]) -> Request:
    roh = [(k.lower().encode(), v.encode()) for k, v in kopf.items()]
    return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": roh})


# ── Form und Art ──────────────────────────────────────────────────────────────

def test_ein_langes_delegations_token_gilt(b_api) -> None:
    assert len(TOKEN) > 512
    assert llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}") is True
    assert llm_auth.zug_art() == "delegation"
    assert llm_auth.b_api_schluessel() == TOKEN


def test_die_obergrenze_liegt_bei_8192(b_api) -> None:
    assert llm_auth.setze_llm_schluessel("Bearer bdt_" + "x" * (8192 - 4)) is True
    assert llm_auth.setze_llm_schluessel("Bearer bdt_" + "x" * (8193 - 4)) is False


@pytest.mark.parametrize(("roh", "art"), [
    (None, ""),
    (f"Bearer {SCHLUESSEL}", "schluessel"),
    (f"Bearer {TOKEN}", "delegation"),
    ("Bearer BDT_" + "x" * 30, "schluessel"),   # das Präfix ist klein geschrieben
], ids=["ohne", "schluessel", "delegation", "praefix_gross"])
def test_die_art_des_zuges(b_api, roh, art) -> None:
    llm_auth.setze_llm_schluessel(roh)
    assert llm_auth.zug_art() == art


def test_ein_schluessel_faellt_ohne_kopf_weiter_auf_die_anlage_zurueck(b_api) -> None:
    """Abwärtskompatibel: der Direktbetrieb mit ``B_API_KEY`` bleibt, wie er war."""
    assert llm_auth.zug_art() == ""
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


# ── Kein Rückfall bei Delegation (E3) ─────────────────────────────────────────

@pytest.mark.parametrize("roh", [
    "Bearer bdt_" + "x" * 9000,          # zu lang
    "Bearer bdt_abc\r\nX-Evil: 1",       # Kopfzeilen-Einschleusung
    "bearer bdt_" + "x" * 40,            # kleines bearer: nicht wörtlich weiterzugeben
], ids=["zu_lang", "einschleusung", "bearer_klein"])
def test_ein_unbrauchbares_delegations_token_faellt_nie_auf_b_api_key_zurueck(b_api, roh) -> None:
    assert llm_auth.setze_llm_schluessel(roh) is False
    assert llm_auth.zug_art() == "delegation"
    with pytest.raises(llm_auth.KeinDelegationsToken) as fehler:
        llm_auth.b_api_schluessel()
    assert fehler.value.grund == "unbrauchbar"
    with pytest.raises(llm_auth.KeinDelegationsToken):
        llm.route(get_chat_model())          # kein Aufruf mit Ersatz-Schlüssel


def test_die_route_nimmt_das_token_ohne_x_api_key(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    _modell, _basis, schluessel, kopf = llm.route(get_chat_model())
    assert schluessel == TOKEN
    assert not kopf or "X-API-KEY" not in {k.upper() for k in kopf}


def test_ein_neuer_zug_ohne_kopf_loescht_die_delegation(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    llm_auth.setze_llm_schluessel(None)
    assert llm_auth.zug_art() == ""
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


# ── Auflegen beendet die Delegation (E4) ──────────────────────────────────────

def test_nach_dem_auflegen_kein_b_api_aufruf_mehr(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    assert llm_auth.delegation_beender()() is True
    with pytest.raises(llm_auth.KeinDelegationsToken) as fehler:
        llm_auth.b_api_schluessel()
    assert fehler.value.grund == "beendet"


def test_auflegen_ohne_delegation_aendert_nichts(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    assert llm_auth.delegation_beender()() is False
    assert llm_auth.b_api_schluessel() == SCHLUESSEL


def test_das_ende_gilt_auch_in_kopierten_kontexten(b_api) -> None:
    """Der Zug läuft als eigene Task (Kontextkopie, LangGraph-Knoten ebenso) — das Auflegen
    bemerkt der Strom im Kontext der Anfrage. Beide sehen dasselbe Ende."""
    import contextvars

    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    kopie = contextvars.copy_context()
    llm_auth.delegation_beender()()
    with pytest.raises(llm_auth.KeinDelegationsToken):
        kopie.run(llm_auth.b_api_schluessel)


# ── Nie im Text ───────────────────────────────────────────────────────────────

def test_das_token_steht_in_keinem_repr_und_keinem_log(b_api, caplog) -> None:
    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    zu_lang = "bdt_" + "y" * 9000
    with caplog.at_level(logging.DEBUG):
        uebernimm_llm_schluessel(_anfrage({"Authorization": f"Bearer {TOKEN}"}))
        uebernimm_llm_schluessel(_anfrage({"Authorization": f"Bearer {zu_lang}"}))
        try:
            llm_auth.b_api_schluessel()
        except llm_auth.KeinDelegationsToken as fehler:
            assert zu_lang[:40] not in f"{fehler!r} {fehler}"
    texte = [rec.getMessage() for rec in caplog.records]
    assert texte, "der unbrauchbare Kopf wird gemeldet"
    assert all(TOKEN[:40] not in t and zu_lang[:40] not in t for t in texte)
    assert TOKEN[:40] not in repr(llm_auth._zug)
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    assert TOKEN[:40] not in repr(llm_auth._zug.get())


# ── turn_auth: static / forward (AB2) ─────────────────────────────────────────

def test_static_liest_auch_kein_delegations_token(b_api) -> None:
    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    b_api.setenv("B_API_KEY_MODE", "static")
    get_settings.cache_clear()
    uebernimm_llm_schluessel(_anfrage({"Authorization": f"Bearer {TOKEN}"}))
    assert llm_auth.zug_art() == ""
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


def test_forward_nimmt_das_delegations_token(b_api) -> None:
    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    b_api.setenv("B_API_KEY_MODE", "forward")
    get_settings.cache_clear()
    uebernimm_llm_schluessel(_anfrage({"Authorization": f"Bearer {TOKEN}"}))
    assert llm_auth.zug_art() == "delegation"
    assert llm_auth.b_api_schluessel() == TOKEN


def test_forward_weist_ein_unbrauchbares_delegations_token_ab(b_api) -> None:
    from fastapi import HTTPException

    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    b_api.setenv("B_API_KEY_MODE", "forward")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as fehler:
        uebernimm_llm_schluessel(_anfrage({"Authorization": "Bearer bdt_" + "x" * 9000}))
    assert fehler.value.status_code == 401


# ── Sprache: eine Auskunft, kein Zug ──────────────────────────────────────────

def test_sprachauskunft_mit_unbrauchbarem_token_wirft_nicht(b_api) -> None:
    from boerdi.services import speech_proxy

    b_api.setenv("B_API_AUDIO", "1")
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel("Bearer bdt_" + "x" * 9000)
    assert speech_proxy.speech_enabled() is False
