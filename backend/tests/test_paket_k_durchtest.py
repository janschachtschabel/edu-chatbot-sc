"""Paket K: Befunde aus dem Staging-Durchtest vom 19.11. (Änderungsnotiz 2026-11-18, Paket K).

1. Der Flow ``node-metadata-write`` scheitert als Ganzes, sobald ein Markdown-Knoten dabei ist —
   md/markdown/txt gehen nicht an ihn; bleibt nichts übrig, kein Start, der Ersatzweg mit Satz.
2. Ein gescheiterter Flow hat einen eigenen Satz vor ``bei_fehler`` (Code nur aus fester Liste).
3. „k von n fertig“ zählt nur gelungene (auch mit Warnung) — gescheiterte getrennt.
4. Eine Wendung an einer wartenden Frage wird nicht still deren Antwort.
6. Ohne Anmeldung nennt ``schnell`` den Grund, warum es „gründlich“ nicht gibt.
8. Ein Platzhalter-Thema bei ``aus_inhalten`` weicht dem Titel des Entwurfs.
"""

from __future__ import annotations

import asyncio
import copy
import json
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.i18n import bot_text
from boerdi.services.ablauf import treiber, wahl_zug, wendung_zug, werkzeuge, zug, zug_basis
from boerdi.services.auftraege import client, mcp_starter
from tests.test_ablauf_auftrag import _pruefe, _starte, freigeschaltet, im_zug  # noqa: F401
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)
from tests.test_paket_k_mcp_starter import JOB, _ok
from tests.test_paket_k_zug import ueber_mcp  # noqa: F401 — Fixture

