"""Token-usage extraction + per-turn accumulator (P3-1, port of ALT
llm_usage.py). The accumulator dict is the exact shape that lands in
DebugInfo.token_usage — totals + per-model + per-phase breakdown so we can
diagnose where the OpenAI prompt cache hits and where it breaks.
"""

from __future__ import annotations

import contextvars as _ctxvars
from typing import Any

# Der Merkposten DIESES Zuges, je asyncio-Task. Für Aufrufer, die ihn nicht als
# Parameter bekommen können: der Vokabular-Abgleich
# (``mcp/arg_resolvers._llm_vocab_match``) hängt hinter der
# ``TOOL_PREPROCESSORS``-Registry und ``call_mcp_tool`` — gemessen 25
# Aufrufstellen in 11 Dateien (2026-08-11), von denen keine einzige den
# Merkposten braucht. Ihn durchzureichen hieße, die Signatur der Registry und
# jeder dieser Stellen für ein Blatt zu ändern. Dasselbe Mittel löst hier schon
# ``_turn_block`` (``mcp/auth.py``, mit derselben Zählung begründet),
# ``_query_metas`` (``mcp/client.py``) und ``_request_hints``
# (``mcp/arg_resolvers.py``).
#
# Der Standard ist ``None`` und ausdrücklich KEIN ``{}``: ``add_usage`` kehrt
# bei falschem ``acc`` still zurück, ein leeres Dict würde also lautlos nichts
# buchen — genau der Fehler, der die Produktion bis 2026-08-11 stumm ließ.
# ``None`` heißt „kein Zug gebunden", ist unveränderlich und kann darum auch
# nichts aus dem Standard auslaufen lassen.
_turn_usage: _ctxvars.ContextVar[dict[str, Any] | None] = _ctxvars.ContextVar(
    "_turn_usage", default=None,
)


def bind_turn_usage(acc: dict[str, Any] | None) -> None:
    """Den Merkposten dieses Zuges binden — einmal je Zug im Setup-Knoten.

    Gebunden wird das Objekt aus ``TurnContext.usage``, nicht eine Kopie:
    ``add_usage`` verändert das Dict an Ort und Stelle, also landet jede
    Buchung aus der Tiefe im Zug selbst. ``None`` löst die Bindung.
    """
    _turn_usage.set(acc)


def current_turn_usage() -> dict[str, Any] | None:
    """Der Merkposten des laufenden Zuges, sonst ``None``.

    ``None`` ist der Normalfall außerhalb eines Zuges (Start-Vorwärmung,
    Werkzeug-Aufrufe ohne Zug) und kein Fehler — ``chat_completion`` und
    ``add_usage`` vertragen ihn, es bucht dann schlicht niemand.
    """
    return _turn_usage.get()


def extract_usage(resp: Any) -> dict[str, Any]:
    """Flatten an OpenAI/LiteLLM response's usage into
    {prompt, completion, cached, reasoning, model}. ``cached`` comes from
    ``prompt_tokens_details.cached_tokens`` (prompt cache), ``reasoning`` from
    ``completion_tokens_details.reasoning_tokens``; 0 on any miss.

    Both are "of which" figures, not extras: ``cached`` is contained in
    ``prompt``, ``reasoning`` in ``completion``. Adding them to their parent
    double-counts — the billing side (K3) prices ``completion`` as a whole and
    keeps ``reasoning`` for display only.
    """
    try:
        u = getattr(resp, "usage", None)
        if not u:
            return {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0,
                    "model": getattr(resp, "model", "") or ""}
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        reasoning = 0
        out_details = getattr(u, "completion_tokens_details", None)
        if out_details is not None:
            reasoning = getattr(out_details, "reasoning_tokens", 0) or 0
        return {
            "prompt": getattr(u, "prompt_tokens", 0) or 0,
            "completion": getattr(u, "completion_tokens", 0) or 0,
            "cached": cached,
            "reasoning": reasoning,
            "model": getattr(resp, "model", "") or "",
        }
    except Exception:
        return {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0, "model": ""}


def new_accumulator() -> dict[str, Any]:
    """Empty per-turn accumulator (one per chat turn, threaded through
    LLM-calling helpers). ``per_phase`` splits totals by call-site label
    (classify | tool_loop | response | quick_replies | …).

    The turn's instance comes from ``TurnContext.usage``'s default factory —
    that is the only production caller. Do not give that field a plain ``{}``
    default again: ``add_usage`` returns early on a falsy accumulator, so an
    empty one silently books nothing.
    """
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
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
    reasoning = int(usage.get("reasoning", 0) or 0)
    acc["prompt_tokens"] += p
    acc["completion_tokens"] += c
    acc["cached_tokens"] += cached
    acc["reasoning_tokens"] += reasoning
    acc["calls"] += 1
    model = usage.get("model") or "unknown"
    m = acc["models"].setdefault(
        model, {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0, "calls": 0})
    m["prompt"] += p
    m["completion"] += c
    m["cached"] += cached
    m["reasoning"] += reasoning
    m["calls"] += 1
    if phase:
        ph = acc.setdefault("per_phase", {}).setdefault(
            phase, {"prompt": 0, "completion": 0, "cached": 0, "reasoning": 0, "calls": 0})
        ph["prompt"] += p
        ph["completion"] += c
        ph["cached"] += cached
        ph["reasoning"] += reasoning
        ph["calls"] += 1
