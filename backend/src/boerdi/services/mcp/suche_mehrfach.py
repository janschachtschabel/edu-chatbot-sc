"""Mehrere Inhaltssuchen in einem Aufruf (Plan 2026-11-14, N4).

Für einen Lernpfad, eine Stunde oder eine Reihe sucht die KI je Schritt ein Material — bisher vier
bis sechs ``search_wlo_content``-Aufrufe, je Aufruf eine Runde oder eine Wartezeit. Der MCP-Server
kennt ab dem Stand vom 14.11. ``search_wlo_content_many``: bis zu acht Anfragen ``{id, query,
filters?}``, je bis zu fünf Treffer in Kurzform unter ``results[id]``. Gemessen am neuen Stand
(lokal, 14.11.): fünf Suchen in einem Aufruf 0,6–1,1 s, nacheinander 4–5 s.

Das Werkzeug steht NICHT im Katalog (``tool_defs.TOOL_DEFINITIONS``): Den reicht der Muster-Weg
als Ganzes weiter, und ein Server ohne das Werkzeug wiese jeden Aufruf ab. Angeboten wird es nur,
wenn der bereitgestellte Server es führt (:mod:`faehigkeiten`).

Die Antwort reist als Umschlag und Text (:func:`mit_umschlag`): vorn der strukturierte Teil des
Servers als JSON, dahinter sein Markdown (rund 6 kB für 15 Treffer). Aus dem Umschlag entstehen
die Karten (``parsers.parse_search_many_cards``) — ohne sie sähe die Person die Treffer nicht:
Die Endverarbeitung nimmt Links aus dem Antworttext (Review N4, M1). Das Modell bekommt nur den
Text (``domain/tool_result_redaction``), ungedeckelt: Der Server begrenzt selbst (8 Anfragen, je
5 Treffer in Kurzform), und was er nicht beantworten konnte, steht am Ende unter „Nicht
beantwortet — KEIN Befund ‚keine Treffer‘“. Eine solche Teilantwort hält der Cache nicht
(``client._cachebar``, Feld ``missing``), eine unvollständige Teilsuche (``incomplete``) nur für
Sekunden (``domain/mcp_unvollstaendig``).

Die Materialien-Box ist gedeckelt (``display_rules.groups``). Ein Zug mit diesem Werkzeug nimmt
den Deckel des Lernpfads (Vorgabe 5, höchstens 8), und die Karten stehen reihum je Anfrage: So
bekommt jeder Teil eine Karte, solange der Deckel reicht (Review 2, Befund 1). Die Titel, die die
KI im Text nennt, bleiben stehen (``turn_links``). Am Endpunkt ``/api/agent`` gibt es keine
Karten — deshalb verlangt die Beschreibung Titel und Link im Text.
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.services.mcp import faehigkeiten

WERKZEUG: Final = "search_wlo_content_many"
HOECHSTENS_ANFRAGEN: Final = 8

_FILTER: Final[dict[str, Any]] = {
    "educationalContext": {"type": "string",
                           "description": "Bildungsstufe als Bezeichnung, z.B. 'Sekundarstufe I'."},
    "discipline": {"type": "string", "description": "Fach als Bezeichnung, z.B. 'Physik'."},
    "userRole": {"type": "string",
                 "description": "Zielgruppe. Nur setzen, wenn ausdruecklich verlangt."},
    "learningResourceType": {"type": "string",
                             "description": "Materialtyp, z.B. 'Video', 'Arbeitsblatt'."},
    "publisher": {"type": "string", "description": "Anbieter, z.B. 'Serlo'."},
    "license": {"type": "string",
                "description": "EINE Lizenz, z.B. 'CC BY', 'CC BY-SA', 'CC0'. 'OER' geht hier "
                               "nicht — dafuer search_wlo_content."},
}

DEFINITION: Final[dict[str, Any]] = {
    "type": "function",
    "function": {
        "name": WERKZEUG,
        "description": (
            "Mehrere Inhaltssuchen in EINEM Aufruf — bis zu 8 Anfragen, je bis zu 5 Treffer. "
            "Nimm das statt mehrerer search_wlo_content-Aufrufe, wenn du fuer mehrere Teile "
            "zugleich Material brauchst: je Schritt eines Lernpfads, je Abschnitt einer Stunde, "
            "je Unterthema. Jede Anfrage traegt eine eigene id; die Treffer stehen je id in "
            "Kurzform (Titel, Link, nodeId, Typ, Stufe, Lizenz, kurze Beschreibung). Gemeinsame "
            "Filter gelten fuer alle Anfragen; ein Filter in einer Anfrage ersetzt dort den "
            "gemeinsamen. distinct=true zeigt jedes Material nur bei der Anfrage, zu der es am "
            "besten passt. WICHTIG fuer wahrheitsgemaesse Antworten: Was unter 'Nicht "
            "beantwortet' steht, ist KEIN Befund 'keine Treffer' — sag das oder suche dort "
            "einzeln nach. Nenne je Teil den Titel und den Link des gewaehlten Materials. Im Chat "
            "erscheinen die ersten Treffer zusaetzlich als Karten (reihum je Anfrage, begrenzt); "
            "Links nimmt die Anzeige dort aus dem Text, die Titel bleiben. "
            "NICHT fuer eine einzelne Suche, zum Blaettern oder fuer mehr als 5 Treffer zu einem "
            "Thema (search_wlo_content), nicht in einer Sammlung (search_wlo_within_collection), "
            "nicht zum blossen Zaehlen (count_wlo_content_matches)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "description": "Die Anfragen, 1 bis 8.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string",
                                   "description": "Eigene kurze Kennung, eindeutig im Aufruf, "
                                                  "z.B. 's1' — unter ihr stehen die Treffer."},
                            "query": {"type": "string",
                                      "description": "Nur der Kernbegriff des Themas auf Deutsch "
                                                     "— nie der ganze Satz."},
                            "filters": {"type": "object", "properties": _FILTER,
                                        "description": "Filter nur fuer diese Anfrage."},
                        },
                        "required": ["id", "query"],
                    },
                },
                **_FILTER,
                "maxResults": {"type": "integer",
                               "description": "Treffer je Anfrage (1-5, Vorgabe 3)."},
                "distinct": {"type": "boolean",
                             "description": "Jedes Material nur einmal, bei der am besten "
                                            "passenden Anfrage."},
            },
            "required": ["queries"],
        },
    },
}

_ZU_VIELE: Final = ("Hoechstens {n} Anfragen je Aufruf, genannt wurden {genannt}. Nichts wurde "
                    "gesucht: teile die Anfragen auf mehrere Aufrufe auf.")
_KEINE: Final = ("queries muss eine Liste mit 1 bis {n} Anfragen sein, jede mit id und query. "
                 "Nichts wurde gesucht.")
_FILTER_UNBEKANNT: Final = ("Unbekannter Filter {namen} in Anfrage {kennung}. Erlaubt sind: "
                            "{erlaubt}. Nichts wurde gesucht.")


def angeboten() -> bool:
    """Führt der bereitgestellte Server das Werkzeug?"""
    return faehigkeiten.kennt(WERKZEUG, "queries")


def definitionen() -> list[dict[str, Any]]:
    """Die Definition für das Modell — leer, solange der Server das Werkzeug nicht führt."""
    return [DEFINITION] if angeboten() else []


def nicht_moeglich(werkzeug: str, argumente: dict[str, Any]) -> str | None:
    """Ein Satz für die KI, wenn der Aufruf so nicht gehen kann — sonst ``None``. Keine Liste,
    keine Anfrage oder mehr als acht wiese der Server mit einer Schemameldung ab; still kürzen
    hieße, dass Schritte ohne Suche bleiben und wie „keine Treffer“ aussehen."""
    if werkzeug != WERKZEUG:
        return None
    anfragen = argumente.get("queries")
    if not isinstance(anfragen, list) or not anfragen:
        return _KEINE.format(n=HOECHSTENS_ANFRAGEN)
    if len(anfragen) > HOECHSTENS_ANFRAGEN:
        return _ZU_VIELE.format(n=HOECHSTENS_ANFRAGEN, genannt=len(anfragen))
    # Einen unbekannten Filternamen ließe der Server still weg: Die Suche liefe ungefiltert und
    # sähe gefiltert aus (Review 2, Befund 4). ``ContentSearchManyArgs`` lässt ihn deshalb stehen.
    for anfrage in anfragen:
        filter_ = anfrage.get("filters") if isinstance(anfrage, dict) else None
        fremd = sorted(str(n) for n in set(filter_) - set(_FILTER)) if isinstance(
            filter_, dict) else []
        if fremd:
            return _FILTER_UNBEKANNT.format(
                namen=", ".join(f"'{n[:40]}'" for n in fremd[:3]),
                kennung=f"'{str(anfrage.get('id'))[:40]}'", erlaubt=", ".join(_FILTER))
    return None


def mit_umschlag(strukturiert: dict[str, Any] | None, text: str) -> str:
    """Die Antwort, wie der Chatbot sie weiterreicht: der strukturierte Teil des Servers als JSON
    vorn, sein Text dahinter — die Form der übrigen JSON-fähigen Werkzeuge. Aus dem Umschlag
    entstehen die Karten und die Kennzeichen für den Cache; das Modell bekommt nur den Text.

    Ohne strukturierten Teil (ein Fehler, ein Server ohne ihn) bleibt der Text, wie er ist; ebenso,
    wenn der Text schon JSON ist (``outputFormat: json`` kam mit rohen Argumenten durch)."""
    if not isinstance(strukturiert, dict) or not isinstance(strukturiert.get("results"), dict):
        return text
    if text.lstrip().startswith("{"):
        return text
    return json.dumps(strukturiert, ensure_ascii=False) + "\n\n" + text
