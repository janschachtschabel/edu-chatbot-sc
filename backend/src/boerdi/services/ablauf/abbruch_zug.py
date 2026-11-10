"""Direktaktion ``ablauf_abbrechen`` (Paket AS-Ua, Plan 2026-11-09 §5h, U-5): „Abbrechen“ in der
Ablauf-Leiste des Widgets.

Ein Abbruch lässt sich nicht zurücknehmen und beendet auch einen Auftrag, auf den der Lauf wartet
(``zug_basis.abbrechen``) — darum erst eine Rückfrage. Ihr Knopf trägt ``bestaetigt`` und die
Marke des Laufs (wie „Neu starten“): hat sich der Lauf inzwischen bewegt, fragt der Zug neu, statt
einen anderen Stand abzubrechen. Nur der eigene Lauf dieses Gesprächs.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import resolve_locale
from boerdi.services import arbeitsstand, plan_fortsetzen
from boerdi.services.ablauf import freigabe_zug, treiber, zug
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.llm_auth import hat_zug_schluessel

AKTION: Final = "ablauf_abbrechen"


async def abbrechen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    entities = session_state.setdefault("entities", {})
    aktiv = await zug.aktiver_lauf(session, req, session_state)
    if aktiv is None:
        return await basis.nur_text(session, req, "action.ablauf.keinLauf", entities)
    v, lauf = aktiv
    lang = resolve_locale(req.environment.locale)
    params = req.action_params or {}
    marke = zug.lauf_marke(v, lauf)
    if params.get("bestaetigt") is not True or params.get("marke") != marke:
        zurueck = _zurueck(req.session_id, session_state, lang)
        # Browser-Abnahme AS-U, L-2: mit Chips des Schritts sagt die Frage, wofür sie stehen
        frage = "action.ablauf.abbrechenFrageZurueck" if zurueck else "action.ablauf.abbrechenFrage"
        antwort = await basis.nur_text(session, req, frage, entities)
        antwort.quick_replies = [zug.rueckfrage_knopf(lang, "action.ablauf.abbrechenJa", AKTION,
                                                      {"bestaetigt": True, "marke": marke}),
                                 *zurueck]
        return antwort
    # Review AS-Ua, Befund 1 (schwer): am Freigabe-Schritt wie dessen eigenes „Abbrechen“ — ein
    # angelaufener Plan wird nicht fortgesetzt, und die Antwort sagt, dass schon geschrieben wurde.
    offen = angelaufen = False
    if lauf.get("status") == treiber.WARTET_FREIGABE:
        offen = freigabe_zug.plan_offen(
            entities, marke={"ablauf": lauf.get("ablauf"), "id": lauf.get("freigabe_id")})
        angelaufen = offen or bool(lauf.get("plan_angelaufen"))
    if not await basis.abbrechen(session, v, lauf, entities,
                                 arbeitsstand.aufrufer_fuer(req.session_id)):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    if offen:
        entities.pop(plan_fortsetzen.KEY, None)
    from boerdi.services import vorgang_aktion

    antwort = await basis.nur_text(session, req, _satz(lauf, angelaufen), entities)
    antwort.quick_replies = vorgang_aktion.knoepfe(lang)
    return antwort


def _satz(lauf: dict[str, Any], plan_angelaufen: bool) -> str:
    """Was die Antwort nach dem Abbruch sagt — ehrlich über das, was weiterläuft (Review AS-Ua,
    Befunde 1 und 6)."""
    if plan_angelaufen:
        return "action.ablauf.freigabeAbgebrochenPlan"
    if lauf.get("status") == treiber.WARTET_AUFTRAG and not hat_zug_schluessel():
        # ohne den Schlüssel der Person endet der Auftrag nur hier — bei der b-api läuft er weiter
        return "action.ablauf.auftragNurHierAbgebrochen"
    return "action.ablauf.abgebrochenPerson"


def _zurueck(session_id: str, session_state: dict, lang: str) -> list[str]:
    """Der Weg zurück in den wartenden Schritt (zweites Review AS-U, Befund 1): schon der Klick auf
    „Abbrechen“ ist eine Direktaktion und verwirft eine offene Abnahme samt Chips — die Rückfrage
    bietet sie wieder an, in derselben Reihenfolge wie ``turn_assembly``."""
    from boerdi.services.ablauf import auftrag_zug, ki_schritt, wahl_zug

    einer = (ki_schritt.weiter_knopf(session_id, session_state, lang)
             or freigabe_zug.weiter_knopf(session_id, session_state, lang))
    if einer:
        return [einer]
    return (wahl_zug.aktuelle_knoepfe(session_id, session_state, lang)
            or auftrag_zug.pruefen_knoepfe(session_id, session_state, lang)[:1])
