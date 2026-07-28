"""P3-1: token-usage extraction + per-turn accumulator — port of ALT
llm_usage.py (_extract_usage / usage_accumulator_new / usage_accumulator_add).
The accumulator dict is the shape that lands in DebugInfo.token_usage.
"""

from __future__ import annotations

from types import SimpleNamespace

from boerdi.obs import usage


def _resp(prompt: int, completion: int, cached: int, model: str) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        usage=SimpleNamespace(
            prompt_tokens=prompt,
            completion_tokens=completion,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        ),
    )


def test_extract_usage_reads_cached_from_details() -> None:
    got = usage.extract_usage(_resp(100, 40, 64, "gpt-5.4-mini"))
    assert got == {"prompt": 100, "completion": 40, "cached": 64, "model": "gpt-5.4-mini"}


def test_extract_usage_missing_usage_is_zero() -> None:
    got = usage.extract_usage(SimpleNamespace(model="m", usage=None))
    assert got == {"prompt": 0, "completion": 0, "cached": 0, "model": "m"}


def test_extract_usage_no_details_defaults_cached_zero() -> None:
    resp = SimpleNamespace(model="m", usage=SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, prompt_tokens_details=None))
    assert usage.extract_usage(resp)["cached"] == 0


def test_accumulator_sums_totals_models_and_phases() -> None:
    acc = usage.new_accumulator()
    assert acc == {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0,
                   "calls": 0, "models": {}, "per_phase": {}}

    usage.add_usage(acc, usage.extract_usage(_resp(100, 40, 64, "m1")), phase="classify")
    usage.add_usage(acc, usage.extract_usage(_resp(200, 60, 0, "m1")), phase="response")
    usage.add_usage(acc, usage.extract_usage(_resp(50, 10, 10, "m2")), phase="response")

    assert acc["prompt_tokens"] == 350
    assert acc["completion_tokens"] == 110
    assert acc["cached_tokens"] == 74
    assert acc["calls"] == 3
    assert acc["models"]["m1"] == {"prompt": 300, "completion": 100, "cached": 64, "calls": 2}
    assert acc["models"]["m2"] == {"prompt": 50, "completion": 10, "cached": 10, "calls": 1}
    assert acc["per_phase"]["classify"]["calls"] == 1
    assert acc["per_phase"]["response"] == {
        "prompt": 250, "completion": 70, "cached": 10, "calls": 2}


def test_add_usage_ignores_empty() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, {})
    usage.add_usage(None, {"prompt": 5})
    assert acc["calls"] == 0


def test_add_usage_without_phase_skips_per_phase() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, usage.extract_usage(_resp(10, 5, 0, "m")))
    assert acc["calls"] == 1 and acc["per_phase"] == {}
    assert acc["models"]["m"]["prompt"] == 10


def test_unknown_model_bucketed() -> None:
    acc = usage.new_accumulator()
    usage.add_usage(acc, {"prompt": 3, "completion": 1, "cached": 0, "model": ""})
    assert "unknown" in acc["models"]
