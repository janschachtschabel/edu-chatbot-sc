"""Darf das Widget auf dieser Seite eine Anmeldung anbieten? (Nutzer-Entscheid 2026-10-15, zu A-2)

Der Zugangsblock liegt im ``sessionStorage`` der Seite, die das Widget einbettet; jedes Skript
dort kann ihn lesen (``docs/mcp-und-anmeldung.md``, R1). Eine geschlossene Anlage
(``CORS_ALLOW_ALL=false``) bietet die Anmeldung deshalb nur den Seiten an, die sie auch sonst
bedient: ``CORS_ORIGINS`` und — solange ``CORS_ALLOW_EXTENSIONS`` gilt — Browser-Erweiterungen.
Dieselbe Prüfung wie die CORS-Middleware (Liste ODER Regel), nur nachsichtiger bei
Groß-/Kleinschreibung und Schrägstrich am Ende.

Die offene Vorgabe ändert nichts: dort bietet jede Seite die Anmeldung an wie bisher.

Rein: keine I/O, die Einstellungen reicht der Aufrufer herein.
"""

from __future__ import annotations

import re


def _gleich(a: str) -> str:
    return a.strip().rstrip("/").lower()


def anmeldung_erlaubt(origin: str | None, *, allow_all: bool, origins: list[str],
                      origin_regex: str | None) -> bool:
    """``True``, wenn eine Seite mit ``origin`` die Anmeldung angeboten bekommt.

    Ohne ``Origin`` gilt die Anfrage als von derselben Herkunft — Browser schicken ihn bei einem
    gewöhnlichen GET an die eigene Adresse oft nicht.
    """
    if allow_all or "*" in origins or not origin:
        return True
    if _gleich(origin) in {_gleich(o) for o in origins}:
        return True
    return bool(origin_regex and re.fullmatch(origin_regex, origin))
