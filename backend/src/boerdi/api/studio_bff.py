"""P9-1: studio-bff auth routes (``/studio/api/auth/*``).

These three are real routes; everything else under ``/studio/api`` is rewritten
into ``/api`` by StudioProxyMiddleware (studio_proxy.py) and never reaches a
router of its own. Login/logout are the ALT pair; ``GET /auth/session`` is new
surface — ALT had no way to ask "am I logged in?" and relied on its middleware
redirecting to /login, which a static SPA cannot observe (spec §5.6, the guard
hits this route).
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response, Security, status
from pydantic import BaseModel, Field

from boerdi.api.ratelimit import limiter
from boerdi.api.studio_auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    authorize,
    configured_password,
    gate_is_open,
    require_studio_cookie,
    studio_token,
)
from boerdi.settings import get_settings

router = APIRouter(prefix="/studio/api/auth", tags=["studio-bff"])

# Fixed, not configurable: this is a brute-force floor, not a tuning knob. ALT
# had no limit at all, so guessing cost two HMAC computations per attempt.
_LOGIN_LIMIT = "10/minute"


class LoginRequest(BaseModel):
    password: str = Field("", max_length=1024)


class LoginResponse(BaseModel):
    ok: bool
    open: bool = Field(description="true = no password configured, login is a no-op")


class SessionResponse(BaseModel):
    authenticated: bool
    open: bool


@router.post("/login", response_model=LoginResponse)
@limiter.limit(_LOGIN_LIMIT)
async def login(request: Request, response: Response, body: LoginRequest) -> LoginResponse:
    """Set the auth cookie on a correct password (ALT login/route.ts).

    ``request``/``response`` are required by the limiter decorator and to set the
    cookie. Both the provided and the expected password are hashed first, so the
    comparison runs over equal-length digests (ALT login/route.ts:34-39).
    """
    if gate_is_open():
        return LoginResponse(ok=True, open=True)
    expected = configured_password()
    if not expected:
        # Unreachable while `gate_is_open()` above covers the OPEN state, but
        # spelled out rather than `raise HTTPException(*authorize(None))`: that
        # would become a TypeError if authorize ever returned None here.
        denial = authorize(None) or (status.HTTP_503_SERVICE_UNAVAILABLE, 'Studio disabled')
        raise HTTPException(status_code=denial[0], detail=denial[1])
    provided = body.password
    if not provided or not _tokens_match(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")
    response.set_cookie(
        COOKIE_NAME,
        studio_token(expected),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=get_settings().studio_cookie_secure,
        path="/",
    )
    return LoginResponse(ok=True, open=False)


def _tokens_match(provided: str, expected: str) -> bool:
    return hmac.compare_digest(studio_token(provided), studio_token(expected))


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    """Clear the cookie. Server-side revocation is impossible by construction
    (see studio_auth.py) — this only asks the browser to forget it.

    Unlike ALT (logout/route.ts:8) the clearing cookie keeps httponly/samesite/
    secure: a Set-Cookie that drops them is a second, script-readable cookie in
    every browser that stores it before expiry.
    """
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=get_settings().studio_cookie_secure,
    )
    return {"ok": True}


@router.get(
    "/session",
    response_model=SessionResponse,
    dependencies=[Security(require_studio_cookie)],
)
async def session() -> SessionResponse:
    """The SPA's auth guard. 401 = show /login, 503 = studio not configured."""
    return SessionResponse(authenticated=True, open=gate_is_open())
