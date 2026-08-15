"""Toleranter JSON-Ausschnitt aus verrauschtem MCP-Text.

Teil der Fassade ``boerdi.services.mcp.parsers``. Eigenes Modul, weil der Scanner
nichts über Karten oder Themenseiten weiß — er sucht rein syntaktisch das erste
balancierte ``{...}``. Vier Verbraucher: die Kombi-Suche und die Schwimmlinien
hier im Paket, dazu ``services/card_reranker.py`` und der respond-Knoten.

:func:`load_envelope` ist die zweite Hälfte davon — „lies das JSON, notfalls den
Ausschnitt" stand bis 2026-08-15 **sechsmal** fast gleich im Paket, und die
Kopien liefen auseinander: drei hatten den Rückfall (``parse_search_all_cards``,
``parse_topic_page_swimlanes``, der Registry-Leser), drei nicht
(``parse_wlo_cards``, ``parse_total_count``, ``parse_wlo_topic_page_cards``).
Genau die ohne verloren ihre Karten und ihre Trefferzahl, als der MCP-Server
anfing, einen zweiten Textblock hinter die Nutzlast zu hängen. Jetzt ein
Besitzer — und die Sammlungs-Prüfung des Skill-Anstoßes als siebter Leser
derselben Regel.
"""

from __future__ import annotations

import json


def _first_json_object(s: str) -> str | None:
    """Erstes balanciertes ``{...}``-Objekt aus einem String (defensiv, falls
    der MCP-Return Begleittext/Meta nach dem Envelope enthält)."""
    i = s.find("{")
    if i < 0:
        return None
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(s)):
        c = s[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[i:j + 1]
    return None


def load_envelope(raw_text: str) -> object | None:
    """Das JSON eines Werkzeugergebnisses, oder ``None`` — auch mit Begleittext.

    Zuerst der ganze Text, dann der Ausschnitt: ein Ergebnis, das NUR aus dem
    Umschlag besteht, kostet damit keinen Scan, und eines mit angehängtem Block
    wird trotzdem gelesen.

    **Warum das eine Funktion ist und nicht viermal derselbe try/except:** der
    MCP-Server hängt seit dem Skill-Umbau die Freigabeliste der angefragten
    Sammlung als eigenen ``content``-Block an — deutsche Prosa hinter der
    Nutzlast, und der Client fügt beide zu einem Text zusammen. Wer nur
    ``json.loads`` rief, bekam ab da nichts mehr. Gemessen 2026-08-15 gegen die
    künftige Antwortform: ``parse_wlo_cards`` 2 → 0 Karten, ``parse_total_count``
    4 → 0, während die beiden Geschwister mit Rückfall unberührt blieben.

    Wirft nie: auf dem Rückweg stehen auch Markdown-Antworten und Fehlertexte,
    und ein Zug darf daran nicht kippen.
    """
    try:
        return json.loads(raw_text)
    except (ValueError, TypeError):
        ausschnitt = _first_json_object(raw_text or "")
        if not ausschnitt:
            return None
        try:
            return json.loads(ausschnitt)
        except ValueError:
            return None
