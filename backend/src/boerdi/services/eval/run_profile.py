"""The profile of one eval run in the Studio (ST-7b) — K0-1's arithmetic.

Judge axes, turn duration, tokens and costs were stored with every run, but the
Studio showed none of them and only the measuring tool K0-1 priced a run. The
run detail now carries ``profile``, computed with the same functions K0-1 uses
per engine (``engine_metrics``), priced with the maintained price table.

Computed on read, not stored: older runs get a profile too, and a price the
Studio maintains later applies to every run — as in K0-1's evaluation.

The two helpers below are shared with the measuring tool
(``evals/engine_matrix.py``), which fetches its price table over HTTP from the
backend it measured instead of from the local store.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.domain.config_models import PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for
from boerdi.i18n.bot_text import bot_text
from boerdi.services.config_loader import load_pricing
from boerdi.services.eval import engine_metrics
from boerdi.services.eval.queries import get_run

#: The app's fallback sentences — how an error bubble with HTTP 200 is recognised.
_FALLBACK_KEYS = ("agent.failed", "agent.incomplete", "error.internal")


def fallback_texts() -> list[str]:
    """The fallback sentences up to their first placeholder: the bubble carries
    the substituted value ("(RuntimeError)"), not the template ``({kind})``."""
    heads = (bot_text(lang, key).split("{", 1)[0].rstrip(" (")
             for lang in ("de", "en") for key in _FALLBACK_KEYS)
    return [h for h in heads if len(h) >= 15]


def price_from_table(table: PricingArea | None) -> engine_metrics.PriceFn:
    """A price function over the table; without a readable table every price is
    unknown — never zero, which would read as "this cost nothing"."""
    def price(model: str, prompt: int, cached: int, completion: int) -> float | None:
        if table is None:
            return None
        amount = cost_for(TokenCounts(model=model, prompt=prompt, cached=cached,
                                      completion=completion), table)
        return float(amount) if amount is not None else None

    return price


def run_profile(detail: dict[str, Any]) -> dict[str, Any]:
    """Quality, speed, cost and robustness of one run, plus the currency."""
    table = load_pricing()
    turns = engine_metrics.turns_of(detail)
    return {
        **engine_metrics.profile(turns, price_from_table(table), fallback_texts()),
        "currency": table.currency if table is not None else None,
    }


async def get_run_with_profile(session: AsyncSession, run_id: str) -> dict[str, Any]:
    """``GET /eval/runs/{id}``: the stored run plus its profile."""
    detail = await get_run(session, run_id)
    detail["profile"] = run_profile(detail)
    return detail
