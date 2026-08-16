"""Direct-action handlers (P5-6, port of ALT ``app/routers/chat_direct_actions.py``).

The three actions the widget triggers by chip — ``req.action`` ∈
{``browse_collection``, ``generate_learning_path``, ``curate_collection``} — skip
the pattern engine / ``generate_response`` entirely and build a full
:class:`ChatResponse` directly (the preflight node sets it as
``TurnContext.early_response``). ``_direct_action_safety_text`` feeds the raw
user fields through the same safety gate the regular path uses; the R2 preflight
node calls it before dispatching here.

DI-**rewrite** of ALT (not a verbatim port — the storage/label boundaries move):

* ``session: AsyncSession`` is injected as the first argument and threaded to
  ``save_message``/``update_session`` (spec rule 3: no module-global DB).
* ``update_session`` receives ``entities`` as a native dict — the NEU
  ``sessions.entities`` column is ``jsonb``, so ALT's ``json.dumps`` wrapper is
  dropped (same rule as R3a's ``messages.cards``/``debug``).
* the ALT ``await resolve_discipline_labels(...)`` calls are dropped — an ALT
  no-op stub (MCP v2 emits clean labels server-side). Precedent: ``lp_fast_path``
  dropped its five copies.
* ALT's ``_display_rules()`` wrapper becomes ``load_display_rules_config() or {}``
  — the wrapper was only that plus a defensive fallback the surrounding
  try/except already covers. Precedent: ``domain/quick_reply_policy``.
* ``PAGE_SIZE`` is imported from ``domain/cards/build`` (its canonical home)
  instead of being redefined.

Every other helper keeps its ALT name, imported from the canonical NEU home, so
the handler bodies read the same as ALT. Tests patch the MCP/LLM/QR/persistence
boundaries on THIS module (ALT convention).

**simplify (bewusste Ausnahme):** drei kohäsive Handler + ihre gemeinsamen
Helfer, deutlich über dem ~300-Zeilen-Schwellwert — ALT
``chat_direct_actions.py`` hatte 519 Z., ein Dispatch-Ziel (der
R2-preflight-Node). Bewusst als eine Datei gehalten (ALT-Parität +
Sibling-Präzedenz ``lp_fast_path`` / ``canvas_fast_path``, beide ähnlich groß).

Bindend ist dabei nicht die Datei, sondern ``_handle_generate_learning_path``
(gemessen 2026-08-16: 253 Zeilen, 37 Zweige): ein Schnitt in drei Dateien
ließe diese Funktion unberührt — Schwellwert erfüllt, nichts gewonnen.

**Auslöser für den Schnitt** in ein ``direct_actions/``-Paket
(browse/curate/learning_path je Datei): Datei über 700 Zeilen **oder** eine
Funktion über 300. Beides prüft ``test_der_simplify_vermerk_wird_eingehalten``
— hier steht bewusst keine aktuelle Zeilenzahl mehr: bis 2026-08-16 stand hier
„~510", während die Datei bei 593 lag. Eine Datei, die ihre eigene Länge im
Präsens behauptet, wird bei jedem Edit ein Stück unwahrer; ein Test wird es
nicht.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, PaginationInfo
from boerdi.domain.cards.build import PAGE_SIZE, _build_cards
from boerdi.domain.cards.lp_diversity import (
    _add_used_lp_ids,
    _filter_cards_used_in_text,
    _filter_unused_cards,
    _get_used_lp_ids,
)
from boerdi.domain.completion_messages import _lp_completion_message
from boerdi.domain.inline_rendering import _build_inline_document
from boerdi.domain.quick_reply_policy import _qr_default_count, _qr_policy
from boerdi.domain.url_helpers import _extract_web_links_from_text
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.services.config_loader import load_context_actions, load_display_rules_config
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.guide_markers import _attach_guide_qr, _attach_guide_urls
from boerdi.services.llm_curation import generate_curation_text
from boerdi.services.llm_learning_path import generate_learning_path_text
from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.mcp.parsers import parse_total_count, parse_wlo_cards
from boerdi.services.quick_replies_llm import generate_quick_replies

logger = logging.getLogger(__name__)


def _direct_action_safety_text(req: ChatRequest) -> str:
    """Concatenate user-controlled fields from ``req`` for safety screening.

    Direct-action requests skip the regular pattern engine, so they would
    otherwise bypass the safety gate. We feed the raw user message plus all
    string-valued ``action_params`` into the same regex/LLM safety pipeline.
    Caps each field at 500 chars, total 2000.
    """
    chunks: list[str] = []
    if req.message:
        chunks.append(req.message[:500])
    for k, v in (req.action_params or {}).items():
        if isinstance(v, str) and v.strip():
            chunks.append(f"{k}: {v[:500]}")
        if sum(len(c) for c in chunks) >= 2000:
            break
    return " \n".join(chunks)[:2000]


# ── Action: Browse collection contents ────────────────────────────
async def _handle_browse_collection(
    session: AsyncSession, req: ChatRequest, session_state: dict,
    usage_acc: dict[str, Any] | None = None,
) -> ChatResponse:
    """Directly call ``get_collection_contents`` and page its items into the canvas.

    ``usage_acc`` (K1b): browsing itself costs no tokens, but the quick-reply
    generator below is a real LLM call. It was in no measurement list — those
    counted modules with their own generator and missed the shared one.
    """
    collection_id = req.action_params.get("collection_id", "")
    lang = resolve_locale(req.environment.locale)
    title = req.action_params.get("title") or bot_text(lang, "action.collectionFallbackTitle")
    skip_count = req.action_params.get("skip_count", 0)

    if not collection_id:
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "action.missingCollectionId"),
        )

    tools_called = ["get_collection_contents"]
    pagination = None

    try:
        # Fetch PAGE_SIZE + 1 to detect if there are more
        result_text = await call_mcp_tool("get_collection_contents", {
            "nodeId": collection_id,
            "maxItems": PAGE_SIZE + 1,
            "skipCount": skip_count,
        })
        cards_raw = parse_wlo_cards(result_text)
        total_from_mcp = parse_total_count(result_text)

        # Kartentyp vom Server, hier NICHT erzwungen: der Inhalt einer Sammlung
        # darf Unter-Sammlungen enthalten, und die gehören als Sammlung gezeigt
        # (Browse- statt Render-Link). Das bis 2026-08-16 hier stehende
        # ``setdefault("node_type", "content")`` war wirkungslos — hätte es
        # gewirkt, hätte es genau diese Unter-Sammlungen falsch etikettiert.

        # Determine if there are more items
        has_more = len(cards_raw) > PAGE_SIZE
        display_cards_raw = cards_raw[:PAGE_SIZE]
        persona = session_state.get("persona_id", "")
        cards = _build_cards(display_cards_raw, persona)

        # Build pagination info
        total = total_from_mcp if total_from_mcp > 0 else (
            skip_count + len(cards_raw) if has_more else skip_count + len(cards_raw)
        )
        pagination = PaginationInfo(
            total_count=total,
            skip_count=skip_count,
            page_size=PAGE_SIZE,
            has_more=has_more,
            collection_id=collection_id,
            collection_title=title,
        )

        if cards:
            showing = f"{skip_count + 1}–{skip_count + len(cards)}"
            total_label = bot_text(lang, "action.browse.ofTotal", total=total) if total > 0 else ""
            response_text = bot_text(
                lang, "action.browse.header", title=title, range=showing, total=total_label,
            )
        else:
            response_text = bot_text(lang, "action.browse.empty", title=title)

    except Exception as e:
        logger.error("browse_collection error: %s", e)
        cards = []
        response_text = bot_text(lang, "action.browse.loadFailed", title=title, error=e)
        tools_called.append("error")

    # Quick-replies are pure UX sugar — a B-API blip on the QR-LLM call must
    # never crash a successful response, so we degrade to an empty list.
    try:
        quick_replies = await generate_quick_replies(
            message=req.message,
            response_text=response_text,
            classification={
                "persona_id": session_state.get("persona_id", "P-AND"),
                "intent_id": "I03",
                "next_state": "S3",
                "entities": session_state.get("entities", {}),
            },
            session_state=session_state,
            usage_acc=usage_acc,
            count=_qr_default_count() or 2,
            lang=resolve_locale(req.environment.locale),
        )
    except Exception as _qr_err:
        logger.warning("browse_collection quick_replies failed: %s", _qr_err)
        quick_replies = []
    quick_replies = _attach_guide_qr(req, quick_replies, session_state, response_text=response_text)

    debug = DebugInfo(
        persona=session_state.get("persona_id", ""),
        intent="I03",
        state="S3",
        pattern="ACTION: browse_collection",
        tools_called=tools_called,
        entities=session_state.get("entities", {}),
        token_usage=usage_acc or {},
    )

    await save_message(
        session, req.session_id, "assistant", response_text,
        cards=[c.model_dump() for c in cards],
        debug=debug.model_dump(),
    )

    # Canvas integration: route collection contents into the canvas instead of
    # duplicating them in the chat stream. The chat bubble gets a short
    # announcement; the full card grid lives in the canvas card pane.
    _canvas_title = (
        bot_text(lang, "action.browse.canvasTitle", title=title)
        if title
        else bot_text(lang, "action.browse.canvasTitleFallback")
    )
    page_action = {
        "action": "canvas_show_cards",
        "payload": {
            "cards": [c.model_dump() for c in cards],
            "query": title or "",
            "title": _canvas_title,
            "source": "collection",
            "collection_id": collection_id,
            "pagination": pagination.model_dump() if pagination else None,
            # append=true when skip_count>0 -> frontend appends instead of replacing
            "append": skip_count > 0,
        },
    }

    _attach_guide_urls(req, cards, page_action)

    return ChatResponse(
        session_id=req.session_id,
        content=response_text,
        cards=cards,
        quick_replies=quick_replies,
        debug=debug,
        pagination=pagination,
        page_action=page_action,
    )


# ── Action: Curate collection (gap analysis: compendium vs. contents) ──────
def _curate_search_pill(title: str, lang: Locale) -> str:
    """A plain-text pill that starts a search for missing content — routed to
    the normal search flow by the classifier when clicked."""
    t = (title or "").strip()
    return (
        bot_text(lang, "action.curate.searchPill", title=t)
        if t
        else bot_text(lang, "action.curate.searchPillPlain")
    )


async def _handle_curate_collection(
    session: AsyncSession, req: ChatRequest, session_state: dict,
    usage_acc: dict[str, Any] | None = None,
) -> ChatResponse:
    """Compare a collection's compendium (SOLL) against its actual contents (IST)
    and point out gaps + search suggestions.

    Without a compendium there is no reliable "should cover" baseline, so we
    return an honest hint instead of asking the LLM to invent gaps. Does not
    persist (ALT parity) — ``session`` is accepted for a uniform dispatch
    signature but unused here.
    """
    collection_id = req.action_params.get("collection_id", "")
    lang = resolve_locale(req.environment.locale)
    title = req.action_params.get("title") or bot_text(lang, "action.collectionFallbackTitle")

    if not collection_id:
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "action.missingCollectionId"),
        )

    meta = (session_state.get("entities") or {}).get("_page_metadata") or {}
    compendium = (meta.get("compendium_text") or "").strip() if isinstance(meta, dict) else ""

    tools_called = ["get_collection_contents"]
    try:
        result_text = await call_mcp_tool("get_collection_contents", {
            "nodeId": collection_id,
            "maxItems": 100,
            "skipCount": 0,
        })
        # Kartentyp vom Server, nicht erzwungen — Begründung bei
        # ``browse_collection`` (dort stand derselbe tote Schutz).
        cards_raw = parse_wlo_cards(result_text)
    except Exception as e:
        logger.warning("curate_collection contents fetch failed: %s", e)
        cards_raw = []

    # No SOLL → no gap analysis. Be honest instead of hallucinating gaps.
    if not compendium:
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "action.curate.noCompendium", title=title),
            quick_replies=[_curate_search_pill(title, lang)],
            debug=DebugInfo(pattern="ACTION: curate_collection", tools_called=tools_called),
        )

    contents_text = "\n".join(
        f"- {c.get('title', '')}"
        f"{(' — ' + c.get('description', '')[:150]) if c.get('description') else ''}"
        for c in cards_raw
    ) or "(Die Sammlung enthält aktuell keine Inhalte.)"

    tools_called.append("llm_curation")
    instruction = load_context_actions().get("curate_prompt", "")

    response_text = await generate_curation_text(
        collection_title=title,
        compendium=compendium[:4000],
        contents_text=contents_text[:6000],
        instruction=instruction,
        session_state=session_state,
        lang=resolve_locale(req.environment.locale),
        usage_acc=usage_acc,
    )

    return ChatResponse(
        session_id=req.session_id,
        content=response_text,
        quick_replies=[_curate_search_pill(title, lang)],
        debug=DebugInfo(
            pattern="ACTION: curate_collection",
            tools_called=tools_called,
            token_usage=usage_acc or {},
        ),
    )


# ── Action: Generate learning path ───────────────────────────────
async def _handle_generate_learning_path(
    session: AsyncSession, req: ChatRequest, session_state: dict,
    usage_acc: dict[str, Any] | None = None,
) -> ChatResponse:
    """Fetch collection contents, then the LLM structures them into a learning path.

    ``usage_acc`` is the turn's token accumulator (K1b), passed in by the
    preflight node. It must also land in this handler's ``DebugInfo``: a direct
    action ends the turn early, so ``turn_persist`` — the only other place that
    fills ``token_usage`` — never runs on this path.
    """
    collection_id = req.action_params.get("collection_id", "")
    lang = resolve_locale(req.environment.locale)
    title = req.action_params.get("title") or bot_text(lang, "action.collectionFallbackTitle")

    if not collection_id:
        return ChatResponse(
            session_id=req.session_id,
            content=bot_text(lang, "action.missingCollectionId"),
        )

    tools_called = ["get_collection_contents"]
    lp_reset_notice = ""
    # Ob der LP-Schritt gescheitert ist, ist eine Tatsache des Kontrollflusses —
    # nicht etwas, das man dem Antworttext ansieht. Vorher stand hier ein
    # ``startswith`` auf den deutschen Fehlersatz; mit einer zweiten Sprache
    # (C1-f2b) haette der still nicht mehr gegriffen, und ein Fehlschlag waere
    # als Canvas-Dokument gerendert worden.
    lp_failed = False

    try:
        # Step 1: fetch a wide window so we can deduplicate against previously used items.
        result_text = await call_mcp_tool("get_collection_contents", {
            "nodeId": collection_id,
            "maxItems": 24,
            "skipCount": 0,
        })

        # Kartentyp vom Server, nicht erzwungen — Begründung bei
        # ``browse_collection`` (dort stand derselbe tote Schutz).
        cards_raw = parse_wlo_cards(result_text)

        # Diversity: skip items that were already used in earlier learning paths
        used_ids = _get_used_lp_ids(session_state)
        cards_raw, was_reset = _filter_unused_cards(cards_raw, used_ids)
        if was_reset:
            lp_reset_notice = "\n\n" + bot_text(lang, "action.lp.resetNotice")
            session_state.setdefault("entities", {})["_lp_used_node_ids"] = "[]"
        cards_raw = cards_raw[:16]

        if not cards_raw:
            return ChatResponse(
                session_id=req.session_id,
                content=bot_text(lang, "action.lp.noContents", title=title),
                debug=DebugInfo(
                    pattern="ACTION: generate_learning_path",
                    tools_called=tools_called,
                ),
            )

        # Step 2: generate the learning path via LLM — from the filtered subset only.
        tools_called.append("llm_learning_path")
        contents_text = "\n".join(
            f"- **{c.get('title','')}** "
            f"({', '.join(c.get('learning_resource_types', [])) or 'Material'})"
            f"{(' — ' + c.get('description','')[:200]) if c.get('description') else ''}"
            f"{(' URL: ' + c.get('url','')) if c.get('url') else ''}"
            for c in cards_raw
        )
        response_text = await generate_learning_path_text(
            collection_title=title,
            contents_text=contents_text[:6000],
            session_state=session_state,
            lang=resolve_locale(req.environment.locale),
            usage_acc=usage_acc,
        )
        if lp_reset_notice:
            response_text = (response_text or "") + lp_reset_notice

        # Mark node_ids as used so the next LP varies (based on the full
        # candidate pool, not the post-filter subset — otherwise the diversity
        # logic never sees the unused items).
        _add_used_lp_ids(session_state, [c.get("node_id", "") for c in cards_raw])

        # Cards render as a separate "Materialien" box; strip an empty
        # "## 📚 Passende Materialien" heading the generator may emit.
        if response_text:
            response_text = re.sub(
                r"\n*##\s*📚\s*Passende\s*Materialien\s*\n*\Z",
                "",
                response_text,
            ).rstrip()

        # Show only the items the LLM actually referenced in the path.
        cards_raw = _filter_cards_used_in_text(cards_raw, response_text)

        # Keep the "- Material: [Titel](URL)" mentions but replace the markdown
        # link with its label — the URLs already live in the Materialien box, so
        # otherwise links would appear twice. Runs AFTER _filter_cards_used_in_text
        # (which matches primarily on URLs); the extracted web_links are discarded.
        if response_text:
            response_text, _ = _extract_web_links_from_text(
                response_text, cards=cards_raw, keep_bullet_labels=True,
            )

        persona = session_state.get("persona_id", "")
        cards = _build_cards(cards_raw, persona)

        # Box cap like the main path (Studio-Key groups.materialien_max_lernpfad,
        # default 5, clamp 1–8). The central group trim in the main path doesn't
        # run for a direct-action return, so without this the box showed ALL
        # referenced cards. Cards are text-position-sorted → the first N = step order.
        try:
            _lp_grp = (load_display_rules_config() or {}).get("groups") or {}
            _lp_max = max(1, min(8, int(_lp_grp.get("materialien_max_lernpfad") or 5)))
        except Exception:
            _lp_max = 5
        if len(cards) > _lp_max:
            logger.info(
                "direct-action LP: cards trimmed %d → %d (materialien_max_lernpfad)",
                len(cards), _lp_max,
            )
            cards = cards[:_lp_max]

    except Exception as e:
        logger.error("generate_learning_path error: %s", e)
        cards = []
        response_text = bot_text(lang, "action.lp.failed", title=title, error=e)
        lp_failed = True
        tools_called.append("error")

    # Quick replies (best-effort — never block a finished LP on QR). QR-Policy
    # (M09): none ⇒ skip the generator (the guide QR stays as a system function);
    # speculative has no parallel window in the direct-action path ⇒ like exact.
    _lp_qr_mode, _lp_qr_max = _qr_policy("M09")
    _lp_qr_count = _lp_qr_max if _lp_qr_max is not None else _qr_default_count()
    if _lp_qr_mode == "none" or _lp_qr_count <= 0:
        quick_replies = []
    else:
        try:
            quick_replies = await generate_quick_replies(
                message=req.message,
                response_text=response_text,
                classification={
                    "persona_id": session_state.get("persona_id", "P-AND"),
                    "intent_id": "I04",
                    "next_state": "S3",
                    "entities": session_state.get("entities", {}),
                },
                session_state=session_state,
                usage_acc=usage_acc,
                count=_lp_qr_count,
                lang=resolve_locale(req.environment.locale),
            )
        except Exception as _qr_err:
            logger.warning("learning_path quick_replies failed: %s", _qr_err)
            quick_replies = []
    quick_replies = _attach_guide_qr(req, quick_replies, session_state, response_text=response_text)

    debug = DebugInfo(
        persona=session_state.get("persona_id", ""),
        intent="I04",
        state="S3",
        pattern="ACTION: generate_learning_path",
        tools_called=tools_called,
        entities=session_state.get("entities", {}),
        token_usage=usage_acc or {},
    )

    await save_message(
        session, req.session_id, "assistant", response_text,
        cards=[c.model_dump() for c in cards],
        debug=debug.model_dump(),
    )

    # Switch session into canvas-edit mode so follow-up messages can be treated
    # as refinements ("mach ihn fuer Klasse 5 einfacher"). ``entities`` is a
    # native dict — the NEU ``sessions.entities`` column is jsonb (no json.dumps).
    session_state["state_id"] = "S3"
    session_state.setdefault("entities", {})["_canvas_material_type"] = "lernpfad"
    session_state["entities"]["_canvas_topic"] = title or ""
    await update_session(
        session,
        req.session_id,
        state_id="S3",
        entities=session_state.get("entities", {}),
    )

    # If the LP step failed above, response_text is the user-facing error string
    # (no markdown headings) — fall back to a plain chat bubble instead of
    # pretending we built a canvas document.
    if lp_failed:
        _attach_guide_urls(req, cards, None)
        return ChatResponse(
            session_id=req.session_id,
            content=response_text,
            cards=cards,
            quick_replies=quick_replies,
            debug=debug,
        )

    # Kein Merker für den Folgezug — Feststellung, nicht Auslassung
    # (2026-08-15). Bis dahin stand hier ``session_state["last_pattern"] =
    # "M09"`` „for the later M11 iteration". Drei unabhängige Gründe, warum das
    # nie ankam:
    #
    # 1. ``last_pattern`` wurde repo-weit von **niemandem** gelesen. Der
    #    zugüberdauernde Merker heisst ``_last_pattern`` und wohnt in
    #    ``entities`` (``turn_persist``) — ein anderer Schlüssel an einem
    #    anderen Ort.
    # 2. Er lag auf der **obersten Ebene** von ``session_state``. Der
    #    ``update_session``-Aufruf oben schreibt genau ``state_id`` und
    #    ``entities``; alles daneben stirbt mit der Anfrage.
    # 3. Er stand ohnehin **hinter** diesem Aufruf — selbst in ``entities``
    #    wäre er zu spät gekommen.
    #
    # Verloren geht nichts: der Folgezug wählt M11 über den Verlauf. Das
    # Lernpfad-Markdown wird als Assistenten-Nachricht persistiert und steht im
    # Prompt; daran greifen die Trigger-Phrasen von M11 („mach das kürzer").
    # Wer hier doch einen Merker braucht: nach ``entities``, VOR dem
    # ``update_session`` oben — und dann braucht es zuerst einen Leser.
    _attach_guide_urls(req, cards, None)
    short_ack = _lp_completion_message(
        title, response_text or "", canvas_enabled=False, lang=lang)
    inline_content = (response_text or short_ack).strip()

    # Direct-action learning path also rendered as an inline box in chat
    # (consistent with the LP fast-path route through the main path).
    _display_rules_dac = load_display_rules_config() or {}
    _inline_docs_dac: list[dict] = []
    if inline_content and len(inline_content.strip()) >= 200:
        try:
            _docs, _intro = _build_inline_document(
                "M09", inline_content, _display_rules_dac,
                topic=str(title or ""),
                extra_meta={"material_type": "lernpfad"},
                lang=lang,
            )
            if _docs:
                _inline_docs_dac = _docs
                inline_content = _intro or ""
        except Exception as _e:
            logger.warning("direct-action LP inline-document failed: %s", _e)

    return ChatResponse(
        session_id=req.session_id,
        content=inline_content,
        cards=cards,
        quick_replies=quick_replies,
        debug=debug,
        inline_documents=_inline_docs_dac,
        display_rules=_display_rules_dac,
    )
