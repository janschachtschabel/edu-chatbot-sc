"""Was das Modell von einem MCP-Werkzeug angeboten bekommt, wenn der Server mehr kann.

Chatbot und MCP-Server werden getrennt bereitgestellt. Die Kataloge (``tool_defs``,
``tool_defs_curation``) beschreiben, was jeder Stand des Servers kann; dieses Modul legt darauf,
was nur der neuere kennt — je Paket ein Modul, das selbst prüft, ob der bereitgestellte Server es
führt (:mod:`faehigkeiten`):

- :mod:`sammlung_per_name` (N3): eine Sammlung über ihren Titel, an fünf Lesewerkzeugen.
- :mod:`werte_hinzufuegen` (N2): Werte ergänzen statt ersetzen, Listen, Inhaltstypen nachschlagen.
- :mod:`suche_mehrfach` (N4): mehrere Inhaltssuchen in einem Aufruf — ein ganzes Werkzeug, das
  nur der neuere Server führt (:func:`zusaetzliche`).
- :mod:`baum_lesen` (SW-1): ein Sammlungsbaum als flache Liste (ein ganzes Werkzeug) und die
  gespeicherte Reihenfolge an zwei Lesewerkzeugen.
- :mod:`baum_metadaten` (SW-2): Fach, Bildungsstufe und Schlagworte gleich beim Anlegen eines
  Sammlungsbaums.
- :mod:`sammlungspflege` (SW-3): sieben Kuratier-Werkzeuge, die im Katalog stehen und nur
  angeboten werden, wenn der Server sie führt (:func:`gefuehrt`); Umsortieren und Vorschlagen an
  den Einsortier-Werkzeugen.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.mcp import (
    baum_lesen,
    baum_metadaten,
    sammlung_per_name,
    sammlungspflege,
    suche_mehrfach,
    werte_hinzufuegen,
)

#: Lesewerkzeuge, die in keinem Katalog stehen und nur angeboten werden, wenn der Server sie
#: führt. Jedes Modul trägt ``WERKZEUG``, ``DEFINITION``, ``angeboten()`` und ``definitionen()``.
#: Die Werkzeugübersicht des Studios und der Schalter am MCP-Server lesen diese Liste.
BEDINGT_LESEND = (suche_mehrfach, baum_lesen)


def nach_faehigkeit(definition: dict[str, Any]) -> dict[str, Any]:
    """Die Definition, wie der bereitgestellte Server sie versteht (eine Kopie, wenn sich etwas
    ändert; sonst die Definition selbst)."""
    return fuer_muster(sammlung_per_name.erweitert(definition))


def fuer_muster(definition: dict[str, Any]) -> dict[str, Any]:
    """Wie :func:`nach_faehigkeit`, ohne die Sammlung per Titel: Die bleibt an den direkten
    Werkzeugen dem Agenten vorbehalten (N3). Für Werkzeuge, die ein Muster beim Namen nennt."""
    return sammlungspflege.erweitert(
        baum_metadaten.erweitert(baum_lesen.erweitert(werte_hinzufuegen.erweitert(definition))))


def gefuehrt(werkzeug: str) -> bool:
    """Darf dieses Katalog-Werkzeug angeboten werden? Nein nur für die Kuratier-Werkzeuge, die
    der bereitgestellte Server (noch) nicht führt — ein Aufruf endete dort im Fehler."""
    return sammlungspflege.gefuehrt(werkzeug)


def fuer_den_server(werkzeug: str, argumente: dict[str, Any]) -> dict[str, Any]:
    """Die Argumente, wie der bereitgestellte Server sie versteht — ohne Felder, die nur der
    neuere kennt und an denen ein älterer den ganzen Aufruf scheitern ließe."""
    return baum_metadaten.fuer_den_server(werkzeug, argumente)


def zusaetzliche() -> list[dict[str, Any]]:
    """Lesende Werkzeuge, die nur der neuere Server führt — leer, solange er sie nicht nennt."""
    return [d for modul in BEDINGT_LESEND for d in modul.definitionen()]


def lokale_ablehnung(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn ein Aufruf so nicht hinausgehen soll (der Server verwürfe eine
    Angabe still oder wiese den Aufruf mit einer Schemameldung ab) — sonst ``None``."""
    return (werte_hinzufuegen.nicht_moeglich(werkzeug, argumente)
            or suche_mehrfach.nicht_moeglich(werkzeug, argumente)
            or baum_lesen.nicht_moeglich(werkzeug, argumente)
            or sammlungspflege.nicht_moeglich(werkzeug, argumente))


def hinweis_zum_senden(werkzeug: str, eingang: dict[str, Any],
                       gesendet: dict[str, Any]) -> str | None:
    """Ein Satz für KI und Person, wenn :func:`fuer_den_server` etwas herausgenommen hat."""
    return baum_metadaten.hinweis(werkzeug, eingang, gesendet)
