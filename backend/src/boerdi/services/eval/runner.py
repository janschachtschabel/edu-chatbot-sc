"""The generative eval run (port of ALT ``eval_service.simulate_conversation``
+ ``execute_run``).

Two stages, either or both selected by ``mode``:

* **scenarios** — one generated opening per persona x intent combo, fired at the
  live ``/api/chat`` and judged. Single-turn.
* **conversations** — an LLM plays the persona for ``turns_per_conv`` turns
  against the live bot; every non-error turn is judged.

Both stages append to a caller-owned ``conversations`` list. That is deliberate:
a run of 144 combos takes minutes, and when it dies halfway the caller still
holds every finished conversation and can persist it as partial data — which is
exactly what ALT's own except-block does with its local variable.

Persistence is NOT here. The caller passes a ``progress`` coroutine and owns all
DB writes (spec rule 4: DB-touching code lives in the service layer), so this
module stays a pure orchestrator over three seams: ``/api/chat`` over HTTP, the
scenario generator, and the judge.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from boerdi.services.config_loader import get_state_directive, load_persona_definitions
from boerdi.services.eval.judge import judge_turn
from boerdi.services.eval.metrics import _aggregate, _aggregate_classification_metrics
from boerdi.services.eval.prompts import _SIMULATOR_SYSTEM
from boerdi.services.eval.scenario_gen import (
    _build_persona_markers_block,
    generate_scenarios,
    simulator_model,
)
from boerdi.services.llm import chat_completion

logger = logging.getLogger(__name__)

# One chat turn can involve tool calls and a reranker — ALT's 60 s, kept.
_CHAT_TIMEOUT_S = 60.0

# I06 is an edit intent: it only makes sense once material exists. Without a
# priming turn every I06 scenario is an opening with nothing to edit, the engine
# reasonably routes to slot clarification, and the judge (expecting the edit
# pattern) scores 0 every time. ALT Welle E v4.
_I06_PRIMING_MSG = (
    "Erstelle mir bitte ein Arbeitsblatt zur Photosynthese für Klasse 6."
)
# The priming turn's session write is non-blocking w.r.t. its HTTP response, so
# the edit turn can start before ``_canvas_last_markdown`` is stored. ALT found
# this race live (eval-bd3a) and settled it with a fixed wait plus one re-poll.
_PRIMING_SETTLE_S = 0.6
_PRIMING_REPOLL_S = 0.4

Progress = Callable[[list[dict], str], Awaitable[None]]


async def _post_chat(
    chat_url: str, message: str, session_id: str | None = None
) -> dict[str, Any]:
    """Fire one user message at ``/api/chat`` and return the raw response JSON.

    The chat API requires a session; a fresh ``eval-<uuid>`` one is generated for
    single-turn scenarios that do not carry their own.
    """
    if not session_id:
        session_id = f"eval-{uuid.uuid4().hex[:12]}"
    payload: dict[str, Any] = {"session_id": session_id, "message": message}
    async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT_S) as c:
        r = await c.post(chat_url, json=payload)
        r.raise_for_status()
        return r.json()


def _merge_canvas(bot_text: str, bot_resp: dict[str, Any]) -> str:
    """Append canvas markdown to the bot text when the turn opened/updated one.

    The visible chat bubble is only the announcement ("Hier ist dein Material");
    the content itself travels in ``page_action.payload.markdown``. The judge has
    to see what the user actually received, not the announcement.
    """
    page_action = bot_resp.get("page_action") or {}
    if (page_action.get("action") in ("canvas_open", "canvas_update")
            and isinstance(page_action.get("payload"), dict)
            and page_action["payload"].get("markdown")):
        canvas_md = page_action["payload"]["markdown"]
        return (
            f"{bot_text}\n\n"
            f"---\n[Canvas-Inhalt — vom Nutzer sichtbar]\n\n"
            f"{canvas_md}"
        )
    return bot_text


def _augment_bot_text(bot_resp: dict[str, Any]) -> str:
    """Render everything the user saw into one text for the judge.

    Generated material arrives in ``inline_documents[].content`` and search hits
    in ``cards``/``query_metas`` — none of it in the chat bubble. Without this a
    judge reads "no concrete material" while eight cards were on screen.

    Twin note: ``evals/run_golden.py`` carries the same rule as
    ``augment_bot_text``. It cannot be shared, because that file is deliberately
    framework-free (it is a standalone CLI, not an installed package, and must
    not import ``boerdi.*``). ALT has the identical twin for the same reason.
    """
    bot_text = bot_resp.get("content", "") or ""

    md_parts: list[str] = []
    for doc in bot_resp.get("inline_documents") or []:
        if not isinstance(doc, dict):
            continue
        content = (doc.get("content") or "").strip()
        if content:
            title = (doc.get("title") or doc.get("kind") or "").strip()
            md_parts.append(
                "---\n[Inline-Document — vom Nutzer sichtbar"
                + (f": {title}" if title else "") + "]\n\n" + content
            )
    if md_parts:
        bot_text = bot_text.rstrip() + "\n\n" + "\n\n".join(md_parts)

    card_lines: list[str] = []
    for card in (bot_resp.get("cards") or [])[:8]:  # cap for the token budget
        if not isinstance(card, dict):
            continue
        ct = (card.get("title") or "").strip()
        cu = (card.get("url") or card.get("wlo_url") or "").strip()
        cd = (card.get("description") or card.get("abstract") or "").strip()[:200]
        if ct or cu:
            line = f"  - **{ct or '(ohne Titel)'}**"
            if cu:
                line += f" — {cu}"
            if cd:
                line += f"\n    {cd}"
            card_lines.append(line)
    if card_lines:
        # The header counts the cards actually rendered, not len(cards): with the
        # cap in play the judge otherwise read "10 Treffer" under 8 entries.
        bot_text = (
            bot_text.rstrip()
            + "\n\n---\n[Material-Cards — vom Nutzer sichtbar, "
            + f"{len(card_lines)} Treffer]\n"
            + "\n".join(card_lines)
        )

    qm_lines: list[str] = []
    for qm in (bot_resp.get("query_metas") or [])[:5]:
        if not isinstance(qm, dict):
            continue
        qt = (qm.get("title") or qm.get("type") or "").strip()
        qu = (qm.get("url") or "").strip()
        if qt or qu:
            qm_lines.append(f"  - {qt}" + (f" — {qu}" if qu else ""))
    if qm_lines:
        bot_text = (
            bot_text.rstrip()
            + "\n\n---\n[Query-Metas — vom Nutzer sichtbar]\n"
            + "\n".join(qm_lines)
        )

    return _merge_canvas(bot_text, bot_resp)


def _flat_debug(debug: dict[str, Any]) -> dict[str, Any]:
    """The debug fields the metrics aggregator and the judge read."""
    return {
        "pattern": debug.get("pattern"),
        "persona": debug.get("persona"),
        "intent": debug.get("intent"),
        "safety": debug.get("safety"),
        "tools_called": debug.get("tools_called", []),
        # Phase-1 pattern hint — feeds the run-global classification metrics.
        "pattern_id_hint": debug.get("pattern_id_hint"),
        "pattern_reasoning": debug.get("pattern_reasoning"),
        "llm_engine_match": debug.get("llm_engine_match"),
        "token_usage": debug.get("token_usage"),
        # Tie-breaker telemetry travels inside phase3_modulations.
        "phase3_modulations": debug.get("phase3_modulations"),
        "i06_priming": debug.get("i06_priming"),
    }


def _transition_plausible(prev_state: str, state_id: str) -> bool | None:
    """Was this state transition a typical one? ``None`` = not assessable.

    Compares against the previous state's ``next_likely`` list; staying in the
    same state always counts as plausible.
    """
    if not (prev_state and state_id):
        return None
    try:
        prev_meta = get_state_directive(prev_state)
        next_likely = prev_meta.get("next_likely", []) if prev_meta else []
        if next_likely:
            return state_id in next_likely or state_id == prev_state
    except Exception:
        logger.debug("state-transition plausibility check failed", exc_info=True)
    return None


async def simulate_conversation(
    chat_url: str,
    persona: dict,
    intent: dict,
    max_turns: int = 3,
    opening: str | None = None,
) -> dict[str, Any]:
    """Multi-turn dialogue: an LLM-simulated user against the live ``/api/chat``.

    Returns ``{session_id, persona_id, intent_id, turns, ended_early}``. The
    simulator may end the dialogue early by answering ``[ENDE]``.
    """
    session_id = f"eval-{uuid.uuid4().hex[:12]}"
    # The marker block comes from the persona definitions — same source as the
    # classifier and the scenario generator (ALT Welle E).
    markers_block = _build_persona_markers_block(persona, load_persona_definitions())
    system_prompt = _SIMULATOR_SYSTEM.format(
        persona_label=persona.get("label", ""),
        persona_desc=(persona.get("description") or "")[:400],
        intent_label=intent.get("label", ""),
        intent_desc=(intent.get("description") or "")[:400],
        persona_markers_block=markers_block,
    )
    sim_messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    if opening:
        user_msg = opening
    else:
        sim_messages.append({
            "role": "user",
            "content": "Starte die Konversation mit einer realistischen "
                       "Eroeffnungsnachricht.",
        })
        resp = await chat_completion(
            messages=sim_messages, model=simulator_model(),
            temperature=0.8, background=True,
        )
        user_msg = (resp.choices[0].message.content or "").strip()
        sim_messages.pop()  # drop the seed instruction from the history

    turns: list[dict[str, Any]] = []
    ended_early = False
    prev_state = ""

    for turn_idx in range(max_turns):
        if user_msg.strip().upper() == "[ENDE]":
            ended_early = True
            break
        try:
            bot_resp = await _post_chat(chat_url, user_msg, session_id=session_id)
        except Exception as e:
            logger.warning("Chat call failed in turn %d: %s", turn_idx, e)
            turns.append({
                "user": user_msg, "bot": f"(chat error: {e})",
                "debug": {}, "error": str(e),
            })
            break
        bot_text = _merge_canvas(bot_resp.get("content", "") or "", bot_resp)
        debug = bot_resp.get("debug", {}) or {}

        # State strings arrive as "state-X (Label)"; the ID drives the
        # conversation-flow plausibility check.
        state_raw = debug.get("state") or ""
        state_id = state_raw.split(" ")[0] if state_raw else ""
        turns.append({
            "user": user_msg,
            "bot": bot_text,
            "debug": {
                **_flat_debug(debug),
                "state": state_raw,
                "state_id": state_id,
                "prev_state_id": prev_state,
                "transition_plausible": _transition_plausible(prev_state, state_id),
            },
            "cards_count": len(bot_resp.get("cards", []) or []),
            "response_length": len(bot_text),
        })
        if state_id:
            prev_state = state_id

        if turn_idx == max_turns - 1:
            break

        sim_messages.append({"role": "assistant", "content": user_msg})
        sim_messages.append({
            "role": "user",
            "content": f"Der Chatbot hat geantwortet:\n\n{bot_text[:1500]}\n\n"
                       f"Deine naechste Nachricht:",
        })
        try:
            resp = await chat_completion(
                messages=sim_messages, model=simulator_model(),
                temperature=0.7, background=True,
            )
            user_msg = (resp.choices[0].message.content or "").strip()
            # Keep the assistant turn, drop the "bot said: …" scaffolding.
            sim_messages.pop()
        except Exception as e:
            logger.warning("Simulator failed on turn %d: %s", turn_idx, e)
            break

    return {
        "session_id": session_id,
        "persona_id": persona.get("id", ""),
        "intent_id": intent.get("id", ""),
        "turns": turns,
        "ended_early": ended_early,
    }


async def _prime_i06_session(chat_url: str, run_id: str, persona_id: str) -> tuple[
    str | None, dict[str, Any] | None
]:
    """Give an I06 (edit) scenario something to edit. See ``_I06_PRIMING_MSG``.

    Returns ``(session_id, priming_meta)``; ``(None, None)`` when priming failed,
    in which case the scenario runs unprimed and shows I06's raw behaviour.
    """
    session_id = f"eval-{uuid.uuid4().hex[:12]}"
    try:
        resp = await _post_chat(chat_url, _I06_PRIMING_MSG, session_id=session_id)
    except Exception as e:
        logger.warning("[eval %s] I06 priming failed for %s: %s", run_id, persona_id, e)
        return None, None
    meta = {
        "priming_message": _I06_PRIMING_MSG,
        "priming_pattern": (resp.get("debug") or {}).get("pattern"),
        "priming_text_preview": (resp.get("content") or "")[:200],
    }
    await asyncio.sleep(_PRIMING_SETTLE_S)
    # Verify the session really carries the primed state; re-poll once if not.
    try:
        from boerdi.services.db_sessions import get_or_create_session
        state = await get_or_create_session(session_id)
        entities = (state.get("entities") or {}) if state else {}
        if not entities.get("_canvas_last_markdown") and not entities.get("_last_pattern"):
            await asyncio.sleep(_PRIMING_REPOLL_S)
    except Exception:
        # The persistence check is a comfort, never a hard stop.
        logger.debug("[eval %s] I06 priming state check failed", run_id, exc_info=True)
    return session_id, meta


async def _run_scenario_stage(
    *, chat_url: str, run_id: str, conversations: list[dict],
    personas: list[dict], intents: list[dict], scenarios_per_combo: int,
    progress: Progress,
) -> None:
    """Stage 1 — one generated opening per combo, fired once and judged."""
    await progress(conversations, "Generiere Szenarien (0/0) …")

    async def on_combo(idx: int, total: int, pid: str, iid: str) -> None:
        # Throttled to every 4th combo plus the first and last: with 144 combos
        # a write per combo would be 144 writes for a progress label.
        if idx == 1 or idx == total or idx % 4 == 0:
            await progress(
                conversations,
                f"Generiere Szenarien {idx}/{total} ({pid} × {iid}) …",
            )

    scens = await generate_scenarios(
        personas, intents, scenarios_per_combo, progress_cb=on_combo,
    )
    logger.info("[eval %s] generated %d scenarios", run_id, len(scens))

    for idx, sc in enumerate(scens):
        persona = next((p for p in personas if p["id"] == sc["persona_id"]), {})
        intent = next((i for i in intents if i["id"] == sc["intent_id"]), {})
        activity = (
            f"Szenario {idx + 1}/{len(scens)}: {sc['persona_id']} × {sc['intent_id']}"
        )
        use_session_id: str | None = None
        try:
            priming_meta: dict[str, Any] | None = None
            if sc["intent_id"] == "I06":
                use_session_id, priming_meta = await _prime_i06_session(
                    chat_url, run_id, sc.get("persona_id", ""),
                )
            bot_resp = await _post_chat(
                chat_url, sc["opening"], session_id=use_session_id,
            )
            debug = dict(bot_resp.get("debug", {}) or {})
            if priming_meta:
                debug["i06_priming"] = priming_meta
            dbg_flat = _flat_debug(debug)
            bot_text = _augment_bot_text(bot_resp)
            judge = await judge_turn(
                persona, intent, sc["opening"], bot_text, dbg_flat,
            )
        except Exception as e:
            logger.warning("[eval %s] scenario failed: %s", run_id, e)
            bot_text, dbg_flat = f"(error: {e})", {}
            judge = {"total": 0.0, "notes": str(e)[:200]}
        conversations.append({
            "kind": "scenario",
            "persona_id": sc["persona_id"],
            "intent_id": sc["intent_id"],
            "session_id": use_session_id,  # set for I06, otherwise None
            "turns": [{
                "user": sc["opening"], "bot": bot_text,
                "debug": dbg_flat, "judge": judge,
            }],
        })
        # Write after the first scenario (so the UI leaves "Generiere Szenarien"
        # as soon as the loop starts), then every second one.
        n = idx + 1
        if n == 1 or n % 2 == 0 or n == len(scens):
            await progress(conversations, activity)


async def _run_conversation_stage(
    *, chat_url: str, run_id: str, conversations: list[dict],
    personas: list[dict], intents: list[dict], turns_per_conv: int,
    progress: Progress,
) -> None:
    """Stage 2 — a simulated multi-turn dialogue per combo, every turn judged."""
    total_combos = len(personas) * len(intents)
    combo_idx = 0
    for persona in personas:
        for intent in intents:
            combo_idx += 1
            activity = (
                f"Dialog {combo_idx}/{total_combos}: {persona['id']} × {intent['id']}"
            )
            await progress(conversations, activity)
            try:
                conv = await simulate_conversation(
                    chat_url, persona, intent, max_turns=turns_per_conv,
                )
            except Exception as e:
                logger.warning("[eval %s] conv failed %s/%s: %s",
                               run_id, persona["id"], intent["id"], e)
                continue
            for turn in conv["turns"]:
                if turn.get("error"):
                    turn["judge"] = {"total": 0.0, "notes": turn["error"]}
                    continue
                turn["judge"] = await judge_turn(
                    persona, intent, turn["user"], turn["bot"], turn["debug"],
                )
            conversations.append({
                "kind": "conversation",
                "persona_id": persona["id"],
                "intent_id": intent["id"],
                "session_id": conv["session_id"],
                "ended_early": conv["ended_early"],
                "turns": conv["turns"],
            })
            # Multi-turn dialogues are expensive — persist after each one.
            await progress(conversations, activity)


def build_summary(conversations: list[dict], target_turns: int, activity: str) -> dict[
    str, Any
]:
    """Score matrix + run-global classification metrics for a set of turns.

    ``classification_metrics`` is what ``GET /eval/trends`` reads; a run that
    never gets here leaves all five trend series empty.
    """
    summary = _aggregate(conversations)
    summary["target_turns"] = target_turns
    summary["current_activity"] = activity
    summary["classification_metrics"] = _aggregate_classification_metrics(conversations)
    return summary


async def execute_run(
    *,
    chat_url: str,
    run_id: str,
    conversations: list[dict],
    mode: str,
    personas: list[dict],
    intents: list[dict],
    scenarios_per_combo: int,
    turns_per_conv: int,
    target_turns: int,
    progress: Progress,
) -> dict[str, Any]:
    """Run both selected stages and return the final summary.

    Appends to the caller-owned ``conversations`` so a raised exception still
    leaves every finished conversation with the caller. The tool cache is cleared
    up front and its stats attached at the end, so the numbers describe THIS run
    instead of mixing in production hits.
    """
    try:
        from boerdi.services.mcp.tool_cache import clear_tool_cache
        cleared = clear_tool_cache()
        if cleared:
            logger.info("[eval %s] cleared tool cache (%d entries)", run_id, cleared)
    except Exception as e:
        logger.warning("[eval %s] tool cache clear failed: %s", run_id, e)

    if mode in ("scenarios", "both"):
        await _run_scenario_stage(
            chat_url=chat_url, run_id=run_id, conversations=conversations,
            personas=personas, intents=intents,
            scenarios_per_combo=scenarios_per_combo, progress=progress,
        )
    if mode in ("conversations", "both"):
        await _run_conversation_stage(
            chat_url=chat_url, run_id=run_id, conversations=conversations,
            personas=personas, intents=intents,
            turns_per_conv=turns_per_conv, progress=progress,
        )

    summary = build_summary(conversations, target_turns, "Fertig")
    try:
        from boerdi.services.mcp.tool_cache import get_tool_cache_stats
        summary["tool_cache"] = get_tool_cache_stats()
    except Exception as e:
        logger.warning("[eval %s] tool_cache stats fetch failed: %s", run_id, e)
    return summary
