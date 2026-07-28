"""Token-usage extraction + per-turn accumulator (P3-1, port of ALT
llm_usage.py). The accumulator dict is the exact shape that lands in
DebugInfo.token_usage — totals + per-model + per-phase breakdown so we can
diagnose where the OpenAI prompt cache hits and where it breaks.
"""

from __future__ import annotations

from typing import Any


def extract_usage(resp: Any) -> dict[str, Any]:
    """Flatten an OpenAI/LiteLLM response's usage into
    {prompt, completion, cached, model}. ``cached`` comes from
    ``prompt_tokens_details.cached_tokens`` (prompt cache); 0 on any miss."""
    try:
        u = getattr(resp, "usage", None)
        if not u:
            return {"prompt": 0, "completion": 0, "cached": 0,
                    "model": getattr(resp, "model", "") or ""}
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        return {
            "prompt": getattr(u, "prompt_tokens", 0) or 0,
            "completion": getattr(u, "completion_tokens", 0) or 0,
            "cached": cached,
            "model": getattr(resp, "model", "") or "",
        }
    except Exception:
        return {"prompt": 0, "completion": 0, "cached": 0, "model": ""}


def new_accumulator() -> dict[str, Any]:
    """Empty per-turn accumulator (one per chat turn, threaded through
    LLM-calling helpers). ``per_phase`` splits totals by call-site label
    (classify | tool_loop | response | quick_replies | …)."""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "calls": 0,
        "models": {},
        "per_phase": {},
    }


def add_usage(
    acc: dict[str, Any] | None, usage: dict[str, Any], phase: str | None = None
) -> None:
    """Fold one extracted usage record into the accumulator (totals + the
    per-model bucket + optionally the per-phase bucket)."""
    if not acc or not usage:
        return
    p = int(usage.get("prompt", 0) or 0)
    c = int(usage.get("completion", 0) or 0)
    cached = int(usage.get("cached", 0) or 0)
    acc["prompt_tokens"] += p
    acc["completion_tokens"] += c
    acc["cached_tokens"] += cached
    acc["calls"] += 1
    model = usage.get("model") or "unknown"
    m = acc["models"].setdefault(model, {"prompt": 0, "completion": 0, "cached": 0, "calls": 0})
    m["prompt"] += p
    m["completion"] += c
    m["cached"] += cached
    m["calls"] += 1
    if phase:
        ph = acc.setdefault("per_phase", {}).setdefault(
            phase, {"prompt": 0, "completion": 0, "cached": 0, "calls": 0})
        ph["prompt"] += p
        ph["completion"] += c
        ph["cached"] += cached
        ph["calls"] += 1
