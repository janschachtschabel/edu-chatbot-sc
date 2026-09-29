"""Die Skill-Brücke im Muster-Modus (E-6, Nutzer-Entscheid 2026-09-27).

Im Muster-Modus legt das gewählte Muster die Werkzeuge fest, und nur sechs von
zwanzig Mustern führen ``get_skill_registry`` und ``get_skill`` (M08, M09, M10,
M18, M19, M20). Sind freigegebene Skills im Spiel, soll auch ein anderes
Werkzeug-Muster sie laden können — so kommt die Skill-Nutzung des Agenten in
den Muster-Modus, ohne den entfernten Hybrid. Der Betreiber schaltet das im
Studio zu (``01-base/engine``, ``muster_skills``); die Vorgabe ist aus.

**Warum ein eigener Schlüssel neben ``tools``.** Diese Liste liest die
Reflexions-Schleife als Pflicht (``tool_loop``, ``force_tool_use``): mit
``requires_all_tools`` verlangte sie dann einen Skill-Abruf, und ein Suchmuster
gälte schon mit einem bloßen Katalog-Abruf als erfüllt. Die Brücke ist ein
Angebot, keine Pflicht.

**Nur beide oder keins.** Ohne Katalog fehlt die ``nodeId``, ohne ``get_skill``
der Wortlaut — ein halber Weg wäre eine Anweisung ohne Werkzeug, und genau die
soll es nicht mehr geben (siehe :func:`verfuegbar`).

Rein und ohne Konfigurationszugriff: ob zugelassen und ob Skills im Spiel sind,
entscheidet der Aufrufer (``graph/nodes/route``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final

SKILL_WERKZEUGE: Final = ("get_skill_registry", "get_skill")

#: Wo die zugeschalteten Werkzeuge in ``pattern_output`` stehen.
ZUSATZ_KEY: Final = "skill_werkzeuge"


def zuschalten(
    pattern_output: dict[str, Any],
    *,
    zugelassen: bool,
    im_spiel: bool,
    gesperrt: Iterable[str],
) -> list[str]:
    """Die Skill-Werkzeuge an ein Werkzeug-Muster hängen, wenn es passt.

    Schreibt in-place nach ``pattern_output[ZUSATZ_KEY]`` und gibt zurück, was
    dazukam (leer: nichts). Ein Muster ohne eigene Werkzeuge bleibt ohne — seine
    Regeln verbieten Werkzeugaufrufe, und dazu gehören die Schutzantworten bei
    Krise und Drohung. Ein Muster, das beide schon führt, braucht nichts.
    """
    eigene = pattern_output.get("tools") or []
    if not (zugelassen and im_spiel and eigene):
        return []
    if all(w in eigene for w in SKILL_WERKZEUGE):
        return []
    if set(gesperrt) & set(SKILL_WERKZEUGE):
        return []
    zusatz = [w for w in SKILL_WERKZEUGE if w not in eigene]
    pattern_output[ZUSATZ_KEY] = zusatz
    return zusatz


def verfuegbar(pattern_output: dict[str, Any]) -> bool:
    """Kann dieser Zug einen Skill laden — mit eigenen oder zugeschalteten Werkzeugen?

    Daran hängen die Skill-Hinweise im Antwort-Prompt: Werkzeug im Katalog ⇔
    Anweisung im Prompt, wie beim ``result_schema`` im Agenten.
    """
    alle = set(pattern_output.get("tools") or ()) | set(pattern_output.get(ZUSATZ_KEY) or ())
    return all(w in alle for w in SKILL_WERKZEUGE)
