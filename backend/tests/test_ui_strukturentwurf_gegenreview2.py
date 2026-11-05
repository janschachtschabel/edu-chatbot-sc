"""Gegenreview zum Entwurfs-Speicher (2026-11-05): fünf Reste.

1. Die Brücke vergisst einen älteren gemerkten Entwurf — sonst arbeitete der Folgezug am falschen.
3. Ein gekürzt gemerkter Entwurf (ohne Beschreibungen) wird nicht als bearbeitbar gezeigt.
4. Der Debug-Block einer Direktaktion trägt keine ``_``-Schlüssel der Sitzung (einer davon ist der
   gemerkte Entwurf samt Texten der Person) — schon durch ``DebugInfo`` gesichert; der Test hält
   es für die Brücke fest.
5. Der Zug mit der Antwort zählt nicht zu den fünf Folgezügen.
(2 — die JSON-Absicherung verändert die Nachrichten des Aufrufers nicht — steht in
``test_llm_json_hinweis.py``.)
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.ui_module import antwort, aufruf, datenquelle
from boerdi.ui_module import strukturentwurf_merken as merken
from boerdi.ui_module.namen import STRUKTURENTWURF, THEMENBAUM
from tests.test_preflight_node import _SESSION
from tests.test_ui_strukturentwurf_aktion import WURZEL, _Rufer, db  # noqa: F401 — Fixture

_ALT = {"titel": "Alter KI-Entwurf", "quelle": "ki", "knoten": [{"id": "k1", "titel": "Alt"}]}


def _bruecke(state: dict):
    from boerdi.services import strukturentwurf_aktion as aktion

    req = ChatRequest(session_id="bb-1", message="als Entwurf", action=aktion.AKTION,
                      action_params={"collection_id": WURZEL, "title": "Mathematik"},
                      environment=Environment(ui_module=[STRUKTURENTWURF, THEMENBAUM]))
    return asyncio.run(aktion.handle_edit_collection_as_draft(_SESSION, req, state,
                                                              blocked_tools=[]))


def test_1_die_bruecke_vergisst_den_aelteren_entwurf(monkeypatch, db):  # noqa: F811
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    state = {"entities": {}}
    merken.aus_bloecken(state["entities"], [])
    merken.aus_antwort(state["entities"], {"modul": STRUKTURENTWURF, "daten": dict(_ALT)})
    resp = _bruecke(state)
    entities = state["entities"]
    assert merken.vorlage(entities) is None
    # Der getippte Folgezug: die Frage ist der Brücken-Entwurf, kein alter Rahmen davor.
    geschlossen = entities[antwort.OFFENE_FRAGE]
    text = antwort.vorsatz(None, geschlossen, merken.rahmen(entities))
    assert "Seinen Stand kennst du nicht" in text and "Alter KI-Entwurf" not in text
    # Gespeichert ist auch der Debug-Stand ohne den Speicher (Befund 4).
    save, update = db
    assert merken.KEY not in update.calls[0]["entities"]
    assert resp.ui.ui_bloecke[0].daten["quelle"] == "wlo"


def test_3_gekuerzt_gemerkt_wird_nicht_als_bearbeitbar_gezeigt():
    knoten = [{"id": f"k{i}", "titel": f"T{i}", "beschreibung": "x" * 300,
               "keywords": ["y" * 40] * 8} for i in range(250)]
    entities: dict = {}
    merken.aus_antwort(entities, {"modul": STRUKTURENTWURF,
                                  "daten": {"titel": "Groß", "quelle": "ki", "knoten": knoten}})
    erg = asyncio.run(aufruf.asynchron(STRUKTURENTWURF, {
        "thema": "Groß", "vorlage": True, "erneut_zeigen": True},
        aufruf.Umgebung(vorlage=merken.vorlage(entities))))
    assert erg.block is None and "Beschreibungen" in erg.text and "herunter" in erg.text


def test_4_der_debug_block_einer_direktaktion_traegt_keine_internen_schluessel(monkeypatch, db):  # noqa: F811
    # Kein eigener Filter nötig: ``DebugInfo`` verwirft ``_``-Schlüssel selbst (Audit 2026-09-29,
    # ``schemas_debug._ohne_interne_schluessel``) — für jeden Erzeuger, auch die Direktaktionen.
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    state = {"entities": {"fach": "Mathe", "_geheim": "x"}}
    merken.aus_antwort(state["entities"], {"modul": STRUKTURENTWURF, "daten": dict(_ALT)})
    resp = _bruecke(state)
    assert resp.debug.entities == {"fach": "Mathe"}
    save, _update = db
    assert "_geheim" not in str(save.calls[-1]) and "Alter KI-Entwurf" not in str(save.calls[-1])
    assert state["entities"]["_geheim"] == "x"          # der Sitzungszustand bleibt unberührt


def test_5_der_zug_mit_der_antwort_zaehlt_nicht_zu_den_folgezuegen():
    entities: dict = {}
    geprueft = {"modul": STRUKTURENTWURF, "daten": dict(_ALT)}
    assert merken.rahmen_fuer_zug(entities, geprueft) == ""          # Antwort-Zug: kein Rahmen
    folgen = [merken.rahmen_fuer_zug(entities, None) for _ in range(merken.ZUEGE + 1)]
    assert all(folgen[:merken.ZUEGE]) and folgen[merken.ZUEGE] == ""
