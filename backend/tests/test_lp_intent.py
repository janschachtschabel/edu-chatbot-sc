"""Characterization tests for domain/lp_intent.py::detect_lp_intent (P4-4-Tail).

ALT origin: ``chat_turn_routing._route_pattern`` LP-intent-detection prolog
(Z. 196-281). Integration-only in ALT → these pin the observable contract: the
``(_has_lp_intent, _thema)`` decision plus the two in-place side effects
(``session_state`` thema-clear on classifier garbage, ``pattern_output`` forced
degradation when an LP intent lacks a concrete topic).
"""

from types import SimpleNamespace

from boerdi.domain.lp_intent import detect_lp_intent, strip_lp_command_words


def _cls(intent_id: str):
    """Minimal classification stub — the gate only reads ``.intent_id``."""
    return SimpleNamespace(intent_id=intent_id)


class TestHasLpIntent:
    def test_keyword_triggers_intent(self):
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Bruchrechnung"}}
        po: dict = {}
        has, thema = detect_lp_intent(
            classification=_cls("I01"),
            message="Erstelle mir einen Lernpfad",
            session_state=ss,
            pattern_output=po,
        )
        assert has is True
        assert thema == "Bruchrechnung"
        assert po == {}  # plausible thema + intent+thema present → no degradation

    def test_i04_triggers_without_keyword(self):
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Photosynthese"}}
        has, thema = detect_lp_intent(
            classification=_cls("I04"),
            message="mach weiter",
            session_state=ss,
            pattern_output={},
        )
        assert has is True
        assert thema == "Photosynthese"

    def test_blocking_intents_suppress(self):
        for iid in ("I02", "I06", "I07", "I08"):
            ss = {"persona_id": "P-LEHR", "entities": {"thema": "Bruchrechnung"}}
            has, _ = detect_lp_intent(
                classification=_cls(iid),
                message="Lernpfad bitte",
                session_state=ss,
                pattern_output={},
            )
            assert has is False, iid

    def test_auftrags_intents_sperren_den_schnellweg(self):
        """K1 (2026-08-11): I09/I10/I11 kamen mit M18/M19/M20 dazu, die
        Sperrliste blieb bei den vier alten stehen.

        Der Schnellweg feuert schon, wenn EIN Stichwort irgendwo im Satz steht —
        und „Unterrichtseinheit" steht in ``_lp_keywords``. Gemessen: alle drei
        Sätze unten lösten ihn aus. Er läuft VOR der Musterwahl, das Muster kommt
        also gar nicht mehr zum Zug: statt einer Prüfung bekäme die Person einen
        erzeugten Lernpfad.

        Die drei sind Aufträge AM BESTAND (anlegen, prüfen, erschliessen); ein
        Stichwort im Nebensatz nennt ihren Zweck, nicht ihre Aufgabe.
        """
        for iid, nachricht in (
            ("I09", "Leg eine Sammlung für meine Unterrichtseinheit Optik an"),
            ("I10", "Prüf, ob die Sammlung für meine Unterrichtseinheit Optik reicht"),
            ("I11", "Nimm diese Seite für meine Unterrichtseinheit Optik auf"),
        ):
            ss = {"persona_id": "P-LEHR", "entities": {"thema": "Optik"}}
            has, _ = detect_lp_intent(
                classification=_cls(iid),
                message=nachricht,
                session_state=ss,
                pattern_output={},
            )
            assert has is False, f"{iid}: {nachricht}"

    def test_persona_p_red_blocks(self):
        ss = {"persona_id": "P-RED", "entities": {"thema": "Klimawandel"}}
        has, _ = detect_lp_intent(
            classification=_cls("I01"),
            message="Lernpfad zum Klimawandel",
            session_state=ss,
            pattern_output={},
        )
        assert has is False

    def test_persona_p_ent_blocks(self):
        ss = {"persona_id": "P-ENT", "entities": {"thema": "Klimawandel"}}
        has, _ = detect_lp_intent(
            classification=_cls("I01"),
            message="Lernpfad zum Klimawandel",
            session_state=ss,
            pattern_output={},
        )
        assert has is False

    def test_no_keyword_and_not_i04(self):
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Bruchrechnung"}}
        has, thema = detect_lp_intent(
            classification=_cls("I01"),
            message="Was ist Photosynthese?",
            session_state=ss,
            pattern_output={},
        )
        assert has is False
        assert thema == "Bruchrechnung"


class TestThemaGarbageGate:
    def test_garbage_thema_cleared_and_degraded(self):
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "wie"}}
        po: dict = {}
        has, thema = detect_lp_intent(
            classification=_cls("I01"),
            message="Erstelle einen Lernpfad",
            session_state=ss,
            pattern_output=po,
        )
        assert has is True
        assert thema == ""  # question word → implausible → cleared
        assert ss["entities"]["thema"] == ""  # in-place clear
        assert po["degradation"] is True
        assert "thema" in po["missing_slots"]

    def test_plausible_thema_kept_no_degradation(self):
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Photosynthese"}}
        po: dict = {}
        has, thema = detect_lp_intent(
            classification=_cls("I01"),
            message="Lernpfad zur Photosynthese",
            session_state=ss,
            pattern_output=po,
        )
        assert thema == "Photosynthese"
        assert ss["entities"]["thema"] == "Photosynthese"
        assert "degradation" not in po

    def test_garbage_thema_cleared_even_without_lp_intent(self):
        # ALT Z.268 garbage-check is unconditional on thema; the degradation
        # (Z.273) additionally requires _has_lp_intent → cleared but not degraded.
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "der"}}
        po: dict = {}
        has, thema = detect_lp_intent(
            classification=_cls("I06"),  # blocking → has_lp_intent False
            message="Bearbeite den Lernpfad",
            session_state=ss,
            pattern_output=po,
        )
        assert has is False
        assert thema == ""
        assert ss["entities"]["thema"] == ""
        assert "degradation" not in po


