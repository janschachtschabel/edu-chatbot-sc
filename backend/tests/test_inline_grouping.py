"""P5-3-Rest (slice): pure inline-grouping helpers — port of ALT llm_tool_loop.py
P13 pure layer (+ ``_strip_trailing_option_lines``).

- ``_strip_trailing_option_lines``: 7 direct ALT tests (test_llm_service_helpers.py).
- predicates + ``_ui_box_state_footer``: the one direct ALT unit test
  (test_generate_response_net.py::test_ui_box_footer_counts_topic_page_node_type_as_themenseite)
  + characterization tests for the remaining branches.
Die Redaktion (was das MODELL sieht) zog 2026-08-16 mit ihrem Modul nach
``test_tool_result_redaction`` um.

All helpers are pure (no LLM/MCP/RAG/config) → run for real, no mocks.
"""
from __future__ import annotations

from boerdi.domain.inline_grouping import (
    MAX_SELECTABLE_CARDS,
    MIN_SELECTABLE_CARDS,
    _is_einzelinhalt_card,
    _is_pure_sammlung_card,
    _is_themenseite_card,
    _strip_trailing_option_lines,
    _ui_box_state_footer,
    max_selectable_cards,
)

# ════════════════════════════════════════════════════════════════════════
# _strip_trailing_option_lines — port ALT test_llm_service_helpers.py (pure)
# ════════════════════════════════════════════════════════════════════════

def test_strip_empty_and_no_match_unchanged():
    assert _strip_trailing_option_lines("", ["Mehr davon"]) == ""
    text = "Hier ist die Antwort.\nNoch ein Satz."
    assert _strip_trailing_option_lines(text, ["Mehr davon"]) == text


def test_strip_removes_trailing_qr_with_markdown_deco():
    text = "Hier ist die Antwort.   \n**Mehr davon:**"
    out = _strip_trailing_option_lines(text, ["Mehr davon"])
    assert out == "Hier ist die Antwort."


def test_strip_removes_multiple_trailing_qr_and_blank_lines():
    text = "Antwort.\n\n- Mehr davon\n\nAnderes Thema"
    out = _strip_trailing_option_lines(text, ["Mehr davon", "Anderes Thema"])
    assert out == "Antwort."


def test_strip_bring_mich_hin_removed_without_qr_list():
    text = "Text.\nBring mich hin zur Fachportal-Uebersicht"
    assert _strip_trailing_option_lines(text, []) == "Text."


def test_strip_inner_lines_untouched():
    text = "Mehr davon\nEigentlicher Inhalt."
    assert _strip_trailing_option_lines(text, ["Mehr davon"]) == text


def test_strip_all_matched_returns_empty_string():
    text = "Mehr davon\nAnderes Thema"
    assert _strip_trailing_option_lines(text, ["Mehr davon", "Anderes Thema"]) == ""


def test_strip_blank_quick_replies_ignored():
    text = "Antwort.\nMehr davon"
    assert _strip_trailing_option_lines(text, ["", "   "]) == text


# ════════════════════════════════════════════════════════════════════════
# card predicates + _ui_box_state_footer
# ════════════════════════════════════════════════════════════════════════

def test_ui_box_footer_counts_topic_page_node_type_as_themenseite():
    # Direct ALT test (T-4, 2026-07-10): node_type=="topic_page" → Themenseite,
    # nicht Einzelinhalt und nicht "durch alle Boxen fallen".
    tp_card = {
        "node_id": "tp1",
        "node_type": "topic_page",
        "topic_pages": [{"url": "https://x", "target_group": "teacher",
                         "label": "L"}],
    }
    assert _is_themenseite_card(tp_card) is True
    assert _is_pure_sammlung_card(tp_card) is False
    assert _is_einzelinhalt_card(tp_card) is False  # keine Doppelzählung
    footer = _ui_box_state_footer([tp_card], True)
    assert "1 Themenseite(n) sichtbar" in footer
    assert "0 Einzelinhalt(e) NICHT sichtbar" in footer


def test_collection_without_topic_pages_is_pure_sammlung():
    c = {"node_type": "collection"}
    assert _is_pure_sammlung_card(c) is True
    assert _is_themenseite_card(c) is False
    assert _is_einzelinhalt_card(c) is False


