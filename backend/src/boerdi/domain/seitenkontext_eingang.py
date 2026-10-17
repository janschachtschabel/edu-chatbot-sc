"""Der Seitenkontext am Eingang: Längen deckeln, bevor er weiterwandert (Paket 9).

``Environment.page_context`` ist ein offenes ``dict[str, Any]``: das Widget
schickt Kennungen, Slugs, Suchbegriff, Filter und den sichtbaren Seitentext, ein
Gastgeber darf eigene Felder setzen. Bis Paket 9 hatte nichts davon eine Grenze —
ein Suchbegriff mit zwei Megabyte lief durch die Entschärfung der Endmarken, den
Klassifikator und beide Prompt-Wege (Review Paket 7, CRITICAL).

Gekürzt, nicht abgewiesen: der Seitenkontext ist Zusatzwissen, kein Auftrag — der
Zug soll laufen. ``result_schema`` dagegen ist ein Vertrag und wird abgewiesen
(``api/schemas``). Der Seitentext behält das Budget der Prompts (EK10b).
In der Domäne, weil ``services/page_context`` das Budget hier liest und
``api/schemas`` nichts aus ``services`` laden kann: ``services/mcp`` lädt
umgekehrt die Argument-Modelle aus ``api/schemas``.
"""

from __future__ import annotations

from typing import Any, Final

#: Budget je TEXTABSCHNITT des Seitenblocks (Gastgeber-Seitentext, gespeicherter
#: Volltext, kompendialer Text, Heuristik-Rohblock) in den ANTWORT-Prompts
#: (Muster-Antwort + Agent). Nutzer-Entscheid 2026-08-21 (EK10, auf 200 000
#: erweitert in EK10b): der Transport ist seit L1 ungedeckelt, und hinter
#: Login-Wänden, in Intranets und auf dem Prüftisch ist dieser Text die EINZIGE
#: Inhaltsquelle — ein knappes Budget verwarf den Rest stillschweigend. 200 000
#: ist die Skala des letzten Vertrags-Deckels (``MAX_RESULT_SCHEMA_CHARS`` und
#: seit EK10b auch ``AgentRequest.instruction``) — praktisch „kein Limit", nur
#: eine Notbremse gegen Unfälle. Einzige Ausnahme bleibt der Klassifikator
#: (übergibt 3000): er wählt nur ein Muster, ein Volltext wäre dort reine
#: Kostenlast bei JEDEM Zug und riskierte das Kontextfenster des kleinen Modells.
TEXT_PROMPT_BUDGET = 200_000

#: Was ``page_context_enrich`` aus dem Seitenkontext in die Entities der Sitzung
#: kopiert. Die Werte stammen von der Seite (Dritte): die Prompts zeigen sie
#: gerahmt im Seitenblock, nicht im Dump der bekannten Entities (Paket 9, Review
#: Paket 7 MAJOR 10 — dort standen sie ungerahmt im Systemteil des Klassifikators).
SEITEN_ENTITIES: Final = (
    "node_id", "collection_id", "search_query", "topic_page_slug", "subject_slug",
    "document_title", "page_type",
)

#: Höchstlänge je Feldname; alle übrigen Texte bekommen :data:`MAX_FELD`. Der
#: Seitentext eins über dem Budget, damit ``page_context._trim_text`` das Kürzen
#: noch bemerkt und mit „…“ anzeigt.
_MAX_JE_FELD: Final = {"page_text": TEXT_PROMPT_BUDGET + 1, "page_url": 2048}
MAX_FELD: Final = 500
#: Höchstzahl der Einträge je Liste oder Objekt.
MAX_EINTRAEGE: Final = 50
#: Tiefer verschachtelte Listen und Objekte kommen leer an. Das Widget braucht
#: zwei Ebenen (``search_filters.publisher``).
MAX_TIEFE: Final = 2


def deckle_seitenkontext(wert: Any, feld: str = "", tiefe: int = 0) -> Any:
    """``wert`` mit gedeckelten Texten, Listen, Objekten und Tiefe.

    ``feld`` ist der Schlüssel, unter dem ``wert`` steht (Listeneinträge erben
    ihn); ``tiefe`` zählt die Ebenen ab dem Seitenkontext selbst (0). Zahlen,
    Wahrheitswerte und ``None`` bleiben, wie sie sind.
    """
    if isinstance(wert, str):
        return wert[:_MAX_JE_FELD.get(feld, MAX_FELD)]
    if isinstance(wert, list):
        if tiefe > MAX_TIEFE:
            return []
        return [deckle_seitenkontext(v, feld, tiefe + 1) for v in wert[:MAX_EINTRAEGE]]
    if isinstance(wert, dict):
        if tiefe > MAX_TIEFE:
            return {}
        return {str(k)[:MAX_FELD]: deckle_seitenkontext(v, str(k), tiefe + 1)
                for k, v in list(wert.items())[:MAX_EINTRAEGE]}
    return wert
