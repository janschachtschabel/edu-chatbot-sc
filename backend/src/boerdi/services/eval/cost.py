"""Config snapshot + cost estimate for the eval UI — pure, no DB, no I/O.

Everything the start panel needs *before* a run exists: which personas, intents
and gold flows are configured, and what a given matrix would cost. Split out of
``eval_service`` unchanged; ``estimate_cost`` is a verbatim port of ALT
``eval_metrics.estimate_cost``.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader import (
    load_gold_flows,
    load_intents,
    load_persona_definitions,
)


def list_personas_and_intents() -> dict[str, Any]:
    """Current config snapshot for the UI (ALT ``list_personas_and_intents``)."""
    return {
        "personas": load_persona_definitions(),
        "intents": load_intents(),
    }


def estimate_cost(
    n_personas: int, n_intents: int, scenarios_per_combo: int,
    mode: str, turns_per_conv: int,
) -> dict[str, Any]:
    """Rough cost + token estimate (verbatim port of ALT ``eval_metrics.estimate_cost``).

    Best-effort; actuals vary with prompt length, chat verbosity, tool payloads.
    Returns exact call counts plus a min/expected/max USD band.
    """
    combos = n_personas * n_intents
    n_scenarios = combos * scenarios_per_combo if mode in ("scenarios", "both") else 0
    n_convs = combos if mode in ("conversations", "both") else 0
    conv_turns = n_convs * turns_per_conv

    sim_gen_calls = combos if n_scenarios > 0 else 0
    sim_turn_calls = conv_turns
    judge_calls = n_scenarios + conv_turns
    chat_calls = n_scenarios + conv_turns

    mini_per_call = 0.0007
    chat_per_call = 0.005

    expected = (
        (sim_gen_calls + sim_turn_calls + judge_calls) * mini_per_call
        + chat_calls * chat_per_call
    )
    return {
        "scenarios": n_scenarios,
        "conversations": n_convs,
        "total_turns": n_scenarios + conv_turns,
        "chat_calls": chat_calls,
        "judge_calls": judge_calls,
        "simulator_calls": sim_gen_calls + sim_turn_calls,
        "est_usd": round(expected, 3),
        "est_usd_min": round(expected * 0.6, 3),
        "est_usd_max": round(expected * 2.0, 3),
    }


def estimate(
    mode: str, persona_ids: list[str], intent_ids: list[str],
    scenarios_per_combo: int, turns_per_conv: int,
) -> dict[str, Any]:
    """Pre-flight estimate (ALT ``estimate`` endpoint body)."""
    cfg = list_personas_and_intents()
    n_p = len(persona_ids) or len(cfg["personas"])
    n_i = len(intent_ids) or len(cfg["intents"])
    return estimate_cost(
        n_personas=n_p, n_intents=n_i,
        scenarios_per_combo=scenarios_per_combo,
        mode=mode, turns_per_conv=turns_per_conv,
    )


def _compute_target_turns(
    mode: str, n_personas: int, n_intents: int,
    scenarios_per_combo: int, turns_per_conv: int,
) -> int:
    """Max judged turns the run will produce (verbatim ALT port)."""
    combos = n_personas * n_intents
    scen_turns = combos * scenarios_per_combo if mode in ("scenarios", "both") else 0
    conv_turns = combos * turns_per_conv if mode in ("conversations", "both") else 0
    return scen_turns + conv_turns


def list_gold_flows() -> dict[str, Any]:
    """Parsed Gold-Standard flow specs (ALT ``get_gold_flows`` endpoint)."""
    flows = load_gold_flows()
    return {"flows": flows, "count": len(flows)}
