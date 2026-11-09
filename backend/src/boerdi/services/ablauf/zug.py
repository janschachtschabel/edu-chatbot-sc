"""Abläufe im Zug (Paket A1): starten per Direktaktion, fortsetzen über die Antwort auf den offenen
Block — beides ohne Modell, im Preflight hinter derselben Sicherheitsprüfung wie jede Direktaktion
(deren Werkzeugsperren gelten auch für die Schritte).

- **Start** per Knopf (``action: ablauf_starten``, ``action_params: {ablauf}``), per Wendung
  (:func:`text_ausloeser`) oder per Modul-Antwort (:func:`modul_ausloeser` — erst übernommen,
  dann ab dem Schritt nach dem Modul): nur aktive Einträge des Katalogs (``06-ablaeufe/katalog``,
  ``ausloeser``), jede Voraussetzung erfüllt (``anmeldung``: bestätigte Person;
  eine unbekannte gilt als nicht erfüllt). Der Lauf hängt am aktiven Vorgang (sonst einem neuen;
  jedes Anlegen ist festgeschrieben, bevor der Treiber rechnet — so hält keine Sperre die Verbindung
  während der Werkzeugaufrufe).
  Hat der aktive Vorgang einen beendeten Lauf oder den Lauf eines anderen Ablaufs, schließt ihn
  :func:`_ziel_vorbereiten` und legt einen neuen an — bevor Antwort oder Treiber etwas schreiben
  (Querschnitts-Review 2026-11-06, M6). Freie Arbeit (ein Vorgang ohne Lauf) übernimmt der Ablauf;
  ein wartender Lauf desselben Ablaufs wird ersetzt.
- **Fortsetzen:** Kommt eine geprüfte Antwort auf den ``offener_block`` des Laufs, prüft
  :func:`wartet_auf` den Lauf: ausgeschaltet oder mit geänderten Schritten → ``abgebrochen`` (die
  Antwort geht den gewöhnlichen Weg). Sonst speichert ``arbeitsstand.uebernehmen`` die Antwort als
  Teil (Manifest ``schreibt``), und der Treiber setzt fort — es sei denn, ein anderer Zug hat den
  Lauf inzwischen bewegt (Hinweis „Konflikt“).
- Getippter Text während eines Laufs ist ein gewöhnlicher KI-Zug; die Kennzeile nennt Ablauf und
  Schritt.

Ausgabe wie die Ordner-Aktion: Text (Nachrichten der Schritte, ein Hinweis bei Fehler), UI-Blöcke,
eine abfragende Frage gemerkt, Nachricht gespeichert. Der Lauf und neue Teile gehen in den Vorgang
(bedingt, ein Konflikt → Hinweis).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ausloeser, ki_schritt, treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.ui_module import strukturentwurf_merken

logger = logging.getLogger(__name__)

AKTION: Final = "ablauf_starten"
#: Paket A2b: „Weiter im Ablauf“ am wartenden ``agent``-Schritt.
AKTION_WEITER: Final = ki_schritt.AKTION
_BEENDET: Final = ("fertig", "fehler", "abgebrochen")


async def starten(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Direktaktion ``ablauf_starten`` (Knopf, Schnellantwort)."""
    ablauf = laden((req.action_params or {}).get("ablauf"))
    if ablauf is None or not ausloeser.per_knopf(ablauf):
        return await basis.nur_text(session, req, "action.ablauf.unbekannt")
    return await starten_mit(session, req, session_state, ablauf, blocked_tools=blocked_tools)


def lauf_wartet(session_id: str, session_state: dict) -> bool:
    """Wartet ein Lauf dieser Person? (nur der Verweis, ohne Datenbank — für den Preflight)"""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    return isinstance(lauf, dict) and lauf.get("status") in (
        treiber.WARTET, treiber.WARTET_KI, treiber.WARTET_AUFTRAG, treiber.WARTET_FREIGABE)


def text_ausloeser(nachricht: str | None) -> AblaufArea | None:
    """Der Ablauf, dessen Wendung in ``nachricht`` vorkommt (für den Preflight) — nur mit erfüllten
    Voraussetzungen: sonst bekäme eine anonyme Frage mit der Wendung nur „bitte anmelden“ und bliebe
    unbeantwortet (Querschnitts-Review)."""
    ablauf = ausloeser.per_text(nachricht)
    return ablauf if ablauf is not None and ausloeser.erfuellt(ablauf) else None


def modul_ausloeser(geprueft: dict[str, Any] | None) -> tuple[AblaufArea, int] | None:
    """Ablauf und Startschritt für eine Modul-Antwort — nur mit erfüllten Voraussetzungen (sonst
    geht die Antwort still den gewöhnlichen Weg)."""
    treffer = ausloeser.per_modul(geprueft)
    return treffer if treffer is not None and ausloeser.erfuellt(treffer[0]) else None


