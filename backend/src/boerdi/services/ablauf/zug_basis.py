"""Gemeinsame Bausteine der Ablauf-Züge (aus ``zug`` gelöst, Paket K1a): die Umgebung des Treibers,
Lauf und neue Teile festhalten, die Antwort bauen, den Treiber ohne 500 rufen, einen Lauf abbrechen.

Genutzt von ``zug`` (Start, Fortsetzen, Weiter) und ``auftrag_zug`` (Stand eines Auftrags).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.db.verbindung import verbindung_freigeben
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.ui_bloecke import DEBUG_KEY, fuer_den_debug_block
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, probe, vorgaenge
from boerdi.services.ablauf import ki_schritt, treiber
from boerdi.services.db_sessions import (
    FESTER_TEXT_KEY,
    an_letzte_antwort_anhaengen,
    save_message,
    update_session,
)
from boerdi.ui_module.antwort import merke_frage

logger = logging.getLogger(__name__)

STATUS: Final = {treiber.WARTET: "wartet_person", treiber.WARTET_KI: "wartet_person",
                 treiber.WARTET_AUFTRAG: vorgaenge.WARTET_AUFTRAG,
                 treiber.WARTET_FREIGABE: "wartet_person", treiber.WARTET_WAHL: "wartet_person",
                 treiber.WARTET_SEITE: "wartet_person",
                  "laeuft": "aktiv", "fertig": "aktiv", "fehler": "aktiv", "abgebrochen": "aktiv"}
_WARTEND: Final = (*treiber.WARTEND, "laeuft")


async def mcp(name: str, args: dict[str, Any]) -> Any:
    from boerdi.services.outcome_service import call_with_outcome

    text, outcome = await call_with_outcome(name, args)
    return text if outcome.status == "success" else None


def umgebung(session: Any, req: ChatRequest, entities: dict[str, Any],
              gesperrt: Iterable[str]) -> treiber.Umgebung:
    from boerdi.services.ablauf import auftrag_zug, freigabe_zug  # zyklenfrei erst zur Laufzeit

    return treiber.Umgebung(teile=arbeitsstand.teil_lader(session, req.session_id, entities),
                            sprache=resolve_locale(req.environment.locale), mcp=mcp,
                            gesperrt=frozenset(gesperrt), auftrag_starten=auftrag_zug.starter(),
                            vorlegen=freigabe_zug.vorleger(req),
                            # AS-7a (F-6): die Seite dieses Zugs — für ``wenn_seite`` und Ankunft
                            seite=req.environment.page or "/",
                            # AS-8a (P-6): Probe der Studio-Vorschau — der Lauf merkt es sich
                            probe=probe.recht())


async def festhalten(session: Any, v: Any, aus: treiber.Ausgabe, *,
                     session_id: str | None = None) -> Any:
    if aus.auftrag:
        # Paket K1a: die Job-ID (nie der Schlüssel); ein neuer Auftrag ersetzt den offenen.
        from boerdi.services.auftraege import ablage

        await ablage.anlegen(session, v.id, **aus.auftrag)
    status = STATUS.get(aus.lauf.get("status"), "aktiv")
    if session_id and status in vorgaenge.WARTEND:
        # Paket K2a: „fortsetzen“ führt in das Gespräch, in dem der Lauf zuletzt zu warten begann —
        # auf einen Auftrag oder auf die Person (Review K2a, Befund 1: ein Gespräch B, das den Lauf
        # aus A übernahm und weiterführte, ist danach sein Gespräch, nicht mehr A).
        await vorgaenge.sitzung_setzen(session, v.id, session_id)
    for name, typ, wert, zusammenfassung in aus.neue_teile:
        v = await vorgaenge.teil_setzen(session, v, name, typ=typ, wert=wert,
                                        zusammenfassung=zusammenfassung, tage=arbeitsstand.tage())
    return await vorgaenge.lauf_setzen(session, v, aus.lauf, status=status,
                                       tage=arbeitsstand.tage())


async def schliessen(session: Any, v: Any) -> str | None:
    """Den Vorgang abschließen (``fertig``) — „neues Vorhaben“ oder der Start eines Ablaufs auf
    einem Vorgang mit beendetem oder fremdem Lauf (Querschnitts-Review 2026-11-06, M6). Ein
    wartender Lauf wird ``abgebrochen``, sein offener Auftrag ebenso. Wirft ``VorgangKonflikt``;
    der Aufrufer schreibt fest — und gibt die zurückgegebene Job-ID erst danach an
    :func:`bei_der_b_api_abbrechen` (Review Job-Vertrag, Befund 1)."""
    lauf = (v.akte or {}).get("lauf")
    job_id = None
    if isinstance(lauf, dict) and lauf.get("status") in _WARTEND:
        if lauf.get("status") == treiber.WARTET_AUFTRAG:
            from boerdi.services.auftraege import ablage

            if (offen := await ablage.offen(session, v.id)) is not None:
                await ablage.abschliessen(session, offen, "abgebrochen")
                job_id = offen.job_id
        lauf = {**lauf, "status": "abgebrochen", "offener_block": None}
    await vorgaenge.lauf_setzen(session, v, lauf if isinstance(lauf, dict) else None,
                                status="fertig", tage=arbeitsstand.tage())
    return job_id


def nicht_festgehalten(aus: treiber.Ausgabe) -> None:
    """Review K1a, Befund 3: ein Konflikt nach dem Start eines Auftrags — der Auftrag läuft bei der
    b-api, ist aber nirgends festgehalten. Seit dem Job-Vertrag (K21 geklärt) endet er dort auch;
    der Aufrufer hat schon zurückgerollt."""
    if aus.auftrag:
        logger.warning("Auftrag gestartet, aber nicht festgehalten (Konflikt) — Flow %s",
                       aus.auftrag.get("flow"))  # log-ok: Flow-Name aus der Konfiguration
        bei_der_b_api_abbrechen(aus.auftrag.get("job_id"))


def antwort_text(lang: str, aus: treiber.Ausgabe) -> str:
    texte = list(aus.texte)
    if aus.fehler:
        texte.append(bot_text(lang, "action.ablauf.fehler"))
    elif not texte:
        texte.append(bot_text(lang, "action.ablauf.fertig" if aus.lauf.get("status") == "fertig"
                              else "action.ablauf.weiter"))
    return "\n\n".join(texte)


#: Querschnitts-Review TW, Befunde 3/4 (N16): der Ablauf, aus dem die Person eben ausgestiegen
#: ist („Ohne Ablauf“ oder „Abbrechen“), und bis zu welchem Zug er nicht von selbst startet.
AUSSTIEG_KEY: Final = "_ablauf_ausstieg"
#: So viele Züge gilt die Marke — kurz genug, dass niemand ausgesperrt bleibt.
AUSSTIEG_ZUEGE: Final = 3
#: Die Direktaktion, die einen Ablauf per Knopf startet (``zug.AKTION``; hier ohne Import-Zirkel).
_START_AKTION: Final = "ablauf_starten"


def ausstieg_merken(session_state: dict, ablauf_id: Any) -> None:
    """Den Ausstieg aus ``ablauf_id`` für die nächsten :data:`AUSSTIEG_ZUEGE` Züge merken."""
    if isinstance(ablauf_id, str) and ablauf_id:
        zug_nr = int(session_state.get("turn_count") or 0)
        session_state.setdefault("entities", {})[AUSSTIEG_KEY] = {
            "ablauf": ablauf_id, "bis": zug_nr + AUSSTIEG_ZUEGE}


def abgelehnt(_session_id: str, session_state: dict) -> str | None:
    """Der Ablauf, aus dem die Person in den letzten Zügen ausgestiegen ist — er startet nicht von
    selbst (Wendung, Modul-Antwort, Werkzeug der KI); ``None`` sonst."""
    marke = (session_state.get("entities") or {}).get(AUSSTIEG_KEY)
    if not isinstance(marke, dict) or not isinstance(marke.get("ablauf"), str):
        return None
    if int(session_state.get("turn_count") or 0) >= int(marke.get("bis") or 0):
        return None
    return marke["ablauf"]


def _ist_ausstieg(ablauf: AblaufArea, aus: treiber.Ausgabe) -> bool:
    """Endete der Lauf an einem ``ende`` mit ``ausstieg``?"""
    if aus.lauf.get("status") != "fertig":
        return False
    schritt = next((s for s in ablauf.schritte if s.id == aus.lauf.get("schritt")), None)
    return schritt is not None and bool(schritt.ausstieg)


def doch_knopf(ablauf_id: str, lang: str) -> str:
    """„Doch mit Ablauf“ — startet ihn per Knopf (der Ausstieg sperrt nur die Selbststarts)."""
    label = bot_text(lang, "action.ablauf.dochMitAblauf").replace("|", "/")
    return f"__action__|{label}|{_START_AKTION}|" + json.dumps({"ablauf": ablauf_id},
                                                              ensure_ascii=False)


async def antwort(session: Any, req: ChatRequest, session_state: dict, aus: treiber.Ausgabe,
                   ablauf: AblaufArea, *, anhaengen: bool = False) -> ChatResponse:
    """Die Antwort des Laufs — gespeichert als eigene Nachricht, mit ``anhaengen`` (Paket R2-f)
    an die eben gespeicherte Antwort desselben Zuges (das Einlösen einer Freigabe)."""
    text = antwort_text(resolve_locale(req.environment.locale), aus)
    entities = session_state.setdefault("entities", {})
    for block in aus.bloecke:
        if block.art == "abfragen":
            merke_frage(entities, block)
    if aus.freigabe is not None:
        # Paket S: die vorgelegte Änderung als offene Abnahme (wie im Chat) — mit Vorschau-Box.
        from boerdi.services.ablauf import freigabe_zug

        aus.bloecke.append(freigabe_zug.merken(entities, aus.freigabe, ablauf.id,
                                               resolve_locale(req.environment.locale)))
    # Zweites Review TW, Befund 1: der Ausstieg wird gemerkt, BEVOR die Sitzung gespeichert wird —
    # sonst lädt der nächste Zug die Entities ohne Marke, und die Schleife bliebe
    ausgestiegen = _ist_ausstieg(ablauf, aus)
    if ausgestiegen:
        ausstieg_merken(session_state, ablauf.id)
    await update_session(session, req.session_id, entities=entities)
    # Review S2/S3, Befund 1: ohne ``_``-Schlüssel wie ``turn_persist`` — die offene Abnahme trägt
    # den Schlüssel, ein offener Plan den seinen. Zweite Sicherung neben dem Validator von
    # ``DebugInfo`` (``schemas_debug._ohne_interne_schluessel``).
    debug = DebugInfo(persona=session_state.get("persona_id", ""), intent="I03", state="S3",
                      pattern=f"ABLAUF: {ablauf.id}/{aus.lauf.get('schritt')}", tools_called=[],
                      entities={k: v for k, v in entities.items() if not k.startswith("_")})
    # AS-Ua (U-7, Review Befund 2): fest nur ohne eingesetzten KI-Inhalt und ohne Modul-Blöcke —
    # ein Block kann einen Entwurf der KI zeigen. Ein Etikett zu viel ist hinnehmbar.
    fest = not aus.ki_inhalt and not aus.bloecke
    gespeichert = {**debug.model_dump(), DEBUG_KEY: fuer_den_debug_block(aus.bloecke),
                   **({FESTER_TEXT_KEY: True} if fest else {})}
    if not (anhaengen and await an_letzte_antwort_anhaengen(session, req.session_id, text,
                                                            gespeichert)):
        await save_message(session, req.session_id, "assistant", text, debug=gespeichert)
    # Paket A2b: hält der Lauf am ``agent``-Schritt, steht „Weiter im Ablauf“ darunter.
    knoepfe = ([ki_schritt.knopf(ablauf.id, resolve_locale(req.environment.locale))]
               if aus.lauf.get("status") == treiber.WARTET_KI else [])
    if knoepfe and (start := ki_schritt.start_knopf(
            ablauf, str(aus.lauf.get("schritt")), resolve_locale(req.environment.locale))):
        # TW-3: beim Eintritt in den KI-Schritt zuerst der Startknopf (sein Text geht an die KI)
        knoepfe.insert(0, start)
    if aus.lauf.get("status") == treiber.WARTET_AUFTRAG:
        from boerdi.services.ablauf import auftrag_zug

        knoepfe = auftrag_zug.knoepfe(ablauf.id, resolve_locale(req.environment.locale))
    if aus.lauf.get("status") == treiber.WARTET_FREIGABE:
        from boerdi.services.ablauf import freigabe_zug

        knoepfe = freigabe_zug.knoepfe(ablauf.id, resolve_locale(req.environment.locale),
                                       vorgelegt=aus.freigabe is not None)
    if aus.lauf.get("status") == treiber.WARTET_WAHL:
        # AS-3a: die Schnellantworten des Schritts als Chips
        from boerdi.services.ablauf import wahl_zug

        knoepfe = wahl_zug.knoepfe(ablauf.id, aus.wahl)
    if aus.lauf.get("status") in ("fertig", "fehler", "abgebrochen"):
        # Querschnitts-Review 2026-11-06 (Review Q3, Befund 4): der Einstieg zu „neues Vorhaben“
        # und „Arbeitsstand löschen“ — ``__action__``-Knöpfe schreibt das Modell nicht.
        from boerdi.services import vorgang_aktion

        knoepfe = vorgang_aktion.knoepfe(resolve_locale(req.environment.locale))
        if ausgestiegen:
            # Querschnitts-Review TW, Befund 14: nach „Ohne Ablauf“ der Weg zurück, nicht
            # „Neues Vorhaben“ (die Marke steht schon, oben vor dem Speichern)
            knoepfe = [doch_knopf(ablauf.id, resolve_locale(req.environment.locale))]
    if aus.navigation:
        # AS-7a (F-2): die Wege der ``seite``-Schritte — vorn, auch wenn es danach weiterging
        from boerdi.services.ablauf import seite_zug

        knoepfe = [*dict.fromkeys(seite_zug.knopf(n) for n in aus.navigation), *knoepfe]
    # Ohne Block kein ``ui`` (``None`` nähme ``ChatResponse`` nicht an — ein Lauf aus Nachricht und
    # Ende scheiterte daran seit A1).
    return ChatResponse(session_id=req.session_id, content=text, debug=debug,
                        quick_replies=knoepfe,
                        ui=UiInfo(ui_bloecke=list(aus.bloecke), fester_text=fest))


async def nur_text(session: Any, req: ChatRequest, schluessel: str,
                   entities: dict[str, Any] | None = None) -> ChatResponse:
    """Ein Hinweis als Antwort. Mit ``entities`` werden sie festgeschrieben (Querschnitts-Review
    2026-11-06, M5): frühe Antworten laufen nicht durch ``persist`` — ein hier aufgefrischter oder
    abgebrochener Verweis ginge sonst verloren, und ein veralteter Lauf hinge in der Sitzung."""
    if entities is not None:
        await update_session(session, req.session_id, entities=entities)
    text = bot_text(resolve_locale(req.environment.locale), schluessel)
    await save_message(session, req.session_id, "assistant", text, debug={FESTER_TEXT_KEY: True})
    return ChatResponse(session_id=req.session_id, content=text, quick_replies=[],
                        ui=UiInfo(fester_text=True))


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


def bei_der_b_api_abbrechen(*job_ids: str | None) -> None:
    """Der Auftrag gilt hier nicht mehr — die B-API soll ihn auch beenden (Kosten, Grenze von 20
    offenen Jobs je Schlüssel). Nur mit dem Schlüssel der Person: mit ``B_API_KEY`` wäre der Job
    fremd (404). Im Hintergrund, ohne zu warten oder zu werfen.

    Erst NACH dem Festschreiben aufrufen (Review Job-Vertrag, Befund 1): ein Abbruch vor einem
    Konflikt-Rollback beendete einen Auftrag, auf den der Lauf eines anderen Zuges noch wartet."""
    from boerdi.services.auftraege import client
    from boerdi.services.llm_auth import hat_zug_schluessel

    if not hat_zug_schluessel():
        return
    for job_id in job_ids:
        if job_id:
            client.abbrechen_im_hintergrund(job_id)


async def abbrechen(session: Any, v: Any, lauf: dict[str, Any], entities: dict[str, Any],
                    aufrufer: str, *, bei_der_b_api: bool = True) -> bool:
    """Ein wartender Lauf, dessen Ablauf aus ist oder dessen Schritte sich änderten (Befund 5) —
    oder den die Person abbricht (K2b). Ohne ``bei_der_b_api`` (der Schlüssel wurde gerade
    abgewiesen) kein DELETE hinterher. ``False`` bei einem Konflikt (nichts geändert)."""
    job_id = None
    try:
        if lauf.get("status") == treiber.WARTET_AUFTRAG:
            # Review K1a, Befund 9: sein Auftrag gilt nicht mehr als offen.
            from boerdi.services.auftraege import ablage

            if (offen := await ablage.offen(session, v.id)) is not None:
                await ablage.abschliessen(session, offen, "abgebrochen")
                job_id = offen.job_id
        v = await vorgaenge.lauf_setzen(session, v, {**lauf, "status": "abgebrochen",
                                                     "offener_block": None},
                                        status="aktiv", tage=arbeitsstand.tage())
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return False
    if bei_der_b_api:
        bei_der_b_api_abbrechen(job_id)
    logger.info("Ablauf %s: wartender Lauf abgebrochen", lauf.get("ablauf"))
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return True
