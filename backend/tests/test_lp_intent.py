"""Characterization tests for domain/lp_intent.py::detect_lp_intent (P4-4-Tail).

ALT origin: ``chat_turn_routing._route_pattern`` LP-intent-detection prolog
(Z. 196-281). Integration-only in ALT → these pin the observable contract: the
``(_has_lp_intent, _thema)`` decision plus the two in-place side effects
(``session_state`` thema-clear on classifier garbage, ``pattern_output`` forced
degradation when an LP intent lacks a concrete topic).
"""

from types import SimpleNamespace

from boerdi.domain.lp_intent import detect_lp_intent


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
