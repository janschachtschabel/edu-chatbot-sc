"""Toleranter JSON-Ausschnitt aus verrauschtem MCP-Text.

Teil der Fassade ``boerdi.services.mcp.parsers``. Eigenes Modul, weil der Scanner
nichts über Karten oder Themenseiten weiß — er sucht rein syntaktisch das erste
balancierte ``{...}``. Vier Verbraucher: die Kombi-Suche und die Schwimmlinien
hier im Paket, dazu ``services/card_reranker.py`` und der respond-Knoten.
"""

from __future__ import annotations


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
