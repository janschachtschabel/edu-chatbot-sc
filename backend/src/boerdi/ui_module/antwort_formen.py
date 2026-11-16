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
    #: Review TG-3a–c, R3-1: liest ``sicherheit`` für diese Antwort nur **Namen** (Ordner, Dateien,
    #: Überschriften eines Dokuments, ungeänderte Titel) — keine Äußerung der Person? Dann gehen sie
    #: nur an die Moderation, nicht an die Krisen- und Drohungsmuster: „Suizid-Prävention.pdf“ ist
    #: ein Thema, kein Hilferuf.
    sicherheit_nur_namen: Callable[[_Daten], bool] | None = None
    #: Text-Schlüssel des festen Satzes unter der Frage (``i18n/bot_text``).
    satz: str = "agent.frage"
    #: Nur der Strukturentwurf: sein gemerkter Stand (``strukturentwurf_merken``) ersetzt den
    #: Rahmen der geschlossenen Frage und entfällt, wenn der Entwurf gerade als Antwort kam.
    letzter_entwurf: bool = False
    #: Endmarke je Antwort, wenn ein Modul mehrere Rahmen kennt (``ui_upload``: Ordner/Dokument).
    ende_fuer: Callable[[_Daten], str] | None = None
    #: Plan 2026-11-16, TG-2: eine alte Antwortform vor der Schema-Prüfung auf die neue heben
    #: (``ui_upload``: ``ordner_als_entwurf`` → ``erfasst``, ``dokument.ziel`` entfällt).
    rueckwaerts: Callable[[_Daten], _Daten] | None = None


FORMEN: Final[dict[str, Form]] = {
    STRUKTURENTWURF: Form(
        merken=entwurf.merken, grund=entwurf.grund, normalisiert=entwurf.normalisiert,
        zeilen=entwurf.zeilen, ende=entwurf.ENTWURF_FRAME_END,
        frage_start=entwurf.LETZTER_FRAME_START, frage_zeilen=entwurf.frage_zeilen,
        sicherheit=entwurf.sicherheit, satz="agent.entwurf", letzter_entwurf=True,
        # R3-1: unbearbeitet trägt der Entwurf nur Titel aus Ordnern, WLO oder der KI — keine
        # Äußerung der Person; hat sie ihn bearbeitet, kann ein Titel ihr eigener Satz sein
        sicherheit_nur_namen=lambda d: d.get("bearbeitet") is False),
    UPLOAD: Form(
        merken=upload.merken, grund=upload.grund, normalisiert=upload.normalisiert,
        zeilen=upload.zeilen, ende=upload.ORDNER_FRAME_END,
        frage_start=upload.OFFEN_FRAME_START, frage_zeilen=upload.frage_zeilen,
        sicherheit=upload.sicherheit, ende_fuer=upload.ende, rueckwaerts=upload.rueckwaerts,
        sicherheit_nur_namen=lambda _d: True),
}


def form(modul: Any) -> Form | None:
    return FORMEN.get(modul) if isinstance(modul, str) else None