_SEED = AblaufArea.model_validate(yaml.safe_load(
    (pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml")
    .read_text(encoding="utf-8")))

_PDF = "11111111-1111-4111-8111-111111111111"
_MD = "22222222-2222-4222-8222-222222222222"
_TXT = "33333333-3333-4333-8333-333333333333"


# ── 1. md/txt gehen nicht an den Metadaten-Flow ─────────────────────────────────────────────────

def _metadaten_ablauf() -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "meta", "titel": {"de": "Meta"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "voraussetzungen": ["anmeldung"], "schritte": [
            {"id": "lauf", "typ": "auftrag", "flow": METADATEN_FLOW, "repo_schreibt": True,
             "argumente": {"node_ids": {"$teil": "ablage", "liste": "inhalte",
                                        "wo": {"stand": "stored"}, "feld": "node_id"}},
             "schreibt": "ergebnis", "bei_fehler": "ohne", "text": {"de": "Ich starte."}},
            {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
            {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Metadaten."}}]})


def _eintrag(node_id: str, name: str, art: str) -> dict:
    return {"index": 0, "titel": name, "name": name, "art": art, "stand": "stored",
            "node_id": node_id, "rolle": "inhalt"}


def _gestartet(*eintraege: dict, flow_ablauf: AblaufArea | None = None):
    teile = {"ablage": {"format": "wlo.ablage@1", "inhalte": list(eintraege)}}
    gestartet: list = []

    async def lader(name):
        return teile.get(name)

    async def starte(flow, args):
        gestartet.append((flow, args))
        return "job-1"

    aus = asyncio.run(treiber.starten(flow_ablauf or _metadaten_ablauf(),
                                      treiber.Umgebung(teile=lader, auftrag_starten=starte)))
    return aus, gestartet


def test_md_und_txt_gehen_nicht_an_den_metadaten_flow():
    aus, gestartet = _gestartet(_eintrag(_PDF, "Blatt.pdf", "pdf"),
                                _eintrag(_MD, "Lehrplan.md", "md"),
                                _eintrag(_TXT, "Notiz.TXT", ""))
    assert gestartet == [(METADATEN_FLOW, {"node_ids": [_PDF]})]
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert bot_text("de", "action.ablauf.metadatenOhneText") in aus.texte


def test_nur_md_startet_nichts_und_nimmt_den_ersatzweg_mit_satz():
    aus, gestartet = _gestartet(_eintrag(_MD, "Lehrplan.md", "md"),
                                _eintrag(_TXT, "x.markdown", "markdown"))
    assert gestartet == []
    assert aus.texte == [bot_text("de", "action.ablauf.metadatenOhneText"), "Ohne Metadaten."]


def test_ohne_md_bleibt_alles_wie_bisher():
    aus, gestartet = _gestartet(_eintrag(_PDF, "Blatt.pdf", "pdf"))
    assert gestartet == [(METADATEN_FLOW, {"node_ids": [_PDF]})]
    assert bot_text("de", "action.ablauf.metadatenOhneText") not in aus.texte


def test_andere_flows_bekommen_md_weiter():
    roh = _metadaten_ablauf().model_dump(exclude_none=True)
    roh["schritte"][0]["flow"] = "f/anders"
    _aus, gestartet = _gestartet(_eintrag(_MD, "Lehrplan.md", "md"),
                                 flow_ablauf=AblaufArea.model_validate(roh))
    assert gestartet == [("f/anders", {"node_ids": [_MD]})]


def test_der_seed_startet_den_metadaten_flow_ohne_md():
    """Der Schritt ``metadaten`` im Seed: dieselbe Auswahl, der Filter greift am Flow."""
    s = next(x for x in _SEED.schritte if x.id == "metadaten")
    assert s.flow == METADATEN_FLOW


# ── 2. Ein gescheiterter Flow sagt es ───────────────────────────────────────────────────────────

def _gestartet_mcp(lage) -> dict:
    state: dict = {"entities": {}}
    _starte(state)
    return state


@pytest.mark.parametrize(("antwort", "code"), [
    ({"status": "failed", "errorCode": "FLOW_FAILED"}, " (FLOW_FAILED)"),
    ({"status": "failed", "errorCode": "TIMEOUT"}, " (TIMEOUT)"),
    ({"status": "failed"}, ""),
    # ein unbekannter Code geht nicht an die Person
    ({"status": "failed", "errorCode": "Geheim: /pfad/zum/job"}, ""),
])
def test_ein_gescheiterter_flow_hat_einen_eigenen_satz(ueber_mcp, antwort, code):  # noqa: F811
    state = _gestartet_mcp(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [_ok(antwort)]
    inhalt = _pruefe(state).content
    satz = bot_text("de", "action.ablauf.auftragFehlgeschlagen", code=code)
    assert inhalt.startswith(satz) and "Das Lesen hat nicht geklappt." in inhalt
    assert "nicht eingerichtet" not in satz and JOB not in inhalt
    assert "Geheim" not in inhalt


def test_der_satz_englisch():
    assert "failed (FLOW_FAILED)" in bot_text("en", "action.ablauf.auftragFehlgeschlagen",
                                               code=" (FLOW_FAILED)")
    # Drittes Review, Punkt 5: neutral — der Satz gilt für jeden Auftrag, nicht nur Metadaten
    assert bot_text("de", "action.ablauf.auftragFehlgeschlagen", code=" (FLOW_FAILED)") == (
        "Der Auftrag in WLO ist fehlgeschlagen (FLOW_FAILED).")
    assert bot_text("en", "action.ablauf.auftragFehlgeschlagen", code="") == (
        "The job in WLO failed.")


def test_ohne_ersatzweg_kein_satz_zum_weitermachen():
    """Ohne ``bei_fehler`` endet der Lauf — „du kannst ohne weitermachen“ wäre falsch."""
    roh = _metadaten_ablauf().model_dump(exclude_none=True)
    roh["schritte"][0].pop("bei_fehler")
    ablauf = AblaufArea.model_validate(roh)
    lauf = {"ablauf": "meta", "fassung": treiber.fassung(ablauf), "status": treiber.WARTET_AUFTRAG,
            "schritt": "lauf"}

    async def nichts(_n):
        return None

    aus = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, None, treiber.Umgebung(teile=nichts),
                                             fehlschlag="SATZ"))
    assert "SATZ" not in aus.texte and aus.lauf["status"] == "fehler"


# ── 3. „k von n fertig“ ohne die gescheiterten ──────────────────────────────────────────────────

def test_fertig_zaehlt_keine_fehlschlaege():
    assert mcp_starter._fortschritt({"started": 3, "succeeded": 0, "warning": 0,
                                     "failed": 3}) == {"fertig": 0, "gesamt": 3,
                                                       "fehlgeschlagen": 3}
    assert mcp_starter._fortschritt({"started": 4, "succeeded": 2, "warning": 1,
                                     "failed": 0}) == {"fertig": 3, "gesamt": 4}


def test_laufend_mit_fehlschlag_nennt_beides(ueber_mcp):  # noqa: F811
    state = _gestartet_mcp(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [_ok({"status": "running", "progress": {
        "started": 5, "running": 1, "succeeded": 2, "warning": 1, "failed": 1}})]
    assert _pruefe(state).content == bot_text(
        "de", "action.ablauf.auftragLaeuftFortschrittFehler", fertig=3, gesamt=5,
        fehlgeschlagen=1)


# ── 4. Eine Wendung an einer wartenden Frage ────────────────────────────────────────────────────

def _wahl_ablauf(id_: str, titel: str, *wendungen: str) -> dict:
    return {"id": id_, "titel": {"de": titel}, "aktiv": True,
            "ausloeser": [{"art": "knopf"}, {"art": "text", "wendungen": list(wendungen)}],
            "schritte": [
                {"id": "wofuer", "typ": "nachricht", "text": {"de": "Wofür ist der Baum?"},
                 "schreibt": "zweck",
                 "optionen": [{"id": "unterricht", "label": {"de": "Unterricht"}, "ziel": "e"}],
                 "freitext": {"ziel": "e", "schreibt": "zweck"}},
                {"id": "e", "typ": "ende", "text": {"de": "Danke."}}]}


@pytest.fixture
def zwei_ablaeufe(umgebung):  # noqa: F811
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"], "ablaeufe": [
        _wahl_ablauf("baum", "Themenbaum erstellen", "themenbaum aus meinen dateien",
                     "themenbaum zu einem thema", "themenbaum aus dem lehrplan"),
        _wahl_ablauf("anders", "Anderes Vorhaben", "ein anderes vorhaben", "rundgang")]}
    state: dict = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "baum"}),
                            state))
    umgebung.state = state
    return umgebung


