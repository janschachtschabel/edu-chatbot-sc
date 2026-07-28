"""LP-Fast-Path body (P4-5, port of ALT ``chat_turn_routing._route_pattern``
Z. 282-597 — the ``if _has_lp_intent and _thema:`` learning-path block).

``run_lp_fast_path`` gathers learning-path material (Priority 1 = individual
session contents, Priority 2 = session collections, Priority 3 = fresh search +
thin-candidates fallback), generates the pedagogical path text via the LLM,
starts the M09 speculative quick-reply task, applies LP-diversity filtering and
marks the canvas follow-up state. It mutates ``session_state`` in place (ALT
parity: LP diversity ids, per-topic skipCount, ``_canvas_*`` markers) and
returns an :class:`LpFastPathResult`.

Home is ``services/`` (async MCP + LLM I/O). The body is a **verbatim** port of
the ALT block — every helper is imported under its ALT name so the 315 lines
need no rewrites. Documented deviations (proven by the AST-diff gate):
- the 5 ``await resolve_discipline_labels(...)`` calls are dropped (ALT no-op
  stub — MCP v2 emits clean labels server-side; ALT even invites deleting them);
- ALT's lazy ``from app.services.llm_service import generate_learning_path_text``
  is a top-level import here;
- the prolog body-init locals (classification_dict, _msg_lower, _last_*, _lp_routed,
  _lp_cards_collected) are computed at the function head (ALT set them in
  ``_route_pattern``'s prolog before the block);
- ``_lp_title`` stays as an unused local (ALT dead code since the canvas-open
  ``page_action`` was removed) — kept verbatim for fidelity.

**simplify (bewusste Ausnahme):** die Funktion ist deutlich länger als der
~50-Zeilen-Schwellwert — ein 1:1-Verbatim-Port eines kohäsiven, getesteten ALT-
Blocks. Als AST-diffbare Einheit gehalten (0 Divergenz) statt in un-diffbare
Sub-Funktionen mit Zustands-Threading zu splitten; ein verhaltens-erhaltender
Split kommt nach der Graph-Verdrahtung (Integrationsdeckung vorhanden).

Verdrahtung in den Route-Node (TurnContext ``lp_routed``/``fp_*``/``qr_*`` +
Effective-Pattern-Reconciliation) + der Canvas-Fast-Path folgen als eigene
Slices.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, NamedTuple

from boerdi.domain.cards.lp_diversity import (
    _add_used_lp_ids,
    _filter_cards_used_in_text,
    _get_used_lp_ids,
)
from boerdi.domain.lp_intent import _lp_keywords
from boerdi.domain.quick_reply_policy import (
    _qr_default_count,
    _qr_policy,
    _spec_qr_response_block,
)
from boerdi.services.llm_learning_path import generate_learning_path_text
from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.mcp.parsers import parse_wlo_cards
from boerdi.services.quick_replies_llm import generate_quick_replies

logger = logging.getLogger(__name__)

# Matches the header line the LP generator emits, e.g. "> **Lernpfad: Eiszeit**".
_re_lp_title = re.compile(r"\*\*(Lernpfad:[^*]+)\*\*")


class LpFastPathResult(NamedTuple):
    """Outputs of the LP fast-path (ALT ``_route_pattern`` LP-block locals).

    ``routed`` mirrors ALT ``_lp_routed``. When it is False the response/cards/qr
    fields are None so the caller keeps the standard path's values (ALT tail:
    ``_fp_* = response_text if _lp_routed else None`` and
    ``if not _lp_routed: _qr_mode, _qr_max = _qr_policy(effective)``).
    ``qr_spec_task`` is the input task unless the M09 speculative branch replaced it.
    """

    routed: bool
    response_text: str | None
    wlo_cards_raw: list[dict] | None
    tools_called: list[str]
    new_state: str
    qr_mode: str | None
    qr_max: int | None
    qr_spec_task: Any


async def run_lp_fast_path(
    *,
    has_lp_intent: bool,
    thema: str,
    req: Any,
    classification: Any,
    session_state: dict,
    pattern_output: dict,
    usage_acc: dict,
    new_state: str,
    qr_spec_task: Any = None,
) -> LpFastPathResult:
    """Run the learning-path fast-path; see the module docstring for the port.

    Returns an :class:`LpFastPathResult`; not routed ⇒ ``routed=False`` with the
    input ``new_state``/``qr_spec_task`` echoed and the fast-path fields None.
    """
    if not (has_lp_intent and thema):
        return LpFastPathResult(
            routed=False, response_text=None, wlo_cards_raw=None,
            tools_called=[], new_state=new_state, qr_mode=None,
            qr_max=None, qr_spec_task=qr_spec_task,
        )
    # ── ALT-Prolog body-init locals (Z. 196/199/225/226/227/231) ─────────
    _has_lp_intent = has_lp_intent
    _thema = thema
    _qr_spec_task = qr_spec_task
    classification_dict = classification.model_dump()
    _msg_lower = req.message.lower()
    _last_contents_json = session_state.get("entities", {}).get("_last_contents", "")
    _last_collections_json = session_state.get("entities", {}).get("_last_collections", "")
    _lp_routed = False
    _lp_cards_collected: list[dict] = []
    contents_text = ""
    topic = _thema
    tools_called = []
    _lp_used = _get_used_lp_ids(session_state)
    _lp_new_ids: list[str] = []
    _lp_reset = False

    # Topic-switch detection: if classification gave us a NEW thema that
    # doesn't appear in any cached content/collection title, force a fresh
    # search (Priority 3) instead of reusing stale session items.
    _new_thema = (classification.entities or {}).get("thema", "").strip()
    _force_fresh_search = False
    if _new_thema:
        _haystack = (_last_contents_json + _last_collections_json).lower()
        if _new_thema.lower() not in _haystack:
            _force_fresh_search = True
            _last_contents_json = ""
            _last_collections_json = ""
            topic = _new_thema
            logger.info("LP topic switch → fresh search for '%s'", topic)

    try:
        # Priority 1: Use individual content items from session
        if _last_contents_json:
            _contents = json.loads(_last_contents_json)
            if _contents:
                # Diversity: skip already-used items
                _filtered = [c for c in _contents if c.get("node_id") and c["node_id"] not in _lp_used]
                if not _filtered:
                    _filtered = _contents
                    _lp_reset = True
                _contents = _filtered
                _lp_new_ids.extend(c.get("node_id", "") for c in _contents)
                _lp_cards_collected.extend(_contents)
                contents_lines = []
                for c in _contents:
                    types = ", ".join(c.get("learning_resource_types", [])) or "Material"
                    line = f"- **{c['title']}** ({types})"
                    if c.get("description"):
                        line += f"\n  {c['description'][:200]}"
                    if c.get("url"):
                        line += f"\n  URL: {c['url']}"
                    contents_lines.append(line)
                contents_text = "\n".join(contents_lines)
                tools_called = ["generate_learning_path (aus Einzelinhalten)"]

        # Priority 2: Fetch contents FROM session collections (not the collections themselves!)
        if not contents_text and _last_collections_json:
            _collections = json.loads(_last_collections_json)
            if _collections:
                all_collection_contents = []
                tools_called = []
                for col in _collections[:5]:  # Max 5 collections
                    try:
                        col_contents = await call_mcp_tool("get_collection_contents", {
                            "nodeId": col["node_id"],
                            "maxItems": 8,
                            "skipCount": 0,
                        })
                        if col_contents:
                            all_collection_contents.append(
                                f"### Aus Sammlung: {col.get('title', 'Unbekannt')}\n{col_contents}"
                            )
                            _col_cards_parsed = parse_wlo_cards(col_contents)
                            _lp_cards_collected.extend(_col_cards_parsed)
                            tools_called.append(f"get_collection_contents ({col.get('title', '')[:30]})")
                    except Exception as e:
                        logger.warning("Failed to fetch contents for collection %s: %s", col.get("title"), e)
                if all_collection_contents:
                    contents_text = "\n\n".join(all_collection_contents)
                    tools_called.append("generate_learning_path")

        # Priority 3: No session data — search for collections, fetch THEIR contents
        if not contents_text:
            import re as _re
            # Use entity 'thema' if available (from LLM classification)
            _topic_from_entities = session_state.get("entities", {}).get("thema", "")
            _topic_msg = ""
            if _topic_from_entities:
                topic = _topic_from_entities
            else:
                # Extract topic by removing LP/command keywords
                _topic_msg = _msg_lower
                # Remove whole phrases first
                for phrase in ["aus der sammlung", "erstelle mir", "erstelle bitte", "bitte einen", "bitte ein"]:
                    _topic_msg = _topic_msg.replace(phrase, "")
                # Then individual keywords
                for kw in list(_lp_keywords) + ["erstelle", "erstell", "daraus", "einen", "ein", "bitte", "mir",
                                                  "wie sieht", "aus", "zum thema", "zur", "zu", "für", "fuer"]:
                    _topic_msg = _topic_msg.replace(kw, " ")
                _topic_msg = _re.sub(r"\s+", " ", _topic_msg).strip()
            if _topic_msg:
                topic = _topic_msg
            # Per-topic skipCount so repeated LP requests for the same topic
            # page through different search results.
            _topic_key = f"_lp_skip_{topic.lower()[:40]}"
            _search_skip = int(session_state.get("entities", {}).get(_topic_key, 0) or 0)
            logger.info("LP search: topic='%s' skip=%d", topic, _search_skip)
            try:
                search_result = await call_mcp_tool("search_wlo_collections", {
                    "query": topic, "maxItems": 5, "skipCount": _search_skip,
                })
                search_cards = parse_wlo_cards(search_result)
                logger.info("LP found %d collections", len(search_cards))
                if not search_cards and _search_skip > 0:
                    # Pagination exhausted → reset and refetch
                    _search_skip = 0
                    _lp_reset = True
                    search_result = await call_mcp_tool("search_wlo_collections", {
                        "query": topic, "maxItems": 5, "skipCount": 0,
                    })
                    search_cards = parse_wlo_cards(search_result)
                # Helper: how many unique items do we have so far?
                def _unique_count(cards_list: list[dict]) -> int:
                    return len({c.get("node_id", "") for c in cards_list if c.get("node_id")})

                all_lines: list[str] = []
                tools_called = [f"search_wlo_collections ({topic[:30]})"]
                # NOTE: topic must stay as the user asked for it (e.g.
                # "Eiszeit"). We deliberately do NOT overwrite it with the
                # first collection's title — doing so would rebrand the
                # whole learning path to the collection's theme
                # ("Formen der Erdoberfläche") instead of the user's
                # actual topic, silently hijacking the request.
                if search_cards:
                    # Latenz (2026-06-10): Die bis zu 3 Sammlungs-Abrufe
                    # liefen vorher SERIELL (~0,5–1,5 s pro MCP-Call) —
                    # jetzt parallel via gather. Fetch+Parse+Label je
                    # Sammlung im Helper; Exceptions werden zurückgegeben
                    # statt geworfen (Behandlung wie vorher: warning +
                    # skip). Die NACHverarbeitung (Diversity-Filter,
                    # all_lines, tools_called) bleibt sequenziell in
                    # search_cards-Reihenfolge → Ergebnis deterministisch
                    # identisch zum alten Code, nur schneller.
                    async def _fetch_collection(sc: dict):
                        try:
                            _txt = await call_mcp_tool("get_collection_contents", {
                                "nodeId": sc.get("node_id"), "maxItems": 16, "skipCount": 0,
                            })
                            _cards = parse_wlo_cards(_txt)
                            return _cards
                        except Exception as e:
                            return e

                    _col_targets = [sc for sc in search_cards[:3] if sc.get("node_id")]
                    _col_results = await asyncio.gather(
                        *[_fetch_collection(sc) for sc in _col_targets]
                    )
                    for sc, _col_res in zip(_col_targets, _col_results):
                        col_title = sc.get("title", "")
                        if isinstance(_col_res, Exception):
                            logger.warning("LP fetch failed for '%s': %s", col_title, _col_res)
                            continue
                        col_cards = _col_res
                        # Diversity filter: drop already-used items
                        fresh_cards = [c for c in col_cards
                                       if c.get("node_id") and c["node_id"] not in _lp_used]
                        if not fresh_cards and col_cards:
                            fresh_cards = col_cards  # exhausted → use all, will reset later
                            _lp_reset = True
                        if fresh_cards:
                            _lp_cards_collected.extend(fresh_cards[:8])
                            all_lines.append(f"### Aus Sammlung: {col_title}")
                            for c in fresh_cards[:8]:
                                types = ", ".join(c.get("learning_resource_types", [])) or "Material"
                                line = f"- **{c.get('title','')}** ({types})"
                                if c.get("description"):
                                    line += f"\n  {c['description'][:200]}"
                                if c.get("url"):
                                    line += f"\n  URL: {c['url']}"
                                all_lines.append(line)
                                if c.get("node_id"):
                                    _lp_new_ids.append(c["node_id"])
                            tools_called.append(f"get_collection_contents ({col_title[:30]})")

                # ── Thin-candidates fallback ─────────────────────────
                # For specific topics (e.g. "Eiszeit") search_wlo_collections
                # sometimes returns only 1 weakly-related collection with
                # a single item. A useful learning path needs at least a
                # handful of distinct materials. If the collection-based
                # search produced fewer than 4 unique candidates, pull in
                # direct content-level hits via search_wlo_content.
                if _unique_count(_lp_cards_collected) < 4:
                    try:
                        content_res = await call_mcp_tool("search_wlo_content", {
                            "query": topic, "maxItems": 10, "skipCount": 0,
                        })
                        content_cards = parse_wlo_cards(content_res)
                        # Drop items already present + previously used
                        _seen_ids = {c.get("node_id") for c in _lp_cards_collected}
                        fresh_content = [
                            c for c in content_cards
                            if c.get("node_id")
                            and c["node_id"] not in _seen_ids
                            and c["node_id"] not in _lp_used
                        ]
                        if fresh_content:
                            _lp_cards_collected.extend(fresh_content[:8])
                            all_lines.append(f"### Direkte Treffer zu \"{topic}\"")
                            for c in fresh_content[:8]:
                                types = ", ".join(c.get("learning_resource_types", [])) or "Material"
                                line = f"- **{c.get('title','')}** ({types})"
                                if c.get("description"):
                                    line += f"\n  {c['description'][:200]}"
                                if c.get("url"):
                                    line += f"\n  URL: {c['url']}"
                                all_lines.append(line)
                                if c.get("node_id"):
                                    _lp_new_ids.append(c["node_id"])
                            tools_called.append(f"search_wlo_content ({topic[:30]})")
                            logger.info(
                                "LP thin-candidates fallback: added %d content items",
                                len(fresh_content[:8]),
                            )
                    except Exception as e:
                        logger.warning("LP content fallback failed: %s", e)

                if all_lines:
                    contents_text = "\n".join(all_lines)
                    tools_called.append("generate_learning_path")
                    # Advance skipCount for next LP request on same topic
                    session_state.setdefault("entities", {})[_topic_key] = _search_skip + 3
            except Exception as e:
                logger.warning("Failed to search+fetch collections for LP: %s", e)

        logger.info("LP contents: %d chars, topic='%s'", len(contents_text) if contents_text else 0, topic)
        if contents_text:
            # QR-Policy speculative (M09): QR-Generator parallel zum
            # LP-Generator starten — die Kandidaten-Titel sind hier
            # schon bekannt. Eingaben als Kopien, damit spätere
            # Mutationen des Hauptpfads den Prompt nicht verändern.
            _qr_mode, _qr_max = _qr_policy("M09")
            _lp_qr_count = _qr_max if _qr_max is not None else _qr_default_count()
            if _qr_mode == "speculative" and _lp_qr_count > 0:
                try:
                    _lp_spec_titles = [
                        (c.get("title") or "").strip()
                        for c in _lp_cards_collected[:5]
                    ]
                    _qr_spec_task = asyncio.create_task(generate_quick_replies(
                        message=req.message,
                        response_text=_spec_qr_response_block(
                            "M09",
                            pattern_output.get("short_purpose") or "",
                            _lp_spec_titles,
                        ),
                        classification={
                            **classification_dict,
                            "entities": dict(classification_dict.get("entities") or {}),
                        },
                        session_state={
                            **session_state,
                            "entities": dict(session_state.get("entities") or {}),
                        },
                        usage_acc=usage_acc,
                        count=_lp_qr_count,
                    ))
                except Exception as _sqr_err:
                    logger.warning("speculative QR start (M09) failed: %s", _sqr_err)
                    _qr_spec_task = None
            response_text = await generate_learning_path_text(
                collection_title=topic,
                contents_text=contents_text[:6000],
                session_state=session_state,
            )
            if _lp_reset:
                response_text = (response_text or "") + (
                    "\n\n_Hinweis: Es waren keine neuen Inhalte verfügbar, "
                    "deshalb wird die Auswahl jetzt wiederholt._"
                )
                session_state.setdefault("entities", {})["_lp_used_node_ids"] = "[]"
            _add_used_lp_ids(session_state, _lp_new_ids)
            # Welle B.5 (2026-05): Filter on cards mentioned in text is
            # now Pattern-driven (`card_text_link_required` flag). M09
            # has it set to true so the existing LP-tile behaviour is
            # preserved. Other Patterns that might one day route through
            # this LP code path can opt out and keep the full card pool.
            if pattern_output.get("card_text_link_required", False):
                wlo_cards_raw = _filter_cards_used_in_text(
                    _lp_cards_collected, response_text or ""
                )
            else:
                wlo_cards_raw = _lp_cards_collected
            # Welle E (2026-05-24, v2): Material-Links werden später
            # im InlineDocument-Routing-Block ans response_text
            # angehängt — dort sind die finalen ``cards`` (mit
            # Repo-Annotation) verfügbar, die der User auch sieht.
            _lp_routed = True

            # Also hand the learning-path text to the canvas so the user
            # can print/download it and edit it via chat commands.
            _lp_title = f"Lernpfad: {topic}" if topic else "Lernpfad"
            _lp_first_line = (response_text or "").lstrip().splitlines()[0] if response_text else ""
            _m = _re_lp_title.search(_lp_first_line)
            if _m:
                _lp_title = _m.group(1).strip() or _lp_title
            # Mark state so follow-up chat messages are treated as
            # canvas-edits against this learning path.
            new_state = "S3"
            session_state["entities"]["_canvas_material_type"] = "lernpfad"
            session_state["entities"]["_canvas_topic"] = topic or ""
            # Welle E (2026-05-23) — Lernpfad-Markdown bleibt im
            # response_text, kein page_action canvas_open mehr. Das
            # InlineDocument-Routing am Hauptpfad-Ende packt es in die
            # ``inline_documents``-Box; response_text enthält bereits
            # den vollständigen Markdown von generate_learning_path_text.

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Learning path from history failed: %s", e)
    return LpFastPathResult(
        routed=_lp_routed,
        response_text=response_text if _lp_routed else None,
        wlo_cards_raw=wlo_cards_raw if _lp_routed else None,
        tools_called=tools_called,
        new_state=new_state,
        qr_mode=_qr_mode if _lp_routed else None,
        qr_max=_qr_max if _lp_routed else None,
        qr_spec_task=_qr_spec_task,
    )