class TestForcedDegradation:
    def test_lp_intent_empty_thema_forces_degradation(self):
        ss = {"persona_id": "P-LEHR", "entities": {}}  # no thema, no stufe
        po: dict = {}
        has, thema = detect_lp_intent(
            classification=_cls("I01"),
            message="Erstelle einen Lernpfad",
            session_state=ss,
            pattern_output=po,
        )
        assert has is True
        assert thema == ""
        assert po["degradation"] is True
        assert set(po["missing_slots"]) == {"thema", "stufe"}

    def test_degradation_filters_present_slots(self):
        ss = {"persona_id": "P-LEHR", "entities": {"stufe": "5"}}
        po: dict = {}
        detect_lp_intent(
            classification=_cls("I01"),
            message="Lernpfad bitte",
            session_state=ss,
            pattern_output=po,
        )
        assert po["missing_slots"] == ["thema"]  # stufe present → only thema

    def test_degradation_merges_existing_missing_slots(self):
        ss = {"persona_id": "P-LEHR", "entities": {}}
        po: dict = {"missing_slots": ["stufe"]}
        detect_lp_intent(
            classification=_cls("I01"),
            message="Lernpfad",
            session_state=ss,
            pattern_output=po,
        )
        assert set(po["missing_slots"]) == {"thema", "stufe"}

    def test_no_lp_intent_no_degradation(self):
        ss = {"persona_id": "P-LEHR", "entities": {}}
        po: dict = {}
        detect_lp_intent(
            classification=_cls("I01"),
            message="Was ist das?",
            session_state=ss,
            pattern_output=po,
        )
        assert po == {}


# ── C1-f2c-b: das LP-Stichwort-Gate kannte nur Deutsch ───────────────
# Auf Englisch blieb allein der Klassifikator-Pfad (``intent_id == "I04"``)
# — das deterministische Gate griff nie.

class TestEnglishLpKeywords:
    def test_english_lesson_plan_request_has_lp_intent(self):
        for msg in ("create a lesson plan on photosynthesis",
                    "I need a learning path for fractions",
                    "help me with my lesson preparation"):
            has, _ = detect_lp_intent(
                classification=_cls("I01"), message=msg,
                session_state={"entities": {"thema": "X"}}, pattern_output={})
            assert has is True, msg

    def test_a_plain_question_still_has_no_lp_intent(self):
        has, _ = detect_lp_intent(
            classification=_cls("I01"), message="do you have videos on fractions",
            session_state={"entities": {"thema": "X"}}, pattern_output={})
        assert has is False

    def test_blocking_intent_still_wins_over_the_english_keyword(self):
        """Die Sperr-Intents sind wichtiger als das Stichwort — wer einen
        BESTEHENDEN Lernpfad bearbeiten will, bekommt keinen neuen."""
        has, _ = detect_lp_intent(
            classification=_cls("I06"), message="edit my lesson plan",
            session_state={"entities": {"thema": "X"}}, pattern_output={})
        assert has is False


# ── C1-f2c-b: der zweite Auftrag des Stichwort-Satzes ───────────────
# ``_lp_keywords`` erkennt nicht nur die Absicht — dieselben Woerter werden
# aus der Nachricht gestrichen, um das Thema freizulegen (Rueckfall, wenn
# der Klassifikator kein ``thema`` geliefert hat). Bis C1-f2c-b lag diese
# zweite Wirkung als Schleife in ``lp_fast_path`` und war nicht pruefbar.

class TestStripLpCommandWords:
    def test_german_stays_byte_exact(self):
        assert strip_lp_command_words(
            "erstelle mir einen lernpfad zum thema photosynthese"
        ) == "photosynthese"

    def test_english_command_words_are_stripped_too(self):
        assert strip_lp_command_words(
            "create a lesson plan on photosynthesis"
        ) == "photosynthesis"
        assert strip_lp_command_words(
            "please prepare a learning path about fractions"
        ) == "fractions"

    def test_no_new_short_word_eats_into_a_topic(self):
        """Die Streichung arbeitet auf Teilzeichenketten, nicht auf Woertern —
        deshalb tragen die neuen englischen Fuellwoerter Leerzeichen. Ohne
        die waere „a" in „maths" und „on" in „photosynthesis" mitgegangen."""
        assert strip_lp_command_words("lesson plan on maths") == "maths"
        assert "photosynthesis" in strip_lp_command_words("a lesson plan photosynthesis")
