"""Die Umwandlung im eigenen Prozess — mit Frist, Speichergrenze und Vorprüfung (Paket 9).

Review Paket 7 (MAJOR 6): markitdown lief im Chat-Prozess, ohne Zeit-, Speicher- oder
Seitengrenze und beliebig viele zugleich; ``asyncio.to_thread`` lässt sich nicht
abbrechen, begrenzt war nur der Upload (25 MB). Gemessen: ein XLSX mit 0,45 MB
brauchte 10,5 s und rund 150 MB, und laut ``api/rag`` beenden PDFs über etwa 15 MB
einen Server mit 2 GB. Dazu entpackte markitdown eine ``.zip`` samt aller Einträge
(V4, ZIP-Bombe).

Jetzt:

* **Ein Kindprozess je Umwandlung** (``spawn``), immer nur einer zugleich (je
  Prozess); nach ``RAG_CONVERSION_TIMEOUT_S`` wird er beendet. Der Start kostet rund
  zwei Sekunden (markitdown lädt) — für den Import im Studio unerheblich.
* **Speicher:** unter Linux ``RLIMIT_DATA`` (Heap und anonyme Abbildungen,
  ``RAG_CONVERSION_MAX_MB``, 0 = aus) und ``oom_score_adj`` 1000 — wird der Speicher
  trotzdem knapp, beendet der Kernel den Kindprozess, nicht den Chat. Unter Windows
  (Entwicklung) gibt es beides nicht; Frist und Trennung bleiben.
* **Vorprüfung** vor der Umwandlung (:func:`vorpruefung`, läuft mit im Kind): ein
  ZIP-Container (DOCX, PPTX, XLSX, EPUB, ZIP) nach entpackter Größe und Zahl der
  Einträge, ein PDF nach Seitenzahl.

Eine eigene, kleinere Grenze für Office und PDF (Vorschlag im Review) gibt es nicht:
Mit Trennung, Speicher- und Seitengrenze schützte sie nichts mehr, sie wiese nur
gültige Dateien früher ab.
"""

from __future__ import annotations

import asyncio
import io
import logging
import multiprocessing
import pathlib
import zipfile
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler, kurz
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Entpackte Größe eines ZIP-Containers (alle Einträge zusammen) in MB.
MAX_ENTPACKT_MB = 200
#: Einträge eines ZIP-Containers.
MAX_EINTRAEGE = 5000
#: Seiten eines PDF.
MAX_PDF_SEITEN = 1000
#: Zeichen des umgewandelten Texts (Review Paket 9) — das Doppelte des Upload-Deckels
#: für reinen Text (25 MB). Der Text reist per ``pickle`` in den Chat-Prozess, und
#: dort gilt die Speichergrenze des Kindes nicht mehr; ein XLSX unter dem Deckel
#: ergibt leicht Hunderte MB Markdown.
MAX_TEXT_ZEICHEN = 50_000_000

_MB = 1024 * 1024

_semaphores: dict[int, asyncio.Semaphore] = {}


def _einer() -> asyncio.Semaphore:
    """Je Ereignisschleife ein Semaphor (wie ``llm_parallel``): einer zugleich."""
    schleife = id(asyncio.get_running_loop())
    if schleife not in _semaphores:
        _semaphores[schleife] = asyncio.Semaphore(1)
    return _semaphores[schleife]


async def im_kindprozess(funktion: Callable[..., str], *args: Any) -> str:
    """``funktion(*args)`` in einem eigenen Prozess — das Ergebnis oder ein
    :class:`Umwandlungsfehler`. ``funktion`` muss auf Modulebene stehen (``spawn``
    importiert sie über ihren Namen). Wirft nur, wenn kein Kindprozess startet: das
    ist ein Fehler des Servers (500), kein Fehler der Datei (Review Paket 9)."""
    s = get_settings()
    async with _einer():
        return await asyncio.to_thread(
            _ausfuehren, funktion, args, s.rag_conversion_timeout_s, s.rag_conversion_max_mb)


def _ausfuehren(funktion: Callable[..., str], args: tuple[Any, ...],
                frist_s: float, max_mb: int) -> str:
    kontext = multiprocessing.get_context("spawn")
    lesen, schreiben = kontext.Pipe(duplex=False)
    prozess = kontext.Process(target=_kind, args=(funktion, args, max_mb, schreiben),
                              daemon=True)
    prozess.start()
    schreiben.close()
    try:
        if not lesen.poll(frist_s):
            logger.warning("Umwandlung nach %ss abgebrochen (%s)", frist_s, funktion.__name__)
            return Umwandlungsfehler(f"Fehler: Umwandlung länger als {frist_s:g} s",
                                     art="umwandlung_zu_langsam", wert=frist_s)
        try:
            ergebnis: str = lesen.recv()
            return ergebnis
        except EOFError:
            # Ohne Antwort beendet — meist der Kernel (Speicher), sonst ein Absturz.
            prozess.join(5)
            logger.warning("Umwandlung ohne Ergebnis beendet (Exitcode %s)", prozess.exitcode)
            return Umwandlungsfehler("Fehler: Umwandlung abgebrochen",
                                     art="umwandlung_zu_gross", wert=max_mb or None,
                                     detail=f"Exitcode {prozess.exitcode}")
    finally:
        lesen.close()
        if prozess.is_alive():
            prozess.kill()
        prozess.join(5)


