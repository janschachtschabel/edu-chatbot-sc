"""Paket D (Plan 2026-11-17, E4/E6): der Auftrags-Client und die Delegation der b-api.

- Neue Fehlercodes der b-api: 400 ``EDU_USER_REQUIRED`` (die Ursprungsanfrage hatte keine
  verifizierte Person) ist eine Abweisung, keine falsche Eingabe; 403 ``LEGACY_HEADERS`` (ein
  abgeschaffter Kopf wie ``X-Edu-User-Id``). Beide bekommen einen eigenen Satz.
- Das Delegations-Token kann keine Jobs (E1/E2): im Delegationsbetrieb startet der Direktweg
  nichts — bis Paket K übernimmt der Ersatzweg des Schritts.
- Kein b-api-Aufruf nach dem Ende der Anfrage (E4): ``abbrechen_im_hintergrund`` startet bei
  Delegation keine Task.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from boerdi.services import llm_auth
from boerdi.services.ablauf import auftrag_zug
from boerdi.services.auftraege import client
from boerdi.settings import get_settings

TOKEN = "bdt_" + "t" * 80


@pytest.fixture(autouse=True)
def _frisch():
    llm_auth.setze_llm_schluessel(None)
    yield
    llm_auth.setze_llm_schluessel(None)


# ── D2: Fehlercodes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("koerper", [
    {"error": {"code": "EDU_USER_REQUIRED", "message": "no verified user"}},
    {"code": "EDU_USER_REQUIRED"},
])
def test_400_edu_user_required_ist_eine_abweisung(koerper):
    with pytest.raises(client.AuftragFehler) as fehler:
        client._pruefe_antwort(httpx.Response(400, json=koerper))
    assert (fehler.value.grund, fehler.value.code) == ("abgewiesen", "EDU_USER_REQUIRED")


def test_400_ohne_bekannten_code_bleibt_eingaben():
    with pytest.raises(client.AuftragFehler) as fehler:
        client._pruefe_antwort(httpx.Response(400, json={"error": {"code": "INVALID_INPUT"}}))
    assert (fehler.value.grund, fehler.value.code) == ("eingaben", None)


def test_403_legacy_headers_traegt_seinen_code(caplog):
    with caplog.at_level(logging.INFO, logger=client.logger.name), \
            pytest.raises(client.AuftragFehler) as fehler:
        client._pruefe_antwort(httpx.Response(403, json={"error": {"code": "LEGACY_HEADERS"}}))
    assert (fehler.value.grund, fehler.value.code) == ("abgewiesen", "LEGACY_HEADERS")
    assert "LEGACY_HEADERS" in caplog.text


def test_die_bekannten_codes():
    assert {"EDU_USER_NOT_VERIFIED", "EDU_USER_REQUIRED", "LEGACY_HEADERS"} <= client.BEKANNTE_CODES


def test_der_client_kennt_keinen_personen_kopf_mehr():
    assert not hasattr(client, "_person")


# ── D5: die Sätze an die Person ───────────────────────────────────────────────

def _starter(monkeypatch, code):
    async def starten(flow, eingaben):
        raise client.AuftragFehler("abgewiesen", code=code)

    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    monkeypatch.setattr(client, "starten", starten)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: True)
    # Review A4: ein lesender Flow geht den Direktweg (der Starter je Schritt)
    starte = auftrag_zug.starter().fuer(False)
    assert asyncio.run(starte("f/x", {})) is None
    return starte


@pytest.mark.parametrize(("code", "de", "en"), [
    # Zweites Review K (Z1): auf dem Direktweg erkennt die b-api nie eine Person — neu anmelden
    # hilft dort nicht; der Satz verweist auf den WLO-Dienst (über den MCP gilt
    # ``auftragAbgelehntPerson``, ``test_paket_k_traeger``)
    ("EDU_USER_REQUIRED", "nur über den WLO-Dienst", "only works through the WLO service"),
    ("LEGACY_HEADERS", "veralteten Kopf", "outdated header"),
])
def test_der_satz_je_code(monkeypatch, code, de, en):
    starte = _starter(monkeypatch, code)
    assert de in starte.hinweis("de")
    assert en in starte.hinweis("en")


def test_mit_delegation_startet_der_direktweg_keinen_auftrag(monkeypatch, caplog):
    """E1/E2: das Token deckt keine Jobs — ein Start wäre eine sichere 401 mit dem Satz „lade die
    Seite neu“, der nicht hilft. Bis Paket K nimmt der Schritt seinen Ersatzweg."""
    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    with caplog.at_level(logging.INFO, logger=auftrag_zug.logger.name):
        # Review A4: ein lesender Flow (Direktweg) — bei Delegation ohne Träger
        assert auftrag_zug.starter().fuer(False).traeger is None
    assert TOKEN not in caplog.text
    llm_auth.setze_llm_schluessel("Bearer " + "k" * 36)        # Schlüssel (forwardApiKey)
    assert auftrag_zug.starter().fuer(False).traeger == "direkt"


# ── D4: kein Abbruch im Hintergrund bei Delegation ────────────────────────────

@pytest.fixture
def bapi(monkeypatch):
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm")
    monkeypatch.setenv("B_API_JOBS_STATUS_PATH", "/api/v1/jobs/{job_id}")
    get_settings.cache_clear()
    gesehen: list[httpx.Request] = []

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return httpx.Response(204)

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    yield gesehen
    get_settings.cache_clear()


def test_abbrechen_im_hintergrund_startet_bei_delegation_keine_task(bapi, caplog):
    async def lauf() -> int:
        llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
        vorher = len(client._abbrueche)
        client.abbrechen_im_hintergrund("job-1")
        neu = len(client._abbrueche) - vorher
        await asyncio.sleep(0.05)
        return neu

    with caplog.at_level(logging.INFO, logger=client.logger.name):
        assert asyncio.run(lauf()) == 0
    assert bapi == []
    assert "job-1" not in caplog.text and TOKEN not in caplog.text
    assert "Repository" in caplog.text


def test_abbrechen_im_hintergrund_ohne_delegation_wie_bisher(bapi):
    async def lauf() -> None:
        llm_auth.setze_llm_schluessel("Bearer " + "k" * 36)
        client.abbrechen_im_hintergrund("job-1")
        await asyncio.gather(*client._abbrueche)

    asyncio.run(lauf())
    assert [r.method for r in bapi] == ["DELETE"]


def test_bei_der_b_api_abbrechen_ruft_den_client_bei_delegation_nicht(monkeypatch, caplog):
    from boerdi.services.ablauf import zug_basis

    gerufen: list[str] = []
    monkeypatch.setattr(client, "abbrechen_im_hintergrund", gerufen.append)
    llm_auth.setze_llm_schluessel(f"Bearer {TOKEN}")
    with caplog.at_level(logging.INFO, logger=zug_basis.logger.name):
        zug_basis.bei_der_b_api_abbrechen("job-1", "job-2")
    assert gerufen == []
    assert "Repository" in caplog.text and "job-1" not in caplog.text
    llm_auth.setze_llm_schluessel("Bearer " + "k" * 36)
    zug_basis.bei_der_b_api_abbrechen("job-1")
    assert gerufen == ["job-1"]
