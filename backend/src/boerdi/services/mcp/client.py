"""MCP-Client-Kern: ``call_mcp_tool`` verdrahtet die 5-1-Bausteine.

Port aus ALT ``app/services/mcp_client.py`` — dort war das Modul zusätzlich eine
Re-Export-Fassade über tool_defs/transport/tool_cache/arg_resolvers/parsers. Im
NEU-Baum importieren Konsumenten direkt aus den Leaf-Modulen (spec §4), sodass
hier nur der EIGEN-Code des Clients verbleibt:

* ``call_mcp_tool`` — die Orchestrierung: Server-URL-Lookup → ``validate_tool_args``
  → ``TOOL_PREPROCESSORS``-Pipeline → outputFormat-json-Injektion → Cache-Lookup
  (Blocklist/Meta-Re-Emit) → ``transport.call_tool`` → Fehler→Retry-once →
  ``_queryMeta``-Extraktion → ``get_subject_portals``-Kompaktierung → cache_set.
* ``_query_metas`` (ContextVar) + ``reset_query_metas`` + ``get_query_metas`` —
  Per-Request-Akkumulator der ``_queryMeta``-Blöcke (die Route/SSE-Schicht liest
  + leert ihn pro Turn). Wie ``_request_hints`` in arg_resolvers per-Task-scoped.
* ``_compact_subject_portals`` — schlankt das bulkige get_subject_portals-Envelope.
* ``_get_server_url_for_tool`` — Tool→Server-URL über die Studio-MCP-Registry.

Bewusste Abweichungen ggü. ALT (dokumentiert, funktional äquivalent):
* **Transport-Seam.** ALTs ``_ensure_initialized_with_session`` + ``_json_rpc(
  "tools/call", {"name","arguments"}, url=)`` werden durch ``transport.call_tool(
  tool_name, arguments, url=)`` ersetzt (5-1b). Das Result-Dict hat exakt die
  ALT-``_json_rpc``-Form (``{"result": {"content": […]}}`` / ``{"error": …}``),
  daher portiert der Extraktions-/Cache-Rumpf nahezu verbatim.
* **Retry ohne Session-Reset.** ALT nullte vor dem Retry den Per-URL-Session-Slot;
  der SDK-Transport öffnet ohnehin pro Call eine frische Session, sodass der Retry
  ein simpler Zweit-Call ist (kein modul-globaler Session-State — Regel 3).
* **Weggelassen:** der PEP-562-``__getattr__``-Shim (``_session_id``/``_initialized``)
  und der ``resolve_discipline_labels``-No-op — beides ALT-Altlasten für Legacy-
  Importer ohne NEU-Konsument (MCP-v2 liefert saubere Labels; kein Session-State).
"""

from __future__ import annotations

import contextvars as _ctxvars
import json
import logging
import time as _time
from typing import Any

from boerdi.domain.prepared_write import PreparedWrite, read_prepared_write
from boerdi.services.mcp import transport
from boerdi.services.mcp.arg_resolvers import TOOL_PREPROCESSORS
from boerdi.services.mcp.tool_args import (
    _JSON_CAPABLE_TOOLS,
    CONTENT_TEXT_MAX_CHARS,
    validate_tool_args,
)
from boerdi.services.mcp.tool_cache import (
    _TOOL_CACHE,
    _TOOL_CACHE_BLOCKLIST,
    _TOOL_META_CACHE,
    _cache_get,
    _cache_key,
    _cache_set,
)

logger = logging.getLogger(__name__)


# Per-request accumulator for MCP query metadata (_queryMeta blocks).
# Each MCP tool call that returns a _queryMeta content block gets appended
# here. The route/SSE layer reads + clears it to forward as SSE events / debug
# info. Per-async-task scoped via ContextVar so concurrent sessions don't bleed.
# B039 is safe here: the mutable default is never mutated in place —
# reset_query_metas always rebinds via .set([]), get_query_metas reads through
# ``.get([])`` and copies, and call_mcp_tool appends to the ``.get([])`` result
# (a fresh list when unset) then rebinds — so the shared default cannot leak.
_query_metas: _ctxvars.ContextVar[list[dict[str, Any]]] = _ctxvars.ContextVar(
    "_query_metas", default=[],  # noqa: B039 — read-only default (see note)
)


def reset_query_metas() -> None:
    """Clear the per-request query-meta accumulator (call at turn start)."""
    _query_metas.set([])


