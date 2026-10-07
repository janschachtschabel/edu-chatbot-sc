"""P9-1: static hosting for the studio SPA (``/studio``).

The first StaticFiles mount in this app. Mounts do not appear in the OpenAPI
schema, so the frozen contract is unaffected (see tests/test_openapi_contract.py).

Angular routes client-side, so an unknown sub-path must boot the shell instead of
404ing — ``StaticFiles(html=True)`` only does that for *directory* requests, so
the 404 fallback below is what makes deep links work. It cannot mask the BFF:
StudioProxyMiddleware rewrites ``/studio/api/*`` out of ``/studio`` before routing
happens, and the auth router is registered before this mount.

Caching (Paket 4b, A1): ``index.html`` is ``no-cache`` — without a header the
browser kept it heuristically and showed the old Studio after a deploy, pointing
at files that no longer exist. Angular's hashed bundles are immutable, as for
the widget. A missing path WITH a file extension is a 404, not the shell: a
stale ``styles-*.css`` answered with ``200 text/html`` was dropped by the
browser (``nosniff``), and the Studio stood there without styles.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from boerdi.settings import get_settings

log = logging.getLogger("startup")

_INDEX = "index.html"

#: What ``ng build`` emits with a content hash in the name; a new build gets new
#: names, so these never change under a URL.
_GEHASHT = re.compile(r"^(?:main|chunk|styles|polyfills|worker)-[A-Za-z0-9_-]{8}\.(?:js|css)$")
_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"

#: Endings of files a build or a page asks for. A missing one is a 404, never the
#: shell — a client route has no such ending, a stale bundle name does.
_DATEI_ENDUNGEN = frozenset({
    ".js", ".mjs", ".css", ".map", ".json", ".html", ".ico", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf", ".txt",
    ".webmanifest", ".xml",
})


class SpaFiles(StaticFiles):
    """StaticFiles that serves ``index.html`` for unknown paths (SPA routing)."""

    def file_response(
        self, full_path: str | os.PathLike[str], stat_result: os.stat_result,
        scope: Scope, status_code: int = 200,
    ) -> Response:
        # After Starlette's own response, so a 304 carries the rule as well.
        response = super().file_response(full_path, stat_result, scope, status_code)
        name = os.path.basename(full_path)
        if name == _INDEX:
            response.headers["Cache-Control"] = _NO_CACHE
        elif _GEHASHT.match(name):
            response.headers["Cache-Control"] = _IMMUTABLE
        return response

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
            teile = path.replace("\\", "/").split("/")
            endung = os.path.splitext(teile[-1])[1].lower()
            if exc.status_code != 404 or teile[0] == "api" or endung in _DATEI_ENDUNGEN:
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
