"""Port of ALT's scenario-generator tests (tests/test_eval_service.py:100-248).

Two units: the persona POSITIV/NEGATIV marker block that gets injected into the
prompt, and the generator that turns an LLM reply into scenario dicts. Both
offline — the LLM boundary is faked.

Adaptation: ALT patched ``get_background_client``; NEU patches
``chat_completion`` on the consumer module (see tests/eval_fakes.py).
"""

from __future__ import annotations

import asyncio

from boerdi.services.eval import scenario_gen as sg
from tests.eval_fakes import FakeLLM


def _run(coro):
    return asyncio.run(coro)


# ── model resolution (the ALT limitation this port removes) ─────────


def test_models_come_from_settings(monkeypatch):
    monkeypatch.setenv("EVAL_SIMULATOR_MODEL", "gpt-5-sim")
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "gpt-5-judge")
    assert sg.simulator_model() == "gpt-5-sim"
    assert sg.judge_model() == "gpt-5-judge"


def test_empty_env_var_falls_back_instead_of_sending_model_empty(monkeypatch):
    # docker-compose passes ${VAR:-} through: SET BUT EMPTY. Without the guard
    # the provider gets model="" → HTTP 400 and the whole stage dies.
    monkeypatch.setenv("EVAL_SIMULATOR_MODEL", "")
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "")
    assert sg.simulator_model() == "gpt-4o-mini"
    assert sg.judge_model() == "gpt-4o-mini"


# ── _build_persona_markers_block ────────────────────────────────────

_P_LEH = {
    "id": "P-LEH",
    "positive_markers": ["meine Klasse", "Unterricht"],
    "anti_markers": [
        {"phrase": "mein Kind", "redirect_to": "P-ELT"},
        {"phrase": "   "},           # empty → skipped
        "roh-string",                # legacy list[str] form
        {"phrase": "Hausaufgabe"},   # dict without redirect_to
    ],
}
_P_ELT = {"id": "P-ELT", "hints": ["mein Kind", "mein Sohn"]}
_P_AND = {"id": "P-AND"}


def test_markers_block_positive_and_negative_sections():
    out = sg._build_persona_markers_block(_P_LEH, [_P_LEH, _P_ELT, _P_AND])
    assert out.startswith(
        'POSITIV (MUSS in der Eröffnung vorkommen):\n  - "meine Klasse"\n  - "Unterricht"'
    )
    assert "NEGATIV (NICHT verwenden — wuerde andere Persona triggern):" in out
    # Own anti_markers: dict with redirect → tag, empty phrase dropped, legacy
    # string quoted, dict without redirect untagged.
    assert '  - "mein Kind" (= P-ELT)' in out
    assert '  - "roh-string"' in out
    assert '  - "Hausaufgabe"' in out
    # Cross-persona NEGATIV: the others' positive markers, tagged with whose.
    assert '  - "mein Sohn" (= P-ELT)' in out


def test_markers_block_p_and_inversion():
    out = sg._build_persona_markers_block(_P_AND, [_P_LEH, _P_ELT, _P_AND])
    assert out.startswith("POSITIV (Eröffnung soll GENERISCH bleiben")
    assert "NEGATIV (jeder klare Marker bricht die P-AND-Anonymität):" in out
    # For P-AND every foreign marker is forbidden — that is the inversion.
    assert '  - "meine Klasse" (= P-LEH)' in out
    assert '  - "mein Kind" (= P-ELT)' in out


def test_markers_block_no_positive_markers_fallback():
    out = sg._build_persona_markers_block({"id": "P-X"}, [{"id": "P-X"}])
    assert out == "POSITIV: (keine Marker konfiguriert — Eröffnung darf generisch sein)"


def test_markers_block_cross_persona_capped_at_six_per_other():
    other = {"id": "P-A", "hints": [f"marker-{i}" for i in range(8)]}
    out = sg._build_persona_markers_block({"id": "P-B"}, [other, {"id": "P-B"}])
    neg_lines = [ln for ln in out.split("\n") if ln.startswith("  - ")]
    assert len(neg_lines) == 6
    assert '  - "marker-5" (= P-A)' in out
    assert "marker-6" not in out


def test_markers_block_p_and_negativ_capped_at_twenty():
    others = [
        {"id": f"P-{n}", "hints": [f"m{n}-{i}" for i in range(7)]}
        for n in range(4)
    ]  # 4 × min(7,6) = 24 cross markers → capped at 20
    out = sg._build_persona_markers_block({"id": "P-AND"}, others + [{"id": "P-AND"}])
    neg_lines = [ln for ln in out.split("\n") if ln.startswith("  - ")]
    assert len(neg_lines) == 20


