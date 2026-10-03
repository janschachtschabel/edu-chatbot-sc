"""Was ein Zug ausführen darf: nur Werkzeuge aus dem Angebot an das Modell.

Audit 2026-09-29, B-M1: Beide Schleifen (``services/agent_loop``,
``services/tool_loop``) schickten jeden Werkzeugnamen an den MCP, den das Modell
nannte, auch einen, der gar nicht angeboten war. Ein solcher Name kommt aus einer
Halluzination oder einer Einschleusung im Fremdtext. Ausgeführt umginge er etwa
den Anonym-Deckel, der Schreibwerkzeuge gar nicht erst anbietet.

Rein (CLAUDE.md, Regel 4): nur stdlib.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

#: Die Werkzeug-Antwort an das Modell, wenn es einen fremden Namen ruft.
NICHT_ANGEBOTEN = (
    "Nicht ausgeführt: Dieses Werkzeug steht in diesem Zug nicht zur Verfügung. "
    "Nutze nur die angebotenen Werkzeuge oder antworte ohne Werkzeug."
)


def angebotene_namen(tools: Iterable[dict[str, Any]] | None) -> frozenset[str]:
    """Die Namen im Werkzeug-Angebot, OpenAI-Form ``{"function": {"name": …}}``."""
    namen: set[str] = set()
    for werkzeug in tools or ():
        name = (werkzeug.get("function") or {}).get("name")
        if isinstance(name, str) and name:
            namen.add(name)
    return frozenset(namen)