def _kind(funktion: Callable[..., str], args: tuple[Any, ...], max_mb: int,
          verbindung: Connection) -> None:
    """Im Kindprozess: Grenzen setzen, umwandeln, Ergebnis zurückschicken."""
    _grenzen_setzen(max_mb)
    try:
        ergebnis = funktion(*args)
    except MemoryError:
        ergebnis = Umwandlungsfehler("Fehler: Umwandlung braucht zu viel Speicher",
                                     art="umwandlung_zu_gross", wert=max_mb or None)
    except BaseException as e:  # noqa: BLE001 — der Elternprozess braucht eine Antwort
        ergebnis = Umwandlungsfehler(f"Fehler beim Konvertieren: {type(e).__name__}: {e}",
                                     detail=f"{type(e).__name__}: {kurz(e)}")
    if not isinstance(ergebnis, Umwandlungsfehler) and len(ergebnis) > MAX_TEXT_ZEICHEN:
        ergebnis = Umwandlungsfehler(f"Fehler: {len(ergebnis)} Zeichen Text",
                                     art="text_zu_lang", wert=MAX_TEXT_ZEICHEN / 1_000_000)
    try:
        verbindung.send(ergebnis)
    finally:
        verbindung.close()


def _grenzen_setzen(max_mb: int) -> None:
    """Unter Linux: zuerst geopfert werden und höchstens ``max_mb`` Heap (0 = frei)."""
    try:
        pathlib.Path("/proc/self/oom_score_adj").write_text("1000")
    except OSError:
        pass  # kein Linux oder keine Rechte — die Frist bleibt
    if max_mb <= 0:
        return
    try:
        import resource  # nur Unix
    except ImportError:
        return
    grenze = max_mb * _MB
    try:
        resource.setrlimit(resource.RLIMIT_DATA, (grenze, grenze))
    except (ValueError, OSError):
        logger.warning("RLIMIT_DATA %s MB ließ sich nicht setzen", max_mb)


def vorpruefung(quelle: str | bytes) -> Umwandlungsfehler | None:
    """Was vor der Umwandlung schon zu groß ist — sonst ``None`` (auch ohne Befund).

    ``quelle`` ist ein Dateipfad oder der geholte Rumpf einer Seite.
    """
    if isinstance(quelle, bytes):
        kopf = quelle[:5]
    else:
        with open(quelle, "rb") as f:
            kopf = f.read(5)
    if kopf.startswith(b"PK\x03\x04"):
        return _zip_pruefen(quelle)
    if kopf.startswith(b"%PDF"):
        return _pdf_pruefen(quelle)
    return None


def _zip_pruefen(quelle: str | bytes) -> Umwandlungsfehler | None:
    try:
        with zipfile.ZipFile(io.BytesIO(quelle) if isinstance(quelle, bytes) else quelle) as z:
            eintraege = z.infolist()
    except (zipfile.BadZipFile, OSError):
        return None
    entpackt = sum(e.file_size for e in eintraege)
    if len(eintraege) > MAX_EINTRAEGE or entpackt > MAX_ENTPACKT_MB * _MB:
        return Umwandlungsfehler(
            f"Fehler: entpackt {entpackt / _MB:.0f} MB in {len(eintraege)} Einträgen",
            art="entpackt_zu_gross", wert=MAX_ENTPACKT_MB)
    return None


def _pdf_pruefen(quelle: str | bytes) -> Umwandlungsfehler | None:
    seiten = _pdf_seiten(quelle)
    if seiten is not None and seiten > MAX_PDF_SEITEN:
        return Umwandlungsfehler(f"Fehler: {seiten} Seiten", art="zu_viele_seiten",
                                 wert=MAX_PDF_SEITEN)
    return None


def _pdf_seiten(quelle: str | bytes) -> int | None:
    """Die Seitenzahl aus dem Seitenbaum (``/Count``) — ohne die Seiten zu lesen."""
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import resolve1

    try:
        with (io.BytesIO(quelle) if isinstance(quelle, bytes) else open(quelle, "rb")) as f:
            dokument = PDFDocument(PDFParser(f))
            anzahl = resolve1(resolve1(dokument.catalog.get("Pages")).get("Count"))
    except Exception:  # noqa: BLE001 — verschlüsselt oder kaputt: die Umwandlung meldet es
        return None
    return anzahl if isinstance(anzahl, int) else None
