"""Port of ALT's runner tests (tests/test_eval_service.py:250-432 + 900-1100).

The generative run's orchestration: the multi-turn simulator loop with its state
tracking, the single-turn scenario stage, and the failure paths that must degrade
instead of aborting a run of hundreds of turns.

Offline. Three seams are faked: ``chat_completion`` (the simulator LLM),
``_post_chat`` (the live chat), and the judge. ``progress`` is a plain recorder —
persistence is the service's job, not the runner's.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.eval import runner as rn
from tests.eval_fakes import FakeLLM


def test_chat_timeout_default_und_env(monkeypatch):
    """Review-Befund 3 (2026-08-22): 120 s statt ALT-60 (Schleifen-Maschinen
    machen mehrere LLM-Runden je Zug), per ``EVAL_CHAT_TIMEOUT`` übersteuerbar."""
    monkeypatch.delenv("EVAL_CHAT_TIMEOUT", raising=False)
    assert rn._chat_timeout_s() == 120.0
    monkeypatch.setenv("EVAL_CHAT_TIMEOUT", "45")
    assert rn._chat_timeout_s() == 45.0

_PERSONA = {"id": "P-LEH", "label": "Lehrkraft", "description": "d"}
_INTENT = {"id": "I01", "label": "Suchen", "description": "d"}
_URL = "http://chat.test/api/chat"


def _run(coro):
    return asyncio.run(coro)


def _patch_env(monkeypatch, llm, responses):
    """Fake the simulator LLM, the persona config and the live chat."""
    monkeypatch.setattr(rn, "chat_completion", llm)
    monkeypatch.setattr(rn, "load_persona_definitions", lambda: [_PERSONA])
    calls: list[tuple] = []

    async def fake_post(chat_url, message, session_id=None):
        calls.append((message, session_id))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(rn, "_post_chat", fake_post)
    return calls


# ── simulate_conversation ───────────────────────────────────────────


def test_simulate_conversation_three_turns_with_state_tracking(monkeypatch):
    llm = FakeLLM(replies=["Zweite Frage bitte", "Dritte Frage bitte"])
    calls = _patch_env(monkeypatch, llm, [
        {"content": "Antwort eins", "debug": {"state": "state-1 (A)"}, "cards": []},
        {"content": "Antwort zwei", "debug": {"state": "state-2 (B)"}},
        {"content": "Antwort drei", "debug": {"state": "state-2 (B)"}},
    ])
    directives = {"state-1": {"next_likely": ["state-9"]},
                  "state-2": {"next_likely": ["state-2"]}}
    monkeypatch.setattr(rn, "get_state_directive", lambda sid: directives.get(sid, {}))

    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=3, opening="Hallo",
    ))
    assert conv["persona_id"] == "P-LEH" and conv["intent_id"] == "I01"
    assert conv["ended_early"] is False
    assert conv["session_id"].startswith("eval-")
    assert [t["user"] for t in conv["turns"]] == [
        "Hallo", "Zweite Frage bitte", "Dritte Frage bitte"]

    d0, d1, d2 = (t["debug"] for t in conv["turns"])
    # Turn 0 has no predecessor → plausibility not assessable.
    assert (d0["state_id"], d0["prev_state_id"], d0["transition_plausible"]) == (
        "state-1", "", None)
    # Turn 1: state-2 is neither in next_likely(state-1) nor == prev → False.
    assert (d1["state_id"], d1["prev_state_id"], d1["transition_plausible"]) == (
        "state-2", "state-1", False)
    # Turn 2: state-2 IS in next_likely(state-2) → True.
    assert (d2["state_id"], d2["prev_state_id"], d2["transition_plausible"]) == (
        "state-2", "state-2", True)

    # All chat calls share one session — that is what makes it a conversation.
    assert len({sid for _, sid in calls}) == 1
    assert conv["turns"][0]["cards_count"] == 0
    assert conv["turns"][0]["response_length"] == len("Antwort eins")


def test_simulate_conversation_ende_marker_stops_early(monkeypatch):
    llm = FakeLLM(replies=["[ende]"])  # case-insensitive
    _patch_env(monkeypatch, llm, [{"content": "Antwort", "debug": {}}])
    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=3, opening="Hallo",
    ))
    assert conv["ended_early"] is True
    assert len(conv["turns"]) == 1


def test_simulate_conversation_generates_opening_when_missing(monkeypatch):
    llm = FakeLLM(replies=["Generierte Eröffnung hier"])
    calls = _patch_env(monkeypatch, llm, [{"content": "Antwort", "debug": {}}])
    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=1, opening=None,
    ))
    assert conv["turns"][0]["user"] == "Generierte Eröffnung hier"
    assert calls[0][0] == "Generierte Eröffnung hier"
    # With max_turns=1 the opening seed is the only LLM call.
    assert len(llm.calls) == 1
    seed = llm.calls[0]["messages"]
    assert seed[0]["role"] == "system"
    assert seed[1]["content"] == (
        "Starte die Konversation mit einer realistischen Eroeffnungsnachricht."
    )
    assert llm.calls[0]["temperature"] == 0.8
    assert llm.calls[0]["background"] is True


def test_simulate_conversation_chat_error_records_turn_and_breaks(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(rn, "chat_completion", llm)
    monkeypatch.setattr(rn, "load_persona_definitions", lambda: [_PERSONA])

    async def broken_post(chat_url, message, session_id=None):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(rn, "_post_chat", broken_post)
    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=3, opening="Hallo",
    ))
    # A chat error ends the dialogue but is NOT the simulator's [ENDE].
    assert conv["ended_early"] is False
    assert conv["turns"] == [{
        "user": "Hallo", "bot": "(chat error: kaputt)",
        "debug": {}, "error": "kaputt",
    }]


def test_simulate_conversation_merges_canvas_update_content(monkeypatch):
    llm = FakeLLM()
    _patch_env(monkeypatch, llm, [
        {"content": "Hier dein Material", "debug": {},
         "page_action": {"action": "canvas_update",
                         "payload": {"markdown": "MD-Inhalt"}}},
    ])
    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=1, opening="Mach es einfacher",
    ))
    bot = conv["turns"][0]["bot"]
    assert "[Canvas-Inhalt — vom Nutzer sichtbar]" in bot and "MD-Inhalt" in bot
    # response_length measures the MERGED text, canvas appendix included.
    assert conv["turns"][0]["response_length"] == len(bot)


def test_simulate_conversation_simulator_error_breaks_loop(monkeypatch):
    llm = FakeLLM(exc=RuntimeError("sim down"))
    _patch_env(monkeypatch, llm, [{"content": "Antwort", "debug": {}}])
    conv = _run(rn.simulate_conversation(
        _URL, _PERSONA, _INTENT, max_turns=3, opening="Hallo",
    ))
    # Turn 0 landed; the follow-up simulator call failed → stop, keep turn 0.
    assert len(conv["turns"]) == 1
    assert conv["ended_early"] is False


# ── _augment_bot_text ───────────────────────────────────────────────


def test_augment_bot_text_renders_everything_the_user_saw():
    bot_resp = {
        "content": "Kurze Ankündigung",
        "inline_documents": [{"title": "AB", "content": "Aufgabe 1"}],
        "cards": [{"title": "Karte", "url": "https://x.test/1",
                   "description": "Beschreibung"}],
        "query_metas": [{"title": "Themenseite", "url": "https://x.test/t"}],
        "page_action": {"action": "canvas_open", "payload": {"markdown": "MD"}},
    }
    out = rn._augment_bot_text(bot_resp)
    for expected in ("Kurze Ankündigung", "Aufgabe 1", "Karte", "Themenseite", "MD"):
        assert expected in out


def test_augment_bot_text_card_header_counts_rendered_not_total():
    """With the cap in play the header must not claim more than it shows.

    Otherwise the judge reads "10 Treffer" under 8 rendered cards and marks the
    answer as inconsistent.
    """
    bot_resp = {"content": "x", "cards": [
        {"title": f"K{i}", "url": f"https://x.test/{i}"} for i in range(10)
    ]}
    out = rn._augment_bot_text(bot_resp)
    assert "8 Treffer" in out
    assert "K7" in out and "K8" not in out


def test_augment_bot_text_skips_non_dict_entries():
    assert rn._augment_bot_text(
        {"content": "x", "cards": ["kaputt"], "inline_documents": [None],
         "query_metas": [42]},
    ) == "x"


# ── execute_run (stages + summary) ──────────────────────────────────


@pytest.fixture()
def recorder():
    seen: list[str] = []

    async def progress(conversations, activity):
        seen.append(activity)

    progress.seen = seen  # type: ignore[attr-defined]
    return progress


def _patch_stage(monkeypatch, *, scenarios, chat_resp, judge=None):
    async def fake_generate(personas, intents, count, progress_cb=None):
        if progress_cb is not None:
            await progress_cb(1, 1, personas[0]["id"], intents[0]["id"])
        return scenarios

    async def fake_post(chat_url, message, session_id=None):
        return chat_resp

    async def fake_judge(persona, intent, user, bot, debug):
        return judge or {"total": 0.8, "pattern_match": 2}

    monkeypatch.setattr(rn, "generate_scenarios", fake_generate)
    monkeypatch.setattr(rn, "_post_chat", fake_post)
    monkeypatch.setattr(rn, "judge_turn", fake_judge)


def test_execute_run_scenario_stage_end_to_end(monkeypatch, recorder):
    _patch_stage(
        monkeypatch,
        scenarios=[{"persona_id": "P-LEH", "intent_id": "I01",
                    "opening": "Ich suche Material", "index": 0}],
        chat_resp={"content": "Antwort", "debug": {
            "pattern": "M05 (Suche)", "persona": "P-LEH (x)",
            "intent": "I01 (y)", "tools_called": [],
        }},
    )
    conversations: list[dict] = []
    summary = _run(rn.execute_run(
        chat_url=_URL, run_id="eval-1", conversations=conversations,
        mode="scenarios", personas=[_PERSONA], intents=[_INTENT],
        scenarios_per_combo=1, turns_per_conv=3, target_turns=1,
        progress=recorder,
    ))
    assert len(conversations) == 1
    assert conversations[0]["kind"] == "scenario"
    assert conversations[0]["turns"][0]["judge"]["total"] == 0.8
    assert summary["current_activity"] == "Fertig"
    assert summary["total_judged_turns"] == 1
    assert summary["target_turns"] == 1
    # The trends key must be there — that is the whole point of the run.
    assert "classification_metrics" in summary
    assert summary["classification_metrics"]["judged_turns"] == 1
    assert any("Generiere Szenarien" in a for a in recorder.seen)


def test_execute_run_degrades_a_failing_scenario_turn(monkeypatch, recorder):
    async def fake_generate(personas, intents, count, progress_cb=None):
        return [{"persona_id": "P-LEH", "intent_id": "I01",
                 "opening": "Frage", "index": 0}]

    async def broken_post(chat_url, message, session_id=None):
        raise RuntimeError("chat weg")

    monkeypatch.setattr(rn, "generate_scenarios", fake_generate)
    monkeypatch.setattr(rn, "_post_chat", broken_post)
    conversations: list[dict] = []
    summary = _run(rn.execute_run(
        chat_url=_URL, run_id="eval-2", conversations=conversations,
        mode="scenarios", personas=[_PERSONA], intents=[_INTENT],
        scenarios_per_combo=1, turns_per_conv=3, target_turns=1,
        progress=recorder,
    ))
    # Review-Befund 6 (2026-08-22): ein Chat-Ausfall ist ein Mess-Ausfall,
    # kein 0-Punkte-Bot. Der Zug traegt ``error`` und KEINEN judge (wie im
    # Golden-Weg) und wird als ``chat_error_turns`` gezaehlt, statt den
    # ``avg_score`` des Laufs herunterzuziehen. Bis dahin stand hier die
    # ALT-Konvention judge={"total": 0.0} — der Test validierte den Befund.
    turn = conversations[0]["turns"][0]
    assert "chat weg" in turn["bot"] and turn["error"] == "chat weg"
    assert "judge" not in turn
    assert summary["chat_error_turns"] == 1
    assert summary["total_judged_turns"] == 0
    assert summary["current_activity"] == "Fertig"


def test_build_summary_counts_judge_failed_turns():
    """Review Runde 2 (2026-08-22): der Golden-Weg zählt Judge-Ausfälle
    (``judge_failed_turns``, GV4), der generative Summary tat es nicht — das
    Studio liest den Schlüssel und zeigte für Generativ-Läufe deshalb nie
    einen Ausfall. Gleiche Regel, gleicher Zähler in beiden Familien."""
    conversations = [{
        "persona_id": "P-LEH", "intent_id": "I01",
        "turns": [
            {"user": "a", "bot": "ok", "debug": {}, "judge": {"total": 0.8}},
            {"user": "b", "bot": "ok", "debug": {},
             "judge_failed": "Judge-Aufruf fehlgeschlagen: leer"},
            {"user": "c", "bot": "(error: down)", "debug": {}, "error": "down"},
        ],
    }]
    summary = rn.build_summary(conversations, 3, "Fertig")
    assert summary["judge_failed_turns"] == 1
    assert summary["chat_error_turns"] == 1
    assert summary["total_judged_turns"] == 1


def test_execute_run_i06_scenario_gets_a_priming_turn(monkeypatch, recorder):
    """I06 is an edit intent — without prior material it can only fail."""
    posted: list[tuple[str, str | None]] = []

    async def fake_generate(personas, intents, count, progress_cb=None):
        return [{"persona_id": "P-LEH", "intent_id": "I06",
                 "opening": "Mach es einfacher", "index": 0}]

    async def fake_post(chat_url, message, session_id=None):
        posted.append((message, session_id))
        return {"content": "ok", "debug": {"pattern": "M11 (Edit)"}}

    async def fake_judge(*a):
        return {"total": 1.0}

    monkeypatch.setattr(rn, "generate_scenarios", fake_generate)
    monkeypatch.setattr(rn, "_post_chat", fake_post)
    monkeypatch.setattr(rn, "judge_turn", fake_judge)
    monkeypatch.setattr(rn, "_PRIMING_SETTLE_S", 0)
    monkeypatch.setattr(rn, "_PRIMING_REPOLL_S", 0)

    conversations: list[dict] = []
    _run(rn.execute_run(
        chat_url=_URL, run_id="eval-3", conversations=conversations,
        mode="scenarios", personas=[_PERSONA], intents=[{"id": "I06"}],
        scenarios_per_combo=1, turns_per_conv=3, target_turns=1,
        progress=recorder,
    ))
    assert len(posted) == 2, "priming turn missing"
    assert "Photosynthese" in posted[0][0]
    # Both turns share the primed session, and only the edit turn is judged.
    assert posted[0][1] == posted[1][1] is not None
    assert len(conversations[0]["turns"]) == 1
    assert conversations[0]["turns"][0]["user"] == "Mach es einfacher"
    assert conversations[0]["turns"][0]["debug"]["i06_priming"]["priming_pattern"]


def test_execute_run_conversation_stage_judges_non_error_turns(monkeypatch, recorder):
    async def fake_simulate(chat_url, persona, intent, max_turns=3):
        return {
            "session_id": "eval-x", "persona_id": persona["id"],
            "intent_id": intent["id"], "ended_early": False,
            "turns": [
                {"user": "a", "bot": "b", "debug": {"pattern": "M05 (S)"}},
                {"user": "c", "bot": "(chat error: weg)", "debug": {},
                 "error": "weg"},
            ],
        }

    async def fake_judge(persona, intent, user, bot, debug):
        return {"total": 0.6}

    monkeypatch.setattr(rn, "simulate_conversation", fake_simulate)
    monkeypatch.setattr(rn, "judge_turn", fake_judge)
    conversations: list[dict] = []
    _run(rn.execute_run(
        chat_url=_URL, run_id="eval-4", conversations=conversations,
        mode="conversations", personas=[_PERSONA], intents=[_INTENT],
        scenarios_per_combo=1, turns_per_conv=2, target_turns=2,
        progress=recorder,
    ))
    turns = conversations[0]["turns"]
    assert turns[0]["judge"] == {"total": 0.6}
    # Review-Befund 6 (2026-08-22): der Fehl-Turn behaelt ``error`` und
    # bekommt KEINEN judge — vorher stand hier judge={"total": 0.0}, und ein
    # Anbieter-Aussetzer sah im Lauf-Schnitt wie ein 0-Punkte-Bot aus.
    assert turns[1]["error"] == "weg" and "judge" not in turns[1]
    assert any("Dialog 1/1" in a for a in recorder.seen)


def test_execute_run_conversation_failure_skips_the_combo(monkeypatch, recorder):
    async def broken_simulate(chat_url, persona, intent, max_turns=3):
        raise RuntimeError("simulator weg")

    monkeypatch.setattr(rn, "simulate_conversation", broken_simulate)
    conversations: list[dict] = []
    summary = _run(rn.execute_run(
        chat_url=_URL, run_id="eval-5", conversations=conversations,
        mode="conversations", personas=[_PERSONA], intents=[_INTENT],
        scenarios_per_combo=1, turns_per_conv=2, target_turns=2,
        progress=recorder,
    ))
    # One dead combo is skipped, the run still finishes.
    assert conversations == []
    assert summary["current_activity"] == "Fertig"


def test_execute_run_unknown_mode_runs_no_stage(monkeypatch, recorder):
    conversations: list[dict] = []
    summary = _run(rn.execute_run(
        chat_url=_URL, run_id="eval-6", conversations=conversations,
        mode="nonsense", personas=[_PERSONA], intents=[_INTENT],
        scenarios_per_combo=1, turns_per_conv=3, target_turns=0,
        progress=recorder,
    ))
    assert conversations == [] and summary["total_judged_turns"] == 0
