"""Paket 18C/D (3.1): ``ui`` — der öffentliche Teil einer Antwort, abgeleitet aus dem Debug-Block.

Das Widget liest live ``pattern``, ``intent``, ``state``, ``tools_called`` und die Modulationen,
nach dem Neuladen dazu die Wiederherstellungsfelder des gespeicherten Zugs. Persona, Signale,
Entitäten, Spur, Zugakte und alles Übrige ist Diagnose und gehört nur ins Studio (Phase 4 nimmt
``debug`` öffentlich weg). Ein Modell je Publikum statt Herausfiltern: ein neues Diagnosefeld
ist damit von selbst nicht öffentlich — der Vertragstest hält die Schlüssel fest.
"""

from __future__ import annotations

from boerdi.api import publikum
from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo

VERTRAG = {
    "pattern", "intent", "state", "tools_called", "modulations",
    "query_metas", "web_links", "type_focus", "dokumente", "topic_page_view", "prepared_write",
}


def test_der_vertrag_haelt_die_schluessel_fest():
    assert set(UiInfo.model_fields) == VERTRAG


def test_live_aus_dem_debug_block_ohne_diagnose():
    debug = DebugInfo(pattern="M04", intent="I03", state="S3", tools_called=["search_wlo_all"],
                      phase3_modulations={"tone": "du"}, persona="P-LEH", signals=["eilig"],
                      entities={"thema": "Optik"})
    ui = publikum.ui_aus_debug(debug)
    assert ui.model_dump(exclude_defaults=True) == {
        "pattern": "M04", "intent": "I03", "state": "S3", "tools_called": ["search_wlo_all"],
        "modulations": {"tone": "du"},
    }
    assert "Optik" not in ui.model_dump_json() and "P-LEH" not in ui.model_dump_json()


def test_aus_einer_gespeicherten_nachricht_samt_wiederherstellung():
    gespeichert = {
        "pattern": "M06", "intent": "I03", "tools_called": ["search_wlo_content"],
        "persona": "P-LEH", "entities": {"thema": "Optik"}, "trace": [{"x": 1}],
        "_query_metas": [{"search_term": "Optik"}], "_web_links": [{"url": "u", "title": "t"}],
        "_type_focus": "Video", "_dokumente": [{"kind": "quiz"}],
        "_topic_page_view": {"swimlanes": []}, "_prepared_write": {"method": "POST"},
        "_zugakte": {"werkzeuge": [{"name": "w"}]},
    }
    ui = publikum.ui_aus_gespeichert(gespeichert)
    assert ui.model_dump(exclude_defaults=True) == {
        "pattern": "M06", "intent": "I03", "tools_called": ["search_wlo_content"],
        "query_metas": [{"search_term": "Optik"}], "web_links": [{"url": "u", "title": "t"}],
        "type_focus": "Video", "dokumente": [{"kind": "quiz"}],
        "topic_page_view": {"swimlanes": []}, "prepared_write": {"method": "POST"},
    }


def test_alte_und_kaputte_nachrichten_geben_leere_felder_statt_fehler():
    assert publikum.ui_aus_gespeichert({}) == UiInfo()
    assert publikum.ui_aus_gespeichert(None) == UiInfo()
    kaputt = {"pattern": 7, "tools_called": "x", "_query_metas": "kein Array",
              "_topic_page_view": [1], "_type_focus": {"a": 1}}
    assert publikum.ui_aus_gespeichert(kaputt) == UiInfo()


def test_die_antwort_bekommt_ui_debug_bleibt():
    resp = ChatResponse(session_id="bb-1", content="x", debug=DebugInfo(pattern="M04"))
    aus = publikum.antwort_mit_ui(resp)
    assert aus.ui == UiInfo(pattern="M04") and aus.debug.pattern == "M04"


def test_der_verlauf_bekommt_ui_je_nachricht():
    verlauf = [{"id": 1, "role": "user", "content": "hi", "debug": {}},
               {"id": 2, "role": "assistant", "content": "a", "debug": {"pattern": "M04"}}]
    aus = publikum.verlauf_mit_ui(verlauf)
    assert [m["ui"] for m in aus] == [{}, {"pattern": "M04"}]
    assert aus[1]["debug"] == {"pattern": "M04"}


def test_von_den_modulationen_nur_was_das_widget_liest():
    """Review Phase 3: ``phase3_modulations`` trägt auch die vom Modell geschriebene Begründung
    der Kartenauswahl, die Kernregel des Musters und den Zustandsübergang samt Grund — Diagnose.
    Öffentlich nur, was das Gastgeber-Ereignis liest (``host-events.ts``)."""
    gespeichert = {"phase3_modulations": {
        "tone": "freundlich", "length": "kurz", "formality": "du", "card_text_mode": "minimal",
        "rag_areas": ["wlo"], "sources": ["wlo"], "_tone_modifier_override": True,
        "selected_card_reasoning": "weil Optik", "core_rule": "Regel",
        "state_transition": {"reason": "validator error: x"}, "missing_slots": ["thema"],
    }}
    assert publikum.ui_aus_gespeichert(gespeichert).modulations == {
        "tone": "freundlich", "length": "kurz", "formality": "du", "card_text_mode": "minimal",
        "rag_areas": ["wlo"], "sources": ["wlo"], "_tone_modifier_override": True,
    }
