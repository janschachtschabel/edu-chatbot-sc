"""Abläufe im Zug (Paket A1): starten per Direktaktion, fortsetzen über die Antwort auf den offenen
Block — beides ohne Modell, im Preflight hinter derselben Sicherheitsprüfung wie jede Direktaktion
(deren Werkzeugsperren gelten auch für die Schritte).

- **Start** per Knopf (``action: ablauf_starten``, ``action_params: {ablauf}``), per Wendung
  (:func:`text_ausloeser`) oder per Modul-Antwort (:func:`modul_ausloeser` — erst übernommen,
  dann ab dem Schritt nach dem Modul): nur aktive Abläufe (``06-ablaeufe/<id>``, seit AS-0 ein
  Dokument je Ablauf; ``ausloeser``), jede Voraussetzung erfüllt (``anmeldung``: bestätigte Person;
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

import hashlib
import json
import logging
from collections.abc import Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, probe, vorgaenge
from boerdi.services.ablauf import ausloeser, ki_schritt, startdaten, treiber, typen, werkzeuge
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.arbeitsstand_teile import BEREITSTELLUNG
from boerdi.ui_module import strukturentwurf_merken

logger = logging.getLogger(__name__)

AKTION: Final = "ablauf_starten"
#: Paket A2b: „Weiter im Ablauf“ am wartenden ``agent``-Schritt.
AKTION_WEITER: Final = ki_schritt.AKTION
_BEENDET: Final = treiber.BEENDET


async def starten(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Direktaktion ``ablauf_starten`` (Knopf, Schnellantwort; AS-4a auch die Gastseite mit
    ``action_params.start``). Startdaten nimmt ein Ablauf mit dem Auslöser ``extern`` oder
    (AS-5a, Knopf eines KI-Vorschlags) ``agent``.

    Die Herkunft „Gastseite“ (Rechte aus Entscheid AS-4a, Befund 10) wird nur **positiv**
    festgestellt: ``quelle: "gastseite"`` (die Widget-API schickt es immer) oder die Marke
    ``start_quelle`` am Knopf „Neu starten“, den nur ein Start der Gastseite erzeugt. Nie allein aus
    vorhandenen Startdaten (ab AS-5 bringt auch ein Vorschlag der KI Daten) und nie aus
    ``ChatRequest.from_host`` — das ist nur Anzeige (Querschnitts-Review RB, Befunde 1 und 9)."""
    params = req.action_params or {}
    ablauf = laden(params.get("ablauf"))
    # AS-8a (P-6/P-7): die Probe der Studio-Vorschau startet jeden Ablauf des Katalogs, auch einen
    # ausgeschalteten, wie von der Gastseite — mit Startdaten nach seinem Startschema.
    in_probe = probe.recht()          # Review AS-8a, Befund 4: nur mit dem Cookie dieses Zuges
    extern = ablauf is not None and (in_probe or ausloeser.per_extern(ablauf))
    if ablauf is None or not (extern or ausloeser.per_knopf(ablauf)):
        return await basis.nur_text(session, req, "action.ablauf.unbekannt")
    roh = params.get("start")
    # AS-5a (A5-4): Daten auch beim Knopf eines KI-Vorschlags (Auslöser ``agent``) — Eingaben, nie
    # Rechte: der Knopf kommt vom Client zurück und kann nicht mehr als die Gastseite.
    if roh is not None and not (in_probe or ausloeser.nimmt_daten(ablauf)):
        return await basis.nur_text(session, req, "action.ablauf.unbekannt")
    start = None
    if ablauf.start or roh is not None:
        start, fehler = startdaten.pruefen(ablauf, roh)
        if fehler:
            # nur die Zahl — die Codes nennen Feldnamen der Gastseite (Log ohne Inhalt)
            logger.info("Ablauf: Startdaten abgewiesen (%d Befunde)", len(fehler))
            return await basis.nur_text(session, req, "action.ablauf.startdaten")
        start = start if ablauf.start else None
    ersetzt = params.get("ersetzt")
    # Review AS-5a, Befund 1: nur ein Ablauf mit dem Auslöser „Gastseite“ bekommt deren Rechte;
    # die Marke ``start_quelle`` gilt nur am Knopf „Neu starten“ (Querschnitt AS-5, Befund 9).
    von_der_gastseite = extern and (
        params.get("quelle") == startdaten.QUELLE_GASTSEITE
        or (ersetzt is not None and params.get("start_quelle") == startdaten.QUELLE_GASTSEITE))
    # Querschnitts-Review AS-5, Befund 1 (schwer): auch der Knopf eines KI-Vorschlags kommt ohne
    # Überlegung der Person zustande — er ersetzt nie still einen laufenden Lauf (samt Auftrag).
    von_der_ki = params.get("start_quelle") == startdaten.QUELLE_KI
    herkunft = (startdaten.QUELLE_GASTSEITE if von_der_gastseite
                else startdaten.QUELLE_KI if von_der_ki else None)
    if params.get("quelle") == "gastseite" or ersetzt is not None or von_der_ki:
        aktiv = await _aktiver_lauf(session, req, session_state)
        if aktiv is not None:
            v, lauf = aktiv
            if ersetzt is not None:
                # Der Knopf „Neu starten“ ersetzt nur den Lauf, für den er gefragt hat — hat der
                # sich bewegt (ein zweiter Klick, weitergeführt), fragt er neu (Nachprüfung
                # Querschnitt AS-4, Befund 4).
                if ersetzt != _marke(v, lauf):
                    return await _ersetzen_fragen(session, req, ablauf, start, v, lauf, herkunft)
            elif lauf.get("ablauf") == ablauf.id and await _gleiche_startdaten(
                    session, v, ablauf, start):
                # Review AS-4b, Befund 1: derselbe Start — es geht weiter, wo er steht
                return await basis.nur_text(session, req, "action.ablauf.laeuftSchon")
            else:
                # Die Gastseite (und der Vorschlag der KI) ersetzt nie still einen Lauf, der noch
                # nicht beendet ist (Querschnitts-Review AS-4, Befund 1; AS-5, Befund 1).
                return await _ersetzen_fragen(session, req, ablauf, start, v, lauf, herkunft)
    elif (aktiv := await _aktiver_lauf(session, req, session_state)) is not None \
            and aktiv[1].get("status") == treiber.WARTET_AUFTRAG:
        # Paket K, Review B1: auch ein gewöhnlicher Start-Knopf beendet einen Lauf, der auf einen
        # Auftrag wartet (nach „Später weitermachen“ oder bei ``warten: frei``), nie still samt
        # Auftrag und Vorgang — erst die Rückfrage wie bei der Gastseite, mit „Stand prüfen“
        return await _ersetzen_fragen(session, req, ablauf, start, *aktiv, herkunft)
    # Nur Daten, die ausdrücklich von der Gastseite kommen (oder von ihrem Knopf „Neu starten“),
    # tragen ihre Rechte; Daten eines KI-Vorschlags heißen ``ki`` (ohne Rechte), alles andere hat
    # keine Herkunft.
    quelle = herkunft if roh is not None else None
    return await starten_mit(session, req, session_state, ablauf, start=start,
                             start_quelle=quelle, blocked_tools=blocked_tools)


