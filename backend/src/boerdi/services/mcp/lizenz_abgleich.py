"""Lizenzwert → Schlüssel des WLO-Lizenzvokabulars (Paket 11 L, C-1; Review 2026-10-16).

Gemessen 2026-10-16: der Server nimmt Schlüssel (``CC_BY_NC``), Bezeichnungen und Aliasse
gleich an, gleicht Unbekanntes aber über Teilwörter ab — „cc by“ steckt in jedem CC-Wert, so
filterte „CC BY NC“ oder „CC BY-NC-SA 3.0 DE“ still auf CC BY. Deshalb hier:

1. **Exakt nach Vereinheitlichung** (Groß/Klein, Bindestrich/Unterstrich, Versionsnummer,
   Länder- und Fassungszusätze wie ``DE``/``international``), nie über Teilwörter.
2. **CC-Werte aus ihren Bausteinen** BY/NC/SA/ND, wenn der Wortlaut keinem Eintrag gleicht.
3. **Sammelwerte des Servers** („OER“, „freie Lizenzen“ …) bleiben, wie sie sind.
4. Was sich so nicht zuordnen lässt, **filtert nicht** (:func:`lizenz_filter` gibt ``None``) —
   roh weitergereicht träfe es am Server über ein Teilwort die falsche Lizenz.

Kein LLM-Rückfall: eine geratene Lizenz wäre schlimmer als keine.
"""

from __future__ import annotations

import re
from typing import Final

#: Sammelwerte des Servers (``filter-criteria.ts``) — nie in eine Einzellizenz übersetzen.
SAMMELWERTE: Final = frozenset({
    "oer", "freie lizenz", "freie lizenzen", "offene lizenz", "offene lizenzen",
    "oer lizenz", "oer lizenzen",
})
#: Versionen 1.0–4.0 („4“, „3.0“) — nie die „0“ von CC 0.
_VERSION = re.compile(r"\b[1-9](?:\.\d+)?\b")
_ZUSATZ: Final = frozenset({
    "de", "at", "ch", "deutschland", "international", "intl", "unported", "generic", "lizenz",
    "license", "licence",
})
_CC_ANFANG: Final = ("cc", "creative")


def _einheitlich(wert: str) -> str:
    ohne_version = _VERSION.sub(" ", wert.lower())
    woerter = re.sub(r"[-_]", " ", ohne_version).split()
    return " ".join(w for w in woerter if w not in _ZUSATZ)


def _aus_bausteinen(einheitlich: str, schluessel: set[str]) -> str | None:
    """``cc by nc sa`` → ``CC_BY_NC_SA`` — nur, wenn der Schlüssel im Vokabular steht."""
    woerter = einheitlich.split()
    if not woerter or woerter[0] not in _CC_ANFANG:
        return None
    teile = set(woerter[1:]) - {"commons"}
    if not teile <= {"by", "nc", "sa", "nd", "0", "zero"}:
        return None
    if teile & {"0", "zero"}:
        kandidat = "CC_0" if teile <= {"0", "zero"} else None
    elif "by" not in teile or {"sa", "nd"} <= teile:
        kandidat = None
    else:
        kandidat = "CC_BY" + ("_NC" if "nc" in teile else "") + (
            "_SA" if "sa" in teile else "_ND" if "nd" in teile else "")
    return kandidat if kandidat in schluessel else None


def lizenz_schluessel(vokabular: dict[str, str], wert: str) -> str | None:
    """Den Schlüssel zu ``wert`` oder ``None``.

    ``vokabular`` ist der Cache ``Bezeichnung/Alias → Schlüssel``. Ein Wert, der ohnehin ein
    Schlüssel ist, zählt ebenso. Nur ein eindeutiger Treffer gilt.
    """
    gesucht = _einheitlich(wert or "")
    if not gesucht:
        return None
    treffer = {s for name, s in vokabular.items() if _einheitlich(name) == gesucht}
    treffer |= {s for s in vokabular.values() if _einheitlich(s) == gesucht}
    if len(treffer) == 1:
        return treffer.pop()
    if treffer:
        return None
    return _aus_bausteinen(gesucht, set(vokabular.values()))


def lizenz_filter(vokabular: dict[str, str], wert: str) -> str | None:
    """Was als ``license`` an den Server geht: Schlüssel, Sammelwert unverändert — oder ``None``
    (weglassen: dann filtert die Suche nicht, wie es die Werkzeugbeschreibung sagt).

    Ohne Vokabular (MCP beim Laden nicht erreichbar) bleibt der Wert, wie er ist: dann lässt sich
    nichts beurteilen, und Weglassen hieße, jede Lizenzsuche still zu entfiltern.
    """
    if " ".join(re.sub(r"[-_]", " ", (wert or "").lower()).split()) in SAMMELWERTE:
        return wert
    if not vokabular:
        return wert
    return lizenz_schluessel(vokabular, wert)
