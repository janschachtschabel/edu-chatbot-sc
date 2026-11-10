"""Querschnitts-Review 2026-11-06, Paket Q2 — Abläufe über die Paketgrenzen.

- M5: frühe Antworten (``nur_text``) schreiben die Entities fest; ein veralteter Verweis wird aus
  dem Vorgang aufgefrischt (eine zweite Sitzung derselben Person hat den Lauf weitergeschoben).
- M7: vor jedem Netzaufruf (Treiber, b-api) gibt der Zug die DB-Verbindung frei.
- Endgültige b-api-Gründe enden den Auftrag statt eines Endlos-Knopfs; ein neuer Lauf schließt den
  Auftrag des alten; eine Wendung startet nur mit erfüllten Voraussetzungen; die Fassung hängt nicht
  an neuen, leeren Feldern des Modells; Längengrenzen und Prüf-Zwischenspeicher des Katalogs.
"""

from __future__ import annotations

import asyncio
import copy

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgang_aktion
from boerdi.services.ablauf import ausloeser, treiber, zug, zug_basis
from boerdi.services.auftraege import client
from tests.test_ablauf_auftrag import (  # noqa: F401 — Fixtures
    _SCHRITTE,
    _pruefe,
    _roh,
    _starte,
    freigeschaltet,
    im_zug,
)
from tests.test_ablauf_zug import _S, _req


@pytest.fixture(autouse=True)
def _frischer_katalog():
    """Review Q2, Befund 5: der Prüf-Zwischenspeicher ist modulweit — jeder Test beginnt leer."""
    ausloeser._gepruefter = None
    yield
    ausloeser._gepruefter = None


def _festgeschrieben(monkeypatch) -> list[dict]:
    geschrieben: list[dict] = []

    async def merke(session, session_id, *, entities=None, **_k):
        geschrieben.append(copy.deepcopy(entities))

    monkeypatch.setattr(zug_basis, "update_session", merke)
    return geschrieben


# ── M5 ──────────────────────────────────────────────────────────────────────────────────────

def test_m5_ein_veralteter_verweis_wird_aufgefrischt_und_festgeschrieben(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    [v] = im_zug.speicher.v.values()
    v.akte["lauf"]["status"] = "fertig"          # eine zweite Sitzung hat abgeholt
    geschrieben = _festgeschrieben(monkeypatch)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == "fertig"
    assert geschrieben and geschrieben[-1][arbeitsstand.VERWEIS]["lauf"]["status"] == "fertig"


def test_m5_ein_abgebrochener_lauf_bleibt_auch_in_der_sitzung_abgebrochen(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    katalog = {"ablaeufe": [_roh(aktiv=False)]}
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog).get("ablaeufe") or [])
    geschrieben = _festgeschrieben(monkeypatch)
    _pruefe(state)
    assert geschrieben[-1][arbeitsstand.VERWEIS]["lauf"]["status"] == "abgebrochen"


# ── M7 ──────────────────────────────────────────────────────────────────────────────────────

def test_m7_die_verbindung_ist_frei_vor_der_b_api_und_vor_dem_treiber(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    folge: list[str] = []

    async def frei(session):
        folge.append("frei")

    async def stand(job_id):
        folge.append("b-api")
        return client.Stand("fertig", {"markdown": "# T"}, [])

    weiter = treiber.weiter_auftrag

    async def treiber_weiter(*a, **k):
        folge.append("treiber")
        return await weiter(*a, **k)

    monkeypatch.setattr(zug_basis, "verbindung_freigeben", frei)
    monkeypatch.setattr(client, "stand", stand)
    monkeypatch.setattr(treiber, "weiter_auftrag", treiber_weiter)
    _pruefe(state)
    assert folge.index("frei") < folge.index("b-api")
    assert "frei" in folge[folge.index("b-api") + 1:folge.index("treiber")]


def test_m7_wartet_auf_gibt_die_verbindung_vor_der_sicherheitspruefung_frei(monkeypatch):
    folge: list[str] = []

    async def frei(session):
        folge.append("frei")

    async def lesen(s, vid, aufrufer):
        folge.append("lesen")
        return None

    monkeypatch.setattr(zug_basis, "verbindung_freigeben", frei)
    monkeypatch.setattr(zug.vorgaenge, "lesen", lesen)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")
    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: True)
    aufrufer = arbeitsstand.aufrufer_fuer("sitzung-0123456789")
    state = {"entities": {arbeitsstand.VERWEIS: {
        "id": "v-1", "b": arbeitsstand._besitz(aufrufer), "titel": "x",
        "bis": "2099-01-01T00:00:00+00:00", "teile": {},
        "lauf": {"ablauf": "a", "status": treiber.WARTET}}}}
    asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, {"block_id": "b1"}))
    assert folge == ["lesen", "frei"]


