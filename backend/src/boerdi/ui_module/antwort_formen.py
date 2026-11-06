"""Verzeichnis der Antwortformen abfragender UI-Module (Paket U3-1b; angekündigt in U2: „beim
dritten abfragenden Modul ein Verzeichnis statt Weichen“).

``ui_module/antwort`` führt den Antwortweg aller abfragenden Module. Was ein Modul dabei anders
macht als die Vorgabe (``ui_entscheidung``: Wahl aus Kennungen), steht hier als ``Form``: was die
Sitzung sich merkt, was über das Schema hinaus geprüft wird, wie die Antwort normalisiert, gerahmt
und von der Sicherheitsprüfung gelesen wird, und welcher feste Satz unter der Frage steht.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from boerdi.ui_module import strukturentwurf_antwort as entwurf
from boerdi.ui_module import upload_antwort as upload
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

_Daten = dict[str, Any]


@dataclass(frozen=True)
class Form:
    merken: Callable[[str, str, _Daten], _Daten]
    grund: Callable[[_Daten], str | None]
    normalisiert: Callable[[_Daten], _Daten]
    #: Kopf und Zeilen des Rahmens einer geprüften Antwort.
    zeilen: Callable[[_Daten], tuple[str, list[str]]]
    ende: str
    #: Kopf und Zeilen, wenn die Frage ohne Antwort geschlossen wurde.
    frage_start: str
    frage_zeilen: Callable[[_Daten], list[str]]
    #: Was die Sicherheitsprüfung vor der Nachricht liest.
    sicherheit: Callable[[_Daten], str]
    #: Text-Schlüssel des festen Satzes unter der Frage (``i18n/bot_text``).
    satz: str = "agent.frage"
    #: Nur der Strukturentwurf: sein gemerkter Stand (``strukturentwurf_merken``) ersetzt den
    #: Rahmen der geschlossenen Frage und entfällt, wenn der Entwurf gerade als Antwort kam.
    letzter_entwurf: bool = False
    #: Endmarke je Antwort, wenn ein Modul mehrere Rahmen kennt (``ui_upload``: Ordner/Dokument).
    ende_fuer: Callable[[_Daten], str] | None = None


FORMEN: Final[dict[str, Form]] = {
    STRUKTURENTWURF: Form(
        merken=entwurf.merken, grund=entwurf.grund, normalisiert=entwurf.normalisiert,
        zeilen=entwurf.zeilen, ende=entwurf.ENTWURF_FRAME_END,
        frage_start=entwurf.LETZTER_FRAME_START, frage_zeilen=entwurf.frage_zeilen,
        sicherheit=entwurf.sicherheit, satz="agent.entwurf", letzter_entwurf=True),
    UPLOAD: Form(
        merken=upload.merken, grund=upload.grund, normalisiert=upload.normalisiert,
        zeilen=upload.zeilen, ende=upload.ORDNER_FRAME_END,
        frage_start=upload.OFFEN_FRAME_START, frage_zeilen=upload.frage_zeilen,
        sicherheit=upload.sicherheit, ende_fuer=upload.ende),
}


def form(modul: Any) -> Form | None:
    return FORMEN.get(modul) if isinstance(modul, str) else None
