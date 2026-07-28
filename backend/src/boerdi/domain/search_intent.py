"""Search-query intent heuristic (verbatim port of ALT
``chat_prefetch._looks_like_search_query``): does a user message look like a concrete
search — substantial content, not an obvious clarification/meta question? Stateless
string logic, no I/O, no app deps → ``domain/`` (same home as the ``content_types`` /
``lp_intent`` / ``canvas/intent`` message-intent heuristics).

Consumed by the response postprocess orchestrator and the async fallback-search sibling
``_fallback_inline_search`` (``services/prefetch``, ported separately).

**NEU-Portierung:** the function is copied byte-for-byte from ALT (only this docstring
differs) — the function AST is identical.
"""

from __future__ import annotations


def _looks_like_search_query(message: str) -> bool:
    """Heuristik: wirkt der User-Input wie eine konkrete Suchanfrage?

    Greift wenn die Nachricht substantiellen Inhalt hat (>= 5 Zeichen Text
    nach Whitespace) und nicht offensichtlich eine Klärungs- oder
    Meta-Frage ist (z.B. ``"was kannst du?"`` triggert nicht).
    """
    msg = (message or "").strip()
    if len(msg) < 5:
        return False
    low = msg.lower()
    # Generic meta/clarification phrases that aren't real searches.
    # Diese matchen unabhängig von der Länge: "Was ist WirLernenOnline?"
    # (24 chars) und "Was ist WLO?" (12 chars) sind beide reine
    # Definition-Fragen, kein Suchanker. Welle C Sprint 6 Hotfix:
    # vorher hatte die Liste nur kurze Phrasen + 25-Zeichen-Limit, was
    # "Was ist WirLernenOnline?" als Suche durchwischen liess —
    # Safety-Net Fallback-Search hat dann eine MCP-Suche darüber
    # ausgelöst und Cards in eine RAG-Antwort geschmuggelt.
    no_search_phrases_exact = (
        "was ist wlo",
        "was ist wirlernenonline",
        "was ist wir lernen online",
        "wer steckt hinter wlo",
        "wer steckt hinter wirlernenonline",
        "was ist oer",
        "was ist edu-sharing",
        "was ist eine themenseite",
        "was ist eine sammlung",
        "was bedeutet oer",
    )
    if any(p in low for p in no_search_phrases_exact):
        return False
    # Kurze Meta-/Greeting-Phrasen (mit Längenlimit, sonst false-positive
    # bei Sätzen wie "Hi, kannst du mir helfen mit Mathe?")
    no_search_phrases_short = (
        "was kannst du", "wie kann ich", "hilfe", "help",
        "hallo", "hi ", "moin", "guten tag",
    )
    if any(p in low for p in no_search_phrases_short) and len(low) < 25:
        return False
    return True