# ── Endgültige b-api-Gründe ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("grund", ["unbekannt", "aus"])
def test_ein_endgueltiger_grund_geht_zu_bei_fehler(im_zug, monkeypatch, grund):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)

    async def stand(job_id):
        raise client.AuftragFehler(grund)

    monkeypatch.setattr(client, "stand", stand)
    antwort = _pruefe(state)
    assert antwort.content == "Das Lesen hat nicht geklappt."
    assert antwort.quick_replies == vorgang_aktion.knoepfe("de")      # kein „Stand prüfen“
    assert im_zug.ablage.auftraege[0].status == "fehler"


def test_ein_abgewiesener_schluessel_ohne_endlos_knopf(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)

    async def stand(job_id):
        raise client.AuftragFehler("abgewiesen")

    monkeypatch.setattr(client, "stand", stand)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragAbgewiesen")
    assert antwort.quick_replies == []


def test_ein_vorubergehender_grund_behaelt_den_knopf(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)

    async def stand(job_id):
        raise client.AuftragFehler("voll")

    monkeypatch.setattr(client, "stand", stand)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNichtAbrufbar")
    assert antwort.quick_replies


# ── Neuer Lauf, Wendung, Fassung, Grenzen, Zwischenspeicher ───────────────────────────────────

def test_ein_neuer_lauf_schliesst_den_auftrag_des_alten(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    zweiter = {"id": "gruss", "titel": {"de": "Gruß"}, "aktiv": True,
               "ausloeser": [{"art": "knopf"}],
               "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Hallo."}}]}
    katalog = {"ablaeufe": [_roh(schritte=[{**_SCHRITTE[0], "argumente": {"text": "fest"}},
                                           *_SCHRITTE[1:]]), zweiter]}
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog).get("ablaeufe") or [])
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "gruss"})
    assert asyncio.run(zug.starten(_S(), anfrage, state)).content == "Hallo."
    assert im_zug.ablage.auftraege[0].status == "abgebrochen"


def test_eine_wendung_ohne_erfuellte_voraussetzung_startet_nichts(monkeypatch):
    katalog = {"ablaeufe": [{"id": "baum", "titel": {"de": "Baum"}, "aktiv": True,
                             "voraussetzungen": ["anmeldung"],
                             "ausloeser": [{"art": "text", "wendungen": ["themenbaum aus"]}],
                             "schritte": [{"id": "ende", "typ": "ende"}]}]}
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog).get("ablaeufe") or [])
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: False)
    assert zug.text_ausloeser("Mach einen Themenbaum aus meinem Ordner") is None
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: True)
    assert zug.text_ausloeser("Mach einen Themenbaum aus meinem Ordner").id == "baum"


def test_die_fassung_haengt_nicht_an_neuen_leeren_feldern():
    ablauf = AblaufArea.model_validate(_roh())

    class SchrittMitMehr(Schritt):
        neues_feld: str | None = None

    erweitert = ablauf.model_copy(update={"schritte": [
        SchrittMitMehr(**s.model_dump()) for s in ablauf.schritte]})
    assert treiber.fassung(erweitert) == treiber.fassung(ablauf)


