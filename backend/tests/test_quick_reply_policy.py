"""P4-4-Tail-QR (slice): pure quick-reply policy helpers — port of ALT
``chat_quick_replies.py``'s four framework-free functions.

Characterization tests ported 1:1 from ALT ``test_chat_quick_replies.py``
(the ``_qr_policy`` / ``_qr_default_count`` / ``_spec_qr_response_block`` /
``_apply_state_auto_followup`` blocks — the guide-QR helpers ``_strip_guide_qrs``
/ ``_attach_guide_qr`` are a different module and stay deferred).

Patch-Ort-Regel (aus ALT übernommen, an die NEU-Import-Struktur angepasst):
- ``_qr_policy`` importiert ``load_pattern_definitions`` LAZY im Funktionskörper
  → am Quellmodul ``boerdi.services.config_loader`` patchen.
- ``_qr_default_count`` bindet ``load_display_rules_config`` am Modul-Top (wie
  ALT ``_display_rules``) → am Zielmodul ``boerdi.domain.quick_reply_policy``
  patchen.
"""
from __future__ import annotations

import boerdi.domain.quick_reply_policy as quick_reply_policy
import boerdi.services.config_loader as config_loader
from boerdi.domain.quick_reply_policy import (
    CONTEXT_GREETING_MARKER,
    _apply_state_auto_followup,
    _qr_default_count,
    _qr_policy,
    _spec_qr_response_block,
    has_curated_quick_replies,
)
from boerdi.i18n import SUPPORTED


def _raise(*_a, **_kw):
    raise RuntimeError("boom")


# ── _qr_policy ───────────────────────────────────────────────────────────
# Lazy-Import in der Funktion: ``from boerdi.services.config_loader import
# load_pattern_definitions`` → im Ursprungsmodul patchen.

def _patch_patterns(monkeypatch, patterns):
    monkeypatch.setattr(config_loader, "load_pattern_definitions", lambda: patterns)


def test_qr_policy_empty_pattern_id_defaults_without_loader(monkeypatch):
    # pid leer → Loader wird gar nicht konsultiert (Loader würde crashen).
    monkeypatch.setattr(config_loader, "load_pattern_definitions", _raise)
    assert _qr_policy("") == ("exact", None)
    assert _qr_policy(None) == ("exact", None)
    assert _qr_policy("   ") == ("exact", None)


def test_qr_policy_known_pattern_without_fields_is_exact_none(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "M09"}])
    assert _qr_policy("M09") == ("exact", None)


def test_qr_policy_mode_and_max_read_from_pattern(monkeypatch):
    _patch_patterns(monkeypatch, [
        {"id": "M09", "quick_replies_mode": " SPECULATIVE ", "quick_replies_max": 3},
    ])
    assert _qr_policy("M09") == ("speculative", 3)


def test_qr_policy_mode_none_is_accepted(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "M05", "quick_replies_mode": "none"}])
    assert _qr_policy("M05") == ("none", None)


def test_qr_policy_invalid_mode_falls_back_to_exact(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "M09", "quick_replies_mode": "banana"}])
    assert _qr_policy("M09") == ("exact", None)


def test_qr_policy_max_is_clamped_1_to_6(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "A", "quick_replies_max": 0}])
    # NOTE: pinnt IST-Verhalten — 0 wird auf 1 hochgeclampt (nicht "aus").
    assert _qr_policy("A") == ("exact", 1)
    _patch_patterns(monkeypatch, [{"id": "A", "quick_replies_max": 99}])
    assert _qr_policy("A") == ("exact", 6)
    _patch_patterns(monkeypatch, [{"id": "A", "quick_replies_max": "3"}])
    assert _qr_policy("A") == ("exact", 3)  # String-Zahl wird konvertiert
    _patch_patterns(monkeypatch, [{"id": "A", "quick_replies_max": "abc"}])
    assert _qr_policy("A") == ("exact", None)  # nicht konvertierbar → None


def test_qr_policy_debug_label_takes_first_token(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "M09", "quick_replies_mode": "speculative"}])
    assert _qr_policy("M09 (Lernpfad)") == ("speculative", None)


def test_qr_policy_unknown_id_defaults(monkeypatch):
    _patch_patterns(monkeypatch, [{"id": "M09"}])
    assert _qr_policy("M99") == ("exact", None)


def test_qr_policy_loader_exception_defaults(monkeypatch):
    monkeypatch.setattr(config_loader, "load_pattern_definitions", _raise)
    assert _qr_policy("M09") == ("exact", None)


