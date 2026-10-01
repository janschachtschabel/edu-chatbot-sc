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

from boerdi.domain.host_capabilities import erlaubt
from boerdi.domain.inline_documents import dokument_werkzeug
from boerdi.domain.result_delivery import ergebnis_werkzeug
from boerdi.services.mcp.auth import has_auth_token
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

#: Der Name, an dem die Schleife das Ende erkennt. Konstante statt Literal, weil
#: ihn zwei Module vergleichen (hier gebaut, in ``agent_loop`` erkannt).
SUBMIT_RESULT = "submit_result"

#: Werkzeuge, die im Katalog stehen, aber KEINEM Lauf angeboten werden.
#:
#: ``search_skill`` (Nutzer-Entscheid 2026-08-13): der Weg zu einer Anleitung
#: fuehrt ueber die Sammlung, die sie freigegeben hat. Die Definition bleibt im
#: Katalog — sie beschreibt ein Werkzeug, das der MCP-Server hat, und ein
#: Bestands-Waechter nennt sie —, aber kein Pfad reicht sie dem Modell.
AUS_DEM_KATALOG = frozenset({"search_skill"})

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
    include_ergebnis: bool = False,
    include_dokument: bool = False,
    tool_mode: str | None = None,
    wissen_tool: dict[str, Any] | None = None,
    antwort_tool: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Der volle Katalog plus ``submit_result``.

    ``antwort_tool`` (Plan 2026-09-30) legt ``respond_to_user`` dazu — die
    Antwort samt Schnellantworten in einem Aufruf, gebaut von
    ``domain/antwort_werkzeug``. Eine Ziellinie wie ``submit_result`` und
    deshalb wie die anderen virtuellen Werkzeuge nach Sperre und Modus.

    ``allow_curation=False`` nimmt die kuratierenden Werkzeuge auch dann heraus,
    wenn eine Anmeldung vorliegt — ein Gastgeber darf einen rein lesenden Lauf
    verlangen, und eine Qualitaetspruefung aendert nichts.

    ``blocked_tools`` (A4c-2b) ist die Werkzeug-Sperre aus Safety/Policy. Der
    Chat-Zug bringt sie mit, der Agent-Endpunkt seit AG-4 Teil B aus seinem
    eigenen Gate (``agent_gate``). Sie greift VOR ``submit_result``, denn das Abschluss-Werkzeug ist
    virtuell — es geht nie an den MCP und darf nicht sperrbar sein, sonst nimmt
    eine Sperre dem Lauf seine Ziellinie.

    ``include_submit=False`` (A4c-2b) laesst es ganz weg: im Chat liest niemand
    das strukturierte ``result``, und seine Beschreibung verlangt einen
    zusaetzlichen Modellzug, nur um zu sagen, was die Prosa-Antwort schon sagt.
    ``run_agent_loop`` endet dort ueber ``stop_reason='text'``.

    ``include_ergebnis`` (J1) legt ``liefere_ergebnis`` dazu — den Kanal des
    **Chat-Zuges** fuer das maschinenlesbare Ergebnis. Er schliesst sich mit
    ``include_submit`` aus, und das ist Absicht: ``submit_result`` beendet den
    Lauf, ``liefere_ergebnis`` nicht. Beide zugleich hiessen zwei Ziellinien —
    und die schnellere naehme der Prosa ihren Zug, also genau das, wogegen J1
    gebaut ist. Der Chat-Zug nimmt den zweiten, ``/api/agent`` den ersten.

    ``tool_mode`` (O-A) ist die Erlaubnis der EINBETTUNG: ``read-only`` nimmt die
    schreibenden Werkzeuge heraus, ``curate`` zusaetzlich den Blick nach draussen
    (Wikipedia, fremde Adressen), ``full`` und ``None`` lassen alles. Er steht
    neben ``allow_curation`` und nicht an seiner Stelle, weil die beiden
    verschiedene Fragen beantworten: jener „darf in diesem LAUF geschrieben
    werden", dieser „was hat der GASTGEBER erlaubt". Ein Browser-Plugin, das den
    Chatbot als Kuratierungswerkzeug fahren will, sagt es hier — und dasselbe
    Wort erreicht ueber ``domain/host_capabilities.prompt_block`` das Modell,
    damit es nicht verspricht, was ihm gleich fehlt. Der Filter greift VOR den
    virtuellen Werkzeugen: eine Anzeige-Entscheidung darf dem Lauf nicht seine
    Ziellinie nehmen.

    ``wissen_tool`` (P) legt die interne Wissensdatenbank dazu — gebaut von
    ``agent_knowledge.wissen_werkzeug`` aus der gepflegten Bereichsliste. Als
    fertige Erklaerung und nicht als Bereichsliste, damit dieses Modul nichts
    ueber RAG wissen muss. Virtuell wie die anderen: nicht sperrbar, denn ein
    Bestand in der eigenen Datenbank ist keine Gefahr, die eine Sperre abwendet.

    ``include_dokument`` (D2) legt ``zeige_dokument`` dazu — das Werkzeug, mit
    dem das Modell ein fertiges Arbeitsergebnis als eigene Box LIEFERT, statt
    dass ``turn_persist`` es aus dem Antworttext rät. Der Chat-Zug setzt es,
    ``/api/agent`` nicht: dort liest niemand eine Box, und die Beschreibung
    kostete nur Prompt. Es steht **nach** dem Sperrfilter und ist damit nicht
    sperrbar — dieselbe Begründung wie bei den beiden anderen virtuellen: eine
    Sperre darauf verhinderte keine Gefahr, sie nähme dem Lauf nur die
    Möglichkeit, sein Ergebnis auszuliefern.

    ``list(TOOL_DEFINITIONS)`` und nicht die Modul-Globale selbst: unten wird
    angehaengt, und eine Referenz schriebe in den Katalog. Genau so wuchs er im
    E2-Fund bei jedem Zug um einen Eintrag.

    **``search_skill`` faellt heraus** (Nutzer-Entscheid 2026-08-13). Der Weg zu
    einer Anleitung fuehrt ueber die Sammlung, die sie freigegeben hat, nicht
    ueber eine freie Suche. Gemessen am selben Tag: mit der nodeId einer
    Fachsammlung liefert das Werkzeug ohnehin nichts (die Anleitungen liegen im
    Arbeitsbereich, die Sammlung fuehrt nur die Freigabeliste) — und es sagt dem
    Modell dann, das Nichts sei normal. Ein Lauf ohne Anleitung, der nicht
    merkt, dass es eine gab, ist der schlechteste Ausgang.
    """
    tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in AUS_DEM_KATALOG]
    if allow_curation and has_auth_token():
        tools.extend(CURATION_TOOL_DEFINITIONS)
    if blocked_tools:
        gesperrt = set(blocked_tools)
        tools = [t for t in tools if t["function"]["name"] not in gesperrt]
    if tool_mode:
        tools = [t for t in tools if erlaubt(t["function"]["name"], tool_mode)]
    if wissen_tool:
        tools.append(wissen_tool)
    if include_dokument:
        tools.append(dokument_werkzeug())
    if include_submit:
        tools.append(submit_result_tool(result_schema))
    if include_ergebnis:
        tools.append(ergebnis_werkzeug(result_schema))
    if antwort_tool:
        tools.append(antwort_tool)
    return tools
