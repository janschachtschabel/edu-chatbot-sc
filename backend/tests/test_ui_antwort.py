"""Paket U1-d1 (d1-4, d1-5, d1-6): der Antwortweg eines abfragenden Moduls.

``ChatRequest.ui_antwort`` = ``{block_id, daten}``; ``message`` bleibt die lesbare Antwort (die
Nutzerblase). Geprüft wird im ersten Knoten (``setup``), vor Schreib-Abnahme und Sicherheit:
passt zur offenen Frage, gültig gegen ``antwort`` des Manifests, nur angebotene Kennungen,
Einzelwahl höchstens eine, Freitext nur, wo das Modul ihn anbot. Sonst fällt ``ui_antwort`` weg,
und die Nachricht zählt wie getippt. Jeder Vordergrund-Zug schließt die offene Frage; ein
Hintergrund-Zug (Kontext-Ping, Tour-Tick) lässt sie stehen. Die geprüfte Antwort steht im
Debug-Block der Nutzernachricht (``_ui_antwort``); daraus leitet der Verlauf den Status ab.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from pydantic import ValidationError

from boerdi.api import publikum
from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.ui_bloecke import fuer_den_debug_block
from boerdi.graph import build as build_mod
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import setup as setup_mod
from boerdi.graph.nodes.setup import setup
from boerdi.services import ui_antwort as ui_antwort_mod
from boerdi.services import write_approval as wa_mod
from boerdi.ui_module.antwort import DEBUG_KEY, OFFENE_FRAGE, merke_frage
from boerdi.ui_module.werkzeuge import modul_aufruf_annehmen

ENTSCHEIDUNG = "ui_entscheidung"
_SESSION = object()
_BLOCK_ID = "a1b2c3d4e5f60718"


def _offen(**mehr) -> dict:
    offen = {"block_id": _BLOCK_ID, "modul": ENTSCHEIDUNG, "frage": "Welche Klasse?",
             "optionen": [{"id": "a", "label": "Klasse 5"}, {"id": "b", "label": "Klasse 6"}],
             "mehrfach": False, "freitext": False}
    offen.update(mehr)
    return offen


class _Spy:
    def __init__(self, ret=None):
        self.calls: list[dict] = []
        self._ret = ret

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self._ret


def _zug(monkeypatch, *, ui_antwort=None, message="Klasse 6", offen=None, umgebung=None,
         pending=None):
    entities: dict = {}
    if offen is not False:
        entities[OFFENE_FRAGE] = offen or _offen()
    if pending is not None:
        entities["_pending_write"] = pending
    row = {"session_id": "bb-1", "entities": entities, "turn_count": 2, "tour_state": {}}
    monkeypatch.setattr(setup_mod, "get_or_create_session", _Spy(ret=row))
    monkeypatch.setattr(setup_mod, "get_messages", _Spy(ret=[]))
    gespeichert = _Spy()
    monkeypatch.setattr(ui_antwort_mod, "update_session", gespeichert)
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id="bb-1", message=message, environment=Environment(**(umgebung or {})),
        ui_antwort=ui_antwort))
    return asyncio.run(setup(ctx, _SESSION)), gespeichert


# ── d1-4 Anfrage ───────────────────────────────────────────────────────────


def test_die_anfrage_kennt_ui_antwort_und_prueft_die_kennung():
    req = ChatRequest(session_id="bb-1", message="x",
                      ui_antwort={"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"]}})
    assert req.ui_antwort is not None and req.ui_antwort.block_id == _BLOCK_ID
    assert ChatRequest(session_id="bb-1", message="x").ui_antwort is None
    with pytest.raises(ValidationError):
        ChatRequest(session_id="bb-1", message="x",
                    ui_antwort={"block_id": "../../x", "daten": {}})


def test_eine_gueltige_antwort_wird_geprueft_uebernommen(monkeypatch):
    ctx, gespeichert = _zug(monkeypatch, ui_antwort={"block_id": _BLOCK_ID,
                                                     "daten": {"gewaehlt": ["b"]}})
    assert ctx.ui_antwort == {"block_id": _BLOCK_ID, "modul": ENTSCHEIDUNG,
                              "frage": "Welche Klasse?", "daten": {"gewaehlt": ["b"]},
                              "labels": ["Klasse 6"]}
    assert ctx.req.ui_antwort is not None
    # Die Frage ist geschlossen — und das steht sofort in der Datenbank.
    assert OFFENE_FRAGE not in ctx.session_state["entities"]
    assert len(gespeichert.calls) == 1
    assert OFFENE_FRAGE not in gespeichert.calls[0]["kwargs"]["entities"]


def test_mehrfachwahl_mit_freitext_wenn_das_modul_es_anbot(monkeypatch):
    ctx, _ = _zug(monkeypatch, offen=_offen(mehrfach=True, freitext=True), ui_antwort={
        "block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a", "b"], "freitext": "beides"}})
    assert ctx.ui_antwort is not None
    assert ctx.ui_antwort["labels"] == ["Klasse 5", "Klasse 6"]
    assert ctx.ui_antwort["daten"]["freitext"] == "beides"


@pytest.mark.parametrize("ui_antwort, offen", [
    ({"block_id": "ffffffffffffffff", "daten": {"gewaehlt": ["a"]}}, None),   # fremde Kennung
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["z"]}}, None),            # gefälschte Option
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a", "b"]}}, None),       # Einzelwahl, zwei
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"], "freitext": "x"}}, None),  # kein Feld
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": []}}, None),               # weder Wahl noch Text
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": [], "freitext": "x"}}, None),  # kein Feld
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"], "mehr": 1}}, None),
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"]}}, False),           # alte Frage
    ({"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"]}},
     _offen(modul="ui_gibtsnicht")),                                          # Modul unbekannt
])
def test_eine_ungueltige_antwort_faellt_weg_und_zaehlt_wie_getippt(monkeypatch, ui_antwort, offen):
    ctx, _ = _zug(monkeypatch, ui_antwort=ui_antwort, offen=offen)
    assert ctx.ui_antwort is None
    assert ctx.req.ui_antwort is None
    assert ctx.req.message == "Klasse 6"
    assert OFFENE_FRAGE not in ctx.session_state["entities"]


# Rückmeldung 2026-11-09: „Eigene Antwort“ ist ein Punkt der Gruppe — wer sie wählt, schickt
# nur den Text (``gewaehlt`` leer). Leer bleibt nur gültig, wenn ein Text mitkommt.
def test_nur_eine_eigene_antwort_gilt_wenn_das_modul_sie_anbot(monkeypatch):
    ctx, _ = _zug(monkeypatch, offen=_offen(freitext=True), ui_antwort={
        "block_id": _BLOCK_ID, "daten": {"gewaehlt": [], "freitext": "Klasse 11"}})
    assert ctx.ui_antwort is not None
    assert ctx.ui_antwort["labels"] == [] and ctx.ui_antwort["daten"]["freitext"] == "Klasse 11"


@pytest.mark.parametrize("daten", [
    {"gewaehlt": []},                               # weder Wahl noch Text
    {"gewaehlt": [], "freitext": "   "},            # nur Leerzeichen
    {"gewaehlt": [], "freitext": ""},
])
def test_ohne_wahl_und_ohne_text_ist_keine_antwort(monkeypatch, daten):
    ctx, _ = _zug(monkeypatch, offen=_offen(freitext=True),
                  ui_antwort={"block_id": _BLOCK_ID, "daten": daten})
    assert ctx.ui_antwort is None


def test_der_block_nennt_die_eigene_antwort_ohne_wahl():
    from boerdi.ui_module.antwort import antwort_block

    block = antwort_block({"block_id": _BLOCK_ID, "modul": ENTSCHEIDUNG, "frage": "Welche Klasse?",
                           "daten": {"gewaehlt": [], "freitext": "Klasse 11"}, "labels": []})
    assert "Gewählt: keine der Möglichkeiten" in block
    assert "Eigene Antwort der Person: Klasse 11" in block


def test_der_freitext_ist_gedeckelt(monkeypatch):
    ctx, _ = _zug(monkeypatch, offen=_offen(freitext=True), ui_antwort={
        "block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"], "freitext": "x" * 1001}})
    assert ctx.ui_antwort is None


def test_jeder_getippte_zug_schliesst_die_offene_frage(monkeypatch):
    ctx, gespeichert = _zug(monkeypatch, message="lieber etwas anderes")
    assert ctx.ui_antwort is None
    assert OFFENE_FRAGE not in ctx.session_state["entities"]
    assert len(gespeichert.calls) == 1


def test_ohne_offene_frage_schreibt_niemand(monkeypatch):
    _ctx, gespeichert = _zug(monkeypatch, offen=False, message="hallo")
    assert gespeichert.calls == []


@pytest.mark.parametrize("message, umgebung", [
    ("[context-open]", {"page_event": "context_open"}),
    ("[tour-tick]", {"tour_action": "tick"}),
])
def test_ein_hintergrund_zug_laesst_die_frage_offen(monkeypatch, message, umgebung):
    ctx, gespeichert = _zug(monkeypatch, message=message, umgebung=umgebung, ui_antwort={
        "block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"]}})
    assert ctx.session_state["entities"][OFFENE_FRAGE] == _offen()
    assert ctx.ui_antwort is None and ctx.req.ui_antwort is None
    assert gespeichert.calls == []


def _abnahme() -> dict:
    from boerdi.domain.write_confirm import remember_pending
    return remember_pending("wlo_create_collection", {"name": "Bruchrechnen"},
                            "Ax9-_QmZ2kLpWvRt7NbYcE4s", now=time.time())


def test_eine_modul_antwort_zaehlt_bei_offener_schreib_abnahme_als_nein(monkeypatch):
    """Sonst würde eine gewählte Option „Ja“ zur Zustimmung (Plan §14, Befund 3)."""
    ctx, _ = _zug(monkeypatch, message="ja", pending=_abnahme(),
                  ui_antwort={"block_id": _BLOCK_ID, "daten": {"gewaehlt": ["a"]}})
    assert ctx.ui_antwort is not None
    assert "_pending_write" not in ctx.session_state["entities"]


def test_eine_verworfene_modul_antwort_zaehlt_bei_offener_schreib_abnahme_als_nein(monkeypatch):
    """Review U1-d1, Befund 2: Auch eine verworfene Modul-Antwort (zweites Fenster, alte Frage) ist
    keine Zustimmung — die Person hat im Auswahlfeld geklickt, nicht der Vorschau zugestimmt. Für
    das Modell zählt der Text danach wie getippt."""
    ctx, _ = _zug(monkeypatch, message="ja", pending=_abnahme(),
                  ui_antwort={"block_id": "ffffffffffffffff", "daten": {"gewaehlt": ["a"]}})
    assert ctx.ui_antwort is None and ctx.req.ui_antwort is None
    assert ctx.req.message == "ja"
    assert "_pending_write" not in ctx.session_state["entities"]


def test_ohne_modul_antwort_entscheidet_der_text_ueber_die_abnahme(monkeypatch):
    ctx, _ = _zug(monkeypatch, message="ja", pending=_abnahme())
    assert "_pending_write" in ctx.session_state["entities"]


def test_merke_frage_haelt_nur_was_die_pruefung_braucht():
    block, _ = modul_aufruf_annehmen(ENTSCHEIDUNG, {
        "frage": "F?", "optionen": [{"id": "a", "label": "A", "hinweis": "h"},
                                    {"id": "b", "label": "B"}], "freitext": True})
    assert block is not None
    entities: dict = {}
    merke_frage(entities, block)
    assert entities[OFFENE_FRAGE] == {
        "block_id": block.block_id, "modul": ENTSCHEIDUNG, "frage": "F?",
        "optionen": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "mehrfach": False, "freitext": True}


# ── d1-5 gespeichert an der Nutzernachricht ────────────────────────────────


def _speichern(monkeypatch, ui_antwort):
    gespeichert = _Spy()
    monkeypatch.setattr(build_mod, "save_message", gespeichert)
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message="Klasse 6"))
    ctx.ui_antwort = ui_antwort
    asyncio.run(build_mod._persist_user_message(ctx, _SESSION))
    return gespeichert.calls[0]


def test_die_gepruefte_antwort_steht_im_debug_block_der_nutzernachricht(monkeypatch):
    antwort = {"block_id": _BLOCK_ID, "modul": ENTSCHEIDUNG, "frage": "F?",
               "daten": {"gewaehlt": ["a"]}, "labels": ["A"]}
    aufruf = _speichern(monkeypatch, antwort)
    assert aufruf["args"][1:4] == ("bb-1", "user", "Klasse 6")
    assert aufruf["kwargs"]["debug"] == {DEBUG_KEY: antwort}


def test_ohne_antwort_bleibt_der_debug_block_leer(monkeypatch):
    aufruf = _speichern(monkeypatch, None)
    assert not aufruf["kwargs"].get("debug")


# ── d1-6 Verlauf: Status abgeleitet ────────────────────────────────────────


def _frage_nachricht(block) -> dict:
    return {"id": 1, "role": "assistant", "content": "Kurz nachgefragt:", "cards": [],
            "debug": {"_ui_bloecke": fuer_den_debug_block([block])}}


def _nutzer(nr: int, debug: dict | None = None) -> dict:
    return {"id": nr, "role": "user", "content": "x", "cards": [], "debug": debug or {}}


def _status(nachrichten: list[dict]) -> dict:
    [block] = [b for n in publikum.verlauf_fuer(nachrichten, intern=False)
               for b in n["ui"].get("ui_bloecke", [])]
    return block


def _block():
    block, _ = modul_aufruf_annehmen(ENTSCHEIDUNG, {
        "frage": "F?", "optionen": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]})
    assert block is not None
    return block


def test_im_verlauf_ist_eine_beantwortete_frage_beantwortet():
    block = _block()
    antwort = {"block_id": block.block_id, "modul": ENTSCHEIDUNG, "frage": "F?",
               "daten": {"gewaehlt": ["b"]}, "labels": ["B"]}
    b = _status([_frage_nachricht(block), _nutzer(2, {DEBUG_KEY: antwort})])
    assert (b["status"], b["antwort"]) == ("beantwortet", {"gewaehlt": ["b"]})


def test_im_verlauf_ist_eine_uebergangene_frage_veraltet():
    block = _block()
    b = _status([_frage_nachricht(block), _nutzer(2)])
    assert (b["status"], b["antwort"]) == ("veraltet", None)


def test_im_verlauf_bleibt_die_juengste_frage_offen():
    b = _status([_nutzer(0), _frage_nachricht(_block())])
    assert (b["status"], b["antwort"]) == ("offen", None)


def test_eine_antwort_auf_eine_andere_frage_macht_diese_veraltet():
    block = _block()
    fremd = {"block_id": "ffffffffffffffff", "modul": ENTSCHEIDUNG, "frage": "F?",
             "daten": {"gewaehlt": ["a"]}, "labels": ["A"]}
    b = _status([_frage_nachricht(block), _nutzer(2, {DEBUG_KEY: fremd})])
    assert b["status"] == "veraltet"
