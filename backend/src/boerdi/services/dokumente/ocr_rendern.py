"""Seiten einer gescannten PDF als JPEG rendern — im Kindprozess (Plan 2026-11-19, Paket C).

Review Paket C, Befund 1 (CRITICAL): PDFium dekodiert eingebettete Bilder in voller Größe, egal wie
klein die Seite gerendert wird — eine 380-KB-PDF mit einem 20000²-Bild kostete im Backend-Prozess
456 MB, eine von 2 MB hätte den Pod beendet. Deshalb:

- :func:`seiten_rendern` läuft über ``umwandlung.im_kind_mit_datei`` im Kindprozess (Frist,
  ``oom_score_adj``, ein Platz wie die Umwandlung) mit eigener Speichergrenze
  (``ocr.RENDER_MAX_MB``, 512 MB ``RLIMIT_DATA``); zurück kommt nur Text. **Die harte Grenze ist
  der Kindprozess**: wird ihm der Speicher zu knapp, endet er, nicht das Backend. Unter Windows
  (Entwicklung) gibt es kein ``RLIMIT_DATA``.
- **Pixelbudget je Seite** (:data:`MAX_BILD_PIXEL`) — nur eine Vorprüfung: die Pixelgröße der
  Bilder auf der Seite und in Form-XObjects bis zur Tiefe 8 steht in ihren Metadaten, gelesen ohne
  zu dekodieren; darüber wird die Seite nicht gerendert (``b""``). Bilder in Kachelmustern, Masken
  (``/SMask``), Type3-Glyphen und tieferen Formen sieht sie nicht (zweites Review, 1: +150–280 MB
  im Kind), ein Inline-Bild dekodiert PDFium schon beim Laden der Seite.
- Anmerkungen werden nicht gezeichnet (``draw_annots=False``): ihre Erscheinung (``/AP``) kann ein
  Bild tragen, und für den Text der Seite braucht es sie nicht.
- Das Seitenbild ist höchstens :data:`MAX_PIXEL` an der längsten Kante (Riesenseiten) und höchstens
  :data:`MAX_JPEG_BYTES` groß (verrauschte Scans: erst Qualität, dann Kante herunter).

Nur leichte Importe: ``spawn`` lädt dieses Modul im Kind über seinen Namen.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Final

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

logger = logging.getLogger(__name__)

DPI: Final = 150
#: Längste Kante eines Seitenbilds in Pixeln — A4 hat bei 150 DPI 1754.
MAX_PIXEL: Final = 2400
JPEG_QUALITAET: Final = 80
#: Pixel aller eingebetteten Bilder einer Seite zusammen — A4 als Scan mit 600 DPI hat 35 MP.
#: Graustufen kosten 1 Byte je Pixel, Farbe 3–4: 60 MP sind höchstens rund 240 MB im Kind.
MAX_BILD_PIXEL: Final = 60_000_000
#: Größtes JPEG je Seite — Rauschen ergab bei 2400 px über 3 MB (zweites Review, 10).
MAX_JPEG_BYTES: Final = 1_500_000
#: Stufen, wenn das JPEG zu groß ist: (Qualität, längste Kante).
_KLEINER: Final = ((60, MAX_PIXEL), (60, 1600), (50, 1200))
#: Trenner im Ergebnis des Kindprozesses (der überträgt Text): Seitenzahl, dann je Seite Base64.
TRENNER: Final = "\x1e"


def _bild_pixel(seite: Any) -> int:
    pixel = 0
    for objekt in seite.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=8):
        breite, hoehe = objekt.get_px_size()
        pixel += max(0, breite) * max(0, hoehe)
    return pixel


def _kodieren(bild: Any, qualitaet: int) -> bytes:
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", quality=qualitaet)
    return puffer.getvalue()


def _jpeg(seite: Any) -> bytes:
    breite, hoehe = seite.get_size()
    skala = min(DPI / 72, MAX_PIXEL / max(breite, hoehe, 1.0))
    bild = seite.render(scale=skala, grayscale=True, draw_annots=False).to_pil().convert("L")
    jpeg = _kodieren(bild, JPEG_QUALITAET)
    for qualitaet, kante in _KLEINER:
        if len(jpeg) <= MAX_JPEG_BYTES:
            break
        if max(bild.size) > kante:
            bild.thumbnail((kante, kante))
        jpeg = _kodieren(bild, qualitaet)
    return jpeg


def bilder(rumpf: bytes | str, seiten_max: int) -> tuple[int, list[bytes]]:
    """``(Seiten der PDF, JPEG je Seite bis seiten_max)``; ``b""`` für eine Seite, die sich nicht
    rendern ließ oder über dem Pixelbudget liegt. Eine unlesbare PDF: ``(0, [])``. Nur im
    Kindprozess aufrufen (Tests ausgenommen)."""
    try:
        dok = pdfium.PdfDocument(rumpf)
    except pdfium.PdfiumError:
        return 0, []
    try:
        aus: list[bytes] = []
        for i in range(min(len(dok), seiten_max)):
            seite = dok[i]
            try:
                if (pixel := _bild_pixel(seite)) > MAX_BILD_PIXEL:
                    logger.info("Texterkennung: Seite %d über dem Pixelbudget (%d MP)", i + 1,
                                pixel // 1_000_000)
                    aus.append(b"")
                else:
                    aus.append(_jpeg(seite))
            except (pdfium.PdfiumError, OSError, ValueError) as fehler:
                logger.info("Texterkennung: Seite %d nicht gerendert (%s)", i + 1,
                            type(fehler).__name__)
                aus.append(b"")
            finally:
                seite.close()
        return len(dok), aus
    finally:
        dok.close()


def seiten_rendern(pfad: str, seiten_max: int) -> str:
    """Im Kindprozess: :func:`bilder` als Text (Seitenzahl, :data:`TRENNER`, Base64 je Seite)."""
    seiten, jpegs = bilder(pfad, seiten_max)
    return TRENNER.join([str(seiten), *(base64.b64encode(j).decode("ascii") for j in jpegs)])


def zerlegen(text: str) -> tuple[int, list[bytes]]:
    """Das Ergebnis von :func:`seiten_rendern` zurück in ``(Seiten, JPEGs)``."""
    kopf, *teile = text.split(TRENNER)
    return (int(kopf) if kopf.isdigit() else 0), [base64.b64decode(t) for t in teile]
