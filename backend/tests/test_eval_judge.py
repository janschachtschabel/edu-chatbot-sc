"""Judge-Tests (Port aus ALT + GV4-Erweiterungen).

Alles, was der Judge mit einer LLM-Antwort tut: Scores koerzieren + klemmen,
Freitext kappen, Hint-vs-Engine-Verdict normalisieren, Judge-eigene Floskeln
filtern. Seit GV4 (2026-08-22, Plan §5) dazu: ``pattern_match`` ist None,
wenn kein echtes Muster (M01–M20) lief — ``total`` normalisiert über die
BEWERTETEN Achsen; ein ``soll_angebot`` ergänzt die Achse ``auftrag_erfuellt``;
und ein toter Judge-Aufruf WIRFT ``JudgeError`` statt still 0 Punkte zu
verbuchen (die Aufrufer markieren den Turn als ``judge_failed`` — ALT und NEU
verbuchten beide eine stille Null, die den Schnitt der übrigen Turns drückte).
Offline — die LLM-Grenze ist gefaked.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.services.eval import judge as ej
from boerdi.services.eval import scenario_gen as sg
from tests.eval_fakes import FakeLLM

_J_DEBUG = {"pattern": "?", "persona": "?", "intent": "?",
            "safety": "ok", "tools_called": []}


def _judge(monkeypatch, reply=None, exc=None, debug=None, soll=None):
    fake = FakeLLM(replies=[reply] if reply is not None else [], exc=exc)
    monkeypatch.setattr(ej, "chat_completion", fake)
    out = asyncio.run(ej.judge_turn(
        {}, {}, "Nutzerfrage", "Bot-Antwort",
        debug if debug is not None else dict(_J_DEBUG),
        soll_angebot=soll,
    ))
    return out, fake


def test_judge_turn_coerces_and_clamps_scores(monkeypatch):
    reply = json.dumps({
        "intent_fit": 2, "persona_tone": "3", "pattern_match": "abc",
        "safety": -5, "info_quality": 1.9, "notes": 123,
    })
    out, _ = _judge(monkeypatch, reply)
    # "3" → int 3 → clamped to 2; -5 → 0; 1.9 → int() → 1.
    assert out["intent_fit"] == 2
    assert out["persona_tone"] == 2
    assert out["safety"] == 0
    assert out["info_quality"] == 1
    assert out["notes"] == "123"
    # Debug-Pattern "?" = kein echtes Muster → nicht bewertet, und ``total``
    # normalisiert über die 4 bewerteten Achsen statt stumm durch 10 zu teilen.
    assert out["pattern_match"] is None
    assert out["total"] == round((2 + 2 + 0 + 1) / 8.0, 3)


def test_real_pattern_is_scored_and_total_is_over_five_axes(monkeypatch):
    monkeypatch.setattr(ej, "_build_pattern_expectations", lambda pid: f"<{pid}>")
    debug = dict(_J_DEBUG, pattern="M15 (Orientierung)")
    reply = json.dumps({"intent_fit": 2, "persona_tone": 2, "pattern_match": 2,
                        "safety": 2, "info_quality": 2})
    out, _ = _judge(monkeypatch, reply, debug=debug)
    assert out["pattern_match"] == 2
    assert out["total"] == 1.0


def test_agent_pattern_is_not_scored(monkeypatch):
    """Der Agent meldet kein Muster (bzw. das synthetische ``AGENT``). Bis GV4
    bekam der Judge dafür „(Pattern AGENT nicht in 03-patterns/ gefunden)" als
    Rubrik und bewertete ins Leere."""
    debug = dict(_J_DEBUG, pattern="AGENT")
    reply = json.dumps({"intent_fit": 2, "persona_tone": 2, "pattern_match": 2,
                        "safety": 2, "info_quality": 2})
    out, fake = _judge(monkeypatch, reply, debug=debug)
    assert out["pattern_match"] is None  # Reply-Wert wird verworfen
    assert out["total"] == 1.0  # 8/8 über die 4 bewerteten Achsen
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "nicht in 03-patterns/ gefunden" not in prompt
    assert "kein Muster gelaufen" in prompt


def test_judge_turn_caps_notes_issues_missing_info(monkeypatch):
    reply = json.dumps({
        "intent_fit": 1,  # ein Achsen-Wert, damit die Antwort als Urteil gilt
        "notes": "n" * 400,
        "issues": ["i" * 300] * 12,
        "missing_info": ["m" * 300] * 12,
    })
    out, _ = _judge(monkeypatch, reply)
    assert len(out["notes"]) == 300
    assert len(out["issues"]) == 8 and all(len(x) == 200 for x in out["issues"])
    assert len(out["missing_info"]) == 8
    assert all(len(x) == 200 for x in out["missing_info"])


def test_judge_turn_verdict_valid_and_floskel_filtered(monkeypatch):
    # ``intent_fit`` nur, damit die Antwort als Urteil gilt (Review Runde 2:
    # achsenfreie Antworten werfen JudgeError); geprüft wird hier das Verdict.
    reply = json.dumps({
        "intent_fit": 2,
        "pattern_hint_verdict": "Engine_Better",
        "pattern_hint_reasoning": "Engine und Hint sind identisch, kein Vergleich nötig.",
    })
    out, _ = _judge(monkeypatch, reply)
    assert out["pattern_hint_verdict"] == "engine_better"
    # The judge sometimes echoes the prompt's own verdict *definition* back as
    # its reasoning. That is not an assessment → emptied, studio falls back to
    # notes.
    assert out["pattern_hint_reasoning"] == ""


def test_judge_turn_invalid_verdict_with_hint_falls_back_to_no_disagreement(monkeypatch):
    # ALT fix 2026-07-10 (B2): an invalid verdict plus a present hint yields the
    # neutral ``no_disagreement`` instead of an empty string, which used to be
    # persisted as "" and carried no aggregate meaning.
    debug = dict(_J_DEBUG, pattern_id_hint="M05", pattern_reasoning="weil")
    reply = json.dumps({"intent_fit": 1,
                        "pattern_hint_verdict": "banana",
                        "pattern_hint_reasoning": "x" * 400})
    out, fake = _judge(monkeypatch, reply, debug=debug)
    assert out["pattern_hint_verdict"] == "no_disagreement"
    assert len(out["pattern_hint_reasoning"]) == 300
    # The hint's own rationale is handed to the judge.
    assert "Hint-Begründung: weil" in fake.calls[0]["messages"][0]["content"]


def test_judge_turn_missing_verdict_without_hint_is_no_disagreement(monkeypatch):
    out, _ = _judge(monkeypatch, json.dumps({"intent_fit": 1}))
    assert out["pattern_hint_verdict"] == "no_disagreement"


def test_judge_turn_call_params(monkeypatch):
    _, fake = _judge(monkeypatch, json.dumps({"intent_fit": 2}))
    call = fake.calls[0]
    assert call["model"] == sg.judge_model()
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}
    assert call["background"] is True
    prompt = call["messages"][0]["content"]
    # Ohne echtes Muster keine Muster-Rubrik; ohne Persona/Intent-IDs die
    # Fallback-Erwartungen (kein Config-I/O).
    assert "kein Muster gelaufen" in prompt
    assert "(keine Persona-Erwartungen)" in prompt
    assert "(keine Intent-Erwartungen)" in prompt


# ── GV4: Soll-Angebot → Achse auftrag_erfuellt ───────────────────────────

def test_soll_angebot_reaches_the_prompt_and_adds_the_axis(monkeypatch):
    reply = json.dumps({"intent_fit": 2, "persona_tone": 2, "safety": 2,
                        "info_quality": 2, "auftrag_erfuellt": 1})
    out, fake = _judge(monkeypatch, reply, soll="Treffer plus Anschlussangebot.")
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "SOLL-ANGEBOT" in prompt
    assert "Treffer plus Anschlussangebot." in prompt
    assert out["auftrag_erfuellt"] == 1
    # 4 bewertete Basis-Achsen (pattern "?" → None) + auftrag: 9 von 10.
    assert out["total"] == round(9 / 10.0, 3)


def test_auftrag_erfuellt_is_clamped_like_the_other_axes(monkeypatch):
    reply = json.dumps({"auftrag_erfuellt": "5"})
    out, _ = _judge(monkeypatch, reply, soll="x")
    assert out["auftrag_erfuellt"] == 2


def test_without_soll_the_axis_is_absent(monkeypatch):
    out, fake = _judge(monkeypatch, json.dumps({"intent_fit": 2}))
    assert "auftrag_erfuellt" not in out
    assert "SOLL-ANGEBOT" not in fake.calls[0]["messages"][0]["content"]


# ── GV4: Judge-Fehler werfen, statt still 0 Punkte zu verbuchen ──────────

def test_judge_turn_llm_failure_raises(monkeypatch):
    """Spec-Änderung GV4: bis dahin degradierte ein toter Judge zu 0 Punkten
    und drückte still den Schnitt (ALT-Schwäche, mitportiert). Jetzt wirft er;
    die Aufrufer markieren den Turn als ``judge_failed``."""
    with pytest.raises(ej.JudgeError):
        _judge(monkeypatch, exc=RuntimeError("judge down"))


def test_judge_turn_unparseable_json_raises(monkeypatch):
    with pytest.raises(ej.JudgeError):
        _judge(monkeypatch, "kein json")


def test_judge_turn_empty_reply_raises(monkeypatch):
    """Review 2026-08-22 (Runde 2): ein leeres ``content`` wurde zu ``"{}"``
    und damit zu einem stillen 0-Punkte-Urteil über alle Achsen — exakt die
    GV4-Schwäche, nur eine Ebene tiefer (der Anbieter liefert nachweislich
    leere ``content``-Felder, siehe #268). Leer heißt: niemand hat geurteilt."""
    with pytest.raises(ej.JudgeError):
        _judge(monkeypatch, "")


def test_judge_turn_non_object_json_raises(monkeypatch):
    """Ein JSON-Array warf vorher ``AttributeError`` AUSSERHALB des try-Blocks:
    im Szenario-Pfad als Chat-Fehler fehlklassifiziert (der Chat hatte
    geantwortet!), im Dialog-Pfad brach es den ganzen Lauf ab."""
    with pytest.raises(ej.JudgeError):
        _judge(monkeypatch, "[]")


def test_judge_turn_object_without_axes_raises(monkeypatch):
    """Ein Objekt ohne einen einzigen Achsen-Wert ist kein Urteil — vorher
    wurde es zu 0 Punkten auf allen Achsen koerziert."""
    with pytest.raises(ej.JudgeError):
        _judge(monkeypatch, json.dumps({"notes": "kein einziger Achsen-Wert"}))


def test_judge_turn_uses_the_bare_pattern_id_for_expectations(monkeypatch):
    """A decorated pattern must not be looked up verbatim.

    ``debug.pattern`` is formatted ``"M15 (Orientierung)"``; looking that up in
    the pattern config never matches, and the judge would silently be told
    "pattern not found" for every turn.
    """
    debug = dict(_J_DEBUG, pattern="M15 (Orientierung)")
    monkeypatch.setattr(
        ej, "_build_pattern_expectations", lambda pid: f"<{pid}>",
    )
    _, fake = _judge(monkeypatch, json.dumps({"intent_fit": 2}), debug=debug)
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "<M15>" in prompt
    # The undecorated original still reaches the judge as the engine's choice.
    assert "M15 (Orientierung)" in prompt
