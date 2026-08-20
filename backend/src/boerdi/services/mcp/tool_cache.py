"""Tool-Result-Cache für MCP-Aufrufe (LRU + TTL + Negativ-Cache + Stats).

1:1-Port aus ALT ``app/services/mcp_tool_cache.py``. Mutabler Modul-Zustand
(OrderedDict-LRU + Hit/Miss-Zähler) samt aller Mutatoren zusammen — die
``global``-Rebinds der Zähler bleiben so intra-modul. Per Eiserne Regel 3
ausdrücklich erlaubt: „MCP-TTL-Cache pro Prozess erlaubt, da nur Performance".
``call_mcp_tool`` (5-1c) importiert die Cache-Handles und mutiert sie in-place;
``_TOOL_META_CACHE`` wird ebenfalls dort befüllt (hier nur definiert + mit-
evictet, damit die B5-Eviction-Kopplung erhalten bleibt). Reiner stdlib-Port.
"""

from __future__ import annotations

import json
import logging
import time as _time
from collections import OrderedDict
from typing import Any

from boerdi.domain.write_confirm import CURATION_TOOLS
from boerdi.services.mcp.auth import caller_fingerprint

logger = logging.getLogger(__name__)


_TOOL_CACHE: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()
# Parallel-Cache für die ``_queryMeta``-Blöcke, die das MCP zusammen mit
# dem Tool-Result emittiert. Müssen separat gecached werden, weil sie
# beim Response-Parsing aus dem Text-Stream rausgezogen werden (siehe
# extraction-Loop unten) und der LIVE-Per-Request-Akkumulator
# (``_query_metas`` ContextVar) bei Cache-Hits sonst leer bliebe.
# Frontend-Search-CTA + URL-Filter-Synthese (chat.py) sind auf diese
# Metas angewiesen, sodass cached-Turns sonst keine URI-resolved
# Filter-Daten mehr hätten.
_TOOL_META_CACHE: dict[tuple[str, str], list[dict[str, Any]]] = {}
_TOOL_CACHE_MAX_ENTRIES = 1024  # was 256 — Multi-User-Sessions füllen die alte Größe schnell
_TOOL_CACHE_TTL_DEFAULT_SECONDS = 300  # 5 Min — fallback, wenn das Tool keine spezifische TTL hat
_TOOL_CACHE_TTL_NEGATIVE_SECONDS = 60  # Empty-Result-Hits werden nur kurz cached
_TOOL_CACHE_HITS = 0
_TOOL_CACHE_MISSES = 0
_TOOL_CACHE_NEG_HITS = 0  # Hits auf empty-result-Cache-Einträge

# A3.1 — Per-Tool TTL: stabile Tools (Vokabular, Top-Level-Fächer, Knoten-
# Details) ändern sich quasi nie und können viel länger gecached werden;
# dynamische Suchen kriegen den Default. Greift nur, wenn das Tool keinen
# Eintrag hat → fällt sauber auf den Default zurück.
_TOOL_CACHE_TTL_PER_TOOL: dict[str, int] = {
    # Vokabular: ändert sich nur bei MCP-Schema-Updates → 24h (O3).
    # Zusätzlich beim Backend-Start vorgewärmt (prewarm_vocabularies), damit
    # schon der erste Such-Turn keine Vokabular-Round-Trips braucht.
    "lookup_wlo_vocabulary": 86400,
    # Top-Level-Fächer: stabil über Wochen → 30 min
    "get_subject_portals": 1800,
    # Sammlungs-Hierarchie: selten geändert → 30 min
    "browse_collection_tree": 1800,
    # Per-Knoten-Metadaten: sehr stabil → 30 min
    "get_node_details": 1800,
    "get_nodes_details": 1800,
    # Sammlung-Inhalte: mittlere Stabilität (neue Materialien können kommen) → 10 min
    "get_collection_contents": 600,
    # Skills: redaktionell gepflegte Anleitungen — Änderungen sollen nach
    # spätestens 3 Minuten beim Bot ankommen (Nutzer-Entscheid 2026-08-20;
    # vorher fielen beide auf den 5-Minuten-Default).
    "get_skill": 180,
    "get_skill_registry": 180,
    # Suchen: dynamisch, neue Treffer möglich → Default 5 min
    "search_wlo_collections": 300,
    "search_wlo_content": 300,
    "search_wlo_topic_pages": 300,
}


