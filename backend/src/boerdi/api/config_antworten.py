"""Die Antworten auf ein gescheitertes Konfig-Schreiben (400, 409).

Aus ``api/config_guards.py`` herausgelöst (Paket 6, Refactor-Runde): dort stehen
die Regeln, die ein Dokument und sein Schlüssel erfüllen müssen; hier, was der
Server antwortet, wenn ein Schreiben scheitert — Wert nicht speicherbar (Paket
4b A4, Paket 4c A2) oder Konflikt beim bedingten Schreiben (Paket 4, D5).
"""

import logging
from datetime import UTC

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from boerdi.api.deps import request_locale
from boerdi.i18n import Locale, msg
from boerdi.services.config_conflict import BereichNichtSpeicherbar, ConfigConflict

logger = logging.getLogger(__name__)


async def nicht_speicherbar_antwort(request: Request, exc: Exception) -> JSONResponse:
    """400 for a value that cannot be stored — refused by Postgres (Paket 4b, A4)
    or not JSON at all (Paket 4c, A2).

    One handler for every config write — restore, seed apply, form and raw
    text. Before, such a write ended as a 500 without naming the area.

    The failed transaction writes nothing, but it is not always the whole
    request (review 4b): restore and seed apply write every area in one
    transaction, the ALT bulk routes (personas, patterns, tone modifiers) one
    per area, so earlier areas stay saved. The message says which case it is.

    The log line names the area and the cause, never the content: the 500's
    traceback used to be the only trail (second review 4b). The cause is the
    SQLSTATE, or for a value JSON cannot hold the error type (Paket 4c, A2).
    """
    fehler = exc if isinstance(exc, BereichNichtSpeicherbar) else BereichNichtSpeicherbar("?")
    if fehler.sqlstate:
        ursache = f"SQLSTATE {fehler.sqlstate}"
    else:
        ursache = type(fehler.__cause__).__name__ if fehler.__cause__ else "?"
    logger.warning("config area %r not storable (%s)", fehler.area, ursache)
    key = "config.notStorableAll" if fehler.ganzer_vorgang else "config.notStorable"
    text = msg(request_locale(request), key, area=fehler.area)
    return JSONResponse(status_code=400, content={"detail": text})


def konflikt_antwort(e: ConfigConflict, lang: Locale, *, anlegen: bool = False) -> HTTPException:
    """409 for a conditional write that found another state (Paket 4, D5).

    ``detail`` is an object: ``message`` for any client, and ``version``,
    ``updated_by``, ``updated_at`` (ISO, UTC) for the Studio, which names who
    changed what and when in the editor's own language.
    """
    cur = e.current or {}
    version = cur.get("version")
    updated_by = cur.get("updated_by")
    when = cur.get("updated_at")
    if anlegen and e.current is not None:
        text = msg(lang, "config.exists", area=e.area)
    elif e.current is None:
        text = msg(lang, "config.conflictGone")
    else:
        text = msg(lang, "config.conflict", version=version, who=updated_by or "?",
                   when=when.astimezone(UTC).strftime("%Y-%m-%d %H:%M") if when else "?")
    stamp = when.astimezone(UTC).isoformat() if when else None
    return HTTPException(status_code=409, detail={
        "message": text, "version": version, "updated_by": updated_by, "updated_at": stamp,
    })
