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
from collections.abc import Sequence
from typing import Any

from boerdi.services import config_loader as cl
from boerdi.services import master_skill, seed_sync
from boerdi.services.config_loader import load_engine
from boerdi.services.engine_choice import choose_engine
from boerdi.services.eval import fingerprint
from boerdi.services.eval.scenario_gen import judge_model
from boerdi.services.llm_models import get_chat_model, get_provider
from boerdi.services.llm_weg import weg_beschreibung
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Die Deckel, die einen Agent-Zug begrenzen — ``safety`` fehlt mit Absicht: das
#: Feld hat keine Konsumenten (Plan §2.2) und sagte über den Lauf nichts aus.
_DECKEL = {"max_iterations", "deadline_s", "token_budget", "write_mode"}


async def _werk() -> dict[str, dict[str, Any]] | None:
    """Die Werksfassung (Seed) — ``None`` ohne Seed-Baum."""
    pfad = seed_sync.seed_pfad(get_settings().config_seed_dir)
    return None if pfad is None else await seed_sync.seed_lesen(pfad)


async def _konfiguration() -> dict[str, Any]:
    """Fingerabdruck der gelebten Konfiguration; ein Fehler wird vermerkt, nicht geworfen."""
    try:
        zeilen = await cl.bound_store().fassungen()
        return fingerprint.konfig_fingerprint(zeilen, werk=await _werk())
    except Exception as fehler:  # Store nicht gebunden, Datenbank, Seed unlesbar
        logger.warning("Messbedingungen: Konfiguration nicht lesbar: %s", fehler)
        return {"fehler": f"{type(fehler).__name__}: {fehler}"[:200]}


async def run_conditions(
    *, judge_enabled: bool, engine: str = "default",
    flows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Womit dieser Lauf misst — Modelle, Weg, Maschine, Master-Skill-Stand, Deckel.

    ``engine`` ist die Wahl des Laufs (``default`` heißt: die Vorgabe des Servers),
    ``flows`` die ausgewählten Golden-Abläufe. Paket 13 (A2/A3): ``maschine``,
    ``weg``/``judge_weg`` (``llm_weg``), ``app``, ``konfiguration`` und ``gold_flows``
    machen zwei Läufe vergleichbar, die mit verschiedenem Stand liefen.
    """
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
        "maschine": choose_engine(None if engine == "default" else engine),
        "weg": weg_beschreibung(),
        "judge_weg": weg_beschreibung(judge_model()) if judge_enabled else None,
        "app": {"version": get_settings().boerdi_version, "commit": get_settings().git_sha},
        "konfiguration": await _konfiguration(),
        "gold_flows": None if flows is None else {
            "hash": fingerprint.gold_flows_hash(flows),
            "ids": [str(f.get("id") or "") for f in flows],
        },
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