def _ttl_for_tool(tool_name: str) -> int:
    return _TOOL_CACHE_TTL_PER_TOOL.get(tool_name, _TOOL_CACHE_TTL_DEFAULT_SECONDS)


def _is_empty_response(value: str) -> bool:
    """Heuristik: Tool-Response liefert keine verwertbaren Items.

    Wir cachen Empty-Responses kürzer (60s) — wiederholte Suchen nach
    selbstem Empty-Topic im selben Turn kosten so nur einen MCP-Roundtrip.
    Kriterium: JSON-Antwort hat ein leeres ``items``/``nodes``-Array,
    oder der ganze Body ist objektiv leer (Whitespace).
    """
    s = (value or "").strip()
    if not s:
        return True
    try:
        parsed = json.loads(s)
    except Exception:
        return False
    if isinstance(parsed, dict):
        for key in ("items", "nodes", "results", "content", "topic_pages"):
            v = parsed.get(key)
            if isinstance(v, list) and len(v) == 0:
                return True
    if isinstance(parsed, list) and len(parsed) == 0:
        return True
    return False


def _cache_key(tool_name: str, arguments: dict[str, Any]) -> tuple[str, str]:
    """Stable cache key: tool name + caller + sorted JSON-serialisation of args.

    **Der Aufrufer gehört in den Schlüssel** (S6, 2026-08-15). Der MCP-Server
    antwortet identitätsabhängig — ``anonymous`` sieht nur Öffentliches,
    ``user`` sieht, was diese Person sehen darf (Begründung und Messung in
    :func:`~boerdi.services.mcp.auth.caller_fingerprint`). Dieser Speicher ist
    prozessweit und überlebt Sitzungen; ohne das Kennzeichen bekäme die zweite
    Person die Treffer der ersten.

    Die Identität wird hier **geholt und nicht hereingereicht**: ein Aufrufer,
    der sie vergisst, öffnet das Loch wieder. Genau eine Produktions-Aufrufstelle
    gibt es (``client.call_mcp_tool``) — sie soll gar nicht daran denken müssen.

    Das Werkzeug bleibt ``key[0]``: ``_cache_get`` liest daraus die
    Per-Tool-TTL. Kennzeichen und Argumente stehen zusammen als **Liste** im
    zweiten Element, nicht ineinandergemischt — ein Argument namens ``_caller``
    könnte sonst die Trennung überschreiben.
    """
    caller = caller_fingerprint()
    try:
        canonical = json.dumps([caller, arguments], sort_keys=True, ensure_ascii=False)
    except Exception:
        canonical = str((caller, sorted(arguments.items())))
    return (tool_name, canonical)


def _cache_get(key: tuple[str, str]) -> str | None:
    """Returns cached value if present + fresh, else None. Touches LRU order.

    Per-Tool TTL: ``key[0]`` (= tool_name) entscheidet. Empty-Response-
    Einträge tragen einen kürzeren TTL — wir prüfen über den ``_neg_``-
    Marker im gespeicherten Wert (siehe ``_cache_set``).
    """
    global _TOOL_CACHE_HITS, _TOOL_CACHE_MISSES, _TOOL_CACHE_NEG_HITS
    entry = _TOOL_CACHE.get(key)
    if entry is None:
        _TOOL_CACHE_MISSES += 1
        return None
    ts, value = entry
    is_negative = value.startswith("__NEG__::")
    ttl = _TOOL_CACHE_TTL_NEGATIVE_SECONDS if is_negative else _ttl_for_tool(key[0])
    if _time.time() - ts > ttl:
        # expired — drop it
        _TOOL_CACHE.pop(key, None)
        _TOOL_CACHE_MISSES += 1
        return None
    # LRU: move to end (most recently used)
    _TOOL_CACHE.move_to_end(key)
    _TOOL_CACHE_HITS += 1
    if is_negative:
        _TOOL_CACHE_NEG_HITS += 1
        return value[len("__NEG__::"):]
    return value


