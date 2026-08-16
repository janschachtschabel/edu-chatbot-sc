"""Card normalization (P5-4a) — byte-parity port of the pure normalization half
of ALT ``card_pipeline.py``.

First sub-module of the ``domain/cards`` package: Phase-2 normalization — turning
a raw card pool into a deduplicated, node-type-tagged, host-rewritten,
priority-sorted list — plus the pure repo-URL builders it shares with the later
link/selection sub-modules.

Pure domain logic (no I/O): the only outward calls are the config read-fassade
``get_repo_base_url`` / ``rewrite_repo_host_v2`` (sanctioned from ``domain/``). The
MCP-driven ``fetch_card_pool``/``run_pipeline_v2`` and the guide-mode link builders
(``build_card_link``/``annotate_cards_with_link`` — need the not-yet-ported
``guide_mode_service``) are separate later sub-slices.

Deviation from ALT: import root only (``app.services.config_loader`` →
``boerdi.services.config_loader``); the ported function bodies are byte-identical
(AST-diff gate). The link-phase comment block that in ALT sits between these
functions describes builders that live in a later sub-module and is not carried.
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from urllib.parse import quote

from boerdi.services.config_loader import get_repo_base_url, rewrite_repo_host_v2

logger = logging.getLogger(__name__)

# Drei kanonische Intent-Kinder für die Beschaffungs-Strategie.
#
#   "general"            — User fragt nach Material zu einem Thema. Pool
#                          wird auf drei Tools verteilt (Themenseite +
#                          Sammlung + Einzelinhalt), Reihenfolge der Final-
#                          Auswahl bevorzugt Themenseite > Sammlung > Einzel.
#   "type-focus"         — User fragt nach einem konkreten Material-Typ
#                          (Videos, Arbeitsblätter, …). Pool kommt nur von
#                          search_wlo_content mit LRT-Filter.
#   "collection-contents"— User klickte/erwähnte eine bestimmte Sammlung.
#                          Pool ist exakt der get_collection_contents-Output.
IntentKind = Literal["general", "type-focus", "collection-contents"]

# Drei kanonische node_types für die Display-Logik:
#   "topic_page" — Sammlung MIT befülltem topic_pages-Feld (Themenseiten-Card)
#   "collection" — Sammlung OHNE topic_pages (reine Sammlung)
#   "content"    — Einzelinhalt (jeder andere Node)
#
# Vorher: 2 Werte ("collection"/"content") + topic_pages-Subfield-Check.
# Die Drei-Wege-Unterscheidung macht alle Folge-Entscheidungen (URL-Resolution
# in Phase 3, Display in Phase 4) zu einem trivialen Lookup statt einer
# zusammengesetzten Bedingung.
NodeType = Literal["topic_page", "collection", "content"]

# Sortier-Prio nach node_type bei "general"-Intent (kleiner = weiter vorn).
_NODE_TYPE_PRIORITY: dict[str, int] = {
    "topic_page": 0,
    "collection": 1,
    "content": 2,
}


def infer_intent_kind(
    *,
    user_message: str,
    wanted_content_types: set[str] | None = None,
    collection_id: str | None = None,
) -> IntentKind:
    """Heuristik für den Intent-Kind aus User-Message + Kontext.

    Wird in Phase 3 (chat-flow Integration) zentral aufgerufen. Aktuell
    bewusst simpel — komplexere Routing-Entscheidungen (z.B. NLU-basiert)
    können später hinzugefügt werden, ohne :func:`fetch_card_pool` zu ändern.

    Reihenfolge der Checks:
      1. ``collection_id`` gesetzt → ``"collection-contents"`` (höchste Prio,
         User hat explizit eine Sammlung im Fokus).
      2. ``wanted_content_types`` nicht-leer → ``"type-focus"`` (User fragt
         nach einem konkreten Material-Typ).
      3. Sonst → ``"general"``.
    """
    if collection_id:
        return "collection-contents"
    if wanted_content_types:
        return "type-focus"
    return "general"


def _is_render_uuid(value: str) -> bool:
    """True, wenn ``value`` ein 8-4-4-4-12 UUID-Hex-String ist (das Format
    von edu-sharing-Node-IDs)."""
    if not isinstance(value, str) or len(value) != 36:
        return False
    parts = value.split("-")
    if len(parts) != 5 or [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return False
    return all(c in "0123456789abcdefABCDEF" for p in parts for c in p)


def _repo_render_url(node_id: str, repo_base: str) -> str:
    """``{repo}/edu-sharing/components/render/{uuid}`` — Permalink eines
    Nodes innerhalb der edu-sharing-Instanz."""
    return f"{repo_base.rstrip('/')}/edu-sharing/components/render/{node_id}"


def _repo_collection_browse_url(
    node_id: str, repo_base: str, search_query: str = "",
) -> str:
    """``{repo}/edu-sharing/components/collections?id={uuid}[&q=…]`` —
    Browse-Ansicht einer Sammlung (zeigt direkt die enthaltenen Materialien
    statt der Metadaten-Detailseite).

    ``search_query`` wird als ``&q=``-Parameter angehängt, wenn nicht leer.
    Damit landet der User in der gefilterten Browse-Ansicht — passend, weil
    der Bot ja gerade nach genau diesem Begriff gesucht hat.
    """
    base = f"{repo_base.rstrip('/')}/edu-sharing/components/collections?id={node_id}"
    if search_query:
        # ``quote`` mit ``safe=""`` codiert auch Leerzeichen → ``%20`` (nicht
        # ``+``, das ist nur in application/x-www-form-urlencoded gültig).
        # edu-sharing's collections-View versteht beides, aber %20 ist sauberer.
        base += f"&q={quote(search_query, safe='')}"
    return base


def _repo_topic_page_url(node_id: str, repo_base: str) -> str:
    """``{repo}/edu-sharing/components/topic-pages?collectionId={uuid}`` —
    der kuratierte Themenseiten-Renderer von edu-sharing.

    Eine Themenseite ist technisch eine Sammlung (``ccm:map`` mit
    ``ccm:page_config_ref``), soll aber NICHT über den generischen Sammlungs-
    Browse-Link geöffnet werden, sondern über diese Themenseiten-Ansicht.
    Identisch zu dem ``topicPageUrl``, das der MCP-Server via
    ``buildTopicPageUrl`` liefert (gleiches ``collectionId``)."""
    return f"{repo_base.rstrip('/')}/edu-sharing/components/topic-pages?collectionId={node_id}"


def _infer_node_type(card: dict[str, Any]) -> NodeType:
    """Drei-Wege-Mapping aus den vorhandenen Card-Feldern.

    * Themenseite (``topic_pages`` nicht-leer ODER ``topic_page_url`` gesetzt
      ODER ``node_type`` bereits ``"topic_page"``) → ``"topic_page"``
    * ``node_type == "collection"`` → ``"collection"``
    * Sonst → ``"content"``

    Wichtig: Eine Themenseite OHNE Varianten hat eine LEERE ``topic_pages``-
    Liste — sie wird trotzdem als Themenseite erkannt, weil sie ein
    ``topic_page_url`` bzw. den vom Parser gesetzten ``node_type`` trägt.
    Sonst landete eine variantenlose Themenseite fälschlich als "content"
    beim render-Permalink (statt beim topic-pages-Renderer). ``topic_page_url``
    setzt nur der MCP für echte Themenseiten (Sammlung mit page_config_ref).
    """
    if (
        (isinstance(card.get("topic_pages"), list) and card.get("topic_pages"))
        or str(card.get("topic_page_url") or "").strip()
        or card.get("node_type") == "topic_page"
    ):
        return "topic_page"
    if card.get("node_type") == "collection":
        return "collection"
    return "content"


def _rewrite_card_urls(card: dict[str, Any], target_repo: str) -> None:
    """In-place: alle URL-Felder einer Card durch den bidirektionalen
    Host-Rewrite schicken.

    Die Felder sind sowohl die externen Links (``url``, ``content_url``,
    ``download_url``, ``preview_url``) als auch der in-repo Permalink
    ``wlo_url``. Topic-Page-URLs (``topic_page_url``, sowie pro Variante in
    ``topic_pages``) zeigen meist auf wirlernenonline.de — sie würden vom
    Rewrite ohnehin nicht angefasst (Host nicht in ``known_repo_hosts``).
    """
    for f in ("url", "content_url", "preview_url", "download_url", "wlo_url"):
        v = card.get(f)
        if v:
            card[f] = rewrite_repo_host_v2(v, target_repo)

    # Variante-URLs in topic_pages: rewrite falls jemand sie auf einen
    # Repo-Host geknüpft hat (unüblich, aber defensiv).
    tps = card.get("topic_pages")
    if isinstance(tps, list):
        for tp in tps:
            if isinstance(tp, dict) and tp.get("url"):
                tp["url"] = rewrite_repo_host_v2(tp["url"], target_repo)


def normalize_cards(
    cards: list[dict[str, Any]],
    *,
    target_repo_base: str | None = None,
    intent_kind: IntentKind = "general",
) -> list[dict[str, Any]]:
    """Normalisierungs-Phase: bringt jede Card durch eine deterministische
    Bereinigung.

    Schritte (Reihenfolge wichtig):
      1. Host-Rewrite (bidirektional, über ``known_repo_hosts``).
      2. ``node_type``-Normalisierung auf drei kanonische Werte
         (``topic_page`` / ``collection`` / ``content``).
      3. Dedup per ``node_id`` (erstes Vorkommen gewinnt).
      4. Sortierung nach Standard-Priorität (nur für ``"general"``-Intent;
         bei ``"type-focus"`` / ``"collection-contents"`` bleibt die
         MCP-Reihenfolge erhalten).

    Args:
        cards: Roh-Cards aus :func:`fetch_card_pool` (oder einer anderen
            Quelle, solange das Card-Dict-Schema passt).
        target_repo_base: Override für den Repo-Base-URL. Default:
            ``get_repo_base_url()``.
        intent_kind: Steuert nur die Sortierung in Schritt 4.

    Returns:
        Neue Card-Liste (in-place mutiert die Dicts, aber NICHT die
        Original-Liste — vorhersehbarer für Caller).
    """
    if not cards:
        return []

    target_repo = (target_repo_base or get_repo_base_url()).rstrip("/")

    # Schritt 1 + 2: Rewrite + node_type-Inferenz. In-place auf den Dicts,
    # weil die Eingabe-Cards eh frisch geparsed sind und nicht weiterleben.
    for c in cards:
        if not isinstance(c, dict):
            continue
        _rewrite_card_urls(c, target_repo)
        c["node_type"] = _infer_node_type(c)
        # Schritt 2b: wlo_url-Repair. Falls die Card als Sammlung erkannt
        # wurde (entweder vom Parser oder via Post-Set in den callers —
        # ``collect_cards`` und ``_build_cards`` befördern eine Karte mit
        # Themenseiten-Varianten NACH dem Parse zur Sammlung), zeigt
        # ``wlo_url`` ggf. noch auf den falschen
        # ``/components/render/<id>``-Endpoint (ccm:io-Permalink). Wir
        # rewriten ihn hier auf ``/components/collections?id=<id>``, sodass
        # auch direkter Aufruf von ``card.wlo_url`` im Frontend einen
        # validen Sammlungs-Link liefert.
        # Beobachtet 2026-05-21: Sammlung wurde als
        # ``…/render/39f845f1-…`` ausgespielt — falsch.
        nid = str(c.get("node_id") or "").strip()
        # Topic-pages SIND Sammlungen (ccm:map mit topic_page-Variants).
        # Ihre wlo_url muss ebenso auf den collections-Browse-Endpoint
        # zeigen — der render-Endpoint wäre für ccm:io.
        if nid and c["node_type"] in ("collection", "topic_page"):
            cur_wlo = str(c.get("wlo_url") or "").strip()
            # Nur Repo-Render-URLs umbiegen — externe URLs (z.B. fremdes
            # Repo, Themenseiten-Provider) bleiben unangetastet.
            if cur_wlo and "/edu-sharing/components/render/" in cur_wlo:
                c["wlo_url"] = _repo_collection_browse_url(nid, target_repo)
        elif nid and c["node_type"] == "content":
            # Defensiv: wenn ein als "content" gemerkter Knoten fälschlich
            # eine Sammlungs-Browse-URL trägt (z.B. Post-Fix lief in die
            # falsche Richtung), zurück auf Render. Sehr selten, aber
            # Symmetrie macht den Pfad vorhersagbar.
            cur_wlo = str(c.get("wlo_url") or "").strip()
            if cur_wlo and "/edu-sharing/components/collections?id=" in cur_wlo:
                c["wlo_url"] = _repo_render_url(nid, target_repo)

    # Schritt 3: Dedup per node_id. Cards ohne node_id (defensiv) bleiben
    # alle erhalten — ohne ID können wir nicht entscheiden, ob's Duplikate
    # sind.
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in cards:
        if not isinstance(c, dict):
            continue
        nid = str(c.get("node_id") or "").strip()
        if nid:
            if nid in seen:
                continue
            seen.add(nid)
        deduped.append(c)

    # Schritt 4: Sortierung. Stabil (Python sort), damit innerhalb einer
    # node_type-Gruppe die MCP-Trefferreihenfolge erhalten bleibt.
    if intent_kind == "general":
        deduped.sort(
            key=lambda c: _NODE_TYPE_PRIORITY.get(c.get("node_type", "content"), 99)
        )

    logger.info(
        "normalize_cards: in=%d out=%d intent=%s repo=%s",
        len(cards), len(deduped), intent_kind, target_repo,
    )
    return deduped
