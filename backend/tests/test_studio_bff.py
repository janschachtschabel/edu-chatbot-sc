"""P9-1: studio-bff — cookie gate, key injection, SPA hosting.

The ALT proxy was a Next.js route handler talking HTTP to a *separate* FastAPI
process. In NEU the studio is a static SPA served by the backend itself, so the
"proxy" is an in-process path rewrite: ``/studio/api/<rest>`` → ``/api/<rest>``
plus ``X-Studio-Key`` injection. That keeps multipart uploads and SSE streaming
free (one receive channel, no buffering) and removes the cross-process hop.

Tests are offline: ``TestClient`` WITHOUT a ``with`` block, because the lifespan
needs Postgres (same rule as test_rag_router.py / test_quality_router.py). The
downstream probe is ``GET /api/debug/mcp-test``, a studio route that answers 501
(P5 stub) — 501 proves the injected key satisfied ``require_studio_key``, while
401 would prove it did not. That discrimination is the point of the probe.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response

from boerdi.api import ratelimit
from boerdi.api.studio_auth import authorize
from boerdi.api.studio_proxy import StudioProxyMiddleware
from boerdi.main import create_app
from boerdi.settings import get_settings


async def _call(app, scope: dict) -> None:
    """Drive a bare ASGI app once — for scopes TestClient cannot express
    (duplicate headers, a non-ASCII cookie, a reverse-proxy ``root_path``)."""
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    await app(scope, receive, send)

PASSWORD = "geheim-studio-pw"
COOKIE = "boerdi_studio_auth"
PROBE = "/studio/api/debug/mcp-test"


def alt_token(password: str) -> str:
    """The ALT token, recomputed independently of the implementation.

    ALT `studio/src/lib/auth-token.ts:17-28`: HMAC-SHA256 where the PASSWORD is
    the key and the message is the fixed string ``boerdi-studio-auth-v1``, hex.
    Recomputing it here (instead of importing the port) is what makes this an
    interop pin: a cookie minted by ALT must still open the new BFF.
    """
    return hmac.new(password.encode("utf-8"), b"boerdi-studio-auth-v1", hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _studio_env(monkeypatch):
    """Configured gate + configured backend key, limiter reset around each test
    (the login limit is a fixed 10/minute and would leak between tests)."""
    monkeypatch.setenv("STUDIO_PASSWORD", PASSWORD)
    monkeypatch.setenv("STUDIO_API_KEY", "backend-key")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    monkeypatch.delenv("STUDIO_DIST_DIR", raising=False)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _authed(client: TestClient) -> TestClient:
    client.cookies.set(COOKIE, alt_token(PASSWORD))
    return client


# ── Login / Logout / Session ──────────────────────────────────────────────


def test_login_sets_the_alt_cookie(client: TestClient) -> None:
    resp = client.post("/studio/api/auth/login", json={"password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "open": False}
    assert resp.cookies[COOKIE] == alt_token(PASSWORD)


def test_login_cookie_carries_the_alt_flags(client: TestClient) -> None:
    resp = client.post("/studio/api/auth/login", json={"password": PASSWORD})
    raw = resp.headers["set-cookie"].lower()
    assert "httponly" in raw
    assert "samesite=strict" in raw
    assert "path=/" in raw
    assert "max-age=2592000" in raw  # 30 d, ALT login/route.ts:47
    assert "secure" in raw  # fail-secure default, unlike ALT's NODE_ENV guess


def test_cookie_secure_can_be_disabled_for_plain_http_dev(monkeypatch, client) -> None:
    monkeypatch.setenv("STUDIO_COOKIE_SECURE", "0")
    get_settings.cache_clear()
    resp = client.post("/studio/api/auth/login", json={"password": PASSWORD})
    assert "secure" not in resp.headers["set-cookie"].lower()


def test_login_rejects_wrong_password_without_a_cookie(client: TestClient) -> None:
    resp = client.post("/studio/api/auth/login", json={"password": "falsch"})
    assert resp.status_code == 401
    assert "set-cookie" not in resp.headers


def test_login_rejects_an_empty_password(client: TestClient) -> None:
    assert client.post("/studio/api/auth/login", json={"password": ""}).status_code == 401


def test_login_rejects_malformed_json(client: TestClient) -> None:
    """ALT answered 400 (login/route.ts:28); FastAPI's body validation answers
    422, as it does on every other route in this app. Keeping 400 would mean a
    per-route exception handler for a case only our own SPA can produce, and it
    treats any non-2xx the same. What matters is that the body is rejected."""
    resp = client.post(
        "/studio/api/auth/login", content=b"nicht-json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422


def test_login_is_rate_limited(client: TestClient) -> None:
    """ALT had NO limiter on login (unbounded password guessing). The BFF caps
    attempts per IP — the only cost in ALT was two HMAC computations."""
    codes = [
        client.post("/studio/api/auth/login", json={"password": "falsch"}).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_logout_clears_the_cookie(client: TestClient) -> None:
    resp = _authed(client).post("/studio/api/auth/logout")
    assert resp.status_code == 200
    raw = resp.headers["set-cookie"].lower()
    assert "max-age=0" in raw
    assert "path=/" in raw
    # ALT dropped the flags when clearing (logout/route.ts:8) — keep them, so the
    # clearing cookie cannot be read by script either.
    assert "httponly" in raw


def test_session_reports_authenticated_with_a_valid_cookie(client: TestClient) -> None:
    resp = _authed(client).get("/studio/api/auth/session")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": True, "open": False}


def test_session_is_401_without_a_cookie(client: TestClient) -> None:
    assert client.get("/studio/api/auth/session").status_code == 401


def test_session_is_401_for_a_forged_cookie(client: TestClient) -> None:
    client.cookies.set(COOKIE, alt_token("anderes-pw"))
    assert client.get("/studio/api/auth/session").status_code == 401


# ── Proxy: gate + key injection ───────────────────────────────────────────


def test_proxy_injects_the_backend_key(client: TestClient) -> None:
    """501 = the stub was reached, i.e. require_studio_key was satisfied by the
    injected header; the client never sent one."""
    assert _authed(client).get(PROBE).status_code == 501


def test_proxy_is_401_without_a_cookie(client: TestClient) -> None:
    """Deliberate deviation from ALT, which 307-redirected API calls to the HTML
    login page (middleware.ts:51-54) so every XHR failed on HTML instead of 401."""
    resp = client.get(PROBE)
    assert resp.status_code == 401
    assert resp.json()["detail"]


def test_a_client_supplied_key_cannot_bypass_the_cookie_gate(client: TestClient) -> None:
    """ALT forwarded all client headers verbatim and only overwrote X-Studio-Key
    when STUDIO_API_KEY was non-empty ([...path]/route.ts:39-44) — the proxy was
    not a trust boundary for that header. Here it is."""
    resp = client.get(PROBE, headers={"X-Studio-Key": "backend-key"})
    assert resp.status_code == 401


def test_a_wrong_client_key_is_replaced_not_merged(client: TestClient) -> None:
    resp = _authed(client).get(PROBE, headers={"X-Studio-Key": "falsch"})
    assert resp.status_code == 501


def test_proxy_forwards_the_query_string(client: TestClient) -> None:
    resp = _authed(client).get("/studio/api/config/guide-mode?x=1&y=zwei")
    # guide-mode is public and DB-backed; without a lifespan it fails at the
    # store, not at routing — 404 would mean the rewrite lost the path.
    assert resp.status_code != 404


def test_proxy_rewrites_the_redirect_back_into_the_bff(client: TestClient) -> None:
    """``GET /api/sessions/`` only exists WITH a trailing slash. FastAPI answers
    the slashless form with a 307 to ``/api/sessions/`` — a Location the browser
    would follow straight past the BFF, arriving key-less at a studio route."""
    resp = _authed(client).get("/studio/api/sessions", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/studio/api/sessions/"


def test_proxy_returns_404_for_an_unknown_api_path(client: TestClient) -> None:
    resp = _authed(client).get("/studio/api/gibt-es-nicht")
    assert resp.status_code == 404
    # As an API 404, not an HTML page — the content type is what tells the SPA
    # "this was a request that failed", not "here is a document".
    assert resp.headers["content-type"].startswith("application/json")


def test_proxy_does_not_touch_the_public_api(client: TestClient) -> None:
    """The rewrite must be scoped to /studio/api — /api stays exactly as it was.

    Checked WITH a valid cookie too: without that, the assertion would also hold
    if the middleware had over-reached onto /api, because the cookie-less request
    is 401 either way. The detail string is the discriminator — deps.py answers
    "Studio API key required", the BFF gate answers "Studio login required".
    """
    assert client.get("/api/debug/mcp-test").status_code == 401
    resp = _authed(client).get("/api/debug/mcp-test")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Studio API key required"


def test_proxy_forwards_path_query_and_headers_verbatim() -> None:
    """Unit-level: what the rewritten scope actually contains.

    The route-level tests cannot see this — dropping ``query_string`` entirely
    left the whole suite green, because no probe route reads a query param. A
    sink app makes the contract observable instead of implied.
    """
    seen: dict[str, object] = {}

    async def sink(scope, receive, send):
        seen.update(scope)
        await Response(status_code=204)(scope, receive, send)

    app = StudioProxyMiddleware(sink)
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(COOKIE, alt_token(PASSWORD))
    resp = client.get(
        "/studio/api/quality/logs?limit=50&scope=prod",
        headers={"X-Studio-Key": "vom-client", "X-Custom": "bleibt"},
    )

    assert resp.status_code == 204
    assert seen["path"] == "/api/quality/logs"
    assert seen["raw_path"] == b"/api/quality/logs"
    assert seen["query_string"] == b"limit=50&scope=prod"

    names = [k.decode() for k, _ in seen["headers"]]  # type: ignore[union-attr]
    # The client's cookie must NOT reach the API layer: nothing there reads it,
    # and a future route that did would be trusting a header the BFF already
    # consumed. ALT forwarded every header verbatim.
    assert "cookie" not in names
    assert names.count("x-studio-key") == 1
    assert dict(seen["headers"])[b"x-studio-key"] == b"backend-key"  # type: ignore[arg-type]
    assert dict(seen["headers"])[b"x-custom"] == b"bleibt"  # type: ignore[arg-type]


def test_proxy_drops_every_duplicate_cookie_header() -> None:
    """Two `Cookie` headers is legal on the wire; dropping only the first would
    still hand one to the API layer."""
    seen: dict[str, object] = {}

    async def sink(scope, receive, send):
        seen.update(scope)
        await Response(status_code=204)(scope, receive, send)

    scope = {
        "type": "http", "method": "GET", "path": "/studio/api/health",
        "raw_path": b"/studio/api/health", "query_string": b"", "root_path": "",
        "headers": [
            (b"cookie", f"{COOKIE}={alt_token(PASSWORD)}".encode()),
            (b"cookie", b"other=1"),
            (b"host", b"testserver"),
        ],
    }
    asyncio.run(_call(StudioProxyMiddleware(sink), scope))
    assert [k for k, _ in seen["headers"]] == [(b"host")] + [b"x-studio-key"]  # type: ignore[union-attr]


def test_proxy_survives_a_reverse_proxy_root_path() -> None:
    """Behind ``--root-path /pfx`` the scope path still carries the prefix while
    Starlette strips it before routing. Matching the raw path meant the
    middleware neither gated nor rewrote — a silent, total outage of the studio
    API the moment the app is deployed under a path prefix."""
    seen: dict[str, object] = {}

    async def sink(scope, receive, send):
        seen.update(scope)
        await Response(status_code=204)(scope, receive, send)

    scope = {
        "type": "http", "method": "GET", "root_path": "/pfx",
        "path": "/pfx/studio/api/config/files", "raw_path": b"/pfx/studio/api/config/files",
        "query_string": b"", "headers": [(b"host", b"testserver")],
    }
    asyncio.run(_call(StudioProxyMiddleware(sink), scope))
    # Gated: no cookie was sent, so the sink must never have been reached.
    assert seen == {}

    scope["headers"] = [
        (b"host", b"testserver"),
        (b"cookie", f"{COOKIE}={alt_token(PASSWORD)}".encode()),
    ]
    asyncio.run(_call(StudioProxyMiddleware(sink), scope))
    # The prefix is preserved, so the downstream router still strips it itself.
    assert seen["path"] == "/pfx/api/config/files"


def test_a_cors_preflight_is_not_swallowed_by_the_gate(monkeypatch) -> None:
    """A preflight carries no cookies by definition, so gating it would break
    every cross-origin non-simple request. CORS must wrap the gate — which is
    why StudioProxyMiddleware is registered BEFORE CORSMiddleware in main.py
    (``add_middleware`` inserts at the front, so later = outer)."""
    monkeypatch.setenv("CORS_ORIGINS", "https://studio.example")
    get_settings.cache_clear()
    client = TestClient(create_app())
    resp = client.options(
        PROBE,
        headers={
            "Origin": "https://studio.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://studio.example"


def test_a_non_ascii_cookie_is_rejected_not_a_500() -> None:
    """``hmac.compare_digest`` raises TypeError on non-ASCII ``str``, and
    Starlette decodes the Cookie header as latin-1 — so a single byte ≥ 0x80
    turned the gate in front of every admin endpoint into an unauthenticated
    500. Reachable with one curl."""
    assert authorize("ÿÿ") == (401, "Studio login required")
    assert authorize("\udcff") == (401, "Studio login required")


# ── Fail-closed / open-admin opt-in ───────────────────────────────────────


def test_gate_is_fail_closed_without_a_password(monkeypatch, client) -> None:
    """ALT was fail-OPEN: an unset STUDIO_PASSWORD silently disabled the gate
    (middleware.ts:31), leaving an unauthenticated proxy into the backend. That
    exact shape was audit blocker T1 in ALT. NEU mirrors require_studio_key:
    503 unless the dev opt-in is explicit."""
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    get_settings.cache_clear()
    assert client.get(PROBE).status_code == 503
    assert client.get("/studio/api/auth/session").status_code == 503
    assert client.post("/studio/api/auth/login", json={"password": "x"}).status_code == 503


def test_placeholder_password_counts_as_unconfigured(monkeypatch, client) -> None:
    monkeypatch.setenv("STUDIO_PASSWORD", "CHANGE_ME_please")
    get_settings.cache_clear()
    assert client.get(PROBE).status_code == 503


def test_open_admin_does_not_defeat_a_configured_backend_key(monkeypatch, client) -> None:
    """The combination that must NOT open the admin surface.

    ``BOERDI_ALLOW_OPEN_ADMIN`` is inert in ``require_studio_key`` whenever a key
    IS configured (deps.py:60-66) — it only skips the check when there is nothing
    to check. The BFF must mirror that: an open cookie gate may let the request
    through, but it must not then MINT the credential the operator configured, or
    a deploy with a strong key would serve /studio/api/config/backup to anyone.
    """
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    monkeypatch.setenv("STUDIO_API_KEY", "strong-prod-key")
    get_settings.cache_clear()
    assert client.get(PROBE).status_code == 401
    assert client.get("/studio/api/config/files").status_code == 401


def test_open_admin_opt_in_disables_the_gate(monkeypatch, client) -> None:
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    get_settings.cache_clear()
    assert client.get(PROBE).status_code == 501  # no cookie needed
    assert client.get("/studio/api/auth/session").json() == {"authenticated": True, "open": True}
    resp = client.post("/studio/api/auth/login", json={"password": "irgendwas"})
    assert resp.json() == {"ok": True, "open": True}
    assert "set-cookie" not in resp.headers


# ── Static SPA hosting ────────────────────────────────────────────────────


def test_spa_is_served_and_deep_links_fall_back_to_index(monkeypatch, tmp_path) -> None:
    dist = tmp_path / "studio_dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>Studio</h1>", encoding="utf-8")
    (dist / "main.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("STUDIO_DIST_DIR", str(dist))
    get_settings.cache_clear()
    client = TestClient(create_app())

    assert client.get("/studio/").text == "<h1>Studio</h1>"
    assert "console.log" in client.get("/studio/main.js").text
    # Angular client-side route — no such file, must still boot the SPA.
    assert client.get("/studio/dimensionen/intents").text == "<h1>Studio</h1>"


def test_missing_dist_does_not_break_startup_and_does_not_mask_the_api(
    monkeypatch, client
) -> None:
    """Without a built SPA the mount is skipped (dev/CI before `ng build`), and
    the BFF routes must keep working — the fallback must never swallow them."""
    assert client.get("/studio/").status_code == 404
    assert _authed(client).get(PROBE).status_code == 501


def test_spa_fallback_never_swallows_the_bff(monkeypatch, tmp_path) -> None:
    dist = tmp_path / "studio_dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>Studio</h1>", encoding="utf-8")
    monkeypatch.setenv("STUDIO_DIST_DIR", str(dist))
    get_settings.cache_clear()
    client = TestClient(create_app())
    client.cookies.set(COOKIE, alt_token(PASSWORD))

    assert client.get(PROBE).status_code == 501
    # An unknown /studio/api path must 404 as an API, not render the SPA shell.
    resp = client.get("/studio/api/gibt-es-nicht")
    assert resp.status_code == 404
    assert "Studio" not in resp.text

    # The AUTH branch is the one the SPA fallback can actually reach: the proxy
    # middleware rewrites every other /studio/api path out of /studio before
    # routing, so only /studio/api/auth/* ever arrives at the mount. A typo'd
    # auth path answering "200 text/html" is exactly the ALT symptom (every XHR
    # failing while parsing a login page) that this port set out to remove.
    typo = client.get("/studio/api/auth/gibt-es-nicht")
    assert typo.status_code == 404, typo.text[:120]
    assert "Studio" not in typo.text
    # GET on the POST-only login route: 404, not 405, and not the SPA shell.
    # A method mismatch is only a PARTIAL route match in Starlette, and the
    # prefix Mount that follows is a FULL match, so the mount always wins over
    # the 405. Answering as an API (JSON) is the property that matters.
    wrong_method = client.get("/studio/api/auth/login")
    assert wrong_method.status_code == 404
    assert wrong_method.headers["content-type"].startswith("application/json")
