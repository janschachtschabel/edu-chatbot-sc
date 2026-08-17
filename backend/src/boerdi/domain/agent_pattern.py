"""Was der Agent-Modus anstelle der Musterwahl liefert (A4c).

Die Muster-Engine wählt aus ``03-patterns/*.md`` ein Muster und moduliert es zu
einem ``pattern_output``. Der Agent-Modus hat nichts zu wählen — er ist die
Maschine, die sich ihr Werkzeug selbst sucht. Trotzdem brauchen die
nachgelagerten Knoten dieselbe **Form**: ``turn_assembly`` liest ``max_items``
und ``format_follow_up``, ``turn_persist`` schreibt Ton/Länge/Detailgrad in die
Qualitätslogs. Bliebe das Dict leer, unterschieden sich die beiden Maschinen im
A/B-Vergleich auch dort, wo gar keine Entscheidung getroffen wurde.

Deshalb: dieselbe Rückgabe wie ``select_pattern`` — ein synthetisches
``PatternDef`` durch die **echte** ``phase3_modulate``. Damit stimmen Ton,
Persona-Modifier und Geräte-Deckel mit dem Bestandsweg überein; verschieden ist
nur, wer die Antwort erzeugt. Ein handgeschriebenes Dict hätte dieselben Werte
ein zweites Mal festgelegt und wäre beim nächsten Studio-Feld auseinandergelaufen.

Der Bezeichner ``AGENT`` ist bewusst kein ``M``-Muster: er taucht in
Qualitätslogs und im Debug-Block auf und soll dort auf den ersten Blick von
einem Muster unterscheidbar sein. Für ``_qr_policy`` ist er eine unbekannte ID
und fällt auf die Standard-Policy — genau richtig, denn eine Muster-QR-Policy
gibt es hier nicht.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.pattern_engine import PatternDef, phase3_modulate

#: ID und Beschriftung des Agent-Laufs im Debug-/Log-Pfad.
AGENT_PATTERN_ID: Final = "AGENT"
AGENT_PATTERN_LABEL: Final = "AGENT (Werkzeug-Agent)"

#: Dasselbe für den Hybrid (H6). Eigene Kennung, weil beide Maschinen
#: nebeneinander gemessen werden: stünde in den Qualitätslogs beider Läufe
#: ``AGENT``, ließe sich der A/B-Vergleich nicht mehr auseinanderhalten. Es ist
#: der **Anfangs**-Zustand — sobald das Modell ein Muster zieht, trägt
#: ``effective_pattern_id`` dessen Kennung.
HYBRID_PATTERN_ID: Final = "HYBRID"
HYBRID_PATTERN_LABEL: Final = "HYBRID (Werkzeug-Agent mit Musterkatalog)"


def _synthetisch(
    pattern_id: str,
    label: str,
    signals: list[str],
    device: str,
    entities: dict[str, Any],
    persona_id: str,
) -> tuple[PatternDef, dict[str, Any], dict[str, float], list[str]]:
    winner = PatternDef(id=pattern_id, label=label)
    output = phase3_modulate(winner, signals, device, entities, persona_id)
    return winner, output, {pattern_id: 1.0}, []


def agent_pattern(
    *,
    signals: list[str],
    device: str,
    entities: dict[str, Any],
    persona_id: str,
) -> tuple[PatternDef, dict[str, Any], dict[str, float], list[str]]:
    """Der Ersatz für ``select_pattern`` im Agent-Modus.

    Gleiche Rückgabe-Form: ``(winner, pattern_output, scores, eliminated)``.
    ``eliminated`` ist leer, weil nichts ausgeschieden ist — es stand nichts zur
    Wahl.
    """
    return _synthetisch(AGENT_PATTERN_ID, AGENT_PATTERN_LABEL,
                        signals, device, entities, persona_id)


def hybrid_pattern(
    *,
    signals: list[str],
    device: str,
    entities: dict[str, Any],
    persona_id: str,
) -> tuple[PatternDef, dict[str, Any], dict[str, float], list[str]]:
    """Dasselbe für den Hybrid — der **Anfangs**-Zustand des Zuges.

    Hier steht ebenfalls nichts zur Wahl, denn die Wahl fällt später: das Modell
    zieht das Muster erst in der Schleife, wenn es die Lage kennt. Bis dahin
    gelten Ton, Persona-Modifier und Geräte-Deckel aus derselben echten
    ``phase3_modulate`` wie überall — was das Modell dann wählt, schreibt
    ``respond_agent`` nach ``effective_pattern_id`` fort.
    """
    return _synthetisch(HYBRID_PATTERN_ID, HYBRID_PATTERN_LABEL,
                        signals, device, entities, persona_id)
