"""Topic-pages MCP-search helpers (P5-6b, port of ALT chat_topic_pages.py):
the stateless emptiness/title-filter helpers, the async warmup+global-fallback
search and — R6-wired — the M16 view resolver
(``_resolve_m16_topic_page_view``). They form one cohesive topic-pages concern
(the warmup consumes both pure helpers; the resolver drives the M16 Themenseiten-
content view), so they land together in ``services/`` — the same pure+async
grouping as ``outcome_service.py`` / sibling ``card_pipeline.py``.

Deviations vs ALT:
- the warmup's lazy MCP import points at the NEU leaf module
  (``boerdi.services.mcp.client``, no facade);
- the M16 resolver takes ``winner_id: str`` (ALT passed a ``winner`` object and
  read only ``winner.id``) and drops the tracer (project-wide in NEU); its MCP/
  schema seams point at ``boerdi.services.mcp.{client,parsers}`` +
  ``boerdi.api.schemas``. ``call_mcp_tool`` is a top-import so the resolver's
  tests patch it on THIS module (the warmup keeps its own lazy alias).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from boerdi.services.mcp.client import call_mcp_tool

logger = logging.getLogger(__name__)


def _is_empty_topic_pages_response(raw: str) -> bool:
    """True when the WLO MCP server reported no topic pages found for a
    ``search_wlo_topic_pages`` call. The server uses BOTH a German plain-
    text marker and (occasionally) an empty JSON results array — match
    either."""
    if not raw:
        return True
    if "Keine Themenseiten" in raw:
        return True
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            results = parsed.get("results") or parsed.get("items") or []
            return not results
    except Exception:
        logger.debug("emptiness check: tool payload is not valid JSON", exc_info=True)
    return False


def _filter_topic_pages_by_title(raw: str, needle: str) -> str | None:
    """Filter a ``search_wlo_topic_pages`` JSON envelope to results whose
    ``title`` contains ``needle`` (case-insensitive). Returns the
    re-serialised filtered envelope, or ``None`` if no match.

    Used for the global-fallback path: when the server's tight query
    matcher returns "Keine Themenseiten gefunden" but the topic page
    actually exists in the unfiltered global list.
    """
    if not raw or not needle:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    results = parsed.get("results") or parsed.get("items") or []
    needle_lower = needle.lower().strip()
    filtered = [
        r for r in results
        if isinstance(r, dict)
        and needle_lower in (r.get("title") or "").lower()
    ]
    if not filtered:
        return None
    out = dict(parsed)
    out["results"] = filtered
    out["total"] = len(filtered)
    out["_query_fallback"] = True
    return json.dumps(out, ensure_ascii=False)


async def _topic_pages_with_warmup(
    query: str,
    extra_args: dict[str, Any],
) -> str:
    # Sprint K (rev3) — Forced module reload signature
    """Run search_wlo_topic_pages with a dedicated collections warmup
    AND a global-list fallback when the server's tight query matcher
    fails to find a topic page that actually exists.

    Two empirical quirks of the WLO MCP server:

    1. Session-state: the topic-page index only populates after a
       ``search_wlo_collections`` call with small ``maxResults`` and no
       discipline filter. We run a dedicated warmup before the actual
       call so this state is always in place.

    2. Tight query matcher: ``search_wlo_topic_pages(query="Mathematik")``
       returns "Keine Themenseiten gefunden" even though a topic page
       titled exactly "Mathematik" exists in the unfiltered global list.
       The server seems to search inside topic-page CONTENT but ignores
       the topic-page title for the query match. Fallback: if the
       initial call returned no results, fetch the global list (no
       query) and filter client-side by title-contains-query.

    Tradeoff: 1 extra MCP roundtrip per turn that requests topic pages,
    plus 1 more if the query-fallback triggers. Mitigated by Phase-A3
    tool cache (TTL 300s) — repeat queries hit the cache for free.
    """
    from boerdi.services.mcp.client import call_mcp_tool as _ct
    try:
        # Fire-and-forget warmup — its cards are discarded; only the
        # session-state side effect on the MCP server matters.
        await _ct("search_wlo_collections", {"query": query, "maxResults": 5})
    except Exception:
        logger.debug("collections warmup call failed (best-effort)", exc_info=True)
    primary = await _ct("search_wlo_topic_pages", extra_args)
    if not _is_empty_topic_pages_response(primary):
        return primary
    # Server returned 0 hits for the query — try the global list and
    # filter by title containment. ``maxResults`` is capped at 20 by the
    # server schema; we ask for the full window.
    try:
        global_args: dict[str, Any] = {"maxResults": 20}
        # Preserve the discipline hint if the caller provided one — even
        # with no query, the server narrows by discipline reliably.
        if extra_args.get("discipline"):
            global_args["discipline"] = extra_args["discipline"]
        global_raw = await _ct("search_wlo_topic_pages", global_args)
    except Exception as _e:
        logger.warning("topic_pages global fallback failed: %s", _e)
        return primary
    filtered = _filter_topic_pages_by_title(global_raw, query)
    if filtered:
        logger.info(
            "topic_pages query-fallback: server reported 0 hits for %r, "
            "but global-list contains a title match (returned filtered set)",
            query,
        )
        return filtered
    # Welle E v4+12  (2026-05-27): Wenn auch der Title-Filter nichts
    # findet, geben wir bis zu 5 globale TPs zurück. Begründung: User
    # hat explizit nach Themenseiten gefragt — eine semantisch
    # ähnliche TP (z.B. „Nachhaltigkeit" bei query=Klimawandel) ist
    # besser als „gar keine Themenseite gefunden", weil der Bot
    # konsistent mit dem User-Wunsch antwortet und das Frontend eine
    # Themenseiten-Box rendern kann. Das LLM hat im Card-Pool die
    # vollen Titel und kann im Prosa-Text klarstellen, dass diese TPs
    # nur indirekt passen.
    if not _is_empty_topic_pages_response(global_raw):
        try:
            import json as _json
            parsed = _json.loads(global_raw)
            if isinstance(parsed, dict):
                results = parsed.get("results") or []
                if results:
                    parsed["results"] = results[:5]
                    parsed["total"] = len(parsed["results"])
                    parsed["_global_fallback"] = True
                    logger.info(
                        "topic_pages global-fallback (no title match): "
                        "returning %d TP-cards as suggestions for %r",
                        len(parsed["results"]), query,
                    )
                    return _json.dumps(parsed, ensure_ascii=False)
        except Exception as _e_json:
            logger.debug("global-fallback JSON parse failed: %s", _e_json)
    return primary


async def _resolve_m16_topic_page_view(
    req, classification, winner_id, spec_query, cards, _final_text,
):
    """M16-Resolver (Themenseiten-Inhalt → Swimlane-Boxen), Port aus ALT
    ``chat_topic_pages._resolve_m16_topic_page_view``. Greift nur bei
    ``winner_id == "M16"``; sonst kommen ``cards``/``_final_text`` unverändert
    zurück und ``_topic_page_view`` bleibt None.

    Rückgabe: ``(_topic_page_view, cards, _final_text)`` — bei erfolgreichem M16
    ist ``cards == []`` (normale Boxen unterdrückt) und ``_final_text`` der
    Auszugs-Intro; scheitert das Laden, ``_topic_page_view is None`` + Fallback-Text.

    NEU-Deviationen ggü. ALT: ``winner`` → ``winner_id: str`` (der einzige Zugriff
    war ``winner.id``, matcht die turn_persist-Konvention); der Tracer ist
    projektweit gedroppt (kein ``tracer.start``/``tracer.end``); die Seams zeigen
    auf ``boerdi.services.mcp.{client,parsers}`` + ``boerdi.api.schemas`` statt der
    ALT-Fassaden.
    """
    # ── M16: Themenseiten-Inhalt — Schwimmlinien-Boxen statt normaler Boxen ──
    # Beste Themenseite zum Thema finden → ihre Schwimmlinien-Inhalte holen
    # (Top-3 je Box) → als Swimlane-Boxen anzeigen. Die normalen Sammlungs-/
    # Inhalts-Boxen werden dabei unterdrückt (cards=[]).
    _topic_page_view = None
    if winner_id == "M16":
        try:
            from boerdi.api.schemas import (
                SwimlaneBox as _M16Box,
            )
            from boerdi.api.schemas import (
                TopicPageView as _M16View,
            )
            from boerdi.api.schemas import (
                WloCard as _M16Card,
            )
            from boerdi.services.mcp.parsers import (
                parse_topic_page_swimlanes as _m16_psl,
            )
            from boerdi.services.mcp.parsers import (
                parse_wlo_cards as _m16_pc,
            )
            _m16_thema = str(
                (classification.entities or {}).get("thema")
                or (classification.entities or {}).get("topic")
                or spec_query or req.message or ""
            ).strip()[:120]
            # Themenseite über die zuverlässige Sammlungs-Suche finden. KEIN
            # CE-Gate hier: der Nutzer hat die Themenseite NAMENTLICH genannt —
            # sie soll gefunden werden, auch bei mäßigem CE-Score. Ranking:
            # Titel-Match + Themenseiten-Flag (topic_page_url) zuerst, sonst
            # MCP-Reihenfolge.
            # Seitenkontext-Kurzschluss (T19): steht der Nutzer schon auf einer
            # Themenseite mit bekannter collectionId, die Sammlungs-Suche
            # überspringen und direkt deren Inhalte laden — spart einen MCP-Call
            # und trifft garantiert die richtige Sammlung. Nur bei
            # page_kind=='topic' + collection_id.
            try:
                _m16_pc_ctx = (req.environment.page_context or {}) if req.environment else {}
            except Exception:
                _m16_pc_ctx = {}
            _m16_known_cid = ""
            if str(_m16_pc_ctx.get("page_kind") or "").lower() == "topic":
                _m16_known_cid = (_m16_pc_ctx.get("collection_id") or "").strip()

            if _m16_known_cid:
                _m16_cands = [{"node_id": _m16_known_cid, "title": _m16_thema}]
            else:
                _m16_raw_col = await call_mcp_tool(
                    "search_wlo_collections", {"query": _m16_thema, "maxResults": 8},
                )
                _m16_cards = _m16_pc(_m16_raw_col) or []
                _m16_thl = _m16_thema.lower()

                def _m16_rank(_c: dict) -> int:
                    _t = (_c.get("title") or "").lower()
                    _tm = bool(_m16_thl) and (_m16_thl in _t or _t in _m16_thl)
                    _tp = bool(_c.get("topic_page_url"))
                    return 0 if (_tm and _tp) else (1 if _tp else (2 if _tm else 3))

                _m16_cands = sorted(_m16_cards, key=_m16_rank)
            _m16_fields = _M16Card.model_fields
            # Top-Kandidaten durchprobieren; erste Sammlung mit echter
            # Schwimmlinien-Struktur gewinnt (max. 3 Versuche).
            for _m16_cand in _m16_cands[:3]:
                _cid = _m16_cand.get("node_id")
                if not _cid:
                    continue
                _m16_raw_tc = await call_mcp_tool(
                    "get_topic_page_content",
                    {"collectionId": _cid, "maxPerSwimlane": 3},
                )
                _m16_parsed = _m16_psl(_m16_raw_tc)
                _m16_boxes = []
                for _m16_sl in _m16_parsed.get("swimlanes", []):
                    _m16_cc = _m16_sl.get("cards") or []
                    if not _m16_cc:
                        continue
                    _m16_boxes.append(_M16Box(
                        heading=_m16_sl.get("heading") or "",
                        type=_m16_sl.get("type") or "",
                        has_more=bool(_m16_sl.get("has_more")),
                        cards=[
                            _M16Card(**{k: v for k, v in c.items() if k in _m16_fields})
                            for c in _m16_cc
                        ],
                    ))
                if _m16_boxes:
                    _topic_page_view = _M16View(
                        variant_title=(_m16_cand.get("title")
                                       or _m16_parsed.get("variant_title") or _m16_thema),
                        topic_page_url=(_m16_parsed.get("topic_page_url")
                                        or _m16_cand.get("topic_page_url") or ""),
                        swimlanes=_m16_boxes,
                    )
                    break
        except Exception as _m16_err:
            logger.warning("M16 topic-content resolve failed: %s", _m16_err)
            _topic_page_view = None
        if _topic_page_view is not None:
            cards = []  # normale Boxen unterdrücken — nur Schwimmlinien zeigen
            _final_text = (
                "Hier ein Auszug der Inhalte der Themenseite "
                f"»{_topic_page_view.variant_title}« — gegliedert nach "
                f"{len(_topic_page_view.swimlanes)} Abschnitt(en). Den vollständigen "
                "Stand findest du über den Themenseiten-Link unter den Inhalten."
            )
            logger.info(
                "M16 topic-content: %d Swimlanes für '%s'",
                len(_topic_page_view.swimlanes), _m16_thema,
            )
        else:
            # generate_response wurde für M16 übersprungen → hier MUSS ein
            # Antworttext gesetzt werden, sonst bleibt die Antwort leer.
            _m16_label = str(
                (classification.entities or {}).get("thema")
                or (classification.entities or {}).get("topic")
                or spec_query or ""
            ).strip()
            cards = []
            if _m16_label:
                _final_text = (
                    f"Zur Themenseite »{_m16_label}« konnte ich gerade keine anzeigbaren "
                    "Inhalte laden — sie ist eventuell noch leer oder nicht vollständig "
                    "freigegeben. Magst du es über die normale Suche zum Thema versuchen?"
                )
            else:
                _final_text = (
                    "Ich konnte gerade keine anzeigbaren Themenseiten-Inhalte laden. "
                    "Magst du es über die normale Suche versuchen?"
                )
            logger.info("M16: keine Inhalte -> Fallback-Text gesetzt (label=%r)", _m16_label)
    return _topic_page_view, cards, _final_text
