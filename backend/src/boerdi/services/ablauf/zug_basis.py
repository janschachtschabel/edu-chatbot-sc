"""Gemeinsame Bausteine der Ablauf-Züge (aus ``zug`` gelöst, Paket K1a): die Umgebung des Treibers,
Lauf und neue Teile festhalten, die Antwort bauen, den Treiber ohne 500 rufen, einen Lauf abbrechen.

Genutzt von ``zug`` (Start, Fortsetzen, Weiter) und ``auftrag_zug`` (Stand eines Auftrags).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.ui_bloecke import DEBUG_KEY, fuer_den_debug_block
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ki_schritt, treiber
from boerdi.services.db_sessions import save_message, update_session
from boerdi.ui_module.antwort import merke_frage

logger = logging.getLogger(__name__)

STATUS: Final = {treiber.WARTET: "wartet_person", treiber.WARTET_KI: "wartet_person",
                 treiber.WARTET_AUFTRAG: "wartet_auftrag",
                  "laeuft": "aktiv", "fertig": "aktiv", "fehler": "aktiv", "abgebrochen": "aktiv"}
_WARTEND: Final = (treiber.WARTET, treiber.WARTET_KI, treiber.WARTET_AUFTRAG, "laeuft")


async def mcp(name: str, args: dict[str, Any]) -> Any:
    from boerdi.services.outcome_service import call_with_outcome

    text, outcome = await call_with_outcome(name, args)
    return text if outcome.status == "success" else None


def umgebung(session: Any, req: ChatRequest, entities: dict[str, Any],
              gesperrt: Iterable[str]) -> treiber.Umgebung:
    from boerdi.services.ablauf import auftrag_zug  # zyklenfrei erst zur Laufzeit

    return treiber.Umgebung(teile=arbeitsstand.teil_lader(session, req.session_id, entities),
                            sprache=resolve_locale(req.environment.locale), mcp=mcp,
                            gesperrt=frozenset(gesperrt), auftrag_starten=auftrag_zug.starter())


async def festhalten(session: Any, v: Any, aus: treiber.Ausgabe) -> Any:
    if aus.auftrag:
        # Paket K1a: die Job-ID (nie der Schlüssel); ein neuer Auftrag ersetzt den offenen.
        from boerdi.services.auftraege import ablage

        await ablage.anlegen(session, v.id, **aus.auftrag)
    for name, typ, wert, zusammenfassung in aus.neue_teile:
        v = await vorgaenge.teil_setzen(session, v, name, typ=typ, wert=wert,
                                        zusammenfassung=zusammenfassung, tage=arbeitsstand.tage())
    return await vorgaenge.lauf_setzen(session, v, aus.lauf,
                                       status=STATUS.get(aus.lauf.get("status"), "aktiv"),
                                       tage=arbeitsstand.tage())


async def schliessen(session: Any, v: Any) -> Any:
    """Den Vorgang abschließen (``fertig``) — „neues Vorhaben“ oder der Start eines Ablaufs auf
    einem Vorgang mit beendetem oder fremdem Lauf (Querschnitts-Review 2026-11-06, M6). Ein
    wartender Lauf wird ``abgebrochen``, sein offener Auftrag ebenso. Wirft ``VorgangKonflikt``;
    der Aufrufer schreibt fest."""
    lauf = (v.akte or {}).get("lauf")
    if isinstance(lauf, dict) and lauf.get("status") in _WARTEND:
        if lauf.get("status") == treiber.WARTET_AUFTRAG:
            from boerdi.services.auftraege import ablage

            if (offen := await ablage.offen(session, v.id)) is not None:
                await ablage.abschliessen(session, offen, "abgebrochen")
        lauf = {**lauf, "status": "abgebrochen", "offener_block": None}
    return await vorgaenge.lauf_setzen(session, v, lauf if isinstance(lauf, dict) else None,
                                       status="fertig", tage=arbeitsstand.tage())


def nicht_festgehalten(aus: treiber.Ausgabe) -> None:
    """Review K1a, Befund 3: ein Konflikt nach dem Start eines Auftrags — der Auftrag läuft bei der
    b-api, ist aber nirgends festgehalten (ohne Abbruch-Schnittstelle, K21, bleibt nur das Log)."""
    if aus.auftrag:
        logger.warning("Auftrag gestartet, aber nicht festgehalten (Konflikt) — Flow %s",
                       aus.auftrag.get("flow"))


def antwort_text(lang: str, aus: treiber.Ausgabe) -> str:
    texte = list(aus.texte)
    if aus.fehler:
        texte.append(bot_text(lang, "action.ablauf.fehler"))
    elif not texte:
        texte.append(bot_text(lang, "action.ablauf.fertig" if aus.lauf.get("status") == "fertig"
                              else "action.ablauf.weiter"))
    return "\n\n".join(texte)


async def antwort(session: Any, req: ChatRequest, session_state: dict, aus: treiber.Ausgabe,
                   ablauf: AblaufArea) -> ChatResponse:
    text = antwort_text(resolve_locale(req.environment.locale), aus)
    entities = session_state.setdefault("entities", {})
    for block in aus.bloecke:
        if block.art == "abfragen":
            merke_frage(entities, block)
    await update_session(session, req.session_id, entities=entities)
    debug = DebugInfo(persona=session_state.get("persona_id", ""), intent="I03", state="S3",
                      pattern=f"ABLAUF: {ablauf.id}/{aus.lauf.get('schritt')}", tools_called=[],
                      entities=entities)
    await save_message(session, req.session_id, "assistant", text,
                       debug={**debug.model_dump(), DEBUG_KEY: fuer_den_debug_block(aus.bloecke)})
    # Paket A2b: hält der Lauf am ``agent``-Schritt, steht „Weiter im Ablauf“ darunter.
    knoepfe = ([ki_schritt.knopf(ablauf.id, resolve_locale(req.environment.locale))]
               if aus.lauf.get("status") == treiber.WARTET_KI else [])
    if aus.lauf.get("status") == treiber.WARTET_AUFTRAG:
        from boerdi.services.ablauf import auftrag_zug

        knoepfe = [auftrag_zug.knopf(ablauf.id, resolve_locale(req.environment.locale))]
    if aus.lauf.get("status") in ("fertig", "fehler", "abgebrochen"):
        # Querschnitts-Review 2026-11-06 (Review Q3, Befund 4): der Einstieg zu „neues Vorhaben“
        # und „Arbeitsstand löschen“ — ``__action__``-Knöpfe schreibt das Modell nicht.
        from boerdi.services import vorgang_aktion

        knoepfe = vorgang_aktion.knoepfe(resolve_locale(req.environment.locale))
    # Ohne Block kein ``ui`` (``None`` nähme ``ChatResponse`` nicht an — ein Lauf aus Nachricht und
    # Ende scheiterte daran seit A1).
    ui = {"ui": UiInfo(ui_bloecke=aus.bloecke)} if aus.bloecke else {}
    return ChatResponse(session_id=req.session_id, content=text, debug=debug,
                        quick_replies=knoepfe, **ui)


async def nur_text(session: Any, req: ChatRequest, schluessel: str,
                   entities: dict[str, Any] | None = None) -> ChatResponse:
    """Ein Hinweis als Antwort. Mit ``entities`` werden sie festgeschrieben (Querschnitts-Review
    2026-11-06, M5): frühe Antworten laufen nicht durch ``persist`` — ein hier aufgefrischter oder
    abgebrochener Verweis ginge sonst verloren, und ein veralteter Lauf hinge in der Sitzung."""
    if entities is not None:
        await update_session(session, req.session_id, entities=entities)
    text = bot_text(resolve_locale(req.environment.locale), schluessel)
    await save_message(session, req.session_id, "assistant", text)
    return ChatResponse(session_id=req.session_id, content=text, quick_replies=[])


def verweis_auffrischen(entities: dict[str, Any], v: Any, aufrufer: str) -> None:
    """Der Verweis nach dem Stand des Vorgangs — eine zweite Sitzung derselben Person kann den Lauf
    weitergeschoben haben (M5); ohne Vorgang fällt der Verweis weg."""
    if v is not None:
        entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    else:
        entities.pop(arbeitsstand.VERWEIS, None)


async def frei(session: Any) -> None:
    """Querschnitts-Review M7 (Audit H-5): keine offene Lese-Transaktion über Netzaufrufe."""
    await verbindung_freigeben(session)


async def rechne(session: Any, ablauf: AblaufArea,
                 aufruf: Awaitable[treiber.Ausgabe | None]) -> treiber.Ausgabe | None:
    """Den Treiber rufen — ein unerwarteter Fehler endet als Hinweis statt als 500. Vorher geht die
    Verbindung frei: der Treiber ruft MCP-Werkzeuge, Dienste und die b-api (M7)."""
    await frei(session)
    try:
        return await aufruf
    except Exception as fehler:  # noqa: BLE001 — der Zug endet mit Hinweis, der Lauf bleibt stehen
        logger.warning("Ablauf %s: Treiber fehlgeschlagen (%s)", ablauf.id, type(fehler).__name__)
        return None


async def abbrechen(session: Any, v: Any, lauf: dict[str, Any], entities: dict[str, Any],
                     aufrufer: str) -> None:
    """Ein wartender Lauf, dessen Ablauf aus ist oder dessen Schritte sich änderten (Befund 5)."""
    try:
        if lauf.get("status") == treiber.WARTET_AUFTRAG:
            # Review K1a, Befund 9: sein Auftrag gilt nicht mehr als offen.
            from boerdi.services.auftraege import ablage

            if (offen := await ablage.offen(session, v.id)) is not None:
                await ablage.abschliessen(session, offen, "abgebrochen")
        v = await vorgaenge.lauf_setzen(session, v, {**lauf, "status": "abgebrochen",
                                                     "offener_block": None},
                                        status="aktiv", tage=arbeitsstand.tage())
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return
    logger.info("Ablauf %s: wartender Lauf abgebrochen (aus oder geändert)", lauf.get("ablauf"))
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
