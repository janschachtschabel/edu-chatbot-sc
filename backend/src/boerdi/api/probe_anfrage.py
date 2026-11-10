"""Paket AS-8a (Plan 2026-11-09 §5n, P-1): Ist diese Chat-Anfrage eine Probe der
Studio-Vorschau?

Das Widget schickt ``probe: true``, wenn die Einbettung das Attribut ``probe`` trägt. Recht gibt
erst das Studio-Cookie: Die Vorschau läuft auf derselben Herkunft wie das Backend, das Cookie
(``SameSite=strict``) geht also mit, und keine fremde Seite kann es mitschicken. Ohne gültiges
Cookie weist ``pruefe_probe`` den Zug ab (403 ``probe_ohne_recht``) — nie läuft er still echt. Ein
falsches Cookie zählt wie im Studio als Fehlversuch (``studio_auth.authorize_request``).
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from starlette.requests import HTTPConnection

from boerdi.api.schemas import ChatRequest
from boerdi.api.studio_auth import COOKIE_NAME, authorize_request

logger = logging.getLogger(__name__)


def probe_erlaubt(request: HTTPConnection, req: ChatRequest) -> bool:
    """``True`` nur für ``req.probe`` mit Studio-Recht; ohne Flag wird das Cookie nicht gelesen."""
    if not req.probe:
        return False
    if authorize_request(request, request.cookies.get(COOKIE_NAME)) is None:
        return True
    logger.info("Probe ohne Studio-Recht angefragt")
    return False


def vorschau_erlaubt(request: HTTPConnection, req: ChatRequest) -> bool:
    """Plan 2026-11-10, TB-E2: ein Gespräch der Studio-Vorschau — ``True`` nur für
    ``req.vorschau`` mit Studio-Recht. Ohne gültiges Cookie bleibt das Flag wirkungslos, aber
    **ohne** 403: es ändert am Zug nichts, nur ob die Sitzung als Betrieb zählt. Ohne Flag wird das
    Cookie nicht gelesen (ein falsches Cookie zählt sonst als Fehlversuch)."""
    if not req.vorschau:
        return False
    return authorize_request(request, request.cookies.get(COOKIE_NAME)) is None


def pruefe_probe(request: HTTPConnection, req: ChatRequest) -> bool:
    """Vorspann beider Chat-Endpunkte (Review AS-8a, Befund 3): eine Probe ohne Studio-Recht läuft
    nie still als echter Zug — die Person hielte ihn für einen Trockenlauf. 403
    ``probe_ohne_recht`` (abgelaufenes Cookie, gedrehtes Passwort, Sperre nach Fehlversuchen)."""
    if req.probe and not probe_erlaubt(request, req):
        raise HTTPException(status_code=403, detail="probe_ohne_recht")
    return req.probe
