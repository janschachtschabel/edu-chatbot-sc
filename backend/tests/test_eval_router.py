"""P7: eval router (generative + golden + read/analytics) — offline.

Two layers, both without Postgres:

* **Router wiring** — TestClient WITHOUT ``with`` (no lifespan → no DB),
  ``get_session`` overridden with a sentinel, every service fn faked at the
  router boundary (``boerdi.api.eval.<name>``). Pins the HTTP contract: DI session
  reaches the service, response passes through, auth is enforced, request/query
  models validate.
* **Service logic** — the pure + orchestration bits (estimate math, start-run
  validation/warnings, the golden runner wiring, the generative "not ported"
  fail) exercised directly with config/runner/finalize faked and a fake session.
  DB semantics themselves are pinned in the pg-gated test_eval_pg.py.

The eval runner is NEVER executed for real (no LLM keys): the golden runner and
``_finalize_run`` are always faked.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import boerdi.api.eval as eval_api
import boerdi.services.eval.cost as eval_cost
import boerdi.services.eval.generative_run as generative_run
import boerdi.services.eval.golden as eval_golden
import boerdi.services.eval.golden_run as golden_run
import boerdi.services.eval_service as svc
from boerdi.api.deps import get_session
from boerdi.api.eval import GoldenRunRequest, StartRequest
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _fake_async(monkeypatch, name, result=None):
    calls: list[tuple] = []

    async def fake(*args, **kwargs):
        calls.append(args)
        return result

    monkeypatch.setattr(eval_api, name, fake)
    return calls


def _fake_sync(monkeypatch, name, result=None):
    calls: list[tuple] = []

    def fake(*args, **kwargs):
        calls.append(args)
        return result

    monkeypatch.setattr(eval_api, name, fake)
    return calls


# ── router wiring ────────────────────────────────────────────────────────


def test_config_returns_service_snapshot(client, monkeypatch):
    _fake_sync(monkeypatch, "list_personas_and_intents",
               {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]})
    r = client.get("/api/eval/config", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]}


def test_estimate_passes_parsed_fields_to_service(client, monkeypatch):
    calls = _fake_sync(monkeypatch, "estimate", {"est_usd": 1.23})
    r = client.post("/api/eval/estimate",
                    json={"mode": "scenarios", "persona_ids": ["P-AND"],
                          "scenarios_per_combo": 4},
                    headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"est_usd": 1.23}
    # (mode, persona_ids, intent_ids, scenarios_per_combo, turns_per_conv)
    assert calls == [("scenarios", ["P-AND"], [], 4, 3)]


def test_list_runs_passes_di_session_and_default_limit(client, monkeypatch):
    calls = _fake_async(monkeypatch, "list_runs", {"runs": []})
    r = client.get("/api/eval/runs", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"runs": []}
    assert calls == [(_SESSION, 50)]


def test_start_run_passes_session_factory_and_body(client, monkeypatch):
    calls = _fake_async(monkeypatch, "start_generative_run",
                        {"run_id": "eval-1", "status": "running"})
    r = client.post("/api/eval/runs", json={"mode": "both"}, headers=_AUTH)
    assert r.status_code == 200 and r.json()["run_id"] == "eval-1"
    (session, factory, req), = calls
    assert session is _SESSION
    assert factory is None  # no lifespan → app.state has no session_factory
    assert isinstance(req, StartRequest) and req.mode == "both"


def test_delete_runs_passes_status_mode_confirm(client, monkeypatch):
    calls = _fake_async(monkeypatch, "delete_runs",
                        {"deleted": 2, "filter": {"status": "failed", "mode": "golden"}})
    r = client.request("DELETE", "/api/eval/runs",
                       params={"status": "failed", "mode": "golden", "confirm": "true"},
                       headers=_AUTH)
    assert r.status_code == 200
    assert calls == [(_SESSION, "failed", "golden", True)]


def test_start_golden_run_passes_session_factory_and_body(client, monkeypatch):
    calls = _fake_async(monkeypatch, "start_golden_eval_run",
                        {"run_id": "eval-g", "status": "running", "mode": "golden"})
    r = client.post("/api/eval/runs/golden",
                    json={"flow_ids": ["GS-1"], "judge": False}, headers=_AUTH)
    assert r.status_code == 200 and r.json()["mode"] == "golden"
    (session, factory, req), = calls
    assert session is _SESSION and factory is None
    assert isinstance(req, GoldenRunRequest)
    assert req.flow_ids == ["GS-1"] and req.judge is False


def test_get_run_passes_run_id(client, monkeypatch):
    calls = _fake_async(monkeypatch, "get_run", {"id": "eval-1", "status": "done"})
    r = client.get("/api/eval/runs/eval-1", headers=_AUTH)
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert calls == [(_SESSION, "eval-1")]


def test_delete_run_passes_run_id(client, monkeypatch):
    calls = _fake_async(monkeypatch, "delete_run", {"deleted": "eval-1"})
    r = client.delete("/api/eval/runs/eval-1", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"deleted": "eval-1"}
    assert calls == [(_SESSION, "eval-1")]


def test_trends_passes_di_session_and_default_limit(client, monkeypatch):
    calls = _fake_async(monkeypatch, "get_trends", {"runs": []})
    r = client.get("/api/eval/trends", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"runs": []}
    assert calls == [(_SESSION, 10)]


def test_gold_flows_returns_service_payload(client, monkeypatch):
    _fake_sync(monkeypatch, "list_gold_flows", {"flows": [{"id": "GS-1"}], "count": 1})
    r = client.get("/api/eval/gold-flows", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"flows": [{"id": "GS-1"}], "count": 1}


def test_quality_logs_delete_passes_di_session(client, monkeypatch):
    calls = _fake_async(monkeypatch, "clear_eval_quality_logs",
                        {"deleted_eval_log_rows": 7})
    r = client.delete("/api/eval/quality-logs", headers=_AUTH)
    assert r.status_code == 200 and r.json() == {"deleted_eval_log_rows": 7}
    assert calls == [(_SESSION,)]


def test_pattern_usage_passes_since_and_scope(client, monkeypatch):
    calls = _fake_async(monkeypatch, "pattern_usage_stats", {"triples": [], "total": 0})
    r = client.get("/api/eval/analytics/pattern-usage",
                   params={"since": "2026-07-01T00:00:00+00:00", "scope": "eval"},
                   headers=_AUTH)
    assert r.status_code == 200
    assert calls == [(_SESSION, "2026-07-01T00:00:00+00:00", "eval")]


def test_pattern_usage_scope_defaults_to_all(client, monkeypatch):
    calls = _fake_async(monkeypatch, "pattern_usage_stats", {"triples": []})
    client.get("/api/eval/analytics/pattern-usage", headers=_AUTH)
    assert calls == [(_SESSION, None, "all")]


# ── request/query validation ─────────────────────────────────────────────


def test_estimate_rejects_bad_mode(client):
    r = client.post("/api/eval/estimate", json={"mode": "bogus"}, headers=_AUTH)
    assert r.status_code == 422


def test_estimate_rejects_out_of_range_scenarios(client):
    r = client.post("/api/eval/estimate",
                    json={"scenarios_per_combo": 99}, headers=_AUTH)
    assert r.status_code == 422


def test_list_runs_limit_bounds(client, monkeypatch):
    _fake_async(monkeypatch, "list_runs", {"runs": []})
    assert client.get("/api/eval/runs", params={"limit": 0}, headers=_AUTH).status_code == 422
    assert client.get("/api/eval/runs", params={"limit": 999}, headers=_AUTH).status_code == 422


def test_trends_limit_lower_bound(client, monkeypatch):
    _fake_async(monkeypatch, "get_trends", {"runs": []})
    assert client.get("/api/eval/trends", params={"limit": 1}, headers=_AUTH).status_code == 422


# ── auth ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/eval/config", None),
        ("POST", "/api/eval/estimate", {}),
        ("GET", "/api/eval/runs", None),
        ("POST", "/api/eval/runs", {}),
        ("DELETE", "/api/eval/runs", None),
        ("POST", "/api/eval/runs/golden", {}),
        ("GET", "/api/eval/runs/eval-1", None),
        ("DELETE", "/api/eval/runs/eval-1", None),
        ("GET", "/api/eval/trends", None),
        ("GET", "/api/eval/gold-flows", None),
        ("DELETE", "/api/eval/quality-logs", None),
        ("GET", "/api/eval/analytics/pattern-usage", None),
    ],
)
def test_endpoints_require_studio_key(client, method, path, body):
    # STUDIO_API_KEY is configured (fixture) → a request without the header is 401.
    r = client.request(method, path, json=body)
    assert r.status_code == 401


# ── service: estimate math ────────────────────────────────────────────────


def test_service_estimate_both_mode_counts(monkeypatch):
    monkeypatch.setattr(eval_cost, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "a"}, {"id": "b"}],
                                 "intents": [{"id": "x"}]})
    out = svc.estimate("both", [], [], 2, 3)
    # combos=2; scenarios=2*2=4; convs=2; conv_turns=6; total=10
    assert out["scenarios"] == 4
    assert out["conversations"] == 2
    assert out["total_turns"] == 10
    assert out["chat_calls"] == 10
    assert out["judge_calls"] == 10
    assert out["simulator_calls"] == 8  # sim_gen=2 + sim_turn=6
    assert out["est_usd_min"] < out["est_usd"] < out["est_usd_max"]


def test_service_estimate_explicit_ids_override_config(monkeypatch):
    monkeypatch.setattr(eval_cost, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "a"}], "intents": [{"id": "x"}]})
    out = svc.estimate("scenarios", ["p1", "p2", "p3"], ["i1", "i2"], 1, 3)
    # n_p=3, n_i=2 → combos=6; scenarios=6; convs=0 (scenarios mode)
    assert out["scenarios"] == 6
    assert out["conversations"] == 0
    assert out["total_turns"] == 6


# ── service: fake session + no-op guard/spawn helpers ─────────────────────


class _FakeSession:
    def __init__(self):
        self.added: list = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeCtx:
    async def __aenter__(self):
        return "S"

    async def __aexit__(self, *exc):
        return False


def _patch_guard_and_spawn(monkeypatch, mod):
    """Patch guard + spawn in ``mod`` — the module owning the start function under
    test (``generative_run`` or ``golden_run``). Both resolve these names in their
    own globals, so the patch has to land where the caller lives, not on the
    ``eval_service`` facade that merely re-exports them."""
    spawned: list = []

    async def no_running(_session):
        return None

    def spawn(coro):
        spawned.append(coro)
        coro.close()  # we never run it; close to avoid "never awaited" warnings

    monkeypatch.setattr(mod, "_ensure_no_running_run", no_running)
    monkeypatch.setattr(mod, "_spawn_background", spawn)
    return spawned


# ── service: generative start (validation faithful, execution not ported) ──


def test_start_generative_run_happy_path(monkeypatch):
    monkeypatch.setattr(generative_run, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "P-AND"}, {"id": "P-LEH"}],
                                 "intents": [{"id": "I01"}, {"id": "I03"}]})
    spawned = _patch_guard_and_spawn(monkeypatch, generative_run)
    session = _FakeSession()
    req = StartRequest(mode="both", persona_ids=["P-AND"], intent_ids=["I03"])
    out = asyncio.run(svc.start_generative_run(session, None, req))
    assert out["status"] == "running"
    assert out["run_id"].startswith("eval-")
    assert out["personas_used"] == ["P-AND"]
    assert out["intents_used"] == ["I03"]
    assert out["warnings"] == []
    # a running generative row was persisted + a background job spawned
    assert len(session.added) == 1 and session.commits == 1
    row = session.added[0]
    assert row.mode == "generative" and row.status == "running"
    assert row.config["personas"] == ["P-AND"] and row.config["intents"] == ["I03"]
    assert len(spawned) == 1


def test_start_generative_run_warns_on_unknown_ids(monkeypatch):
    monkeypatch.setattr(generative_run, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]})
    _patch_guard_and_spawn(monkeypatch, generative_run)
    req = StartRequest(persona_ids=["P-AND", "P-XXX"], intent_ids=["I01"])
    out = asyncio.run(svc.start_generative_run(_FakeSession(), None, req))
    assert out["personas_used"] == ["P-AND"]
    assert out["warnings"] == ["Unknown persona IDs ignored: ['P-XXX']"]


def test_start_generative_run_400_when_filter_matches_nothing(monkeypatch):
    monkeypatch.setattr(generative_run, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]})
    _patch_guard_and_spawn(monkeypatch, generative_run)
    req = StartRequest(persona_ids=["P-NONE"])
    with pytest.raises(HTTPException) as ei:
        asyncio.run(svc.start_generative_run(_FakeSession(), None, req))
    assert ei.value.status_code == 400


def _run_generative(monkeypatch, factory, **over):
    """Drive the background job with the engine faked at the service boundary."""
    captured: dict = {}

    async def fake_finalize(session, run_id, **kw):
        captured["run_id"] = run_id
        captured.update(kw)

    monkeypatch.setattr(generative_run, "_finalize_run", fake_finalize)
    kwargs = dict(
        mode="scenarios", personas=[{"id": "P-AND"}], intents=[{"id": "I01"}],
        scenarios_per_combo=1, turns_per_conv=3, target_turns=1,
    )
    kwargs.update(over)
    asyncio.run(svc._execute_generative_run(factory, "eval-9", **kwargs))
    return captured


def test_execute_generative_run_persists_the_engine_result(monkeypatch):
    async def fake_execute(*, conversations, **kw):
        conversations.append({"kind": "scenario", "turns": []})
        return {"total_judged_turns": 4, "avg_score": 0.75,
                "classification_metrics": {"persona_correct_rate": 0.5}}

    monkeypatch.setattr(generative_run.runner, "execute_run", fake_execute)
    captured = _run_generative(monkeypatch, lambda: _FakeCtx())
    assert captured["status"] == "done"
    assert captured["total_turns"] == 4
    assert captured["avg_score"] == 0.75
    # The key GET /eval/trends reads must reach the row.
    assert "classification_metrics" in captured["summary"]
    assert len(captured["conversations"]) == 1


def test_execute_generative_run_keeps_partial_conversations_on_failure(monkeypatch):
    """A run that dies after 100 of 144 combos is still worth reading."""
    async def fake_execute(*, conversations, **kw):
        conversations.append({"kind": "scenario", "persona_id": "P-AND",
                              "intent_id": "I01", "turns": []})
        raise RuntimeError("provider weg")

    monkeypatch.setattr(generative_run.runner, "execute_run", fake_execute)
    captured = _run_generative(monkeypatch, lambda: _FakeCtx())
    assert captured["status"] == "failed"
    assert captured["error_message"] == "provider weg"
    assert len(captured["conversations"]) == 1
    assert "provider weg" in captured["summary"]["current_activity"]


def test_execute_generative_run_without_factory_is_noop(monkeypatch):
    called: list = []

    async def fake_execute(**kw):
        called.append(1)

    monkeypatch.setattr(generative_run.runner, "execute_run", fake_execute)
    captured = _run_generative(monkeypatch, None)
    assert called == [] and captured == {}


def test_progress_writer_throttles_the_transcript(monkeypatch):
    """Summary on every write, transcript only every 5th — ALT's ratio.

    ALT tracked this counter in a module-global dict keyed by run id; here it is
    closure state, so two runs in one process cannot share a counter.
    """
    rows: list[dict] = []

    class Row:
        def __init__(self):
            self.totals, self.summary, self.conversations = {}, {}, None

    row = Row()

    class Ctx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a):
            class R:
                def scalar_one_or_none(self_inner):
                    return row
            return R()

        async def commit(self):
            rows.append({"conversations": row.conversations,
                         "activity": row.summary.get("current_activity")})

    monkeypatch.setattr(
        generative_run.runner, "build_summary",
        lambda conv, target, activity: {
            "total_judged_turns": len(conv), "avg_score": 0.5,
            "current_activity": activity, "target_turns": target,
        },
    )
    progress = svc._progress_writer(lambda: Ctx(), "eval-9", 10)
    for i in range(5):
        asyncio.run(progress([{"turns": []}], f"Schritt {i}"))

    assert [r["activity"] for r in rows] == [f"Schritt {i}" for i in range(5)]
    # Writes 1-4 leave the transcript untouched; the 5th stores it.
    assert [r["conversations"] is None for r in rows] == [
        True, True, True, True, False,
    ]


def test_progress_write_failure_does_not_kill_the_run(monkeypatch):
    class Boom:
        async def __aenter__(self):
            raise RuntimeError("db weg")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(
        generative_run.runner, "build_summary",
        lambda conv, target, activity: {"total_judged_turns": 0, "avg_score": 0.0},
    )
    progress = svc._progress_writer(lambda: Boom(), "eval-9", 10)
    asyncio.run(progress([], "Schritt"))  # must not raise


# ── service: golden start + LIVE runner wiring ────────────────────────────


def _golden_flows():
    return [
        {"id": "GS-1", "persona": "P-LEH", "intents": ["I03"],
         "turns": [{"message": "hallo"}, {"message": "mehr"}]},
        {"id": "GS-2", "persona": "P-AND", "intents": ["I01"],
         "turns": [{"message": "hi"}]},
    ]


def test_start_golden_run_happy_path(monkeypatch):
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    spawned = _patch_guard_and_spawn(monkeypatch, golden_run)
    session = _FakeSession()
    out = asyncio.run(svc.start_golden_eval_run(session, None,
                                                GoldenRunRequest(judge=True)))
    assert out["status"] == "running" and out["mode"] == "golden"
    assert out["flows_used"] == ["GS-1", "GS-2"]
    assert out["turns_total"] == 3  # 2 + 1 turns
    assert out["judge"] is True and out["warnings"] == []
    row = session.added[0]
    assert row.mode == "golden" and row.status == "running"
    assert row.config["flows"] == ["GS-1", "GS-2"]
    assert row.config["personas"] == ["P-AND", "P-LEH"]  # sorted
    assert len(spawned) == 1


def test_start_golden_run_filters_and_warns(monkeypatch):
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    _patch_guard_and_spawn(monkeypatch, golden_run)
    out = asyncio.run(svc.start_golden_eval_run(
        _FakeSession(), None, GoldenRunRequest(flow_ids=["GS-2", "GS-99"])))
    assert out["flows_used"] == ["GS-2"]
    assert out["warnings"] == ["Unbekannte Flow-IDs ignoriert: ['GS-99']"]
    assert out["turns_total"] == 1


def test_start_golden_run_400_when_no_flows_configured(monkeypatch):
    monkeypatch.setattr(golden_run, "load_gold_flows", lambda: [])
    _patch_guard_and_spawn(monkeypatch, golden_run)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(svc.start_golden_eval_run(_FakeSession(), None, GoldenRunRequest()))
    assert ei.value.status_code == 400


def test_start_golden_run_400_when_filter_matches_nothing(monkeypatch):
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    _patch_guard_and_spawn(monkeypatch, golden_run)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(svc.start_golden_eval_run(
            _FakeSession(), None, GoldenRunRequest(flow_ids=["GS-nope"])))
    assert ei.value.status_code == 400


def _golden_convs():
    return [{"kind": "golden", "flow_id": "GS-1", "persona_id": "P-SYN",
             "intent_id": "I-SYN", "turns": [
                 {"user": "hallo", "bot": "antwort", "debug": {"pattern": "M-SYN (z)"},
                  "expected_persona": "P-SYN", "expected_intent": "I-SYN",
                  "golden": {"checks": {}}},
             ]}]


def _wire_golden(monkeypatch, *, judge=None):
    """Patch the golden run's four seams and return (runner, captured summary)."""
    convs = _golden_convs()
    metrics = {"overall_pass_rate": 0.9, "turns": 3, "flows": 2}

    class FakeRunner:
        def __init__(self):
            self.url = None
            self.flows = None

        async def run_flows(self, url, f):
            self.url, self.flows = url, f
            return convs

        def aggregate_golden(self, c):
            assert c is convs
            return metrics

    fake_runner = FakeRunner()
    monkeypatch.setattr(golden_run, "_load_golden_runner", lambda: fake_runner)
    monkeypatch.setattr(eval_golden, "load_persona_definitions",
                        lambda: [{"id": "P-SYN", "label": "Synth", "description": ""}])
    monkeypatch.setattr(eval_golden, "load_intents",
                        lambda: [{"id": "I-SYN", "label": "Synth", "description": ""}])
    if judge is not None:
        monkeypatch.setattr(eval_golden, "judge_turn", judge)

    captured: dict = {}

    async def fake_finalize(session, run_id, **kw):
        captured["run_id"] = run_id
        captured.update(kw)

    monkeypatch.setattr(golden_run, "_finalize_run", fake_finalize)
    return fake_runner, convs, metrics, captured


