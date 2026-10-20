"""Shared API dependencies.

``get_session`` — one ``AsyncSession`` per request, from the factory the
lifespan puts on ``app.state`` (spec rule 3: no module-global engine).

``require_studio_key`` — port of ALT ``app/services/auth.py`` (P1-3).
Fail-closed (ALT Audit T1): when no real key is configured, admin endpoints
are DISABLED (503) — a blank/forgotten/``CHANGE_ME`` key must never leave
backup/restore/purge open to the internet. Local development that
deliberately wants an open admin sets ``BOERDI_ALLOW_OPEN_ADMIN`` (no
implicit open path). The key is accepted ONLY via the ``X-Studio-Key``
header — never as a query param, so it cannot leak into proxy/access logs
or Referer headers.
"""

import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.i18n import Locale, resolve_locale
from boerdi.services.session_origin import Scope
from boerdi.settings import get_settings, studio_schluessel

_HEADER = "X-Studio-Key"


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One ``AsyncSession`` per request, closed when the request ends.

    Services commit themselves, so leaving the block rolls back anything they
    left uncommitted rather than silently persisting a half-finished write.
    """
    async with request.app.state.session_factory() as session:
        yield session


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """The factory itself — for work that may outlive the request (Review Paket 7,
    A-1): a streamed turn finishes after the client hung up (P2), but FastAPI
    closes the request-scoped session as soon as the response ends."""
    return request.app.state.session_factory


studio_key_header = APIKeyHeader(
    name=_HEADER, auto_error=False, scheme_name="StudioKey"
)


def expected_studio_key() -> str:
    """The configured Studio key, or "" if none. ``CHANGE_ME…`` placeholders
    count as unconfigured so a forgotten scaffold value can't act as a key.

    Public because the studio-bff injects exactly this value (P9-1) — deriving it
    twice would let a placeholder slip past one of the two call sites."""
    return studio_schluessel()


async def require_studio_key(
    x_studio_key: str | None = Security(studio_key_header),
) -> None:
    """FastAPI dependency. Fails closed:

    - No real key configured → 503 (admin disabled), UNLESS
      ``BOERDI_ALLOW_OPEN_ADMIN`` is set (explicit dev opt-in) → no-op.
    - Key configured but request key missing/wrong → 401.
    """
    expected = expected_studio_key()
    if not expected:
        if get_settings().allow_open_admin:
            return  # explicit local-dev opt-in — admin intentionally open
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Admin endpoints are disabled: STUDIO_API_KEY is not configured. "
                "Set it, or set BOERDI_ALLOW_OPEN_ADMIN=1 for local development."
            ),
        )
    provided = (x_studio_key or "").strip()
    # `isascii()` guard: `hmac.compare_digest` raises TypeError on a non-ASCII
    # `str` and Starlette decodes headers as latin-1, so a single byte ≥ 0x80 in
    # X-Studio-Key answered 500 instead of 401 (found reviewing P9-1, same class
    # of bug as the cookie gate in studio_auth.authorize).
    if not provided.isascii() or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Studio API key required",
            headers={"WWW-Authenticate": _HEADER},
        )


def request_locale(request: Request) -> Locale:
    """The language this request wants, from ``Accept-Language`` (C1-e).

    Read off ``Request`` rather than declared as ``Header()`` on purpose: a
    declared header parameter shows up in the OpenAPI document, and every
    endpoint that took the dependency would change the frozen contract that
    ``scripts/export_openapi.py --check`` guards. The header is optional and
    additive — a client that never sends it sees exactly what it saw before.

    Known limitation, deliberately taken: because it is not declared, the
    header does not appear in ``/docs``. It is documented here and in the
    C1-e section of ``docs/plans/2026-08-02-c1-i18n.md`` instead.
    """
    return resolve_locale(request.headers.get("accept-language"))


Lang = Annotated[Locale, Depends(request_locale)]

#: Herkunft der Sitzungen (ST-9) an Kosten und Sitzungsliste — ein Literal statt
#: eines freien Strings wie bei ``/api/quality/*``: ein Tippfehler soll 422
#: ergeben, nicht still „alle". Bedeutung in ``services/session_origin.py``.
OriginScope = Annotated[
    Scope,
    Query(description="Herkunft: 'all' | 'production' (ohne Eval-, Lasttest- "
                      "und Studio-Probe-Sitzungen) | 'eval'"),
]


def todo(package: str) -> HTTPException:
    """501 for contract stubs — names the package that implements the route."""
    return HTTPException(
        status_code=501, detail=f"not implemented yet (arrives with {package})"
    )