def get_query_metas() -> list[dict[str, Any]]:
    """Return accumulated query metas for the current request."""
    return list(_query_metas.get([]))


# Zweiter Sammler gleicher Bauart, für die vorbereiteten Schreibzugriffe (E3).
# Im eingebetteten Betrieb führt der MCP-Server eine bestätigte Änderung nicht
# aus, sondern beschreibt sie; abgesetzt wird sie später in der
# Repository-Seite. Getrennt von ``_query_metas``, weil es eine andere Sache
# ist: Metas beschreiben eine gelaufene Suche, dies eine Änderung, die noch
# aussteht. Zur B039-Sicherheit gilt die Notiz oben unverändert.
_prepared_writes: _ctxvars.ContextVar[list[PreparedWrite]] = _ctxvars.ContextVar(
    "_prepared_writes", default=[],  # noqa: B039 — read-only default (siehe oben)
)


def reset_prepared_writes() -> None:
    """Sammler der vorbereiteten Schreibzugriffe leeren (zu Zugbeginn)."""
    _prepared_writes.set([])


def get_prepared_writes() -> list[PreparedWrite]:
    """Die in diesem Zug vorbereiteten Schreibzugriffe."""
    return list(_prepared_writes.get([]))


# Registry-Lookup Tool-Name → Server-URL (config-gekoppelt). ALTs Modul-Konstante
# ``MCP_URL`` (Import-Zeit) wird durch ``transport.resolve_mcp_url()`` ersetzt:
# gleiche Semantik (konfigurierte oder Default-MCP-URL, Trailing-Slash-frei),
# aber pro Aufruf ausgewertet → kein modul-globaler URL-State.
def _get_server_url_for_tool(tool_name: str) -> str:
    """Look up which MCP server provides a given tool.

    Falls back to the configured default MCP URL if no registry match is found.
    """
    from boerdi.services.config_loader import get_enabled_mcp_servers

    default_url = transport.resolve_mcp_url()
    for server in get_enabled_mcp_servers():
        server_tools = server.get("tools", [])
        if tool_name in server_tools:
            return server.get("url", default_url)

    return default_url


