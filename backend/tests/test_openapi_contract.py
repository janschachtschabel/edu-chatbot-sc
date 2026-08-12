"""P0-4: frozen OpenAPI contract (spec §5.1).

EXPECTED_ROUTES is the §5.1 acceptance inventory: ALT's live openapi.json
(107 routes, dumped from :8000 on 2026-07-11) plus GET /api/config/schema/{area}
and GET/PUT /api/config/data/{area} (improvement V3 — the exported schema needs
a JSON counterpart to bind a form to; ``/config/file`` is YAML text, see 9-3a)
and GET /widget/frameless (U1 — the demo page for the frameless embed mode,
which ALT did not have; purely additive, one path, nothing changed or removed)
and GET /api/usage/{session,period} (K4 — cost monitoring, which ALT did not do
at all; the reason per route is in ``docs/api/bewusste-vertragszusaetze.md``,
kept in shipped docs rather than only here because that file is also what
``tests/test_openapi_additions.py`` counts against the frozen baseline).
``/api/static/*`` is a StaticFiles mount in ALT and NEU —
mounts never appear in OpenAPI, so it is deliberately absent here.

docs/api/openapi-v1.json is the frozen artifact; ``scripts/export_openapi.py
--check`` is the CI diff gate. Contract updates (typed payloads arriving in
P1–P7) are made deliberately: regenerate the file in the same change.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from boerdi.main import create_app

FROZEN = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-v1.json"

EXPECTED_ROUTES = """
GET    /
HEAD   /
POST   /api/chat
POST   /api/chat/stream
GET    /api/config/backup
GET    /api/config/canvas/material-types
PUT    /api/config/canvas/material-types
GET    /api/config/context-actions
PUT    /api/config/context-actions
GET    /api/config/elements
GET    /api/config/entities
PUT    /api/config/entities
GET    /api/config/factory
GET    /api/config/factory/download
POST   /api/config/factory/restore
POST   /api/config/factory/save
POST   /api/config/factory/upload
DELETE /api/config/file
GET    /api/config/file
PUT    /api/config/file
GET    /api/config/files
GET    /api/config/guide-mode
GET    /api/config/intents
PUT    /api/config/intents
GET    /api/config/mcp-servers
PUT    /api/config/mcp-servers
POST   /api/config/mcp-servers/discover
GET    /api/config/patterns
PUT    /api/config/patterns
GET    /api/config/personas
PUT    /api/config/personas
GET    /api/config/privacy
PUT    /api/config/privacy
POST   /api/config/restore
GET    /api/config/schema/{area}
GET    /api/config/data/{area}
PUT    /api/config/data/{area}
GET    /api/config/snapshots
POST   /api/config/snapshots
DELETE /api/config/snapshots/{snap_id}
GET    /api/config/snapshots/{snap_id}/download
POST   /api/config/snapshots/{snap_id}/restore
GET    /api/config/states
PUT    /api/config/states
GET    /api/config/tone-modifiers
PUT    /api/config/tone-modifiers
GET    /api/config/welcome
PUT    /api/config/welcome
GET    /api/debug/mcp-test
GET    /api/eval/analytics/pattern-usage
GET    /api/eval/config
POST   /api/eval/estimate
GET    /api/eval/gold-flows
DELETE /api/eval/quality-logs
DELETE /api/eval/runs
GET    /api/eval/runs
POST   /api/eval/runs
POST   /api/eval/runs/golden
DELETE /api/eval/runs/{run_id}
GET    /api/eval/runs/{run_id}
GET    /api/eval/trends
GET    /api/health
HEAD   /api/health
GET    /api/loadtest/mix-options
GET    /api/loadtest/runs
POST   /api/loadtest/runs
DELETE /api/loadtest/runs/{run_id}
GET    /api/loadtest/runs/{run_id}
GET    /api/quality/degradations
GET    /api/quality/empty-entities
GET    /api/quality/logs
POST   /api/quality/logs/clear
DELETE /api/quality/logs/{log_id}
GET    /api/quality/low-confidence
GET    /api/quality/matrix
GET    /api/quality/state-transitions
GET    /api/quality/stats
GET    /api/quality/tight-races
DELETE /api/rag/area/{area}
GET    /api/rag/area/{area}
DELETE /api/rag/area/{area}/doc
GET    /api/rag/area/{area}/doc
GET    /api/rag/areas
POST   /api/rag/embed
POST   /api/rag/ingest/file
POST   /api/rag/ingest/text
POST   /api/rag/ingest/url
POST   /api/rag/query
GET    /api/safety/logs
GET    /api/safety/stats
GET    /api/sessions/
GET    /api/sessions/db-stats
POST   /api/sessions/optimize
POST   /api/sessions/purge
DELETE /api/sessions/{session_id}
GET    /api/sessions/{session_id}
GET    /api/sessions/{session_id}/memory
POST   /api/sessions/{session_id}/memory
DELETE /api/sessions/{session_id}/messages
GET    /api/sessions/{session_id}/messages
GET    /api/speech/status
POST   /api/speech/synthesize
POST   /api/speech/transcribe
POST   /api/agent
POST   /api/agent/stream
GET    /api/usage/period
GET    /api/usage/session/{session_id}
GET    /health
HEAD   /health
POST   /studio/api/auth/login
POST   /studio/api/auth/logout
GET    /studio/api/auth/session
GET    /widget/
GET    /widget/boerdi-widget.js
GET    /widget/classic
GET    /widget/frameless
GET    /widget/inline
GET    /widget/{asset_name}
"""

# §5.1 public routes — everything else must carry the StudioKey security marker.
PUBLIC_ROUTES = {
    "GET /", "HEAD /", "GET /health", "HEAD /health", "GET /api/health",
    "HEAD /api/health", "POST /api/chat", "POST /api/chat/stream",
    "GET /api/speech/status", "POST /api/speech/transcribe",
    "POST /api/speech/synthesize", "GET /api/sessions/{session_id}/messages",
    "GET /api/config/guide-mode", "GET /widget/", "GET /widget/boerdi-widget.js",
    "GET /widget/classic", "GET /widget/frameless", "GET /widget/inline",
    "GET /widget/{asset_name}",
    # studio-bff (P9-1): the login pair must be reachable unauthenticated, like
    # ALT's PUBLIC_PATHS (middleware.ts:25). GET /studio/api/auth/session is NOT
    # here — it carries the StudioCookie marker, which is what the else-branch
    # below asserts. Everything else under /studio/api is the proxy middleware,
    # which owns no routes and therefore no OpenAPI entries.
    "POST /studio/api/auth/login", "POST /studio/api/auth/logout",
}


def expected() -> set[str]:
    routes = set()
    for line in EXPECTED_ROUTES.strip().splitlines():
        method, path = line.split()
        routes.add(f"{method} {path}")
    return routes


def spec_routes(spec: dict) -> set[str]:
    routes = set()
    for path, ops in spec["paths"].items():
        for method in ops:
            if method in ("get", "post", "put", "delete", "head", "patch"):
                routes.add(f"{method.upper()} {path}")
    return routes


def test_route_inventory_matches_spec_5_1() -> None:
    spec = create_app().openapi()
    actual = spec_routes(spec)
    exp = expected()
    assert exp - actual == set(), f"missing routes: {sorted(exp - actual)}"
    assert actual - exp == set(), f"unexpected routes: {sorted(actual - exp)}"


def test_frozen_contract_matches_app() -> None:
    assert FROZEN.exists(), "docs/api/openapi-v1.json missing — run scripts/export_openapi.py"
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    live = json.loads(json.dumps(create_app().openapi()))
    assert live == frozen, (
        "OpenAPI drifted from the frozen contract. If the change is deliberate, "
        "regenerate: uv run python scripts/export_openapi.py"
    )


def test_studio_routes_carry_security_marker() -> None:
    spec = create_app().openapi()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "head", "patch"):
                continue
            route = f"{method.upper()} {path}"
            has_security = bool(op.get("security"))
            if route in PUBLIC_ROUTES:
                assert not has_security, f"{route} must be public (no security)"
            else:
                assert has_security, f"{route} must carry the StudioKey marker"


def test_health_is_live_not_stub() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}


def test_stubs_return_501(monkeypatch) -> None:
    client = TestClient(create_app())
    # There is no PUBLIC 501 stub left: C4 implemented the last three (the widget
    # demo pages). Every public route now answers for itself — asserted here so
    # the claim is checked rather than remembered.
    for path in (
        "/widget/",
        "/widget/inline",
        "/widget/classic",
        "/widget/frameless",
        "/widget/boerdi-widget.js",
    ):
        assert client.get(path).status_code != 501, path
    # The representative STUDIO 501 stub is GET /api/debug/mcp-test (P5-1); all the
    # studio ROUTERS are implemented. Reach it past fail-closed auth via the
    # explicit dev opt-in (the 503/401 matrix is covered in test_auth.py).
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    from boerdi.settings import get_settings

    get_settings.cache_clear()
    assert client.get("/api/debug/mcp-test").status_code == 501