def test_collection_with_topic_pages_is_themenseite_not_sammlung():
    c = {"node_type": "collection", "topic_pages": [{"url": "u"}]}
    assert _is_themenseite_card(c) is True
    assert _is_pure_sammlung_card(c) is False
    assert _is_einzelinhalt_card(c) is False


def test_themenseite_auch_ohne_varianten_wenn_topic_page_url_gesetzt():
    # So kommt eine Themenseite aus ``search_wlo_all``: der Envelope-Leser setzt
    # ``topic_page_url``, ein Varianten-Array gibt es auf diesem Weg nicht. Bis
    # 2026-08-16 zaehlten die drei Praedikate sie deshalb als reine Sammlung —
    # gemessen am Optik-Zug meldete der Fusstext „0 Themenseite(n) sichtbar",
    # waehrend das Frontend zwei rendert (``_infer_node_type`` liest dasselbe
    # Feld). Der Fusstext nennt sich Frontend-Spiegel; das hier ist die Zusage.
    c = {"node_type": "collection",
         "topic_page_url": "https://repo/edu-sharing/components/topic-pages?collectionId=9e7"}
    assert _is_themenseite_card(c) is True
    assert _is_pure_sammlung_card(c) is False
    assert _is_einzelinhalt_card(c) is False


def test_leerer_topic_page_url_bleibt_eine_reine_sammlung():
    # Gegenprobe zur Zeile darueber: das Feld existiert auf JEDER Karte des
    # Envelope-Lesers, nur eben leer. Wer auf Anwesenheit statt Inhalt prueft,
    # macht jede Sammlung zur Themenseite.
    c = {"node_type": "collection", "topic_page_url": "  "}
    assert _is_pure_sammlung_card(c) is True
    assert _is_themenseite_card(c) is False


def test_content_card_is_einzelinhalt():
    c = {"node_type": "content"}
    assert _is_einzelinhalt_card(c) is True
    assert _is_themenseite_card(c) is False
    assert _is_pure_sammlung_card(c) is False


def test_ui_box_footer_empty_when_not_inline_mode():
    c = {"node_type": "content"}
    assert _ui_box_state_footer([c], False) == ""


def test_ui_box_footer_counts_mixed_boxes():
    # Reale Themenseiten-Card trägt ein topic_pages-Array (wie der ALT-Direkttest
    # + parse_wlo_topic_page_cards) → _is_einzelinhalt_card-Guard verhindert die
    # Doppelzählung. Ohne topic_pages zählte ALT eine bare topic_page-Card sowohl
    # als Themenseite als auch als Einzelinhalt (latenter Quirk, real nie erreicht).
    cards = [
        {"node_type": "topic_page", "topic_pages": [{"url": "u"}]},
        {"node_type": "collection"},
        {"node_type": "content"},
    ]
    footer = _ui_box_state_footer(cards, True)
    assert "1 Themenseite(n) sichtbar" in footer
    assert "1 Sammlung(en) sichtbar" in footer
    assert "1 Einzelinhalt(e) NICHT sichtbar" in footer
    assert "WAHRHEITSPFLICHT" in footer


def test_der_fusstext_zaehlt_den_optik_zug_wie_das_frontend():
    # Der gemessene Zug (2026-08-16, ``search_wlo_all`` zu „Optik"): zwei
    # Sammlungen mit Themenseite, zwei ohne, acht Einzelinhalte. Der Fusstext
    # meldete „0 Themenseite(n), 4 Sammlung(en)" — das Frontend rendert 2/2.
    cards = (
        [{"node_type": "collection", "topic_page_url": f"https://repo/tp/{i}"}
         for i in range(2)]
        + [{"node_type": "collection"} for _ in range(2)]
        + [{"node_type": "content"} for _ in range(8)]
    )
    footer = _ui_box_state_footer(cards, True)
    assert "2 Themenseite(n) sichtbar" in footer
    assert "2 Sammlung(en) sichtbar" in footer
    assert "8 Einzelinhalt(e) NICHT sichtbar" in footer


