"""Paket K2b (Plan 2026-11-08): einen wartenden Auftrag abbrechen und die Eingabe je Schritt
sperren.

- Direktaktion ``ablauf_auftrag_abbrechen {ablauf}``: erst eine Rückfrage, mit ``bestaetigt`` endet
  der Lauf (``abgebrochen``) und der Auftrag — nach dem Festschreiben auch bei der b-api.
- Unter „läuft noch“ stehen „Stand prüfen“ und „Abbrechen“.
- ``warten: gesperrt`` am Auftragsschritt: solange der Lauf wartet, beantwortet der Preflight
  getippte Nachrichten und Modul-Antworten nur mit einem Hinweis samt Knöpfen; die Antwort trägt
  ``eingabe_gesperrt``.
"""
# ruff: noqa: F811 — die Fixtures kommen per Import aus test_ablauf_auftrag

from __future__ import annotations

import asyncio
import copy
import json

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.graph.nodes import preflight_ablauf
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text
from boerdi.services import vorgaenge, vorgang_aktion
from boerdi.services.ablauf import auftrag_zug, ausloeser
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.services.auftraege import client
from tests.test_ablauf_auftrag import (  # noqa: F401 — Fixtures
    _SCHRITTE,
    _pruefe,
    _roh,
    _starte,
    abbrueche,
    freigeschaltet,
    im_zug,
)
from tests.test_ablauf_zug import _S, _req

_SID = "sitzung-0123456789"
_K1 = client.kuerzel("job-1")


def _abbrechen(state, **params):
    anfrage = _req(action=auftrag_zug.AKTION_ABBRECHEN, action_params={"ablauf": "lesen", **params})
    return asyncio.run(auftrag_zug.abbrechen(_S(), anfrage, state))


def _aktionen(antwort_oder_knoepfe) -> list[tuple[str, dict]]:
    knoepfe = getattr(antwort_oder_knoepfe, "quick_replies", antwort_oder_knoepfe)
    aus = []
    for knopf in knoepfe:
        teile = knopf.split("|", 3)
        if len(teile) == 4 and teile[0] == "__action__":
            aus.append((teile[2], json.loads(teile[3])))
    return aus


def _gesperrt_katalog(monkeypatch, warten="gesperrt"):
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[0] = {**schritte[0], "argumente": {"text": "fest"}, "warten": warten}
    katalog = {"ablaeufe": [_roh(schritte=schritte)]}
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog).get("ablaeufe") or [])


# ── Abbrechen ───────────────────────────────────────────────────────────────────────────────