def test_execute_golden_run_uses_ported_runner_and_persists_done(monkeypatch):
    flows = _golden_flows()
    judge_calls: list[tuple] = []

    async def fake_judge(persona, intent, user, bot, dbg):
        judge_calls.append((persona["id"], intent["id"], user))
        return {"total": 0.5, "notes": ""}

    fake_runner, convs, metrics, captured = _wire_golden(monkeypatch, judge=fake_judge)
    monkeypatch.setenv("EVAL_CHAT_URL", "http://backend:8100/api/chat")

    asyncio.run(svc._execute_golden_run(lambda: _FakeCtx(), "eval-g", flows, True))

    assert fake_runner.url == "http://backend:8100/api/chat"
    assert fake_runner.flows is flows
    assert captured["status"] == "done"
    assert captured["total_turns"] == 3
    assert captured["conversations"] is convs
    # The judge ran for real (C3) — it used to be a "not ported" note.
    assert judge_calls == [("P-SYN", "I-SYN", "hallo")]
    assert convs[0]["turns"][0]["judge"]["total"] == 0.5
    assert captured["summary"]["judge_avg"] == 0.5
    # …and the headline stayed the deterministic hard pass rate.
    assert captured["avg_score"] == 0.9
    assert captured["summary"]["avg_score"] == 0.9
    assert captured["summary"]["golden_metrics"] is metrics
    assert metrics["judge_avg"] == 0.5 and metrics["judged_turns"] == 1
    # Gold runs feed the trend series too — the source is written here.
    assert "classification_metrics" in captured["summary"]