_SID = "sitzung-0123456789"


def _lauf(lage) -> dict:
    [v] = lage.speicher.v.values()
    return v.akte["lauf"]


def test_dieselbe_wendung_zeigt_die_offene_frage_erneut(zwei_ablaeufe):
    state = zwei_ablaeufe.state
    text = "Themenbaum aus meinen Dateien"
    ziel = wendung_zug.wendung_trifft(_SID, state, text, "de")
    assert ziel is not None and ziel.id == "baum"
    vorher = copy.deepcopy(_lauf(zwei_ablaeufe))
    antwort = asyncio.run(wendung_zug.wendung_beantworten(
        _S(), _req().model_copy(update={"message": text}), state, ziel))
    assert antwort.content.startswith(bot_text("de", "action.ablauf.schonMitten",
                                               titel="Themenbaum erstellen"))
    assert "Wofür ist der Baum?" in antwort.content
    # die Chips der Frage, dazu (drittes Review) „Neu starten“
    assert len(antwort.quick_replies) == 2 and "ablauf_wahl" in antwort.quick_replies[0]
    # nichts gespeichert: der Lauf wartet unverändert, kein Teil ``zweck``
    assert _lauf(zwei_ablaeufe) == vorher
    [v] = zwei_ablaeufe.speicher.v.values()
    assert "zweck" not in (v.akte.get("teile") or {})


def test_eine_fremde_wendung_bekommt_die_ersetzen_rueckfrage(zwei_ablaeufe):
    state = zwei_ablaeufe.state
    text = "bitte ein anderes Vorhaben"
    ziel = wendung_zug.wendung_trifft(_SID, state, text, "de")
    assert ziel is not None and ziel.id == "anders"
    antwort = asyncio.run(wendung_zug.wendung_beantworten(
        _S(), _req().model_copy(update={"message": text}), state, ziel))
    assert antwort.content == bot_text("de", "action.ablauf.ersetzen")
    assert any('"ablauf": "anders"' in k and "ersetzt" in k for k in antwort.quick_replies)
    assert _lauf(zwei_ablaeufe)["schritt"] == "wofuer"


