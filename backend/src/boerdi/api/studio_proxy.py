"""P9-1: the studio "proxy" — an in-process path rewrite, not an HTTP hop.

ALT's proxy (`studio/src/app/api/[...path]/route.ts`) existed because the studio
was a separate Next.js process: it re-issued every request over HTTP to the
backend, streaming the raw body and injecting ``X-Studio-Key``. In NEU the studio
is a static SPA served by this very app, so the same job is a scope rewrite:

    /studio/api/<rest>   ──►   /api/<rest>   (+ X-Studio-Key, cookie-gated)

What that buys, and why it is not a cheat:

- **Multipart and SSE stream for free.** The request keeps its original
  ``receive`` channel and the response its original ``send``; nothing is
  buffered, so a 200 MB RAG upload and an SSE stream behave exactly as on /api.
- **No 120 s timeout** (the plan row asked for one). ALT's ``AbortSignal`` guarded
  a socket to a *different* process that could hang. There is no socket here, and
  an artificial deadline would abort legitimately long responses (backup ZIP,
  eval start) at an arbitrary point. Deliberate deviation, recorded in the plan.
- **Location rewrite inverted.** ALT mapped backend-absolute Locations down to a
  path; here the danger is the opposite: FastAPI's redirect_slashes answers
  ``/studio/api/sessions`` with ``Location: /api/sessions/``, which the browser
  would follow *past* the BFF and hit a studio route without the key. So a
  Location pointing into ``/api`` is mapped back into ``/studio/api``.

Request headers are allow-listed by removal: the client's ``Cookie`` and any
client-supplied ``X-Studio-Key`` are dropped. ALT forwarded every header verbatim
and only overwrote the key when one was configured, so the proxy was not a trust
boundary for it ([...path]/route.ts:39-44).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from boerdi.api.deps import expected_studio_key
from boerdi.api.studio_auth import COOKIE_NAME, authorize, gate_is_open

PREFIX = "/studio/api"
_AUTH_PREFIX = f"{PREFIX}/auth"
_API = "/api"
_DROPPED_REQUEST_HEADERS = (b"cookie", b"x-studio-key")


def _route_path(scope: Scope) -> str:
    """The path WITHOUT ``root_path``, i.e. what the router will match on.

    Behind a path-prefix reverse proxy (``--root-path /pfx``) ``scope["path"]``
    still carries the prefix, while Starlette strips it before routing. Matching
    on the raw path there meant the middleware neither gated nor rewrote anything
    and the /studio SPA mount answered instead — a silent, total outage of the
    studio API. Fails safe (no key is ever injected), but it fails.
    """
    path: str = scope.get("path", "")
    root: str = scope.get("root_path", "")
    if root and path.startswith(root):
        return path[len(root):] or "/"
    return path


def _is_proxied(path: str) -> bool:
    """True for every /studio/api path except the BFF's own auth routes."""
    if path != PREFIX and not path.startswith(f"{PREFIX}/"):
        return False
    return path != _AUTH_PREFIX and not path.startswith(f"{_AUTH_PREFIX}/")


def _forward_headers(headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    forwarded = [(k, v) for k, v in headers if k.lower() not in _DROPPED_REQUEST_HEADERS]
    key = _injectable_key()
    if key:
        forwarded.append((b"x-studio-key", key))
    return forwarded


def _injectable_key() -> bytes:
    """The key to inject, or b"" — the credential is only minted for a request
    that actually passed the cookie gate.

    Without the ``gate_is_open`` check, ``BOERDI_ALLOW_OPEN_ADMIN=1`` on a deploy
    that DID configure a strong ``STUDIO_API_KEY`` would let anonymous requests
    through the open cookie gate and then hand them the configured key —
    unauthenticated ``/studio/api/config/backup``. ``require_studio_key`` treats
    the flag as inert whenever a key is configured (deps.py:60-66); mirroring
    that means: gate open ⇒ inject nothing, and downstream decides. Found by the
    9-1 review; pinned by test_open_admin_does_not_defeat_a_configured_backend_key.
    """
    if gate_is_open():
        return b""
    try:
        return expected_studio_key().encode("latin-1")
    except UnicodeEncodeError:
        # Such a key cannot be sent as an HTTP header at all, so it is unusable
        # on /api/* too. Injecting nothing yields a 401 instead of a 500 here.
        return b""


def _map_location(value: str, host: str) -> str:
    """Map a Location that points into /api back into /studio/api.

    Absolute URLs are only considered when they address this very host; anything
    else is passed through untouched (no endpoint reachable through the BFF emits
    one, and dropping the header would turn a redirect into a blank 307).
    """
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        if parts.netloc != host:
            return value
        target = parts.path + (f"?{parts.query}" if parts.query else "")
    else:
        target = value
    if target == _API or target.startswith(f"{_API}/"):
        return PREFIX + target[len(_API) :]
    return value


def _location_rewriter(send: Send, host: str) -> Send:
    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            message = dict(message)
            message["headers"] = [  # ASGI declares `headers` optional here

                (k, _map_location(v.decode("latin-1"), host).encode("latin-1"))
                if k.lower() == b"location"
                else (k, v)
                for k, v in message.get("headers", [])
            ]
        await send(message)

    return wrapped


class StudioProxyMiddleware:
    """Gates ``/studio/api/*`` on the studio cookie, then re-dispatches it as
    ``/api/*`` with the backend key injected."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        route_path = _route_path(scope) if scope["type"] == "http" else ""
        if scope["type"] != "http" or not _is_proxied(route_path):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        denial = authorize(request.cookies.get(COOKIE_NAME))
        if denial is not None:
            response = JSONResponse({"detail": denial[1]}, status_code=denial[0])
            await response(scope, receive, send)
            return

        inner = scope.get("root_path", "") + _API + route_path[len(PREFIX) :]
        forwarded = dict(scope)
        forwarded["path"] = inner
        forwarded["raw_path"] = inner.encode("utf-8")
        forwarded["headers"] = _forward_headers(list(scope["headers"]))
        host = request.headers.get("host", "")
        await self.app(forwarded, receive, _location_rewriter(send, host))