@pytest.mark.parametrize("aenderung", [
    {"titel": {"de": "x" * 121}},
    {"wann": ["w"] * 6},
    {"wann": ["w" * 201]},
    {"nicht_wann": ["n" * 201]},
])
def test_laengengrenzen_der_werkzeugbeschreibung(aenderung):
    with pytest.raises(ValidationError):
        AblaufArea.model_validate(_roh(**aenderung))


def test_der_katalog_wird_je_stand_einmal_geprueft(monkeypatch):
    katalog = {"ablaeufe": [_roh()]}
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog).get("ablaeufe") or [])
    gerufen: list[int] = []
    echt = AblaufArea.model_validate

    def zaehle(roh, *a, **k):
        gerufen.append(1)
        return echt(roh, *a, **k)

    monkeypatch.setattr(ausloeser.AblaufArea, "model_validate", zaehle)
    ausloeser.katalog()
    ausloeser.katalog()
    assert len(gerufen) == 1
    katalog["ablaeufe"] = [_roh(titel={"de": "Neu"})]
    assert ausloeser.katalog()[0].titel["de"] == "Neu"
    assert len(gerufen) == 2



# ── Review Q2 ───────────────────────────────────────────────────────────────────────────────

def test_review_q2_1_abgewiesen_bricht_den_lauf_ab(im_zug, monkeypatch):  # noqa: F811
    """Sonst sperrte der wartende Lauf jeden Neustart, und „Stand prüfen“ käme wieder."""
    state: dict = {"entities": {}}
    _starte(state)

    async def stand(job_id):
        raise client.AuftragFehler("abgewiesen")

    monkeypatch.setattr(client, "stand", stand)
    geschrieben = _festgeschrieben(monkeypatch)
    _pruefe(state)
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert im_zug.ablage.auftraege[0].status == "abgebrochen"
    assert geschrieben[-1][arbeitsstand.VERWEIS]["lauf"]["status"] == "abgebrochen"


def test_review_q2_2_wartet_auf_frischt_einen_weitergeschobenen_lauf_auf(im_zug):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    [v] = im_zug.speicher.v.values()
    # Diese Sitzung glaubt, der Lauf warte auf eine Person; die andere hat ihn weitergeschoben.
    state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] = treiber.WARTET
    assert v.akte["lauf"]["status"] == treiber.WARTET_AUFTRAG
    wartet = asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, {"block_id": "x"}))
    assert wartet is False
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == treiber.WARTET_AUFTRAG


def test_review_q2_6_weiter_nach_ki_frischt_auf_und_schreibt_fest(im_zug, monkeypatch):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] = treiber.WARTET_KI
    geschrieben = _festgeschrieben(monkeypatch)
    anfrage = _req(action=zug.AKTION_WEITER, action_params={"ablauf": "lesen"})
    antwort = asyncio.run(zug.weiter_nach_ki(_S(), anfrage, state))
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")
    assert geschrieben[-1][arbeitsstand.VERWEIS]["lauf"]["status"] == treiber.WARTET_AUFTRAG


def test_review_q2_4_ein_gescheiterter_neustart_laesst_das_ki_budget_stehen(im_zug, monkeypatch):  # noqa: F811
    from boerdi.services.ablauf import ki_schritt

    state: dict = {"entities": {ki_schritt.ZUEGE_KEY: {"zug": 3}}}

    async def kaputt(session, ablauf, aufruf):
        aufruf.close()
        return None

    monkeypatch.setattr(zug_basis, "rechne", kaputt)
    geschrieben = _festgeschrieben(monkeypatch)
    antwort = _starte(state)
    assert antwort.content == bot_text("de", "action.ablauf.fehler")
    assert state["entities"][ki_schritt.ZUEGE_KEY] == {"zug": 3}
    assert geschrieben and geschrieben[-1][ki_schritt.ZUEGE_KEY] == {"zug": 3}
