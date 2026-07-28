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
* **Resource sampling is dropped.** ALT sampled process CPU/RAM via ``psutil``
  every 0.5 s and reported ``peak_rss_mb``/``peak_proc_cpu_pct``. ``psutil`` is
  not a boerdi-chat dependency and ``pyproject.toml`` is out of this slice's
  scope, so ``resource_samples`` stays ``[]`` and the summary omits the peaks.
* The background runner fires the REAL ``/api/chat`` pipeline (LLM + MCP) via
  ``httpx.ASGITransport`` exactly as ALT did — real cost + staging load, so it
  is mocked in the router tests and never exercised offline.
* ``sweep_orphaned_loadtests`` is provided for the startup deadlock-fix (ALT
  Audit 2026-07-03) but is NOT wired into ``main.py``'s lifespan (shared file,
  out of scope) — flagged for the user.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import time
from datetime import UTC, datetime
from typing import Any

import httpx
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

    return {
        "stages": stages,
        "requests_per_stage": rps,
        "mix": mix,
        "p95_threshold_s": p95_threshold,
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
    live run) → permanent deadlock (Audit 2026-07-03). NOT wired into the app
    lifespan here (``main.py`` is out of scope) — flagged for the user.
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
) -> dict[str, Any]:
    """One real chat request; measures latency and success (verbatim ALT logic)."""
    prompt = MIX_TEMPLATES[kind]["prompt"].format(topic=topic)
    payload = {
        "session_id": session_id,
        "message": prompt,
        # ALT sent ``environment.page_url``; NEU ``Environment`` field is ``page``.
        "environment": {"page": "https://staging.openeduhub.net/"},
    }
    t0 = time.perf_counter()
    try:
        r = await client.post("/api/chat", json=payload, timeout=REQUEST_TIMEOUT_S)
        dt = time.perf_counter() - t0
        return {"kind": kind, "ok": r.status_code == 200, "status": r.status_code,
                "latency_s": round(dt, 2)}
    except Exception as e:  # network/timeout → count as a failed request, keep going
        dt = time.perf_counter() - t0
        return {"kind": kind, "ok": False, "status": 0,
                "latency_s": round(dt, 2), "error": type(e).__name__}


async def _run_stage(
    app: Any, run_id: str, stage_idx: int, concurrency: int, kinds: list[str],
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
            return await _fire_request(client, kind, topic, sid)

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


def _summary(stages: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Highest stage that stayed error-free AND under the p95 threshold.

    ALT's ``peak_rss_mb``/``peak_proc_cpu_pct`` are dropped (no psutil sampling).
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
    try:
        for stage_idx, concurrency in enumerate(profile["stages"]):
            n = profile["requests_per_stage"]
            kinds = _mix_sequence(profile["mix"], n)
            stage_t0 = time.perf_counter()
            results = await _run_stage(app, run_id, stage_idx, concurrency, kinds)
            stage_dt = time.perf_counter() - stage_t0
            result["stages"].append(_stage_stats(concurrency, n, kinds, results, stage_dt))
            await _persist(factory, run_id, result=result)
        result["summary"] = _summary(result["stages"], profile["p95_threshold_s"])
    except Exception as e:  # runner records the failure instead of crashing the task
        logger.exception("loadtest %s failed", run_id)
        result["error"] = f"{type(e).__name__}: {e}"
        status = "failed"
    finally:
        result["finished_at"] = _now_iso()
        await _persist(factory, run_id, status=status, result=result)
