"""Argument-Resolution für MCP-Tool-Calls (Preprocessor-Registry).

1:1-Port aus ALT ``app/services/mcp_arg_resolvers.py``: Request-Hints
(ContextVar), die Selbstheilungs-Resolver für LLM-Fehlgriffe (Fachportal-/
Sammlungs-UUIDs), die Label→URI-Vokabular-Caches inkl. LLM-Fallback sowie die
``TOOL_PREPROCESSORS``-Registry.

Der mutable Zustand (``_request_hints``, ``_label_to_uri_cache``,
``_label_cache_loaded``, ``_llm_vocab_cache``, ``TOOL_PREPROCESSORS``) lebt
GENAU EINMAL hier; ``client`` (5-1c) importiert die Registry per Referenz.

``call_mcp_tool`` wird über den Shim unten LATE-BOUND aus ``client`` aufgelöst —
damit bleibt der etablierte Patch-Ort ``services.mcp.client.call_mcp_tool``
auch für die Resolver-Roundtrips (get_subject_portals / search_wlo_collections /
lookup_wlo_vocabulary) wirksam, und es entsteht kein Import-Zyklus (``client``
importiert ``arg_resolvers`` beim Laden; der Rück-Import hier ist lazy).

Bewusste Abweichungen ggü. ALT (dokumentiert, verhaltensneutral):
* ``_llm_vocab_match`` geht über ``llm.chat_completion`` (Routing/Semaphore/
  Usage) statt ALTs ``get_client()``/``get_chat_model()`` — LiteLLM hat kein
  persistentes Client-Objekt; identische Anpassung wie in ``quick_replies_llm``.
* ``from boerdi.services import llm`` steht auf Modulebene (NEU-Hausstil; kein
  Zyklus, da ``llm.py`` nichts aus ``mcp`` importiert).
"""

from __future__ import annotations

import contextvars as _ctxvars
import json
import logging
import re
from typing import Any

from boerdi.services import llm

