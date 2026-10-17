"""Ein Umwandlungsfehler des RAG-Imports wird zur HTTP-Antwort (Paket 6, B6).

Aus ``api/rag.py`` herausgelöst, als die Abbildung je Art dazukam: dort stehen
die Routen, hier die Regel, welcher Fehler welchen Status und welchen Satz
bekommt. Die Arten beschreibt ``services/rag/umwandeln_fehler.Umwandlungsfehler``.
"""

from fastapi import HTTPException

from boerdi.i18n import Locale, msg
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler

#: Art eines Umwandlungsfehlers → (Status, Satz).
_ANTWORT: dict[str, tuple[int, str]] = {
    "datei": (400, "ingest.convertFailed"),
    "format": (415, "ingest.formatUnsupported"),
    "server": (500, "ingest.serverMissing"),
    "adresse": (400, "url.notAllowed"),
    "adresse_unbekannt": (400, "url.unknownHost"),
    "abruf": (400, "ingest.fetchFailed"),
    "zu_gross": (400, "ingest.fetchTooLarge"),
    "zu_langsam": (400, "ingest.fetchTooSlow"),
    # Paket 9: die Grenzen der Umwandlung selbst (``services/rag/umwandeln_kind``).
    "entpackt_zu_gross": (400, "ingest.unpackedTooLarge"),
    "zu_viele_seiten": (400, "ingest.tooManyPages"),
    "umwandlung_zu_langsam": (400, "ingest.convertTooSlow"),
    "umwandlung_zu_gross": (400, "ingest.convertTooBig"),
    "text_zu_lang": (400, "ingest.textTooLong"),
}


def pruefe_umwandlung(markdown: str, lang: Locale) -> None:
    """Ein Fehlertext der Umwandlung wird zur HTTP-Antwort; ein Dokument passiert.

    Erkannt am Typ, nicht am Präfix „Fehler“ (Paket 4b, A3): ein Dokument, das so
    beginnt, ist ein Dokument. Status und Satz hängen seit Paket 6 (B6) an der
    Art: zweisprachig statt des rohen deutschen Texts, und ein fehlendes Paket
    im Image ist ein Fehler des Servers (500) statt 400. Ein Format ohne Wandler
    bleibt 415 (Paket 4, C5).
    """
    if not isinstance(markdown, Umwandlungsfehler):
        return
    status, schluessel = _ANTWORT.get(markdown.art, _ANTWORT["datei"])
    wert = f"{markdown.wert:g}" if markdown.wert is not None else ""
    raise HTTPException(status_code=status,
                        detail=msg(lang, schluessel, detail=markdown.detail, wert=wert))