def test_eine_antwort_ohne_wendung_bleibt_freitext(zwei_ablaeufe):
    state = zwei_ablaeufe.state
    assert wendung_zug.wendung_trifft(_SID, state, "für den Unterricht in Klasse 7", "de") is None
    # eine Beschriftung ist immer die Wahl, auch wenn sie eine Wendung enthielte
    assert wendung_zug.wendung_trifft(_SID, state, "Unterricht", "de") is None


def test_ohne_wartende_frage_greift_nichts(umgebung):  # noqa: F811
    assert wendung_zug.wendung_trifft(_SID, {"entities": {}}, "Themenbaum aus meinen Dateien",
                                   "de") is None


# ── 6. Ohne Anmeldung nennt ``schnell`` den Grund ───────────────────────────────────────────────

async def _nichts(_name):
    return None


def _bereit(**kontext) -> dict:
    return asyncio.run(werkzeuge.DIENSTE["bereitgestellt"](
        {}, werkzeuge.DienstKontext(teile=_nichts, **kontext)))


def test_bereit_nennt_warum_es_gruendlich_nicht_gibt():
    # Drittes Review, Punkt 4: „nur mit Anmeldung“ nur, wenn die Anmeldung den Weg öffnete
    ohne = _bereit(nach_anmeldung=lambda: True, wlo_ablage=lambda: False)
    assert ohne["ohne_gruendlich"] == bot_text("de", "action.ablauf.gruendlichNurAngemeldet")
    hilft_nicht = _bereit(nach_anmeldung=lambda: False, wlo_ablage=lambda: False)
    assert hilft_nicht["ohne_gruendlich"] == bot_text("de", "action.ablauf.gruendlichNichtDa")
    nicht_da = _bereit(nach_anmeldung=lambda: False, wlo_ablage=lambda: True,
                       wlo_erschliessen=lambda: False)
    assert nicht_da["ohne_gruendlich"] == bot_text("de", "action.ablauf.gruendlichNichtDa")
    geht = _bereit(nach_anmeldung=lambda: False, wlo_ablage=lambda: True,
                   wlo_erschliessen=lambda: True)
    assert geht["ohne_gruendlich"] is None


def test_der_satz_schnell_setzt_den_grund_ein():
    s = next(x for x in _SEED.schritte if x.id == "schnell")
    assert "{teil.bereit.ohne_gruendlich}" in s.text["de"]
    assert "{teil.bereit.ohne_gruendlich}" in s.text["en"]
    assert "Anmeldung" in bot_text("de", "action.ablauf.gruendlichNurAngemeldet")
    assert "sign-in" in bot_text("en", "action.ablauf.gruendlichNurAngemeldet")


# ── 8. Platzhalter-Thema bei ``aus_inhalten`` ───────────────────────────────────────────────────

@pytest.mark.parametrize(("thema", "platzhalter"), [
    ("Themen aus den bereitgestellten eigenen Dateien", True),
    ("Themen aus den bereitgestellten Dateien", True),
    ("Inhalte der Person", True),
    ("Meine Materialien", True),
    ("Topics from the provided files", True),
    ("Fotosynthese aus meinen Dateien", False),
    ("Optik", False),
    ("Themen", False),           # ohne Hinweis auf die Dateien: kein Platzhalter dieser Art
    ("", False),
])
def test_platzhalter_thema(thema, platzhalter):
    from boerdi.services.strukturentwurf_dienst import platzhalter_thema

    assert platzhalter_thema(thema) is platzhalter


