"""Pläne: Sammlungsbaum und Massen-Aufnahme unter EINER Bestätigung (Paket M5, Plan 2026-11-07).

Der MCP (Stand 2026-11-07) führt ``wlo_create_collection_tree`` und ``wlo_add_to_collections`` als
Plan: eine Vorschau für das Ganze, nach dem „ja“ Abschnitte von etwa 40 s. Ist nach einem Abschnitt
etwas offen, antwortet er mit ``complete: false``, ``progress`` und einem ``continuationToken``.
Fortgesetzt wird **ohne neue Bestätigung** — der Plan ist an die Freigabe gebunden, und denselben
Schlüssel erneut vorzulegen ist sicher (der Server setzt fort oder liefert dasselbe Ergebnis, er
legt nie doppelt an). Auch der Bestätigungsschlüssel, der den Plan gestartet hat, gilt dort als
Fortsetzungs-Schlüssel — so übersteht ein Plan eine verlorene erste Antwort.

Hier: den offenen Plan merken (:data:`KEY` in ``entities`` — Werkzeug, Angaben ohne Schlüssel,
Fortsetzungs-Schlüssel, Aufrufer, Frist), den Stand für die Person aufbereiten (ohne den Schlüssel)
und die Direktaktion :data:`AKTION` („Weiter anlegen“) — nur für dieselbe Person, nur mit
Schreibrecht und nur, solange das Werkzeug hier freigegeben ist (dieselben Prüfungen wie beim
Einlösen), höchstens bis zur Frist des Plans. Ohne Modell, hinter der Sicherheitsprüfung des
Preflights wie jede Direktaktion. Das Modell setzt nie selbst fort
(``domain/write_confirm.strip_confirm_token`` entfernt auch :data:`FORTSETZEN_FIELD`).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.domain.write_confirm import (
    CONFIRM_TOKEN_FIELD,
    FORTSETZEN_FIELD,
    OFFENER_PLAN_KEY,
    PLAN_TOOLS,
    is_plan,
    redact_confirm_token,
)
from boerdi.i18n import Locale, bot_text, resolve_locale
from boerdi.obs.log_inhalt import kennung
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.mcp.auth import aufrufer_kennung
from boerdi.services.mcp.client import McpAntwort, call_mcp_tool_antwort, is_mcp_error
from boerdi.services.schreibrecht import schreiben_erlaubt

logger = logging.getLogger(__name__)

AKTION: Final = "plan_weiter"
#: In ``session_state["entities"]``: der offene Plan (überdauert Züge, wie ``_pending_write``).
KEY: Final = OFFENER_PLAN_KEY
#: Ein Plan gilt 30 min ab Bestätigung (Server); ohne ``expiresAt`` gilt diese Frist ab jetzt.
PLAN_TTL_SECONDS: Final = 30 * 60
_PATTERN_ID: Final = "DIRECT: plan_weiter"


def ist_plan(tool_name: str) -> bool:
    return is_plan(tool_name)


__all__ = ["AKTION", "KEY", "PLAN_TOOLS", "PLAN_TTL_SECONDS", "abgelaufen_weg", "anzeige",
           "ist_plan", "knopf", "merke", "merke_unklar", "offen_fuer", "ohne_schluessel", "weiter"]


def knopf(lang: Locale | str) -> str:
    """Die Schnellantwort „Weiter anlegen“."""
    label = bot_text(lang, "action.plan.weiterKnopf").replace("|", "/")
    return f"__action__|{label}|{AKTION}|{{}}"


def ohne_schluessel(args: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in args.items() if k not in (CONFIRM_TOKEN_FIELD, FORTSETZEN_FIELD)}


def _frist(sc: dict[str, Any], now: float) -> float:
    """Die Frist des Servers (``expiresAt``, Review M5 NIT 10) — sonst :data:`PLAN_TTL_SECONDS`."""
    wert = sc.get("expiresAt")
    if isinstance(wert, str) and wert:
        try:
            return datetime.fromisoformat(wert.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return now + PLAN_TTL_SECONDS


def _ablauf(plan: dict[str, Any]) -> float:
    if isinstance(plan.get("expires_at"), (int, float)):
        return float(plan["expires_at"])
    return float(plan.get("minted_at") or 0) + PLAN_TTL_SECONDS


def _gleicher_plan(entities: dict[str, Any], tool: str, args: dict[str, Any]) -> bool:
    gemerkt = entities.get(KEY)
    return (isinstance(gemerkt, dict) and gemerkt.get("tool") == tool
            and gemerkt.get("args") == ohne_schluessel(args))


def _merke(entities: dict[str, Any], tool: str, args: dict[str, Any], schluessel: str, *,
           caller: str, now: float, frist: float) -> None:
    entities[KEY] = {"tool": tool, "args": ohne_schluessel(args), "token": schluessel,
                     "caller": caller, "minted_at": now, "expires_at": frist}


def merke(entities: dict[str, Any], tool: str, args: dict[str, Any], antwort: McpAntwort, *,
          caller: str, now: float) -> bool:
    """Den offenen Plan merken — oder vergessen, wenn er fertig ist. ``True``: offen.

    Vergessen wird nur DIESER Plan (Review M5, Befund 4): ein anderer, noch offener behält
    seinen Merkposten, wenn ein zweiter in einem Abschnitt fertig wird."""
    sc = antwort.strukturiert or {}
    schluessel = sc.get(FORTSETZEN_FIELD)
    if sc.get("complete") is False and isinstance(schluessel, str) and schluessel:
        _merke(entities, tool, args, schluessel, caller=caller, now=now, frist=_frist(sc, now))
        return True
    if _gleicher_plan(entities, tool, args):
        entities.pop(KEY, None)
    return False


def merke_unklar(entities: dict[str, Any], tool: str, args: dict[str, Any], *, caller: str,
                 now: float) -> bool:
    """Das Einlösen eines Plans blieb ohne Antwort (Review M5, Befund 3): der Server nimmt den
    Bestätigungsschlüssel auch als Fortsetzungs-Schlüssel — ihn merken. Kennt der Server den Plan
    nicht (die Anfrage kam nie an), antwortet er ``plan_expired``. ``True``: gemerkt."""
    schluessel = args.get(CONFIRM_TOKEN_FIELD)
    if not isinstance(schluessel, str) or not schluessel:
        return False
    _merke(entities, tool, args, schluessel, caller=caller, now=now, frist=now + PLAN_TTL_SECONDS)
    return True


def anderer_plan_offen(entities: dict[str, Any], tool: str, args: dict[str, Any], *, caller: str,
                       now: float) -> bool:
    """Liegt ein ANDERER eigener Plan offen, als der mit ``tool``/``args``?"""
    return offen_fuer(entities, caller, now) and not _gleicher_plan(entities, tool, args)


def offen_fuer(entities: dict[str, Any], caller: str, now: float) -> bool:
    """Liegt ein eigener, noch nicht abgelaufener Plan zum Fortsetzen bereit?"""
    plan = entities.get(KEY)
    return (isinstance(plan, dict) and plan.get("caller") == caller and bool(plan.get("token"))
            and now < _ablauf(plan))


def abgelaufen_weg(entities: object, now: float) -> bool:
    """Einen abgelaufenen Plan zu Zugbeginn verwerfen (Review M5, Befund 7: sonst stünden Titel
    und Beschreibungen des Baums dauerhaft im Sitzungszustand). ``True``: verworfen."""
    if isinstance(entities, dict) and isinstance(entities.get(KEY), dict) \
            and now >= _ablauf(entities[KEY]):
        entities.pop(KEY, None)
        return True
    return False


def anzeige(text: str, lang: Locale | str, *, offen: bool) -> str:
    """Der Stand des Servers für die Person: ohne die Zeile mit dem Fortsetzungs-Schlüssel (sie
    richtet sich an ein Programm), bei einem offenen Plan mit dem Hinweis auf „Weiter anlegen“."""
    zeilen = [z for z in redact_confirm_token(text or "").splitlines()
              if FORTSETZEN_FIELD not in z]
    sauber = "\n".join(zeilen).strip()
    return f"{sauber}\n\n{bot_text(lang, 'write.planOpen')}" if offen else sauber


async def weiter(session: Any, req: ChatRequest, session_state: dict, *,
                 blocked_tools: list[str] | None = None) -> ChatResponse:
    """Direktaktion „Weiter anlegen“: den gemerkten Plan mit seinem Schlüssel fortsetzen. Die
    Sperren der Sicherheitsprüfung (``blocked_tools``) gelten wie für jede Direktaktion."""
    # Zyklenfrei erst zur Laufzeit: ``write_approval`` bindet dieses Modul beim Import.
    from boerdi.services import write_approval

    lang = resolve_locale(req.environment.locale)
    entities = session_state.setdefault("entities", {})
    plan = entities.get(KEY) if isinstance(entities.get(KEY), dict) else None
    tool = str((plan or {}).get("tool") or "")
    debug = DebugInfo(pattern=_PATTERN_ID, tools_called=[], entities={"tool": tool})
    if not schreiben_erlaubt():
        return await _antwort(session, req, entities, bot_text(lang, "write.loginNeeded"), debug)
    if (plan is None or not ist_plan(tool) or not isinstance(plan.get("args"), dict)
            or not offen_fuer(entities, aufrufer_kennung(), time.time())):
        abgelaufen_weg(entities, time.time())
        return await _antwort(session, req, entities, bot_text(lang, "write.planNone"), debug)
    # Review M5, Befund 1: dieselben Prüfungen wie beim Einlösen — im Studio verborgen, nur lesende
    # Einbettung. Ein verborgenes Werkzeug wird hier nie mehr fortgesetzt; der Merkposten fällt weg.
    if tool in (blocked_tools or []):
        logger.warning("Plan %s nicht fortgesetzt (gesperrt durch die Sicherheitsprüfung)", tool)
        return await _antwort(session, req, entities, bot_text(lang, "write.planBlocked"), debug)
    if grund := write_approval._nicht_einloesbar(tool, req):
        logger.warning("Plan %s nicht fortgesetzt (%s)", tool, grund)
        if tool in write_approval.verborgene_werkzeuge():
            entities.pop(KEY, None)
        return await _antwort(session, req, entities, bot_text(lang, "write.planBlocked"), debug)
    debug.tools_called.append(tool)
    antwort = await call_mcp_tool_antwort(tool, {**plan["args"], FORTSETZEN_FIELD: plan["token"]})
    if is_mcp_error(antwort.text) or antwort.art:
        return await _fehler(session, req, entities, lang, antwort, debug)
    offen = merke(entities, tool, plan["args"], antwort, caller=plan["caller"],
                  now=float(plan.get("minted_at") or time.time()))
    logger.info("Plan %s (Sitzung %s) fortgesetzt — %s", tool, kennung(req.session_id),
                "offen" if offen else "fertig")
    return await _antwort(session, req, entities, anzeige(antwort.text, lang, offen=offen), debug,
                          knoepfe=[knopf(lang)] if offen else [])


async def _fehler(session: Any, req: ChatRequest, entities: dict[str, Any], lang: Locale,
                  antwort: McpAntwort, debug: DebugInfo) -> ChatResponse:
    if antwort.code in ("plan_expired", "plan_mismatch"):
        entities.pop(KEY, None)
        return await _antwort(session, req, entities, bot_text(lang, "write.planExpired"), debug)
    if antwort.art == "auth":
        return await _antwort(session, req, entities, bot_text(lang, "write.loginNeeded"), debug)
    if antwort.art == "busy":
        # Plan 2026-11-07 (CB-2): ausgelastet, nichts lief — der Plan bleibt samt Schlüssel.
        return await _antwort(session, req, entities, bot_text(lang, "write.planBusy"), debug,
                              knoepfe=[knopf(lang)])
    if antwort.art in ("timeout", "transport"):
        # Denselben Schlüssel erneut vorzulegen ist sicher — der Plan bleibt gemerkt.
        return await _antwort(session, req, entities, bot_text(lang, "write.planUnclear"), debug,
                              knoepfe=[knopf(lang)])
    from boerdi.services.write_approval import _abgelehnt_text  # zyklenfrei erst zur Laufzeit

    entities.pop(KEY, None)
    return await _antwort(session, req, entities, _abgelehnt_text(lang, antwort), debug)


async def _antwort(session: Any, req: ChatRequest, entities: dict[str, Any], text: str,
                   debug: DebugInfo, *, knoepfe: list[str] | None = None) -> ChatResponse:
    """Festschreiben (der Plan-Merkposten überdauert den Zug) und antworten — dieser Weg endet vor
    ``persist``, also schreibt sonst niemand mehr."""
    await update_session(session, req.session_id, entities=entities)
    try:
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
    except Exception:  # noqa: BLE001 — nur eine Zeile im Verlauf fehlt
        logger.warning("Plan: Antwort nicht im Verlauf gespeichert", exc_info=True)
    return ChatResponse(session_id=req.session_id, content=text, quick_replies=knoepfe or [],
                        debug=debug)
