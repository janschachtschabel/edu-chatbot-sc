"""Messbedingungen eines Gold-Laufs (K0-2, 2026-09-26).

Plan ``docs/plans/2026-09-26-betriebsmodi-und-studio.md`` §5: die
Maschinen werden in Wiederholungen gegeneinander gemessen. Das taugt nur, wenn
jeder Lauf sagt, womit er lief — sonst sind zwei Läufe mit verschiedenem
Master-Skill oder Modell nicht zu unterscheiden, und das Messwerkzeug
(``evals/engine_matrix.py``) vergliche sie trotzdem.

Dazu das frische Messen: ein Lauf beginnt mit leerem MCP-Werkzeug-Cache, wie die
generative Strecke (``runner.execute_run``). Sonst bekäme der zweite Lauf die
Treffer des ersten geschenkt und wäre schneller, ohne besser zu sein.

Weder Bedingungen noch Cache dürfen einen Lauf verhindern: ein Fehler wird
vermerkt bzw. geloggt, der Lauf geht weiter.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services import master_skill
from boerdi.services.config_loader import load_engine
from boerdi.services.eval.scenario_gen import judge_model
from boerdi.services.llm_models import get_chat_model, get_provider

logger = logging.getLogger(__name__)

#: Die Deckel, die einen Agent-Zug begrenzen — ``safety`` fehlt mit Absicht: das
#: Feld hat keine Konsumenten (Plan §2.2) und sagte über den Lauf nichts aus.
_DECKEL = {"max_iterations", "deadline_s", "token_budget", "write_mode"}


async def run_conditions(*, judge_enabled: bool) -> dict[str, Any]:
    """Womit dieser Lauf misst — Modelle, Master-Skill-Stand, Deckel."""
    try:
        skill = await master_skill.anzeige()
    except Exception as fehler:  # Transport, MCP, Programmfehler
        logger.warning("Messbedingungen: Master-Skill nicht lesbar: %s", fehler)
        skill = {"last_error": f"{type(fehler).__name__}: {fehler}"[:200]}
    skill.pop("text", None)  # der Wortlaut gehört ins Studio, nicht in jeden Lauf
    return {
        "provider": get_provider(),
        "chat_model": get_chat_model(),
        "judge_model": judge_model() if judge_enabled else "",
        "master_skill": skill,
        "agent_limits": load_engine().agent.model_dump(include=_DECKEL),
    }


def fresh_tool_cache(run_id: str) -> None:
    """Den MCP-Werkzeug-Cache vor dem ersten Flow leeren."""
    try:
        from boerdi.services.mcp.tool_cache import clear_tool_cache
        geleert = clear_tool_cache()
        if geleert:
            logger.info("[golden %s] cleared tool cache (%d entries)", run_id, geleert)
    except Exception as fehler:
        logger.warning("[golden %s] tool cache clear failed: %s", run_id, fehler)


def tool_cache_stats() -> dict[str, Any]:
    """Treffer und Fehlgriffe des Caches in DIESEM Lauf — ``{}`` im Fehlerfall."""
    try:
        from boerdi.services.mcp.tool_cache import get_tool_cache_stats
        return get_tool_cache_stats()
    except Exception as fehler:
        logger.warning("tool_cache stats fetch failed: %s", fehler)
        return {}
