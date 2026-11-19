"""Review N4 (19.11.): Befunde 3, 4, 6, 7, 8 und NIT — je über die Drahtform des MCP.

Treiber-Ebene über ``_am_auftrag`` (Rückfrage „Ja“ → Box → echte Freigabe
``auftrag_freigabe_zug.starten``), Zug-Ebene über die Fixture ``n4``.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services.ablauf import (
    auftrag_freigabe,
    auftrag_zug,
    freigabe_zug,
    treiber,
)
from boerdi.services.auftraege import client, mcp_vorschau
from boerdi.services.mcp import auth
from tests.test_ablauf_auftrag import _starte, freigeschaltet, im_zug  # noqa: F401
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_k_mcp_starter import TOKEN, _abgelehnt, _ok
from tests.test_paket_k_mcp_starter import mcp as mcp_fixture  # noqa: F401
from tests.test_paket_k_traeger import _am_auftrag
from tests.test_paket_k_traeger import lage as traeger_lage  # noqa: F401
from tests.test_paket_k_zug import ueber_mcp  # noqa: F401
from tests.test_paket_n4_freigabe import FREI, _aktion, _antworten, _box, _lauf, n4  # noqa: F401
from tests.test_paket_n4_vorschau import _vorschau

NICHT_DA = {"error": {"kind": "tool", "message": "MCP error -32602: Tool wlo_start_flow not found"}}
GESTARTET = _ok({"status": "started", "jobId": "job-7", "flow": "f/meta"})


def _ablauf(ids=("n-1", "n-2", "n-3"), flow="f/meta") -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "meta", "titel": {"de": "Meta"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "voraussetzungen": ["anmeldung"], "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Metadaten erzeugen?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "lauf"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "ohne"}]},
            {"id": "lauf", "typ": "auftrag", "flow": flow, "repo_schreibt": True,
             "argumente": {"node_ids": list(ids), "language": "de"},
             "schreibt": "ergebnis", "bei_fehler": "ohne", "text": {"de": "Ich starte."}},
            {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
            {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Metadaten."}}]})


@pytest.fixture
def draht(traeger_lage, mcp_fixture, monkeypatch):  # noqa: F811
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    monkeypatch.setattr(auftrag_freigabe, "aufrufer_kennung", lambda: "person-a")
    return mcp_fixture


def _rueckfrage(aus, satz: str) -> None:
    assert aus.lauf["status"] == treiber.WARTET_WAHL and aus.lauf["schritt"] == "frage"
    assert aus.texte[0] == satz and "Ohne Metadaten." not in aus.texte


def test_vorschau_mit_429_fuehrt_zur_rueckfrage(draht):
    draht["antworten"]["wlo_start_flow"] = [_abgelehnt("rate_limited", retryAfter=60)]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragVoll", minuten=1))


def test_nur_ungepruefte_sind_voruebergehend(draht):
    draht["antworten"]["wlo_start_flow"] = [_abgelehnt("upstream_error", problems=[
        {"nodeId": "n-1", "problem": "unchecked"}, {"nodeId": "n-2", "problem": "unchecked"}])]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragNichtVerfuegbar"))


def test_gemischte_probleme_mit_ungeprueften_sind_voruebergehend(draht):
    """Befund 4: ein ungeprüfter fällt nicht heraus — kein zweiter Versuch ohne ihn."""
    draht["antworten"]["wlo_start_flow"] = [_abgelehnt("bad_inputs", problems=[
        {"nodeId": "n-1", "problem": "not_writable"}, {"nodeId": "n-2", "problem": "unchecked"}])]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragNichtVerfuegbar"))
    assert len(draht["gerufen"]) == 1


def test_unbekanntes_werkzeug_bei_der_vorschau_fuehrt_zur_rueckfrage(draht, monkeypatch):
    async def nichts():
        return False

    from boerdi.services.mcp import faehigkeiten
    monkeypatch.setattr(faehigkeiten, "nachfragen", nichts)
    draht["antworten"]["wlo_start_flow"] = [NICHT_DA]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragNichtVerfuegbar"))


def test_keins_geht_mit(draht):
    draht["antworten"]["wlo_start_flow"] = [_abgelehnt("bad_inputs", problems=[
        {"nodeId": k, "problem": "not_writable"} for k in ("n-1", "n-2", "n-3")])]
    aus = _am_auftrag(_ablauf(), auftrag_zug.starter())
    assert aus.texte == [bot_text("de", "action.ablauf.auftragFreigabeKeins", n=3),
                         "Ohne Metadaten."]
    assert len(draht["gerufen"]) == 1


def test_zweite_vorschau_im_teil_scheitert_erneut(draht):
    draht["antworten"]["wlo_start_flow"] = [
        _abgelehnt("bad_inputs", problems=[{"nodeId": "n-2", "problem": "not_writable"}]),
        _abgelehnt("rate_limited")]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragVollOhneZeit"))


def test_429_beim_freigeben_fuehrt_zur_rueckfrage(draht):
    draht["antworten"]["wlo_start_flow"] = [
        _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]),
        _abgelehnt("rate_limited", outcome_open=False, retryAfter=120)]
    _rueckfrage(_am_auftrag(_ablauf(), auftrag_zug.starter()),
                bot_text("de", "action.ablauf.auftragVoll", minuten=2))
    assert draht["gerufen"][1][1]["confirmToken"] == TOKEN


# ── Befund 7: Texte je Flow ─────────────────────────────────────────────────────────────────

def test_ein_anderer_flow_hat_einen_neutralen_kopf(monkeypatch):
    monkeypatch.setattr(auftrag_freigabe, "aufrufer_kennung", lambda: "p")
    basis = {"erst": {}, "token": TOKEN, "laeuft_ab": 9e9, "probleme": [], "schritt": "s",
             "id": "x"}
    block = auftrag_freigabe.merken({}, {**basis, "flow": "f/andere", "eintraege": []}, "a", "de")
    assert block.daten["freigabe"]["metadaten"] is False
    assert block.text.startswith("**Dieser Auftrag schreibt in WLO: f/andere**")
    assert "0 Materialien" not in block.text and "Schlagworte" not in block.text
    eins = auftrag_freigabe.merken({}, {**basis, "flow": "f/andere", "eintraege": [("n", "")]},
                                   "a", "de")
    assert "(1 Material)" in eins.text
    meta = auftrag_freigabe.merken({}, {**basis, "flow": "edusharing.chatbot/node-metadata-write",
                                        "eintraege": [("n", "T")],
                                        "probleme": [("m", "not_found")]}, "a", "de")
    assert "1 Material wird in WLO erschlossen" in meta.text and "Schlagworte" in meta.text
    assert "1 Material geht nicht mit" in meta.text


def test_titel_versteht_json_items():
    items = ['{"node_ids":["n-1","n-2"],"language":"de"}', "n-3 „Drei“", "kein json"]
    assert mcp_vorschau._titel(items) == {"n-1": "", "n-2": "", "n-3": "Drei"}


def test_titel_aus_der_ablage_liest_auch_frueher():
    ablage = {"inhalte": [], "frueher": [{"node_id": "n-9", "titel": "Alt"}]}
    daten = auftrag_freigabe.box_daten({"id": "x", "flow": "f", "eintraege": [],
                                        "probleme": [("n-9", "not_found")]}, "a", ablage)
    assert daten["probleme"] == [{"titel": "Alt", "grund": "not_found"}]


# ── Zug: „Vorschau erneut zeigen“, Befund 3 und 8, Abbruch ──────────────────────────────────

def _erneut(state, ablauf="lesen"):
    anfrage = _req(action=freigabe_zug.AKTION_ERNEUT, action_params={"ablauf": ablauf})
    return asyncio.run(freigabe_zug.erneut(_S(), anfrage, state))


def test_vorschau_erneut_zeigen_am_auftragsschritt(n4, monkeypatch):  # noqa: F811
    monkeypatch.setattr(freigabe_zug, "schreiben_erlaubt", lambda: True)
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]),
               _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"], token="ct_2"))
    state: dict = {"entities": {}}
    erste = _box(_starte(state, freigeben=False))
    zweite = _box(_erneut(state))
    assert zweite["freigabe"]["id"] != erste["freigabe"]["id"]
    assert state["entities"][auftrag_freigabe.KEY]["token"] == "ct_2"
    alt = _aktion(state, FREI, erste)                 # die alte Box gilt nicht mehr
    assert alt.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")


def test_vorschau_erneut_zeigen_ohne_anmeldung(n4, monkeypatch):  # noqa: F811
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    _starte(state, freigeben=False)
    monkeypatch.setattr(auth, "has_personal_auth", lambda: False)
    monkeypatch.setattr(freigabe_zug, "schreiben_erlaubt", lambda: True)    # etwa das Gastkonto
    antwort = _erneut(state)
    assert antwort.content == bot_text("de", "action.ablauf.freigabeOhneAnmeldung")
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE
    assert len(n4.mcp["gerufen"]) == 1


def test_kein_satz_zur_neuen_box_ohne_neue_box(n4):  # noqa: F811
    """Befund 3: abgelaufen, die neue Vorschau scheitert — kein „hier ist sie neu“."""
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]), _abgelehnt("rejected"))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    state["entities"][auftrag_freigabe.KEY]["laeuft_ab"] = 0
    antwort = _aktion(state, FREI, daten)
    assert bot_text("de", "action.ablauf.auftragFreigabeNeu") not in antwort.content
    assert "Das Lesen hat nicht geklappt." in antwort.content


def test_abbrechen_des_ablaufs_entfernt_die_freigabe(n4):  # noqa: F811
    from boerdi.services.ablauf import abbruch_zug

    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    _starte(state, freigeben=False)
    frage = asyncio.run(abbruch_zug.abbrechen(_S(), _req(
        action=abbruch_zug.AKTION, action_params={"ablauf": "lesen"}), state))
    [ja] = [json.loads(t[3]) for t in (c.split("|", 3) for c in frage.quick_replies)
            if t[2] == abbruch_zug.AKTION]
    asyncio.run(abbruch_zug.abbrechen(_S(), _req(action=abbruch_zug.AKTION, action_params=ja),
                                      state))
    assert auftrag_freigabe.KEY not in state["entities"]


# ── Durchtest-Restpunkte (19.11.) ────────────────────────────────────────────────────────────

def test_ueber_der_box_steht_ihr_kopf_statt_weiter_gehts(n4):  # noqa: F811
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    antwort = _starte({"entities": {}}, freigeben=False)
    assert bot_text("de", "action.ablauf.weiter") not in antwort.content
    assert antwort.content == ("Dieser Auftrag schreibt in WLO: wlo/volltext (3 Materialien)"
                               + bot_text("de", "action.ablauf.auftragFreigabeBitte"))


def test_der_kopf_beim_metadaten_flow():
    from boerdi.services.ablauf import zug_basis

    aus = treiber.Ausgabe(lauf={"status": treiber.WARTET_FREIGABE}, auftrag_freigabe={
        "flow": "edusharing.chatbot/node-metadata-write", "eintraege": [("n-1", "A")] * 2})
    assert zug_basis.antwort_text("de", aus) == (
        "2 Materialien werden in WLO erschlossen – bitte prüfen und freigeben")
    assert zug_basis.antwort_text("en", aus) == (
        "2 materials will be indexed in WLO – please review and approve")


def test_eine_veraltete_freigabe_zeigt_die_knoepfe_von_jetzt(n4, monkeypatch):  # noqa: F811
    """Nach „Abbrechen“ wartet der Lauf an einer Frage — ein Klick auf die alte Box nennt
    „nicht mehr offen“ und gibt die Chips dieser Frage mit."""
    from boerdi.services.ablauf import ausloeser
    from tests.test_ablauf_auftrag import _SCHRITTE, _roh

    schritte = [{**_SCHRITTE[0], "repo_schreibt": True, "bei_fehler": "ohne",
                 "argumente": {"node_ids": ["n-1"], "language": "de"}}, _SCHRITTE[1],
                {"id": "ohne", "typ": "nachricht", "text": {"de": "Wie weiter?"},
                 "optionen": [{"id": "a", "label": {"de": "Nochmal"}, "ziel": "lesen"},
                              {"id": "b", "label": {"de": "Ende"}, "ziel": "fertig"}]}]
    katalog = [_roh(schritte=schritte)]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: katalog)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(freigabe_zug, "update_session", nichts)    # ``_laden(stumm=True)``
    _antworten(n4, _vorschau(["n-1 „A“"]))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    abgebrochen = _aktion(state, "ablauf_auftrag_verwerfen", daten)
    assert _lauf(state)["status"] == treiber.WARTET_WAHL and abgebrochen.quick_replies
    for nochmal in (FREI, "ablauf_auftrag_verwerfen"):
        alt = _aktion(state, nochmal, daten)
        assert alt.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")
        assert alt.quick_replies == abgebrochen.quick_replies
