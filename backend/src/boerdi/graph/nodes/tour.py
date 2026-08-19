"""Tour node — deterministic website-tour state machine (P4-2c, R2).

Port of ALT ``chat_tour.py::_handle_tour``. Runs BEFORE classify/pattern/LLM
(and before the page_context MCP resolve — saves latency on ticks). Handles:
  * ``environment.tour_action == 'start'`` → begin the tour (button click),
  * ``'tick'`` + an active tour → arrival-advance / explore / nudge,
  * a normal message in the ``group`` step → group reply,
  * a trigger phrase in a normal message → typed start.

It builds the answer entirely from ``01-base/website-tour.yaml`` (texts, URLs) +
``__guide__`` nav quick-replies via the pure ``domain/tour`` core, persists
``tour_state`` and sets ``ctx.early_response``. Leaves it None when not
responsible (or when the tour ends) so the regular flow takes over.

Die Sprache des Zuges wird hier EINMAL auf die Config angewandt
(``domain/tour_i18n.localize``, C1-g2d), bevor die Zustandsmaschine sie sieht —
die Begründung für diesen Schnitt steht dort.

DI (Regel 3): ``session`` is injected — the graph-build (P4-6) binds the request
session, like ``assess``/``preflight``. NEU deviations over ALT: ``tour_state`` is
a native jsonb dict (the ``sessions.tour_state`` column is jsonb), so ALT's
``json.loads``/``json.dumps`` wrappers are dropped; ``tour_action``/``page`` are
read from the typed ``req.environment`` (ALT read a flattened ``env`` dict). Tests
patch the config load + the two DB writes on THIS module; ``domain/tour`` runs
for real.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.domain import tour as tour_domain
from boerdi.domain.tour_i18n import localize as localize_tour
from boerdi.graph.state import TurnContext
from boerdi.i18n import resolve_locale
from boerdi.services.config_loader import load_website_tour_config
from boerdi.services.db_sessions import save_message, update_session

logger = logging.getLogger(__name__)


async def tour(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Drive the website tour; set ``ctx.early_response`` on a tour turn, else None."""
    req = ctx.req
    env = req.environment
    action = (env.tour_action or "").strip().lower()

    state = ctx.session_state.get("tour_state") or {}
    if not isinstance(state, dict):
        state = {}
    active = bool(state.get("active"))
    step = state.get("step") or ""
    group_id = state.get("group") or ""

    # Stale tick: the frontend flag is still set but the tour is server-side
    # over. Empty answer + tour.active=false → the frontend clears its flag.
    if action == "tick" and not active:
        ctx.early_response = ChatResponse(
            session_id=req.session_id,
            content="",
            follow_up="none",
            debug=DebugInfo(pattern="TOUR:inactive", tools_called=["website_tour"]),
            tour={"active": False, "step": "", "group": ""},
        )
        return ctx

    is_group_reply = active and step == "group" and action == ""

    # Getippter Auslöser aus website-tour.yaml. OHNE laufende Tour startet er
    # sie wie der Knopf; MIT laufender bestätigt er den aktuellen Schritt und
    # zeigt ihn erneut. Der zweite Fall fehlte bis 2026-08-19: geprüft wurde nur
    # bei ``not active``, danach griff der weiche Ausstieg unten — und ausgerechnet
    # der Satz, der die Tour meint („Ja, starte die Tour"), beendete sie. Live in
    # BEIDEN Maschinen gemessen; der Zug landete im gewöhnlichen Chat, der die
    # Tour dann aus dem Gedächtnis nacherzählte statt sie zu fahren.
    # Der ``group``-Schritt bleibt ausgenommen: dort entscheidet das
    # Gruppen-Matching samt Fehlversuch-Zähler, und eine Wiederholung nähme ihm
    # seine eigene Mechanik ab.
    wiederholen = False
    if action == "" and not is_group_reply:
        try:
            cfg_t = load_website_tour_config()
            if cfg_t.get("enabled", True) and tour_domain.ist_ausloeser(req.message, cfg_t):
                if active:
                    wiederholen = True
                else:
                    action = "start"
        except Exception:
            logger.debug("website-tour trigger check failed", exc_info=True)

    handle = (
        (action == "start") or (action == "tick" and active)
        or is_group_reply or wiederholen
    )
    if not handle:
        # Normal message. If a tour sits in a nav-wait step, softly end it (no
        # hijack of the normal chat) and fall through.
        if active and action == "":
            state["active"] = False
            await update_session(session, req.session_id, tour_state=state)
        return ctx

    cfg = load_website_tour_config()
    if not cfg.get("enabled", True):
        return ctx
    # Sprache des Zuges EINMAL auflösen, statt sie durch die ~15 Lesestellen der
    # Zustandsmaschine zu fädeln (C1-g2d). Pfade und IDs bleiben unberührt, das
    # Gruppen-Matching sieht danach die englische Beschriftung.
    cfg = localize_tour(cfg, resolve_locale(env.locale))

    persist_user = False
    persist_assistant = True
    kind = "normal"

    if action == "start":
        persist_user = True
        # Entry-point detection (flow model B1/C1/D1/D2): the tour starts mid-
        # funnel depending on the current page instead of always on /home/.
        step, group_id = tour_domain.detect_entry(env.page or "/", cfg)
        state = {"active": True, "step": step, "group": group_id, "misses": 0}
        if step == "solutions":
            kind = "entry"

    elif wiederholen:
        # Schritt, Gruppe und Zustand bleiben, wie sie sind — nur die Nachricht
        # wird festgehalten. Bewusst KEIN „nudge": der Mensch hat nichts falsch
        # gemacht, er hat die Tour bestätigt.
        persist_user = True

    elif action == "tick":
        if step == "group":
            # Page-load on /home/ during group → re-show the group QRs.
            persist_assistant = False
        else:
            adv, expl, nxt = tour_domain.expected(step, group_id, cfg)
            page = tour_domain._norm_path(env.page or "/")
            if adv and nxt and page == adv:
                step = nxt
                state["step"] = step
                persist_assistant = True
            elif page in expl:
                kind = "explore"
                persist_assistant = False
            else:
                kind = "nudge"
                persist_assistant = False

    else:  # group reply (normal message in the group step)
        persist_user = True
        matched = tour_domain.match_group(req.message, cfg)
        if matched is not None:
            group_id = matched.get("id", "")
            step = "group_page"
            state["group"] = group_id
            state["step"] = step
            state["misses"] = 0
        else:
            misses = int(state.get("misses", 0)) + 1
            state["misses"] = misses
            if misses >= 2:
                # Twice no group recognised → end the tour, continue normally.
                # Do NOT persist the user message here (the normal flow does).
                state["active"] = False
                await update_session(session, req.session_id, tour_state=state)
                return ctx
            kind = "unsure"  # step stays "group"

    # Final step → end the tour.
    if step == "contact":
        state["active"] = False

    rendered = tour_domain.render(step, cfg, group_id, kind=kind)

    await update_session(session, req.session_id, tour_state=state)
    if persist_user:
        try:
            await save_message(session, req.session_id, "user", req.message)
        except Exception:
            logger.debug("tour: persisting user message failed", exc_info=True)
    if persist_assistant and (rendered.get("text") or "").strip():
        try:
            await save_message(
                session, req.session_id, "assistant", rendered["text"],
                debug={"pattern": f"TOUR:{step}"},
            )
        except Exception:
            logger.debug("tour: persisting assistant message failed", exc_info=True)

    ctx.early_response = ChatResponse(
        session_id=req.session_id,
        content=rendered["text"],
        quick_replies=rendered["quick_replies"],
        follow_up="none",
        debug=DebugInfo(pattern=f"TOUR:{step}", tools_called=["website_tour"]),
        tour={"active": bool(state.get("active")), "step": step, "group": group_id},
    )
    return ctx
