"""Config snapshot + cost estimate for the eval UI — no DB, config reads only.

Everything the start panel needs *before* a run exists: which personas, intents
and gold flows are configured, and what a given matrix would cost. Split out of
``eval_service`` unchanged; the call counting in ``estimate_cost`` is a verbatim
port of ALT ``eval_metrics.estimate_cost``.

**Paket 7 (K7, Nutzer-Entscheid 2026-10-09):** the money no longer comes from
ALT's fixed USD amounts per call. ``bepreise`` prices the counted calls with the
studio's price table (``01-base/pricing``) in the table's own currency — the
editors maintain EUR there, nothing is converted. A model without a maintained
price yields no amount at all, never a guessed one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from boerdi.domain.config_models.pricing import PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for
from boerdi.services.config_loader import (
    load_gold_flows,
    load_intents,
    load_persona_definitions,
    load_pricing,
)
from boerdi.services.eval.scenario_gen import judge_model, simulator_model
from boerdi.services.llm_models import get_chat_model

#: Token-Annahmen je Aufruf, ``(Eingabe, Ausgabe)`` — Schätzwerte, keine Messung.
#: Ein Chat-Zug sind mehrere Modellaufrufe (Klassifikation, Antwort samt
#: Werkzeugrunden, Schnellantworten); Simulator und Bewerter je ein kurzer.
CHAT_ZUG_TOKEN: Final = (12_000, 900)
KLEINER_AUFRUF_TOKEN: Final = (2_500, 300)

#: Das Band um den Erwartungswert, aus ALT übernommen.
_BAND_UNTEN: Final = Decimal("0.6")
_BAND_OBEN: Final = Decimal("2.0")
_STELLEN: Final = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class Modelle:
    """Wer die Aufrufe eines Laufs bedient (seit Paket 7, L4, Vorgabe: das Chat-Modell)."""

    chat: str
    simulator: str
    bewerter: str


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
    """Exact call counts of a generative run (verbatim port of ALT
    ``eval_metrics.estimate_cost``, without its fixed USD amounts — see
    :func:`bepreise`)."""
    combos = n_personas * n_intents
    n_scenarios = combos * scenarios_per_combo if mode in ("scenarios", "both") else 0
    n_convs = combos if mode in ("conversations", "both") else 0
    conv_turns = n_convs * turns_per_conv

    sim_gen_calls = combos if n_scenarios > 0 else 0
    sim_turn_calls = conv_turns
    judge_calls = n_scenarios + conv_turns
    chat_calls = n_scenarios + conv_turns
    return {
        "scenarios": n_scenarios,
        "conversations": n_convs,
        "total_turns": n_scenarios + conv_turns,
        "chat_calls": chat_calls,
        "judge_calls": judge_calls,
        "simulator_calls": sim_gen_calls + sim_turn_calls,
    }


def _betrag(wert: Decimal) -> str:
    """Als Zeichenkette, wie jeder Betrag den Server verlässt (K4)."""
    return str(wert.quantize(_STELLEN))


def bepreise(
    counts: dict[str, Any], table: PricingArea | None, modelle: Modelle,
) -> dict[str, Any]:
    """Die gezählten Aufrufe in der Währung der Preistafel.

    ``est``/``est_min``/``est_max`` sind ``None``, sobald ein aufgerufenes Modell
    keinen gepflegten Preis hat; ``price_missing`` nennt jedes davon einmal.
    """
    posten = (
        (modelle.chat, counts["chat_calls"], CHAT_ZUG_TOKEN),
        (modelle.simulator, counts["simulator_calls"], KLEINER_AUFRUF_TOKEN),
        (modelle.bewerter, counts["judge_calls"], KLEINER_AUFRUF_TOKEN),
    )
    summe = Decimal(0)
    fehlend: set[str] = set()
    for modell, anzahl, (eingabe, ausgabe) in posten:
        if not anzahl:
            continue
        je_aufruf = (cost_for(TokenCounts(model=modell, prompt=eingabe, cached=0,
                                          completion=ausgabe), table)
                     if table is not None else None)
        if je_aufruf is None:
            fehlend.add(modell)
        else:
            summe += je_aufruf * anzahl
    waehrung = table.currency if table is not None else None
    if fehlend or table is None:
        return {"currency": waehrung, "est": None, "est_min": None, "est_max": None,
                "price_missing": sorted(fehlend)}
    return {
        "currency": waehrung,
        "est": _betrag(summe),
        "est_min": _betrag(summe * _BAND_UNTEN),
        "est_max": _betrag(summe * _BAND_OBEN),
        "price_missing": [],
    }


def estimate(
    mode: str, persona_ids: list[str], intent_ids: list[str],
    scenarios_per_combo: int, turns_per_conv: int,
) -> dict[str, Any]:
    """Pre-flight estimate (ALT ``estimate`` endpoint body): counts plus money."""
    cfg = list_personas_and_intents()
    n_p = len(persona_ids) or len(cfg["personas"])
    n_i = len(intent_ids) or len(cfg["intents"])
    counts = estimate_cost(
        n_personas=n_p, n_intents=n_i,
        scenarios_per_combo=scenarios_per_combo,
        mode=mode, turns_per_conv=turns_per_conv,
    )
    modelle = Modelle(chat=get_chat_model(), simulator=simulator_model(),
                      bewerter=judge_model())
    return {**counts, **bepreise(counts, load_pricing(), modelle)}


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