# ── generate_scenarios ──────────────────────────────────────────────

_GEN_PERSONA = {"id": "P-LEH", "label": "Lehrkraft", "description": "unterrichtet",
                "positive_markers": ["meine Klasse"]}
_GEN_INTENT = {"id": "I01", "label": "Material suchen", "description": "sucht",
               "trigger_verbs": ["suche", "finde"]}


def test_generate_scenarios_parses_numbers_bullets_and_quotes(monkeypatch):
    raw = (
        "1. Ich suche Arbeitsblätter für Mathe\n"
        '- "Können Sie mir Material zeigen?"\n'
        "Hi\n"
        "2) Noch eine dritte Zeile hier"
    )
    fake = FakeLLM(replies=[raw])
    monkeypatch.setattr(sg, "chat_completion", fake)
    scens = _run(sg.generate_scenarios([_GEN_PERSONA], [_GEN_INTENT], count_per_combo=2))
    # 3 candidates ("Hi" is under 8 chars and drops out) → capped at 2
    assert len(scens) == 2
    assert scens[0]["opening"] == "Ich suche Arbeitsblätter für Mathe"
    # Bullet + number prefix are stripped BEFORE the quotes, so `- "Frage?"`
    # loses both quotes (ALT fix 2026-07-10 B7: quote-first left the leading one).
    assert scens[1]["opening"] == "Können Sie mir Material zeigen?"
    assert scens[0] == {
        "persona_id": "P-LEH", "persona_label": "Lehrkraft",
        "intent_id": "I01", "intent_label": "Material suchen",
        "opening": "Ich suche Arbeitsblätter für Mathe", "index": 0,
    }


def test_generate_scenarios_call_params_and_prompt_content(monkeypatch):
    fake = FakeLLM(replies=["Eine lange genug erste Zeile"])
    monkeypatch.setattr(sg, "chat_completion", fake)
    _run(sg.generate_scenarios([_GEN_PERSONA], [_GEN_INTENT], count_per_combo=1))
    call = fake.calls[0]
    assert call["model"] == sg.simulator_model()
    assert call["temperature"] == 0.7
    # The eval must not compete with live traffic for LLM slots.
    assert call["background"] is True
    prompt = call["messages"][0]["content"]
    assert "Lehrkraft" in prompt and "Material suchen" in prompt
    assert '"suche", "finde"' in prompt   # trigger_verbs quoted + joined
    assert '"meine Klasse"' in prompt     # marker block injected


def test_generate_scenarios_no_trigger_verbs_fallback_text(monkeypatch):
    fake = FakeLLM(replies=["Eine lange genug erste Zeile"])
    monkeypatch.setattr(sg, "chat_completion", fake)
    intent = {"id": "I02", "label": "X", "description": ""}
    _run(sg.generate_scenarios([_GEN_PERSONA], [intent], count_per_combo=1))
    assert "(keine Trigger-Verben konfiguriert)" in fake.calls[0]["messages"][0]["content"]


def test_generate_scenarios_unparseable_reply_yields_empty(monkeypatch):
    fake = FakeLLM(replies=["ok"])  # under 8 chars → no candidate
    monkeypatch.setattr(sg, "chat_completion", fake)
    assert _run(sg.generate_scenarios([_GEN_PERSONA], [_GEN_INTENT], 2)) == []


def test_generate_scenarios_llm_error_skips_combo_without_raising(monkeypatch):
    # One dead combo must not abort a run of 144 combos.
    fake = FakeLLM(exc=RuntimeError("provider down"))
    monkeypatch.setattr(sg, "chat_completion", fake)
    assert _run(sg.generate_scenarios([_GEN_PERSONA], [_GEN_INTENT], 2)) == []


def test_generate_scenarios_progress_cb_called_and_errors_swallowed(monkeypatch):
    fake = FakeLLM(replies=["Eine lange genug erste Zeile"] * 2)
    monkeypatch.setattr(sg, "chat_completion", fake)
    seen: list[tuple] = []

    async def cb(idx, total, pid, iid):
        seen.append((idx, total, pid, iid))
        raise RuntimeError("cb kaputt")  # must never break generation

    p2 = {"id": "P-ELT", "label": "Eltern", "description": ""}
    scens = _run(sg.generate_scenarios(
        [_GEN_PERSONA, p2], [_GEN_INTENT], 1, progress_cb=cb,
    ))
    assert seen == [(1, 2, "P-LEH", "I01"), (2, 2, "P-ELT", "I01")]
    assert len(scens) == 2
