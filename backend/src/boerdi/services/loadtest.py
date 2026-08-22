"""Loadtest service — Studio scalability self-test (P7, improvement V9).

pg-**REWRITE** of ALT ``app/services/loadtest_service.py``. The query mix, the
hard safety caps, the profile validation and the per-stage measurement are ported
verbatim; **persistence moves from per-run JSON files** (``data/loadtests/<id>``)
**to the ``loadtest_runs`` table** (improvement V9), so runs survive an
ephemeral-filesystem deploy and the Studio polls them through the normal DB. The
dict shapes callers/consumers see stay ALT-identical; the single ALT run dict is
split across the model's two JSONB columns:

* ``config`` = the normalised profile (ALT ``run["profile"]``).
* ``result`` = ``{finished_at, stages, resource_samples, summary, error}`` —
  everything ALT accumulated while the run progressed.

Deviations, each flagged in the progress log:

* ``session: AsyncSession`` is injected into every persistence function (spec
  rule 3/4: no module-global engine; DB access stays in the service layer). The
  background runner has no request scope, so it opens its own session from
  ``app.state.session_factory``.
* ~~Resource sampling is dropped.~~ **Restored 2026-07-31 (C5, on the user's
  decision to take the dependency).** ``psutil`` is a boerdi-chat dependency now
  (BSD-3-Clause, license gate §0 rule 1), and ALT's 0.5 s CPU/RAM sampling plus
  ``peak_rss_mb``/``peak_proc_cpu_pct`` are ported. Until then the Studio
  advertised a feature it could never fill: ``resource_samples`` was always
  ``[]``, and B5 had to word the view around permanently missing peaks.
* The background runner fires the REAL ``/api/chat`` pipeline (LLM + MCP) via
  ``httpx.ASGITransport`` exactly as ALT did — real cost + staging load, so it
  is mocked in the router tests and never exercised offline.
* ``sweep_orphaned_loadtests`` is the startup deadlock-fix (ALT Audit
  2026-07-03) and **is** wired into ``main.py``'s lifespan (``main.py:92-98``),
  which runs it once per process start on its own session — best-effort, so a
  failed sweep never blocks boot.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import psutil
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import LoadtestRun

logger = logging.getLogger(__name__)

# ── Query mix (verbatim ALT) ─────────────────────────────────────────
# Each category exercises a different pipeline path (pattern in brackets).
# Topics rotate so tool-/prompt-caches do not serve every request identically.
_TOPICS = [
    "Photosynthese", "Bruchrechnung", "Klimawandel", "Elektrizität",
    "Mittelalter", "Prozentrechnung", "Zellbiologie", "Französische Revolution",
]

MIX_TEMPLATES: dict[str, dict[str, Any]] = {
    "wissen": {
        "label": "Wissensfrage (M04 — RAG, keine Tools)",
        "prompt": "Was ist {topic}? Erkläre kurz.",
    },
    "suche": {
        "label": "Material-Suche (M05/M06 — MCP-Suche + Reranker)",
        "prompt": "Suche Arbeitsblätter zu {topic}",
    },
    "orientierung": {
        "label": "Orientierung (M15 — leichtester Pfad)",
        "prompt": "Was kannst du eigentlich?",
    },
    "lernpfad": {
        "label": "Lernpfad (M09 — teuerster Pfad: Suche + Generator)",
        "prompt": "Erstelle einen Lernpfad zu {topic}",
    },
}

# Hard safety caps (verbatim ALT — independent of the Studio input).
MAX_STAGES = 6
MAX_CONCURRENCY = 32
MAX_REQUESTS_PER_STAGE = 60
MAX_TOTAL_REQUESTS = 200
REQUEST_TIMEOUT_S = 120


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ── Profile validation + mix expansion (verbatim ALT) ────────────────

def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalise + hard-cap a profile. Raises ``ValueError`` on nonsense."""
    stages = [int(s) for s in (profile.get("stages") or [1, 2, 4])]
    stages = [max(1, min(MAX_CONCURRENCY, s)) for s in stages][:MAX_STAGES]
    if not stages:
        raise ValueError("Mindestens eine Stufe nötig.")

    rps = int(profile.get("requests_per_stage") or 6)
    rps = max(1, min(MAX_REQUESTS_PER_STAGE, rps))

    total = rps * len(stages)
    if total > MAX_TOTAL_REQUESTS:
        raise ValueError(
            f"Profil zu groß: {total} Requests gesamt (Limit {MAX_TOTAL_REQUESTS}). "
            "Stufenzahl oder Requests/Stufe reduzieren."
        )

    raw_mix = profile.get("mix") or {"wissen": 1, "suche": 1, "orientierung": 1}
    mix: dict[str, int] = {}
    for k, v in raw_mix.items():
        if k not in MIX_TEMPLATES:
            raise ValueError(f"Unbekannte Mix-Kategorie: {k!r}")
        w = max(0, min(10, int(v)))
        if w:
            mix[k] = w
    if not mix:
        raise ValueError("Mix darf nicht leer sein (alle Gewichte 0).")

    p95_threshold = float(profile.get("p95_threshold_s") or 20.0)
    p95_threshold = max(1.0, min(120.0, p95_threshold))

    # Review-Befund 7 (2026-08-22): Engine je Lauf. Der Router validiert per
    # Literal; hier noch einmal, weil validate_profile auch die Cap-Schicht
    # für direkte Aufrufer ist.
    engine = str(profile.get("engine") or "default")
    if engine not in ("default", "pattern", "agent", "hybrid"):
        raise ValueError(f"Unbekannte Engine: {engine!r}")

    return {
        "stages": stages,
        "requests_per_stage": rps,
        "mix": mix,
        "p95_threshold_s": p95_threshold,
        "engine": engine,
        "total_requests": total,
    }


