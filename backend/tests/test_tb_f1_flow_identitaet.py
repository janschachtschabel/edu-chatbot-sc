"""Plan 2026-11-10, TB-F1 (Nutzer-Entscheide N13, N15): ein Kestra-Flow startet im Namen der
angemeldeten Person — Weg A mit ``X-Edu-User-Id`` (B-API-Leitfaden §9.1); schreibende Flows sind
erlaubt und tragen den Vermerk ``repo_schreibt`` (die Redaktion legt ihn fest, der Chatbot sieht
nicht in den Flow).

- Den Benutzernamen (``authority`` aus ``/auth/status``) hält der Chatbot nur im Zug: nie
  gespeichert, nie geloggt, nie im ``repr``.
- ``X-Edu-User-Id`` geht nur mit bestätigter Anmeldung mit, und nur beim Start.
- Ein Flow, den der Betrieb nicht freischaltet, sperrt nur einen **eingeschalteten** Ablauf; bei
  einem ausgeschalteten (etwa einem Seed) ist es ein Hinweis — sonst bräche der Werksabgleich.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import pruefung
from boerdi.services.auftraege import client
from boerdi.services.mcp import anmeldung, auth
from boerdi.settings import get_settings


@pytest.fixture
def betrieb(monkeypatch):
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", "schluessel-der-anlage")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "edusharing.chatbot/node-metadata-write")
    get_settings.cache_clear()
    gesehen: list[httpx.Request] = []

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return httpx.Response(202, json={"jobId": "job-123"})

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    marke = auth._bestaetigung.set(None)
    yield gesehen
    auth._bestaetigung.reset(marke)
    get_settings.cache_clear()


def test_die_bestaetigung_traegt_den_benutzernamen_nicht_im_repr():
    befund = anmeldung._aus_stand({"mode": "user", "authenticated": True, "authority": "jan.test"})
    assert befund.person and befund.benutzer == "jan.test"
    assert "jan.test" not in repr(befund)


@pytest.fixture
def frische_bestaetigung():
    marke = auth._bestaetigung.set(None)
    yield
    auth._bestaetigung.reset(marke)


def test_der_benutzername_gilt_nur_fuer_eine_bestaetigte_person(monkeypatch, frische_bestaetigung):
    monkeypatch.setattr(auth, "caller_fingerprint", lambda: "fp-1")
    monkeypatch.setattr(auth, "zug_block_wirkt_persoenlich", lambda: True)
    auth.setze_bestaetigung(person=True, kennung="p:abc", benutzer="jan.test")
    assert auth.benutzername() == "jan.test"
    auth.setze_bestaetigung(person=False)
    assert auth.benutzername() == ""
    monkeypatch.setattr(auth, "caller_fingerprint", lambda: "fp-anderer-block")
    auth._bestaetigung.set(("fp-1", True, "p:abc", "jan.test"))
    assert auth.benutzername() == ""          # ein anderer Block gilt erst nach eigener Bestätigung


def test_der_start_schickt_x_edu_user_id_der_person(betrieb, monkeypatch):
    monkeypatch.setattr(auth, "benutzername", lambda: "jan.test")
    job = asyncio.run(client.starten("edusharing.chatbot/node-metadata-write",
                                     {"node_ids": ["a"], "language": "de"}))
    assert job == "job-123"
    [anfrage] = betrieb
    assert anfrage.headers["X-Edu-User-Id"] == "jan.test"
    assert json.loads(anfrage.content) == {"node_ids": ["a"], "language": "de"}


def test_ohne_anmeldung_kein_x_edu_user_id(betrieb, monkeypatch):
    monkeypatch.setattr(auth, "benutzername", lambda: "")
    asyncio.run(client.starten("edusharing.chatbot/node-metadata-write", {"node_ids": ["a"]}))
    assert "X-Edu-User-Id" not in betrieb[0].headers


def _ablauf(aktiv: bool, **auftrag) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "probe_auftrag", "titel": {"de": "Probe"}, "aktiv": aktiv,
        "voraussetzungen": ["anmeldung"], "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Metadaten erzeugen?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "meta"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "ende"}]},
            {"id": "meta", "typ": "auftrag", "flow": "fremd/nicht-frei", "schreibt": "bericht",
             "bei_fehler": "ende", **auftrag},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]})


def test_ein_nicht_freigeschalteter_flow_sperrt_nur_einen_eingeschalteten_ablauf(betrieb):
    aus = _ablauf(False)
    assert not any("fremd/nicht-frei" in b for b in pruefung.pruefe(aus))
    assert any("fremd/nicht-frei" in w for w in pruefung.warnungen(aus))
    assert any("fremd/nicht-frei" in b for b in pruefung.pruefe(_ablauf(True)))


def test_der_vermerk_repo_schreibt_gilt_am_auftrag(betrieb):
    ablauf = _ablauf(False, repo_schreibt=True)
    assert ablauf.schritte[1].repo_schreibt is True
    assert _ablauf(False).schritte[1].repo_schreibt is None   # Vorgabe None (treiber.fassung)


# ── Review TB-F1 ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("authority", ["jürgen", "jan\r\nX-Evil: 1", "a" * 201, {"name": "x"}, 42])
def test_review_1_ein_unbrauchbarer_name_wird_kein_kopf(authority):
    """Befund 1: Nicht-ASCII, Steuerzeichen, zu lang oder kein Text — kein Kopfwert (der Start
    scheitert dann sauber mit 400), nie ein abgebrochener Zug."""
    befund = anmeldung._aus_stand({"mode": "user", "authenticated": True, "authority": authority})
    assert befund.person and befund.benutzer == ""


def test_review_4_kein_name_ohne_persoenlichen_block(monkeypatch, frische_bestaetigung):
    monkeypatch.setattr(auth, "caller_fingerprint", lambda: "fp-1")
    auth.setze_bestaetigung(person=True, kennung="p:abc", benutzer="jan.test")
    monkeypatch.setattr(auth, "zug_block_wirkt_persoenlich", lambda: False)
    assert auth.benutzername() == ""


def test_review_2_ein_schreibender_flow_braucht_eine_rueckfrage_davor(betrieb):
    ohne = AblaufArea.model_validate({
        "id": "ohne_frage", "titel": {"de": "Probe"}, "aktiv": False,
        "voraussetzungen": ["anmeldung"], "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "meta", "typ": "auftrag", "flow": "edusharing.chatbot/node-metadata-write",
             "schreibt": "bericht", "repo_schreibt": True, "bei_fehler": "ende"},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]})
    assert any("meta" in b and "Rückfrage" in b for b in pruefung.pruefe(ohne))
    # mit Wahl davor (_ablauf): kein Befund
    assert not any("Rückfrage" in b for b in pruefung.pruefe(_ablauf(False, repo_schreibt=True)))
    # ohne Vermerk: kein Befund (lesende Flows brauchen keine Rückfrage)
    lesend = ohne.model_copy(deep=True)
    lesend.schritte[0].repo_schreibt = None
    assert not any("Rückfrage" in b for b in pruefung.pruefe(lesend))


# ── Querschnitts-Review F/T ───────────────────────────────────────────────────────────────────

def _mit_upload_davor(**frage) -> AblaufArea:
    """Eine Wahl am Anfang, dann ein Upload, dann der schreibende Flow — die Wahl führt nicht zu
    ihm."""
    return AblaufArea.model_validate({
        "id": "weit_weg", "titel": {"de": "Probe"}, "aktiv": False,
        "voraussetzungen": ["anmeldung"], "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "wofuer", "typ": "nachricht", "text": {"de": "Wofür?"},
             "optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "hoch"}]},
            {"id": "hoch", "typ": "modul", "modul": "ui_upload", "text": {"de": "Wähle."},
             "daten": {"zweck": "sammlungsstruktur"}},
            *([frage] if frage else []),
            {"id": "meta", "typ": "auftrag", "flow": "edusharing.chatbot/node-metadata-write",
             "schreibt": "bericht", "repo_schreibt": True, "bei_fehler": "ende"},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]})


def test_ft5_eine_fruehere_wahl_ist_keine_rueckfrage(betrieb):
    assert any("meta" in b and "Rückfrage" in b for b in pruefung.pruefe(_mit_upload_davor()))


def test_ft5_eine_wahl_direkt_davor_genuegt(betrieb):
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "Schreiben?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "meta"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "ende"}]}
    assert not any("Rückfrage" in b for b in pruefung.pruefe(_mit_upload_davor(**frage)))


def test_ft1_eine_leere_auswahl_startet_keinen_auftrag():
    from boerdi.services.ablauf import treiber

    ablauf = AblaufArea.model_validate({
        "id": "leer", "titel": {"de": "Leer"}, "schritte": [
            {"id": "meta", "typ": "auftrag", "flow": "f/x", "bei_fehler": "schade",
             "argumente": {"node_ids": {"$teil": "ablage", "liste": "inhalte",
                                        "wo": {"stand": "stored"}, "feld": "node_id"}}},
            {"id": "ende", "typ": "ende", "text": {"de": "Gestartet."}},
            {"id": "schade", "typ": "ende", "text": {"de": "Nichts zu tun."}}]})
    gestartet: list = []

    async def starten(flow, args):
        gestartet.append(args)
        return "job-1"

    async def teile(name):
        return {"inhalte": [{"stand": "failed", "node_id": "x"}]} if name == "ablage" else None

    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=teile,
                                                               auftrag_starten=starten)))
    assert gestartet == [] and aus.texte == ["Nichts zu tun."]