# ════════════════════════════════════════════════════════════════════════
# max_selectable_cards — Befund 2026-08-14 (Nutzer: „die Optik-Sammlung
# wird nicht gefunden")
#
# ``select_top_cards`` kappte die LLM-Auswahl hart auf 5 Karten, quer ueber
# ALLE Boxen. Der Postprocess filtert die Karten danach auf genau diese IDs —
# die Box-Deckel in ``turn_persist`` konnten also nur noch kuerzen, nie
# ergaenzen. Belegten Einzelinhalte die fuenf Plaetze, fiel die gesuchte
# Sammlung heraus. Gemessen an „Optik": ``search_wlo_collections`` liefert sie
# als Treffer 1, im Chat erschien sie nie.
# ════════════════════════════════════════════════════════════════════════

def test_deckel_folgt_den_studio_gruppen():
    # Die Materialien-Box hat ZWEI Deckel: ``materialien_max`` (3) und im
    # Lernpfad-Zug ``materialien_max_lernpfad`` (5) — ``turn_persist`` waehlt je
    # nach Muster den einen ODER den anderen. Das Budget muss den groesseren
    # tragen, sonst hungert es im M09-Zug dieselbe Sammlung aus, die #193
    # sichtbar machen sollte (Review-Befund 2026-08-14).
    rules = {"groups": {"themenseiten_max": 3, "sammlungen_max": 3,
                        "materialien_max": 3, "materialien_max_lernpfad": 5}}
    assert max_selectable_cards(rules) == 11


def test_ohne_konfiguration_gelten_die_vorgaben():
    # Leere Config = die Defaults aus ``GroupsRules`` (3/3/3, Lernpfad 5).
    assert max_selectable_cards({}) == 11
    assert max_selectable_cards({"groups": {}}) == 11


def test_der_lernpfad_deckel_ersetzt_und_addiert_nicht():
    # Ist der Standard-Deckel groesser, bleibt er massgeblich — die beiden
    # Werte sind Alternativen fuer DIESELBE Box, keine zwei Boxen.
    rules = {"groups": {"themenseiten_max": 3, "sammlungen_max": 3,
                        "materialien_max": 8, "materialien_max_lernpfad": 5}}
    assert max_selectable_cards(rules) == 14


def test_der_deckel_liegt_nie_unter_dem_bisherigen():
    # Selbst eine sehr enge Redaktions-Einstellung darf nicht schlechter
    # werden als der alte harte Wert — sonst waere die Aenderung ein
    # Rueckschritt fuer alle, die die Gruppen klein halten.
    rules = {"groups": {"themenseiten_max": 1, "sammlungen_max": 1,
                        "materialien_max": 1, "materialien_max_lernpfad": 1}}
    assert max_selectable_cards(rules) == MIN_SELECTABLE_CARDS


def test_der_lernpfad_deckel_gehoert_zur_engen_einstellung_dazu():
    # Wer nur ``materialien_max`` klein stellt, hat NICHT eng eingestellt: der
    # Lernpfad-Deckel ist ein eigener Studio-Schluessel und steht dann weiter
    # auf 5 — genau wie im Loader. Das Budget muss das spiegeln, sonst
    # verspricht es weniger, als die Boxen zeigen duerfen.
    rules = {"groups": {"themenseiten_max": 1, "sammlungen_max": 1,
                        "materialien_max": 1}}
    assert max_selectable_cards(rules) == 7


def test_der_deckel_bleibt_gedeckelt():
    # Die Gruppen duerfen bis 20/20/8 gehen; 48 Karten in einer Antwort sind
    # keine Auswahl mehr.
    rules = {"groups": {"themenseiten_max": 20, "sammlungen_max": 20,
                        "materialien_max": 8}}
    assert max_selectable_cards(rules) == MAX_SELECTABLE_CARDS


def test_unsinnige_werte_werfen_nicht():
    rules = {"groups": {"themenseiten_max": "drei", "sammlungen_max": None,
                        "materialien_max": -5}}
    assert MIN_SELECTABLE_CARDS <= max_selectable_cards(rules) <= MAX_SELECTABLE_CARDS


def test_bei_vorgabe_ist_platz_fuer_eine_sammlung_neben_drei_materialien():
    # Der eigentliche Befund in einer Zusicherung: mit den Vorgabe-Gruppen
    # passen drei Einzelinhalte UND Sammlungen in dieselbe Auswahl. Beim
    # alten Deckel 5 konkurrierten sie um dieselben Plaetze.
    assert max_selectable_cards({}) >= 3 + 3
