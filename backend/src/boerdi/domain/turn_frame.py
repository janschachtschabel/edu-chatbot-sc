"""Der offene Vorgang eines Zuges — „Frame" (E1 Slot-Register + E2 Frame).

Reine Domänenlogik: nimmt das ``entities``-Dict, gibt Entscheidungen zurück,
kennt weder Datenbank noch Graph. Der Zustand reist in
``session_state["entities"]["_frame"]`` mit — die ``_``-Konvention ist der
etablierte Platz für zugübergreifenden Nicht-Slot-Zustand (``_canvas_topic``,
``_lp_used_node_ids``, ``_last_pattern`` …) und wird von ``turn_persist`` ohnehin
als JSONB geschrieben. Deshalb braucht der Frame weder eine eigene Spalte noch
eine Migration.

**Warum es ihn gibt** — B0-Messung 2026-08-10, zwei Läufe, identisch:

    „Erstell mir ein Arbeitsblatt."  → M03: „Zu welchem Thema?"
    „weiss nicht"                    → M03: dieselbe Frage
    „egal"                           → M03: dieselbe Frage
    „such du was aus"                → M10: „Arbeitsblatt zum Thema
                                       *such du was aus* erstellt" — das
                                       Dokument darunter hieß
                                       „Prozentrechnung im Alltag"

Der Bot entkam der Schleife also nur, indem er die Ausweich-Floskel als Thema
nahm und darunter ein frei erfundenes Thema auslieferte. Wer nur die
Platzhalter-Wortliste repariert, macht aus dem falschen Ausstieg eine echte
Endlosschleife — Wortliste und Versuchsgrenze gehören zusammen.

**Bewusst NICHT gebaut** (``simplify:``, jeweils ohne messbaren Bedarf):

* *Eigentümer-Feld* — die Übergabe funktioniert bereits: M03 → „Bruchrechnung"
  landete gemessen bei M10, weil ``merge`` die Entitäten faltet und der
  Klassifikator ``turn_type=clarification`` erkennt.
* *Frist* — ``thema`` wurde nach vier fremden Zügen gemessen vom neuen Thema
  ersetzt; ein Verfall nach N Zügen hätte nichts zu reparieren.

Aufstiegspfad für beide: hier ein Feld ergänzen, ``note_clarification`` füllt es.
"""

from __future__ import annotations

from typing import Any

# Das Muster, das die Rückfrage stellt (``output_mode: clarify``).
CLARIFIER_PATTERN_ID = "M03"

# Wohin der erschöpfte Vorgang aufgelöst wird: Orientierung statt einer vierten
# wortgleichen Frage. Bewusst NICHT über das Fallenlassen des Klassifikator-
# Hinweises gelöst — der Rückfall von ``select_pattern`` iteriert die nach
# Schlüssel SORTIERTE Musterliste, in der ``m03…`` vor ``m15…`` steht, und
# liefert damit wieder den Klärer (siehe Notiz im Plan).
_EXHAUSTED_TARGET_PATTERN_ID = "M15"

# Zwei wortgleiche Rückfragen darf der Bot stellen, die dritte nicht mehr: die
# Messung zeigt, dass der dritte Anlauf in beiden Läufen nichts Neues brachte.
CLARIFICATION_ATTEMPT_LIMIT = 2

_FRAME_KEY = "_frame"


def _filled_slots(entities: dict[str, Any]) -> list[str]:
    """Die vom Nutzer belegten Slots — das Slot-Register (E1).

    ``_``-präfigierte Schlüssel schreibt die Maschine, nicht der Nutzer; leere
    Werte zählen nicht, weil ``merge`` Platzhalter-Themen auf ``""`` setzt statt
    sie zu entfernen.
    """
    return sorted(
        k for k, v in (entities or {}).items()
        if not str(k).startswith("_") and v
    )


def note_clarification(entities: dict[str, Any]) -> None:
    """Der Klärer hat gefragt — Versuch zählen, in ``entities`` in-place.

    Kam seit der letzten Frage ein Slot dazu, war sie erfolgreich und die
    Zählung beginnt von vorn: M03 fragt laut seinem Pflicht-Schema immer nur
    nach dem WICHTIGSTEN offenen Slot, eine Folgefrage ist also Fortschritt und
    keine Wiederholung.
    """
    jetzt = _filled_slots(entities)
    frame = entities.get(_FRAME_KEY)
    if isinstance(frame, dict) and frame.get("slots") == jetzt:
        frame["attempts"] = _attempts(frame) + 1
    else:
        entities[_FRAME_KEY] = {"slots": jetzt, "attempts": 1}


def clear_frame(entities: dict[str, Any]) -> None:
    """Vorgang schließen (in-place). Aufzurufen, sobald ein anderes Muster den
    Zug beantwortet hat — auch bei einem Themenwechsel."""
    (entities or {}).pop(_FRAME_KEY, None)


def _attempts(frame: Any) -> int:
    """Versuchszähler eines Frames, robust gegen Fremdinhalt.

    Der Frame reist in einer JSONB-Spalte mit; eine ältere Session kann dort
    etwas anderes stehen haben. Unlesbar ⇒ 0, also nie erschöpft — im Zweifel
    fragt der Bot lieber einmal zu viel als gar nicht.
    """
    if not isinstance(frame, dict):
        return 0
    wert = frame.get("attempts")
    return wert if isinstance(wert, int) and not isinstance(wert, bool) else 0


def clarification_exhausted(
    entities: dict[str, Any], limit: int = CLARIFICATION_ATTEMPT_LIMIT
) -> bool:
    """Hat der Klärer seine Versuche verbraucht, ohne dass etwas dazukam?"""
    return _attempts((entities or {}).get(_FRAME_KEY)) >= limit


def resolve_frame(
    entities: dict[str, Any], pattern_id_hint: str | None
) -> str | None:
    """Auflösung VOR der Musterwahl: welches Muster erzwingt der Frame?

    ``None`` ⇒ der Frame mischt sich nicht ein (Normalfall). Ein Rückgabewert
    wird im ``route``-Knoten als ``enforced_pattern_id`` gesetzt und steht damit
    auf der ersten Vorrangstufe von ``select_pattern`` — hinter der Safety, die
    ihre eigene Erzwingung behält, aber vor dem Klassifikator-Hinweis.
    """
    if pattern_id_hint != CLARIFIER_PATTERN_ID:
        return None
    if not clarification_exhausted(entities):
        return None
    return _EXHAUSTED_TARGET_PATTERN_ID