def _cache_set(key: tuple[str, str], value: str) -> None:
    """Cache a tool response. Empty responses get a short-TTL marker prefix
    so the same empty-result query within ~1 min reuses the cached miss
    instead of round-tripping to MCP again.
    """
    if _is_empty_response(value):
        # Mark as negative cache entry; _cache_get strips the prefix.
        stored = "__NEG__::" + value
    else:
        stored = value
    _TOOL_CACHE[key] = (_time.time(), stored)
    _TOOL_CACHE.move_to_end(key)
    while len(_TOOL_CACHE) > _TOOL_CACHE_MAX_ENTRIES:
        # B5 (2026-06-10): Meta-Cache-Eintrag MIT evicten — vorher wuchs
        # _TOOL_META_CACHE unbegrenzt (jede einzigartige (tool,args)-Kombi
        # blieb prozesslebenslang im RAM).
        _old_key, _ = _TOOL_CACHE.popitem(last=False)  # drop oldest
        _TOOL_META_CACHE.pop(_old_key, None)


def get_tool_cache_stats() -> dict[str, Any]:
    """For Studio diagnostics: hit/miss/size of the tool-result cache."""
    total = _TOOL_CACHE_HITS + _TOOL_CACHE_MISSES
    return {
        "hits": _TOOL_CACHE_HITS,
        "misses": _TOOL_CACHE_MISSES,
        "negative_hits": _TOOL_CACHE_NEG_HITS,
        "size": len(_TOOL_CACHE),
        "max_entries": _TOOL_CACHE_MAX_ENTRIES,
        "hit_rate": round(_TOOL_CACHE_HITS / total, 3) if total else 0.0,
        "ttl_per_tool": dict(_TOOL_CACHE_TTL_PER_TOOL),
        "ttl_default_seconds": _TOOL_CACHE_TTL_DEFAULT_SECONDS,
        "ttl_negative_seconds": _TOOL_CACHE_TTL_NEGATIVE_SECONDS,
    }


def clear_tool_cache() -> int:
    """Wipe the cache + reset all stat counters (used between eval runs)."""
    global _TOOL_CACHE_HITS, _TOOL_CACHE_MISSES, _TOOL_CACHE_NEG_HITS
    n = len(_TOOL_CACHE)
    _TOOL_CACHE.clear()
    _TOOL_META_CACHE.clear()  # B5: Meta-Cache mit leeren (lief sonst voll)
    _TOOL_CACHE_HITS = 0
    _TOOL_CACHE_MISSES = 0
    _TOOL_CACHE_NEG_HITS = 0
    return n


# Tools deren Output transient ist und die wir NICHT cachen wollen
# (Health-Checks, Live-Daten, etc.). Default: alles cachen.
#
# S5 (2026-08-15): Die kuratierende Oberfläche gehört vollständig hierher, und
# das war der zweite Teil der Bestätigungs-Schleife. Drei getrennte Gründe:
#
# * **Eine Ausführung ist kein Lesevorgang.** Sie aus dem Zwischenspeicher zu
#   beantworten heisst, sie NICHT auszuführen — und trotzdem Vollzug zu melden.
# * **Der Schlüssel steht nicht im Cache-Schlüssel.** ``_cache_key`` liest die
#   Argumente NACH ``validate_tool_args``; bis heute fiel ``confirmToken`` dort
#   heraus, Vorschau und Ausführung hatten damit denselben Cache-Schlüssel. Der
#   Ausführungsaufruf bekam die alte Vorschau zurück, ohne dass der Server je
#   davon erfuhr. Beide Stellen sind jetzt behoben; die Sperre hier bleibt
#   trotzdem die belastbare — sie hängt an keiner zweiten Bedingung.
# * **Vorschläge ändern sich.** ``wlo_list_suggestions`` liest nur, aber nach
#   einer Entscheidung ist die aufgehobene Liste falsch.
#
# ``wlo_auth_status`` steht daneben, weil es „unter welchem Namen würde
# geschrieben" beantwortet. Der Zugangsblock reist im ContextVar und nicht in
# den Argumenten, geht also NICHT in den Cache-Schlüssel ein — eine aufgehobene
# Antwort gehörte womöglich einer anderen Person.
_TOOL_CACHE_BLOCKLIST = frozenset({
    "wlo_health_check",
    "wlo_auth_status",
    *CURATION_TOOLS,
})
