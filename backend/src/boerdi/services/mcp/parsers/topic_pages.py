"""Themenseiten-Antworten des MCP → Boerdi-Karten und Schwimmlinien.

Teil der Fassade ``boerdi.services.mcp.parsers``. Eigenes Modul, weil
Themenseiten eine **andere Antwortform** haben als gewöhnliche Karten:
``search_wlo_topic_pages`` liefert ``collectionId`` + ``variants``,
``get_topic_page_content`` liefert Schwimmlinien. Nur die Karten *innerhalb*
einer Schwimmlinie sind gewöhnliche FormattedNodes — dafür kommt der
Envelope-Leser aus :mod:`~boerdi.services.mcp.parsers.cards`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from boerdi.services.config_loader import get_repo_base_url
from boerdi.services.mcp.parsers.cards import (
    _cards_from_json_envelope,
    _normalize_card_repo_hosts,
)
from boerdi.services.mcp.parsers.json_scan import load_envelope
from boerdi.services.mcp.parsers.skill_registry import skill_count_of

logger = logging.getLogger(__name__)


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
    Platzhalter ankommt — bei gecachten Alt-Antworten oder bei einem (noch)
    nicht gepatchten MCP-Server in der Registry. (Die Vercel-Instanz, auf die
    sich diese Zeile ursprünglich bezog, ist seit W7b abgelöst.)
    Ein sauberer Titel bleibt immer unverändert; nur ein echter
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
    obj = load_envelope(mcp_text)
    if obj is None:
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
            # Gleiche Regel wie am Sammlungs-Parser. Gemessen 2026-08-14: der
            # MCP haengt ``skillRegistry`` an DIESES Werkzeug (noch) nicht an —
            # derselbe Knoten traegt sie ueber ``search_wlo_collections``, hier
            # fehlt sie. Also heute ehrlich 0. Kommt sie, traegt die
            # Themenseiten-Kachel den Hinweis ohne weitere Aenderung; und wo
            # beide Suchen im selben Zug liefen, erbt die Karte die Zahl
            # ohnehin ueber ``_build_cards``.
            "skill_count":          skill_count_of(r),
        })
    return _normalize_card_repo_hosts(cards)


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

        {"variant_title": str, "topic_page_url": str, "reason": str,
         "swimlanes": [{"heading": str, "type": str, "has_more": bool,
                        "cards": [<Boerdi-Karte>, ...]}]}

    Die Karten je Schwimmlinie sind im selben Schema wie
    :func:`~boerdi.services.mcp.parsers.cards.parse_wlo_cards` (ueber
    :func:`~boerdi.services.mcp.parsers.cards._cards_from_json_envelope`).

    ``reason`` (W2-3, 2026-07-30, nicht in ALT): der WLO-MCP begruendet den
    Leerfall seit 2026-07-27 selbst — ``no_match`` | ``node_not_found`` |
    ``no_page_config_ref`` | ``no_variant`` | ``empty_config`` — und laesst das
    Feld bei Erfolg weg. Leerstring heisst also "kein Grund gemeldet", nicht
    "Grund unbekannt".
    """
    out: dict[str, Any] = {
        "variant_title": "", "topic_page_url": "", "swimlanes": [], "reason": "",
    }
    if not mcp_text:
        return out
    obj: Any = load_envelope(mcp_text)
    if not isinstance(obj, dict):
        logger.warning("parse_topic_page_swimlanes: kein JSON-Envelope (%r)", mcp_text[:80])
        return out
    # W5-1: ``collectionTitle`` ist der lesbare Name der Themenseite;
    # ``variantTitle`` trägt den technischen Varianten-Namen und lautet bei allen
    # Fachportal-Seiten „Fachportalstartseite" (live gemessen 2026-07-30). Der
    # Server liefert beide, mit dem lesbaren zuerst gemeint — bis W5-1 lasen wir
    # den falschen; verdeckt hatte das nur der Kandidaten-Titel aus der Suche.
    out["variant_title"] = obj.get("collectionTitle") or obj.get("variantTitle") or ""
    out["topic_page_url"] = obj.get("topicPageUrl") or ""
    out["reason"] = obj.get("reason") or ""
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
