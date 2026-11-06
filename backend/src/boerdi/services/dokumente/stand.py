"""Das Dokument der Sitzung für einen Zug (Paket U3-2b, Plan 2026-11-04 §16.6).

Der Strukturentwurf liest es serverseitig — sein Text läuft nie durch die KI-Antwort des Zugs,
nur gedeckelte Auszüge gerahmt in die eigenen Aufrufe des Dienstes. :func:`lader` gibt eine
Funktion, die das Dokument beim ersten Bedarf lädt (und sich das Ergebnis merkt): ein Zug ohne
``aus_dokument`` zahlt keine Abfrage, und die zwei Millionen Zeichen liegen nicht in jedem Zug.

Beim Laden beginnt die Frist neu (``beruehren``, „24 h nach letzter Nutzung“). Danach geht die
Verbindung in den Pool zurück — es folgen LLM-Aufrufe (``db/verbindung``).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.dokument_gliederung import Abschnitt
from boerdi.services.config_loader.upload import load_upload_config
from boerdi.services.dokumente import ablage
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DokumentStand:
    upload_id: str
    name: str
    format: str
    befund: dict[str, Any]
    abschnitte: list[Abschnitt]
    markdown: str


DokumentLader = Callable[[], Awaitable[DokumentStand | None]]


def _abschnitte(roh: Any) -> list[Abschnitt] | None:
    if not isinstance(roh, list):
        return None
    try:
        return [Abschnitt(**a) for a in roh]
    except TypeError:
        return None


async def laden(session: Any, session_id: str) -> DokumentStand | None:
    """Das Dokument — oder ``None``: keins da, abgelaufen, unlesbar, gerade nicht erlaubt (das
    Studio hat abgeschaltet, die Anmeldung fehlt; Review U3-2 Befund 7) oder die Datenbank streikt
    (dann sagt der Dienst ``kein_dokument`` statt den Werkzeugaufruf zu beenden)."""
    from boerdi.ui_module.dienst_upload import dokument_erlaubt

    if not dokument_erlaubt():
        return None
    aufrufer = aufrufer_kennung() if has_personal_auth() else None
    try:
        zeile = await ablage.aktuelles(session, session_id, aufrufer)
        if zeile is None:
            return None
        abschnitte = _abschnitte(zeile.gliederung)
        if abschnitte is None:
            logger.warning("Dokument der Sitzung: Gliederung unlesbar, wird nicht genutzt")
            return None
        await ablage.beruehren(session, zeile.id, ttl_h=load_upload_config().aufbewahrung_h)
        await session.commit()
        return DokumentStand(upload_id=zeile.id, name=zeile.name, format=zeile.format,
                             befund=dict(zeile.befund or {}), abschnitte=abschnitte,
                             markdown=zeile.markdown)
    except SQLAlchemyError as fehler:
        logger.warning("Dokument der Sitzung nicht lesbar (%s)", type(fehler).__name__)
        try:
            await session.rollback()
        except SQLAlchemyError:
            logger.debug("Rollback nach Lesefehler gescheitert", exc_info=True)
        return None
    finally:
        await verbindung_freigeben(session)


def lader(session: Any, session_id: str) -> DokumentLader:
    """Lädt beim ersten Aufruf, danach dasselbe Ergebnis (auch ``None``)."""
    gemerkt: list[DokumentStand | None] = []

    async def holen() -> DokumentStand | None:
        if not gemerkt:
            gemerkt.append(await laden(session, session_id))
        return gemerkt[0]

    return holen
