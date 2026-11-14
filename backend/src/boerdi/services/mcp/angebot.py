"""Was das Modell von einem MCP-Werkzeug angeboten bekommt, wenn der Server mehr kann.

Chatbot und MCP-Server werden getrennt bereitgestellt. Die Kataloge (``tool_defs``,
``tool_defs_curation``) beschreiben, was jeder Stand des Servers kann; dieses Modul legt darauf,
was nur der neuere kennt — je Paket ein Modul, das selbst prüft, ob der bereitgestellte Server es
führt (:mod:`faehigkeiten`):

- :mod:`sammlung_per_name` (N3): eine Sammlung über ihren Titel, an fünf Lesewerkzeugen.
- :mod:`werte_hinzufuegen` (N2): Werte ergänzen statt ersetzen, Listen, Inhaltstypen nachschlagen.
- :mod:`suche_mehrfach` (N4): mehrere Inhaltssuchen in einem Aufruf — ein ganzes Werkzeug, das
  nur der neuere Server führt (:func:`zusaetzliche`).
"""

from __future__ import annotations

from typing import Any

from boerdi.services.mcp import sammlung_per_name, suche_mehrfach, werte_hinzufuegen


def nach_faehigkeit(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition, wie der bereitgestellte Server sie versteht (eine Kopie, wenn sich etwas
    ändert; sonst die Definition selbst)."""
    return werte_hinzufuegen.erweitert(sammlung_per_name.erweitert(definition))


def zusaetzliche() -> list[dict[str, Any]]:
    """Lesende Werkzeuge, die nur der neuere Server führt — leer, solange er sie nicht nennt."""
    return suche_mehrfach.definitionen()


def lokale_ablehnung(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn ein Aufruf so nicht hinausgehen soll (der Server verwürfe eine
    Angabe still oder wiese den Aufruf mit einer Schemameldung ab) — sonst ``None``."""
    return (werte_hinzufuegen.nicht_moeglich(werkzeug, argumente)
            or suche_mehrfach.nicht_moeglich(werkzeug, argumente))
