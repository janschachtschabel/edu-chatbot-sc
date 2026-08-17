"""Die Werkzeugliste der Agent-Schleife (A1) und des Hybrid (H2).

Die Muster-Engine lässt ein Muster auswählen, welche Werkzeuge das Modell sieht
(``response_tool_selection._select_active_tools``). Die Agent-Schleife tut das
ausdrücklich nicht: sie gibt den GANZEN Katalog und überlässt die Wahl dem
Modell — das ist der Unterschied, um den es geht.

Der **Hybrid** (``muster_katalog``) setzt einen dritten Weg daneben: er gibt
ebenfalls den ganzen Katalog, legt aber ``waehle_vorgehen`` davor. Damit wählt
weiterhin ein Muster die Werkzeuge — nur zieht es nicht der Klassifikator im
Voraus, sondern das Modell selbst, wenn es die Lage kennt. Die redaktionell
gepflegten Muster bleiben dabei die Quelle; neu ist nur, wer sie aufschlägt.

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

from boerdi.domain.inline_documents import ZEIGE_DOKUMENT, dokument_werkzeug
from boerdi.domain.pattern_catalog import katalog_kurz, katalog_text, waehlbare_muster
from boerdi.domain.pattern_engine import PatternDef
from boerdi.services.mcp.auth import has_auth_token
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

#: Der Name, an dem die Schleife das Ende erkennt. Konstante statt Literal, weil
#: ihn zwei Module vergleichen (hier gebaut, in ``agent_loop`` erkannt).
SUBMIT_RESULT = "submit_result"

#: Der Name, an dem die Schleife den Musterwechsel erkennt (H2/H3). Gleiche
#: Begründung wie oben: hier gebaut, in ``agent_loop`` erkannt.
WAEHLE_VORGEHEN = "waehle_vorgehen"

#: Die Werkzeuge, die nie an den MCP gehen. Ein Muster, das seine Werkzeugliste
#: einschränkt, darf sie nicht mitnehmen: ohne ``waehle_vorgehen`` käme der Lauf
#: aus dem gewählten Muster nicht mehr heraus, ohne ``submit_result`` verlöre er
#: seine Ziellinie. Beides wäre eine Sackgasse, die wie eine Regel aussieht.
VIRTUELLE_WERKZEUGE = frozenset({WAEHLE_VORGEHEN, SUBMIT_RESULT, ZEIGE_DOKUMENT})

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


_VORGEHEN_KOPF = (
    "Waehle das redaktionell gepflegte Vorgehen fuer diese Anfrage und erhalte "
    "seine verbindliche Arbeitsanweisung. Rufe dieses Werkzeug, sobald du weisst, "
    "worum es geht — die Anweisung schaltet zugleich die Werkzeuge frei, die zu "
    "diesem Vorgehen gehoeren. Du darfst mitten im Lauf wechseln, wenn die Lage es "
    "verlangt (Beispiel: eine Suche liefert keine Treffer). Passt keines der "
    "Vorgehen, arbeite ohne und antworte direkt.\n\n"
    "VERFUEGBARE VORGEHEN:\n\n"
)

#: Der Kopfsatz NACH der Wahl (H8-2). Der obere fordert eine Entscheidung; blieb
#: er stehen, forderte er sie in jeder Runde erneut — ein Lauf, der schon gewaehlt
#: hat, waehlte dann wieder statt zu arbeiten.
_VORGEHEN_KOPF_KURZ = (
    "Du arbeitest bereits nach einem Vorgehen und hast seine Anweisung erhalten. "
    "Rufe dieses Werkzeug nur noch, wenn du WECHSELN musst, weil die Lage sich "
    "geaendert hat (Beispiel: die Suche liefert keine Treffer). Sonst arbeite "
    "weiter und antworte.\n\n"
    "VORGEHEN, ZU DENEN DU WECHSELN KANNST:\n\n"
)

_MUSTER_ID_DESCRIPTION = (
    "Kennung des gewaehlten Vorgehens, genau wie in der Liste oben aufgefuehrt."
)


def waehle_vorgehen_tool(
    muster: list[PatternDef], *, kurz: bool = False
) -> dict[str, Any] | None:
    """Das Musterwerkzeug — oder ``None``, wenn nichts waehlbar ist.

    ``None`` statt eines Werkzeugs mit leerem ``enum``: ein Anbieter wuerde das
    leere ``enum`` entweder ablehnen oder das Werkzeug unaufrufbar machen. Beides
    waere ein angekuendigtes Koennen, das der naechste Schritt zuruecknimmt —
    dieselbe Regel wie bei den kuratierenden Werkzeugen.

    ``kurz`` (H8-2) ist die Fassung fuer einen Lauf, der schon gewaehlt hat: eine
    Zeile je Muster statt der Einsatzregeln. **Das ``enum`` bleibt dasselbe** —
    gespart wird an der Beschreibung, nicht an der Auswahl, sonst waere ein
    Muster nach der ersten Wahl unerreichbar.
    """
    waehlbar = waehlbare_muster(muster)
    if not waehlbar:
        return None
    kopf, katalog = ((_VORGEHEN_KOPF_KURZ, katalog_kurz) if kurz
                     else (_VORGEHEN_KOPF, katalog_text))
    return {
        "type": "function",
        "function": {
            "name": WAEHLE_VORGEHEN,
            "description": kopf + katalog(muster),
            "parameters": {
                "type": "object",
                "properties": {
                    "muster_id": {
                        "type": "string",
                        "enum": [m.id for m in waehlbar],
                        "description": _MUSTER_ID_DESCRIPTION,
                    },
                },
                "required": ["muster_id"],
            },
        },
    }


def build_agent_tools(
    *,
    result_schema: dict[str, Any] | None = None,
    allow_curation: bool = True,
    blocked_tools: list[str] | None = None,
    include_submit: bool = True,
    muster_katalog: list[PatternDef] | None = None,
    include_dokument: bool = False,
    katalog_kurz: bool = False,
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

    ``muster_katalog`` (H2) macht aus der Agent-Schleife den **Hybrid**: die
    waehlbaren Muster kommen als ``waehle_vorgehen`` an den Anfang der Liste.
    Ohne den Parameter aendert sich nichts — ``agent`` und ``/api/agent`` bleiben
    die Maschine ohne Muster. Das Werkzeug steht **vorn**, weil die Reihenfolge
    der Liste die Reihenfolge der Arbeit spiegelt (erst das Vorgehen waehlen,
    dann arbeiten, zuletzt ``submit_result``), und **nach** dem Sperrfilter, weil
    es virtuell ist: eine Sperre darauf naehme dem Lauf die Wahl seines Vorgehens
    statt eine Gefahr abzuwenden. Die Gefahr sitzt in den Werkzeugen, die ein
    Muster freigibt — und die filtert ``blocked_tools`` weiterhin.

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
    if include_dokument:
        tools.append(dokument_werkzeug())
    if muster_katalog and (
        vorgehen := waehle_vorgehen_tool(muster_katalog, kurz=katalog_kurz)
    ):
        tools.insert(0, vorgehen)
    if include_submit:
        tools.append(submit_result_tool(result_schema))
    return tools