def _aus_inhalten(monkeypatch, thema: str) -> dict:
    from boerdi.services import strukturentwurf_dienst as dienst
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def erzeugen(auftrag, *, llm, frist_ende, vorlage=None, dokument=None, moderieren=None):
        return dienst.Erzeugt(daten={"titel": "Fotosynthese und Blattaufbau", "quelle": "dokument",
                                     "thema": thema, "knoten": [{"id": "k1", "titel": "Blatt"}]})

    async def nicht_beanstandet(_text):
        return None

    async def teile(name):
        return {"format": "wlo.metadaten@1", "titel": "M", "fehlend": [], "inhalte": [
            {"i": 0, "titel": "Blatt", "rolle": "inhalt"}]} if name == "metadaten" else None

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    monkeypatch.setattr(modul_dienst, "_ebene_eins_pruefen", nicht_beanstandet)
    ergebnis = asyncio.run(modul_dienst.aufruf(
        katalog()["ui_strukturentwurf"], {"thema": thema, "aus_inhalten": True},
        Umgebung(teile=teile)))
    assert ergebnis.block is not None
    return ergebnis.block.daten


def test_ein_platzhalter_thema_wird_der_titel(monkeypatch):
    daten = _aus_inhalten(monkeypatch, "Themen aus den bereitgestellten eigenen Dateien")
    assert daten["thema"] == "Fotosynthese und Blattaufbau"


def test_ein_sachliches_thema_bleibt(monkeypatch):
    assert _aus_inhalten(monkeypatch, "Fotosynthese")["thema"] == "Fotosynthese"


# ── Drittes Review (19.11.) ─────────────────────────────────────────────────────────────────────

def _wendung(lage, text):
    return wendung_zug.wendung_trifft(_SID, lage.state, text, "de",
                                   ohne=zug_basis.abgelehnt(_SID, lage.state))


def _beantworten(lage, text, ziel):
    return asyncio.run(wendung_zug.wendung_beantworten(
        _S(), _req().model_copy(update={"message": text}), lage.state, ziel))


@pytest.mark.parametrize("text", [
    "Virtueller Stadtrundgang durch Rom",                              # Teilwort „rundgang“
    "Kein Themenbaum aus dem Lehrplan, sondern nach Kompetenzen geordnet",
    "Themenbaum zu einem Thema für die Klassen 7 und 8",               # mehr als 3 Wörter danach
])
def test_r3_1_eine_antwort_mit_wendung_darin_bleibt_freitext(zwei_ablaeufe, text):
    assert _wendung(zwei_ablaeufe, text) is None


@pytest.mark.parametrize("text", [
    "Themenbaum aus meinen Dateien", "themenbaum aus meinen dateien!",
    "Themenbaum aus meinen Dateien bitte", "Bitte Themenbaum aus meinen Dateien"])
def test_r3_1_die_echte_wendung_wird_erkannt(zwei_ablaeufe, text):
    assert _wendung(zwei_ablaeufe, text).id == "baum"


def test_r3_1_derselbe_text_ein_zweites_mal_ist_die_antwort(zwei_ablaeufe):
    """„Themenbaum zu einem Thema für Klasse 7“: höchstens 3 Wörter nach der Wendung — beim ersten
    Mal die Frage erneut, beim zweiten Mal ist es die Antwort (die Person kommt heraus)."""
    text = "Themenbaum zu einem Thema für Klasse 7"
    ziel = _wendung(zwei_ablaeufe, text)
    assert ziel is not None and ziel.id == "baum"
    _beantworten(zwei_ablaeufe, text, ziel)
    assert _wendung(zwei_ablaeufe, text) is None
    assert wahl_zug.nimmt_getippt(_SID, zwei_ablaeufe.state, text, "de")


def test_r3_1_die_ersetzen_rueckfrage_hat_hier_weitermachen(zwei_ablaeufe):
    text = "ein anderes Vorhaben"
    ziel = _wendung(zwei_ablaeufe, text)
    antwort = _beantworten(zwei_ablaeufe, text, ziel)
    hier = [k for k in antwort.quick_replies if k.split("|")[1] == "Hier weitermachen"]
    assert len(hier) == 1 and '"wahl": "_hier"' in hier[0] and '"schritt": "wofuer"' in hier[0]
    # wer die Rückfrage übergeht, hat abgelehnt: dieselbe Wendung ist danach die Antwort
    assert zug_basis.abgelehnt(_SID, zwei_ablaeufe.state) == "anders"
    assert _wendung(zwei_ablaeufe, text) is None
    # „Hier weitermachen“ zeigt die offene Frage mit ihren Chips, ohne etwas zu speichern
    params = json.loads(hier[0].split("|", 3)[3])
    weiter = asyncio.run(wahl_zug.waehlen(
        _S(), _req(action=wahl_zug.AKTION, action_params=params), zwei_ablaeufe.state))
    assert weiter.content == "Wofür ist der Baum?"
    assert any('"wahl": "unterricht"' in k for k in weiter.quick_replies)
    assert _lauf(zwei_ablaeufe)["schritt"] == "wofuer"


