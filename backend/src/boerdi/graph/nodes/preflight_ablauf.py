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
from boerdi.domain.hintergrund_zug import ist_hintergrund_anfrage
from boerdi.graph.state import TurnContext
from boerdi.services import plan_fortsetzen, vorgang_aktion
from boerdi.services.ablauf import abbruch_zug, auftrag_zug, freigabe_zug, wahl_zug
from boerdi.services.ablauf import zug as ablauf_zug
from boerdi.services.ordner_aktion import ist_ordner_als_entwurf

#: Was ein gesperrter Lauf (K2b, ``warten: gesperrt``) durchlässt — alles andere bekommt den
#: Hinweis.
_IM_GESPERRTEN_LAUF: frozenset[str] = frozenset({
    auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN,
    vorgang_aktion.AKTION_NEU, vorgang_aktion.AKTION_LOESCHEN,
    abbruch_zug.AKTION,
})


@dataclass(frozen=True)
class Ausloeser:
    im_lauf: bool
    per_modul: Any
    ordner: bool
    per_text: Any
    #: K2b: die Kennung des Ablaufs, dessen wartender Auftragsschritt die Eingabe sperrt.
    gesperrt: str | None = None
    #: AS-3a: getippter Text ist die Antwort am wartenden Schritt (gleich einem Label oder
    #: ``freitext``).
    freitext: bool = False

    @property
    def irgendeiner(self) -> bool:
        return bool(self.ordner or self.im_lauf or self.per_modul or self.per_text
                    or self.gesperrt or self.freitext)


def abgewiesen(aktion: str | None, gesperrt: str | None) -> bool:
    """Bekommt dieser Zug im gesperrten Lauf nur den Hinweis? (getippt, Modul-Antwort, andere
    Knöpfe — nicht die Auftrags- und Vorgangs-Aktionen)."""
    return gesperrt is not None and aktion not in _IM_GESPERRTEN_LAUF


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
    # Paket K2b: ein Zug der Person (kein Kontext-Ping, kein Tour-Tick) im gesperrten Lauf.
    gesperrt = None
    if not ist_hintergrund_anfrage(req.environment):
        auftrag_zug.sperre_aufraeumen(req.session_id, ctx.session_state)
        gesperrt = auftrag_zug.gesperrt(req.session_id, ctx.session_state)
    # Paket AS-3a: getippter Text (kein Knopf, keine Modul-Antwort, kein Hintergrund-Zug) an einem
    # wartenden Schritt — gleich einem Label oder als Freitext — ist die Antwort, durch dieselbe
    # Sicherheitsprüfung. Vorher ein Lauf aufräumen, der nicht mehr kann (Review, Befund 3).
    getippt = (not req.action and ctx.ui_antwort is None and bool((req.message or "").strip())
               and not ist_hintergrund_anfrage(req.environment))
    if getippt:
        await wahl_zug.aufraeumen(session, req.session_id, ctx.session_state)
    freitext = getippt and wahl_zug.nimmt_getippt(req.session_id, ctx.session_state, req.message)
    return Ausloeser(bool(im_lauf), per_modul, bool(ordner), per_text, gesperrt, freitext)


async def antwort(ctx: TurnContext, session: AsyncSession, a: Ausloeser,
                  gesperrt: Iterable[str]) -> Antwort | None:
    """Die Antwort einer Ablauf-, Auftrags- oder Vorgangs-Aktion — ``None``, wenn keine gemeint
    ist. Die Sperren der Sicherheitsprüfung gelten auch für die Schritte (Review A1, Befund 2)."""
    req, state = ctx.req, ctx.session_state
    gesperrt = list(gesperrt)
    if abgewiesen(req.action, a.gesperrt):
        return Antwort(await auftrag_zug.gesperrt_antwort(session, req, a.gesperrt or ""))
    if req.action == auftrag_zug.AKTION_ABBRECHEN:
        return Antwort(await auftrag_zug.abbrechen(session, req, state))
    if req.action == abbruch_zug.AKTION:
        return Antwort(await abbruch_zug.abbrechen(session, req, state))
    if req.action == ablauf_zug.AKTION:
        return Antwort(await ablauf_zug.starten(session, req, state, blocked_tools=gesperrt))
    if req.action == auftrag_zug.AKTION:
        return Antwort(await auftrag_zug.pruefen(session, req, state, blocked_tools=gesperrt))
    if req.action == vorgang_aktion.AKTION_NEU:
        return Antwort(await vorgang_aktion.neu(session, req, state))
    if req.action == vorgang_aktion.AKTION_LOESCHEN:
        return Antwort(await vorgang_aktion.loeschen(session, req, state))
    if req.action == freigabe_zug.AKTION_ERNEUT:
        return Antwort(await freigabe_zug.erneut(session, req, state, blocked_tools=gesperrt))
    if req.action == freigabe_zug.AKTION_ABBRECHEN:
        return Antwort(await freigabe_zug.abbrechen(session, req, state))
    if req.action == plan_fortsetzen.AKTION:
        # Paket S4: gehörte der Plan zu einem Lauf, geht der weiter, wenn der Plan fertig ist
        vorher = (state.get("entities") or {}).get(plan_fortsetzen.KEY)
        antwort_plan = await plan_fortsetzen.weiter(session, req, state, blocked_tools=gesperrt)
        return Antwort(await freigabe_zug.nach_plan(session, req, state, vorher, antwort_plan,
                                                    blocked_tools=gesperrt))
    if req.action == wahl_zug.AKTION:
        return Antwort(await wahl_zug.waehlen(session, req, state, blocked_tools=gesperrt))
    if a.freitext:
        # ``None``: der Lauf wartet nicht mehr auf Text — der Zug geht den gewöhnlichen Weg
        return Antwort(await wahl_zug.getippt(session, req, state, blocked_tools=gesperrt))
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