def _mix_sequence(mix: dict[str, int], n: int) -> list[str]:
    """Deterministic round-robin expansion of the weights onto n requests."""
    base: list[str] = []
    for key, weight in mix.items():
        base.extend([key] * weight)
    return [base[i % len(base)] for i in range(n)]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    idx = min(len(vs) - 1, max(0, round((pct / 100.0) * (len(vs) - 1))))
    return vs[idx]


# ── loadtest_runs persistence (V9: DB instead of JSON files) ─────────

def _row_to_run(row: LoadtestRun) -> dict[str, Any]:
    """Reconstruct ALT's full run dict from the two JSONB columns."""
    result = row.result or {}
    return {
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": result.get("finished_at"),
        "profile": row.config,
        "stages": result.get("stages", []),
        "resource_samples": result.get("resource_samples", []),
        "summary": result.get("summary"),
        "error": result.get("error"),
    }


async def create_run(session: AsyncSession, run_id: str, profile: dict[str, Any]) -> None:
    """Persist a fresh ``running`` row (the request session; server-set stamp)."""
    session.add(LoadtestRun(id=run_id, status="running", config=profile, result={}))
    await session.commit()


async def load_run(session: AsyncSession, run_id: str) -> dict[str, Any] | None:
    """The full ALT-shaped run dict, or ``None`` if unknown."""
    row = await session.get(LoadtestRun, run_id)
    return _row_to_run(row) if row else None


