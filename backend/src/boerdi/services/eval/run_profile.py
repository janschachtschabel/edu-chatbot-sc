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

import re
from functools import cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.domain.config_models import PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for
from boerdi.i18n.bot_text import bot_text
from boerdi.services.config_loader import load_pricing
from boerdi.services.eval import auswertung_v2, engine_metrics
from boerdi.services.eval.queries import get_run

#: The app's fallback sentences — how an error bubble with HTTP 200 is recognised.
#: ``error.moderationUnavailable`` (Paket 18A, ``MODERATION_FAILURE_MODE=closed``) refuses the turn
#: politely — no answer either (review 2026-10-30).
_FALLBACK_KEYS = ("agent.failed", "agent.incomplete", "error.internal", "error.answerFailed",
                  "error.llmBusy", "error.moderationUnavailable")
_BUSY_KEYS = ("error.llmBusy",)
#: Where a fallback sentence is looked for — as ``engine_metrics.robustness`` does.
_HEAD_WINDOW = 400


@cache
def _heads(keys: tuple[str, ...]) -> tuple[str, ...]:
    heads = (re.split(r"[.({]", bot_text(lang, key), maxsplit=1)[0].strip()
             for lang in ("de", "en") for key in keys)
    return tuple(h for h in heads if len(h) >= 15)


def fallback_texts() -> list[str]:
    """The first sentence of each fallback text, up to the first ``.``, ``(`` or placeholder:
    the bubble carries the substituted number, not the template. Cut at the first sentence
    rather than at the placeholder so bubbles stored before Paket 18C/D Phase 3 ("…schiefgelaufen
    (RuntimeError).") still count — the profile of an old run is recomputed when it is read."""
    return list(_heads(_FALLBACK_KEYS))


def fallback_kind(text: str) -> str | None:
    """``"ausgelastet"`` for the busy bubble (Paket 18F), ``"ersatzsatz"`` for any other fallback
    sentence, else ``None``. Both arrive with HTTP 200 — the load test counted them as answers
    (review 2026-10-30)."""
    window = (text or "")[:_HEAD_WINDOW]
    if any(h in window for h in _heads(_BUSY_KEYS)):
        return "ausgelastet"
    if any(h in window for h in _heads(_FALLBACK_KEYS)):
        return "ersatzsatz"
    return None


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
    """``GET /eval/runs/{id}``: the stored run plus its profile — and, for golden runs, the
    evaluation of the judge v2 (Paket 13, D1), priced with the same table."""
    detail = await get_run(session, run_id)
    detail["profile"] = run_profile(detail)
    if detail.get("mode") == "golden":
        detail["auswertung"] = auswertung_v2.auswerten(
            detail, price_from_table(load_pricing()))
    return detail
