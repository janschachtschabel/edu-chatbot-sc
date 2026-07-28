"""P9-1: static hosting for the studio SPA (``/studio``).

The first StaticFiles mount in this app. Mounts do not appear in the OpenAPI
schema, so the frozen contract is unaffected (see tests/test_openapi_contract.py).

Angular routes client-side, so an unknown sub-path must boot the shell instead of
404ing — ``StaticFiles(html=True)`` only does that for *directory* requests, so
the 404 fallback below is what makes deep links work. It cannot mask the BFF:
StudioProxyMiddleware rewrites ``/studio/api/*`` out of ``/studio`` before routing
happens, and the auth router is registered before this mount.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from boerdi.settings import get_settings

log = logging.getLogger("startup")

_INDEX = "index.html"


class SpaFiles(StaticFiles):
    """StaticFiles that serves ``index.html`` for unknown paths (SPA routing)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # NEVER fall back for an API path. StudioProxyMiddleware rewrites
            # every /studio/api/* path except the auth routes out of /studio
            # before routing, so `/studio/api/auth/<typo>` is the one API path
            # that reaches this mount — and answering it with "200 text/html"
            # would recreate the exact ALT symptom this port removed: an XHR
            # failing while parsing a login page instead of seeing a status.
            # `path` arrives OS-normalised (StaticFiles runs os.path.normpath),
            # so on Windows it is "api\auth\x" — a `startswith("api/")` check
            # would hold on the Linux deploy target and silently miss locally.
            segment = path.replace("\\", "/").split("/", 1)[0]
            if exc.status_code != 404 or segment == "api":
                raise
            return await super().get_response(_INDEX, scope)


def mount_studio_spa(app: FastAPI) -> None:
    """Mount the built studio, or skip with a hint when it is absent.

    Absent is the normal state in dev and CI before ``ng build``; a hard failure
    there would make the backend unusable for everyone not working on the studio.
    """
    directory = Path(get_settings().studio_dist_dir)
    if not (directory / _INDEX).is_file():
        log.info(
            "Studio-SPA nicht eingebunden: %s/%s fehlt (STUDIO_DIST_DIR). "
            "Erst bauen: cd frontend && npm run build:studio",
            directory,
            _INDEX,
        )
        return
    app.mount("/studio", SpaFiles(directory=str(directory), html=True), name="studio")
