"""MCP-Response-Parser: JSON/Text-Envelopes -> Boerdi-Card-Dicts.

1:1-Port aus ALT ``app/services/mcp_parsers.py`` — zustandslose reine Funktionen,
kein geteilter Client-/Cache-Zustand, nur ``config_loader`` für Repo-URLs
(``get_repo_base_url``/``rewrite_repo_host`` sind settings-getrieben → kein PG).
Der Leaf-Knoten des ``services/mcp``-Pakets für die Karten-Erzeugung; die Tool-
Loop (5-3) und der Reranker (5-5) konsumieren diese Parser direkt (kein Facade-
Re-Export wie in ALT — NEU-Baum importiert Leaves direkt, spec §4).

Einzige Abweichung ggü. ALT: der Import-Root (``app.`` → ``boerdi.``) und eine
umbrochene ``for``-Tupel-Zeile (E501, verhaltens-/AST-neutral).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from boerdi.services.config_loader import get_repo_base_url, rewrite_repo_host

logger = logging.getLogger(__name__)


def parse_total_count(mcp_text: str) -> int:
    """Extract total result count from MCP response text.

    Looks for patterns like:
    - "Gesamt: 42"
    - "Total: 42"
    - "42 Ergebnisse"
    - "Found 42 results"
    """
    import re
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


# UUID-Form (für Placeholder-Titel-Erkennung der Themenseiten).
_TP_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def _topic_page_display_title(
    raw_title: str, collection_id: str, educational_contexts: list | None
) -> str:
    """Menschenlesbarer Titel für eine Themenseiten-Card (Defense-in-Depth).

    Hintergrund: Der MCP-Server lieferte im ``title``-Feld früher teils einen
    technischen Platzhalter (``PAGE_VARIANT_<uuid>`` = ``cm:name`` eines
    Page-Variant-Knotens) statt des lesbaren Titels — beobachtet im Widget
    („PAGE_VARIANT_037c4c53-…").

    Der eigentliche Fix sitzt jetzt SERVERSEITIG: der WLO-MCP bevorzugt
    ``cm:title`` (z.B. „Seiten-Variante 1") vor ``cm:name`` (server.ts
    ``pickThemePageTitle`` / formatter ``formatNode``). Dieser Client-Guard
    bleibt als Sicherheitsnetz erhalten und greift nur noch, wenn doch ein
    Platzhalter ankommt — etwa solange die Server-Korrektur auf der
    Staging-Vercel-Instanz noch nicht deployt ist, bei gecachten Alt-
    Antworten, oder bei einem (noch) nicht gepatchten MCP-Server in der
    Registry. Ein sauberer Titel bleibt immer unverändert; nur ein echter
    Platzhalter wird auf ein generisches, lesbares Label gemappt — bevorzugt
    mit Bildungsstufe, sonst schlicht „Themenseite".
    """
    t = (raw_title or "").strip()
    low = t.lower()
    is_placeholder = (
        not t
        or low.startswith("page_variant")
        or low.startswith("variant_")
        or t == (collection_id or "")
        or bool(_TP_UUID_RE.match(t))
    )
    if not is_placeholder:
        return t
    ctxs = [c for c in (educational_contexts or []) if isinstance(c, str) and c.strip()]
    if ctxs:
        return f"Themenseite ({ctxs[0]})"
    return "Themenseite"


def parse_wlo_topic_page_cards(mcp_text: str) -> list[dict]:
    """Parse `search_wlo_topic_pages` v2 JSON output into Boerdi cards.

    The MCP server (v2) merges variants by collection server-side and
    delivers each card pre-labelled. We just need to map field names to
    Boerdi's internal card schema.

    Server output shape::

        {
          "total": N,
          "results": [
            {
              "title": "Mathematik",
              "collectionId": "<uuid>",
              "topicPageUrl": "https://...",
              "educationalContexts": ["Sek I", ...],
              "variants": [
                {"variantId": "...", "targetGroup": "teacher",
                 "targetGroupLabel": "Lehrkräfte", "topicPageUrl": "..."},
                ...
              ]
            }
          ]
        }

    The legacy Markdown parser (with `_pending_variant`-state and
    target-group label inference) was removed in v2. v1 servers — which
    only emit Markdown — are no longer supported.
    """
    if not mcp_text:
        return []
    try:
        obj = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        logger.warning(
            "parse_wlo_topic_page_cards: not a JSON envelope (first 80 chars: %r)",
            mcp_text[:80],
        )
        return []
    if not isinstance(obj, dict) or not isinstance(obj.get("results"), list):
        return []

    cards: list[dict] = []
    for r in obj["results"]:
        if not isinstance(r, dict):
            continue
        cid = r.get("collectionId") or ""
        if not cid:
            continue
        topic_pages: list[dict] = []
        # Magic strings the WLO-MCP returns when no real value is set —
        # treat as empty so the frontend's variantLabel disambiguator
        # (target_group → URL params → variant_id → "Variante N") kicks
        # in and the dropdown shows distinguishable entries instead of
        # all variants showing the same generic placeholder.
        UNINFORMATIVE = {
            "", "nicht gesetzt", "nicht gesezt", "unbekannt",
            "topic page", "topic pages", "themenseite", "themenseiten",
            "-", "—",
        }

        # B023 safe: UNINFORMATIVE is a loop-invariant constant (identical every
        # iteration) and _clean is called only within its defining iteration —
        # the late-binding footgun cannot fire (ALT-Parität, AST bleibt identisch).
        def _clean(val: str | None) -> str:
            s = (val or "").strip()
            return "" if s.lower() in UNINFORMATIVE else s  # noqa: B023 — see note

        for v in r.get("variants") or []:
            if not isinstance(v, dict):
                continue
            topic_pages.append({
                "variant_id":   _clean(v.get("variantId")),
                "target_group": _clean(v.get("targetGroup")),
                "label":        _clean(v.get("targetGroupLabel")) or "Themenseite",
                "url":          v.get("topicPageUrl") or r.get("topicPageUrl") or "",
            })

        # ── Dedup: collapse functionally-identical variants ─────────
        # Real-world WLO data often has multiple variants with the SAME
        # url + target_group + label — only the variantId UUID differs.
        # Klicking any of them opens the same page → showing them all in
        # the dropdown is misleading. Keep only one entry per unique
        # (url, target_group, label) tuple. The variant_id of the FIRST
        # entry wins (preserves the canonical-ID semantics).
        if len(topic_pages) > 1:
            _seen: dict[tuple, dict] = {}
            for tp in topic_pages:
                _key = (
                    tp.get("url", ""),
                    tp.get("target_group", "").lower(),
                    tp.get("label", "").lower(),
                )
                if _key not in _seen:
                    _seen[_key] = tp
            _before = len(topic_pages)
            topic_pages = list(_seen.values())
            if len(topic_pages) < _before:
                logger.info(
                    "topic_page variants collapsed: %d → %d für '%s' "
                    "(funktional identisch — gleiche URL/Target/Label)",
                    _before, len(topic_pages), r.get("title", "?"),
                )
        # Themenseiten sind technisch Sammlungen (ccm:map mit
        # page_config_ref), sollen aber als kuratierte Themenseite geöffnet
        # werden — über ``/components/topic-pages?collectionId=<id>``, NICHT
        # den generischen Sammlungs-Browse-Link und NICHT den render-Permalink
        # (der ist für ccm:io). Deshalb: node_type=topic_page und alle
        # URL-Felder auf den Themenseiten-Renderer (Fallback aus der cid, falls
        # der MCP keine ``topicPageUrl`` mitliefert).
        tp_render_url = (
            f"{get_repo_base_url()}/edu-sharing/components/topic-pages?collectionId={cid}"
        )
        cards.append({
            "node_id":              cid,
            "title":                _topic_page_display_title(
                r.get("title"), cid, r.get("educationalContexts"),
            ),
            "node_type":            "topic_page",
            "topic_pages":          topic_pages,
            "educational_contexts": r.get("educationalContexts") or [],
            "wlo_url":              r.get("topicPageUrl") or tp_render_url,
            "topic_page_url":       r.get("topicPageUrl") or tp_render_url,
        })
    return _normalize_card_repo_hosts(cards)


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
    # Heuristic: v2 envelope always has a `total` int and at least one
    # entry shaped like a FormattedNode (with `nodeId`).
    if not (
        ("total" in data or "count" in data)
        and (
            len(results) == 0
            or (isinstance(results[0], dict) and "nodeId" in results[0])
        )
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
    for pot, key in (
        ("content", "content"),
        ("collections", "collections"),
        ("topic_pages", "topicPages"),
    ):
        sub = obj.get(key)
        if isinstance(sub, dict):
            out[pot] = _cards_from_json_envelope(sub) or []
    return out


def parse_topic_page_swimlanes(mcp_text: str) -> dict[str, Any]:
    """Parst ``get_topic_page_content`` (outputFormat=json) in eine
    Swimlane-Struktur fuer die Anzeige.

    Envelope (json):

    .. code-block:: json

        {"variantId": "...", "collectionId": "...", "variantTitle": "...",
         "topicPageUrl": "https://…", "swimlaneCount": N,
         "swimlanes": [{"heading": "...", "type": "container",
                        "items": [FormattedNode, ...], "hasMore": true}]}

    Rueckgabe::

        {"variant_title": str, "topic_page_url": str,
         "swimlanes": [{"heading": str, "type": str, "has_more": bool,
                        "cards": [<Boerdi-Karte>, ...]}]}

    Die Karten je Schwimmlinie sind im selben Schema wie
    :func:`parse_wlo_cards` (ueber :func:`_cards_from_json_envelope`).
    """
    out: dict[str, Any] = {"variant_title": "", "topic_page_url": "", "swimlanes": []}
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
        logger.warning("parse_topic_page_swimlanes: kein JSON-Envelope (%r)", mcp_text[:80])
        return out
    out["variant_title"] = obj.get("variantTitle") or ""
    out["topic_page_url"] = obj.get("topicPageUrl") or ""
    for sl in obj.get("swimlanes") or []:
        if not isinstance(sl, dict):
            continue
        items = sl.get("items") or []
        cards = _cards_from_json_envelope(
            {"total": len(items), "count": len(items), "results": items}
        ) or []
        out["swimlanes"].append({
            "heading": sl.get("heading") or "",
            "type": sl.get("type") or "",
            "has_more": bool(sl.get("hasMore")),
            "cards": cards,
        })
    return out
