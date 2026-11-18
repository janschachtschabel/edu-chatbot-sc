"""Review Paket D (18.11.): Befunde 1–5, 7, 8.

- Ein durchgereichter Wert heißt nicht „kann Jobs“: das Delegations-Token deckt keine Jobs
  (``llm_auth.darf_jobs``). Abbruch, Stand und Löschen sagen dann ehrlich, dass der Auftrag
  weiterläuft bzw. nicht abrufbar ist.
- ``KeinDelegationsToken`` ist überall ein erwarteter Ausgang (INFO ohne Traceback); die Moderation
  endet mit ihm wie bei jedem Ausfall nach ``MODERATION_FAILURE_MODE``, nie mit 500.
- Eine 401 nach dem Auflegen ist der Vermerk „Verbindung brach ab“, nicht „Seite neu laden“.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from boerdi.i18n.bot_text import bot_text
from boerdi.services import llm_auth
from boerdi.services.fehlertext import antwort_fehlertext

TOKEN = "bdt_" + "t" * 80
SCHLUESSEL = "k" * 36


@pytest.fixture(autouse=True)
def _frisch():
    llm_auth.setze_llm_schluessel(None)
    yield
    llm_auth.setze_llm_schluessel(None)


# ── Befund 1: darf_jobs ───────────────────────────────────────────────────────

@pytest.mark.parametrize(("kopf", "darf"), [
    (None, False), (f"Bearer {SCHLUESSEL}", True), (f"Bearer {TOKEN}", False),
], ids=["ohne", "schluessel", "delegation"])
def test_darf_jobs(kopf, darf):
    llm_auth.setze_llm_schluessel(kopf)
    assert llm_auth.darf_jobs() is darf


def test_der_abbruch_sagt_bei_delegation_dass_der_auftrag_weiterlaeuft():
    from boerdi.services.ablauf import abbruch_zug, treiber

    lauf = {"status": treiber.WARTET_AUFTRAG}
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    assert abbruch_zug._satz(lauf, False) == "action.ablauf.auftragNurHierAbgebrochen"
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    assert abbruch_zug._satz(lauf, False) == "action.ablauf.abgebrochenPerson"


@pytest.mark.parametrize("modul", [
    "boerdi.services.ablauf.auftrag_zug", "boerdi.services.ablauf.abbruch_zug",
    "boerdi.api.ui_vorgaenge", "boerdi.api.ui_auftrag",
])
def test_die_job_stellen_fragen_darf_jobs(modul):
    """Abbrechen, Stand prüfen, Löschen und die Stand-Abfrage der Leiste: ``darf_jobs`` statt
    ``hat_zug_schluessel`` (das bei Delegation wahr ist)."""
    import importlib
    import inspect

    quelle = inspect.getsource(importlib.import_module(modul))
    assert "darf_jobs()" in quelle
    assert "hat_zug_schluessel()" not in quelle


# ── Befund 2: tool_loop ───────────────────────────────────────────────────────

def test_tool_loop_behandelt_kein_token_als_erwarteten_ausgang(monkeypatch, caplog):
    from tests.test_tool_loop import _run_loop

    with caplog.at_level(logging.INFO):
        _fake, result, _st = _run_loop(
            monkeypatch, [], raises=llm_auth.KeinDelegationsToken("beendet"))
    assert result[0] == bot_text("de", "error.connectionLost")
    assert not any(r.exc_info for r in caplog.records)


# ── Befund 3: Moderation ──────────────────────────────────────────────────────

def test_die_moderation_endet_ohne_token_als_ausfall_nicht_mit_500(monkeypatch, caplog):
    from boerdi.services.safety import moderation
    from boerdi.settings import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    gerufen: list = []

    async def _nie(kwargs):
        gerufen.append(kwargs)

    monkeypatch.setattr(moderation, "_mit_platz", _nie)
    llm_auth.setze_llm_schluessel("Bearer bdt_" + "x" * 9000)   # unbrauchbar
    try:
        with caplog.at_level(logging.INFO, logger=moderation.logger.name):
            befund = asyncio.run(moderation.moderate("hallo"))
    finally:
        get_settings.cache_clear()
    assert befund == {}            # ungeprüft — ``service`` wendet MODERATION_FAILURE_MODE an
    assert gerufen == []           # kein Aufruf, kein Rückfall
    assert not any(r.exc_info for r in caplog.records)


# ── Befund 4: 401 nach dem Auflegen ───────────────────────────────────────────

class _Abgewiesen(Exception):
    status_code = 401


def test_delegation_beendet():
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    assert llm_auth.delegation_beendet() is False
    llm_auth.delegation_beender()()
    assert llm_auth.delegation_beendet() is True


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_eine_401_nach_dem_auflegen_ist_der_vermerk(sprache):
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    llm_auth.delegation_beender()()
    text = antwort_fehlertext(sprache, "error.answerFailed", fehler=_Abgewiesen("401"))
    assert text == bot_text(sprache, "error.connectionLost")


# ── Befund 5: ehrlicher Satz bis Paket K ──────────────────────────────────────

def test_edu_user_required_sagt_ehrlich_dass_umgestellt_wird():
    de = bot_text("de", "action.ablauf.auftragAbgelehntPerson")
    en = bot_text("en", "action.ablauf.auftragAbgelehntPerson")
    assert "gerade nicht möglich" in de and "umgestellt" in de
    assert "not possible right now" in en and "being switched over" in en


# ── Befund 7 und 8 ────────────────────────────────────────────────────────────

def test_der_ausgelassene_start_steht_auf_debug(monkeypatch, caplog):
    from boerdi.services.ablauf import auftrag_zug
    from boerdi.services.auftraege import client

    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    with caplog.at_level(logging.DEBUG, logger=auftrag_zug.logger.name):
        assert auftrag_zug.starter() is None
    zeilen = [r for r in caplog.records if "Delegation" in r.getMessage()]
    assert zeilen and all(r.levelno == logging.DEBUG for r in zeilen)


def test_nur_der_gebundene_beender_bleibt():
    assert not hasattr(llm_auth, "beende_delegation")
