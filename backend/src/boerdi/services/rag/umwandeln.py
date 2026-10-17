"""Datei und Webseite → Markdown für den RAG-Import (P6, ALT-treu).

Aus ``services/rag/ingest.py`` herausgelöst (Paket 6, Refactor-Runde): dort
standen Umwandeln und Speichern in einer Datei über der 300-Zeilen-Regel.

Die Umwandlung selbst (``wandle_datei``, ``wandle_rumpf``) ist ALT-verbatim
(``rag_service.py``), läuft seit Paket 9 aber in einem eigenen Prozess mit Frist,
Speichergrenze und Vorprüfung (``umwandeln_kind``) — vorher im Chat-Prozess, wo
eine große Datei ihn anhalten oder beenden konnte. Fehler kommen als
:class:`Umwandlungsfehler` zurück, der Router übersetzt sie — nie geworfen. Der
URL-Weg ist über ``url_safety`` abgesichert (``assert_public_url`` vor jedem
Abruf, die Umleitungen prüfende ``make_ssrf_guarded_session`` für markitdown,
Audit T8/T9/N-2).
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import logging
import os
from collections.abc import Awaitable, Callable

from boerdi.services.rag.umwandeln_fehler import (
    FORMAT_NICHT_LESBAR,
    Umwandlungsfehler,
    format_nicht_lesbar,
    kurz,
)
from boerdi.services.rag.umwandeln_kind import im_kindprozess, vorpruefung
from boerdi.settings import get_settings

__all__ = ["FORMAT_NICHT_LESBAR", "URL_FRIST_S", "Umwandlungsfehler", "convert_to_markdown",
           "convert_url_to_markdown", "wandle_datei", "wandle_rumpf"]

logger = logging.getLogger(__name__)

#: Gesamtfrist eines URL-Abrufs in Sekunden (Paket 4, C5).
URL_FRIST_S = 60.0

#: Wo ``wandle_*`` läuft: Vorgabe ist der Kindprozess; Tests reichen einen Aufruf im
#: eigenen Prozess herein (dort wirken ihre Attrappen).
Ausfuehrer = Callable[..., Awaitable[str]]

_IMPORT_FEHLT = (
    "markitdown ImportError — auf dem Server fehlt eine Python-/OS-Dependency. "
    "Häufige Ursachen: pip install markitdown nicht ausgeführt; libmagic1 / "
    "poppler-utils / tesseract-ocr fehlen im Container.")


async def convert_to_markdown(file_path: str, *, ausfuehren: Ausfuehrer | None = None) -> str:
    """Convert any document to markdown using markitdown — in a child process.

    A failure comes back as :class:`Umwandlungsfehler`, never raised.
    """
    return await (ausfuehren or im_kindprozess)(wandle_datei, file_path)


def wandle_datei(file_path: str) -> str:
    """Die Umwandlung einer Datei — synchron; läuft im Kindprozess."""
    try:
        size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
    except Exception:
        size = -1
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        logger.exception("%s Datei: %s (%d bytes)", _IMPORT_FEHLT, file_path, size)
        return Umwandlungsfehler(f"Fehler beim Konvertieren (ImportError): {e}", art="server")
    if size > 0 and (zu_gross := vorpruefung(file_path)):
        return zu_gross
    try:
        return MarkItDown().convert(file_path).text_content
    except Exception as e:
        if format_nicht_lesbar(e):
            # Keine kaputte Datei, sondern ein Format, das dieses Image nicht
            # liest (Paket 4, C5) — seit Paket 7 (P6) etwa .doc, .ppt oder Audio;
            # PDF, DOCX, PPTX und XLSX liest es. Der Router macht daraus 415.
            logger.warning("markitdown liest das Format von %s nicht: %s",
                           file_path, type(e).__name__)
            return Umwandlungsfehler(f"{FORMAT_NICHT_LESBAR}: {type(e).__name__}", art="format")
        # Volltext-Trace ins Backend-Log — die HTTP-Antwort kürzt nur die
        # Top-Zeile mit, daher hier explizit logger.exception aufrufen.
        logger.exception(
            "markitdown convert failed für %s (%d bytes): %s",
            file_path, size, e,
        )
        return Umwandlungsfehler(f"Fehler beim Konvertieren: {type(e).__name__}: {e}",
                                 detail=f"{type(e).__name__}: {e}")


async def convert_url_to_markdown(url: str, *, ausfuehren: Ausfuehrer | None = None) -> str:
    """Fetch a URL and convert to markdown using markitdown.

    SSRF-Schutz via ``url_safety.assert_public_url`` (zentraler Choke-Point,
    Audit T8/T9): blockt Nicht-http(s)-Schemata und private/interne Netzbereiche
    (Loopback, link-local inkl. Cloud-Metadaten 169.254.169.254, private Ranges).
    Bei einem Verstoß wird KEIN Netz-Fetch versucht — die Funktion kehrt (wie bei
    anderen Fehlern) mit einem "Fehler:"-String zurück, den der Router in 400
    übersetzt.

    Seit Paket 4 (C5, externes Audit F17) holt ``url_safety.hole_begrenzt`` den
    Rumpf — mit Frist und Bytedeckel —, und markitdown wandelt nur noch um.
    Vorher holte markitdown selbst, ohne Frist und mit dem ganzen Rumpf im
    Speicher. Auch die DNS-Prüfung läuft im Thread: ``getaddrinfo`` blockierte
    den Event-Loop. Seit Paket 6 (B2) ist der Abruf asynchron, und die Frist
    gilt auch für Kopfzeilen und Umleitungen; jeder Umleitungs-Schritt geht
    durch den Wächter. Seit Paket 9 wandelt ein Kindprozess (``wandle_rumpf``).
    """
    from boerdi.services import url_safety

    # Wie beim Datei-Weg: melden statt werfen, und dann ohne Abruf (Paket 4c, A1).
    # ``find_spec`` statt Import — markitdown lädt erst im Kindprozess.
    if importlib.util.find_spec("markitdown") is None:
        logger.error("%s (URL-Import)", _IMPORT_FEHLT)
        return Umwandlungsfehler("Fehler beim Konvertieren (ImportError): markitdown fehlt",
                                 art="server")
    try:
        await asyncio.to_thread(url_safety.assert_public_url, url)
    except url_safety.UnsafeUrlError as e:
        return _adressfehler(e)
    max_mb = get_settings().max_ingest_mb
    try:
        rumpf, typ = await url_safety.hole_begrenzt(
            url, max_bytes=max_mb * 1024 * 1024, frist_s=URL_FRIST_S)
    except url_safety.DownloadAbgebrochen as e:
        return Umwandlungsfehler(f"Fehler: {e}", art=e.grund, wert=e.wert)
    except url_safety.UnsafeUrlError as e:  # ein Umleitungs-Schritt nach innen (B2)
        return _adressfehler(e)
    except Exception as e:
        return Umwandlungsfehler(f"Fehler beim Konvertieren: {e}", art="abruf",
                                 detail=kurz(e))
    mime, _, rest = typ.partition(";")
    charset = rest.split("charset=", 1)[1].strip() if "charset=" in rest else None
    return await (ausfuehren or im_kindprozess)(
        wandle_rumpf, rumpf, url, mime.strip() or None, charset)


def _adressfehler(fehler: Exception) -> Umwandlungsfehler:
    """Eine abgewiesene Adresse — der Grund als Art, ohne den englischen Text des
    Wächters (Paket 9); ein unbekannter Name nennt sich selbst."""
    if getattr(fehler, "grund", "") == "unbekannt":
        return Umwandlungsfehler(f"Fehler: {fehler}", art="adresse_unbekannt",
                                 detail=getattr(fehler, "host", ""))
    return Umwandlungsfehler(f"Fehler: {fehler}", art="adresse")


def wandle_rumpf(rumpf: bytes, url: str, mime: str | None, charset: str | None) -> str:
    """Die Umwandlung eines geholten Rumpfs — synchron; läuft im Kindprozess."""
    from boerdi.services import url_safety

    try:
        from markitdown import MarkItDown, StreamInfo
    except ImportError as e:
        logger.exception("%s (URL-Import)", _IMPORT_FEHLT)
        return Umwandlungsfehler(f"Fehler beim Konvertieren (ImportError): {e}", art="server")
    if zu_gross := vorpruefung(rumpf):
        return zu_gross
    try:
        # N-2 (Audit 2026-07-10): Guard-Session prüft AUCH Redirect-Ziele.
        # markitdown holt bei manchen Formaten selbst nach (etwa Transkripte);
        # auch dort darf kein 302 auf eine interne Adresse durchgehen.
        mid = MarkItDown(requests_session=url_safety.make_ssrf_guarded_session())
        info = StreamInfo(url=url, mimetype=mime, charset=charset)
        return mid.convert_stream(io.BytesIO(rumpf), stream_info=info).text_content
    except Exception as e:
        if format_nicht_lesbar(e):
            # Wie beim Datei-Upload (C5): ein Link auf ein Format ohne Wandler im
            # Image ist keine kaputte Seite (Prüfer 2026-10-04; ein PDF-Link
            # liest sich seit Paket 7, P6).
            logger.warning("markitdown liest das Format einer URL nicht: %s",
                           type(e).__name__)
            return Umwandlungsfehler(f"{FORMAT_NICHT_LESBAR}: {type(e).__name__}",
                                     art="format")
        return Umwandlungsfehler(f"Fehler beim Konvertieren: {e}", detail=kurz(e))
