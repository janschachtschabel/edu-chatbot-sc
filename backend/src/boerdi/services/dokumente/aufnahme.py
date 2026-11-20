"""Ein hochgeladenes Dokument aufbereiten (Paket U3-2a, Plan 2026-11-04 §16.6).

Art (Magic Bytes) → Umwandlung (``umwandlung.wandle``) → bereinigen → Gliederung → „kein Text?“
→ Moderation (Übersicht + Anfang) → Befund. Plan 2026-11-19, Paket C (C2): ist eine PDF gescannt und
gibt der Aufrufer eine Texterkennung mit (``ocr_lesen``, nur der Weg „Hier im Chat“), liest sie die
Seiten; danach derselbe Weg, der Befund trägt die Warnung ``ocr``. Kein HTTP, keine Datenbank:
zurück kommt entweder
:class:`Aufbereitet` oder eine :class:`Abweisung` mit Status und Code, die der Endpunkt als
``detail`` ausliefert — nie ein Text des Servers (der bleibt im Log, ohne Dateinamen).
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any, Final

from boerdi.domain.dokument_art import erkenne, ist_bild
from boerdi.domain.dokument_befund import befund, gescannt
from boerdi.domain.dokument_gliederung import bereinigen, gliederung, uebersicht
from boerdi.services.dokumente.ocr import OcrGrenze, OcrLesen
from boerdi.services.dokumente.umwandlung import wandle
from boerdi.services.rag.umwandeln import Ausfuehrer
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

MAX_NAME: Final = 200
#: So viel der Übersicht und des Anfangs liest die Moderation — mindestens, was die obere Ebene des
#: Strukturentwurfs davon sieht (``strukturentwurf_dienst.DOKUMENT_GLIEDERUNG``/``_ANFANG``, Review
#: U3-2 Befund 6; ein Wächtertest hält beide zusammen).
MODERATION_UEBERSICHT: Final = 8000
MODERATION_ANFANG: Final = 4000
VORSCHAU: Final = 8

#: Art eines :class:`Umwandlungsfehler` → (Status, Code).
_FEHLER: Final[dict[str, tuple[int, str]]] = {
    "zu_viele_seiten": (400, "zu_viele_seiten"),
    "entpackt_zu_gross": (400, "entpackt_zu_gross"),
    "umwandlung_zu_gross": (413, "zu_gross"),
    "text_zu_lang": (413, "zu_gross"),
    "umwandlung_zu_langsam": (504, "zu_langsam"),
    "ausgelastet": (503, "ausgelastet"),
    "format": (400, "art_unbekannt"),
    "datei": (400, "unlesbar"),
    "server": (500, "fehler"),
}


@dataclass(frozen=True)
class Abweisung:
    status: int
    code: str


@dataclass(frozen=True)
class Aufbereitet:
    format: str
    markdown: str
    befund: dict[str, Any]
    gliederung: list[dict[str, Any]]
    vorschau: list[str]


Moderieren = Callable[[str], Awaitable[dict[str, Any]]]


def sauberer_name(roh: str) -> str:
    """Der Dateiname als eine Zeile ohne Pfad und Steuerzeichen — für Anzeige und Rahmen."""
    name = re.split(r"[\\/]", roh or "")[-1]
    name = re.sub(r"\s+", " ", name)
    name = "".join(z for z in name if unicodedata.category(z) not in ("Cc", "Cf"))
    return " ".join(name.split())[:MAX_NAME] or "Dokument"


async def aufbereiten(rumpf: bytes, name: str, *, max_seiten: int, frist_s: float,
                      moderieren: Moderieren, ausfuehren: Ausfuehrer | None = None,
                      ocr_lesen: OcrLesen | None = None) -> Aufbereitet | Abweisung:
    if ist_bild(rumpf[:256]):
        return Abweisung(415, "bild")
    # In Threads (Review U3-2, Befund 1/2): ZIP-Verzeichnis, Bereinigen und Gliedern von bis zu zwei
    # Millionen Zeichen sollen die Ereignisschleife nicht anhalten.
    art = await asyncio.to_thread(erkenne, rumpf, name)
    if art is None:
        return Abweisung(400, "art_unbekannt")
    gewandelt = await wandle(rumpf, art, max_seiten=max_seiten, frist_s=frist_s,
                             ausfuehren=ausfuehren)
    if isinstance(gewandelt, Umwandlungsfehler):
        status, code = _FEHLER.get(gewandelt.art, (400, "unlesbar"))
        logger.info("Dokument (%s) nicht umgewandelt: %s", art, gewandelt.art)
        return Abweisung(status, code)
    md, bilder = await asyncio.to_thread(bereinigen, gewandelt.markdown)
    gekuerzt, ocr, text_seiten = gewandelt.gekuerzt, False, gewandelt.seiten
    if gescannt(md, gewandelt.seiten):
        if art != "pdf" or ocr_lesen is None:
            return Abweisung(400, "kein_text")
        try:
            gelesen = await ocr_lesen(rumpf)
        except OcrGrenze:
            return Abweisung(429, "grenze_ocr")
        logger.info("Dokument per Texterkennung: %d von %d Seiten gelesen", gelesen.gelesen,
                    gelesen.seiten)
        if not gelesen.gelesen:
            # Review 5: fehlten Frist oder Anbieter, kann ein neuer Versuch helfen — eine Seite,
            # die sich nicht rendern lässt (kaputt, Pixelbudget, zu schwer), bleibt es
            if gelesen.code == "zu_gross":
                return Abweisung(413, "zu_gross")
            return Abweisung(503, "ausgelastet") if gelesen.fehlend else Abweisung(400, "unlesbar")
        # die Bilder der Seiten sind jetzt gelesen — keine Warnung „bilder_entfernt“
        md, bilder = await asyncio.to_thread(bereinigen, gelesen.markdown)
        # Review 7: Text je Seite zählt über die gelesenen Seiten, nicht über die ganze PDF
        text_seiten = gelesen.gelesen
        if gescannt(md, text_seiten):
            return Abweisung(400, "kein_text")
        gekuerzt, ocr = gekuerzt or gelesen.gekuerzt, True
    abschnitte, gliederung_art = await asyncio.to_thread(gliederung, md)
    kurz, _ = uebersicht(abschnitte, MODERATION_UEBERSICHT)
    urteil = await moderieren(kurz + "\n\n" + md[:MODERATION_ANFANG])
    if urteil.get("flagged"):
        logger.info("Dokument (%s) von der Moderation abgewiesen", art)
        return Abweisung(400, "abgewiesen")
    if not urteil:
        # Ungeprüft (kein Zugang, Fehler): wie bei Nachrichten entscheidet MODERATION_FAILURE_MODE.
        if get_settings().moderation_failure_mode == "closed":
            return Abweisung(503, "pruefung_fehlt")
        logger.warning("Dokument (%s) ohne Moderation angenommen", art)
    werte = await asyncio.to_thread(
        lambda: befund(md, seiten=gewandelt.seiten, gekuerzt=gekuerzt, bilder=bilder,
                       abschnitte=abschnitte, gliederung_art=gliederung_art, ocr=ocr,
                       text_seiten=text_seiten))
    return Aufbereitet(format=art, markdown=md, befund=werte,
                       gliederung=[asdict(a) for a in abschnitte],
                       vorschau=[a.titel for a in abschnitte[:VORSCHAU]])
