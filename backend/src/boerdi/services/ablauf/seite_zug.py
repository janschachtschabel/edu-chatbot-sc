"""Führungen im Zug (Paket AS-7a, Plan 2026-11-09 §5m).

Ein ``seite``-Schritt zeigt den Weg als Chip ``__fuehrung__|<Label>|<URL>`` (F-2). Das Widget zeigt
ihn wie den Lotsen-Chip der Tour: Er öffnet die Seite und übergibt die Sitzung. Ein eigenes
Präfix, weil der Widget-Nachlauf ``__guide__``-Chips außerhalb der Tour zu Links macht oder
entfernt. Mit ``ankunft`` wartet der Lauf (``treiber.WARTET_SEITE``):

- :func:`angekommen` beantwortet den **Seiten-Ping** (``page_event: ablauf_seite``, F-4), den das
  Widget nach einem Seitenaufruf schickt, solange der Stand ``wartet_seite`` ist. Der frühe Knoten
  ``graph/nodes/ablauf_seite`` ruft ihn vor dem Speichern der Nutzernachricht: Passt die Seite,
  geht der Lauf weiter, und die Antwort erscheint. Sonst der Hinweis des Schritts (``abweichung``
  oder ``umsehen``, WF-4) mit dem Chip, ohne ihn zu speichern; ohne Hinweis ist sie leer, und das
  Widget zeigt nichts.
- :func:`aktueller_knopf`: solange ein Schritt wartet, steht sein Chip unter jeder Antwort (F-5),
  wie die Chips einer Wahl.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain import seiten_muster
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.hintergrund_zug import ABLAUF_SEITE
from boerdi.domain.wahl_knopf import FUEHRUNG_PRAEFIX
from boerdi.i18n import resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import platzhalter, treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden, trifft_text

logger = logging.getLogger(__name__)

#: Das ``page_event`` des Seiten-Pings.
PING: Final = ABLAUF_SEITE
#: So lang darf die Aufschrift im Chip sein (das Modell deckelt bei 60).
_LABEL_ZEICHEN: Final = 60


def knopf(navigation: dict[str, str]) -> str:
    """Der Chip eines ``seite``-Schritts (``treiber.Ausgabe.navigation``). ``|`` trennt die Teile;
    in der URL verbietet es die Prüfung, in der Aufschrift wird es ``/``."""
    label = (navigation.get("label") or "")[:_LABEL_ZEICHEN].replace("|", "/")
    return f"{FUEHRUNG_PRAEFIX}{label}|{navigation.get('url') or ''}"


def wartend(session_id: str, session_state: dict[str, Any]
             ) -> tuple[dict[str, Any], AblaufArea, Schritt] | None:
    """Lauf, Ablauf und Schritt, solange ein Lauf dieser Person an einem ``seite``-Schritt wartet —
    nur aus dem Verweis, ohne Datenbank."""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_SEITE:
        return None
    ablauf = laden(lauf.get("ablauf"))
    if not treiber.gilt(ablauf, lauf):
        return None
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if schritt is None or schritt.typ != "seite":
        return None
    return lauf, ablauf, schritt


def aktueller_knopf(session_id: str, session_state: dict[str, Any], lang: str) -> list[str]:
    """Der Chip des wartenden ``seite``-Schritts — sonst leer (F-5)."""
    if (treffer := wartend(session_id, session_state)) is None:
        return []
    return aktueller_knopf_von(treffer[2], lang)


def aktueller_knopf_von(schritt: Schritt, lang: str) -> list[str]:
    """Der Chip eines ``seite``-Schritts."""
    return [knopf({"url": schritt.url or "", "label": treiber.seiten_label(schritt, lang)})]


def wiederholt(session_id: str, session_state: dict[str, Any], text: str | None) -> bool:
    """Review 16.11. (Führung wie Tour, M1): Tippt die Person an einem wartenden ``seite``-Schritt
    eine Wendung DESSELBEN Ablaufs („starte die Tour“), meint sie die Führung — der Schritt wird
    erneut gezeigt, statt dass ``endet_bei_text`` den Lauf beendet. So macht es die Tour seit
    2026-08-19 (``graph/nodes/tour``, ``wiederholen``). Nur aus dem Verweis, ohne Datenbank."""
    treffer = wartend(session_id, session_state)
    return treffer is not None and trifft_text(treffer[1], text)


async def wiederholen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse | None:
    """Den wartenden ``seite``-Schritt erneut zeigen: sein Text (mit Platzhaltern) und sein Chip.
    Der Lauf bleibt, wie er ist; die Antwort wird gespeichert (wie die Tour). ``None``: der Lauf
    wartet nicht mehr — der Zug geht den gewöhnlichen Weg."""
    if (treffer := wartend(req.session_id, session_state)) is None:
        return None
    _lauf, ablauf, s = treffer
    entities = session_state.setdefault("entities", {})
    lang = resolve_locale(req.environment.locale)
    text = ((s.text or {}).get(lang) or (s.text or {}).get("de") or "").strip()
    teile = basis.umgebung(session, req, entities, ()).teile
    text, _fremd = await treiber.wahl_einsetzen(text, ablauf, lang, teile)
    text = await platzhalter.einsetzen(text, teile)
    return await basis.fester_text(session, req, text, entities, aktueller_knopf_von(s, lang))


def _leer(req: ChatRequest) -> ChatResponse:
    return ChatResponse(session_id=req.session_id, content="", follow_up="none")


async def _hinweis(session: Any, req: ChatRequest, ablauf: AblaufArea, lauf: dict[str, Any],
                   seite: str, entities: dict[str, Any]) -> ChatResponse:
    """WF-4 (Plan 2026-11-15): die Seite passt nicht — auf einer Umschau-Seite deren Text, sonst
    der Hinweis ``abweichung``, jeweils mit demselben Chip; ohne beides bleibt der Ping leer. Der
    Lauf wartet weiter (wie in der eingebauten Führung: ``explore`` und ``nudge``).

    Nicht gespeichert (Review WF-3/4, Befund M1, wie ``persist_assistant = False`` der Tour): sonst
    stünde nach jedem Seitenaufruf derselbe Hinweis im Verlauf und im Gedächtnis der KI."""
    s = next((x for x in ablauf.schritte if x.id == lauf.get("schritt")), None)
    # Review, Befund m1: auf der Zielseite selbst (der Treiber rechnete nicht) kein „woanders“
    if s is None or s.typ != "seite" or (s.ankunft and seiten_muster.passt(seite, s.ankunft)):
        return _leer(req)
    lang = resolve_locale(req.environment.locale)
    texte = (s.umsehen.text if s.umsehen is not None
             and seiten_muster.passt(seite, s.umsehen.muster) else s.abweichung)
    text = ((texte or {}).get(lang) or (texte or {}).get("de") or "").strip()
    if not text:
        return _leer(req)
    return ChatResponse(session_id=req.session_id, content=text,
                        quick_replies=aktueller_knopf_von(s, lang), ui=UiInfo(fester_text=True))


async def angekommen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    """Der Seiten-Ping (F-4). Den Lauf liest der Zug aus dem Vorgang, nicht aus dem Verweis (wie
    ``wahl_zug``). Passt die Seite nicht: der Hinweis des Schritts (WF-4) oder leer; nur ein
    Treffer wird festgehalten."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    if not isinstance((vw or {}).get("lauf"), dict) or vw["lauf"].get("status") != (
            treiber.WARTET_SEITE):
        return _leer(req)   # ohne wartenden Verweis kein Lesen
    v = await vorgaenge.lesen(session, vw["id"], aufrufer)
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_SEITE:
        # Zweites Review AS-7a, Befund 2 (wie ``wahl_zug``, M5): eine zweite Sitzung hat den Lauf
        # bewegt — der Verweis folgt dem Vorgang, sonst pingte das Widget weiter und zeigte einen
        # toten Chip. Still: der Ping ist kein Zug der Person.
        basis.verweis_auffrischen(entities, v, aufrufer)
        await basis.update_session(session, req.session_id, entities=entities)  # wie nur_text
        return _leer(req)
    ablauf = laden(lauf.get("ablauf"))
    if not treiber.gilt(ablauf, lauf):
        # wie ``wahl_zug``: ein Lauf, der nicht mehr kann, wartet nicht weiter
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    umgebung = replace(basis.umgebung(session, req, entities, ()),
                       seite=req.environment.page or "/")
    aus = await basis.rechne(session, ablauf, treiber.weiter_seite(ablauf, dict(lauf), umgebung))
    if aus is None:
        return await _hinweis(session, req, ablauf, lauf, umgebung.seite, entities)
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        # ein paralleler Zug hat den Lauf bewegt — der Ping bleibt still
        await session.rollback()
        await basis.nicht_festgehalten(aus)
        return _leer(req)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)
