"""Schnellantworten eines Ablaufs im Zug (Paket AS-3a, Plan 2026-11-09 §5d, D2).

Ein Schritt mit ``optionen`` oder ``freitext`` wartet (``treiber.WARTET_WAHL``). Die Optionen stehen
als Direktaktion-Chips unter der Antwort (:func:`knoepfe`) — ``__action__|<Label>|ablauf_wahl|
{ablauf, schritt, wahl}`` — und zwar unter jeder Antwort, solange der Lauf wartet
(:func:`aktuelle_knoepfe`): tippt die Person etwas anderes, antwortet die KI, und die Wahl bleibt
der Weg „zurück zum Ablauf“.

- :func:`waehlen`: die Direktaktion ``ablauf_wahl`` — sie wirkt nur, wenn der Lauf dieser Person an
  genau diesem Schritt dieses Ablaufs in unveränderter Fassung wartet.
- :func:`getippt`: getippter Text, der einem Label entspricht, ist diese Wahl; an einem Schritt mit
  ``freitext`` ist sonst jeder Text die Antwort und wird ein Teil (:func:`nimmt_getippt` sagt es
  dem Preflight, ohne Datenbank). Er geht durch dieselbe Sicherheitsprüfung wie jede Nachricht.
  Greift er nicht (Lauf inzwischen anders), ist die Antwort ``None`` — der Zug geht den
  gewöhnlichen Weg.
- :func:`aufraeumen`: ein wartender Lauf, dessen Ablauf aus ist oder dessen Schritte sich änderten,
  wird abgebrochen (wie ``zug.wartet_auf``) — sonst sperrte er Wendungen und Modul-Auslöser, ohne
  dass ein Chip zurückführt (Review AS-3a, Befund 3).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.wahl_knopf import AKTION as WAHL_AKTION
from boerdi.i18n import resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber, vorschlag
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.ablauf.pruefung import mit_wahl

logger = logging.getLogger(__name__)

AKTION: Final = WAHL_AKTION
#: So lang darf ein Label im Chip sein (die Prüfung deckelt bei 60).
_LABEL_ZEICHEN: Final = 60


def knoepfe(ablauf_id: str, wahl: dict[str, Any] | None) -> list[str]:
    """Die Chips der angebotenen Wahl (``treiber.Ausgabe.wahl``)."""
    if not wahl:
        return []
    return [f"__action__|{label[:_LABEL_ZEICHEN].replace('|', '/')}|{AKTION}|"
            + json.dumps({"ablauf": ablauf_id, "schritt": wahl["schritt"], "wahl": kennung},
                         ensure_ascii=False)
            for kennung, label in wahl.get("optionen") or []]


def _wartend(session_id: str, session_state: dict[str, Any]
             ) -> tuple[dict[str, Any], AblaufArea, Schritt] | None:
    """Lauf, Ablauf und Schritt, solange ein Lauf dieser Person auf eine Wahl wartet — nur der
    Verweis, ohne Datenbank (Preflight, Schnellantworten); nur, solange der Ablauf gilt."""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_WAHL:
        return None
    ablauf = laden(lauf.get("ablauf"))
    if not treiber.gilt(ablauf, lauf):
        return None
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if schritt is None or not mit_wahl(schritt):
        return None
    return lauf, ablauf, schritt


def platz_fuer_vorschlag(session_id: str, session_state: dict[str, Any], lang: str,
                         hoechstens: int | None = None) -> bool:
    """Passt neben die Chips einer wartenden Wahl noch ein Ablauf-Knopf? Die Chips bleiben ganz
    (``vorschlag.anhaengen(alle=True)``); füllen sie den Platz, fiele der Knopf weg, obwohl die KI
    ihn angekündigt hätte — dann bietet der Zug keinen Ablauf an (offen seit AS-5b)."""
    return len(aktuelle_knoepfe(session_id, session_state, lang)) < vorschlag.grenze(hoechstens)


def aktuelle_knoepfe(session_id: str, session_state: dict[str, Any], lang: str) -> list[str]:
    """Die Chips, solange ein Lauf dieser Person auf eine Wahl wartet — sonst leer."""
    if (treffer := _wartend(session_id, session_state)) is None:
        return []
    _lauf, ablauf, schritt = treffer
    return knoepfe(ablauf.id, treiber.wahl_angebot(schritt, lang))


wahl_aus_text = treiber.wahl_aus_text


def nimmt_getippt(session_id: str, session_state: dict[str, Any], text: str | None) -> bool:
    """Nimmt der wartende Schritt dieser Person den getippten Text — als Wahl (gleich einem Label)
    oder als Freitext?"""
    if (treffer := _wartend(session_id, session_state)) is None:
        return False
    schritt = treffer[2]
    return schritt.freitext is not None or wahl_aus_text(schritt, text) is not None


async def aufraeumen(session: Any, session_id: str, session_state: dict[str, Any]) -> None:
    """Review AS-3a, Befund 3: ein Lauf, der auf eine Wahl wartet, aber nicht mehr kann (Ablauf
    aus, Schritte geändert), wird abgebrochen. Nur, wenn der Verweis so aussieht — sonst kein
    Lesen. Fehler beim Lesen lassen den Zug den gewöhnlichen Weg gehen."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    lauf = (vw or {}).get("lauf")
    status = lauf.get("status") if isinstance(lauf, dict) else None
    # Querschnitts-Review AS-7, Befund 3: auch eine wartende Führung — ohne Stand pingt das Widget
    # nie, und der tote Lauf sperrte Wendungen und Modul-Auslöser
    if status == treiber.WARTET_WAHL:
        noch_gut = _wartend(session_id, session_state) is not None
    elif status == treiber.WARTET_SEITE:
        from boerdi.services.ablauf import seite_zug

        noch_gut = seite_zug.wartend(session_id, session_state) is not None
    else:
        return
    if noch_gut:
        return
    try:
        v = await vorgaenge.lesen(session, vw["id"], aufrufer)
        await basis.frei(session)
        echt = (v.akte or {}).get("lauf") if v is not None else None
        if not isinstance(echt, dict) or echt.get("status") != status:
            basis.verweis_auffrischen(entities, v, aufrufer)
            return
        ablauf = laden(echt.get("ablauf"))
        schritt = (next((s for s in ablauf.schritte if s.id == echt.get("schritt")), None)
                   if ablauf is not None else None)
        passt = schritt is not None and (
            mit_wahl(schritt) if status == treiber.WARTET_WAHL else schritt.typ == "seite")
        if (not treiber.gilt(ablauf, echt) or not passt):
            await basis.abbrechen(session, v, echt, entities, aufrufer)
    except Exception as fehler:  # noqa: BLE001 — ohne Lesen geht der Zug den gewöhnlichen Weg
        logger.warning("Ablauf: Vorgang nicht lesbar (%s)", type(fehler).__name__)


