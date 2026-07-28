"""P3-2: instructor classify orchestration (services/classify.py).

Boundary faked: ``classify._acreate`` (= AsyncInstructor.create_with_completion).
The prompt renderer is stubbed so these tests exercise message assembly,
routing/gating wiring, usage folding and the ALT Layer-A fallback — not config.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from boerdi.services import classify
from boerdi.settings import get_settings

_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY", "B_API_KEY")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    # Isolate from config: the prompt is not under test here.
    monkeypatch.setattr(classify, "build_classify_system_prompt",
                        lambda ss, env, cs=None: "SYS")
    return monkeypatch


def _fake_raw(prompt=100, completion=20, cached=10):
    return SimpleNamespace(
        model="gpt-5.4-mini",
        usage=SimpleNamespace(
            prompt_tokens=prompt, completion_tokens=completion,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached)),
    )


def _install(monkeypatch, result=None, raw=None, captured=None):
    from boerdi.api.schemas import ClassificationResult

    async def fake_acreate(*, messages, response_model, max_retries, **kwargs):
        if captured is not None:
            captured.update(messages=messages, response_model=response_model,
                            max_retries=max_retries, kwargs=kwargs)
        return (result or ClassificationResult(persona_id="P-LER", intent_id="I01"),
                raw if raw is not None else _fake_raw())

    monkeypatch.setattr(classify, "_acreate", fake_acreate)


# ── happy path ─────────────────────────────────────────────────────────────
def test_returns_validated_result(monkeypatch) -> None:
    _install(monkeypatch)
    result = asyncio.run(classify.classify_input("hi", [], {}, {}))
    assert result.persona_id == "P-LER" and result.intent_id == "I01"


def test_message_assembly_system_first_user_last(monkeypatch) -> None:
    cap: dict = {}
    _install(monkeypatch, captured=cap)
    asyncio.run(classify.classify_input("frage?", [], {}, {}))
    msgs = cap["messages"]
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[-1] == {"role": "user", "content": "frage?"}


def test_history_capped_to_last_ten_in_order(monkeypatch) -> None:
    cap: dict = {}
    _install(monkeypatch, captured=cap)
    history = [{"role": "user", "content": f"m{i}"} for i in range(12)]
    asyncio.run(classify.classify_input("now", history, {}, {}))
    msgs = cap["messages"]
    assert len(msgs) == 12  # 1 system + 10 history + 1 user
    assert msgs[1:11] == history[-10:]  # last 10, order preserved
    assert msgs[1]["content"] == "m2" and msgs[10]["content"] == "m11"


def test_response_model_and_retries_passed(monkeypatch) -> None:
    from boerdi.api.schemas import ClassificationResult

    cap: dict = {}
    _install(monkeypatch, captured=cap)
    asyncio.run(classify.classify_input("hi", [], {}, {}))
    assert cap["response_model"] is ClassificationResult
    assert cap["max_retries"] == 2  # one validation re-ask (spec improvement)


def test_gpt5_gating_sets_verbosity_drops_temperature(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    cap: dict = {}
    _install(monkeypatch, captured=cap)
    asyncio.run(classify.classify_input("hi", [], {}, {}))
    kw = cap["kwargs"]
    assert kw["model"] == "openai/gpt-5.4-mini"
    assert kw["api_base"] == "https://api.openai.com/v1"
    assert kw["api_key"] == "sk-x"
    assert kw["timeout"] == 75.0 and kw["num_retries"] == 2
    assert kw["verbosity"] == "medium"  # GPT-5 gating flowed through
    assert "temperature" not in kw  # effort=low drops it (tool-call branch)
    assert "tools" not in kw and "reasoning_effort" not in kw  # marker stripped


def test_classic_model_sends_temperature(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    cap: dict = {}
    _install(monkeypatch, captured=cap)
    asyncio.run(classify.classify_input("hi", [], {}, {}))
    kw = cap["kwargs"]
    assert kw["temperature"] == 0.1  # classic branch keeps it
    assert kw["extra_headers"] == {"X-API-KEY": "bkey"}
    assert "verbosity" not in kw


def test_usage_folded_with_classify_phase(monkeypatch) -> None:
    from boerdi.obs import usage

    _install(monkeypatch, raw=_fake_raw(prompt=100, completion=20, cached=10))
    acc = usage.new_accumulator()
    asyncio.run(classify.classify_input("hi", [], {}, {}, usage_acc=acc))
    assert acc["prompt_tokens"] == 100 and acc["completion_tokens"] == 20
    assert acc["cached_tokens"] == 10
    assert acc["per_phase"]["classify"]["calls"] == 1


# ── Layer-A fallback (InstructorRetryException) ────────────────────────────
def _retry_exc(last_completion):
    from instructor.core import InstructorRetryException

    return InstructorRetryException(
        "validation exhausted", last_completion=last_completion,
        n_attempts=2, total_usage=0)


def _raise(monkeypatch, exc):
    async def boom(*, messages, response_model, max_retries, **kwargs):
        raise exc

    monkeypatch.setattr(classify, "_acreate", boom)


def test_fallback_salvages_valid_subset_from_last_completion(monkeypatch) -> None:
    raw = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        tool_calls=[SimpleNamespace(function=SimpleNamespace(
            arguments=json.dumps({"persona_id": "P-LEH", "bogus": 123, "intent_id": "I01"})))]))])
    _raise(monkeypatch, _retry_exc(raw))
    result = asyncio.run(classify.classify_input("hi", [], {}, {}))
    # valid subset kept (model_construct), invalid field dropped, rest defaults
    assert result.persona_id == "P-LEH" and result.intent_id == "I01"
    assert not hasattr(result, "bogus")
    assert result.next_state == "S1"  # schema default fills the gap


def test_fallback_without_completion_returns_defaults(monkeypatch) -> None:
    _raise(monkeypatch, _retry_exc(None))
    result = asyncio.run(classify.classify_input("hi", [], {}, {}))
    assert result.persona_id == "P-AND" and result.intent_id == "I03"  # pure defaults


def test_fallback_on_malformed_arguments_returns_defaults(monkeypatch) -> None:
    raw = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments="not json{"))]))])
    _raise(monkeypatch, _retry_exc(raw))
    result = asyncio.run(classify.classify_input("hi", [], {}, {}))
    assert result.persona_id == "P-AND"  # unparseable → defaults, no crash
