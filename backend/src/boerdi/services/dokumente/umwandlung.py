"""Ein hochgeladenes Dokument → Markdown (Paket U3-2a, Plan 2026-11-04 §16.6).

Dieselbe Umwandlung wie der RAG-Import (``wandle_datei`` mit Speichergrenze), davor die Grenzen
des Chats: Seiten (Studio ``max_seiten``) und entpackte Größe (ZIP-Bombe). **Alles, was eine Datei
parst, läuft im Kindprozess** (:func:`pruefe_und_wandle`, Review U3-2 Befund 2): pdfminer brauchte
für ein kaputtes 8-MB-PDF im Elternprozess 16 s — die Ereignisschleife stand so lange. Text und
Markdown brauchen keinen Kindprozess.

Frist und Platz (Review Befund 4): Der Kindprozess bekommt die Frist des Uploads und wird danach
beendet (er gibt den einzigen Platz frei, den auch RAG-Importe nutzen); auf den Platz wartet ein
Upload höchstens :data:`PLATZ_FRIST_S`, sonst ``ausgelastet``. Mehr als :data:`MAX_WARTENDE`
zugleich bekommen sofort ``ausgelastet``; der Zähler sinkt erst, wenn der Lauf wirklich vorbei ist.

Die Datei liegt nur für die Umwandlung auf der Platte: in einem eigenen Verzeichnis (0700),
benannt nach der erkannten Art — nie nach dem Namen aus dem Browser —, gelöscht im ``finally``.
Fehler kommen als :class:`Umwandlungsfehler` zurück, nie geworfen.
"""

from __future__ import annotations

import asyncio
import functools
import os
import shutil
import tempfile
from dataclasses import dataclass

from boerdi.domain.dokument_art import ENDUNG
from boerdi.services.rag.umwandeln import Ausfuehrer, wandle_datei
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler
from boerdi.services.rag.umwandeln_kind import im_kindprozess, pdf_seiten, vorpruefung

#: Mehr Zeichen bewahrt die Ablage nicht; der Rest gilt als gekürzt (Befund ``gekuerzt``).
MAX_ZEICHEN = 2_000_000
#: So viele Umwandlungen dürfen zugleich laufen oder warten.
MAX_WARTENDE = 3
#: So lange wartet ein Upload höchstens auf den Platz im Kindprozess.
PLATZ_FRIST_S = 20.0
#: Letzte Wache über Platz und Frist hinaus (der Kindprozess hält beide selbst ein).
_PUFFER_S = 10.0
#: Trenner zwischen Seitenzahl und Text im Ergebnis des Kindprozesses (der überträgt nur Text).
_TRENNER = "\x1e"

_wartende = 0


@dataclass(frozen=True)
class Gewandelt:
    markdown: str
    seiten: int | None
    gekuerzt: bool


def pruefe_und_wandle(pfad: str, max_seiten: int) -> str:
    """Im Kindprozess: Seiten bzw. ZIP-Grenzen prüfen, dann umwandeln. Ergebnis: Seitenzahl
    (leer außer bei PDF), :data:`_TRENNER`, Markdown — oder ein :class:`Umwandlungsfehler`."""
    seiten = None
    if pfad.endswith(".pdf"):
        seiten = pdf_seiten(pfad)
        if seiten is not None and seiten > max_seiten:
            return Umwandlungsfehler(f"Fehler: {seiten} Seiten", art="zu_viele_seiten",
                                     wert=max_seiten)
    elif zu_gross := vorpruefung(pfad):
        return zu_gross
    text = wandle_datei(pfad, vorgeprueft=True)
    if isinstance(text, Umwandlungsfehler):
        return text
    return f"{'' if seiten is None else seiten}{_TRENNER}{text}"


def _schreiben(pfad: str, rumpf: bytes) -> None:
    with open(pfad, "wb") as f:
        f.write(rumpf)


async def wandle(rumpf: bytes, art: str, *, max_seiten: int, frist_s: float,
                 ausfuehren: Ausfuehrer | None = None) -> Gewandelt | Umwandlungsfehler:
    """``rumpf`` (Art aus :func:`boerdi.domain.dokument_art.erkenne`) als Markdown."""
    if art in ("txt", "md"):
        return _fertig(_text(rumpf), None)
    global _wartende
    if _wartende >= MAX_WARTENDE:
        return Umwandlungsfehler("Fehler: Umwandlung ausgelastet", art="ausgelastet")
    _wartende += 1
    verzeichnis = None
    try:
        # Querschnitts-Review (NIT): bis 25 MB schreiben und löschen nicht in der Ereignisschleife.
        # Das Verzeichnis entsteht vorher hier — ein Abbruch während des Schreibens räumt es im
        # ``finally`` mit weg (Review Q1, Befund 8).
        verzeichnis = tempfile.mkdtemp(prefix="boerdi-dok-")   # 0700 laut mkdtemp
        pfad = os.path.join(verzeichnis, "dokument" + ENDUNG[art])
        await asyncio.to_thread(_schreiben, pfad, rumpf)
        rufe = ausfuehren or functools.partial(im_kindprozess, frist_s=frist_s,
                                               platz_frist_s=PLATZ_FRIST_S)
        try:
            ergebnis = await asyncio.wait_for(rufe(pruefe_und_wandle, pfad, max_seiten),
                                              frist_s + PLATZ_FRIST_S + _PUFFER_S)
        except TimeoutError:
            return Umwandlungsfehler(f"Fehler: Umwandlung länger als {frist_s:g} s",
                                     art="umwandlung_zu_langsam", wert=frist_s)
    except OSError:
        return Umwandlungsfehler("Fehler: Datei nicht ablegbar", art="server")
    finally:
        _wartende -= 1
        if verzeichnis:
            await asyncio.to_thread(shutil.rmtree, verzeichnis, ignore_errors=True)
    if isinstance(ergebnis, Umwandlungsfehler):
        return ergebnis
    kopf, _, text = ergebnis.partition(_TRENNER)
    return _fertig(text, int(kopf) if kopf.isdigit() else None)


def _text(rumpf: bytes) -> str:
    try:
        return rumpf.decode("utf-8-sig")
    except UnicodeDecodeError:
        return rumpf.decode("cp1252", errors="replace")


def _fertig(text: str, seiten: int | None) -> Gewandelt:
    # NUL lässt Postgres in ``text`` nicht zu; es trägt in einem Dokument nie Inhalt.
    text = text.replace("\x00", "")
    gekuerzt = len(text) > MAX_ZEICHEN
    return Gewandelt(markdown=text[:MAX_ZEICHEN], seiten=seiten, gekuerzt=gekuerzt)