def _compact_subject_portals(raw_response: str) -> str:
    """Slim the bulky marketing fields from a ``get_subject_portals``
    response. Each Fachportal's ``description`` is multi-paragraph
    marketing copy (~1-2 KB per item, ~50 KB total) that buries the
    crucial ``nodeId`` so deeply that the LLM emits placeholder UUIDs
    when asked to drill down. We keep:
      * ``nodeId``, ``title``, ``contentCount`` — for the Fach→UUID lookup
      * ``description`` truncated to 220 chars — for downstream
        ``parse_wlo_cards`` which renders subject-portal cards in the UI
      * ``disciplines`` / ``educationalContexts`` (top 4 each) — same
        reason; the cards display them as chips
    Drops keywords, userRoles, learningResourceTypes and any unknown
    extra fields. ~50 KB → ~6 KB for 30 portals: small enough that the
    LLM can scan it for Mathematik in one read.
    """
    parsed = json.loads(raw_response)
    items = parsed.get("results") or parsed.get("items") or []
    compact_items = []
    for it in items:
        if not isinstance(it, dict):
            continue
        slim: dict[str, Any] = {}
        for key in ("nodeId", "title", "contentCount"):
            if key in it:
                slim[key] = it[key]
        # Fachportale SIND Sammlungen (ccm:map) → nodeType erhalten/setzen, sonst
        # defaultet parse_wlo_cards auf "content" → falsche Box (Materialien
        # statt Sammlungen) + Render- statt Collections-Browse-Link.
        slim["nodeType"] = it.get("nodeType") or "collection"
        # Truncate description so cards still render but the LLM doesn't
        # have to wade through a paragraph each.
        desc = it.get("description") or ""
        if isinstance(desc, str) and desc:
            slim["description"] = desc if len(desc) <= 220 else desc[:217] + "…"
        for key in ("disciplines", "educationalContexts"):
            v = it.get(key)
            if isinstance(v, list) and v:
                slim[key] = v[:4]
        if slim:
            compact_items.append(slim)
    out = {
        "total": parsed.get("total", len(compact_items)),
        "results": compact_items,
        "_compacted": True,
    }
    return json.dumps(out, ensure_ascii=False)


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Call a WLO MCP tool via the SDK transport, with parity-preserving wiring.

    Resolved den Tool-Namen über die Studio-Registry (mcp-servers.yaml,
    Env-Override durch ``MCP_SERVER_URL``) auf die passende Server-URL.
    Wenn kein Server den Tool deklariert, fällt es auf die Default-MCP-URL
    zurück — Backward-Compat für Tools, die im Code registriert sind aber
    (noch) nicht in der YAML.
    """
    # Per-Call-Server-URL: zuerst aus der Studio-Registry, sonst Default.
    target_url = _get_server_url_for_tool(tool_name)
    _call_t0 = _time.perf_counter()  # für Tool-Laufzeit-Logging (#3 Debug-Timing)

    # Debug: log raw LLM-supplied arguments BEFORE validation/resolution so we
    # can see exactly what the model wanted to send. Keeps this at INFO — the
    # cost is ~100 bytes per tool call and it's indispensable for diagnosing
    # filter bugs.
    logger.info("MCP tool %s args: %s", tool_name, arguments)

    # Validate arguments before sending to MCP server
    arguments = validate_tool_args(tool_name, arguments)

    # Preprocessor pipeline — zentral registriert in TOOL_PREPROCESSORS.
    # Jeder Preprocessor bekommt das ``arguments``-Dict und gibt ein neues
    # Dict zurück. Aktuell registriert:
    #   * search_wlo_content / search_wlo_collections → label→URI für Filter
    #   * browse_collection_tree                      → Fach-Name → UUID
    #   * get_collection_contents                     → Sammlungs-Name → UUID
    # Neue Auto-Korrekturen kommen einfach als Eintrag in TOOL_PREPROCESSORS
    # dazu, ohne diese Funktion anzufassen.
    pp = TOOL_PREPROCESSORS.get(tool_name)
    if pp is not None:
        try:
            arguments = await pp(arguments)
        except Exception as _ppe:  # noqa: BLE001 — best-effort, Original-Args weiter
            logger.warning(
                "preprocessor for %s failed: %s — passing original args through",
                tool_name, _ppe,
            )

    # Default to JSON output for tools that support it. Cleaner parsing in
    # parse_wlo_cards / parse_wlo_topic_page_cards, label-resolved values,
    # no regex mosaic. v1 servers ignore the unknown param and return
    # Markdown — our parsers accept both, so this is safe to roll out.
    if (
        tool_name in _JSON_CAPABLE_TOOLS
        and "outputFormat" not in arguments
    ):
        arguments = {**arguments, "outputFormat": "json"}

    # Volltext-Deckel zentral anheben (W5-3b). Wie bei ``outputFormat``: an EINER
    # Stelle, damit kein Aufrufer — und kein LLM-Toolcall — versehentlich beim
    # Server-Standard 8000 landet und ein halbes Arbeitsblatt liefert. Ein
    # ausdrücklich mitgegebener Wert gewinnt (z.B. bewusst kurze Vorschau).
    if tool_name == "get_wlo_content_text" and "maxChars" not in arguments:
        arguments = {**arguments, "maxChars": CONTENT_TEXT_MAX_CHARS}

    # Cache-Lookup BEVOR der Transport bemüht wird (Hits sparen den kompletten
    # SDK-Handshake+Call). Blocklist-Tools (Health-Checks) umgehen den Cache.
    cache_key = None
    if tool_name not in _TOOL_CACHE_BLOCKLIST:
        cache_key = _cache_key(tool_name, arguments)
        cached = _cache_get(cache_key)
        if cached is not None:
            logger.info("MCP tool %s cache HIT (%d entries)", tool_name, len(_TOOL_CACHE))
            # Cached queryMetas auch wieder in den Per-Request-Akkumulator
            # zurückspielen — sonst hätten Cache-Hit-Turns keine URI-resolved
            # Filter-Daten für die Such-CTA-URL.
            _cached_metas = _TOOL_META_CACHE.get(cache_key) or []
            if _cached_metas:
                _cur = _query_metas.get([])
                for _cm in _cached_metas:
                    _cur.append(_cm)
                _query_metas.set(_cur)
                logger.debug(
                    "re-emitted %d cached queryMetas for %s",
                    len(_cached_metas), tool_name,
                )
            return cached

    # SDK-Transport (5-1b): Handshake + Call + Result-Normalisierung liegen im
    # Transport, ein Call = frische Session. Result-Dict trägt die ALT-
    # ``_json_rpc``-Form (``{"result": {"content": …}}`` / ``{"error": …}``).
    result = await transport.call_tool(tool_name, arguments, url=target_url)

    if "error" in result:
        error_msg = result["error"].get("message", "Unknown error")
        logger.error("MCP tool %s error @ %s: %s", tool_name, target_url, error_msg)
        # Retry once with a fresh session (der Transport öffnet sie ohnehin neu).
        logger.info("Retrying MCP tool %s with fresh session @ %s...", tool_name, target_url)
        result = await transport.call_tool(tool_name, arguments, url=target_url)
        if "error" in result:
            error_msg = result["error"].get("message", "Unknown error")
            logger.error("MCP tool %s retry failed @ %s: %s", tool_name, target_url, error_msg)
            return f"MCP error: {error_msg}"

    # Extract text content from result, separating _queryMeta blocks.
    result_data = result.get("result", {})
    content_parts = result_data.get("content", [])

    texts = []
    _extracted_metas_this_call: list[dict[str, Any]] = []
    for part in content_parts:
        if isinstance(part, dict) and part.get("type") == "text":
            raw_text = part.get("text", "")
            # Detect _queryMeta JSON block and accumulate it instead of
            # mixing it into the LLM-visible response text.
            if raw_text.startswith('{"_queryMeta"'):
                try:
                    meta = json.loads(raw_text).get("_queryMeta")
                    if meta:
                        metas = _query_metas.get([])
                        metas.append(meta)
                        _query_metas.set(metas)
                        _extracted_metas_this_call.append(meta)
                        logger.debug(
                            "extracted _queryMeta from %s: %s",
                            tool_name, meta.get("queryType"),
                        )
                except (json.JSONDecodeError, AttributeError):
                    texts.append(raw_text)
            else:
                texts.append(raw_text)
        elif isinstance(part, str):
            texts.append(part)

    # Vorbereiteter Schreibzugriff (E3): der Server hat die bestätigte Änderung
    # beschrieben, statt sie auszuführen. Der Text bleibt unangetastet — er sagt
    # dem Modell, dass hier nichts geschrieben wurde. Unbrauchbares wird still
    # verworfen (``read_prepared_write``): abgesetzt wird das später von einem
    # Browser mit fremden Rechten, da ist nichts besser als etwas Halbes.
    vorbereitet = read_prepared_write(result_data.get("structuredContent"))
    if vorbereitet is not None:
        offene = _prepared_writes.get([])
        offene.append(vorbereitet)
        _prepared_writes.set(offene)
        logger.info("MCP tool %s hat einen Schreibzugriff vorbereitet: %s",
                    tool_name, vorbereitet.method)
    elif result_data.get("structuredContent") is not None:
        logger.warning(
            "MCP tool %s schickte einen strukturierten Teil, der keine "
            "brauchbare Anfrage ergibt — verworfen", tool_name)

    response = "\n".join(texts) if texts else json.dumps(result_data)
    logger.info(
        "MCP tool %s returned %d chars in %d ms",
        tool_name, len(response), round((_time.perf_counter() - _call_t0) * 1000),
    )

    # Slim ``get_subject_portals``: the raw API ships rich marketing
    # descriptions for every Fachportal (~50 KB total). The LLM only
    # needs nodeId + title to resolve a Fach name → UUID, and the
    # over-long descriptions actively confuse the model into emitting a
    # placeholder UUID like ``"dummmy"`` instead of extracting the right
    # one. Compact the response to nodeId / title / contentCount while
    # keeping the JSON-envelope shape callers expect.
    if tool_name == "get_subject_portals":
        try:
            response = _compact_subject_portals(response)
            logger.info("get_subject_portals compacted to %d chars", len(response))
        except Exception as _ce:  # noqa: BLE001 — Kompaktierung best-effort
            logger.warning("get_subject_portals compaction failed: %s", _ce)

    # Successful response into cache (only if we have a key, i.e. the tool
    # isn't in the blocklist).
    if cache_key is not None:
        _cache_set(cache_key, response)
        # Auch die extrahierten queryMetas mit-cachen, damit Cache-Hits die
        # strukturierten Filter-Daten (URI-resolved discipline /
        # educationalContext / learningResourceType) wieder re-emitten können —
        # siehe Re-Emit-Logik im Cache-Hit-Zweig oben.
        if _extracted_metas_this_call:
            _TOOL_META_CACHE[cache_key] = _extracted_metas_this_call
    return response
