"""Is this page already in WLO? — the duplicate check before an offer to add it.

When the bot sits on a page outside WLO it may offer to turn it into a WLO
record. M20 makes the duplicate check a precondition of that offer ("Vor JEDER
Neuanlage … mit Titel und Adresse suchen"), and the editorial reason is plain: a
second record for the same address is the expensive mistake, because nothing
downstream merges them again.

Measured against the live staging MCP (2026-08-11) before this was written:
``search_wlo_content`` queried with a full URL that IS in the holdings answers
with exactly that one node; a URL that is not answers with an empty result and
no near-misses. That is why the address is the strong signal and the title only
the fallback — and why the address is asked first.

A FALSE hit is the direction that hurts: the bot would claim "we already have
this" and swallow the offer. So a candidate only counts when it really carries
that address (resp. exactly that title). The search ranking is a way to find
candidates, never the proof.

Own module rather than a branch inside ``graph/nodes/context_greeting``: this is
a second responsibility (asking the holdings a question) next to that node's
first one (composing the message), and it is the piece a later, richer
duplicate check would grow in.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.mcp.parsers import parse_wlo_cards

logger = logging.getLogger(__name__)

# Enough to survive a couple of better-ranked near-misses ahead of the exact
# node, small enough to stay one cheap call. The measured exact-URL query
# returned a single result.
_MAX_RESULTS = 5


def _same_address(a: str, b: str) -> bool:
    """True when two URLs address the same page.

    Scheme and host are compared case-insensitively and a trailing slash is
    ignored; the path is compared as-is, because it is genuinely
    case-sensitive (``/classic/ahzTeJKG``) and folding it could merge two
    different pages into one false duplicate.
    """
    def key(url: str) -> tuple[str, str, str, str]:
        try:
            parts = urlsplit(url.strip())
        except ValueError:
            return ("", "", "", "")
        host = parts.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return (parts.scheme.lower(), host, parts.path.rstrip("/"), parts.query)

    ka, kb = key(a), key(b)
    return ka == kb and bool(ka[1])


async def _search(query: str) -> list[dict]:
    """One content search, reduced to cards. Empty on any failure — the caller
    treats "found nothing" and "could not ask" alike, and the honest difference
    is logged rather than raised: the greeting must not die on a search."""
    try:
        raw = await call_mcp_tool(
            "search_wlo_content", {"query": query, "maxResults": _MAX_RESULTS},
        )
    except Exception as err:
        logger.warning("duplicate check: search failed: %s", err)
        return []
    if not raw or raw.startswith("MCP error"):
        logger.info("duplicate check: no usable answer for %r", query[:80])
        return []
    return parse_wlo_cards(raw)


async def find_existing_by_url(url: str, title: str) -> dict | None:
    """First WLO record for this address or this exact title, else ``None``.

    Returns ``{"node_id": str, "title": str, "matched_on": "url" | "title"}``.
    Never raises: a duplicate check that fails must cost the offer its
    certainty, not the whole turn.
    """
    url = (url or "").strip()
    title = (title or "").strip()
    if not url:
        return None

    for card in await _search(url):
        if _same_address(card.get("url") or "", url):
            return {
                "node_id": card.get("node_id") or "",
                "title": card.get("title") or "",
                "matched_on": "url",
            }

    if not title:
        return None

    needle = title.casefold()
    for card in await _search(title):
        if (card.get("title") or "").strip().casefold() == needle:
            return {
                "node_id": card.get("node_id") or "",
                "title": card.get("title") or "",
                "matched_on": "title",
            }
    return None