async def per_modul_starten(session: Any, req: ChatRequest, session_state: dict,
                            geprueft: dict[str, Any], treffer: tuple[AblaufArea, int], *,
                            blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Die Antwort wird Teil des Vorgangs (dieser Zug erreicht ``persist`` nicht), dann rechnet der
    Treiber ab dem Schritt nach dem Modul."""
    entities = session_state.setdefault("entities", {})
    ablauf, ab = treffer
    # Review Q3, Befund 2: das Ziel steht fest, bevor die Antwort gespeichert wird — sonst landete
    # sie im beendeten Vorgang und der Lauf in einem neuen.
    if not await _ziel_vorbereiten(session, req, entities, ablauf, anlegen=True) \
            or not await arbeitsstand.uebernehmen(session, req.session_id, entities, geprueft,
                                                  nur_dieser=True):
        # Review Q3, Befund 9: ohne gespeicherte Antwort rechnete der Treiber ohne sie.
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    return await starten_mit(session, req, session_state, ablauf, ab=ab,
                             gewaehlt=treiber.gewaehlt_aus(geprueft.get("daten")),
                             blocked_tools=blocked_tools)


async def starten_mit(session: Any, req: ChatRequest, session_state: dict, ablauf: AblaufArea,
                      *, ab: int = 0, gewaehlt: list[str] | None = None,
                      blocked_tools: Iterable[str] = ()) -> ChatResponse:
    if not ausloeser.erfuellt(ablauf):
        return await basis.nur_text(session, req, "action.ablauf.anmeldung")
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    if not await _ziel_vorbereiten(session, req, entities, ablauf):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    aus = await basis.rechne(session, ablauf, treiber.starten(
        ablauf, basis.umgebung(session, req, entities, blocked_tools), ab, gewaehlt))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if vw is not None and (v is None or v.status in vorgaenge.ABGESCHLOSSEN):
        # Nachprüfung, Befund 3: inzwischen abgeschlossen oder weg (eine zweite Sitzung) — der Lauf
        # hinge sonst an einem frischen Vorgang ohne die Teile, die er davor bekam.
        basis.nicht_festgehalten(aus)
        basis.verweis_auffrischen(entities, None, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    try:
        alter_job = await _alten_auftrag_schliessen(session, v, aus)
        if v is None:
            v = await _anlegen(session, req, aufrufer, ablauf)
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    basis.bei_der_b_api_abbrechen(alter_job)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    # Ein neuer Lauf zählt seine KI-Züge neu (Review A2b, Befund 4) — erst nach dem Festhalten:
    # ein gescheiterter Neustart ließe sonst den alten Lauf mit leerem Budget weiterlaufen (Review
    # Q2, Befund 4).
    entities.pop(ki_schritt.ZUEGE_KEY, None)
    return await basis.antwort(session, req, session_state, aus, ablauf)


async def _anlegen(session: Any, req: ChatRequest, aufrufer: str, ablauf: AblaufArea) -> Any:
    return await vorgaenge.anlegen(session, aufrufer=aufrufer, session_id=req.session_id,
                                   titel=ablauf.titel.get("de") or ablauf.id, zweck=ablauf.id,
                                   tage=arbeitsstand.tage())


async def _ziel_vorbereiten(session: Any, req: ChatRequest, entities: dict[str, Any],
                            ablauf: AblaufArea, *, anlegen: bool = False) -> bool:
    """Querschnitts-Review 2026-11-06, M6 (nach Review Q3): ein beendeter Lauf lässt seinen Vorgang
    offen — der Entwurf darin bleibt erreichbar. Erst ein neuer Start schließt einen Vorgang, dessen
    Lauf beendet ist (fertig, Fehler, abgebrochen) oder einem anderen Ablauf gehört, und beginnt
    einen neuen; sonst bliebe jede Person bei einem ewigen Vorgang. Freie Arbeit (kein Lauf) und ein
    wartender Lauf desselben Ablaufs bleiben. Mit ``anlegen`` steht danach immer ein Ziel fest (ein
    neuer Vorgang, wenn keiner da ist) — der Modul-Auslöser speichert dann nur dorthin (Review Q3,
    Nachprüfung, Befund 3). ``False`` bei einem Konflikt."""
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if v is not None and v.status in vorgaenge.ABGESCHLOSSEN:
        v = None
    if v is None:
        arbeitsstand.verweis_weg(entities, aufrufer)
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if v is not None and (not isinstance(lauf, dict) or (lauf.get("ablauf") == ablauf.id
                                                         and lauf.get("status") not in _BEENDET)):
        return True
    if v is None and not anlegen:
        return True
    alter_job = None
    try:
        if v is not None:
            alter_job = await basis.schliessen(session, v)
            # Ein neues Vorhaben: der gemerkte Entwurf des alten ist kein Gegenstand mehr.
            entities.pop(strukturentwurf_merken.KEY, None)
        neu = await _anlegen(session, req, aufrufer, ablauf)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return False
    basis.bei_der_b_api_abbrechen(alter_job)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(neu, aufrufer)
    return True


async def _alten_auftrag_schliessen(session: Any, v: Any, aus: treiber.Ausgabe) -> str | None:
    """Ein neuer Lauf ersetzt einen, der auf einen Auftrag wartete — dessen Zeile gilt nicht mehr
    als offen (Querschnitts-Review). Startet der neue selbst einen, ersetzt ``ablage.anlegen``
    sie. Gibt die Job-ID des ersetzten Auftrags zurück: er endet auch bei der B-API — erst nach
    dem Festschreiben (Job-Vertrag 2026-11-07; Review, Befund 1)."""
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_AUFTRAG:
        return None
    from boerdi.services.auftraege import ablage

    if (offen := await ablage.offen(session, v.id)) is None:
        return None
    if not aus.auftrag:
        await ablage.abschliessen(session, offen, "abgebrochen")
    return offen.job_id


def _offener_lauf(v: Any, geprueft: dict[str, Any]) -> dict[str, Any] | None:
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if isinstance(lauf, dict) and lauf.get("offener_block") == geprueft.get("block_id"):
        return lauf
    return None


async def wartet_auf(session: Any, session_id: str, session_state: dict,
                    geprueft: dict[str, Any] | None) -> bool:
    """Gehört ``geprueft`` zum offenen Block eines Laufs dieser Person, der fortsetzen kann? (für
    den Preflight). Ein Lauf, der nicht mehr kann, wird hier schon ``abgebrochen`` — VOR der
    Sicherheitsprüfung; das ist nur Aufräumen von Zustand, nichts davon erreicht die Person oder ein
    Modell (Querschnitts-Review, NIT)."""
    if not geprueft:
        return False
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET:
        return False
    try:
        v = await vorgaenge.lesen(session, vw["id"], aufrufer)
        # M7: danach folgt im Preflight die Sicherheitsprüfung (Moderation, ein Netzaufruf).
        await basis.frei(session)
        if (offen := _offener_lauf(v, geprueft)) is None:
            # Review Q2, Befund 2: eine zweite Sitzung kann den Lauf weitergeschoben haben — der
            # Verweis folgt dem Vorgang (``persist`` schreibt ihn mit), sonst sperrte ein alter
            # „wartet“ Wendungen und Modul-Auslöser.
            basis.verweis_auffrischen(entities, v, aufrufer)
            return False
        ablauf = laden(offen.get("ablauf"))
        if ablauf is not None and ablauf.aktiv and treiber.kann_weiter(ablauf, offen):
            return True
        await basis.abbrechen(session, v, offen, entities, aufrufer)
    except Exception as fehler:  # noqa: BLE001 — ohne Lesen geht der Zug den gewöhnlichen Weg
        logger.warning("Ablauf: Vorgang nicht lesbar (%s)", type(fehler).__name__)
    return False


async def fortsetzen(session: Any, req: ChatRequest, session_state: dict,
                     geprueft: dict[str, Any] | None, *,
                     blocked_tools: Iterable[str] = ()) -> ChatResponse | None:
    """Gehört die geprüfte Antwort zum offenen Block eines Laufs, setzt der Treiber fort —
    sonst ``None`` (dann ist noch nichts gespeichert; der Zug geht den gewöhnlichen Weg)."""
    if not geprueft:
        return None
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = _offener_lauf(v, geprueft)
    ablauf = laden(lauf.get("ablauf")) if lauf else None
    # Review A1, Befund 6: erst prüfen, dann übernehmen — sonst speichert ``persist`` sie doppelt.
    if lauf is None or ablauf is None or not ablauf.aktiv or not treiber.kann_weiter(ablauf, lauf):
        return None
    if not await arbeitsstand.uebernehmen(session, req.session_id, entities, geprueft,
                                          nur_dieser=True):
        # Querschnitts-Review: ohne gespeicherte Antwort rechnete der Treiber auf altem Stand.
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    v = await vorgaenge.lesen(session, v.id, aufrufer)
    # Befund 7: hat ein anderer Zug den Lauf inzwischen bewegt, nicht mit dem alten fortsetzen.
    if _offener_lauf(v, geprueft) is None:
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    aus = await basis.rechne(session, ablauf, treiber.weiter(
        ablauf, dict(lauf), geprueft.get("daten") or {},
        basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)


async def weiter_nach_ki(session: Any, req: ChatRequest, session_state: dict, *,
                         blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Direktaktion ``ablauf_weiter`` (Paket A2b): der Lauf dieser Person wartet am
    ``agent``-Schritt des genannten Ablaufs → der Treiber setzt fort; fehlt dessen ``ausgabe``, ein
    Hinweis."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    gewollt = (req.action_params or {}).get("ablauf")
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_KI):
        # Querschnitts-Review M5: der Verweis folgt dem Vorgang (zweite Sitzung, verdrängt).
        basis.verweis_auffrischen(entities, v, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    ablauf = laden(gewollt)
    if ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf):
        # Review A2b, Befund 7: ein Lauf, der nicht mehr kann, wartet nicht weiter.
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    aus = await basis.rechne(session, ablauf, treiber.weiter_ki(
        ablauf, dict(lauf), basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    if aus.fehlt_teil:
        antwort = await basis.nur_text(session, req, "action.ablauf.fehltNoch")
        antwort.quick_replies = [ki_schritt.knopf(ablauf.id,
                                                  resolve_locale(req.environment.locale))]
        return antwort
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    entities.pop(ki_schritt.ZUEGE_KEY, None)
    return await basis.antwort(session, req, session_state, aus, ablauf)
