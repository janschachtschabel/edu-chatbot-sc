"""Was das Modell von einem MCP-Werkzeug angeboten bekommt, wenn der Server mehr kann.

Chatbot und MCP-Server werden getrennt bereitgestellt. Die Kataloge (``tool_defs``,
``tool_defs_curation``) beschreiben, was jeder Stand des Servers kann; dieses Modul legt darauf,
was nur der neuere kennt — je Paket ein Modul, das selbst prüft, ob der bereitgestellte Server es
führt (:mod:`faehigkeiten`):

- :mod:`sammlung_per_name` (N3): eine Sammlung über ihren Titel, an fünf Lesewerkzeugen.
- :mod:`werte_hinzufuegen` (N2): Werte ergänzen statt ersetzen, Listen, Inhaltstypen nachschlagen.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.mcp import sammlung_per_name, werte_hinzufuegen


def nach_faehigkeit(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition, wie der bereitgestellte Server sie versteht (eine Kopie, wenn sich etwas
    ändert; sonst die Definition selbst)."""
    return werte_hinzufuegen.erweitert(sammlung_per_name.erweitert(definition))
