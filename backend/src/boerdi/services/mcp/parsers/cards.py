"""FormattedNode-Envelope → Boerdi-Karten.

Teil der Fassade ``boerdi.services.mcp.parsers``. Hier liegt das Kartenschema
selbst: die Envelope-Erkennung, das Feld-Mapping und die zwei Werkzeuge, die
reine Karten-Antworten liefern. ``parse_total_count`` gehört dazu, weil es
dasselbe Such-Envelope liest — nur das Zählfeld statt der Treffer.

``_cards_from_json_envelope`` und ``_normalize_card_repo_hosts`` werden auch von
``topic_pages`` gebraucht; sie sind hier zuhause, weil sie das Kartenschema
definieren. Wer sie in einem Test ersetzen will, muss sie **hier** ersetzen —
über die Fassade zu patchen wirkt auf modulinterne Aufrufe nicht.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from boerdi.services.config_loader import get_repo_base_url, rewrite_repo_host
from boerdi.services.mcp.parsers.json_scan import _first_json_object

logger = logging.getLogger(__name__)


def parse_total_count(mcp_text: str) -> int:
    """Extract the total result count from an MCP response.

    Two shapes, in this order:

    1. **v2 JSON envelope** — ``{"total": N, "count": M, "results": [...]}``.
       The count is a structured field; read it directly.
    2. **Markdown/prose** (v1 servers, ``outputFormat="markdown"``) — fall back
       to the historical patterns "Gesamt: 42", "Total: 42", "42 Ergebnisse",
       "Found 42 results".

    Deviation vs ALT (W2-1, 2026-07-30): ALT only had the prose branch. Its sole
    caller asks ``get_collection_contents``, which sits in ``_JSON_CAPABLE_TOOLS``
    and therefore *always* answers with the JSON envelope — where none of the
    patterns match (``{"total": 42`` has a quote between key and colon). ALT thus
    silently returned 0 for every real call, and worse: on an envelope whose card
    descriptions contain prose digits the regex scraped *those* instead. Reading
    the envelope first fixes both. A JSON object without ``total`` returns 0
    rather than falling through — the envelope is authoritative, so prose digits
    inside it are card text, never the count.
    """
    import re
    if not mcp_text:
        return 0
    try:
        envelope = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        envelope = None
    if isinstance(envelope, dict):
        total = envelope.get("total")
        # bool is an int subclass — a stray ``"total": true`` is not a count.
        return total if isinstance(total, int) and not isinstance(total, bool) else 0
    # "Gesamt: 17" or "Total: 17"
    m = re.search(r"(?:Gesamt|Total|Treffer|Ergebnisse gesamt)[:\s]+(\d+)", mcp_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # "17 Ergebnisse" or "17 results"
    m = re.search(r"(\d+)\s+(?:Ergebnisse|results|Treffer|Eintr)", mcp_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # "Found 17"
    m = re.search(r"(?:Found|Gefunden)[:\s]+(\d+)", mcp_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


def _normalize_card_repo_hosts(cards: list[dict]) -> list[dict]:
    """URL-Felder aller Cards durch ``rewrite_repo_host`` schicken.

    Notwendig, weil der MCP-Server ``previewUrl``/``contentUrl``/``url``-
    Felder serverseitig auf den Production-Repo-Host bakt — auch wenn der
    MCP-Server selbst Staging ist. Ohne Rewrite würden Staging-Node-IDs
    auf Production-Hostnamen landen und 404 liefern.
    """
    _fields = ("url", "content_url", "preview_url", "download_url")
    for c in cards:
        if not isinstance(c, dict):
            continue
        for f in _fields:
            v = c.get(f)
            if v:
                c[f] = rewrite_repo_host(v)
    return cards


def _cards_from_json_envelope(data: dict) -> list[dict] | None:
    """Map an MCP v2 JSON envelope ({total, count, results: FormattedNode[]})
    to the internal Boerdi card schema.

    Returns the parsed cards on a v2 envelope, ``None`` if the input doesn't
    look like one (so the caller can fall back to the regex parser).

    The MCP v2 ``FormattedNode`` shape (from ``formatNodes`` in the MCP
    server) is the canonical input — every field is already label-resolved
    server-side (disciplines, educationalContexts, license, …).
    """
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    if not isinstance(results, list):
        return None
    # Heuristic: an entry shaped like a FormattedNode (with `nodeId`) is what
    # makes this a card envelope. A `total`/`count` header is typical but NOT
    # required — W9b (2026-08-01) measured `get_related_content`, which answers
    # with `{seedNodeId, seedTitle, disciplines, educationalContexts, results}`
    # and no counters at all. Demanding one threw away three perfectly good
    # cards. An empty `results` list still needs the header, otherwise any
    # unrelated `{"results": []}` would read as "zero cards" instead of
    # "not an envelope".
    if not (
        (isinstance(results[0], dict) and "nodeId" in results[0])
        if results
        else ("total" in data or "count" in data)
    ):
        return None

    cards: list[dict] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        nid = r.get("nodeId") or ""
        if not nid:
            continue
        node_type = r.get("nodeType") or "content"
        # wlo_url muss zum node_type passen: Sammlungen (ccm:map) brauchen
        # den ``components/collections?id=<uuid>``-Browse-Endpoint, nicht
        # ``components/render/<uuid>`` (das ist ccm:io-Permalink und liefert
        # für eine Sammlung eine falsche/leere Detail-View). Für content-
        # Nodes bleibt render/<uuid> korrekt. Hinweis: Wenn die Eingabe
        # ``nodeType`` nicht setzt (default "content"), aber später per
        # ``c.setdefault("node_type", "collection")`` in den callers
        # (chat.py / llm_service.py für search_wlo_collections) überschrieben
        # wird, holt ``normalize_cards`` (card_pipeline) den wlo_url-Repair
        # nach — siehe dort.
        _repo = get_repo_base_url()
        if node_type == "collection":
            _wlo_url = f"{_repo}/edu-sharing/components/collections?id={nid}"
        else:
            _wlo_url = f"{_repo}/edu-sharing/components/render/{nid}"
        cards.append({
            "node_id": nid,
            "title": r.get("title") or "",
            "description": r.get("description") or "",
            "keywords": r.get("keywords") or [],
            "disciplines": r.get("disciplines") or [],
            "educational_contexts": r.get("educationalContexts") or [],
            "user_roles": r.get("userRoles") or [],
            "learning_resource_types": r.get("learningResourceTypes") or [],
            # Primary "open"-link (external preferred, in-repo viewer as fallback).
            "url": r.get("url") or "",
            # Direct binary download (no auth) — only set on file nodes.
            # Frontend can offer a download button without an extra round-trip.
            "download_url": r.get("downloadUrl") or "",
            # In-repo viewer URL (PDF/video preview component).
            "content_url": r.get("contentUrl") or "",
            "preview_url": r.get("previewUrl") or "",
            # Distinguish generic mediatype-icon from real generated thumbnail —
            # frontend can decide whether to feature the preview prominently.
            "preview_is_icon": bool(r.get("previewIsIcon")),
            "mime_type": r.get("mimeType") or "",
            "file_size": r.get("fileSize") or 0,
            "license": r.get("license") or "",
            "publisher": r.get("publisher") or "",
            "node_type": node_type,
            "wlo_url": _wlo_url,
            "topic_page_url": r.get("topicPageUrl") or "",
        })
    return _normalize_card_repo_hosts(cards)


def parse_wlo_cards(mcp_text: str) -> list[dict]:
    """Parse an MCP v2 JSON envelope into Boerdi card objects.

    The MCP server is called with ``outputFormat="json"`` (set centrally in
    :func:`call_mcp_tool` for all v2-aware tools) and returns:

    .. code-block:: json

        {"total": N, "count": M, "results": [FormattedNode, ...]}

    All vocab fields (`disciplines`, `educationalContexts`, `userRoles`,
    `learningResourceTypes`, `license`) arrive **label-resolved** —
    Hochschulfächersystematik via server-side `_DISPLAYNAME`, school
    vocab via the local map, license via the license vocab. No client-
    side URI-→-label resolution remains.

    The legacy Markdown / key-value parser was removed in v2 (see git
    history if you need it back). v1 servers — which only emit Markdown —
    are no longer supported.
    """
    if not mcp_text:
        return []
    try:
        obj = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        logger.warning("parse_wlo_cards: not a JSON envelope (first 80 chars: %r)", mcp_text[:80])
        return []
    cards = _cards_from_json_envelope(obj)
    if cards is None:
        logger.warning("parse_wlo_cards: JSON did not match v2 envelope shape")
        return []
    return cards


def parse_search_all_cards(mcp_text: str) -> dict[str, list[dict]]:
    """Parst das ``search_wlo_all``-Envelope in DREI getrennte Karten-Töpfe.

    Envelope (outputFormat=json):

    .. code-block:: json

        {"query": "...",
         "content":     {"total": N, "count": M, "results": [FormattedNode, ...]},
         "collections": {...}, "topicPages": {...}}

    Rückgabe: ``{"content": [...], "collections": [...], "topic_pages": [...]}``
    mit Boerdi-Karten (gleiche Form wie :func:`parse_wlo_cards`). Sammlungen
    und Themenseiten tragen ``node_type='collection'`` (vom MCP gesetzt);
    Themenseiten zusätzlich ``topic_page_url``. So kann der Aufrufer die Töpfe
    direkt in getrennte Anzeige-Boxen einsortieren.
    """
    out: dict[str, list[dict]] = {"content": [], "collections": [], "topic_pages": []}
    if not mcp_text:
        return out
    obj: Any = None
    try:
        obj = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        frag = _first_json_object(mcp_text)
        if frag:
            try:
                obj = json.loads(frag)
            except (ValueError, json.JSONDecodeError):
                obj = None
    if not isinstance(obj, dict):
        logger.warning("parse_search_all_cards: kein JSON-Envelope (%r)", mcp_text[:80])
        return out
    # Alle drei Töpfe durch denselben Envelope-Leser. Gemessen 2026-08-01 gegen
    # den Server: der ``topicPages``-Topf von ``search_wlo_all`` ist eine
    # gewöhnliche FormattedNode-Liste (``nodeId`` + ``topicPageUrl``) — NICHT
    # die ``collectionId``+``variants``-Form, die ``search_wlo_topic_pages``
    # liefert. Zwei Werkzeuge, zwei Antwortformen; der dedizierte
    # Themenseiten-Parser gehört deshalb NICHT hierher (er würde jeden Eintrag
    # verwerfen, weil ``collectionId`` fehlt).
    for pot, key in (
        ("content", "content"),
        ("collections", "collections"),
        ("topic_pages", "topicPages"),
    ):
        sub = obj.get(key)
        if isinstance(sub, dict):
            out[pot] = _cards_from_json_envelope(sub) or []
    return out
