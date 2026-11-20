"""Paket K, Review-Befunde vom 19.11. (Review A: Kern; Review B: Flow, Warten, Oberfläche).

Die MCP-Antworten in der Drahtform von ``wlo-mcp-server-sc`` (``src/tools/bapi-flows.ts``), wie in
``test_paket_k_mcp_starter``. Ohne Postgres.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgang_aktion
from boerdi.services.ablauf import (
    auftrag_spaeter,
    auftrag_zug,
    treiber,
    treiber_bloecke,
    zug,
    zug_basis,
)
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.services.auftraege import client, mcp_starter
from boerdi.services.mcp import faehigkeiten
from tests.test_ablauf_auftrag import _roh, _starte, freigeschaltet, im_zug  # noqa: F401
from tests.test_ablauf_auftrag_abbruch import _SID, _aktionen, _gesperrt_katalog
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_k_mcp_starter import FLOW, JOB, VORSCHAU, _abgelehnt, _ok
from tests.test_paket_k_mcp_starter import mcp as mcp_fixture  # noqa: F401
from tests.test_paket_k_traeger import _ablauf, _am_auftrag, _mcp_startet
from tests.test_paket_k_traeger import lage as traeger_lage  # noqa: F401
from tests.test_paket_k_zug import KENNUNG, _gestartet, ueber_mcp  # noqa: F401

START_NICHT_DA = {"error": {"kind": "tool",
                            "message": "MCP error -32602: Tool wlo_start_flow not found"}}


# ── A1: ein offener Start bekommt keinen Fortschritts-Block, /stand hört auf ──────────────────────

def test_a1_ein_offener_start_bekommt_keinen_fortschritts_block(monkeypatch):
    monkeypatch.setattr(treiber_bloecke.schalter, "aktiv", lambda _name: True)
    assert treiber_bloecke.fortschritt("lesen", "job-1", "Läuft.", "de") is not None
    assert treiber_bloecke.fortschritt("lesen", mcp_starter.offene_kennung(), "Läuft.",
                                       "de") is None


def test_a1_der_treiber_haengt_beim_offenen_start_keinen_block_an(traeger_lage, monkeypatch):  # noqa: F811
    monkeypatch.setattr(treiber_bloecke.schalter, "aktiv", lambda _name: True)

    async def offen(flow, eingaben):
        raise client.AuftragFehler("offen")

    _mcp_startet(monkeypatch, offen)
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert aus.bloecke == []




def test_a1_stand_pruefen_beim_offenen_start_sagt_nicht_stand_weg(ueber_mcp):  # noqa: F811
    """Ein offener Start (etwa 429 mit ``outcomeOpen``) hat vielleicht nie gestartet — „Seine
    Ergebnisse stehen an den Materialien“ wäre falsch."""
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _abgelehnt("rate_limited", outcome_open=True, retryAfter=30)]
    state: dict = {"entities": {}}
    _starte(state)
    from tests.test_ablauf_auftrag import _pruefe

    antwort = _pruefe(state)
    assert bot_text("de", "action.ablauf.auftragStandWeg") not in antwort.content
    assert antwort.content.startswith(bot_text("de", "action.ablauf.auftragOffenGelesen"))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_a1_der_satz_zum_offenen_start_in_beiden_sprachen(lang):
    satz = bot_text(lang, "action.ablauf.auftragOffenGelesen")
    assert satz and "{" not in satz and satz != bot_text(lang, "action.ablauf.auftragStandWeg")


# ── A2: nach „unbekanntes Werkzeug“ kein Direktweg, kurz neu fragen ───────────────────────────────

class _Uhr:
    def __init__(self) -> None:
        self.t = 1_000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def uhr(monkeypatch):
    u = _Uhr()
    monkeypatch.setattr(faehigkeiten, "_jetzt", u)
    monkeypatch.setattr(mcp_starter, "_jetzt", u)
    monkeypatch.setattr(mcp_starter, "_neu_geholt", None)
    return u


def test_a2_zweiter_klick_nach_neustart_geht_wieder_zur_rueckfrage(ueber_mcp, uhr, monkeypatch):  # noqa: F811
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    faehigkeiten.uebernehmen([{"name": n} for n in mcp_starter.WERKZEUGE])   # Zeitpunkt merken
    liste: list = [{"name": "search_wlo_content"}]                            # nach dem Neustart
    erkundet: list = []

    async def erkunden():
        erkundet.append(uhr.t)
        return faehigkeiten.uebernehmen(liste)

    monkeypatch.setattr(faehigkeiten, "nachfragen", erkunden)
    direkt: list = []

    async def direkt_starten(flow, eingaben):
        direkt.append(flow)
        return "job-direkt"

    monkeypatch.setattr(client, "starten", direkt_starten)
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [START_NICHT_DA]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["schritt"] == "frage" and not mcp_starter.verfuegbar()
    # zweiter Klick gleich danach — der Direktweg wäre da, wird aber nicht genommen
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: True)
    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    uhr.t += 5
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_WAHL and aus.lauf["schritt"] == "frage"
    assert aus.texte[0] == bot_text("de", "action.ablauf.auftragNichtVerfuegbar")
    assert "Ohne Metadaten." not in aus.texte and direkt == []
    assert len(erkundet) == 1                        # innerhalb des Takts nicht schon wieder
    # nach TAKT_NACH_FEHLER_S sind die Werkzeuge zurück — der dritte Klick startet über den MCP
    uhr.t += mcp_starter.TAKT_NACH_FEHLER_S
    liste[:] = [{"name": n} for n in mcp_starter.WERKZEUGE]
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _ok({"status": "started", "jobId": JOB, "flow": "f/meta"})]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG and aus.auftrag["job_id"] == KENNUNG
    assert len(erkundet) == 2 and direkt == []


def test_a2_nach_zehn_minuten_ohne_werkzeuge_endet_es_ehrlich(ueber_mcp, uhr, monkeypatch):  # noqa: F811
    faehigkeiten.uebernehmen([{"name": n} for n in mcp_starter.WERKZEUGE])
    uhr.t += mcp_starter.KUERZLICH_S + 1
    faehigkeiten.uebernehmen([{"name": "search_wlo_content"}])

    async def erkunden():
        return True

    monkeypatch.setattr(faehigkeiten, "nachfragen", erkunden)
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: True)
    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.texte == [bot_text("de", "action.ablauf.auftragNurUeberWlo"), "Ohne Metadaten."]


def test_a2_faehigkeiten_merken_wann_ein_werkzeug_zuletzt_da_war(uhr):
    faehigkeiten.vergessen()
    try:
        assert faehigkeiten.alter("wlo_start_flow") is None
        faehigkeiten.uebernehmen([{"name": "wlo_start_flow"}])
        uhr.t += 42
        faehigkeiten.uebernehmen([{"name": "anderes"}])
        assert faehigkeiten.alter("wlo_start_flow") == 42
        assert not faehigkeiten.kennt_werkzeug("wlo_start_flow")
    finally:
        faehigkeiten.vergessen()


# ── A3: der Code einer Abweisung reist mit ───────────────────────────────────────────────────────

@pytest.mark.parametrize(("code", "erwartet"), [
    ("EDU_USER_NOT_VERIFIED", "EDU_USER_NOT_VERIFIED"), ("LEGACY_HEADERS", "LEGACY_HEADERS"),
    ("IRGENDWAS", None)])
def test_a3_rejected_traegt_den_bekannten_code(mcp_fixture, code, erwartet):  # noqa: F811
    mcp_fixture["antworten"]["wlo_start_flow"] = [VORSCHAU, _abgelehnt("rejected", code=code)]
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.starten(FLOW, {"node_ids": ["n-1"], "language": "de"}))
    assert fehler.value.grund == "abgewiesen" and fehler.value.code == erwartet


def test_a3_edu_user_not_verified_ueber_den_mcp_nennt_das_konto(traeger_lage, mcp_fixture,  # noqa: F811
                                                                monkeypatch):
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    mcp_fixture["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _abgelehnt("rejected", code="EDU_USER_NOT_VERIFIED")]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.texte == [bot_text("de", "action.ablauf.auftragAbgelehntKonto"), "Ohne Metadaten."]


@pytest.mark.parametrize(("lang", "alt"), [("de", "umgestellt"), ("en", "switched over")])
def test_a3_der_satz_zur_person_ist_nicht_mehr_umstellung(lang, alt):
    satz = bot_text(lang, "action.ablauf.auftragAbgelehntPerson")
    assert alt not in satz and satz


# ── A4/A7: der MCP-Weg nur für Schritte mit repo_schreibt ──────────────────────────────────────

@pytest.mark.parametrize(("mcp", "darf", "repo_schreibt", "erwartet"), [
    (True, True, True, ("mcp", "")),
    (True, True, False, ("direkt", "")),           # lesender Flow: Direktweg wie vor Paket K
    (True, False, False, (None, "ohne_schluessel")),
    (False, True, True, (None, "ohne_mcp")),
    (False, True, False, ("direkt", "")),
])
def test_a4_der_traeger_folgt_repo_schreibt(traeger_lage, mcp, darf, repo_schreibt, erwartet):  # noqa: F811
    traeger_lage.update(mcp=mcp, darf_jobs=darf)
    assert auftrag_zug.traeger(repo_schreibt=repo_schreibt) == erwartet


def test_a4_ein_lesender_flow_startet_nie_ueber_den_mcp(traeger_lage, monkeypatch):  # noqa: F811
    traeger_lage.update(mcp=True, darf_jobs=False)
    gerufen: list = []

    async def ueber_mcp_starten(flow, eingaben):
        gerufen.append(flow)
        return mcp_starter.PRAEFIX + "job-1"

    _mcp_startet(monkeypatch, ueber_mcp_starten)
    aus = _am_auftrag(_ablauf(False), auftrag_zug.starter())
    assert gerufen == [] and aus.texte[-1] == "Ohne Metadaten."


def test_a4_die_pruefung_verlangt_repo_schreibt_fuer_den_metadaten_flow(freigeschaltet):  # noqa: F811
    roh = _roh()
    roh["schritte"][0].update(flow=zug_basis.METADATEN_FLOW)
    befunde = pruefe(AblaufArea.model_validate(roh))
    assert any("repo_schreibt" in b for b in befunde), befunde


def test_a4_not_allowed_bekommt_einen_satz(traeger_lage, mcp_fixture, monkeypatch):  # noqa: F811
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    mcp_fixture["antworten"]["wlo_start_flow"] = [_abgelehnt("not_allowed")]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.texte == [bot_text("de", "action.ablauf.auftragNichtErlaubt"), "Ohne Metadaten."]


# ── A5: auch „weiter“ bekommt einen Satz; Ersetzen verwirft den Ausgang nicht ───────────────────

def test_a5_neues_vorhaben_sagt_wenn_der_auftrag_weiterlaeuft(ueber_mcp):  # noqa: F811
    state = _gestartet(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_cancel_flow"] = [_abgelehnt("rejected")]
    kuerzel = client.kuerzel(KENNUNG)
    antwort = asyncio.run(vorgang_aktion.neu(_S(), _req(
        action=vorgang_aktion.AKTION_NEU, action_params={"bestaetigt": True, "kuerzel": kuerzel}),
        state))
    assert antwort.content == (bot_text("de", "action.vorgang.neu") + " "
                               + bot_text("de", "action.vorgang.auftragLaeuftWeiter"))


def test_a5_ersetzen_eines_laufs_nennt_den_ausgang(ueber_mcp):  # noqa: F811
    state = _gestartet(ueber_mcp)
    frage = _starte(state)                                  # B1: erst die Rückfrage
    [neu] = [p for a, p in _aktionen(frage) if a == zug.AKTION]
    ueber_mcp.mcp["antworten"]["wlo_cancel_flow"] = [_abgelehnt("upstream_error",
                                                                outcome_open=True)]
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _ok({"status": "started", "jobId": "job-zwei", "flow": "wlo/volltext"})]
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params=neu), state))
    assert ("wlo_cancel_flow", {"jobId": JOB}) in ueber_mcp.mcp["gerufen"]
    assert antwort.content.startswith(bot_text("de", "action.vorgang.auftragUnklar"))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_a5_der_satz_laeuft_weiter_in_beiden_sprachen(lang):
    satz = bot_text(lang, "action.vorgang.auftragLaeuftWeiter")
    assert satz and "{" not in satz


# ── A6: isError ohne Code nach dem Bestätigen ist offen ─────────────────────────────────────────

def test_a6_is_error_ohne_code_nach_der_bestaetigung_ist_offen(mcp_fixture):  # noqa: F811
    mcp_fixture["antworten"]["wlo_start_flow"] = [
        VORSCHAU, {"error": {"kind": "tool", "message": "Internal error"}}]
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.starten(FLOW, {"node_ids": ["n-1"], "language": "de"}))
    assert fehler.value.grund == "offen"


def test_a6_unbekanntes_werkzeug_nach_der_bestaetigung_bleibt_voruebergehend(mcp_fixture,  # noqa: F811
                                                                             monkeypatch):
    async def erkunden():
        return False

    monkeypatch.setattr(faehigkeiten, "nachfragen", erkunden)
    mcp_fixture["antworten"]["wlo_start_flow"] = [VORSCHAU, START_NICHT_DA]
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.starten(FLOW, {"node_ids": ["n-1"], "language": "de"}))
    assert fehler.value.grund == "nicht_verfuegbar"


def test_a6_is_error_ohne_code_bei_der_vorschau_startet_nichts(mcp_fixture):  # noqa: F811
    mcp_fixture["antworten"]["wlo_start_flow"] = [{"error": {"kind": "tool", "message": "x"}}]
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.starten(FLOW, {"node_ids": ["n-1"], "language": "de"}))
    assert fehler.value.grund == "fehler"


# ── A8: auch eine offene Kennung nur mit Anmeldung ──────────────────────────────────────────────

def test_a8_offene_kennung_nur_mit_anmeldung(monkeypatch):
    offen = mcp_starter.offene_kennung()
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: False)
    assert auftrag_zug.abrufbar(offen) is False
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    assert auftrag_zug.abrufbar(offen) is True


# ── A9: die Funktion ist öffentlich ─────────────────────────────────────────────────────────────

def test_a9_wlo_erschliessen_ist_oeffentlich():
    assert callable(zug_basis.wlo_erschliessen)
    assert not hasattr(zug_basis, "_wlo_erschliessen")


# ── B2/B7: der Satz zu „Später“ ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("lang", "wort"), [("de", "Stand prüfen"), ("en", "Check status")])
def test_b2_spaeter_verweist_auf_stand_pruefen_nicht_auf_meine_vorgaenge(lang, wort):
    satz = bot_text(lang, "action.ablauf.auftragSpaeter", datum="X")
    assert wort in satz and "X" in satz
    assert "Meine Vorgänge" not in satz and "My tasks" not in satz


def test_b7_das_datum_liegt_nie_vor_heute():
    heute = datetime(2026, 11, 19, 9, tzinfo=UTC)
    in_stunden = heute + timedelta(hours=5)
    assert auftrag_spaeter.datum(in_stunden, "de", jetzt=heute) == "19.11.2026"
    assert auftrag_spaeter.datum(heute + timedelta(days=3), "de", jetzt=heute) == "21.11.2026"


# ── B3: die Marke der ruhenden Sperre gilt nur für ihren Teil des Stapels ──────────────────────

def test_b3_teil_zwei_eines_stapels_ist_wieder_gesperrt(im_zug, monkeypatch):  # noqa: F811
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    assert auftrag_zug.spaeter_merken(_SID, state)
    assert auftrag_zug.gesperrt(_SID, state) is None
    # eine andere Sitzung holte Teil 1 ab, Teil 2 läuft — der Preflight frischt den Verweis auf
    [v] = im_zug.speicher.v.values()
    v.akte["lauf"]["auftrag_teile"] = {"i": 1, "n": 2}
    state["entities"][arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, "person-a")
    auftrag_zug.sperre_aufraeumen(_SID, state)
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"
    assert auftrag_zug.SPAETER not in state["entities"]


# ── B4/B9: der Seed ─────────────────────────────────────────────────────────────────────────────

def _seed_themenbaum() -> dict:
    from pathlib import Path

    import yaml

    pfad = Path(__file__).resolve().parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml"
    return yaml.safe_load(pfad.read_text(encoding="utf-8"))


def test_b4_der_metadaten_schritt_sperrt_die_eingabe():
    schritte = {s["id"]: s for s in _seed_themenbaum()["schritte"]}
    assert schritte["metadaten"]["warten"] == "gesperrt"


def test_b9_die_rueckfrage_nennt_strukturdokumente_nur_falls_dabei():
    schritte = {s["id"]: s for s in _seed_themenbaum()["schritte"]}
    text = schritte["metadaten_frage"]["text"]
    assert "falls dabei" in text["de"] and "if any" in text["en"]


# ── B5: der Satz zum fehlenden Volltext ─────────────────────────────────────────────────────────

def test_b5_volltext_fehlt_sagt_nicht_mehr_nochmal_schreiben():
    """Plan 2026-11-20 §8, E1: „nochmal“ half bei ``not_extracted`` nie — der Satz nennt die
    Auswege statt eines neuen Versuchs."""
    from boerdi.ui_module import dienst

    satz = dienst._FEHLER["volltext_endgueltig"]
    assert "nochmal" not in satz and "das prüft den Stand" not in satz
    assert "Hier im Chat lesen lassen" in satz


# ══ Zweites Review (19.11.) ══════════════════════════════════════════════════════════════════════

# ── Z1: EDU_USER_REQUIRED auf dem Direktweg — neu anmelden hilft dort nicht ─────────────────────

@pytest.mark.parametrize("lang", ["de", "en"])
def test_z1_der_direktweg_hat_einen_eigenen_satz(traeger_lage, monkeypatch, lang):  # noqa: F811
    async def nein(flow, eingaben):
        raise client.AuftragFehler("abgewiesen", code="EDU_USER_REQUIRED")

    monkeypatch.setattr(client, "starten", nein)
    starte = auftrag_zug.starter().fuer(False)
    assert starte.traeger == "direkt" and asyncio.run(starte("f/x", {})) is None
    assert starte.hinweis(lang) == bot_text(lang, "action.ablauf.auftragAbgelehntDirekt")
    assert starte.hinweis(lang) != bot_text(lang, "action.ablauf.auftragAbgelehntPerson")


# ── Z2: Stapel mit offenem Ausgang ──────────────────────────────────────────────────────────────

def test_z2_ein_offener_start_ab_teil_zwei_sagt_es():
    from tests.test_r1_auftrag_teile import _ablauf as _stapel_ablauf
    from tests.test_r1_auftrag_teile import _umgebung as _stapel_umgebung

    ablauf = _stapel_ablauf()
    umgebung, _ = _stapel_umgebung(jobs=["job-1", mcp_starter.offene_kennung()])

    class _Offen:
        def __init__(self, starte):
            self.starte = starte

        async def __call__(self, flow, args):
            return await self.starte(flow, args)

        def hinweis(self, sprache):
            return "OFFEN-SATZ"

    from dataclasses import replace

    umgebung = replace(umgebung, auftrag_starten=_Offen(umgebung.auftrag_starten))
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    zweiter = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, {"outputs": {}}, umgebung))
    assert mcp_starter.ist_offen(zweiter.auftrag["job_id"])
    assert zweiter.texte[-1] == "OFFEN-SATZ" and zweiter.bloecke == []


@pytest.mark.parametrize(("stapel", "schluessel", "werte"), [
    (None, "action.ablauf.auftragOffenGelesen", {}),
    ({"n": 3, "i": 2, "ergebnisse": [], "args": {}}, "action.ablauf.auftragOffenGelesen", {}),
    ({"n": 3, "i": 0, "ergebnisse": [], "args": {}}, "action.ablauf.auftragTeilUnklar",
     {"teil": 1, "naechster": 2}),
])
def test_z2_stand_pruefen_beim_offenen_teil(stapel, schluessel, werte):
    lauf = {"auftrag_teile": stapel} if stapel else {}
    satz = auftrag_zug.stand_weg_satz(mcp_starter.offene_kennung(), lauf, "de")
    assert satz == bot_text("de", schluessel, **werte)
    assert auftrag_zug.stand_weg_satz(KENNUNG, lauf, "de") == bot_text(
        "de", "action.ablauf.auftragStandWeg")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_z2_der_satz_zum_unklaren_teil(lang):
    satz = bot_text(lang, "action.ablauf.auftragTeilUnklar", teil=2, naechster=3)
    assert "2" in satz and "3" in satz and "{" not in satz


# ── Z3: unknown_job — ehrlich, dass Teile fehlen können ─────────────────────────────────────────

@pytest.mark.parametrize(("lang", "wort"), [("de", "später noch einmal"), ("en", "again later")])
def test_z3_stand_weg_sagt_dass_teile_fehlen_koennen(lang, wort):
    satz = bot_text(lang, "action.ablauf.auftragStandWeg")
    assert wort in satz
    assert "Seine Ergebnisse stehen an den" not in satz and "Its results are on" not in satz


# ── Z4: 429 beim Start ohne offenen Ausgang — zurück an die Rückfrage ───────────────────────────

@pytest.mark.parametrize(("retry", "minuten"), [(120, 2), (30, 1), (None, None)])
def test_z4_voll_fuehrt_zur_rueckfrage(traeger_lage, mcp_fixture, monkeypatch, retry, minuten):  # noqa: F811
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    mehr = {"retryAfter": retry} if retry else {}
    mcp_fixture["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _abgelehnt("rate_limited", outcome_open=False, **mehr)]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_WAHL and aus.lauf["schritt"] == "frage"
    erwartet = (bot_text("de", "action.ablauf.auftragVoll", minuten=minuten) if minuten
                else bot_text("de", "action.ablauf.auftragVollOhneZeit"))
    assert aus.texte[0] == erwartet and "Ohne Metadaten." not in aus.texte


def test_z4_voll_mit_offenem_ausgang_bleibt_offen(traeger_lage, mcp_fixture, monkeypatch):  # noqa: F811
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    mcp_fixture["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _abgelehnt("rate_limited", outcome_open=True, retryAfter=60)]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert mcp_starter.ist_offen(aus.auftrag["job_id"])


# ── Z5: auftragNichtErlaubt neutral ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("lang", "wort"), [("de", "nicht freigegeben"), ("en", "not enabled")])
def test_z5_nicht_erlaubt_ist_neutral(lang, wort):
    satz = bot_text(lang, "action.ablauf.auftragNichtErlaubt")
    assert wort in satz and "WLO-Dienst" not in satz and "WLO service" not in satz


# ── Z7: Nachholen im Takt, ohne die Fähigkeiten zu verwerfen ────────────────────────────────────

def test_z7_unbekanntes_werkzeug_holt_nur_im_takt_und_zaehlt_nicht(mcp_fixture, uhr,  # noqa: F811
                                                                   monkeypatch):
    from boerdi.services.mcp import transport

    faehigkeiten.vergessen()
    faehigkeiten.uebernehmen([{"name": "search_wlo_content"}])
    gefragt: list = []

    async def kaputt(_url):
        gefragt.append(uhr.t)
        raise RuntimeError("MCP startet neu")

    monkeypatch.setattr(transport, "discover_server_tools", kaputt)
    mcp_fixture["antworten"]["wlo_flow_status"] = [START_NICHT_DA]
    try:
        for schritt in range(6):
            uhr.t += 5 if schritt % 2 else mcp_starter.TAKT_NACH_FEHLER_S
            with pytest.raises(client.AuftragFehler):
                asyncio.run(mcp_starter.stand(KENNUNG))
        assert len(gefragt) == 3                          # nur jeder zweite Versuch im Takt
        assert faehigkeiten._fehlversuche == 0            # kein Verwerfen aller Fähigkeiten
        assert faehigkeiten.kennt_werkzeug("search_wlo_content")
    finally:
        faehigkeiten.vergessen()
