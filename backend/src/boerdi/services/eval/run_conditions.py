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
from boerdi.ui_module import schalter

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


def _wirksame_module(ui_module: Sequence[str] | None) -> dict[str, Any] | None:
    """Was von den gemeldeten Modulen wirkte (Review U1-g #7): gemeldet ∩ aktiv nach den
    Studio-Schaltern (``module``), davon die nur für den Agenten abgeschalteten (``agent_aus``).
    Ein abgeschaltetes Modul bietet der Server trotz Meldung nicht an."""
    if ui_module is None:
        return None
    try:
        module = [n for n in ui_module if schalter.aktiv(n)]
        return {"module": module, "agent_aus": [n for n in module if not schalter.fuer_agent(n)]}
    except Exception as fehler:  # Konfiguration nicht lesbar
        logger.warning("Messbedingungen: UI-Modul-Schalter nicht lesbar: %s", fehler)
        return {"fehler": f"{type(fehler).__name__}: {fehler}"[:200]}


def _gold_flows(flows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Prüfsumme und Kennungen der Abläufe; ``eigene_ui_module`` nur, wenn ein Flow im
    ``environment`` eigene Module setzt — die gewinnen über die Laufvorgabe (G-2)."""
    werte: dict[str, Any] = {"hash": fingerprint.gold_flows_hash(flows),
                             "ids": [str(f.get("id") or "") for f in flows]}
    eigene = [str(f.get("id") or "") for f in flows
              if "ui_module" in (f.get("environment") or {})]
    if eigene:
        werte["eigene_ui_module"] = eigene
    return werte


async def run_conditions(
    *, judge_enabled: bool, engine: str = "default",
    flows: Sequence[dict[str, Any]] | None = None,
    ui_module: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Womit dieser Lauf misst — Modelle, Weg, Maschine, Master-Skill-Stand, Deckel.

    ``engine`` ist die Wahl des Laufs (``default`` heißt: die Vorgabe des Servers),
    ``flows`` die ausgewählten Golden-Abläufe. Paket 13 (A2/A3): ``maschine``,
    ``weg``/``judge_weg`` (``llm_weg``), ``app``, ``konfiguration`` und ``gold_flows``
    machen zwei Läufe vergleichbar, die mit verschiedenem Stand liefen. ``ui_module`` (U1-g):
    die Module, die die Züge melden — ``None`` bei einem Lauf, der keine Liste kennt;
    ``ui_module_wirksam`` davon, was die Studio-Schalter durchlassen.
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
        "gold_flows": None if flows is None else _gold_flows(flows),
        "ui_module": None if ui_module is None else list(ui_module),
        "ui_module_wirksam": _wirksame_module(ui_module),
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
