"""Respond node — Standard-Antwortpfad P16-19 (R4c).

Port of ALT ``chat_turn_answer._produce_answer``: consume the speculative MCP
prefetch (block-cascade / ``search_wlo_all`` envelope-split / extras), pre-fill
the M16-skip variables, then on the standard path run the CE relevance-gate,
hint the MCP client, start the speculative quick-reply task, call
``generate_response`` (with inline error-degrade + card-salvage), and finally
post-process the text (policy disclaimers, medium-risk safety note,
outcome-based confidence + state hint). Reads merge's ``spec_*`` and route's
pattern/policy/fast-path outputs off ``ctx``; writes ``response_text`` /
``wlo_cards_raw`` (raw handoff to the ``turn_assembly`` slice) / ``tools_called``
/ ``debug.outcomes`` / ``debug.confidence`` / ``state_id`` / ``qr_spec_task``.

Deviations over ALT (each documented at its site):

* ``session`` + ``on_token`` are injected params (pg-DI seam; setup precedent).
  ``generate_response`` takes ``session`` as its first positional argument.
* the Studio tracer instrumentation (``tracer.start`` / ``tracer.end``) is
  dropped — telemetry, deferred with the tracer subsystem (assess precedent).
* ``run_in_rerank_pool`` is dropped (V13 — no CPU-bound rerank backend): the
  CE-gate calls ``rerank_gate_envelope`` directly (sync, per-target isolated).
* ``resolve_discipline_labels`` is dropped (No-op stub in NEU; precedent
  direct_actions / lp_fast_path / tool_loop) — the error-salvage path omits it.

Boundary convention (mirrors ALT): ``generate_response`` /
``generate_quick_replies`` / ``parse_wlo_cards`` / ``_qr_default_count`` /
``_spec_qr_response_block`` are top-level imports (tests patch them on THIS
module); ``rerank_gate_envelope`` / ``set_request_hints`` / ``_first_json_object``
/ ``adjust_confidence`` / ``derive_state_hint`` stay lazy function-local (tests
patch them at their source module).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from boerdi.domain.answer_notes import append_answer_notes
from boerdi.domain.quick_reply_policy import _qr_default_count, _spec_qr_response_block
from boerdi.domain.skill_precedence import mit_ladehinweis
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.tasks import _retrieve_task_exception
from boerdi.services.engine_choice import laeuft_ueber_die_schleife
from boerdi.services.generate import generate_response
from boerdi.services.mcp.parsers import parse_wlo_cards
from boerdi.services.quick_replies_llm import generate_quick_replies

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def respond(
    ctx: TurnContext,
    session: AsyncSession,
    on_token: Any = None,
    progress: TurnProgress = NO_PROGRESS,
    engine: str = "pattern",
) -> TurnContext:
    """Erzeuge die Antwort (Standard-Pfad P16-19). Mutiert ``ctx`` in-place und
    gibt ihn zurück. ``session`` (pg-DI) reicht nur ``generate_response`` an die
    DB durch; ``on_token`` ist der Streaming-Hook (POST /api/chat/stream).

    ``engine`` (A4c-2b) ist die Maschine dieses Zuges. Im Agent-Modus antwortet
    ``respond_agent``, und zwar **vor** allem anderen: der Rumpf unten ist der
    Bestandsweg und bleibt unangetastet. Der Vorabruf aus ``merge`` wird dort
    verworfen, nicht hier — sonst stünde Agent-Wissen im Bestandspfad."""
    if not laeuft_ueber_die_schleife(engine) and ctx.req.environment.result_schema:
        # Ein Ergebnis-Schema wirkt NUR in der Agent-Schleife, und die Vorgabe
        # der Anlage ist ``pattern``. Ohne diese Zeile bekäme ein Gastgeber, der
        # das Attribut setzt und die Maschine vergisst, stumm nie ein Ergebnis
        # — und suchte den Fehler bei sich. Warnen statt abweisen: der Zug ist
        # in Ordnung, nur die Erwartung nicht.
        logger.warning(
            "result_schema wurde erklärt, aber diese Anfrage läuft mit der "
            "Maschine %r — es bleibt wirkungslos. Kopfzeile X-Boerdi-Engine auf "
            "'agent' oder 'hybrid' setzen oder 01-base/engine umstellen.",
            engine)
    if laeuft_ueber_die_schleife(engine):
        # ``session`` reicht nur die Wissensdatenbank durch (P) — dieselbe
        # pg-DI-Naht, die der Bestandsweg an ``generate_response`` gibt.
        return await respond_agent(ctx, progress=progress, engine=engine,
                                   session=session)

    req = ctx.req
    history = ctx.history
    session_state = ctx.session_state
    env = ctx.env
    usage_acc = ctx.usage
    safety = ctx.safety
    classification = ctx.classification
    classification_dict = classification.model_dump()
    policy = ctx.policy
    pattern_output = ctx.pattern_output
    available_rag_areas = ctx.available_rag_areas
    rag_config = ctx.rag_config
    memory_context = ctx.memory_context
    spec_task = ctx.spec_task
    spec_tool_name = ctx.spec_tool_name
    spec_tool_args = ctx.spec_tool_args
    spec_query = ctx.spec_query
    extra_spec_tasks = ctx.extra_spec_tasks
    spec_is_search_all = ctx.spec_is_search_all
    _search_all_extras = list(ctx.search_all_extras)
    _qr_mode = ctx.qr_mode
    _qr_max = ctx.qr_max
    _qr_spec_task = ctx.qr_spec_task
    _lp_routed = ctx.lp_routed
    _canvas_routed = ctx.canvas_routed
    _effective_pattern_id = ctx.effective_pattern_id
    tools_called = ctx.tools_called
    new_state = ctx.state_id
    # Fast-Path-Werte kommen als Eingang herein (None, wenn keine LP-/Canvas-
    # Route lief); auf Standard-/M16-Pfad hier garantiert rebound.
    response_text = ctx.fp_response_text
    wlo_cards_raw = ctx.fp_wlo_cards_raw

    response_outcomes: list = []

    # ── Resolve speculative tool task (if any) ──────────────────────
    # Hat Safety/Policy das spekulierte Tool blockiert → canceln + verwerfen.
    # Sonst awaiten + an generate_response durchreichen (LLM spart den eigenen
    # Tool-Round-Trip). Pattern.sources ist autoritativ: ein Pattern, das MCP
    # nicht explizit erlaubt (oder ein leeres tools-Set hat), unterdrückt die
    # Speculative-Suche; ebenso ein fehlender Pflicht-Slot (Degradation).
    prefetched_tool_payload: dict | None = None
    # C9 (ALT ``chat_turn_answer.py:114``): "Durchsuche WLO-Inhalte" steht,
    # solange die spekulative Suche awaitet und die Karten gewählt werden.
    if spec_task is not None and not _lp_routed and not _canvas_routed:
        progress.start("wlo_search", "Durchsuche WLO-Inhalte")
    if spec_task is not None:
        _pat_sources = pattern_output.get("sources")
        _pat_forbids_mcp = _pat_sources is not None and "mcp" not in _pat_sources
        _pat_wants_no_tools = (
            "tools" in pattern_output and not pattern_output["tools"]
        ) and not (_pat_sources and "mcp" in _pat_sources)
        _degradation_blocks = bool(
            pattern_output.get("degradation") and pattern_output.get("missing_slots")
        )
        spec_blocked = (
            spec_tool_name in (safety.blocked_tools or [])
            or _pat_forbids_mcp
            or _pat_wants_no_tools
            or _lp_routed
            or _canvas_routed
            or _degradation_blocks
        )
        if spec_blocked:
            spec_task.cancel()
            try:
                await spec_task
            except (asyncio.CancelledError, Exception):
                pass
            logger.info(
                "speculative %s discarded (blocked by safety/pattern)", spec_tool_name
            )
        else:
            try:
                spec_result_text = await spec_task
                if spec_result_text and spec_is_search_all:
                    # O1: search_wlo_all-Envelope in drei Per-Tool-Payloads splitten
                    # (content/collections/topicPages), damit der bestehende
                    # generate_response/parse_wlo_cards-Pfad sie wie einzelne
                    # Tool-Ergebnisse verarbeitet — kein Downstream-Umbau.
                    from boerdi.services.mcp.parsers import _first_json_object as _fjo
                    _envobj = None
                    try:
                        _envobj = json.loads(spec_result_text)
                    except (ValueError, TypeError):
                        _frag = _fjo(spec_result_text)
                        if _frag:
                            try:
                                _envobj = json.loads(_frag)
                            except (ValueError, TypeError):
                                _envobj = None
                    if isinstance(_envobj, dict) and (
                        "content" in _envobj or "collections" in _envobj
                        or "topicPages" in _envobj
                    ):
                        _cpot = _envobj.get("content")
                        _colpot = _envobj.get("collections")
                        _tpot = _envobj.get("topicPages")
                        if isinstance(_cpot, dict) and _cpot.get("results"):
                            prefetched_tool_payload = {
                                "name": "search_wlo_content",
                                "arguments": {"query": spec_query},
                                "result_text": json.dumps(_cpot, ensure_ascii=False),
                            }
                        if isinstance(_colpot, dict) and _colpot.get("results"):
                            _search_all_extras.append({
                                "name": "search_wlo_collections",
                                "arguments": {"query": spec_query},
                                "result_text": json.dumps(_colpot, ensure_ascii=False),
                            })
                        if isinstance(_tpot, dict) and _tpot.get("results"):
                            _search_all_extras.append({
                                "name": "search_wlo_topic_pages",
                                "arguments": {"query": spec_query},
                                "result_text": json.dumps(_tpot, ensure_ascii=False),
                            })
                        logger.info(
                            "speculative search_wlo_all split → "
                            "content=%s collections=%s topicPages=%s",
                            len((_cpot or {}).get("results") or [])
                            if isinstance(_cpot, dict) else 0,
                            len((_colpot or {}).get("results") or [])
                            if isinstance(_colpot, dict) else 0,
                            len((_tpot or {}).get("results") or [])
                            if isinstance(_tpot, dict) else 0,
                        )
                    else:
                        # Kein erkennbares Envelope → als content durchreichen.
                        prefetched_tool_payload = {
                            "name": "search_wlo_content",
                            "arguments": spec_tool_args,
                            "result_text": spec_result_text,
                        }
                elif spec_result_text:
                    prefetched_tool_payload = {
                        "name": spec_tool_name,
                        "arguments": spec_tool_args,
                        "result_text": spec_result_text,
                    }
            except Exception as _e:
                logger.warning("speculative %s failed: %s", spec_tool_name, _e)

    # Extras: auf LP-/Canvas-Routen nie konsumiert → explizit canceln
    # (symmetrisch zu spec_task), sonst laufen sie unbeobachtet weiter.
    if extra_spec_tasks and (_lp_routed or _canvas_routed):
        for _ex_name, _ex_task in extra_spec_tasks:
            _ex_task.cancel()
            try:
                await _ex_task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info(
            "speculative extras discarded (lp/canvas route): %d", len(extra_spec_tasks)
        )
        extra_spec_tasks = []

    # Extras (Themenseiten/Inhalte) awaiten + durchreichen: der LLM sieht den
    # Gesamt-Treffer-Pool und wählt IDs, ohne selbst ein zweites Such-Tool zu
    # rufen. Bei search_wlo_all sind sie bereits aus dem Envelope gesplittet.
    prefetched_extras_payload: list[dict] = list(_search_all_extras)
    if extra_spec_tasks and not _lp_routed and not _canvas_routed:
        for _ex_name, _ex_task in extra_spec_tasks:
            if _ex_name in (safety.blocked_tools or []):
                _ex_task.cancel()
                try:
                    await _ex_task
                except (asyncio.CancelledError, Exception):
                    pass
                continue
            try:
                _ex_text = await _ex_task
                if _ex_text:
                    prefetched_extras_payload.append({
                        "name": _ex_name,
                        "arguments": {"query": spec_query, "maxResults": 5},
                        "result_text": _ex_text,
                    })
            except Exception as _ex_err:
                logger.warning("speculative extra %s failed: %s", _ex_name, _ex_err)
        extra_spec_tasks = []
        if prefetched_extras_payload:
            logger.info(
                "speculative extras pre-injected: %s",
                [p["name"] for p in prefetched_extras_payload],
            )

    # Bedarfssteuerung M16: die generische Antwort-LLM-Runde wäre verworfene
    # Arbeit — M16 baut Text + Schwimmlinien-Boxen im Assembly-Slice selbst.
    if ctx.winner_id == "M16":
        response_text = ""
        wlo_cards_raw = []
        tools_called = ["search_wlo_collections", "get_topic_page_content"]
        response_outcomes = []

    if not _lp_routed and not _canvas_routed and ctx.winner_id != "M16":
        # ── CE-Auswahl + Relevanz-Gate (ersetzt select_top_cards) ──────
        # Prefetch-Payloads per Cross-Encoder auf die angezeigten Top-N kürzen +
        # off-topic gaten, BEVOR sie ans Antwort-LLM gehen. Sequenziell und pro
        # Target isoliert (ein fehlgeschlagener Rerank lässt nur DIESES Target
        # ungegatet).
        #
        # **W7 (2026-08-09): wieder im gedeckelten Rerank-Pool.** Hier stand
        # „V13: kein CPU-Rerank-Pool mehr — das Gate ist synchron und
        # deterministisch". Das stimmte, solange hinter dem Seam nichts hing.
        # Mit echtem ONNX kostet ein Gate 0,2–0,5 s CPU (gemessen: 25
        # Kartenzeilen = 507 ms bei intra_op=1) — direkt im Event-Loop steht
        # in dieser Zeit der ganze Worker, samt der SSE-Ströme aller anderen
        # Nutzer. „Synchron" sagt etwas über Determinismus, nichts über den
        # Ausführungsort.
        try:
            from functools import partial as _partial

            from boerdi.services.card_reranker import rerank_gate_envelope as _ce_gate
            from boerdi.services.rag.rerank import run_in_rerank_pool as _rerank_pool
            _ce_targets: list[dict] = []
            if prefetched_tool_payload and prefetched_tool_payload.get("result_text"):
                _ce_targets.append(prefetched_tool_payload)
            _ce_targets.extend(
                p for p in prefetched_extras_payload if p.get("result_text")
            )
            # Soft-Fallback (Themenseiten nicht hart auf 0 gaten) NUR wenn der
            # User explizit Themenseiten browsen will.
            _wants_tp = "themenseite" in (
                (req.message or "") + " " + (spec_query or "")
            ).lower()
            for _p in _ce_targets:
                try:
                    # `partial`, weil der Executor nur positionale Argumente
                    # durchreicht (ALT-Muster, dort mit derselben Begründung).
                    _nt, _ = await _rerank_pool(_partial(
                        _ce_gate,
                        spec_query, _p["result_text"],
                        tool_name=_p.get("name", ""), allow_soft_fallback=_wants_tp,
                    ))
                    _p["result_text"] = _nt
                except Exception as _ge:
                    logger.warning(
                        "CE card-gate failed for %s: %s", _p.get("name", ""), _ge
                    )
        except Exception as _ce_err:
            logger.warning("CE card-gate failed: %s", _ce_err)

        # MCP-Client die Classifier-Entities dieses Turns mitgeben (fach, thema,
        # …); Tool-Preprocessors self-korrigieren damit LLM-Argumente.
        # Underscore-Keys (Page-Metadaten-Cache) fallen raus.
        try:
            from boerdi.services.mcp.arg_resolvers import (
                set_request_hints as _set_request_hints,
            )
            _entities = classification_dict.get("entities", {}) or {}
            _set_request_hints({
                k: v for k, v in _entities.items() if not str(k).startswith("_")
            })
        except Exception:
            logger.debug("set_request_hints failed", exc_info=True)

        # QR-Policy speculative: QR-Generator PARALLEL zum Antwort-LLM starten.
        # Er kennt Pattern/Entities/CE-gegatete Treffer — nicht den Antworttext.
        # Der Konsistenz-/Fallback-Check folgt im Assembly-Slice.
        _qr_count_eff = _qr_max if _qr_max is not None else _qr_default_count()
        if _qr_mode == "speculative" and _qr_spec_task is None and _qr_count_eff > 0:
            try:
                _spec_titles: list[str] = []
                _spec_payloads = (
                    [prefetched_tool_payload] if prefetched_tool_payload else []
                ) + list(prefetched_extras_payload or [])
                for _p in _spec_payloads:
                    if len(_spec_titles) >= 5:
                        break
                    if _p and _p.get("result_text"):
                        for _c in parse_wlo_cards(_p["result_text"]):
                            _t = (_c.get("title") or "").strip()
                            if _t and _t not in _spec_titles:
                                _spec_titles.append(_t)
                            if len(_spec_titles) >= 5:
                                break
                _qr_spec_task = asyncio.create_task(generate_quick_replies(
                    message=req.message,
                    response_text=_spec_qr_response_block(
                        _effective_pattern_id,
                        pattern_output.get("short_purpose") or "",
                        _spec_titles,
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
                    count=_qr_count_eff,
                    lang=resolve_locale(req.environment.locale),
                ))
                # Same guard every other fire-and-forget task carries (see
                # ``services/prefetch.py``): if the turn errors before
                # ``assemble`` consumes this task, its exception is retrieved
                # here instead of surfacing as a stray "Task exception was never
                # retrieved" (audit 2026-08-12).
                _qr_spec_task.add_done_callback(_retrieve_task_exception)
            except Exception as _sqr_err:
                logger.warning("speculative QR start failed: %s", _sqr_err)
                _qr_spec_task = None

        progress.start("response", "LLM response generation")
        try:
            (
                response_text, wlo_cards_raw, tools_called, response_outcomes
            ) = await generate_response(
                session,
                message=req.message,
                history=history,
                classification=classification_dict,
                pattern_output=pattern_output,
                pattern_label=ctx.winner_label,
                session_state=session_state,
                environment=env,
                rag_context=memory_context,  # Only memory, no blind RAG injection
                available_rag_areas=available_rag_areas,
                rag_config=rag_config,
                blocked_tools=safety.blocked_tools,
                prefetched_tool=prefetched_tool_payload,
                prefetched_extras=prefetched_extras_payload,
                canvas_state=req.canvas_state,
                usage_acc=usage_acc,
                on_token=on_token,
            )
        except Exception as _gen_err:
            # Der Antwort-LLM-Call ist die größte Quelle intermittierender Fehler
            # (Rate-Limit, Netz, JSON). Ohne Guard wird jeder Blip ein 500 →
            # Frontend schluckt es als generisches "etwas ist schiefgelaufen".
            # Stattdessen freundlich degradieren + spekulativ-geholte Karten
            # behalten, damit der User noch etwas Nützliches sieht.
            logger.error("generate_response failed: %s", _gen_err)
            response_text = (
                "Ich konnte gerade keine Antwort erzeugen "
                f"({type(_gen_err).__name__}). Versuch es nochmal — meistens "
                "klappt es beim zweiten Anlauf."
            )
            wlo_cards_raw = []
            tools_called = ["error"]
            response_outcomes = []
            if prefetched_tool_payload and prefetched_tool_payload.get("result_text"):
                try:
                    wlo_cards_raw = parse_wlo_cards(
                        prefetched_tool_payload["result_text"]
                    )
                    # NEU-Deviation: resolve_discipline_labels ist in NEU ein
                    # No-op-Stub (Präzedenz direct_actions/lp_fast_path/tool_loop)
                    # — ALT rief hier ``await resolve_discipline_labels(...)``.
                except Exception as _spec_parse_err:
                    logger.warning(
                        "could not salvage spec cards in error path: %s",
                        _spec_parse_err,
                    )

        # Aussetzer des Anbieters, der auch die Wiederholungen im Tool-Loop
        # überlebt hat (``llm.LEERLAUF_VERSUCHE``): kein Fehler, nur eine
        # leere Antwort. Der Guard oben fängt ausschließlich **Exceptions** —
        # ein leerer Text lief bis hier unbemerkt durch bis in die leere
        # Blase, und ein stiller Ausfall ist der schlechtere von beiden.
        #
        # Absichtlich INNERHALB dieses Zweigs: M16 setzt ``response_text``
        # weiter oben mit voller Absicht auf "" (den Text baut das Assembly),
        # und ein gerouteter Schnellweg bringt seinen eigenen mit. Beide
        # dürfen diesen Satz nie sehen.
        #
        # Derselbe Satz wie im Agent-Modus (``agent.failed``) — es ist
        # derselbe Ausfall, und zwei Formulierungen dafür wären zwei Wahrheiten.
        if not (response_text or "").strip():
            logger.warning(
                "Muster-Weg: Antwort ohne Text (Muster %s) — ehrlicher Ersatzsatz",
                ctx.winner_id)
            response_text = bot_text(
                resolve_locale(req.environment.locale), "agent.failed")

    # Policy-Disclaimer + Medium-Risk-Notiz (seit A4c-2b in ``domain/answer_notes``,
    # weil der Agent-Modus denselben Text zu verantworten hat).
    response_text = append_answer_notes(response_text, policy=policy, safety=safety)
    # Hartcodierte Ansage, wenn dieser Zug eine Anleitung geladen hat
    # (Nutzer-Vorgabe 2026-08-16). Sie steht VOR den Hinweisen oben, weil
    # sie ansagt, was gleich kommt — und nach ihnen berechnet, weil sie
    # dem fertigen Text vorangestellt wird.
    response_text = mit_ladehinweis(
        response_text,
        (session_state or {}).get("entities"),
        (session_state or {}).get("turn_count"),
    )

    # Triple-Schema T-25/27: Confidence + State-Hint aus den Tool-Outcomes.
    from boerdi.services.outcome_service import adjust_confidence, derive_state_hint
    final_confidence = adjust_confidence(
        classification.intent_confidence, response_outcomes
    )
    state_hint = derive_state_hint(response_outcomes)
    if state_hint and state_hint != new_state:
        logger.info("Outcome-based state hint: %s -> %s", new_state, state_hint)
        new_state = state_hint

    # ── Ergebnisse zurück in den TurnContext ───────────────────────
    ctx.response_text = response_text
    ctx.wlo_cards_raw = wlo_cards_raw
    ctx.tools_called = tools_called
    ctx.debug.outcomes = response_outcomes
    ctx.state_id = new_state
    ctx.debug.confidence = final_confidence
    ctx.qr_spec_task = _qr_spec_task
    return ctx
