"""What an eval run spends besides the chat turns — simulator, judge, scenarios (Paket 15, A6).

The chat turns of a run book themselves (``eval-<hex>`` sessions). The LLM calls AROUND them
belonged to no session and to no booking: the costs page never showed them. Each role keeps
its own accumulator during the run; at the end every one is booked without a session under
``eval-<rolle>``, which ``session_origin`` counts as evaluation, not production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.obs.usage import new_accumulator
from boerdi.services.session_origin import EVAL_QUELLE_PREFIX
from boerdi.services.usage_store import record_turn_usage


@dataclass
class EvalVerbrauch:
    """One accumulator per role, filled by ``chat_completion(usage_acc=…)``."""

    simulator: dict[str, Any] = field(default_factory=new_accumulator)
    judge: dict[str, Any] = field(default_factory=new_accumulator)
    szenario: dict[str, Any] = field(default_factory=new_accumulator)


async def buche(session: AsyncSession, verbrauch: EvalVerbrauch, *, engine: str | None) -> None:
    """Book every role; an empty accumulator writes nothing (``record_turn_usage``)."""
    for rolle in ("simulator", "judge", "szenario"):
        await record_turn_usage(
            session, None, getattr(verbrauch, rolle), engine=engine,
            quelle=f"{EVAL_QUELLE_PREFIX}{rolle}",
        )
