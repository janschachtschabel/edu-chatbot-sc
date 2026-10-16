"""Kurations-Aufträge ins Muster mit den Schreibwerkzeugen leiten (Paket 10, S-7).

Schreibende Werkzeuge bietet die Muster-Maschine nur in M18 (Kuration) und M20
(Erschließen) an (``_select_active_tools``). Wählt der Klassifikator für einen klaren
Auftrag ein anderes Muster, fehlen sie, und das Modell erklärt oft, man müsse sich
anmelden — obwohl die Person angemeldet ist (Kurzaudit 2026-10-10, S-7). Diese Regel
ist das Netz darunter, deterministisch und im Studio pflegbar
(``classify-overrides.yaml`` → ``curation_reroute``):

- ein Auftragsverb (``verbs``, ganze Wörter) UND ein Gegenstand im Bestand
  (``objects``, Wortanfänge) oder eine Webadresse,
- keine Wie-Frage (erstes Wort nicht in ``question_words`` — „Wie füge ich …“ zeigt
  M13 den Weg),
- und der Klassifikator hat nicht schon eines der beiden Muster gewählt.

Ziel ist M20, wenn eine Webadresse dasteht (der Gegenstand kommt von außen), sonst M18.
"""

from __future__ import annotations

import re
from typing import Any

KURATION = "M18"
ERSCHLIESSEN = "M20"
_ZIELE = frozenset({KURATION, ERSCHLIESSEN})

_WORT = re.compile(r"\w+")
_ADRESSE = re.compile(r"https?://|\bwww\.", re.IGNORECASE)


def _liste(regel: dict[str, Any], schluessel: str) -> tuple[str, ...]:
    return tuple(str(w).strip().lower() for w in regel.get(schluessel) or [] if str(w).strip())


def umleitung(nachricht: str, hinweis: str | None, regel: dict[str, Any] | None) -> str | None:
    """Das Muster, in das ``nachricht`` gehört — ``None``, wenn es beim Klassifikator bleibt."""
    if not regel or not regel.get("enabled", True) or hinweis in _ZIELE:
        return None
    woerter = _WORT.findall((nachricht or "").lower())
    if not woerter or woerter[0] in _liste(regel, "question_words"):
        return None
    if not set(woerter) & set(_liste(regel, "verbs")):
        return None
    adresse = bool(_ADRESSE.search(nachricht or ""))
    gegenstaende = _liste(regel, "objects")
    if not adresse and not (gegenstaende and any(w.startswith(gegenstaende) for w in woerter)):
        return None
    return ERSCHLIESSEN if adresse else KURATION
