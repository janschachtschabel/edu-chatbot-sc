"""Paket N4 (Plan 2026-11-19): „Freigeben“ und „Abbrechen“ an der Freigabe-Box eines Auftrags.

Nur als Direktaktion (Knopf der Box), nie über einen Text — weder der Person noch des Modells:
``ablauf_auftrag_freigeben {ablauf, id}`` und ``ablauf_auftrag_verwerfen {ablauf, id}``.

- **Freigeben** löst ein nur mit persönlicher Anmeldung und Schreibrecht, nur für denselben
  Aufrufer (``auftrag_freigabe.offen``: Muster ``caller_fingerprint``), nur für die Vorlage, auf
  die der Lauf gerade wartet (``freigabe_id``). Die Freigabe wird **vor** dem Aufruf des MCP aus der
  Sitzung genommen und festgeschrieben: ein zweites „Freigeben“ findet nichts mehr und startet
  keinen zweiten Job (bis zum MCP durchgerutscht, antwortet er ``replayed`` mit demselben Job).
- Abgelaufen (eigene Frist oder ``confirm_expired``/``confirm_mismatch`` des MCP): eine neue
  Vorschau, die Person gibt neu frei — nichts scheitert.
- **Abbrechen** startet nichts; der Lauf nimmt den Ersatzweg (``bei_fehler``) mit einem Satz.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import (
    auftrag_freigabe,
    auftrag_zug,
    freigabe_zug,
    seite_zug,
    treiber,
    wahl_zug,
)
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.mcp import auth as mcp_auth

logger = logging.getLogger(__name__)

AKTION_FREIGEBEN: Final = "ablauf_auftrag_freigeben"
AKTION_VERWERFEN: Final = "ablauf_auftrag_verwerfen"
AKTIONEN: Final = frozenset({AKTION_FREIGEBEN, AKTION_VERWERFEN})


async def _wartender_lauf(session: Any, req: ChatRequest, entities: dict[str, Any]) -> Any:
    """Vorgang, Lauf, Ablauf und Aufrufer, wenn der Lauf auf GENAU diese Vorlage wartet (Ablauf,
    ``id`` der Direktaktion, Auftragsschritt) — sonst die Antwort des Zugs."""
    params = req.action_params or {}
    # ``stumm``: wartet der Lauf woanders, frischt ``_laden`` den Verweis auf und sagt nichts
    geladen = await freigabe_zug._laden(session, req, entities, params.get("ablauf"), stumm=True)
    if not isinstance(geladen, tuple):
        return await _nicht_mehr_offen(session, req, entities)
    v, lauf, ablauf, aufrufer = geladen
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if (schritt is None or schritt.typ != "auftrag" or not params.get("id")
            or lauf.get("freigabe_id") != params.get("id")):
        return await _nicht_mehr_offen(session, req, entities)
    return v, lauf, ablauf, aufrufer


def _knoepfe_jetzt(session_id: str, entities: dict[str, Any], lang: str) -> list[str]:
    """Durchtest N4 (19.11.): die Chips der Stelle, an der der Lauf jetzt wartet — wie unter
    einer gewöhnlichen Antwort (``turn_assembly``)."""
    state = {"entities": entities}
    if knopf := freigabe_zug.weiter_knopf(session_id, state, lang):
        return [knopf]
    return (wahl_zug.aktuelle_knoepfe(session_id, state, lang)
            or seite_zug.aktueller_knopf(session_id, state, lang)
            or auftrag_zug.pruefen_knoepfe(session_id, state, lang))


async def _nicht_mehr_offen(session: Any, req: ChatRequest, entities: dict[str, Any]
                            ) -> ChatResponse:
    """Eine veraltete Freigabe: „nicht mehr offen“ und die Chips von jetzt."""
    lang = resolve_locale(req.environment.locale)
    return await basis.fester_text(session, req,
                                   bot_text(lang, "action.ablauf.freigabeNichtMehrOffen"),
                                   entities, _knoepfe_jetzt(req.session_id, entities, lang))


async def _weiter(session: Any, req: ChatRequest, state: dict, geladen: Any, aus: Any,
                  vorweg: str | None = None) -> ChatResponse:
    """Lauf festschreiben (samt gestartetem Auftrag) und antworten. Ein Konflikt nach dem Start
    beendet den Job wieder (wie jeder Start, ``nicht_festgehalten``)."""
    v, _lauf, ablauf, aufrufer = geladen
    entities = state.setdefault("entities", {})
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        await basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    if vorweg:
        aus.texte.insert(0, vorweg)
    return await basis.antwort(session, req, state, aus, ablauf)


async def _neu_vorlegen(session: Any, req: ChatRequest, state: dict, geladen: Any,
                        blocked_tools: Iterable[str]) -> ChatResponse:
    """Der Schlüssel gilt nicht mehr — eine neue Vorschau (neue Box), die Person gibt neu frei."""
    _v, lauf, ablauf, _a = geladen
    entities = state.setdefault("entities", {})
    aus = await basis.rechne(session, ablauf, treiber.erneut_vorlegen(
        ablauf, dict(lauf), basis.umgebung(session, req, entities, blocked_tools)))
    lang = resolve_locale(req.environment.locale)
    # Review N4 (3): der Satz nur, wenn wirklich eine neue Box kommt
    satz = (bot_text(lang, "action.ablauf.auftragFreigabeNeu")
            if aus is not None and aus.auftrag_freigabe is not None else None)
    return await _weiter(session, req, state, geladen, aus, satz)


#: Ergebnis von :func:`starten`: der Schlüssel gilt nicht mehr, eine neue Vorschau ist nötig.
NEU_VORLEGEN: Final = "neu_vorlegen"


async def starten(ablauf: Any, lauf: dict[str, Any], umgebung: treiber.Umgebung,
                  offen: dict[str, Any]) -> treiber.Ausgabe | str | None:
    """Der Kern von „Freigeben“ ohne Sitzung: mit dem gespeicherten Schlüssel bestätigen und den
    Lauf fortsetzen — :data:`NEU_VORLEGEN`, wenn der Schlüssel abgelaufen ist (eigene Frist oder
    ``confirm_expired``/``confirm_mismatch``). Vorübergehend (429 ohne offenen Ausgang, Werkzeug
    kurz weg) geht es zurück an die Rückfrage."""
    if auftrag_freigabe.abgelaufen(offen):
        return NEU_VORLEGEN
    waehle = getattr(umgebung.auftrag_starten, "fuer", None)
    traeger = waehle(True) if callable(waehle) else None
    job = (await traeger.bestaetigen(str(offen["flow"]), dict(offen["args"]), str(offen["token"]))
           if traeger is not None else None)
    if job is None and traeger is not None and traeger.grund_des_fehlers == "abgelaufen":
        return NEU_VORLEGEN
    satz = traeger.hinweis(umgebung.sprache) if traeger is not None else None
    if job is None and not satz:
        satz = bot_text(umgebung.sprache, "action.ablauf.freigabeOhneAnmeldung" if traeger is None
                        else "action.ablauf.auftragAbgelehnt")
    zurueck = job is None and traeger is not None and traeger.voruebergehend()
    return await treiber.weiter_nach_freigabe(ablauf, dict(lauf), umgebung, job, satz,
                                              zurueck=zurueck)


async def freigeben(session: Any, req: ChatRequest, state: dict, *,
                    blocked_tools: Iterable[str] = ()) -> ChatResponse:
    entities = state.setdefault("entities", {})
    # nur die persönliche Anmeldung, nie das Gastkonto (``schreiben_erlaubt`` ließe es zu)
    if not mcp_auth.has_personal_auth():
        return await basis.nur_text(session, req, "action.ablauf.freigabeOhneAnmeldung")
    params = req.action_params or {}
    offen = auftrag_freigabe.offen(entities, params.get("ablauf"))
    marke = (offen or {}).get("marke") or {}
    if offen is None or not params.get("id") or marke.get("id") != params.get("id"):
        logger.info("Ablauf: Freigabe eines Auftrags nicht offen (fremd, verbraucht oder alt)")
        return await _nicht_mehr_offen(session, req, entities)
    geladen = await _wartender_lauf(session, req, entities)
    if isinstance(geladen, ChatResponse):
        return geladen
    # Zuerst weg damit und festschreiben — ein zweites „Freigeben“ findet nichts mehr
    entities.pop(auftrag_freigabe.KEY, None)
    await basis.update_session(session, req.session_id, entities=entities)
    _v, lauf, ablauf, _a = geladen
    aus = await basis.rechne(session, ablauf, starten(
        ablauf, lauf, basis.umgebung(session, req, entities, blocked_tools), offen))
    if aus == NEU_VORLEGEN:
        return await _neu_vorlegen(session, req, state, geladen, blocked_tools)
    return await _weiter(session, req, state, geladen, aus if not isinstance(aus, str) else None)


async def verwerfen(session: Any, req: ChatRequest, state: dict, *,
                    blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """„Abbrechen“: nichts starten, der Ersatzweg mit einem Satz."""
    entities = state.setdefault("entities", {})
    geladen = await _wartender_lauf(session, req, entities)
    if isinstance(geladen, ChatResponse):
        return geladen
    entities.pop(auftrag_freigabe.KEY, None)
    _v, lauf, ablauf, _a = geladen
    lang = resolve_locale(req.environment.locale)
    aus = await basis.rechne(session, ablauf, treiber.weiter_nach_freigabe(
        ablauf, dict(lauf), basis.umgebung(session, req, entities, blocked_tools), None,
        bot_text(lang, "action.ablauf.auftragVerworfen")))
    return await _weiter(session, req, state, geladen, aus)
