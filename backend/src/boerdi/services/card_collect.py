"""Karten aus einem Werkzeug-Ergebnis einsammeln (A4c-2a).

Der Block stand bis A4c-2a inline in ``tool_loop._run_tool_loop``. Er ist
verhaltensgleich hierher gezogen, weil mit dem Agent-Modus ein **zweiter**
Aufrufer dazukommt: dort baut nicht der Muster-Tool-Loop die Karten, sondern die
Agent-Schleife — und beide müssen dieselbe Ernte einfahren, sonst misst der
A/B-Vergleich einen Unterschied, den er selbst gebaut hat.

Drei Dinge passieren hier, und alle drei sind teuer erkaufte Erfahrung:

* **Parser-Auswahl je Werkzeug.** ``search_wlo_topic_pages`` hat einen eigenen
  Parser (der Standard liest ``nodeId`` und ignoriert ``variants`` → Karten ohne
  ``topic_pages``-Feld → das Frontend rendert sie als flache Inhalts-Karte ohne
  Themenseiten-Knopf). ``search_wlo_all`` antwortet in DREI Töpfen statt mit
  einem ``results`` — der Standardparser gab darauf null Karten zurück (W9b,
  live gemessen: 13 verlorene Treffer).
* **Themenseiten in bestehende Karten mischen** statt sie danebenzustellen.
* **Entdoppeln nach ``node_id``**, dabei Themenseiten-Angaben anreichern.

Wer die Karten „mal eben selbst" parst, verliert alle drei — und zwar still.
"""

from __future__ import annotations

import logging
from typing import Final

from boerdi.services.mcp.parsers import parse_wlo_cards

logger = logging.getLogger(__name__)

# Only search/content tools produce card-shaped output. Vocabulary and *_info
# tools return markdown documentation that would pollute the card list (e.g.
# "## Vokabular: Bildungsstufe" becoming a card).
#
# W9b (2026-08-01): von funktions-lokal auf Modulebene gehoben. Vorher wurde die
# Menge bei JEDEM Tool-Aufruf neu gebaut und war von außen nicht prüfbar — und
# genau dadurch fiel nicht auf, dass ``search_wlo_all`` fehlte, obwohl es seit
# W5-2a das Standard-Suchwerkzeug ist. Ein Werkzeug, das hier fehlt, scheitert
# NICHT: es liefert stillschweigend null Karten.
CARD_YIELDING_TOOLS: Final = {
    "search_wlo_collections", "search_wlo_content",
    "search_wlo_topic_pages", "get_collection_contents",
    "get_node_details",
    # MCP v2 — Discovery/Listing-Tools liefern auch Karten
    # (Fachportale + Sub-Sammlungen sind klickbare Cards).
    "get_subject_portals",
    "browse_collection_tree",
    # W9b: Kombi-Suche (drei Töpfe) + die zwei neuen Karten-Werkzeuge.
    "search_wlo_all",
    "search_wlo_within_collection",
    "get_related_content",
}