async def waehlen(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Die Direktaktion ``ablauf_wahl``. Ein alter Chip (der Lauf steht inzwischen woanders)
    bekommt „gilt nicht mehr“ und die Chips, die jetzt gelten (Review AS-3a, Befund 4)."""
    params = req.action_params or {}
    wahl = params.get("wahl")
    antwort = await _fortsetzen(session, req, session_state, blocked_tools,
                                ablauf_id=params.get("ablauf"), schritt_id=params.get("schritt"),
                                wahl=wahl if isinstance(wahl, str) else None, text=None)
    if antwort is not None:
        return antwort
    entities = session_state.setdefault("entities", {})
    antwort = await basis.nur_text(session, req, "action.ablauf.wahlVeraltet", entities)
    antwort.quick_replies = aktuelle_knoepfe(req.session_id, session_state,
                                             resolve_locale(req.environment.locale))
    return antwort


async def getippt(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse | None:
    """Getippter Text am wartenden Schritt: gleich einem Label → diese Wahl, sonst Freitext.
    ``None``: der Zug geht den gewöhnlichen Weg (der Lauf wartet inzwischen nicht mehr)."""
    if (treffer := _wartend(req.session_id, session_state)) is None:
        return None
    _lauf, ablauf, schritt = treffer
    wahl = wahl_aus_text(schritt, req.message)
    return await _fortsetzen(session, req, session_state, blocked_tools, ablauf_id=ablauf.id,
                             schritt_id=schritt.id, wahl=wahl,
                             text=None if wahl else (req.message or ""))


async def _fortsetzen(session: Any, req: ChatRequest, session_state: dict,
                      blocked_tools: Iterable[str], *, ablauf_id: Any, schritt_id: Any,
                      wahl: str | None, text: str | None) -> ChatResponse | None:
    """Wie ``zug.weiter_nach_ki``: den Lauf aus dem Vorgang lesen (nicht aus dem Verweis), prüfen,
    rechnen, festhalten. ``None``, wenn der Lauf nicht an diesem Schritt wartet oder die Eingabe
    nicht passt — dann ist noch nichts gespeichert."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if (not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_WAHL
            or lauf.get("ablauf") != ablauf_id or lauf.get("schritt") != schritt_id):
        # Querschnitts-Review M5: der Verweis folgt dem Vorgang (zweite Sitzung, verdrängt).
        basis.verweis_auffrischen(entities, v, aufrufer)
        return None
    ablauf = laden(ablauf_id)
    if not treiber.gilt(ablauf, lauf):
        # wie Review A2b, Befund 7: ein Lauf, der nicht mehr kann, wartet nicht weiter
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    if not treiber.wahl_gilt(ablauf, lauf, wahl, text):
        return None
    aus = await basis.rechne(session, ablauf, treiber.weiter_wahl(
        ablauf, dict(lauf), wahl, text, basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        # Review AS-3a, Befund 4: ein Fehler beim Rechnen ist kein veralteter Chip
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)

