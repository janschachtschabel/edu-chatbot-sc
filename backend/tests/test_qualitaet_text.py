"""Paket 16, D1: der Text im Qualitätsprotokoll verfällt mit den Gesprächsverläufen (rein).

Das Qualitätsprotokoll behält seine Kennzahlen länger als die Gespräche (eigene Frist), trug aber
die Nachricht und Wörter daraus mit: ``message``, dreimal die Entities (Thema, Suchbegriff der
Seite, Dokumenttitel), die Begründungen des Modells, Fehlertexte von Werkzeugen und den Freitext
der Rechtsprüfung. ``text_entfernen`` nimmt genau das heraus und lässt alles Zählbare stehen.
"""

from __future__ import annotations

from boerdi.services.qualitaet_text import MARKE, text_entfernen

ZEILE = {
    "turn_count": 3, "persona_id": "P-LK", "intent_confidence": 0.8, "signals": ["s1"],
    "entities": {"thema": "Bruchrechnung", "search_query": "brüche klasse 6"},
    "tools_called": ["search_wlo_all"], "response_length": 420, "cards_count": 4,
    # Die flache Kopie der Werkzeug-Ergebnisse (`log_quality_event`, Review B-1).
    "tool_outcomes": [{"tool": "search", "status": "error", "error": "brüche: 0 Treffer"}],
    "message": "Ich suche Arbeitsblätter zu Brüchen für meine 6b",
    "debug": {
        "persona": "P-LK", "intent": "I01", "phase2_scores": {"M04": 0.7},
        "entities": {"thema": "Bruchrechnung"},
        "context": {"page": "/home", "locale": "de", "entities": {"document_title": "Brüche"}},
        "pattern_reasoning": "Die Lehrkraft sucht Material zu Brüchen.",
        "phase3_modulations": {"tone": "sachlich", "selected_card_reasoning": "Passt zu Brüchen",
                               "core_rule": "Zeige Karten."},
        "outcomes": [{"tool": "search", "status": "error", "error": "kein Treffer für brüche"},
                     {"tool": "search", "status": "ok", "item_count": 4}],
        "safety": {"risk_level": "low",
                   "reasons": ["regex:none", "legal:urheber low (zitiert Buch)"]},
        "token_usage": {"total": 1200},
    },
}


def test_nimmt_jeden_text_aus_nachricht_und_debug():
    neu = text_entfernen(ZEILE)
    assert neu["message"] is None
    assert neu["entities"] == {} and neu["debug"]["entities"] == {}
    assert neu["debug"]["context"]["entities"] == {}
    assert "pattern_reasoning" not in neu["debug"]
    assert "selected_card_reasoning" not in neu["debug"]["phase3_modulations"]
    assert all("error" not in o for o in neu["debug"]["outcomes"])
    assert neu["tool_outcomes"] == [{"tool": "search", "status": "error"}]
    assert neu["debug"]["safety"]["reasons"] == ["regex:none", "legal:urheber low"]
    assert "brüche" not in str(neu).lower()
    assert neu[MARKE] is True


def test_laesst_kennzahlen_und_kennungen_stehen():
    neu = text_entfernen(ZEILE)
    for schluessel in ("turn_count", "persona_id", "intent_confidence", "signals", "tools_called",
                       "response_length", "cards_count"):
        assert neu[schluessel] == ZEILE[schluessel]
    assert neu["debug"]["phase2_scores"] == {"M04": 0.7}
    assert neu["debug"]["context"]["page"] == "/home"
    assert neu["debug"]["outcomes"][1] == {"tool": "search", "status": "ok", "item_count": 4}
    assert neu["debug"]["phase3_modulations"]["core_rule"] == "Zeige Karten."   # Konfiguration
    assert neu["debug"]["token_usage"] == {"total": 1200}


def test_aendert_die_eingabe_nicht_und_vertraegt_duenne_zeilen():
    vorher = repr(ZEILE)
    text_entfernen(ZEILE)
    assert repr(ZEILE) == vorher
    assert text_entfernen({}) == {"message": None, MARKE: True}
    assert text_entfernen({"debug": "kaputt"})["debug"] == "kaputt"