async def list_runs(session: AsyncSession) -> list[dict[str, Any]]:
    """Compact overview (no stage detail), newest first — ALT ``list_runs`` shape."""
    rows = (
        await session.execute(
            select(LoadtestRun).order_by(LoadtestRun.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": (r.result or {}).get("finished_at"),
            "profile": r.config,
            "summary": (r.result or {}).get("summary"),
            "error": (r.result or {}).get("error"),
        }
        for r in rows
    ]


async def delete_run(session: AsyncSession, run_id: str) -> bool:
    """Delete a run row. Returns ``True`` iff a row was removed."""
    res = await session.execute(delete(LoadtestRun).where(LoadtestRun.id == run_id))
    await session.commit()
    return bool(res.rowcount)


async def any_run_running(session: AsyncSession) -> str | None:
    """Id of a currently-``running`` run (one-run-at-a-time guard), or ``None``."""
    return (
        await session.execute(
            select(LoadtestRun.id).where(LoadtestRun.status == "running").limit(1)
        )
    ).scalars().first()


async def sweep_orphaned_loadtests(session: AsyncSession) -> int:
    """Mark leftover ``running`` rows ``failed`` at startup (ALT deadlock fix).

    A ``running`` row after a process start is orphaned by definition — its
    asyncio task cannot have survived the restart. Without this it blocks every
    new run (``any_run_running`` → 409) and cannot be deleted (delete refuses a
    live run) → permanent deadlock (Audit 2026-07-03). Wired into the app
    lifespan (``main.py``), once per process start, best-effort.
    """
    rows = (
        await session.execute(
            select(LoadtestRun).where(LoadtestRun.status == "running")
        )
    ).scalars().all()
    for row in rows:
        result = dict(row.result or {})
        result["error"] = (
            "verwaister running-Run beim Start abgeräumt "
            "(Backend-Neustart — der Lauf-Task hat ihn nicht überlebt)"
        )
        result.setdefault("finished_at", _now_iso())
        row.status = "failed"
        row.result = result
    await session.commit()
    return len(rows)


async def _persist(
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    *,
    status: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    """Background-runner write: its own short-lived session from the factory."""
    async with factory() as session:
        row = await session.get(LoadtestRun, run_id)
        if row is None:
            return
        if status is not None:
            row.status = status
        if result is not None:
            row.result = dict(result)
        await session.commit()


# ── Live runner (fires the real /api/chat pipeline) ──────────────────

async def _fire_request(
    client: httpx.AsyncClient, kind: str, topic: str, session_id: str,
    *, engine: str = "default",
) -> dict[str, Any]:
    """One real chat request; measures latency and success (verbatim ALT logic).

    ``engine`` (Review-Befund 7): alles außer "default" reist als
    ``X-Boerdi-Engine`` mit — sonst misst der Lasttest immer die
    Server-Vorgabe, und die Kapazitätszahlen sagen nichts über agent/hybrid.
    """
    prompt = MIX_TEMPLATES[kind]["prompt"].format(topic=topic)
    payload = {
        "session_id": session_id,
        "message": prompt,
        # ALT sent ``environment.page_url``; NEU ``Environment`` field is ``page``.
        "environment": {"page": "https://staging.openeduhub.net/"},
    }
    headers = {"X-Boerdi-Engine": engine} if engine != "default" else None
    t0 = time.perf_counter()
    try:
        r = await client.post("/api/chat", json=payload,
                              timeout=REQUEST_TIMEOUT_S, headers=headers)
        dt = time.perf_counter() - t0
        return {"kind": kind, "ok": r.status_code == 200, "status": r.status_code,
                "latency_s": round(dt, 2)}
    except Exception as e:  # network/timeout → count as a failed request, keep going
        dt = time.perf_counter() - t0
        return {"kind": kind, "ok": False, "status": 0,
                "latency_s": round(dt, 2), "error": type(e).__name__}


async def _run_stage(
    app: Any, run_id: str, stage_idx: int, concurrency: int, kinds: list[str],
    *, engine: str = "default",
) -> list[dict[str, Any]]:
    """Fire one stage at the given concurrency. Extracted from the stages loop so
    ``_worker`` closes over parameters, not loop variables (verbatim firing)."""
    sem = asyncio.Semaphore(concurrency)

    async def _worker(i: int, kind: str) -> dict[str, Any]:
        # Own doc-IP (TEST-NET-2) + session per virtual user, so the per-IP rate
        # limit spreads like real visitors and does not skew the measurement.
        ip = f"198.51.100.{(i % 50) + 1}"
        transport = httpx.ASGITransport(app=app, client=(ip, 50000 + i))
        topic = _TOPICS[(stage_idx * 7 + i) % len(_TOPICS)]
        sid = f"loadtest-{run_id[:8]}-s{stage_idx}-{i}"
        async with sem, httpx.AsyncClient(
            transport=transport, base_url="http://loadtest.local",
        ) as client:
            return await _fire_request(client, kind, topic, sid, engine=engine)

    return await asyncio.gather(*[_worker(i, k) for i, k in enumerate(kinds)])


def _stage_stats(
    concurrency: int, requests: int, kinds: list[str],
    results: list[dict[str, Any]], stage_dt: float,
) -> dict[str, Any]:
    """Per-stage latency/error aggregation (verbatim ALT)."""
    lat_ok = [r["latency_s"] for r in results if r["ok"]]
    errors = [r for r in results if not r["ok"]]
    by_kind: dict[str, dict[str, Any]] = {}
    for k in set(kinds):
        ks = [r["latency_s"] for r in results if r["kind"] == k and r["ok"]]
        by_kind[k] = {
            "n": kinds.count(k),
            "ok": len(ks),
            "p50_s": round(_percentile(ks, 50), 2),
            "p95_s": round(_percentile(ks, 95), 2),
        }
    return {
        "concurrency": concurrency,
        "requests": requests,
        "ok": len(lat_ok),
        "errors": len(errors),
        "error_kinds": sorted({r.get("error") or f"HTTP {r['status']}" for r in errors}),
        "p50_s": round(_percentile(lat_ok, 50), 2),
        "p95_s": round(_percentile(lat_ok, 95), 2),
        "max_s": round(max(lat_ok), 2) if lat_ok else 0.0,
        "mean_s": round(statistics.fmean(lat_ok), 2) if lat_ok else 0.0,
        "duration_s": round(stage_dt, 1),
        "rps": round(requests / stage_dt, 2) if stage_dt > 0 else 0.0,
        "by_kind": by_kind,
    }


async def _sample_resources(samples: list[dict[str, Any]], stop: asyncio.Event) -> None:
    """CPU/RAM alle 0,5 s sampeln, bis ``stop`` gesetzt ist (ALT-Port).

    Die erste Iteration misst OHNE Wartezeit — deshalb hat auch ein sehr kurzer
    Lauf mindestens einen Messpunkt. ``cpu_percent(None)`` wird vorher einmal
    „geprimt": der allererste Aufruf liefert sonst 0.0, weil er kein
    Vergleichsintervall hat.

    Messfehler beenden die Abtastung NICHT: ein Lasttest darf nicht daran
    scheitern, dass ein Prozess-Zähler einmal nicht lesbar war.
    """
    proc = psutil.Process()
    proc.cpu_percent(None)
    psutil.cpu_percent(None)
    t0 = time.perf_counter()
    while not stop.is_set():
        try:
            samples.append({
                "t": round(time.perf_counter() - t0, 2),
                "proc_cpu": proc.cpu_percent(None),
                "sys_cpu": psutil.cpu_percent(None),
                "rss_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
            })
        except Exception:
            logger.debug("resource sampling failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.5)
        except TimeoutError:
            continue


def _summary(
    stages: list[dict[str, Any]], threshold: float, samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Highest stage that stayed error-free AND under the p95 threshold, plus
    ALT's two resource peaks.

    ``samples`` ist ein Pflicht-Parameter, kein Default: ein Aufrufer, der die
    Messpunkte vergisst, soll auffallen, statt still ``0.0``-Spitzen zu melden.
    Bei einer leeren Liste sind ``0.0``-Spitzen dagegen richtig und ALT-treu
    (``max(…, default=0.0)``) — der Schlüssel FEHLT nicht, damit die Anzeige
    nicht zwischen „nichts gemessen" und „nicht erhoben" raten muss.
    """
    stable = None
    for st in stages:
        if st["errors"] == 0 and st["p95_s"] <= threshold:
            stable = st["concurrency"]
        else:
            break
    return {
        "stable_concurrency": stable,
        "p95_threshold_s": threshold,
        "peak_rss_mb": max((s["rss_mb"] for s in samples), default=0.0),
        "peak_proc_cpu_pct": max((s["proc_cpu"] for s in samples), default=0.0),
        "total_requests": sum(st["requests"] for st in stages),
        "total_errors": sum(st["errors"] for st in stages),
    }


async def execute_load_test(app: Any, run_id: str, profile: dict[str, Any]) -> None:
    """Background runner — writes progress to ``loadtest_runs`` after each stage.

    Untested offline (fires the real LLM/MCP pipeline); mocked at the router.
    """
    factory: async_sessionmaker[AsyncSession] = app.state.session_factory
    result: dict[str, Any] = {
        "finished_at": None, "stages": [], "resource_samples": [],
        "summary": None, "error": None,
    }
    status = "completed"
    # C5: die Abtastung schreibt DIREKT in ``result["resource_samples"]``, damit
    # jedes ``_persist`` nach einer Stufe den bis dahin gemessenen Verlauf
    # mitnimmt — das Studio pollt während des Laufs und soll die Kurve wachsen
    # sehen, nicht erst am Ende bekommen.
    samples: list[dict[str, Any]] = result["resource_samples"]
    stop_sampling = asyncio.Event()
    sampler = asyncio.create_task(_sample_resources(samples, stop_sampling))
    try:
        # ``.get``: vor Befund 7 gespeicherte Profile tragen kein engine-Feld.
        engine = str(profile.get("engine") or "default")
        for stage_idx, concurrency in enumerate(profile["stages"]):
            n = profile["requests_per_stage"]
            kinds = _mix_sequence(profile["mix"], n)
            stage_t0 = time.perf_counter()
            results = await _run_stage(app, run_id, stage_idx, concurrency, kinds,
                                       engine=engine)
            stage_dt = time.perf_counter() - stage_t0
            result["stages"].append(_stage_stats(concurrency, n, kinds, results, stage_dt))
            await _persist(factory, run_id, result=result)
        result["summary"] = _summary(result["stages"], profile["p95_threshold_s"], samples)
    except Exception as e:  # runner records the failure instead of crashing the task
        logger.exception("loadtest %s failed", run_id)
        result["error"] = f"{type(e).__name__}: {e}"
        status = "failed"
    finally:
        # Vor dem letzten _persist stoppen und abwarten: sonst könnte der Sampler
        # noch während der Serialisierung an die Liste anhängen (RuntimeError
        # „list changed size during iteration"), und ein verwaister Task liefe
        # nach einem Fehlschlag endlos weiter.
        stop_sampling.set()
        try:
            await asyncio.wait_for(sampler, timeout=2)
        except (TimeoutError, asyncio.CancelledError):
            sampler.cancel()
            logger.debug("resource sampler did not stop in time; cancelled")
        result["finished_at"] = _now_iso()
        await _persist(factory, run_id, status=status, result=result)
