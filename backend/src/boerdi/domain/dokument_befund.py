"""Befund eines umgewandelten Dokuments (Paket U3-2a, Plan 2026-11-04 §16.6) — rein, ohne I/O.

Was die Person (und gerahmt die KI) über das Dokument erfährt: Seiten, Wörter, Sprache, Gliederung,
Warnungen. Gescannte PDF (fast kein Text je Seite) werden erkannt, damit die Person einen ehrlichen
Satz bekommt — eine Texterkennung (OCR) gibt es nicht (Plan O-5).
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal

from boerdi.domain.dokument_gliederung import Abschnitt

#: Unter so vielen Zeichen je Seite gilt ein PDF als gescannt (kein Textlayer).
GESCANNT_JE_SEITE: Final = 30
#: Unter so vielen Zeichen je Seite: Warnung ``wenig_text``.
WENIG_JE_SEITE: Final = 300
_PROBE: Final = 20_000
_DE: Final = frozenset("der die das und ist nicht mit sich auf für dem den eine wir".split())
_EN: Final = frozenset("the and is not with for that this are of to in we".split())


def sprache(text: str) -> Literal["de", "en", "unbekannt"]:
    woerter = re.findall(r"[a-zäöüß]+", text[:_PROBE].lower())
    de = sum(w in _DE for w in woerter)
    en = sum(w in _EN for w in woerter)
    if de + en < 5:
        return "unbekannt"
    if de >= 2 * en:
        return "de"
    if en >= 2 * de:
        return "en"
    return "unbekannt"


def gescannt(md: str, seiten: int | None) -> bool:
    zeichen = len(md.strip())
    if zeichen == 0:
        return True
    return bool(seiten) and zeichen / seiten < GESCANNT_JE_SEITE


def befund(md: str, *, seiten: int | None, gekuerzt: bool, bilder: int,
           abschnitte: list[Abschnitt], gliederung_art: str) -> dict[str, Any]:
    zeichen = len(md)
    warnungen: list[str] = []
    if bilder:
        warnungen.append("bilder_entfernt")
    if seiten and zeichen / seiten < WENIG_JE_SEITE:
        warnungen.append("wenig_text")
    if gliederung_art == "teile":
        warnungen.append("keine_gliederung")
    if gekuerzt:
        warnungen.append("gekuerzt")
    return {"seiten": seiten, "zeichen": zeichen, "woerter": len(re.findall(r"\w+", md)),
            "sprache": sprache(md), "abschnitte": len(abschnitte),
            "gliederung_art": gliederung_art, "warnungen": warnungen, "gekuerzt": gekuerzt}