async def _gleiche_startdaten(session: Any, v: Any, ablauf: AblaufArea,
                              start: dict[str, Any] | None) -> bool:
    """Trägt der Vorgang schon dieselben Startdaten (ohne Startschema: immer)?"""
    if not ablauf.start:
        return True
    return (await vorgaenge.teil_wert(session, v, typen.START_TEIL) or {}) == (start or {})


async def _aktiver_lauf(session: Any, req: ChatRequest, session_state: dict
                        ) -> tuple[Any, dict[str, Any]] | None:
    """Vorgang und Lauf des Gesprächs, solange der Lauf nicht beendet ist."""
    entities = session_state.get("entities") or {}
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if v is None or v.status in vorgaenge.ABGESCHLOSSEN:
        return None
    lauf = (v.akte or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") in _BEENDET:
        return None
    return v, lauf


#: So groß darf der Knopf „Neu starten“ samt Startdaten werden — das Schema erlaubt 10 Felder zu
#: höchstens 500 Zeichen (Nachprüfung Querschnitt AS-4, Befund 3).
_KNOPF_ZEICHEN: Final = 8000


def _marke(v: Any, lauf: dict[str, Any]) -> str:
    """Kurz und ohne Inhalt: welcher Lauf in welchem Stand gemeint ist."""
    roh = "|".join(str(x) for x in (v.id, lauf.get("ablauf"), lauf.get("schritt"),
                                    lauf.get("status"), lauf.get("fassung")))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def _knopf(lang: str, schluessel: str, aktion: str, params: dict[str, Any]) -> str:
    label = bot_text(lang, schluessel).replace("|", "/")
    return f"__action__|{label}|{aktion}|" + json.dumps(params, ensure_ascii=False)


async def _ersetzen_fragen(session: Any, req: ChatRequest, ablauf: AblaufArea,
                           start: dict[str, Any] | None, v: Any, lauf: dict[str, Any],
                           herkunft: str | None = None) -> ChatResponse:
    """Die Person entscheidet: „Neu starten“ (ohne ``quelle``, gebunden an diesen Lauf) oder,
    wartet der Lauf auf einen Auftrag, „Stand prüfen“. Beide überstehen jeden Deckel der
    Schnellantworten (``domain/wahl_knopf``)."""
    from boerdi.services.ablauf import auftrag_zug

    lang = resolve_locale(req.environment.locale)
    marke = _marke(v, lauf)
    # ohne ``quelle`` (sonst bremste der Knopf sich selbst), aber mit der Herkunft der Daten
    # Die Herkunft reist mit — die Gastseite nur mit Daten, die KI immer (ihr Knopf bremst so
    # auch beim zweiten Mal).
    marke_herkunft = ({"start_quelle": herkunft} if herkunft == startdaten.QUELLE_KI
                      or (herkunft and start) else {})
    neu = _knopf(lang, "action.ablauf.neuStarten", AKTION,
                 {"ablauf": ablauf.id, **({"start": start} if start else {}), "ersetzt": marke,
                  **marke_herkunft})
    if len(neu) > _KNOPF_ZEICHEN:
        return await basis.nur_text(session, req, "action.ablauf.ersetzenOhneKnopf")
    antwort = await basis.nur_text(session, req, "action.ablauf.ersetzen")
    knoepfe = [neu]
    if lauf.get("status") == treiber.WARTET_AUFTRAG and isinstance(lauf.get("ablauf"), str):
        knoepfe.append(_knopf(lang, "action.ablauf.auftragKnopf", auftrag_zug.AKTION,
                              {"ablauf": lauf["ablauf"], "ersetzt": marke}))
    return antwort.model_copy(update={"quick_replies": knoepfe})


#: Durchtest Paket K (19.11.): auch eine Wendung an einer wartenden Frage fragt so
#: (``wendung_zug.wendung_beantworten``).
ersetzen_fragen = _ersetzen_fragen


def neu_starten_knopf(lang: str, ablauf_id: str, v: Any, lauf: dict[str, Any]) -> str:
    """Drittes Review Paket K: „Neu starten“ für ``ablauf_id``, gebunden an diesen Lauf (wie in
    :func:`_ersetzen_fragen`) — hat er sich bewegt, fragt :func:`starten` neu."""
    return _knopf(lang, "action.ablauf.neuStarten", AKTION,
                  {"ablauf": ablauf_id, "ersetzt": _marke(v, lauf)})


def lauf_wartet(session_id: str, session_state: dict) -> bool:
    """Wartet ein Lauf dieser Person? (nur der Verweis, ohne Datenbank — für den Preflight)"""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    return isinstance(lauf, dict) and lauf.get("status") in treiber.WARTEND


# Querschnitts-Review TW, Befunde 3/4: der Ausstieg ist eine kurze Marke (``zug_basis``).
abgelehnt = basis.abgelehnt
ausstieg_merken = basis.ausstieg_merken
AUSSTIEG_ZUEGE = basis.AUSSTIEG_ZUEGE


def text_ausloeser(nachricht: str | None, ohne: str | None = None) -> AblaufArea | None:
    """Der Ablauf, dessen Wendung in ``nachricht`` vorkommt (für den Preflight) — nur mit erfüllten
    Voraussetzungen: sonst bekäme eine anonyme Frage mit der Wendung nur „bitte anmelden“ und bliebe
    unbeantwortet (Querschnitts-Review). Nie ``ohne`` (der eben abgelehnte, :func:`abgelehnt`)."""
    ablauf = ausloeser.per_text(nachricht)
    if ablauf is None or ablauf.id == ohne:
        return None
    return ablauf if ausloeser.erfuellt(ablauf) else None


def tour_chip(req: ChatRequest) -> AblaufArea | None:
    """Plan 2026-11-20, G2c: der Tour-Chip der Begrüßung (``tour_action: start``), den die
    eingebaute Tour nicht genommen hat (sie ist aus) — der aktive Ablauf mit dem Merkmal
    ``tour_chip`` (Review G2, MINOR 7: nicht mehr über eine Wendung im Text des Chips), mit Knopf
    und erfüllten Voraussetzungen. Ein Druck ist ausdrücklich — auch ein eben abgelehnter
    startet."""
    if req.action or (req.environment.tour_action or "").strip().lower() != "start":
        return None
    ablauf = ausloeser.per_tour_chip()
    return (ablauf if ablauf is not None and ausloeser.per_knopf(ablauf)
            and ausloeser.erfuellt(ablauf) else None)


async def per_tour_chip(session: Any, req: ChatRequest, session_state: dict, ablauf: AblaufArea,
                        *, blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """G2c: der Tour-Chip startet ``ablauf`` wie sein Knopf — ein wartender Lauf desselben Ablaufs
    beginnt neu an der aktuellen Seite (wie die Tour). Review G2, MAJOR 2: wartet ein ANDERER
    Ablauf, erst die Ersetzen-Rückfrage — an seiner Frage wie bei einer Wendung samt „Hier
    weitermachen“ (``wendung_zug``), sonst mit „Neu starten“ (und „Stand prüfen“ am Auftrag)."""
    aktiv = await _aktiver_lauf(session, req, session_state)
    if (aktiv is not None and aktiv[1].get("ablauf") != ablauf.id
            and aktiv[1].get("status") in treiber.WARTEND):
        from boerdi.services.ablauf import wendung_zug  # zyklenfrei erst zur Laufzeit

        if (frage := await wendung_zug.wendung_beantworten(session, req, session_state,
                                                           ablauf)) is not None:
            return frage
        return await _ersetzen_fragen(session, req, ablauf, None, *aktiv)
    knopf = req.model_copy(update={"action": AKTION, "action_params": {"ablauf": ablauf.id}})
    return await starten(session, knopf, session_state, blocked_tools=blocked_tools)


def anmelde_zeile(nachricht: str | None, lang: str, ohne: str | None = None) -> str | None:
    """Rückmeldung 11.11. (Nutzer-Entscheid „Hinweis + weiterhelfen“): passt eine Wendung zu einem
    Ablauf, dessen Voraussetzung (Anmeldung) fehlt, startet er nicht (:func:`text_ausloeser`) —
    die KI erfährt es aber und sagt es in einem Satz, statt den Ablauf stumm zu übergehen."""
    ablauf = ausloeser.per_text(nachricht)
    # R2-b: nur, wenn die Anmeldung hilft — ist Lesen im Studio aus, wäre der Satz falsch
    if ablauf is None or ablauf.id == ohne or ausloeser.fehlt(ablauf) != "anmeldung":
        return None
    titel = _titel_ohne_klammern(ablauf, lang)
    # TW-6: den Satz zur Anmeldung hängt das System an (:func:`anmelde_satz`) — die KI ließ ihn im
    # Durchtest weg und öffnete nur das Upload-Feld
    return (f"[ABLAUF OHNE ANMELDUNG — Zur Bitte passt der geführte Ablauf „{titel}“; er braucht "
            "eine Anmeldung bei WLO. Der Hinweis steht schon unter deiner Antwort; hilf ohne den "
            "Ablauf weiter.]")


def _titel_ohne_klammern(ablauf: AblaufArea, lang: str) -> str:
    titel = ablauf.titel.get(lang) or ablauf.titel.get("de") or ablauf.id
    return titel.replace("[", "(").replace("]", ")")[:80]


def anmelde_satz(nachricht: str | None, lang: str, ohne: str | None = None) -> str | None:
    """TW-6: der Satz unter der Antwort, wenn eine Wendung zu einem Ablauf passt, dem die
    Anmeldung fehlt (dieselbe Bedingung wie :func:`anmelde_zeile`)."""
    ablauf = ausloeser.per_text(nachricht)
    # R2-b: nur, wenn die Anmeldung hilft — ist Lesen im Studio aus, wäre der Satz falsch
    if ablauf is None or ablauf.id == ohne or ausloeser.fehlt(ablauf) != "anmeldung":
        return None
    return bot_text(lang, "action.ablauf.anmeldungHinweis",
                    titel=_titel_ohne_klammern(ablauf, lang))


def modul_ausloeser(geprueft: dict[str, Any] | None, ohne: str | None = None
                    ) -> tuple[AblaufArea, int] | None:
    """Ablauf und Startschritt für eine Modul-Antwort — nur mit erfüllten Voraussetzungen (sonst
    geht die Antwort still den gewöhnlichen Weg), nie ``ohne`` (:func:`abgelehnt`)."""
    treffer = ausloeser.per_modul(geprueft)
    if treffer is None or treffer[0].id == ohne:
        return None
    return treffer if ausloeser.erfuellt(treffer[0]) else None


async def per_modul_starten(session: Any, req: ChatRequest, session_state: dict,
                            geprueft: dict[str, Any], treffer: tuple[AblaufArea, int], *,
                            blocked_tools: Iterable[str] = ()) -> ChatResponse:
    """Die Antwort wird Teil des Vorgangs (dieser Zug erreicht ``persist`` nicht), dann rechnet der
    Treiber ab dem Schritt nach dem Modul."""
    entities = session_state.setdefault("entities", {})
    ablauf, ab = treffer
    ausgaenge: list[str] = []
    # Review Q3, Befund 2: das Ziel steht fest, bevor die Antwort gespeichert wird — sonst landete
    # sie im beendeten Vorgang und der Lauf in einem neuen.
    if not await _ziel_vorbereiten(session, req, entities, ablauf, anlegen=True,
                                   ausgaenge=ausgaenge) \
            or not await arbeitsstand.uebernehmen(session, req.session_id, entities, geprueft,
                                                  nur_dieser=True):
        # Review Q3, Befund 9: ohne gespeicherte Antwort rechnete der Treiber ohne sie.
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    return await starten_mit(session, req, session_state, ablauf, ab=ab,
                             gewaehlt=treiber.gewaehlt_aus(geprueft.get("daten")),
                             blocked_tools=blocked_tools, frisch=False, ausgaenge=ausgaenge)


async def starten_mit(session: Any, req: ChatRequest, session_state: dict, ablauf: AblaufArea,
                      *, ab: int = 0, gewaehlt: list[str] | None = None,
                      start: dict[str, Any] | None = None, start_quelle: str | None = None,
                      blocked_tools: Iterable[str] = (), frisch: bool = True,
                      ausgaenge: list[str] | None = None) -> ChatResponse:
    """Einen Lauf beginnen. ``ausgaenge`` (Review A5): wie ein dabei beendeter Auftrag ausging
    (``zug_basis.auftraege_beenden``) — der Satz dazu steht vor der Antwort."""
    ausgaenge = ausgaenge if ausgaenge is not None else []
    if (fehlt := ausloeser.fehlt(ablauf)) is not None:
        # R2-b: ist Lesen im Studio aus, hilft keine Anmeldung — dann ein eigener Satz
        return await basis.nur_text(session, req, "action.ablauf.dokumentLesenAus"
                                    if fehlt == "dokument_lesen" else "action.ablauf.anmeldung")
    if start is None and startdaten.pflichtfelder(ablauf):
        # AS-4a: Wendung, Modul oder Knopf bringen keine Startdaten — ohne Pflichtfelder kein Start
        return await basis.nur_text(session, req, "action.ablauf.startdaten")
    if start is None and ablauf.start:
        # Review AS-4a, Befund 5: auch ohne Daten ein (leerer) Teil — sonst gälten im selben
        # Vorgang die Startdaten eines früheren Laufs
        start = {}
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    # Zweites Review TW, Befund 8: „Doch mit Ablauf“ (oder ein anderer Start) hebt den Ausstieg auf
    if (entities.get(basis.AUSSTIEG_KEY) or {}).get("ablauf") == ablauf.id:
        entities.pop(basis.AUSSTIEG_KEY, None)
    # Querschnitts-Review F/T, Befund 1: ein Ablauf, der ins Repositorium schreibt, beginnt in
    # einem frischen Vorgang — eine alte Ablage ginge sonst als „frisch hochgeladen“ an einen
    # schreibenden Flow (N14). Seit Review TG-4–6 (MAJOR 2) nur, wenn dort eine Ablage, ein
    # Metadaten-Lauf oder ein offener Lauf liegt (``_frisch_noetig``); sonst bleibt freie
    # Arbeit. Der Modul-Auslöser (``frisch=False``) bleibt: er hat sein Ziel schon
    # vorbereitet und die Antwort dort gespeichert.
    if not await _ziel_vorbereiten(session, req, entities, ablauf,
                                   # Review TW-6, Befund 4: nur, wer selbst schreibt (N14) —
                                   # ein Upload-Feld schloss sonst beim Direktstart ohne Klick
                                   # die freie Arbeit samt Entwurf
                                   frisch=frisch and werkzeuge.ablauf_schreibt_selbst(ablauf),
                                   ausgaenge=ausgaenge):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    aus = await basis.rechne(session, ablauf, treiber.starten(
        ablauf, basis.umgebung(session, req, entities, blocked_tools), ab, gewaehlt, start,
        start_quelle))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if vw is not None and (v is None or v.status in vorgaenge.ABGESCHLOSSEN):
        # Nachprüfung, Befund 3: inzwischen abgeschlossen oder weg (eine zweite Sitzung) — der Lauf
        # hinge sonst an einem frischen Vorgang ohne die Teile, die er davor bekam.
        await basis.nicht_festgehalten(aus)
        basis.verweis_auffrischen(entities, None, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    try:
        alter_job = await _alten_auftrag_schliessen(session, v, aus)
        if v is None:
            v = await _anlegen(session, req, aufrufer, ablauf)
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        await basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    ausgaenge.append(await basis.auftraege_beenden(alter_job))
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    # Ein neuer Lauf zählt seine KI-Züge neu (Review A2b, Befund 4) — erst nach dem Festhalten:
    # ein gescheiterter Neustart ließe sonst den alten Lauf mit leerem Budget weiterlaufen (Review
    # Q2, Befund 4).
    entities.pop(ki_schritt.ZUEGE_KEY, None)
    # Review A5: ersetzte der Start einen Lauf samt Auftrag, sagt ein Satz vorweg, wie es ausging
    lang = resolve_locale(req.environment.locale)
    aus.texte[:0] = [s for a in dict.fromkeys(ausgaenge) if (s := basis.auftrag_satz(a, lang))]
    return await basis.antwort(session, req, session_state, aus, ablauf)


async def _anlegen(session: Any, req: ChatRequest, aufrufer: str, ablauf: AblaufArea) -> Any:
    return await vorgaenge.anlegen(session, aufrufer=aufrufer, session_id=req.session_id,
                                   titel=ablauf.titel.get("de") or ablauf.id, zweck=ablauf.id,
                                   tage=arbeitsstand.tage())


async def _ziel_vorbereiten(session: Any, req: ChatRequest, entities: dict[str, Any],
                            ablauf: AblaufArea, *, anlegen: bool = False,
                            frisch: bool = False, ausgaenge: list[str] | None = None) -> bool:
    """Querschnitts-Review 2026-11-06, M6 (nach Review Q3): ein beendeter Lauf lässt seinen Vorgang
    offen — der Entwurf darin bleibt erreichbar. Erst ein neuer Start schließt einen Vorgang, dessen
    Lauf beendet ist (fertig, Fehler, abgebrochen) oder einem anderen Ablauf gehört, und beginnt
    einen neuen; sonst bliebe jede Person bei einem ewigen Vorgang. Freie Arbeit (kein Lauf) und ein
    wartender Lauf desselben Ablaufs bleiben. Mit ``anlegen`` steht danach immer ein Ziel fest (ein
    neuer Vorgang, wenn keiner da ist) — der Modul-Auslöser speichert dann nur dorthin (Review Q3,
    Nachprüfung, Befund 3). Mit ``frisch`` (ein schreibender Ablauf) wird jeder vorhandene Vorgang
    geschlossen, auch freie Arbeit und ein wartender Lauf desselben Ablaufs (Querschnitts-Review
    F/T, Befund 1). ``False`` bei einem Konflikt.

    Plan 2026-11-16, Nachprüfung TG-2: der neue Vorgang übernimmt aus dem geschlossenen die
    Bereitstellungs-Teile (``arbeitsstand_teile.BEREITSTELLUNG``) — Ordner und Dokument, die die
    Person im freien Chat bereitgestellt hat, gingen sonst mit dem alten verloren. Nur Teile, die es
    dort gibt, mit ihrem Inhalt bzw. Verweis (``document`` zeigt auf das Sitzungsdokument); kein
    Entwurf, kein Lauf, keine Antworten, keine Historie. Das gilt für jeden Start.

    Review A5: endet dabei ein Auftrag, kommt sein Ausgang in ``ausgaenge`` (der Satz dazu steht
    vor der Antwort des Starts)."""
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    if v is not None and v.status in vorgaenge.ABGESCHLOSSEN:
        v = None
    if v is None:
        arbeitsstand.verweis_weg(entities, aufrufer)
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    if frisch and v is not None and not _frisch_noetig(v, lauf):
        # Plan 2026-11-16, Review TG-4–6, MAJOR 2: N14 schützt den Flow vor einer ALTEN Ablage —
        # liegt keine im Vorgang (auch kein Metadaten-Lauf) und läuft dort nichts, gibt es nichts
        # zu mischen; die freie Arbeit samt Entwurf bleibt (wie TW-6, Befund 4)
        frisch = False
    if v is not None and not frisch and (
            not isinstance(lauf, dict) or (lauf.get("ablauf") == ablauf.id
                                           and lauf.get("status") not in _BEENDET)):
        return True
    if v is None and not anlegen:
        return True
    alter_job = None
    try:
        mitnehmen = await _bereitstellung(session, v) if v is not None else []
        if v is not None:
            alter_job = await basis.schliessen(session, v, session_id=req.session_id)
            # Ein neues Vorhaben: der gemerkte Entwurf des alten ist kein Gegenstand mehr.
            entities.pop(strukturentwurf_merken.KEY, None)
        neu = await _anlegen(session, req, aufrufer, ablauf)
        for name, typ, wert, kurz in mitnehmen:
            neu = await vorgaenge.teil_setzen(session, neu, name, typ=typ, wert=wert,
                                              zusammenfassung=kurz, tage=arbeitsstand.tage())
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        return False
    ausgang = await basis.auftraege_beenden(alter_job)
    if ausgaenge is not None:
        ausgaenge.append(ausgang)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(neu, aufrufer)
    return True


def _frisch_noetig(v: Any, lauf: Any) -> bool:
    """MAJOR 2: braucht ein schreibender Ablauf einen frischen Vorgang?
    (``werkzeuge.frisch_noetig``)"""
    return werkzeuge.frisch_noetig((v.akte or {}).get("teile") or {}, lauf)


async def _bereitstellung(session: Any, v: Any) -> list[tuple[str, str, Any, str]]:
    """Die Bereitstellungs-Teile von ``v``, die es gibt: (Name, Typ, Wert, Kurzbeschreibung)."""
    teile = (v.akte or {}).get("teile") or {}
    mit: list[tuple[str, str, Any, str]] = []
    for name in BEREITSTELLUNG:
        if not isinstance(eintrag := teile.get(name), dict):
            continue
        if (wert := await vorgaenge.teil_wert(session, v, name)) is not None:
            mit.append((name, str(eintrag.get("typ") or ""), wert,
                        str(eintrag.get("zusammenfassung") or "")))
    # Plan 2026-11-17, Paket U5: hier im Chat gelesene Angaben (``metadaten``, ``quelle: chatbot``)
    # sind Daten der Person wie die Auswahl — sie gehen mit; Metadaten aus WLO nicht (sie hängen an
    # ``ablage``, das ein schreibender Ablauf frisch beginnt, N14)
    if isinstance(eintrag := teile.get("metadaten"), dict):
        from boerdi.services.dokumente import metadaten_lokal

        if metadaten_lokal.ist_lokal(wert := await vorgaenge.teil_wert(session, v, "metadaten")):
            mit.append(("metadaten", str(eintrag.get("typ") or ""), wert,
                        str(eintrag.get("zusammenfassung") or "")))
    return mit


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
        if treiber.gilt(ablauf, offen) and treiber.kann_weiter(ablauf, offen):
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
    # E-F (Review Paket F): ein Lauf, der in einem anderen Gespräch wartet, nimmt hier nichts an.
    if (lauf is None or not basis.gehoert_hierher(v, req.session_id)
            or not treiber.gilt(ablauf, lauf) or not treiber.kann_weiter(ablauf, lauf)):
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
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        await basis.nicht_festgehalten(aus)
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
    return await _weiter_ki(session, req, session_state, v, lauf, gewollt, blocked_tools)


async def nach_uebernahme(session: Any, req: ChatRequest, session_state: dict,
                          geprueft: dict[str, Any], *,
                          blocked_tools: Iterable[str] = ()) -> ChatResponse | None:
    """Plan 2026-11-16, Durchtest TG-7 (M1b): die Person übernimmt den Entwurf des wartenden
    KI-Schritts (``ki_schritt.uebernimmt``) — den Teil speichern (nur in den Vorgang des Laufs) und
    weiter wie „Weiter im Ablauf“, ohne KI-Zug dazwischen. ``None``, wenn es keine solche Übernahme
    ist (dann ist nichts gespeichert, der Zug geht den gewöhnlichen Weg)."""
    if (treffer := ki_schritt.uebernimmt(session_state, req.session_id, geprueft)) is None:
        return None
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    # Review der TG-7-Behebung, Befund 3: auch derselbe Schritt — ein veralteter Verweis (der Lauf
    # steht schon an einem anderen KI-Schritt) übernimmt nicht in den falschen
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != treffer[0].id
            or lauf.get("status") != treiber.WARTET_KI
            or lauf.get("schritt") != treffer[1].id
            or not basis.gehoert_hierher(v, req.session_id)):     # E-F (Review Paket F)
        return None
    if not await arbeitsstand.uebernehmen(session, req.session_id, entities, geprueft,
                                          nur_dieser=True):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    v = await vorgaenge.lesen(session, v.id, aufrufer)
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    return await _weiter_ki(session, req, session_state, v, lauf, treffer[0].id, blocked_tools)


async def _weiter_ki(session: Any, req: ChatRequest, session_state: dict, v: Any, lauf: Any,
                     gewollt: Any, blocked_tools: Iterable[str]) -> ChatResponse:
    """„Weiter im Ablauf“ bzw. nach der Übernahme (M1b): der Treiber setzt am KI-Schritt fort."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_KI):
        # Querschnitts-Review M5: der Verweis folgt dem Vorgang (zweite Sitzung, verdrängt).
        basis.verweis_auffrischen(entities, v, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    ablauf = laden(gewollt)
    if not treiber.gilt(ablauf, lauf):
        # Review A2b, Befund 7: ein Lauf, der nicht mehr kann, wartet nicht weiter.
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    aus = await basis.rechne(session, ablauf, treiber.weiter_ki(
        ablauf, dict(lauf), basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    if aus.fehlt_teil:
        antwort = await basis.nur_text(session, req, "action.ablauf.fehltNoch")
        lang = resolve_locale(req.environment.locale)
        antwort.quick_replies = [ki_schritt.knopf(ablauf.id, lang)]
        # Review TW-3, Befund 4: hat die KI am Schritt noch nichts getan, wieder der Startknopf
        if not ki_schritt.zuege_bisher(entities, ablauf.id, str(lauf.get("schritt"))) and (
                start := ki_schritt.start_knopf(ablauf, str(lauf.get("schritt")), lang)):
            antwort.quick_replies.insert(0, start)
        return antwort
    try:
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        await basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    entities.pop(ki_schritt.ZUEGE_KEY, None)
    return await basis.antwort(session, req, session_state, aus, ablauf)


# Öffentlich für die anderen Züge (Review AS-Ua, Kleinigkeit 10): ``abbruch_zug``.
aktiver_lauf = _aktiver_lauf
lauf_marke = _marke
rueckfrage_knopf = _knopf