logger = logging.getLogger(__name__)


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Late-bound Shim auf den Client — NICHT hier patchen; der Patch-Ort
    bleibt ``services.mcp.client.call_mcp_tool`` (Lookup pro Aufruf)."""
    from boerdi.services.mcp.client import call_mcp_tool as _impl
    return await _impl(tool_name, arguments)


# Pattern for canonical UUID (8-4-4-4-12 hex). Used to decide whether
# ``browse_collection_tree``'s ``nodeId`` is already a real UUID or a
# Fachportal name we have to resolve first.
_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)


# Per-request classification hints — chat.py sets this once per turn from
# ClassificationResult.entities (fach, thema, stufe, …). Tool preprocessors
# read it to override LLM mistakes (e.g. wrong UUID in browse_collection_tree).
# Per-async-task scoped via ContextVar so concurrent sessions don't bleed.
# B039 is safe here: the mutable default is never mutated in place —
# set_request_hints always rebinds via .set(), and get_request_hint reads
# through ``or {}`` — so the shared-default footgun cannot fire (ALT-Parität).
_request_hints: _ctxvars.ContextVar[dict[str, Any]] = _ctxvars.ContextVar(
    "_request_hints", default={},  # noqa: B039 — read-only default (see note)
)


def set_request_hints(hints: dict[str, Any]) -> None:
    """Set the per-request hint dict (typically the classifier's
    ``entities`` map). Tool preprocessors look up keys like ``fach``,
    ``thema``, ``stufe`` to self-correct LLM-supplied arguments.

    Empty / falsy values are dropped so a missing hint never overrides a
    correct LLM choice.
    """
    cleaned: dict[str, Any] = {}
    for k, v in (hints or {}).items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        cleaned[k] = v
    _request_hints.set(cleaned)


def get_request_hint(key: str, default: Any = "") -> Any:
    """Read one hint from the active request context."""
    return (_request_hints.get() or {}).get(key, default)


# Backwards-compatible thin alias for the old single-purpose API. New code
# should use ``set_request_hints({"fach": ...})`` instead.
def set_active_fach(fach: str) -> None:
    set_request_hints({"fach": (fach or "").strip()})


def _find_portal_by_name(results: list, name: str) -> dict[str, Any] | None:
    """Best-effort title match against a list of subject-portal dicts.
    Strategy (most → least strict): exact, case-insensitive, prefix,
    contains."""
    if not name or not results:
        return None
    needle = name.lower()
    for r in results:
        if isinstance(r, dict) and r.get("title") == name:
            return r
    for r in results:
        if isinstance(r, dict) and (r.get("title") or "").lower() == needle:
            return r
    for r in results:
        if isinstance(r, dict) and (r.get("title") or "").lower().startswith(needle):
            return r
    for r in results:
        if isinstance(r, dict) and needle in (r.get("title") or "").lower():
            return r
    return None


async def _resolve_browse_node_id(arguments: dict[str, Any]) -> dict[str, Any]:
    """Self-heal ``browse_collection_tree`` calls.

    Two fix paths, both rooted in the same problem: the LLM is bad at
    picking the right UUID for a Fach name from ``get_subject_portals``.

    1. **Non-UUID input** (``"Mathematik"``, ``"?"``, ``"dummmy"``,
       empty): treat as a Fach name and resolve to UUID via cached
       ``get_subject_portals``.

    2. **UUID input but wrong Fach** (e.g. picked Geographie's UUID
       while user asked about Mathematik): if the per-request
       ``_active_fach`` context-var is set AND the chosen UUID's title
       doesn't match it, override with the correct UUID.

    Both paths are no-ops when the LLM picked correctly.
    """
    nid = (arguments.get("nodeId") or "").strip()
    fach_hint = (get_request_hint("fach", "") or "").strip()

    # Fast-path: not a UUID — must be a name (or junk). Resolve.
    if not nid or not _UUID_RE.match(nid):
        try:
            portals_raw = await call_mcp_tool(
                "get_subject_portals", {"includeContentCounts": False},
            )
            results = (json.loads(portals_raw).get("results")
                       or json.loads(portals_raw).get("items") or [])
        except Exception as e:
            logger.warning("browse_collection_tree nodeId resolution failed: %s", e)
            return arguments
        match = _find_portal_by_name(results, nid) or (
            _find_portal_by_name(results, fach_hint) if fach_hint else None
        )
        if match and match.get("nodeId"):
            resolved = match["nodeId"]
            logger.info(
                "browse_collection_tree nodeId resolved: %r → %s (%s)",
                nid, resolved, match.get("title", ""),
            )
            return {**arguments, "nodeId": resolved}
        logger.info(
            "browse_collection_tree nodeId %r not resolvable to a Fachportal — passing through",
            nid,
        )
        return arguments

    # UUID input — verify against fach_hint if we have one.
    if not fach_hint:
        return arguments
    try:
        portals_raw = await call_mcp_tool(
            "get_subject_portals", {"includeContentCounts": False},
        )
        results = (json.loads(portals_raw).get("results")
                   or json.loads(portals_raw).get("items") or [])
    except Exception:
        return arguments
    chosen = next(
        (r for r in results if isinstance(r, dict) and r.get("nodeId") == nid),
        None,
    )
    chosen_title = (chosen.get("title") if chosen else "") or ""
    fach_lower = fach_hint.lower()
    if chosen_title and fach_lower in chosen_title.lower():
        return arguments  # LLM picked correctly
    correct = _find_portal_by_name(results, fach_hint)
    if correct and correct.get("nodeId") and correct["nodeId"] != nid:
        logger.info(
            "browse_collection_tree nodeId override: %s (%s) → %s (%s) — entities.fach=%r",
            nid, chosen_title, correct["nodeId"], correct.get("title"), fach_hint,
        )
        return {**arguments, "nodeId": correct["nodeId"]}
    return arguments


async def _resolve_collection_node_id(arguments: dict[str, Any]) -> dict[str, Any]:
    """Self-heal ``get_collection_contents`` calls when the LLM passed a
    collection name instead of a UUID.

    Same failure pattern as M08 / browse_collection_tree, but for
    arbitrary collections (not just Fachportale). When ``nodeId`` is a
    plain title like ``"Eiszeit"`` or ``"Klimawandel-Materialien"``, run
    a one-shot ``search_wlo_collections(query=<name>, maxResults=1)`` and
    substitute the top hit's UUID. Falls back to passing through if no
    match.

    Less aggressive than the browse_collection_tree resolver — we do NOT
    override an LLM-supplied UUID even on hint mismatch, because the
    universe of collections is huge and a UUID-mismatch is more often
    semantically valid (e.g. user clicks a sub-collection card and the
    UUID legitimately differs from the parent topic).
    """
    nid = (arguments.get("nodeId") or "").strip()
    if not nid or _UUID_RE.match(nid):
        return arguments
    # Treat as collection name — resolve via search.
    try:
        raw = await call_mcp_tool(
            "search_wlo_collections",
            {"query": nid, "maxResults": 3},
        )
        # search_wlo_collections returns a JSON envelope or markdown depending
        # on the MCP server. Try JSON first, fall back to looking for the
        # first ``"nodeId"`` field via regex if not parseable.
        try:
            parsed = json.loads(raw)
            results = parsed.get("results") or parsed.get("items") or []
            top = next(
                (r for r in results if isinstance(r, dict) and r.get("nodeId")),
                None,
            )
            top_uuid = top.get("nodeId") if top else None
            top_title = (top.get("title") if top else "") or ""
        except Exception:
            m = re.search(r'"nodeId"\s*:\s*"([^"]+)"', raw or "")
            top_uuid = m.group(1) if m else None
            top_title = ""
    except Exception as e:
        logger.warning("get_collection_contents nodeId resolution failed: %s", e)
        return arguments
    if top_uuid and _UUID_RE.match(top_uuid):
        logger.info(
            "get_collection_contents nodeId resolved: %r → %s (%s)",
            nid, top_uuid, top_title,
        )
        return {**arguments, "nodeId": top_uuid}
    logger.info(
        "get_collection_contents nodeId %r not resolvable to a collection — passing through",
        nid,
    )
    return arguments


# ── Label→URI caches for filter auto-resolution ─────────────────
#
# Maps lowercased label OR alias → canonical URI. Populated lazily
# via lookup_wlo_vocabulary. Used by _resolve_filter_uris to translate
# LLM-produced filter values (which may arrive as labels like 'Video'
# or aliases like 'interaktiv') into the URI form the MCP server
# requires for filtering.
_label_to_uri_cache: dict[str, dict[str, str]] = {
    # vocabulary → {normalized_label_or_alias: uri}
    "lrt": {},
    "discipline": {},
    "educationalContext": {},
    "userRole": {},
}
_label_cache_loaded: dict[str, bool] = {
    "lrt": False,
    "discipline": False,
    "educationalContext": False,
    "userRole": False,
}


def _norm_label(s: str) -> str:
    """Lowercase and strip for case-insensitive lookup."""
    return (s or "").strip().lower()


async def _ensure_label_cache(vocab: str) -> None:
    """Lazily populate the label→URI cache for a vocabulary."""
    if _label_cache_loaded.get(vocab):
        return
    if vocab not in _label_to_uri_cache:
        return  # unknown vocab, do nothing
    try:
        raw = await call_mcp_tool("lookup_wlo_vocabulary", {"vocabulary": vocab})
    except Exception as e:  # pragma: no cover — network failure
        # B5 (2026-06-10): NICHT als geladen markieren — vorher latchte ein
        # einziger Netzwerkfehler beim Start den Cache permanent leer
        # (Filter-Auflösung degradiert bis zum Neustart). Ohne Latch
        # versucht der nächste Bedarfs-Aufruf es einfach erneut.
        logger.warning("%s vocabulary preload failed (retry on next use): %s",
                       vocab, e)
        return

    # Output format (from real MCP response):
    #   - **Video**
    #     URI: http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/...
    #   - **Interaktives medium** | Aliases: interactive media, interaktiv, simulation
    #     URI: http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/...
    import re as _re
    current_label: str | None = None
    current_aliases: list[str] = []
    cache = _label_to_uri_cache[vocab]

    for line in (raw or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        # Entry header: "- **Label** | Aliases: a, b, c" or "- **Label**"
        m_label = _re.match(r"-\s*\*\*(.+?)\*\*(?:\s*\|\s*Aliases:\s*(.+))?\s*$", line)
        if m_label:
            current_label = m_label.group(1).strip()
            aliases_str = m_label.group(2) or ""
            current_aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]
            continue
        # URI line: "URI: http://..."
        m_uri = _re.match(r"URI:\s*(https?://\S+)", line)
        if m_uri and current_label:
            uri = m_uri.group(1).strip()
            cache.setdefault(_norm_label(current_label), uri)
            for alias in current_aliases:
                cache.setdefault(_norm_label(alias), uri)
            current_label = None
            current_aliases = []

    logger.info("%s label→URI cache loaded: %d entries", vocab, len(cache))
    _label_cache_loaded[vocab] = True


async def prewarm_vocabularies() -> None:
    """O3: Vokabular-Caches beim Backend-Start vorladen, damit schon der ERSTE
    Such-Turn warm ist (sonst mehrere MCP-Round-Trips beim ersten Nutzer).

    Lädt die vier genutzten Vokabulare parallel und best-effort: Fehler (z.B.
    MCP gerade kalt/nicht erreichbar) werden geschluckt — der bestehende
    Lazy-Fallback (``_ensure_label_cache`` beim ersten echten Bedarf) greift
    dann weiterhin. Die Result-TTL für ``lookup_wlo_vocabulary`` liegt bei 24h.
    """
    import asyncio as _asyncio
    vocabs = ["lrt", "discipline", "educationalContext", "userRole"]
    results = await _asyncio.gather(
        *[_ensure_label_cache(v) for v in vocabs], return_exceptions=True,
    )
    loaded = sum(1 for v in vocabs if _label_cache_loaded.get(v))
    # zip parity: vocabs/results are equal-length by gather-construction, so
    # strict= is moot; keeping bare zip preserves the exact ALT bytes.
    failed = [v for v, r in zip(vocabs, results) if isinstance(r, Exception)]  # noqa: B905
    logger.info("vocabulary prewarm: %d/%d geladen%s", loaded, len(vocabs),
                f", fehlgeschlagen={failed}" if failed else "")


def _fuzzy_lookup(cache: dict[str, str], needle: str) -> tuple[str, str] | None:
    """Best-effort label→URI lookup that tolerates LLM paraphrasing.

    Strategy:
    1. Exact match on normalized form ("Video" → cache["video"]).
    2. Substring containment either way — cache key contains needle OR
       needle contains cache key. This catches "Interaktives Material"
       vs. cache entry "interaktiv" (alias of "Interaktives medium"):
       needle contains the alias, so it matches.
    3. Longest-substring wins when multiple keys match, to prefer
       specific over generic (e.g. "interaktives medium" over "medium").

    Returns (matched_key, uri) on hit, None otherwise.
    """
    if not needle:
        return None
    nn = _norm_label(needle)
    # 1. exact
    if nn in cache:
        return nn, cache[nn]
    # 2. substring
    best_key: str | None = None
    best_len = 0
    for key in cache:
        if not key:
            continue
        # key appears in needle (e.g. "interaktiv" in "interaktives material")
        if key in nn or nn in key:
            if len(key) > best_len:
                best_key = key
                best_len = len(key)
    if best_key is not None:
        return best_key, cache[best_key]
    return None


# ── LLM-gestütztes Vocab-Mapping (Fallback wenn fuzzy_lookup leer ausgeht) ──
#
# User-Eingaben sind nicht immer in unserer Vokabular-Form ("biology" statt
# "Biologie", "Mathe Klasse 11 Gym", "Naturwiss"). _fuzzy_lookup deckt
# Substring-Paraphrasen ab; für komplexere Mappings (Sprache, paraphrasierte
# Konzepte) holen wir den LLM dazu — pro (vocab, value)-Kombination einmal,
# dann gecacht.
_llm_vocab_cache: dict[tuple[str, str], str | None] = {}

# Eingaben, die offensichtlich keine Vokabular-Werte sind, sollten gar nicht
# erst beim LLM landen (verschwendet Tokens und Latenz). Sehr lange Strings,
# offensichtliche Sätze oder Whitespace-only werden hier abgewiesen.
_LLM_VOCAB_MIN_LEN = 2
_LLM_VOCAB_MAX_LEN = 80
_LLM_VOCAB_CACHE_MAX = 5000  # FIFO-Deckel gegen unbegrenztes Cache-Wachstum (Audit)


def _cache_vocab(cache_key: tuple[str, str], value: str | None) -> str | None:
    """LLM-Vocab-Ergebnis cachen mit FIFO-Größendeckel.

    ``_llm_vocab_cache`` wuchs sonst über die Prozesslaufzeit unbegrenzt (ein
    Eintrag je einzigartigem normalisiertem Wert). Bei Überschreitung wird der
    ÄLTESTE Eintrag verworfen (dict bewahrt Insertion-Order ab Py 3.7).
    """
    if cache_key not in _llm_vocab_cache and len(_llm_vocab_cache) >= _LLM_VOCAB_CACHE_MAX:
        _llm_vocab_cache.pop(next(iter(_llm_vocab_cache)), None)
    _llm_vocab_cache[cache_key] = value
    return value


async def _llm_vocab_match(vocab: str, value: str) -> str | None:
    """Use the chat LLM to map a free-form value to a vocabulary URI.

    Returns the URI on a confident match, ``None`` when the LLM declines.
    Cached per (vocab, normalized_value) — repeats only consume one LLM call
    across the whole process lifetime.
    """
    nv = _norm_label(value)
    if not nv:
        return None
    if len(nv) < _LLM_VOCAB_MIN_LEN or len(nv) > _LLM_VOCAB_MAX_LEN:
        return None
    cache_key = (vocab, nv)
    if cache_key in _llm_vocab_cache:
        return _llm_vocab_cache[cache_key]

    cache = _label_to_uri_cache.get(vocab) or {}
    if not cache:
        return None

    # Build a compact list of "<label or alias>: <uri>" — the LLM picks one.
    # We dedupe URIs since multiple aliases share the same URI.
    by_uri: dict[str, list[str]] = {}
    for key, uri in cache.items():
        by_uri.setdefault(uri, []).append(key)
    options_lines: list[str] = []
    for uri, aliases in by_uri.items():
        prim = aliases[0]
        rest = aliases[1:6]  # cap aliases to keep prompt small
        suffix = f" (also: {', '.join(rest)})" if rest else ""
        options_lines.append(f"- {prim}{suffix} → {uri}")
    options_text = "\n".join(options_lines)

    vocab_label = {
        "lrt": "learning resource type",
        "discipline": "school subject / discipline",
        "educationalContext": "educational level / Bildungsstufe",
        "userRole": "target user role",
    }.get(vocab, vocab)

    system = (
        "You are a strict vocabulary mapper for the WirLernenOnline (WLO) "
        f"taxonomy. Map a free-form user term to ONE entry from the list of "
        f"valid {vocab_label}s, or reply 'NONE' if no entry matches with "
        "reasonable confidence. Reply ONLY with the URI of the chosen entry "
        "(verbatim from the list) or the literal string 'NONE'. No prose, no "
        "punctuation."
    )
    user = (
        f"User term: {value!r}\n\n"
        f"Valid {vocab_label}s:\n{options_text}\n\n"
        "Pick the URI of the best matching entry, or reply 'NONE'."
    )

    try:
        # Transport über die NEU-LLM-Fassade (Routing/Semaphore/Usage) statt
        # ALTs get_client()/get_chat_model() — LiteLLM hat kein persistentes
        # Client-Objekt; identische Anpassung wie in quick_replies_llm. Das
        # Modell löst chat_completion selbst über get_chat_model() auf.
        resp = await llm.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=80,
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("LLM vocab-match for %s=%r failed: %s", vocab, value, e)
        _cache_vocab(cache_key, None)
        return None

    if not content or content.upper() == "NONE":
        _cache_vocab(cache_key, None)
        logger.info("LLM declined vocab match: %s=%r", vocab, value)
        return None

    # Validate: must be one of the URIs we offered.
    valid_uris = set(by_uri.keys())
    # The model sometimes wraps the URI in quotes/backticks — strip light
    # decoration before comparing.
    candidate = content.strip().strip("`'\"<>")
    if candidate not in valid_uris:
        # Last resort: see if the response *contains* one of the URIs.
        for uri in valid_uris:
            if uri in candidate:
                candidate = uri
                break
        else:
            logger.warning(
                "LLM vocab-match returned non-URI for %s=%r: %r",
                vocab, value, content[:200],
            )
            _cache_vocab(cache_key, None)
            return None

    _cache_vocab(cache_key, candidate)
    logger.info("LLM resolved vocab %s=%r → %s", vocab, value, candidate)
    return candidate


async def _resolve_filter_uris(arguments: dict[str, Any]) -> dict[str, Any]:
    """Rewrite label-style filter values into URIs using vocabulary caches.

    The WLO MCP server accepts BOTH plain labels and full URIs for its
    filter params (learningResourceType, discipline, educationalContext,
    userRole). We still run a label→URI translation because:
      * it normalises paraphrased values ("Interaktives Material" → the
        canonical alias "interaktiv" → URI for Interaktives medium), and
      * URIs are unambiguous and less brittle to server-side label parsing.

    Leaves URIs untouched. Unresolvable labels are passed through — the
    server may still accept them (exact label match) or at worst return
    unfiltered results.
    """
    # Map the server's actual parameter names → vocabulary name used with
    # lookup_wlo_vocabulary. These are the REAL MCP param names (matched
    # against the server's tools/list schema), NOT our historical aliases.
    key_to_vocab = {
        "learningResourceType": "lrt",
        "discipline": "discipline",
        "educationalContext": "educationalContext",
        "userRole": "userRole",
    }
    out = dict(arguments)
    for key, vocab in key_to_vocab.items():
        val = out.get(key)
        if not isinstance(val, str) or not val:
            continue
        if val.startswith(("http://", "https://")):
            continue  # already a URI
        await _ensure_label_cache(vocab)
        cache = _label_to_uri_cache.get(vocab) or {}
        match = _fuzzy_lookup(cache, val)
        if match:
            matched_key, uri = match
            if matched_key == _norm_label(val):
                logger.info("resolved %s=%r → %s", key, val, uri)
            else:
                logger.info("resolved %s=%r via fuzzy %r → %s", key, val, matched_key, uri)
            out[key] = uri
            continue
        # Heuristik leer → LLM-Fallback. Greift bei paraphrasierten /
        # fremdsprachigen / nicht-canonical Eingaben ("sciences",
        # "Mathe Klasse 11 Gym", "Naturwiss"). Pro (vocab, value) genau
        # ein LLM-Call dank _llm_vocab_cache.
        llm_uri = await _llm_vocab_match(vocab, val)
        if llm_uri:
            out[key] = llm_uri
            continue
        logger.info("no URI for %s=%r (vocab=%s); passing label through", key, val, vocab)
    return out


# ── Tool-Preprocessor-Registry ─────────────────────────────────────────
# Map of MCP tool name → async preprocessor that mutates the call args
# BEFORE they reach the WLO server. Used to self-correct LLM mistakes
# (wrong UUIDs, label-as-URI mix-ups, etc.) without round-tripping back
# to the LLM via the Reflection-Loop. Each preprocessor takes a dict
# and returns a (possibly modified) dict; raising = pass through original.
#
# Defined at module-bottom so the resolver functions above are bound by
# the time this dict is built. ``call_mcp_tool`` looks up by tool name at
# every call.
TOOL_PREPROCESSORS: dict[str, Any] = {
    "search_wlo_content":      _resolve_filter_uris,
    "search_wlo_collections":  _resolve_filter_uris,
    "search_wlo_all":          _resolve_filter_uris,
    "browse_collection_tree":  _resolve_browse_node_id,
    "get_collection_contents": _resolve_collection_node_id,
}