def test_execute_golden_run_keeps_the_transcript_when_judging_fails(monkeypatch):
    """The flows have already cost ~40 real chat turns by the time the judge
    runs. A judge outage must not throw that away."""
    _, convs, _, captured = _wire_golden(monkeypatch)

    async def boom(_conversations):
        raise RuntimeError("judge model not deployed")

    monkeypatch.setattr(eval_golden, "judge_conversations", boom)
    asyncio.run(svc._execute_golden_run(
        lambda: _FakeCtx(), "eval-g", _golden_flows(), True))

    assert captured["status"] == "failed"
    assert "judge model not deployed" in captured["error_message"]
    assert captured["conversations"] is convs


def test_execute_golden_run_without_judge_calls_no_llm(monkeypatch):
    async def forbidden_judge(*a, **k):  # pragma: no cover - must not run
        raise AssertionError("judge must not be called when judge=False")

    _, convs, metrics, captured = _wire_golden(monkeypatch, judge=forbidden_judge)

    asyncio.run(svc._execute_golden_run(
        lambda: _FakeCtx(), "eval-g", _golden_flows(), False))

    assert captured["status"] == "done"
    assert "judge" not in convs[0]["turns"][0]
    assert "judge_avg" not in captured["summary"] and "judge_avg" not in metrics
    assert captured["summary"]["avg_score"] == 0.9  # unchanged headline


def test_execute_golden_run_persists_failure_on_runner_error(monkeypatch):
    def boom():
        raise RuntimeError("chat backend down")

    class FakeRunner:
        async def run_flows(self, url, f):
            boom()

        def aggregate_golden(self, c):  # pragma: no cover - not reached
            return {}

    monkeypatch.setattr(golden_run, "_load_golden_runner", lambda: FakeRunner())
    captured: dict = {}

    async def fake_finalize(session, run_id, **kw):
        captured.update(kw)

    monkeypatch.setattr(golden_run, "_finalize_run", fake_finalize)
    asyncio.run(svc._execute_golden_run(lambda: _FakeCtx(), "eval-g",
                                        _golden_flows(), False))
    assert captured["status"] == "failed"
    assert "chat backend down" in captured["error_message"]


# ── service: bulk delete confirm guard (pre-DB) ───────────────────────────


def test_delete_runs_requires_confirm_without_filter():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(svc.delete_runs(_FakeSession(), None, None, False))
    assert ei.value.status_code == 400
