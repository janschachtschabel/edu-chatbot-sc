"""The golden run: validation, the run row, and the background job.

Split out of ``eval_service`` unchanged. The deterministic half is executed by
the framework-free ``evals/run_golden.py`` (loaded by path, never edited); the
optional soft layer comes from ``eval/golden.py``. This module owns only the
persistence around both.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import EvalRun
from boerdi.obs.tasks import _spawn_background
from boerdi.services.config_loader import load_gold_flows
from boerdi.services.engine_choice import choose_engine
from boerdi.services.eval import golden
from boerdi.services.eval.cancel import RunCancelled
from boerdi.services.eval.run_conditions import (
    fresh_tool_cache,
    run_conditions,
    tool_cache_stats,
)
from boerdi.services.eval.run_store import (
    _chat_url,
    _ensure_chat_reachable,
    _ensure_no_running_run,
    _finalize_run,
    _register_run_task,
)
from boerdi.services.eval.scenario_gen import judge_model

logger = logging.getLogger(__name__)

_runner_mod: Any = None


def _runner_path() -> Path:
    """Wo die framework-freie Runner-DATEI liegt (evals ist kein Paket).

    Im QUELLBAUM liegt sie fünf Ebenen über diesem Modul (parents[5]:
    eval→services→boerdi→src→backend→Repo). Im PROD-IMAGE ist das Paket in
    die venv INSTALLIERT — dieselbe Arithmetik ergab dort
    ``/app/.venv/lib/evals/run_golden.py`` und jeder Gold-Lauf starb sofort
    mit Errno 2 (Prod-Befund 2026-08-22; generative Läufe waren nie
    betroffen, ihr Runner ist ein normales Paket-Modul). Deshalb gewinnt die
    Umgebung: das Dockerfile kopiert die Datei nach ``/app/evals/`` und setzt
    ``EVAL_RUNNER_PATH`` darauf (Wächter in ``test_deploy_compose.py``).
    """
    env = os.getenv("EVAL_RUNNER_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[5] / "evals" / "run_golden.py"


def _load_golden_runner() -> Any:
    """Import the ported golden runner from its file path (evals is not a package).

    Cached after first load. Reused verbatim — never edited (READ-ONLY runner)."""
    global _runner_mod
    if _runner_mod is None:
        runner_path = _runner_path()
        if not runner_path.exists():
            # Ohne diese Prüfung käme ein nackter Errno 2 aus exec_module —
            # der Betreiber erfuhr nicht, an welcher Schraube er drehen kann.
            raise RuntimeError(
                f"Golden-Runner nicht gefunden: {runner_path} — "
                "EVAL_RUNNER_PATH auf evals/run_golden.py zeigen lassen "
                "(im Image: /app/evals/run_golden.py)."
            )
        spec = importlib.util.spec_from_file_location(
            "boerdi_eval_run_golden", runner_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load golden runner from {runner_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _runner_mod = mod
    return _runner_mod


async def start_golden_eval_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession] | None,
    req: Any,
) -> dict[str, Any]:
    """Validate + persist a golden run and spawn its live background job."""
    all_flows = load_gold_flows()
    if not all_flows:
        raise HTTPException(
            400,
            "Keine Gold-Flows konfiguriert (eval/gold-flows.yaml fehlt oder leer).",
        )
    flows = all_flows
    warnings: list[str] = []
    if req.flow_ids:
        requested = set(req.flow_ids)
        known = {str(f.get("id")) for f in all_flows}
        unknown = sorted(requested - known)
        if unknown:
            warnings.append(f"Unbekannte Flow-IDs ignoriert: {unknown}")
        flows = [f for f in all_flows if str(f.get("id")) in requested]
    if not flows:
        raise HTTPException(
            400,
            "Keine Flows matchten den Filter. Verfügbar: "
            f"{sorted({str(f.get('id')) for f in all_flows})}",
        )

    # Vor dem ersten bezahlten Zug: ein vertippter Deckel (``tools_max``) fiele
    # sonst erst mitten im Lauf auf, und der Lauf endete ``failed`` (Review
    # 2026-09-26). Dieselbe Prüfung, die der CLI-Weg in ``load_flows`` macht.
    try:
        _load_golden_runner().validate_flows(flows)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    await _ensure_chat_reachable()
    await _ensure_no_running_run(session)
    run_id = f"eval-{uuid.uuid4().hex[:12]}"
    engine = str(getattr(req, "engine", "") or "default")
    # v2-Flows tragen die Zielgruppe; "persona" bleibt als Rückfall lesbar,
    # solange ein gespeicherter Config-Stand noch v1 sein kann.
    persona_ids = sorted({
        str(f.get("zielgruppe") or f.get("persona") or "*") for f in flows
    })
    intent_ids = sorted({
        iid for f in flows for iid in (f.get("intents") or []) if iid
    })
    turns_total = sum(len(f.get("turns") or []) for f in flows)
    flow_ids_used = [str(f.get("id")) for f in flows]

    session.add(EvalRun(
        id=run_id, status="running", mode="golden",
        config={
            "config_slug": req.config_slug,
            "personas": persona_ids, "intents": intent_ids,
            "flows": flow_ids_used, "judge": bool(req.judge),
            "engine": engine,
            # ST-7a: welche Maschine die Züge bekommen — aufgelöst wie im Chat,
            # damit auch „Server-Vorgabe" sagt, was sie gemessen hat.
            "engine_effective": choose_engine(None if engine == "default" else engine),
            # K0-2: bis dahin hart "" — die Lauf-Details verschwiegen das Modell.
            "turns_per_conv": 0, "simulator_model": "",
            "judge_model": judge_model() if req.judge else "",
        },
        totals={"total_turns": 0, "avg_score": None},
        summary={
            "target_turns": turns_total, "current_activity": "Starte Gold-Flows …",
            "matrix": {}, "pattern_usage": {},
            "avg_score": 0.0, "total_judged_turns": 0,
        },
    ))
    await session.commit()
    task = _spawn_background(
        _execute_golden_run(session_factory, run_id, flows, bool(req.judge),
                            engine=engine)
    )
    _register_run_task(run_id, task)
    return {
        "run_id": run_id,
        "status": "running",
        "mode": "golden",
        "flows_used": flow_ids_used,
        "turns_total": turns_total,
        "judge": bool(req.judge),
        "engine": engine,
        "warnings": warnings,
    }


async def _write_golden_progress(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: str,
    *,
    conversations: list[dict[str, Any]],
    target_turns: int,
    turns_done: int,
    activity: str,
    conditions: dict[str, Any] | None = None,
) -> bool:
    """Zwischenstand eines Gold-Laufs (Feedback 2026-08-22).

    Bis dahin schrieb der Gold-Weg NUR beim Finale — die Lauf-Liste stand
    minutenlang auf „0 von N Turns · Starte Gold-Flows …" und das Detail
    hatte keine Teil-Transkripte. Anders als der generative
    ``_progress_writer`` schreibt dieser die Transkripte IMMER mit: ein
    Gold-Lauf hat höchstens ~40 Züge, und der Zwischenstand kommt nur je
    Flow. Ein verlorener Zwischenstand darf den Lauf nie beenden.

    Gibt zurück, ob der Lauf NOCH LÄUFT (Review-Befund 2026-08-22): der
    In-Prozess-Abbruch erreicht nur den Task dieses Prozesses, deshalb liest
    dieser Prüfpunkt die Zeile mit — kostet keine zusätzliche Abfrage, weil
    er sie ohnehin lädt. Ein FEHLGESCHLAGENER Schreibvorgang meldet ``True``:
    ein Lauf darf nicht abbrechen, nur weil die Datenbank kurz zuckte.
    """
    try:
        async with session_factory() as s:
            r = (
                await s.execute(select(EvalRun).where(EvalRun.id == run_id))
            ).scalar_one_or_none()
            if r is None:
                return False  # Zeile gelöscht — der Lauf hat kein Ziel mehr
            laeuft_noch = r.status == "running"
            r.totals = {**(r.totals or {}), "total_turns": turns_done}
            summary = dict(r.summary or {})
            # Zahlen und Transkripte kommen auch beim letzten Mal noch an — der
            # Flow, der gerade fertig geworden ist, IST gemessen und wäre sonst
            # verloren. Das Schlusswort dagegen gehört dem Abbrecher
            # („Abgebrochen"), sobald der Lauf nicht mehr läuft.
            if laeuft_noch:
                summary["current_activity"] = activity
            summary["target_turns"] = target_turns
            if conditions is not None:  # K0-2: auch ein Teilstand sagt, womit er lief
                summary["messbedingungen"] = conditions
            r.summary = summary
            r.conversations = list(conversations)
            await s.commit()
            return laeuft_noch
    except Exception:
        logger.warning("[golden %s] progress write failed", run_id, exc_info=True)
        return True


async def _execute_golden_run(
    session_factory: async_sessionmaker[AsyncSession] | None,
    run_id: str, flows: list[dict[str, Any]], judge_enabled: bool,
    *, engine: str = "default",
) -> None:
    """Background job: fire the flows at EVAL_CHAT_URL via the ported runner,
    add the optional judge layer, persist to eval_runs.

    The hard scorecard comes from the framework-free runner; ``judge=True`` adds
    the soft axes on top via ``eval/golden.py`` (C3). The headline ``avg_score``
    stays the deterministic pass rate either way.

    ``engine`` (GV5): anything but "default" rides as ``X-Boerdi-Engine`` on
    every turn — until then this job silently measured whatever engine.yaml
    said, and the Studio could not choose.
    """
    if session_factory is None:
        logger.error("[golden %s] no session factory — cannot run", run_id)
        return
    target_turns = sum(len(f.get("turns") or []) for f in flows)
    # Bound outside the try: by the time judging or aggregation can fail, the
    # flows have already cost a full round of real chat turns. Losing that
    # transcript to a judge outage would be the expensive kind of data loss.
    conversations: list[dict[str, Any]] = []
    try:
        runner = _load_golden_runner()
        # K0-2: frisch messen und festhalten, womit gemessen wird.
        fresh_tool_cache(run_id)
        conditions = await run_conditions(judge_enabled=judge_enabled)
        headers = {"X-Boerdi-Engine": engine} if engine != "default" else None
        # Feedback 2026-08-22: Flow für Flow statt EIN Block — nur so gibt es
        # Zwischenstände und Teil-Transkripte. ``run_flows`` öffnet je Flow
        # ohnehin eine frische Session; die Schleife ändert am Messverhalten
        # nichts.
        turns_done = 0
        for i, flow in enumerate(flows, start=1):
            flow_convs = await runner.run_flows(_chat_url(), [flow], headers=headers)
            conversations.extend(flow_convs)
            turns_done = sum(len(c.get("turns") or []) for c in conversations)
            if not await _write_golden_progress(
                session_factory, run_id,
                conversations=conversations, target_turns=target_turns,
                turns_done=turns_done,
                activity=(
                    f"Flow {i}/{len(flows)}: {flow.get('id')} fertig "
                    f"({turns_done}/{target_turns} Züge)"
                ),
                conditions=conditions,
            ):
                raise RunCancelled(f"nach Flow {i}/{len(flows)}")
        if judge_enabled:
            # Auch die Bewertungsphase dauert Minuten — ohne Ansage sähe der
            # Lauf nach dem letzten Flow erneut eingefroren aus. Zugleich der
            # letzte Prüfpunkt vor einer teuren Phase: wer JETZT stoppt, spart
            # sich die Bewertung ganz.
            if not await _write_golden_progress(
                session_factory, run_id,
                conversations=conversations, target_turns=target_turns,
                turns_done=turns_done,
                activity=f"Judge bewertet {turns_done} Züge …",
            ):
                raise RunCancelled("vor der Bewertung")
            judged = await golden.judge_conversations(conversations)
            logger.info("[golden %s] judged %d turn(s)", run_id, judged)
        summary = golden.summarize_golden_run(
            conversations,
            target_turns=target_turns,
            golden_metrics=runner.aggregate_golden(conversations),
        )
        summary["engine"] = engine
        summary["messbedingungen"] = conditions
        summary["tool_cache"] = tool_cache_stats()
        golden_metrics = summary["golden_metrics"]
        async with session_factory() as s:
            await _finalize_run(
                s, run_id, status="done",
                total_turns=golden_metrics["turns"],
                avg_score=golden_metrics["overall_pass_rate"],
                summary=summary, conversations=conversations,
            )
        logger.info(
            "[golden %s] done, pass=%.2f, %d flows / %d turns",
            run_id, golden_metrics["overall_pass_rate"],
            golden_metrics["flows"], golden_metrics["turns"],
        )
    except RunCancelled as e:
        # Kein Fehlerfall: die Zeile trägt ihren Endstand bereits (``cancelled``)
        # oder ist gelöscht. Der letzte Prüfpunkt hat die Teil-Transkripte
        # geschrieben — daraus ein „failed" zu machen, wäre eine Lüge über
        # alles, was bis dahin sauber gemessen wurde.
        logger.info("[golden %s] gestoppt (%s) — Teilstand bleibt stehen", run_id, e)
    except Exception as e:
        logger.exception("[golden %s] failed", run_id)
        try:
            async with session_factory() as s:
                await _finalize_run(
                    s, run_id, status="failed",
                    error_message=str(e)[:500],
                    current_activity=f"Fehler: {str(e)[:200]}",
                    conversations=conversations,
                )
        except Exception:
            logger.exception("[golden %s] failed to persist failure", run_id)
