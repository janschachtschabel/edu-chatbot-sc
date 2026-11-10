"""Führungen im Zug (Paket AS-7a, Plan 2026-11-09 §5m).

Ein ``seite``-Schritt zeigt den Weg als Chip ``__fuehrung__|<Label>|<URL>`` (F-2). Das Widget zeigt
ihn wie den Lotsen-Chip der Tour: Er öffnet die Seite und übergibt die Sitzung. Ein eigenes
Präfix, weil der Widget-Nachlauf ``__guide__``-Chips außerhalb der Tour zu Links macht oder
entfernt. Mit ``ankunft`` wartet der Lauf (``treiber.WARTET_SEITE``):

- :func:`angekommen` beantwortet den **Seiten-Ping** (``page_event: ablauf_seite``, F-4), den das
  Widget nach einem Seitenaufruf schickt, solange der Stand ``wartet_seite`` ist. Der frühe Knoten
  ``graph/nodes/ablauf_seite`` ruft ihn vor dem Speichern der Nutzernachricht: Passt die Seite,
  geht der Lauf weiter, und die Antwort erscheint. Sonst ist sie leer, das Widget zeigt nichts,
  und nichts wird gespeichert.
- :func:`aktueller_knopf`: solange ein Schritt wartet, steht sein Chip unter jeder Antwort (F-5),
  wie die Chips einer Wahl.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.hintergrund_zug import ABLAUF_SEITE
from boerdi.domain.wahl_knopf import FUEHRUNG_PRAEFIX
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden

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
    schritt = treffer[2]
    return [knopf({"url": schritt.url or "", "label": treiber.seiten_label(schritt, lang)})]


def _leer(req: ChatRequest) -> ChatResponse:
    return ChatResponse(session_id=req.session_id, content="", follow_up="none")


async def angekommen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    """Der Seiten-Ping (F-4). Den Lauf liest der Zug aus dem Vorgang, nicht aus dem Verweis (wie
    ``wahl_zug``). Leer, solange nichts passt; nur ein Treffer wird festgehalten."""
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
        return _leer(req)
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        # ein paralleler Zug hat den Lauf bewegt — der Ping bleibt still
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return _leer(req)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)