# ── _qr_default_count ────────────────────────────────────────────────────
# ``_qr_default_count`` schlägt ``load_display_rules_config`` in
# quick_reply_policy nach (Read-Fassade, am Modul-Top gebunden) → dort patchen.

def _patch_rules(monkeypatch, rules):
    monkeypatch.setattr(quick_reply_policy, "load_display_rules_config", lambda: rules)


def test_qr_default_count_reads_max_count(monkeypatch):
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": 5}})
    assert _qr_default_count() == 5


def test_qr_default_count_zero_means_zero(monkeypatch):
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": 0}})
    assert _qr_default_count() == 0


def test_qr_default_count_missing_section_defaults_to_4(monkeypatch):
    _patch_rules(monkeypatch, {})
    assert _qr_default_count() == 4
    _patch_rules(monkeypatch, None)
    assert _qr_default_count() == 4


def test_qr_default_count_clamped_to_6(monkeypatch):
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": 99}})
    assert _qr_default_count() == 6


def test_qr_default_count_negative_clamped_to_0(monkeypatch):
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": -2}})
    assert _qr_default_count() == 0


def test_qr_default_count_explicit_none_defaults_to_4(monkeypatch):
    # NOTE: Fix 2026-07-10 (C4) — ``max_count: None`` (explizit null in der
    # YAML) wird wie ein fehlender Key auf den Default 4 aufgelöst, NICHT
    # auf 0. Nur explizites ``max_count: 0`` schaltet QRs global aus.
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": None}})
    assert _qr_default_count() == 4


def test_qr_default_count_unparseable_value_defaults_to_4(monkeypatch):
    _patch_rules(monkeypatch, {"quick_replies": {"max_count": "abc"}})
    assert _qr_default_count() == 4  # int() wirft → except → 4


def test_qr_default_count_rules_loader_exception_defaults_to_4(monkeypatch):
    monkeypatch.setattr(quick_reply_policy, "load_display_rules_config", _raise)
    assert _qr_default_count() == 4


# ── _spec_qr_response_block ──────────────────────────────────────────────

def test_spec_block_with_purpose_and_titles():
    out = _spec_qr_response_block("M09", "Lernpfad bauen", ["T1", "T2"])
    lines = out.split("\n")
    assert lines[0].startswith("(Die Bot-Antwort wird gerade parallel generiert")
    assert lines[1] == "Gewähltes Antwort-Pattern: M09 — Lernpfad bauen"
    assert lines[2] == "Treffer, die unter der Antwort angezeigt werden:"
    assert lines[3:] == ["- T1", "- T2"]


def test_spec_block_without_purpose_omits_dash():
    out = _spec_qr_response_block("M03", "", [])
    assert "Gewähltes Antwort-Pattern: M03" in out
    assert "—" not in out.split("\n")[1]


def test_spec_block_no_titles_fallback_line():
    out = _spec_qr_response_block("M03", "x", [])
    assert out.endswith("Es sind vorab keine Treffer-Karten bekannt.")
    assert "Treffer, die unter der Antwort" not in out


def test_spec_block_caps_titles_at_5_and_filters_blank():
    titles = ["", "  ", "A", "B", "C", "D", "E", "F", None]
    out = _spec_qr_response_block("M09", "p", titles)
    # Nach Blank-Filter bleiben A..F; Cap [:5] → A..E
    assert [ln for ln in out.split("\n") if ln.startswith("- ")] == [
        "- A", "- B", "- C", "- D", "- E",
    ]


def test_spec_block_titles_none_is_tolerated():
    out = _spec_qr_response_block("M09", "p", None)
    assert "Es sind vorab keine Treffer-Karten bekannt." in out


# ── _apply_state_auto_followup ───────────────────────────────────────────

def test_auto_followup_only_for_s3():
    qrs = ["A", "B"]
    assert _apply_state_auto_followup(
        state_id="S1", quick_replies=qrs, has_cards=True) == ["A", "B"]
    assert _apply_state_auto_followup(
        state_id="S2", quick_replies=qrs, has_cards=True) == ["A", "B"]


def test_auto_followup_s3_without_cards_is_noop():
    assert _apply_state_auto_followup(
        state_id="S3", quick_replies=["A"], has_cards=False) == ["A"]


def test_auto_followup_s3_appends_when_below_4():
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["A", "B"], has_cards=True)
    assert out == ["A", "B", "Hat das geholfen?"]


def test_auto_followup_s3_replaces_last_when_4_or_more():
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["A", "B", "C", "D"], has_cards=True)
    assert out == ["A", "B", "C", "Hat das geholfen?"]


