"""Karten aus einem Werkzeug-Ergebnis einsammeln (A4c-2a).

Der Block stand bis A4c-2a inline in ``tool_loop._run_tool_loop``. Er ist
verhaltensgleich hierher gezogen, weil mit dem Agent-Modus ein **zweiter**
Aufrufer dazukommt: dort baut nicht der Muster-Tool-Loop die Karten, sondern die
Agent-Schleife — und beide müssen dieselbe Ernte einfahren, sonst misst der
A/B-Vergleich einen Unterschied, den er selbst gebaut hat.

Vier Dinge passieren hier, und drei davon sind teuer erkaufte Erfahrung:

* **Parser-Auswahl je Werkzeug.** ``search_wlo_topic_pages`` hat einen eigenen
  Parser (der Standard liest ``nodeId`` und ignoriert ``variants`` → Karten ohne
  ``topic_pages``-Feld → das Frontend rendert sie als flache Inhalts-Karte ohne
  Themenseiten-Knopf). ``search_wlo_all`` antwortet in DREI Töpfen statt mit
  einem ``results`` — der Standardparser gab darauf null Karten zurück (W9b,
  live gemessen: 13 verlorene Treffer).
* **Sammlungen markieren**, damit die UI sie als Sammlung erkennt.
* **Themenseiten in bestehende Karten mischen** statt sie danebenzustellen.
* **Entdoppeln nach ``node_id``**, dabei Themenseiten-Angaben anreichern.

Wer die Karten „mal eben selbst" parst, verliert alle vier — und zwar still.
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


def collect_cards(
    all_cards: list[dict], tool_name: str, result_text: str
) -> list[dict]:
    """Karten aus ``result_text`` lesen und in ``all_cards`` einsortieren.

    Mutiert ``all_cards`` in-place (entdoppelt, reichert an) und gibt die Karten
    **dieses** Aufrufs zurück — der Tool-Loop braucht sie getrennt für die
    Redaktion des Ergebnistexts ans LLM. Ein Werkzeug ohne Karten liefert eine
    leere Liste und lässt ``all_cards`` unberührt.
    """
    if tool_name in CARD_YIELDING_TOOLS:
        # search_wlo_topic_pages has its OWN parser — the standard
        # parse_wlo_cards reads ``nodeId`` and ignores ``variants``,
        # producing cards without the ``topic_pages`` array. Without
        # that array isTopicPage() returns false → cards render as
        # plain Inhalt-cards instead of topic-page-cards with the
        # 🌐 Themenseite button. The dedicated parser fixes this.
        if tool_name == "search_wlo_topic_pages":
            from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards
            cards = parse_wlo_topic_page_cards(result_text)
        elif tool_name == "search_wlo_all":
            # W9b (2026-08-01): das Kombi-Werkzeug antwortet in DREI
            # Töpfen (content/collections/topicPages) statt mit einem
            # Top-Level-``results``. ``parse_wlo_cards`` gab darauf
            # null Karten zurück — live gemessen gingen so 13 Treffer
            # verloren, sobald das Modell es selbst aufrief (M06
            # bietet es an, seit W5-2a ist es das Standard-Suchtool).
            # Der Prefetch-Pfad hatte dafür längst einen eigenen
            # Splitter in ``respond.py``; hier fehlte er schlicht.
            from boerdi.services.mcp.parsers import parse_search_all_cards
            _pots = parse_search_all_cards(result_text)
            cards = (
                _pots["content"] + _pots["collections"] + _pots["topic_pages"]
            )
        else:
            cards = parse_wlo_cards(result_text)
    else:
        cards = []
    # Mark cards from search_wlo_collections as collections
    if tool_name == "search_wlo_collections":
        for c in cards:
            c.setdefault("node_type", "collection")
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
