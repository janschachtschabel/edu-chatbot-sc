"""``route`` — der Routing-Entscheidungs-Knoten (P4-4).

Fasst den Entscheidungs-Kern der ALT-Turn-Phasen zusammen: aus ``chat_turn_setup``
den Persona/Signal/State-Merge + ``validate_transition`` (Telemetrie) +
``assess_policy`` inkl. Merge der Policy-Tool-Sperren in ``safety.blocked_tools``
(ein Enforcement-Pfad); aus dem Kopf von ``chat_turn_routing._route_pattern`` die
``select_pattern``-Auswahl (Enforce > Hint > Fallback), den Blocked-Tools-Strip,
die strenge RAG-Whitelist je Pattern und den Memory-Render.

Der Fast-Path-Tail von ``_route_pattern`` (Z. 196-674) ist verdrahtet: der
LP-Fast-Path (Head-Gate ``detect_lp_intent`` → Body ``run_lp_fast_path``), der
Canvas-Create-Fast-Path (``run_canvas_create_fast_path``, Passthrough bei
``lp_routed``), die Effective-Pattern-Reconciliation
(``reconcile_effective_pattern``) und die QR-Policy (LP-Policy bei ``lp_routed``,
sonst ``_qr_policy`` am effektiven Pattern). Bewusst NOCH VERTAGT: der spekulative
MCP-Prefetch (``_launch_speculative_prefetch`` → der LP-Body bekommt hier
``qr_spec_task=None`` als Eingang), als eigener Slice.

Die Entscheidungs- und Fast-Path-Funktionen sind Top-Level-Importe (Tests patchen
sie an DIESEM Modul); ``load_rag_config`` ist die Read-Fassade. ``async`` aus
Parität mit ALT ``_route_pattern`` und weil die Fast-Paths hier ``await`` brauchen.

Die drei reinen Kopf-Helfer (``_update_persona`` / ``_resolve_rag_areas`` /
``_render_memory_context``) wohnen seit A4c in ``domain/route_head`` — dieser
Knoten war für sie nur der Fundort, nicht der richtige Ort. Sie werden hier
zurückimportiert, damit dieselbe Randkonvention gilt: auflösbar und patchbar AN
DIESEM Modul.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.agent_pattern import agent_pattern
from boerdi.domain.context import build_context
from boerdi.domain.lp_intent import detect_lp_intent
from boerdi.domain.pattern_engine import select_pattern
from boerdi.domain.policy import assess_policy
from boerdi.domain.quick_reply_policy import _qr_policy
from boerdi.domain.route_head import (
    _render_memory_context,
    _resolve_rag_areas,
    _update_persona,
)
from boerdi.domain.route_tail import reconcile_effective_pattern
from boerdi.domain.state_machine import validate_transition
from boerdi.domain.turn_frame import clarification_exhausted, resolve_frame
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.services.canvas_fast_path import (
    CanvasFastPathResult,
    run_canvas_create_fast_path,
)
from boerdi.services.config_loader import load_rag_config
from boerdi.services.lp_fast_path import run_lp_fast_path

logger = logging.getLogger(__name__)


async def route(
    ctx: TurnContext,
    progress: TurnProgress = NO_PROGRESS,
    engine: str = "pattern",
) -> TurnContext:
    """Routing-Entscheidung: merge → validate → policy → select → strip → RAG →
    memory → Fast-Path-Tail (LP-Fast-Path → Canvas-Fast-Path →
    Effective-Pattern-Reconciliation → QR-Policy → fp-Marker). Mutiert ``ctx``
    in-place und gibt ihn zurück.

    ``engine`` (A4c) ist die Maschine dieses Zuges. Im Agent-Modus entfallen die
    Musterwahl und beide Schnellwege; alles andere — Persona-Merge, Policy samt
    Werkzeug-Sperren, RAG-Whitelist, QR-Policy — gilt unverändert."""
    cls = ctx.classification
    safety = ctx.safety
    ss = ctx.session_state

    # 1. Persona (R-06) + Signal-/State-Merge.
    _update_persona(ss, cls)
    new_signals = cls.signals
    signal_history = list(set(ss.get("signal_history", []) + new_signals))
    new_state = cls.next_state

    # 2. Conversation-State-Plausibilität — Telemetrie-only; darf den Turn nie
    #    scheitern lassen (ALT ``chat_turn_setup`` try/except).
    try:
        trans_check = validate_transition(
            prev=ss.get("state_id") or "",
            next_=new_state,
            intent=cls.intent_id,
            auto_correct=False,
        )
    except Exception as exc:  # pragma: no cover — Verteidigung, nie den Turn killen
        trans_check = {
            "validated_state": new_state,
            "plausible": True,
            "reason": f"validator error: {exc}",
            "prev_next_likely": [],
        }

    # 2b. ContextSnapshot (T-04/05) — ALT ``chat_turn_setup`` build_context; wie
    #     ALT OHNE ``memories`` (→ memory_keys bleibt []).
    ctx.context_snapshot = build_context(ctx.env, ss, cls)
    progress.record("context", "Context snapshot built")

    # 3. Policy → Tool-Sperren in safety mergen (ein Enforcement-Pfad).
    progress.start("policy", "Policy evaluation")
    policy = assess_policy(
        message=ctx.req.message,
        persona_id=ss["persona_id"],
        intent_id=cls.intent_id,
        # Der Hinweis wird in `respond` an die Antwort gehängt und ist damit
        # Bot-Ausgabe — er folgt der Sprache des Zuges (C1-g2c).
        lang=resolve_locale(getattr(ctx.req.environment, "locale", None)),
    )
    for t in policy.blocked_tools:
        if t not in safety.blocked_tools:
            safety.blocked_tools.append(t)

    # 3b. Frame-Auflösung (B3) — VOR der Musterwahl, weil sie sonst schon
    #     gefallen ist. Hat der Klärer seine Versuche verbraucht, ohne dass der
    #     Nutzer einen Slot geliefert hat, wird er hier umgeleitet, statt zum
    #     dritten Mal wortgleich zu fragen. Die Safety behält Vorrang: ihre
    #     Erzwingung wird nur ersetzt, wenn es gar keine gibt.
    enforced_pattern_id = safety.enforced_pattern or None
    frame_exhausted = clarification_exhausted(ss.get("entities") or {})
    if not enforced_pattern_id:
        frame_target = resolve_frame(
            ss.get("entities") or {}, getattr(cls, "pattern_id_hint", None)
        )
        if frame_target:
            logger.info(
                "Frame erschoepft: Klaerer nach %s umgeleitet statt erneut zu fragen",
                frame_target,
            )
            enforced_pattern_id = frame_target

    # 4. Pattern-Selektion (Enforce > Hint > Fallback). Im Agent-Modus (A4c)
    #    gibt es nichts zu wählen — der Agent sucht sich sein Werkzeug selbst.
    #    Die Rückgabe-Form bleibt dieselbe, damit alles Nachgelagerte unverändert
    #    weiterläuft (Präzedenz A4b: gleiche Form, anderer Erzeuger).
    if engine == "agent":
        winner, pattern_output, scores, eliminated = agent_pattern(
            signals=new_signals,
            device=ctx.env.get("device", "desktop"),
            entities=ss.get("entities") or {},
            persona_id=ss["persona_id"],
        )
    else:
        progress.start("pattern", "Pattern selection (Safety → Hint → Fallback)")
        winner, pattern_output, scores, eliminated = select_pattern(
            persona_id=ss["persona_id"],
            state_id=new_state,
            intent_id=cls.intent_id,
            signals=new_signals,
            page=ctx.env.get("page", "/"),
            device=ctx.env.get("device", "desktop"),
            entities=ss.get("entities") or {},
            intent_confidence=cls.intent_confidence,
            enforced_pattern_id=enforced_pattern_id,
            pattern_id_hint=getattr(cls, "pattern_id_hint", None),
        )

    # 4b. Safety/Policy: gesperrte Tools aus dem gewählten Pattern entfernen.
    if safety.blocked_tools and "tools" in pattern_output:
        pattern_output["tools"] = [
            t for t in pattern_output["tools"] if t not in safety.blocked_tools
        ]
        logger.info("Safety/Policy blocked tools: %s", safety.blocked_tools)

    # 5. RAG-Whitelist je Pattern + Memory-Render.
    rag_config = load_rag_config()
    available_rag_areas = _resolve_rag_areas(pattern_output, rag_config)
    memory_context = _render_memory_context(ctx.memories)

    # 6. Fast-Path-Tail (ALT ``_route_pattern`` Z. 196-674). Zuerst der
    #    LP-Fast-Path: der Head-Gate ``detect_lp_intent`` bestimmt
    #    ``_has_lp_intent`` + ``_thema`` (und mutiert session_state/
    #    pattern_output in-place: Garbage-thema-Reset + Degradation), dann
    #    sammelt der LP-Body ``run_lp_fast_path`` das Material und generiert
    #    ggf. den Lernpfad. Danach der Canvas-Create-Fast-Path — er weicht bei
    #    ``lp_routed`` als Passthrough zurück (Guard: not lp_routed). Der
    #    spekulative MCP-Prefetch (P5) fehlt noch → der LP-Body bekommt
    #    ``qr_spec_task=None`` als Eingang (startet seinen M09-Spec-Task selbst).
    #    A4c: Beide Schnellwege sind Abkürzungen der Muster-Engine und deshalb
    #    im Agent-Modus aus. Die Sperre hängt an DIESEM Schalter und nicht
    #    daran, dass die Ersatz-Klassifikation zufällig nie I05 sagt — ein
    #    Verhalten, das nur aus einer Eigenschaft eines anderen Knotens folgt,
    #    ist geliehen und nicht zugesichert.
    fast_paths_on = engine != "agent"
    fp_response_local = ""
    fp_cards_local: list[dict[str, Any]] = []
    has_lp_intent, thema = detect_lp_intent(
        classification=cls,
        message=ctx.req.message,
        session_state=ss,
        pattern_output=pattern_output,
    ) if fast_paths_on else (False, "")
    lp = await run_lp_fast_path(
        has_lp_intent=has_lp_intent,
        thema=thema,
        req=ctx.req,
        classification=cls,
        session_state=ss,
        pattern_output=pattern_output,
        usage_acc=ctx.usage,
        new_state=new_state,
        qr_spec_task=None,
    )
    lp_routed = lp.routed
    tools_called = lp.tools_called
    qr_spec_task = lp.qr_spec_task
    if lp_routed:
        fp_response_local = lp.response_text
        fp_cards_local = lp.wlo_cards_raw
        new_state = lp.new_state

    if fast_paths_on:
        cv = await run_canvas_create_fast_path(
            req=ctx.req,
            classification=cls,
            session_state=ss,
            pattern_output=pattern_output,
            memory_context=memory_context,
            lp_routed=lp_routed,
            tools_called=tools_called,
            new_state=new_state,
            frame_exhausted=frame_exhausted,
            usage_acc=ctx.usage,
        )
    else:
        # Der „nicht geroutet"-Vertrag des Schnellwegs: Eingaben durchgereicht.
        cv = CanvasFastPathResult(
            routed=False, payload_out=None, forced_quick_replies=[],
            response_text="", tools_called=tools_called, wlo_cards_raw=[],
            new_state=new_state,
        )
    canvas_routed = cv.routed
    # ALT entpackt ``tools_called`` unbedingt aus dem Fast-Path-Return (5.
    # Tupel-Position); nicht geroutet → der Fast-Path echot den Input zurück.
    tools_called = cv.tools_called
    if canvas_routed:
        fp_response_local = cv.response_text
        fp_cards_local = cv.wlo_cards_raw
        new_state = cv.new_state

    # Effective-Pattern-Reconciliation: ein Fast-Path kann den Engine-Pick
    # überschrieben haben (Quality-Logs / Inline-Document-Box lesen das
    # AUSGEFÜHRTE Pattern, nicht die ursprüngliche Engine-Wahl).
    effective_pattern_id, effective_pattern_label = reconcile_effective_pattern(
        winner, lp_routed, canvas_routed, tools_called,
    )

    # QR-Policy am effektiven Pattern auflösen. Bei ``lp_routed`` hat der
    # LP-Fast-Path sie bereits auf die M09-Policy gesetzt (inkl. evtl.
    # laufendem Spec-Task) und über ``lp.qr_mode``/``lp.qr_max`` geliefert; für
    # den Canvas-/Standardpfad hier via ``_qr_policy``.
    qr_mode: str | None = lp.qr_mode
    qr_max: int | None = lp.qr_max
    if not lp_routed:
        qr_mode, qr_max = _qr_policy(effective_pattern_id)

    # Fast-Path-Marker: nur bei geroutetem Fast-Path gesetzt → sonst nutzt der
    # Respond-Node den Standardpfad (ALT: response_text/wlo_cards_raw bleiben dort
    # ungebunden, die Conditional-Expression wertet den True-Zweig nur bei
    # geroutetem Fast-Path aus).
    fp_routed = lp_routed or canvas_routed
    fp_response_text = fp_response_local if fp_routed else None
    fp_wlo_cards_raw = fp_cards_local if fp_routed else None

    ctx.signals = new_signals
    ctx.signal_history = signal_history
    ctx.state_id = new_state
    ctx.trans_check = trans_check
    ctx.policy = policy
    ctx.winner_id = winner.id
    ctx.winner_label = winner.label
    ctx.pattern_output = pattern_output
    ctx.scores = scores
    ctx.eliminated = eliminated
    ctx.rag_config = rag_config
    ctx.available_rag_areas = available_rag_areas
    ctx.memory_context = memory_context
    ctx.lp_routed = lp_routed
    ctx.canvas_routed = canvas_routed
    ctx.canvas_payload = cv.payload_out
    ctx.canvas_forced_quick_replies = cv.forced_quick_replies
    ctx.tools_called = tools_called
    ctx.effective_pattern_id = effective_pattern_id
    ctx.effective_pattern_label = effective_pattern_label
    ctx.qr_mode = qr_mode
    ctx.qr_max = qr_max
    ctx.qr_spec_task = qr_spec_task
    ctx.fp_response_text = fp_response_text
    ctx.fp_wlo_cards_raw = fp_wlo_cards_raw
    return ctx