def parse_cards_for_tool(tool_name: str, result_text: str) -> list[dict]:
    """Die Karten EINES Werkzeug-Ergebnisses — mit dem Parser, der dazu passt.

    Der erste der drei Punkte aus dem Modul-Docstring, herausgelöst, weil er
    **drei** Aufrufer hat: diese Datei und zweimal ``tool_loop_messages`` für die
    Prefetch-Einspeisung. Bis 2026-08-16 stand die Weiche dort als eigene Kopie,
    die der W9b-Fix nie erreichte — gemessen an der echten „Optik"-Antwort gab
    der Prefetch-Zweig 0 statt 12 Karten zurück, und weil ``search_wlo_all``
    genau das Werkzeug ist, das der Prefetch selbst wählt, war das der
    Normalfall. Der Fehler war nicht die Kopie, sondern dass es eine gab.

    Maßgeblich für den Kartentyp ist der ``nodeType`` des Servers. Hier stand
    bis 2026-08-16 ein ``setdefault("node_type", "collection")`` für
    ``search_wlo_collections`` — er konnte nie greifen: der Server setzt das
    Feld immer (``formatter.ts`` leitet es aus ``ccm:map`` ab, das
    Ausgabe-Schema erzwingt es), und der Envelope-Leser setzt es ebenfalls
    immer, notfalls auf ``"content"``. Wer den Typ hier erzwingen wollte,
    überschriebe also eine Auskunft, statt eine Lücke zu füllen.
    """
    if tool_name == "search_wlo_topic_pages":
        # Der Standardparser liest ``nodeId`` und ignoriert ``variants`` →
        # Karten ohne ``topic_pages``-Feld → das Frontend rendert sie als
        # flache Inhalts-Karte ohne Themenseiten-Knopf.
        from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards
        karten = parse_wlo_topic_page_cards(result_text) or []
        if karten:
            return karten
        # Unter DIESEM Namen kommen zwei Antwortformen an. Der Prefetch zerlegt
        # das ``search_wlo_all``-Envelope und etikettiert dessen
        # ``topicPages``-Topf hiermit (``graph/nodes/respond.py``:196-201). Der
        # Topf ist aber eine gewöhnliche FormattedNode-Liste (``nodeId`` +
        # ``topicPageUrl``), nicht die ``collectionId``+``variants``-Form des
        # dedizierten Werkzeugs — der Themenseiten-Parser verwirft sie deshalb
        # vollständig (``if not cid: continue``, ``parsers/topic_pages.py``:118).
        # Live gemessen 2026-08-16 an „Optik": content 10→10 Karten,
        # collections 2→2, topicPages 2→0. Verloren gingen genau die
        # Sammlungen MIT Themenseite, also die kuratierten.
        # Ein leeres Ergebnis kostet hier nichts: hat der Topf gar keine
        # Treffer, geben beide Parser dasselbe ``[]`` zurück.
        #
        # ``_als_themenseiten_karten`` ist derselbe Schritt, den
        # ``parse_search_all_cards`` auf seinen Themenseiten-Topf anwendet:
        # der Standardparser liefert ``node_type='collection'`` ohne
        # Varianten, und damit gilt die Karte flussabwärts als gewöhnliche
        # Sammlung statt als Themenseite.
        from boerdi.services.mcp.parsers import _als_themenseiten_karten
        return _als_themenseiten_karten(parse_wlo_cards(result_text) or [])
    if tool_name == "search_wlo_all":
        # Drei Töpfe statt einem ``results`` — der Standardparser gibt 0 zurück.
        from boerdi.services.mcp.parsers import parse_search_all_cards
        toepfe = parse_search_all_cards(result_text)
        return toepfe["content"] + toepfe["collections"] + toepfe["topic_pages"]
    return parse_wlo_cards(result_text) or []


def collect_cards(
    all_cards: list[dict], tool_name: str, result_text: str
) -> list[dict]:
    """Karten aus ``result_text`` lesen und in ``all_cards`` einsortieren.

    Mutiert ``all_cards`` in-place (entdoppelt, reichert an) und gibt die Karten
    **dieses** Aufrufs zurück — der Tool-Loop braucht sie getrennt für die
    Redaktion des Ergebnistexts ans LLM. Ein Werkzeug ohne Karten liefert eine
    leere Liste und lässt ``all_cards`` unberührt.
    """
    cards = (
        parse_cards_for_tool(tool_name, result_text)
        if tool_name in CARD_YIELDING_TOOLS
        else []
    )
    # Merge topic_pages from search_wlo_topic_pages into existing cards
    if tool_name == "search_wlo_topic_pages":
        existing_by_id = {c["node_id"]: c for c in all_cards if c.get("node_id")}
        for c in cards:
            nid = c.get("node_id", "")
            tp_list = c.get("topic_pages", [])
            if nid and nid in existing_by_id and tp_list:
                existing = existing_by_id[nid]
                existing_vids = {
                    v.get("variant_id") for v in existing.get("topic_pages", [])
                }
                for v in tp_list:
                    if v.get("variant_id") not in existing_vids:
                        existing.setdefault("topic_pages", []).append(v)
                # If the existing card came from a non-topic-page tool
                # (e.g. get_subject_portals → node_type='content'),
                # promote it to 'collection' now that it has topic
                # pages — otherwise the frontend's isTopicPage()
                # check fails and the card renders as a flat
                # Inhalt-card without the 🌐 Themenseite button.
                existing["node_type"] = "collection"
    # Deduplicate by node_id — enrich topic_pages on collision
    existing_by_id = {c.get("node_id"): c for c in all_cards if c.get("node_id")}
    for c in cards:
        _nid = c.get("node_id")
        if _nid and _nid in existing_by_id:
            _ex = existing_by_id[_nid]
            if not _ex.get("topic_pages") and c.get("topic_pages"):
                _ex["topic_pages"] = c["topic_pages"]
            if not _ex.get("topic_page_url") and c.get("topic_page_url"):
                _ex["topic_page_url"] = c["topic_page_url"]
        elif _nid:
            all_cards.append(c)
            existing_by_id[_nid] = c
        else:
            all_cards.append(c)
    return cards