def test_auto_followup_does_not_mutate_input():
    qrs = ["A", "B", "C", "D"]
    _apply_state_auto_followup(state_id="S3", quick_replies=qrs, has_cards=True)
    assert qrs == ["A", "B", "C", "D"]


def test_auto_followup_skips_if_pass_quality_qr_present():
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["Passt das so?"], has_cards=True)
    assert out == ["Passt das so?"]
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["Hat dir das weiterhilft-Zeug gefallen?"],
        has_cards=True)
    assert len(out) == 1  # "weiterhilft" ist Keyword-Substring → kein Append


def test_auto_followup_keyword_is_substring_match():
    # NOTE: pinnt IST-Verhalten — reiner Substring-Match: "richtig" in
    # "Richtig starke Auswahl!" verhindert den Auto-Followup, obwohl das
    # keine Pass-Quality-Frage ist.
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["Richtig starke Auswahl!"], has_cards=True)
    assert out == ["Richtig starke Auswahl!"]


def test_auto_followup_empty_and_none_qrs_get_single_auto_qr():
    assert _apply_state_auto_followup(
        state_id="S3", quick_replies=[], has_cards=True) == ["Hat das geholfen?"]
    assert _apply_state_auto_followup(
        state_id="S3", quick_replies=None, has_cards=True) == ["Hat das geholfen?"]


# ── C1-f2b6a: derselbe Auto-Chip auf Englisch ────────────────────────────

def test_auto_followup_english_chip():
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["A", "B"], has_cards=True, lang="en")
    assert out == ["A", "B", "Did that help?"]


def test_auto_followup_english_is_idempotent():
    """Der Doublette-Schutz und der Chip sind DASSELBE Wort.

    ``"Hat das geholfen?"`` enthaelt ``"geholfen"`` — einen Eintrag der
    Stichwortliste. Uebersetzt man nur den Chip, erkennt der Waechter die
    englische Pass-Quality-Frage des LLM nicht mehr und haengt eine zweite an.
    """
    out = _apply_state_auto_followup(
        state_id="S3", quick_replies=["Did that help?"], has_cards=True, lang="en")
    assert out == ["Did that help?"]


def test_auto_followup_english_erkennt_llm_varianten():
    for qr in ("Was that the right fit?", "Did this help you?", "Does that fit?"):
        out = _apply_state_auto_followup(
            state_id="S3", quick_replies=[qr], has_cards=True, lang="en")
        assert out == [qr], qr


def test_pass_quality_tabelle_kennt_jede_sprache():
    assert set(quick_reply_policy._PASS_QUALITY_KEYWORDS) == set(SUPPORTED)


# ── Kuratierte Quick-Replies (Review-Befund 2026-08-14) ────────────────────
#
# ``display-rules.quick_replies.max_count`` ist die Zielzahl des Generators.
# Redaktionell gepflegte Pillen (Kontext-Begrüßung) sind keine Generator-Ausgabe
# und fallen deshalb nicht darunter — von fünf gepflegten Knöpfen kamen sonst
# zwei an. Diese Tests halten die Grenze der Ausnahme fest.


def test_die_marke_des_begruessungs_knotens_erfuellt_das_praedikat():
    """Der Knoten SETZT die Marke, der Anzeige-Trim LIEST sie.

    Deshalb eine geteilte Konstante statt zweier Literale — und deshalb dieser
    Test: hardcodiert jemand im Knoten wieder ein ``"CTX:"``, fällt es hier auf
    und nicht erst daran, dass Knöpfe live verschwinden.
    """
    from boerdi.graph.nodes import context_greeting as cg

    assert cg.CONTEXT_GREETING_MARKER is CONTEXT_GREETING_MARKER
    assert has_curated_quick_replies(f"{CONTEXT_GREETING_MARKER}collection")
    assert has_curated_quick_replies(f"{CONTEXT_GREETING_MARKER}skipped")


def test_fuehrender_abstand_hebt_die_marke_nicht_auf():
    # Das Debug-Label kommt aus verschiedenen Quellen; ein Leerzeichen davor
    # darf die Pillen nicht kosten.
    assert has_curated_quick_replies("  CTX:collection")


def test_alles_andere_bleibt_unter_dem_generator_deckel():
    """Die Gegenprobe. Ohne sie liesse sich der Deckel versehentlich global
    abschalten, und niemand merkte es."""
    for pattern in (None, "", "   ", "M09 (Lernpfad)", "TOUR:intro",
                    "ACTION: browse_collection", "SAFETY: blocked_direct_action",
                    "context:collection"):
        assert not has_curated_quick_replies(pattern), pattern
