"""Pure "Lernpfad-Diversity" helpers (P4-4-Tail, port of ALT chat_cards.py's
used-id/diversity cluster): learning-path material dedup tracking across turns
(``_get_used_lp_ids`` / ``_add_used_lp_ids``), keeping only cards actually linked
in the generated LP text (``_filter_cards_used_in_text``) and the generic
used-set diversity filter with reset signal (``_filter_unused_cards``).

All framework-free (stdlib ``json`` + dict/text only) → ``domain/cards/``.
Verbatim 1:1 from ALT (byte-exact contiguous extraction, no import swaps). The
first three are consumed by the P4-5 LP-fast-path; ``_get_used_lp_ids`` and
``_filter_unused_cards`` are also used by the P4-5 direct-actions browse handler.
"""

from __future__ import annotations

import json


def _get_used_lp_ids(session_state: dict) -> set[str]:
    raw = session_state.get("entities", {}).get("_lp_used_node_ids", "")
    if not raw:
        return set()
    try:
        return set(json.loads(raw))
    except Exception:
        return set()


def _add_used_lp_ids(session_state: dict, new_ids: list[str]) -> None:
    used = _get_used_lp_ids(session_state)
    used.update(i for i in new_ids if i)
    # Keep last 100 to bound size
    session_state.setdefault("entities", {})["_lp_used_node_ids"] = json.dumps(list(used)[-100:])


def _filter_cards_used_in_text(cards_raw: list[dict], response_text: str) -> list[dict]:
    """Keep only cards whose URL, wlo_url, node_id OR title appears in the LP
    response. The LP prompt asks the LLM for `[Titel](URL)` links, so URL match
    is the primary signal. Title match is a narrow fallback for cases where the
    LLM rewrites/truncates the URL.

    De-duplicates by node_id AND url (the same resource can appear under
    multiple collections with distinct node_ids). Ordering (2026-06-10):
    by FIRST OCCURRENCE in the response text, not by pool order — die Box
    spiegelt so die Schritt-Reihenfolge des Lernpfads, und der spätere
    ``materialien_max_lernpfad``-Trim schneidet Zusatz-Links (z.B. aus
    einem Differenzierungs-Absatz) statt der Schritt-Materialien ab.

    Fallback: if *nothing* matches (e.g. LLM error or non-standard formatting),
    return the original list — it's safer to show too many cards than none.
    """
    if not cards_raw or not response_text:
        return cards_raw
    text_lower = response_text.lower()
    used: list[tuple[int, dict]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for c in cards_raw:
        nid = (c.get("node_id") or "").strip()
        url = (c.get("url") or "").strip()
        if nid and nid in seen_ids:
            continue
        if url and url in seen_urls:
            continue
        wlo = (c.get("wlo_url") or "").strip()
        matched = False
        match_pos = len(response_text)
        # 1. URL / wlo_url / node_id — exact substring match (primary)
        if url and url in response_text:
            matched = True
            match_pos = response_text.find(url)
        elif wlo and wlo in response_text:
            matched = True
            match_pos = response_text.find(wlo)
        elif nid and nid in response_text:
            matched = True
            match_pos = response_text.find(nid)
        else:
            # 2. Title fallback — only for multi-word titles (≥ 3 words after
            #    stripping common provider suffixes). A single-word match like
            #    "Photosynthese" is too generic: it matches the LP topic itself
            #    and produces false positives. The YouTube/provider suffix
            #    (" | Mathe by Daniel Jung", " – Serlo") gets trimmed first.
            title = (c.get("title") or "").strip()
            if title:
                primary = title
                for sep in [" | ", " – ", " - "]:
                    primary = primary.split(sep)[0]
                primary = primary.strip()
                words = [w for w in primary.split() if len(w) >= 3]
                if len(words) >= 3 and len(primary) >= 15 and primary.lower() in text_lower:
                    matched = True
                    match_pos = text_lower.find(primary.lower())
        if matched:
            used.append((match_pos, c))
            if nid:
                seen_ids.add(nid)
            if url:
                seen_urls.add(url)
    # Stabil nach Text-Position sortieren (Ties behalten Pool-Reihenfolge).
    used.sort(key=lambda t: t[0])
    return [c for _, c in used] if used else cards_raw


def _filter_unused_cards(cards_raw: list[dict], used: set[str]) -> tuple[list[dict], bool]:
    """Return (filtered_cards, was_reset). Resets when nothing new is left."""
    if not used:
        return cards_raw, False
    fresh = [c for c in cards_raw if c.get("node_id") and c["node_id"] not in used]
    if not fresh:
        return cards_raw, True  # nothing new — reuse all but signal reset
    return fresh, False
