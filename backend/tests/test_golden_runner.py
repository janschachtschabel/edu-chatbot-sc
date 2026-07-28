"""P0-8: golden-flow runner port (evals/run_golden.py) — deterministic parts.

Ports of ALT eval_golden._check_golden_turn / eval_metrics._aggregate_golden /
eval_text_utils helpers must behave identically (incl. B1 semantics: wildcard
persona / empty intent / register 'any' are None == not asserted).
"""

import asyncio
import importlib.util
from pathlib import Path

import yaml

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("run_golden", EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def test_strip_id() -> None:
    assert rg.strip_id("M03 (Schritt-für-Schritt)") == "M03"
    assert rg.strip_id("P-LEH") == "P-LEH"
    assert rg.strip_id("") == ""


def test_detect_register() -> None:
    assert rg.detect_register("Gerne zeige ich Ihnen passende Materialien.")[0] == "sie"
    assert rg.detect_register("Schau dir das an, du findest dein Material hier.")[0] == "du"
    assert rg.detect_register("Hier sind Materialien.")[0] == "neutral"


def test_check_golden_turn_assertions() -> None:
    expect = {"persona": "P-LEH", "intent": "I03", "register": "sie", "structure": "cards"}
    bot = {
        "content": "Gerne zeige ich Ihnen Material.",
        "cards": [{"wlo_url": "https://redaktion.openeduhub.net/x"}],
        "inline_documents": [],
        "quick_replies": ["Mehr zeigen"],
    }
    debug = {"persona": "P-LEH (Lehrkraft)", "intent": "I03 (Suche)", "pattern": "M05 (x)"}
    got = rg.check_golden_turn(expect, bot, debug)
    assert got["checks"] == {
        "persona": True, "intent": True, "register": True,
        "structure": True, "qr": True, "host": True,
    }


def test_check_golden_turn_not_asserted_is_none() -> None:
    # B1 (ALT 2026-07-10): wildcard/empty/any => None, NOT True
    got = rg.check_golden_turn(
        {"persona": "*", "intent": "", "register": "any"},
        {"content": "Hi", "cards": [], "inline_documents": [], "quick_replies": []},
        {"persona": "P-AND", "intent": "I01"},
    )
    checks = got["checks"]
    assert checks["persona"] is None
    assert checks["intent"] is None
    assert checks["register"] is None
    assert checks["structure"] is None
    assert checks["host"] is None  # no card urls => not asserted
    assert checks["qr"] is False  # qr is always asserted


def test_check_golden_turn_failures() -> None:
    got = rg.check_golden_turn(
        {"persona": "P-LEH", "intent": "I03", "register": "sie", "structure": "idoc"},
        {
            "content": "Schau du dir dein Material an!",
            "cards": [{"url": "https://fremdhost.example/x"}],
            "inline_documents": [],
            "quick_replies": [],
        },
        {"persona": "P-LER (Lernende)", "intent": "I04 (Lernpfad)"},
    )
    assert got["checks"] == {
        "persona": False, "intent": False, "register": False,
        "structure": False, "qr": False, "host": False,
    }


def test_register_neutral_passes_both_expectations() -> None:
    neutral_bot = {"content": "Hier ist Material.", "cards": [],
                   "inline_documents": [], "quick_replies": ["ok"]}
    for exp_reg in ("sie", "du"):
        got = rg.check_golden_turn(
            {"persona": "*", "register": exp_reg}, neutral_bot, {})
        assert got["checks"]["register"] is True  # only OPPOSITE register fails


def test_aggregate_golden_rates_and_hard_rate() -> None:
    conversations = [{
        "flow_id": "GS-T", "title": "t", "persona_id": "P-LEH",
        "turns": [
            {"golden": {"checks": {"persona": True, "intent": True, "register": None,
                                   "structure": True, "qr": True, "host": True},
                        "expected": {}, "observed": {}}, "user": "a"},
            {"golden": {"checks": {"persona": False, "intent": True, "register": True,
                                   "structure": None, "qr": True, "host": None},
                        "expected": {}, "observed": {}}, "user": "b"},
        ],
    }]
    m = rg.aggregate_golden(conversations)
    assert m["flows"] == 1 and m["turns"] == 2
    # hard cats: persona 1/2, intent 2/2, register 1/1, structure 1/1, qr 2/2 => 7/8
    assert m["hard_total"] == 8 and m["hard_passed"] == 7
    assert m["overall_pass_rate"] == round(7 / 8, 3)
    assert m["rates"]["host"] == 1.0  # host is soft: reported, not in hard rate


# ── run_flows record shape (C3: what the judge + aggregators read) ───────
# The flat debug subset mirrors ALT ``eval_golden._flatten_debug``; the full
# ``debug`` blob (trace, context, entities) must NOT travel, or every golden
# report and every persisted transcript carries kilobytes nobody reads.
_FULL_DEBUG = {
    "pattern": "M04 (Fakten-Bulletin)", "persona": "P-LEH (Lehrkraft)",
    "intent": "I01 (Suche)", "safety": None, "tools_called": ["search_wlo"],
    "pattern_id_hint": "M04", "pattern_reasoning": "weil", "llm_engine_match": True,
    "token_usage": {"total_tokens": 7}, "phase3_modulations": {"length": "kurz"},
    "trace": ["big"], "context": {"blob": "x" * 500}, "entities": {"thema": "wasser"},
}


def _flow(*expects: dict) -> dict:
    return {
        "id": "F1", "title": "Flow Eins", "persona": "P-LEH",
        "turns": [{"message": f"m{i}", "expect": e} for i, e in enumerate(expects, 1)],
    }


def test_run_flows_records_what_judge_and_metrics_read(monkeypatch) -> None:
    async def fake_post(url, message, session_id):
        return {"content": "Antwort", "cards": [{"title": "K", "url": "https://r/x"}],
                "quick_replies": ["a"], "debug": dict(_FULL_DEBUG)}

    monkeypatch.setattr(rg, "post_chat", fake_post)
    convs = asyncio.run(rg.run_flows(
        "http://x/api/chat", [_flow({"persona": "P-LEH", "intent": "I01"}, {})]))

    conv = convs[0]
    assert conv["persona_id"] == "P-LEH"
    assert conv["intent_id"] == "I01"  # primary = turn 1's expected intent
    t1, t2 = conv["turns"]
    assert t1["debug"]["pattern"] == "M04 (Fakten-Bulletin)"
    assert t1["debug"]["llm_engine_match"] is True
    assert set(t1["debug"]) == {
        "pattern", "persona", "intent", "safety", "tools_called", "pattern_id_hint",
        "pattern_reasoning", "llm_engine_match", "token_usage", "phase3_modulations",
    }
    assert t1["expected_persona"] == "P-LEH" and t1["expected_intent"] == "I01"
    assert t1["cards_count"] == 1 and t1["response_length"] == len("Antwort")
    assert t2["expected_intent"] is None  # expect {} → nothing asserted


def test_run_flows_error_turn_keeps_the_expectations(monkeypatch) -> None:
    async def broken_post(url, message, session_id):
        raise RuntimeError("down")

    monkeypatch.setattr(rg, "post_chat", broken_post)
    convs = asyncio.run(rg.run_flows(
        "http://x/api/chat", [_flow({"persona": "P-LEH", "intent": "I01"})]))

    turn = convs[0]["turns"][0]
    assert turn["error"] == "down" and turn["bot"] == "(chat error: down)"
    assert turn["expected_persona"] == "P-LEH" and turn["expected_intent"] == "I01"
    assert "golden" not in turn  # no check result for a turn that never happened


def test_gold_flows_yaml_copy_has_12_flows() -> None:
    data = yaml.safe_load((EVALS / "gold-flows.yaml").read_text(encoding="utf-8"))
    flows = data["flows"]
    assert len(flows) == 12
    assert [f["id"] for f in flows] == [f"GS-{i}" for i in range(1, 13)]
    for flow in flows:
        assert flow["turns"], f"{flow['id']} has no turns"
        for turn in flow["turns"]:
            assert turn.get("message"), f"{flow['id']} turn without message"
