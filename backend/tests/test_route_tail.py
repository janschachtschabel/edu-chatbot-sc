"""P4-4-Tail route-decision helpers — characterization tests for the two pure
helpers lifted out of ALT ``_route_pattern``'s tail (``domain/route_tail.py``).

Neither had a direct ALT unit test (``_thema_plausible`` is nested,
``reconcile_effective_pattern`` was inline) → these pin ALT behaviour. Pure
(stdlib only) → run for real, no mocks.
"""
from __future__ import annotations

from types import SimpleNamespace

from boerdi.domain.route_tail import _thema_plausible, reconcile_effective_pattern

# ── _thema_plausible ─────────────────────────────────────────────────────

class TestThemaPlausible:
    def test_plausible_topics_pass(self):
        assert _thema_plausible("Eiszeit") is True
        assert _thema_plausible("Photosynthese") is True
        assert _thema_plausible("Satz des Pythagoras") is True

    def test_empty_is_false(self):
        assert _thema_plausible("") is False

    def test_too_short_after_strip_is_false(self):
        # _tl < 3 Zeichen (nach lower+strip von " .,:;?!").
        assert _thema_plausible("ab") is False
        assert _thema_plausible("e.") is False

    def test_pronoun_or_article_start_is_false(self):
        assert _thema_plausible("das Wetter heute") is False
        assert _thema_plausible("die aktuelle Lage") is False
        assert _thema_plausible("eine Sache") is False

    def test_question_or_meta_word_start_is_false(self):
        assert _thema_plausible("wie geht das") is False
        assert _thema_plausible("was ist Photosynthese") is False
        assert _thema_plausible("bitte etwas zu Mathe") is False

    def test_trailing_question_mark_is_false(self):
        # NOTE: greift NACH dem Strip — der Roh-Text endet auf "?".
        assert _thema_plausible("Eiszeit?") is False

    def test_query_or_meta_verb_is_false(self):
        assert _thema_plausible("Video herunterladen") is False
        assert _thema_plausible("das Material bewerten") is False
        assert _thema_plausible("bitte ausdrucken") is False

    def test_material_type_strip_fragment_is_false(self):
        # "Fragment-Rest nach Material-Typ-Strip": beginnt mit e|er|es|en|em|n|s + Space.
        assert _thema_plausible("e der aktuellen Lage") is False
        assert _thema_plausible("n Sammlung dazu") is False


# ── reconcile_effective_pattern ──────────────────────────────────────────

def _winner(pid: str, label: str) -> SimpleNamespace:
    return SimpleNamespace(id=pid, label=label)


class TestReconcileEffectivePattern:
    def test_no_fast_path_passes_engine_winner_through(self):
        w = _winner("M07", "Recherche")
        assert reconcile_effective_pattern(w, False, False, []) == ("M07", "Recherche")

    def test_lp_routed_maps_to_m09(self):
        w = _winner("M03", "Slot-Klärung")
        assert reconcile_effective_pattern(w, True, False, []) == (
            "M09", "Lernpfad-Erstellung")

    def test_canvas_with_generate_tool_maps_to_m10(self):
        w = _winner("M03", "Slot-Klärung")
        out = reconcile_effective_pattern(
            w, False, True, ["canvas_service.generate_canvas_content"])
        assert out == ("M10", "KI-Inhalt-Generierung")

    def test_canvas_without_generate_tool_maps_to_m03(self):
        w = _winner("M15", "Orientierung")
        assert reconcile_effective_pattern(w, False, True, []) == (
            "M03", "Slot-Klärung")

    def test_canvas_tools_none_is_tolerated(self):
        # (tools_called or []) fängt None ab → Slot-Klärungs-Zweig.
        w = _winner("M15", "Orientierung")
        assert reconcile_effective_pattern(w, False, True, None) == (
            "M03", "Slot-Klärung")

    def test_lp_takes_priority_over_canvas(self):
        w = _winner("M03", "Slot-Klärung")
        out = reconcile_effective_pattern(
            w, True, True, ["canvas_service.generate_canvas_content"])
        assert out == ("M09", "Lernpfad-Erstellung")  # LP-Zweig zuerst
