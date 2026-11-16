"""Zeilen und Rahmen für Blöcke vor der Nachricht an die KI (aus ``ui_module/antwort``, U3-1b).

Gemeinsam für alle Antwortformen (``ui_module/antwort_formen``): eine Zeile ohne Umbruch (ein
Umbruch dürfte im Block keinen eigenen Abschnitt beginnen) und ein Rahmen, dessen Endmarke
Fremdtext nicht vorzeitig schließen kann — in keiner Schreibweise (``domain/endmarken``).
"""

from __future__ import annotations

from typing import Final

from boerdi.domain.endmarken import entschaerfe_endmarken

ZEILE: Final = 300


def zeile(wert: object, deckel: int = ZEILE) -> str:
    """Eine Zeile: ein Umbruch darf im Block keinen eigenen Abschnitt beginnen."""
    return " ".join(str(wert).split())[:deckel] if wert is not None else ""


def name_fuer_ki(name: object, deckel: int = 80) -> str:
    """Ein Name der Person (Datei, Dokument) für die KI: eine Zeile, ohne Anführungs- und
    Rahmenzeichen (Review TG-3d–f, MINOR 3; Review der TG-7-Behebung, Befund 4)."""
    return zeile(name, deckel).translate({ord(c): None for c in "„“”\"[]"})


def gerahmt(start: str, zeilen: list[str], ende: str) -> str:
    """Zeilen im Rahmen; Endmarken im Inhalt sind entschärft."""
    return "\n".join([start, entschaerfe_endmarken("\n".join(zeilen)), ende])
