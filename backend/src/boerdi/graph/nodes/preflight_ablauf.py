"""Abläufe im Preflight (aus ``preflight`` gelöst, Querschnitts-Review 2026-11-06, Q4) —
verhaltensgleich: welcher Auslöser ohne Knopf greift (:func:`bestimmen`, vor der
Sicherheitsprüfung) und die Antwort der Ablauf-, Auftrags- und Vorgangs-Aktionen
(:func:`antwort`, danach).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatResponse
from boerdi.graph.state import TurnContext
from boerdi.services import plan_fortsetzen, vorgang_aktion
from boerdi.services.ablauf import auftrag_zug
from boerdi.services.ablauf import zug as ablauf_zug
from boerdi.services.ordner_aktion import ist_ordner_als_entwurf


@dataclass(frozen=True)
class Ausloeser:
    im_lauf: bool
    per_modul: Any
    ordner: bool
    per_text: Any

    @property
    def irgendeiner(self) -> bool:
        return bool(self.ordner or self.im_lauf or self.per_modul or self.per_text)


@dataclass(frozen=True)
class Antwort:
    """Eine Aktion dieses Moduls hat geantwortet (``antwort`` kann ``None`` sein: ``fortsetzen``
    ohne offenen Block)."""
    antwort: ChatResponse | None


async def bestimmen(ctx: TurnContext, session: AsyncSession) -> Ausloeser:
    req = ctx.req
    # Paket U3-1b: „Ordnerstruktur als Entwurf“ aus ``ui_upload`` ist wie eine Direktaktion — der
    # Entwurf entsteht ohne LLM. Geprüft wird, was die Person schickt: Blase UND Ordnernamen
    # (``antwort.sicherheits_text``), durch dasselbe Tor wie jede Direktaktion.
    # Paket A1: eine Antwort auf den offenen Block eines Laufs setzt den Ablauf fort (ohne KI) —
    # zuerst geprüft, auch für den Ordner-Knopf von ui_upload (Review A1, Befund 1).
    im_lauf = (not req.action and ctx.ui_antwort is not None
               and await ablauf_zug.wartet_auf(session, req.session_id, ctx.session_state,
                                               ctx.ui_antwort))
    # Paket A2a: Auslöser ohne Knopf — eine Modul-Antwort (vor der Ordner-Aktion: der Ablauf führt
    # sie weiter) oder eine Wendung in einer getippten Nachricht.
    # Nicht, solange ein Lauf wartet (Review A2b, Befund 2): eine Modul-Antwort im agent-Schritt
    # ersetzte ihn sonst still.
    per_modul = (ablauf_zug.modul_ausloeser(ctx.ui_antwort)
                 if not req.action and not im_lauf and ctx.ui_antwort is not None
                 and not ablauf_zug.lauf_wartet(req.session_id, ctx.session_state) else None)
    ordner = (not req.action and not im_lauf and per_modul is None
              and ist_ordner_als_entwurf(ctx.ui_antwort))
    # Review A2a, Befund 1: getippter Text während eines wartenden Laufs ist ein gewöhnlicher Zug
    # (F1) — eine Wendung ersetzte sonst still den Lauf.
    per_text = (ablauf_zug.text_ausloeser(req.message)
                if not req.action and ctx.ui_antwort is None
                and not ablauf_zug.lauf_wartet(req.session_id, ctx.session_state) else None)
    return Ausloeser(bool(im_lauf), per_modul, bool(ordner), per_text)


async def antwort(ctx: TurnContext, session: AsyncSession, a: Ausloeser,
                  gesperrt: Iterable[str]) -> Antwort | None:
    """Die Antwort einer Ablauf-, Auftrags- oder Vorgangs-Aktion — ``None``, wenn keine gemeint
    ist. Die Sperren der Sicherheitsprüfung gelten auch für die Schritte (Review A1, Befund 2)."""
    req, state = ctx.req, ctx.session_state
    gesperrt = list(gesperrt)
    if req.action == ablauf_zug.AKTION:
        return Antwort(await ablauf_zug.starten(session, req, state, blocked_tools=gesperrt))
    if req.action == auftrag_zug.AKTION:
        return Antwort(await auftrag_zug.pruefen(session, req, state, blocked_tools=gesperrt))
    if req.action == vorgang_aktion.AKTION_NEU:
        return Antwort(await vorgang_aktion.neu(session, req, state))
    if req.action == vorgang_aktion.AKTION_LOESCHEN:
        return Antwort(await vorgang_aktion.loeschen(session, req, state))
    if req.action == plan_fortsetzen.AKTION:
        return Antwort(await plan_fortsetzen.weiter(session, req, state, blocked_tools=gesperrt))
    if req.action == ablauf_zug.AKTION_WEITER:
        return Antwort(await ablauf_zug.weiter_nach_ki(session, req, state,
                                                       blocked_tools=gesperrt))
    if a.per_modul is not None and ctx.ui_antwort is not None:
        return Antwort(await ablauf_zug.per_modul_starten(
            session, req, state, ctx.ui_antwort, a.per_modul, blocked_tools=gesperrt))
    if a.per_text is not None:
        return Antwort(await ablauf_zug.starten_mit(session, req, state, a.per_text,
                                                    blocked_tools=gesperrt))
    if a.im_lauf and ctx.ui_antwort is not None:
        return Antwort(await ablauf_zug.fortsetzen(session, req, state, ctx.ui_antwort,
                                                   blocked_tools=gesperrt))
    return None
