"""Die Werkzeugliste der Agent-Schleife (A1).

Die Muster-Engine lässt ein Muster auswählen, welche Werkzeuge das Modell sieht
(``response_tool_selection._select_active_tools``). Die Agent-Schleife tut das
ausdrücklich nicht: sie gibt den GANZEN Katalog und überlässt die Wahl dem
Modell — das ist der Unterschied, um den es geht.

**Eine Regel wird trotzdem übernommen**, und zwar aus ``_nameable_tools``:
kuratierende Werkzeuge nur mit hinterlegtem Zugangsblock. Ohne ihn verweigert der
MCP-Server sie ohnehin; sie gar nicht erst anzubieten ist trotzdem richtig, weil
sonst ein Können angekündigt wird, das der nächste Schritt zurücknimmt.

``submit_result`` löst zwei Aufgaben mit einem Mittel: es ist das **saubere
Abbruchsignal** (der Agent sagt selbst, dass er fertig ist) und der Träger der
**strukturierten Ausgabe**. Gibt der Aufrufer ein ``result_schema`` mit, wird es
wörtlich zu den ``parameters`` des Feldes ``result`` — dann erzwingt der Anbieter
die Form über seine eigene Werkzeug-Validierung, und wir müssen über die Struktur
nichts wissen und nichts parsen. „Bewerte die Sachrichtigkeit von 0–5" ist damit
ausdrückbar, ohne dass dieser Code je von Sachrichtigkeit gehört hat.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.mcp.auth import has_auth_token
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

#: Der Name, an dem die Schleife das Ende erkennt. Konstante statt Literal, weil
#: ihn zwei Module vergleichen (hier gebaut, in ``agent_loop`` erkannt).
SUBMIT_RESULT = "submit_result"

_SUBMIT_DESCRIPTION = (
    "Schliesse die Arbeit ab. Rufe dieses Werkzeug GENAU EINMAL, wenn du fertig "
    "bist — es beendet den Lauf. Solange du es nicht rufst, arbeitest du weiter. "
    "``text`` ist die Antwort in Prosa fuer einen Menschen. ``result`` traegt "
    "das maschinenlesbare Ergebnis; wer diesen Lauf gestartet hat, wertet es aus."
)

_TEXT_DESCRIPTION = (
    "Die Antwort in Prosa. Nenne, worauf du dich stuetzt, und sage ausdruecklich, "
    "was du NICHT pruefen konntest."
)

_FREE_RESULT_DESCRIPTION = (
    "Frei geformtes Ergebnis als Objekt. Ohne vorgegebenes Schema waehlst du die "
    "Schluessel selbst — nimm sprechende, und halte Werte, die verglichen werden "
    "sollen (Noten, Zaehlungen, Ja/Nein), aus dem Prosatext heraus."
)


def submit_result_tool(result_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Das Abschluss-Werkzeug, wahlweise auf das Schema des Aufrufers geformt.

    Ohne Schema ist ``result`` ein freies Objekt und **freiwillig** — nicht jeder
    Auftrag hat ein strukturiertes Ergebnis. Mit Schema ist es **Pflicht**: wer
    eine Form verlangt hat, kann mit einer Antwort ohne sie nichts anfangen.
    """
    pflicht = ["text", "result"] if result_schema else ["text"]
    ergebnis = result_schema or {
        "type": "object",
        "description": _FREE_RESULT_DESCRIPTION,
    }
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_RESULT,
            "description": _SUBMIT_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": _TEXT_DESCRIPTION},
                    "result": ergebnis,
                },
                "required": pflicht,
            },
        },
    }


def build_agent_tools(
    *,
    result_schema: dict[str, Any] | None = None,
    allow_curation: bool = True,
    blocked_tools: list[str] | None = None,
    include_submit: bool = True,
) -> list[dict[str, Any]]:
    """Der volle Katalog plus ``submit_result``.

    ``allow_curation=False`` nimmt die kuratierenden Werkzeuge auch dann heraus,
    wenn eine Anmeldung vorliegt — ein Gastgeber darf einen rein lesenden Lauf
    verlangen, und eine Qualitaetspruefung aendert nichts.

    ``blocked_tools`` (A4c-2b) ist die Werkzeug-Sperre aus Safety/Policy. Der
    Chat-Zug bringt sie mit; der Agent-Endpunkt hat keine und reicht nichts
    herein. Sie greift VOR ``submit_result``, denn das Abschluss-Werkzeug ist
    virtuell — es geht nie an den MCP und darf nicht sperrbar sein, sonst nimmt
    eine Sperre dem Lauf seine Ziellinie.

    ``include_submit=False`` (A4c-2b) laesst es ganz weg: im Chat liest niemand
    das strukturierte ``result``, und seine Beschreibung verlangt einen
    zusaetzlichen Modellzug, nur um zu sagen, was die Prosa-Antwort schon sagt.
    ``run_agent_loop`` endet dort ueber ``stop_reason='text'``.

    ``list(TOOL_DEFINITIONS)`` und nicht die Modul-Globale selbst: unten wird
    angehaengt, und eine Referenz schriebe in den Katalog. Genau so wuchs er im
    E2-Fund bei jedem Zug um einen Eintrag.
    """
    tools = list(TOOL_DEFINITIONS)
    if allow_curation and has_auth_token():
        tools.extend(CURATION_TOOL_DEFINITIONS)
    if blocked_tools:
        gesperrt = set(blocked_tools)
        tools = [t for t in tools if t["function"]["name"] not in gesperrt]
    if include_submit:
        tools.append(submit_result_tool(result_schema))
    return tools