def test_r3_2_derselbe_ablauf_bietet_neu_starten(zwei_ablaeufe):
    text = "Themenbaum aus meinen Dateien"
    antwort = _beantworten(zwei_ablaeufe, text, _wendung(zwei_ablaeufe, text))
    assert antwort.content.startswith(bot_text("de", "action.ablauf.schonMitten",
                                               titel="Themenbaum erstellen"))
    assert "Neu starten" in bot_text("de", "action.ablauf.schonMitten", titel="T")
    assert "Restart" in bot_text("en", "action.ablauf.schonMitten", titel="T")
    assert any('"wahl": "unterricht"' in k for k in antwort.quick_replies)
    neu = [json.loads(k.split("|", 3)[3]) for k in antwort.quick_replies
           if k.split("|")[2] == zug.AKTION]
    assert len(neu) == 1 and neu[0]["ablauf"] == "baum" and isinstance(neu[0]["ersetzt"], str)
    # der Knopf ersetzt genau diesen Lauf: ein neuer beginnt, ohne erneute Rückfrage
    neu_start = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params=neu[0]),
                                        zwei_ablaeufe.state))
    assert neu_start.content != bot_text("de", "action.ablauf.ersetzen")
    assert "Wofür ist der Baum?" in neu_start.content


def test_r3_3_ohne_metadaten_nennt_keine_vermuteten_gruende():
    s = next(x for x in _SEED.schritte if x.id == "ohne_metadaten")
    assert s.text["de"] == ("Die Angaben aus WLO ließen sich gerade nicht erzeugen oder lesen. "
                            "Wie soll es weitergehen?")
    assert s.text["en"] == ("The details from WLO could not be created or read right now. "
                            "How shall we continue?")


def test_r3_4_gruendlich_nach_anmeldung(monkeypatch):
    from boerdi.ui_module import dienst_upload

    lage = {"schalter": {"ablage_nach_anmeldung": True}, "werkzeuge": True, "flow": True}
    monkeypatch.setattr(dienst_upload, "schalter", lambda: lage["schalter"])
    monkeypatch.setattr(mcp_starter, "verfuegbar", lambda: lage["werkzeuge"])
    monkeypatch.setattr(mcp_starter, "flow_erlaubt",
                        lambda flow: lage["flow"] and flow == METADATEN_FLOW)
    assert zug_basis.gruendlich_nach_anmeldung() is True
    for schluessel, wert in (("werkzeuge", False), ("flow", False),
                             ("schalter", {"ablage_in_wlo": False})):
        alt = lage[schluessel]
        lage[schluessel] = wert
        assert zug_basis.gruendlich_nach_anmeldung() is False, schluessel
        lage[schluessel] = alt


@pytest.mark.parametrize(("fortschritt", "schluessel"), [
    ({"fertig": 2, "gesamt": 5, "fehlgeschlagen": 1},
     "action.ablauf.auftragLaeuftFortschrittFehler"),
    # Drittes Review, Punkt 9: fertig + fehlgeschlagen über gesamt — ohne die Fehlerzahl
    ({"fertig": 3, "gesamt": 4, "fehlgeschlagen": 2}, "action.ablauf.auftragLaeuftFortschritt"),
])
def test_r3_9_der_chat_satz_prueft_die_zahlen(im_zug, fortschritt, schluessel):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("laeuft", fortschritt=fortschritt))
    assert _pruefe(state).content == bot_text("de", schluessel, **fortschritt)


def test_r3_9_unbrauchbare_zahlen_ergeben_den_satz_ohne_zahlen(im_zug):  # noqa: F811
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("laeuft", fortschritt={"fertig": 5, "gesamt": 4}))
    assert _pruefe(state).content == bot_text("de", "action.ablauf.auftragLaeuft")