def test_abbrechen_fragt_erst_nach(im_zug, abbrueche):
    state: dict = {"entities": {}}
    _starte(state)
    antwort = _abbrechen(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragAbbrechenFrage")
    assert _aktionen(antwort) == [(auftrag_zug.AKTION_ABBRECHEN,
                                   {"ablauf": "lesen", "bestaetigt": True, "kuerzel": _K1}),
                                  (auftrag_zug.AKTION, {"ablauf": "lesen"})]
    assert abbrueche == [] and im_zug.ablage.auftraege[0].status == "laeuft"


def test_bestaetigtes_abbrechen_beendet_lauf_und_auftrag(im_zug, abbrueche):
    state: dict = {"entities": {}}
    _starte(state)
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.auftragAbgebrochen")
    assert antwort.quick_replies == vorgang_aktion.knoepfe("de")
    assert abbrueche == ["job-1"] and im_zug.ablage.auftraege[0].status == "abgebrochen"
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert auftrag_zug.pruefen_knoepfe(_SID, state, "de") == []


def test_abbrechen_ohne_wartenden_lauf(im_zug, abbrueche):
    state: dict = {"entities": {}}
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    # Zweites Review K2b, Befund 9: den Ablauf gibt es — sein Auftrag läuft nur nicht (mehr).
    assert antwort.content == bot_text("de", "action.ablauf.auftragSchonBeendet")
    assert abbrueche == []


def test_abbrechen_bei_konflikt_sendet_kein_delete(im_zug, monkeypatch, abbrueche):
    state: dict = {"entities": {}}
    _starte(state)

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v-1")

    monkeypatch.setattr(vorgaenge, "lauf_setzen", konflikt)
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    assert abbrueche == []


def test_unter_laeuft_noch_stehen_pruefen_und_abbrechen(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("laeuft"))
    antwort = _pruefe(state)
    beide = [auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN]
    assert [a for a, _p in _aktionen(antwort)] == beide
    assert [a for a, _p in _aktionen(auftrag_zug.pruefen_knoepfe(_SID, state, "de"))] == beide


# ── Sperre je Schritt ──────────────────────────────────────────────────────────────────────

def test_warten_gilt_nur_am_auftragsschritt(freigeschaltet):  # noqa: F811
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[1] = {**schritte[1], "warten": "gesperrt"}
    befunde = pruefe(AblaufArea.model_validate(_roh(schritte=schritte)))
    assert any("warten" in b for b in befunde)
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[0] = {**schritte[0], "warten": "gesperrt"}
    assert pruefe(AblaufArea.model_validate(_roh(schritte=schritte))) == []


def test_ohne_angabe_ist_nichts_gesperrt(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    assert auftrag_zug.gesperrt(_SID, state) is None


def test_ein_gesperrter_schritt_sperrt_bis_zum_ende(im_zug, monkeypatch):
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    _pruefe(state)
    assert auftrag_zug.gesperrt(_SID, state) is None


def _preflight(state, message="", **req):
    ctx = TurnContext(req=_req(**req).model_copy(update={"message": message}), session_state=state)

    async def lauf():
        a = await preflight_ablauf.bestimmen(ctx, _S())
        return a, await preflight_ablauf.antwort(ctx, _S(), a, [])
    return asyncio.run(lauf())


def test_getippter_text_bekommt_im_gesperrten_lauf_den_hinweis(im_zug, monkeypatch):
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    a, antwort = _preflight(state, message="Was gibt es zu Optik?")
    assert a.gesperrt == "lesen" and a.irgendeiner
    assert antwort.antwort.content == bot_text("de", "action.ablauf.auftragGesperrt")
    assert [x for x, _p in _aktionen(antwort.antwort)] == [auftrag_zug.AKTION,
                                                           auftrag_zug.AKTION_ABBRECHEN]
    assert im_zug.staende == []           # der Hinweis fragt die b-api nicht


def test_im_freien_lauf_geht_getippter_text_den_gewoehnlichen_weg(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    a, antwort = _preflight(state, message="Was gibt es zu Optik?")
    assert a.gesperrt is None and antwort is None


@pytest.mark.parametrize("aktion", [auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN,
                                    vorgang_aktion.AKTION_NEU, vorgang_aktion.AKTION_LOESCHEN])
def test_die_auftrags_aktionen_bleiben_im_gesperrten_lauf_erlaubt(im_zug, monkeypatch, aktion):
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    assert not preflight_ablauf.abgewiesen(aktion, "lesen")


def test_andere_aktionen_sind_im_gesperrten_lauf_abgewiesen():
    assert preflight_ablauf.abgewiesen("browse_collection", "lesen")
    assert not preflight_ablauf.abgewiesen("browse_collection", None)


def test_die_antwort_traegt_die_sperre_ans_widget(im_zug, monkeypatch):
    """Nach dem Zug (beide Wege, ``api/chat._anmeldestand``): solange der gesperrte Schritt wartet,
    ``eingabe_gesperrt``; danach nicht mehr."""
    from boerdi.api import chat

    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    antwort = _starte(state)
    zustand = {"response": antwort, "session_state": state}
    assert chat._anmeldestand(antwort, _req(), zustand).eingabe_gesperrt is True
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    fertig = _pruefe(state)
    assert chat._anmeldestand(fertig, _req(), {"session_state": state}).eingabe_gesperrt is False


def test_ein_altes_ja_beendet_keinen_spaeteren_auftrag(im_zug, monkeypatch, abbrueche):
    """Review K2b, Befund 2: die Bestätigung trägt das Kürzel des Auftrags, für den sie gefragt
    wurde — ein altes „Ja, abbrechen“ im Verlauf fragt beim neuen Auftrag erst wieder nach."""
    async def starten(flow, eingaben):
        im_zug.gestartet.append((flow, eingaben))
        return f"job-{len(im_zug.gestartet)}"

    monkeypatch.setattr(client, "starten", starten)
    state: dict = {"entities": {}}
    _starte(state)
    _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    _starte(state)                                    # derselbe Ablauf, neuer Auftrag job-2
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.auftragAbbrechenFrage")
    assert abbrueche == ["job-1"] and im_zug.ablage.auftraege[-1].status == "laeuft"
    assert _aktionen(antwort)[0][1]["kuerzel"] == client.kuerzel("job-2")


def test_ein_zweites_ja_meldet_schon_beendet(im_zug, abbrueche):
    state: dict = {"entities": {}}
    _starte(state)
    _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.auftragSchonBeendet")
    assert abbrueche == ["job-1"]


def test_warten_aendert_die_fassung_bestehender_ablaeufe_nicht():
    """Review K2b, Befund 1: ``treiber.fassung`` lässt nur ``None`` weg — mit der Vorgabe ``frei``
    bräche nach dem Deploy jeder wartende Lauf ab (samt DELETE bei der b-api)."""
    from boerdi.services.ablauf import treiber

    ablauf = AblaufArea.model_validate(_roh())
    assert all("warten" not in s.model_dump(mode="json", exclude_none=True)
               for s in ablauf.schritte)
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[0] = {**schritte[0], "warten": "frei"}
    gesetzt = treiber.fassung(AblaufArea.model_validate(_roh(schritte=schritte)))
    assert gesetzt != treiber.fassung(ablauf)  # ein gesetzter Wert ist eine bewusste Änderung


def test_hintergrund_zuege_sperren_nichts(im_zug, monkeypatch):
    """Kontext-Ping und Tour-Tick schickt das Widget von sich aus — kein Hinweis darauf."""
    from boerdi.api.schemas import Environment

    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    ctx = TurnContext(req=_req().model_copy(update={
        "message": "[context-open]", "environment": Environment(page_event="context_open")}),
        session_state=state)
    a = asyncio.run(preflight_ablauf.bestimmen(ctx, _S()))
    assert a.gesperrt is None and not a.irgendeiner


def test_eine_gesperrte_antwort_ohne_knoepfe_bekommt_sie(im_zug, monkeypatch):
    """Review K2b, Befund 3: Konflikt, Drosselung, Sicherheits-Block tragen keine Knöpfe."""
    from boerdi.api import chat
    from boerdi.api.schemas import ChatResponse

    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    leer = ChatResponse(session_id=_SID, content="Konflikt")
    chat._anmeldestand(leer, _req(), {"session_state": state})
    assert leer.eingabe_gesperrt is True
    assert [a for a, _p in _aktionen(leer)] == [auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN]


def test_die_sperre_bricht_nie_einen_zug(im_zug, monkeypatch):
    from boerdi.api import chat
    from boerdi.api.schemas import ChatResponse

    def kaputt(*_a):
        raise RuntimeError("x")

    monkeypatch.setattr(auftrag_zug, "gesperrt", kaputt)
    antwort = ChatResponse(session_id=_SID, content="x")
    assert chat._anmeldestand(antwort, _req(), {"session_state": {}}).eingabe_gesperrt is False


# ── Zweites Review K2b ─────────────────────────────────────────────────────────────────────

def _kontext_ping():
    from boerdi.api.schemas import Environment

    return _req().model_copy(update={
        "message": "[context-open]", "environment": Environment(page_event="context_open")})


def test_stumme_hintergrund_antworten_bekommen_keine_knoepfe(im_zug, monkeypatch):
    """Befund 1: die leere Antwort eines Kontext-Pings zeigte sonst eine Blase mit zwei Knöpfen."""
    from boerdi.api import chat
    from boerdi.api.schemas import ChatResponse

    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    stumm = ChatResponse(session_id=_SID, content="")
    chat._anmeldestand(stumm, _kontext_ping(), {"session_state": state})
    assert stumm.quick_replies == [] and stumm.eingabe_gesperrt is True


def test_nach_einer_krise_ist_nichts_gesperrt(im_zug, monkeypatch):
    """Befund 2: die Krisenantwort sperrt nicht, und die Sperre ruht für dieses Warten."""
    from boerdi.api import chat
    from boerdi.api.schemas import ChatResponse, SafetyDecision

    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    krise = ChatResponse(session_id=_SID, content="Ich bin für dich da.")
    chat._anmeldestand(krise, _req(), {"session_state": state,
                                       "safety": SafetyDecision(risk_level="high")})
    assert krise.eingabe_gesperrt is False and krise.quick_replies == []
    auftrag_zug.sperre_aussetzen(_SID, state)
    assert auftrag_zug.gesperrt(_SID, state) is None
    a, antwort = _preflight(state, message="mir geht es nicht gut")
    assert a.gesperrt is None and antwort is None          # die Antwort geht den gewöhnlichen Weg


def test_die_ruhende_sperre_gilt_nur_fuer_ihr_warten(im_zug, monkeypatch):
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    auftrag_zug.sperre_aussetzen(_SID, state)
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    _pruefe(state)
    ctx = TurnContext(req=_req().model_copy(update={"message": "danke"}), session_state=state)
    asyncio.run(preflight_ablauf.bestimmen(ctx, _S()))
    assert auftrag_zug.SPERRE_RUHT not in ctx.session_state
    state = ctx.session_state
    _starte(state)                                          # ein neues Warten sperrt wieder
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"


def test_der_preflight_setzt_die_sperre_nach_einer_krise_aus(im_zug, monkeypatch):
    """Der ganze Knoten: im gesperrten Lauf geht eine getippte Krise den gewöhnlichen Weg (M01),
    gewöhnlicher Text bekommt den Hinweis."""
    from boerdi.api.schemas import SafetyDecision
    from boerdi.graph.nodes import preflight as pf_mod
    from boerdi.services.rate_limits import RateVerdict

    async def frei(*_a, **_k):
        return RateVerdict(allowed=True)

    async def nichts(*_a, **_k):
        return None

    risiko = {"stufe": "low"}

    async def sicherheit(*_a, **_k):
        return SafetyDecision(risk_level=risiko["stufe"])

    monkeypatch.setattr(pf_mod, "check_rate_limit", frei)
    monkeypatch.setattr(pf_mod, "assess_safety", sicherheit)
    monkeypatch.setattr(pf_mod, "log_safety_event", nichts)
    monkeypatch.setattr(pf_mod, "save_message", nichts)
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)

    def zug(text, stand):  # TurnContext kopiert den Stand — der Zug gibt ihn zurück
        ctx = TurnContext(req=_req().model_copy(update={"message": text}), session_state=stand)
        return asyncio.run(pf_mod.preflight(ctx, _S()))

    hinweis = zug("Was gibt es zu Optik?", state).early_response
    assert hinweis.content == bot_text("de", "action.ablauf.auftragGesperrt")
    risiko["stufe"] = "high"
    krise = zug("ich will nicht mehr", state)
    assert krise.early_response is None
    assert krise.session_state[auftrag_zug.SPERRE_RUHT]
    risiko["stufe"] = "low"
    assert zug("mir geht es schlecht", krise.session_state).early_response is None


def test_der_deckel_laesst_im_gesperrten_lauf_die_auftrags_knoepfe_stehen(im_zug, monkeypatch):
    """Befund 3: ``max_count: 0`` (oder 1) strich sonst den einzigen Weg weiter."""
    from boerdi.api.schemas import ChatResponse
    from boerdi.services import config_loader
    from boerdi.services import widget_postprocess as wp

    knoepfe = auftrag_zug.knoepfe("lesen", "de")
    assert wp._auftrags_knoepfe_behalten(["a", *knoepfe], []) == knoepfe
    assert wp._auftrags_knoepfe_behalten(["a", "b", *knoepfe], ["a", "b", knoepfe[0]]) == [
        *knoepfe, "a"]
    assert wp._auftrags_knoepfe_behalten(["a", "b"], ["a"]) == ["a"]

    monkeypatch.setattr(config_loader, "load_display_rules_config",
                        lambda: {"quick_replies": {"max_count": 0}})

    def nach(gesperrt):
        resp = ChatResponse(session_id=_SID, content="Hinweis", quick_replies=list(knoepfe),
                            eingabe_gesperrt=gesperrt)
        return asyncio.run(wp._postprocess_response_for_widget_modes(_req(), resp)).quick_replies

    assert nach(True) == knoepfe
    assert nach(False) == knoepfe        # R2-e: auch ohne Sperre übersteht sie jeder Deckel


def test_neues_vorhaben_fragt_bei_laufendem_auftrag_erst_nach(im_zug, abbrueche):
    """Befund 5: ein alter „Neues Vorhaben“-Knopf beendete sonst still den Auftrag."""
    state: dict = {"entities": {}}
    _starte(state)

    def neu(**params):
        anfrage = _req(action=vorgang_aktion.AKTION_NEU, action_params=params)
        return asyncio.run(vorgang_aktion.neu(_S(), anfrage, state))

    frage = neu()
    assert frage.content == bot_text("de", "action.vorgang.neuFrage")
    assert _aktionen(frage) == [(vorgang_aktion.AKTION_NEU, {"bestaetigt": True, "kuerzel": _K1})]
    assert abbrueche == [] and im_zug.ablage.auftraege[0].status == "laeuft"
    assert neu(bestaetigt=True, kuerzel="alt").content == bot_text("de", "action.vorgang.neuFrage")
    assert neu(bestaetigt=True, kuerzel=_K1).content == bot_text("de", "action.vorgang.neu")
    assert abbrueche == ["job-1"]


def test_ein_leeres_warten_aus_dem_studio_ist_nicht_gesetzt():
    """Befund 6: „— nicht gesetzt —“ speichert das Studio als ``""`` — kein 422."""
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[0] = {**schritte[0], "warten": ""}
    ablauf = AblaufArea.model_validate(_roh(schritte=schritte))
    assert ablauf.schritte[0].warten is None
    with pytest.raises(ValueError):
        schritte[0] = {**schritte[0], "warten": "Gesperrt"}
        AblaufArea.model_validate(_roh(schritte=schritte))


def test_abbrechen_ohne_schluessel_sagt_dass_der_auftrag_weiterlaeuft(im_zug, monkeypatch,
                                                                     abbrueche):
    """Befund 8: ohne den Schlüssel der Person endet der Auftrag nur hier."""
    from boerdi.services import llm_auth

    state: dict = {"entities": {}}
    _starte(state)
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: False)
    monkeypatch.setattr(llm_auth, "hat_zug_schluessel", lambda: False)
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNurHierAbgebrochen")
    assert abbrueche == []


def test_ein_knopf_nach_dem_loeschen_meldet_schon_beendet(im_zug, abbrueche):
    """Befund 9: ein Abbruch-Knopf, dessen Arbeitsstand gelöscht ist."""
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.speicher.v.clear()
    antwort = _abbrechen(state, bestaetigt=True, kuerzel=_K1)
    assert antwort.content == bot_text("de", "action.ablauf.auftragSchonBeendet")
