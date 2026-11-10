"""Die Namen der Ablauf-Werkzeuge der KI (Paket AS-5a/5b, Plan 2026-11-09 §5g, A5-2).

Rein und ohne Abhängigkeiten zu ``services``: auch ``domain/pattern_engine`` muss die Namen in
``tools:`` eines Musters erkennen (AS-5b), ohne den Katalog der Abläufe zu laden.

Ein Werkzeug heißt ``ablauf-<Kennung eines Ablaufs>`` — mit Bindestrich, weil ``__`` ein Werkzeug
eines Fremdservers kennzeichnet und Ablauf-Kennungen nie ``-`` enthalten. Ein Fremdserver, dessen
Kennung mit ``ablauf-`` beginnt, ergibt nie ein Ablauf-Werkzeug (Review AS-5a, Befund 3).
"""

from __future__ import annotations

import re
from typing import Any, Final

from boerdi.domain.config_models.ablauf import ID_FORM
from boerdi.domain.fremdwerkzeug import ist_fremd

PRAEFIX: Final = "ablauf-"
#: Im Ergebnis von ``phase3_modulate``: die Ablauf-Werkzeuge, die ein Muster in ``tools:`` nennt —
#: getrennt von den MCP-Werkzeugen (Pflicht-Prüfung, Kuratier-Absicht lesen nur MCP-Namen).
MUSTER_KEY: Final = "ablauf_werkzeuge"


def kennung(name: str) -> str:
    return name[len(PRAEFIX):]


def ist_ablauf_werkzeug(name: Any) -> bool:
    return (isinstance(name, str) and name.startswith(PRAEFIX) and not ist_fremd(name)
            and re.fullmatch(ID_FORM, kennung(name)) is not None)
