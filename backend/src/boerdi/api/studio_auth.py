"""P9-1: studio cookie auth — the primitives shared by router and middleware.

Token mechanics are a verbatim port of ALT `studio/src/lib/auth-token.ts`:
HMAC-SHA256 with the PASSWORD as the key and the fixed message
``boerdi-studio-auth-v1``, hex-encoded. Porting it exactly means a cookie minted
by the old Next.js studio still opens this one (and vice versa), so a mixed
deploy during the P11 cutover does not log everyone out.

Two deliberate deviations from ALT, both hardening:

- **Fail-closed.** ALT treated an unset ``STUDIO_PASSWORD`` as "studio is open"
  (middleware.ts:31), which turns a misconfigured deploy into an unauthenticated
  proxy into the backend — the shape of ALT audit blocker T1. Here an unset
  password disables the studio (503) unless ``BOERDI_ALLOW_OPEN_ADMIN`` is set,
  exactly mirroring ``require_studio_key`` in deps.py.
- **401 instead of an HTML redirect.** ALT redirected unauthenticated ``/api/*``
  calls to the login page, so every XHR failed while parsing HTML. The SPA guard
  asks ``GET /studio/api/auth/session`` and routes to /login itself.

Known limitation (inherited, not introduced): the token is a pure function of
the password, so it has no expiry and cannot be revoked server-side — logout
only asks the browser to forget it. Rotating STUDIO_PASSWORD invalidates every
cookie. Upgrade path (``simplify:``): a signed payload with ``exp`` + a key id,
at the cost of breaking ALT interop.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyCookie

from boerdi.settings import get_settings

COOKIE_NAME = "boerdi_studio_auth"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 d, ALT login/route.ts:47
_TOKEN_MESSAGE = b"boerdi-studio-auth-v1"

_OPEN = "open"
_CLOSED = "closed"
_GUARDED = "guarded"

_CLOSED_DETAIL = (
    "Studio is disabled: STUDIO_PASSWORD is not configured. Set it, or set "
    "BOERDI_ALLOW_OPEN_ADMIN=1 for local development."
)
_UNAUTHORIZED_DETAIL = "Studio login required"

studio_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False, scheme_name="StudioCookie")


def studio_token(password: str) -> str:
    """The cookie value for ``password`` — ALT auth-token.ts:17-28."""
    return hmac.new(password.encode("utf-8"), _TOKEN_MESSAGE, hashlib.sha256).hexdigest()


def configured_password() -> str:
    """The configured studio password, or "" if none.

    Returned VERBATIM, not stripped: the password is the HMAC key, and ALT reads
    ``process.env.STUDIO_PASSWORD`` raw (login/route.ts:18, middleware.ts:28). A
    trim here would silently mint a different token for any value with
    surrounding whitespace — plausible in a .env/compose/k8s secret — and break
    exactly the cookie interop this port promises. Only the emptiness and
    placeholder checks look at the trimmed form.

    ``CHANGE_ME…`` placeholders count as unconfigured for the same reason as in
    ``expected_studio_key``: a forgotten scaffold value must not act as a gate.
    """
    password = get_settings().studio_password.get_secret_value()
    probe = password.strip().upper()
    if not probe or probe.startswith("CHANGE_ME"):
        return ""
    return password


def _gate_state() -> str:
    if configured_password():
        return _GUARDED
    return _OPEN if get_settings().allow_open_admin else _CLOSED


def gate_is_open() -> bool:
    """True when no password guards the studio (explicit dev opt-in only)."""
    return _gate_state() == _OPEN


def authorize(cookie: str | None) -> tuple[int, str] | None:
    """``None`` = let the request through, else the (status, detail) to answer.

    One decision function for both consumers: the FastAPI dependency below and
    the ASGI middleware in studio_proxy.py, which cannot raise HTTPException.
    """
    state = _gate_state()
    if state == _OPEN:
        return None
    if state == _CLOSED:
        return (status.HTTP_503_SERVICE_UNAVAILABLE, _CLOSED_DETAIL)
    # `isascii()` first: `hmac.compare_digest` raises TypeError on a non-ASCII
    # `str`, and Starlette decodes the Cookie header as latin-1 — so one byte
    # ≥ 0x80 would turn this gate into an unauthenticated 500. A valid token is
    # 64 hex characters, so a non-ASCII value is simply wrong.
    if cookie and cookie.isascii():
        if hmac.compare_digest(cookie, studio_token(configured_password())):
            return None
    return (status.HTTP_401_UNAUTHORIZED, _UNAUTHORIZED_DETAIL)


async def require_studio_cookie(cookie: str | None = Security(studio_cookie)) -> None:
    """FastAPI dependency for the BFF's own routes (``Security`` so the cookie
    scheme shows up in the OpenAPI contract, like ``require_studio_key``)."""
    denial = authorize(cookie)
    if denial is not None:
        raise HTTPException(status_code=denial[0], detail=denial[1])
