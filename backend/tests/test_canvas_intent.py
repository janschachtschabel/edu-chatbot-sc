"""Characterization tests for domain/canvas/intent.py (P4-5 canvas leaf).

ALT origin: ``app/services/canvas_intent.py`` — the 7 pure regex intent
heuristics (``resolve_material_type`` / ``extract_material_type_from_message`` /
``named_artifact_label`` / ``_phrase_matches`` / ``looks_like_create_intent`` /
``looks_like_edit_intent`` / ``has_explicit_new_create_override``). ALT tested
these directly in test_canvas_service.py (via the canvas_service re-export) — the
getter-dependent cases here mirror those 1:1. Logic fidelity is proven by the
AST-diff gate.

The ``defaults_only`` fixture forces the 5 canvas_types getters onto their
in-code ``_DEFAULT_*`` vocabulary by making the config_loader read-facade raise
(same patch point + technique as ALT's fixture) — deterministic and
PG-independent. ``_phrase_matches`` is pure and needs no fixture.
"""

import pytest

from boerdi.domain.canvas import intent, types


def _boom(*_a, **_k):
    raise RuntimeError("config store down")


@pytest.fixture
def defaults_only(monkeypatch):
    """All canvas YAML loaders fail → deterministic _DEFAULT_* vocabulary.

    Patch point: the config_loader read-facade the getters call at runtime.
    """
    for name in (
        "load_canvas_material_types",
        "load_canvas_type_aliases",
        "load_canvas_create_triggers",
        "load_canvas_edit_triggers",
        "load_canvas_persona_priorities",
    ):
        monkeypatch.setattr(types.config_loader, name, _boom)


# ── _phrase_matches (pure) ────────────────────────────────────────────────
class TestPhraseMatches:
    def test_empty_needle_is_false(self):
        assert intent._phrase_matches("irgendwas", "") is False

    def test_trailing_space_needle_bypasses_right_boundary(self):
        assert intent._phrase_matches("zeig mir was", "zeig ") is True

    def test_left_boundary_blocks_inner_word(self):
        assert intent._phrase_matches("supererstelle was", "erstelle") is False
        assert intent._phrase_matches("ein quiz, bitte", "quiz") is True

    def test_right_boundary_blocks_suffix(self):
        assert intent._phrase_matches("neues quizspiel", "neues quiz") is False


# ── resolve_material_type ─────────────────────────────────────────────────
class TestResolveMaterialType:
    def test_strips_leading_emoji(self, defaults_only):
        assert intent.resolve_material_type("📝 Arbeitsblatt") == "arbeitsblatt"

    def test_slash_variant_falls_back_to_first_word(self, defaults_only):
        assert intent.resolve_material_type("Quiz/Test") == "quiz"
        assert intent.resolve_material_type("❓ Quiz/Test") == "quiz"

    def test_multiword_uses_first_word(self, defaults_only):
        assert intent.resolve_material_type("arbeitsblatt zum thema x") == "arbeitsblatt"

    def test_unknown_none_and_empty(self, defaults_only):
        assert intent.resolve_material_type("123abc") is None
        assert intent.resolve_material_type(None) is None
        assert intent.resolve_material_type("") is None

    def test_umlaut_plural_alias(self, defaults_only):
        assert intent.resolve_material_type("Arbeitsblätter") == "arbeitsblatt"


# ── extract_material_type_from_message ────────────────────────────────────
class TestExtract:
    def test_long_alias_substring(self, defaults_only):
        assert intent.extract_material_type_from_message(
            "Ich hätte gern ein Arbeitsblatt zu Brüchen") == "arbeitsblatt"

    def test_short_whitelisted_alias_needs_word_boundary(self, defaults_only):
        assert intent.extract_material_type_from_message("ein Test zu Brüchen") == "quiz"
        assert intent.extract_material_type_from_message("wir testen morgen") is None

    def test_dehyphenated_second_pass(self, defaults_only):
        assert intent.extract_material_type_from_message(
            "Info-Blatt zur Photosynthese") == "infoblatt"

    def test_pm_maps_to_pressemitteilung(self, defaults_only):
        assert intent.extract_material_type_from_message(
            "brauche eine PM für den Launch") == "pressemitteilung"

    def test_non_whitelisted_short_alias_ignored(self, defaults_only):
        assert intent.extract_material_type_from_message(
            "Ich brauche Info zur Photosynthese") is None

    def test_longest_alias_wins(self, defaults_only):
        assert intent.extract_material_type_from_message(
            "mach ein quiz als arbeitsblatt") == "arbeitsblatt"

    def test_empty_and_no_match(self, defaults_only):
        assert intent.extract_material_type_from_message("") is None
        assert intent.extract_material_type_from_message("nichts passendes da") is None


# ── looks_like_create / edit / explicit-override ──────────────────────────
class TestIntentHeuristics:
    def test_create_intent_trigger_forms(self, defaults_only):
        assert intent.looks_like_create_intent("erstelle ein quiz") is True
        assert intent.looks_like_create_intent("   erstelle ein quiz") is True
        assert intent.looks_like_create_intent(
            "Kannst du mir ein Quiz zu Brüchen bauen?") is True

    def test_create_intent_60_char_window(self, defaults_only):
        assert intent.looks_like_create_intent("a" * 61 + " ich brauche ein quiz") is False

    def test_create_intent_negatives(self, defaults_only):
        assert intent.looks_like_create_intent("") is False
        assert intent.looks_like_create_intent("suche material zu brüchen") is False

    def test_edit_intent_triggers_and_negatives(self, defaults_only):
        assert intent.looks_like_edit_intent("füge Lösungen hinzu") is True
        assert intent.looks_like_edit_intent("mach es einfacher") is True
        assert intent.looks_like_edit_intent("erstelle ein quiz") is False
        assert intent.looks_like_edit_intent("") is False

    def test_explicit_override_positives(self, defaults_only):
        assert intent.has_explicit_new_create_override("erstell mir ein neues Quiz dazu") is True
        assert intent.has_explicit_new_create_override(
            "bitte zu einem anderen Thema wechseln") is True

    def test_explicit_override_boundary_and_negatives(self, defaults_only):
        assert intent.has_explicit_new_create_override("ein neues Quizspiel") is False
        assert intent.has_explicit_new_create_override("mach es einfacher") is False
        assert intent.has_explicit_new_create_override("") is False


# ── named_artifact_label (ALT had no direct test → characterization) ──────
class TestNamedArtifactLabel:
    def test_classifier_type_unlisted_returned(self, defaults_only):
        # classifier extracted a label that isn't a known alias → pass it through
        assert intent.named_artifact_label("egal", "Argumentationshilfe") == "Argumentationshilfe"

    def test_classifier_generic_noun_ignored(self, defaults_only):
        # "Material" is a generic placeholder → not a named artifact → scan msg → ""
        assert intent.named_artifact_label("mach mir was", "Material") == ""

    def test_named_noun_in_message_returned(self, defaults_only):
        assert intent.named_artifact_label("Erstelle ein Lernplakat dazu") == "Lernplakat"

    def test_known_type_in_message_skipped(self, defaults_only):
        # "Arbeitsblatt" resolves to a known type → handled elsewhere, not here
        assert intent.named_artifact_label("Erstelle ein Arbeitsblatt") == ""

    def test_no_concrete_artifact_returns_empty(self, defaults_only):
        assert intent.named_artifact_label("mach mir bitte was") == ""
