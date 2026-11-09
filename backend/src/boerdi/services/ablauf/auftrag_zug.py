"""Der Schritt ``auftrag`` im Zug (Paket K1a, Plan 2026-11-05 §5/§9) — b-api-Aufträge (Kestra).

- :func:`starter`: die Naht der Treiber-Umgebung — nur in einer eingerichteten Anlage
  (``client.freigeschaltet``) und mit **bestätigter Anmeldung** (Plan V-3: der Gast-Schlüssel teilt
  sich 20 Jobs). Ein abgewiesener Start liefert ``None`` (``bei_fehler``).
- :func:`pruefen` (Direktaktion ``ablauf_auftrag_pruefen {ablauf}``, Knopf „Stand prüfen“): fragt im
  Zug der Person ab — der Schlüssel, mit dem der Auftrag lief, wird nie gespeichert, ein Wächter im
  Hintergrund könnte ihn nicht lesen. Läuft noch → Hinweis; fertig → Ausgaben werden Teil
  ``schreibt``, der Treiber setzt fort; Fehler → ``bei_fehler`` oder Ende mit Hinweis.
- :func:`knoepfe` / :func:`pruefen_knoepfe`: „Stand prüfen“ und „Auftrag abbrechen“, solange ein
  Lauf auf einen Auftrag wartet.
- :func:`abbrechen` (Direktaktion ``ablauf_auftrag_abbrechen {ablauf}``, Paket K2b): erst eine
  Rückfrage, mit ``bestaetigt`` endet der Lauf (``abgebrochen``) samt Auftrag — nach dem
  Festschreiben auch bei der b-api.
- :func:`gesperrt` / :func:`gesperrt_antwort` (K2b): ein Auftragsschritt mit ``warten: gesperrt``
  lässt, solange er wartet, nur die Auftrags- und Vorgangs-Knöpfe durch.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.auftraege import ablage, client, dateien
from boerdi.services.llm_auth import hat_zug_schluessel
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

AKTION: Final = "ablauf_auftrag_pruefen"
AKTION_ABBRECHEN: Final = "ablauf_auftrag_abbrechen"
#: Zweites Review K2b, Befund 2: nach einer Nachricht mit hohem Risiko (Krise) ruht die Sperre,
#: solange DIESES Warten dauert — die Person soll auf die Krisenantwort antworten können.
SPERRE_RUHT: Final = "auftrag_sperre_ruht"
#: Gründe des Clients, die kein neuer Versuch heilt — der Auftrag gilt als gescheitert
#: (``bei_fehler``), statt dass „Stand prüfen“ endlos wiederkommt (Querschnitts-Review).
ENDGUELTIG: Final = frozenset({"unbekannt", "aus"})
#: Paket K2d-2 (Review, Befund 1): so oft holt „Stand prüfen“ Dateien nach einem vorübergehenden
#: Fehler, bevor das Ergebnis ohne sie weitergeht; je Job in ``entities`` gezählt.
DATEI_VERSUCHE: Final = 3
DATEI_VERSUCHE_KEY: Final = "_auftrag_dateien_versuche"



def starter() -> Callable[[str, dict[str, Any]], Awaitable[str | None]] | None:
    """Die Start-Naht für den Treiber — ``None`` ohne Einrichtung, ohne Anmeldung oder ohne den
    durchgereichten Schlüssel der Person: sonst teilten alle Angemeldeten die 20 Aufträge von
    ``B_API_KEY`` (Plan V-3, Review K1a, Befund 1)."""
    if not client.freigeschaltet() or not has_personal_auth() or not hat_zug_schluessel():
        return None

    async def starte(flow: str, eingaben: dict[str, Any]) -> str | None:
        try:
            return await client.starten(flow, eingaben)
        except client.AuftragFehler as fehler:
            logger.info("Auftrag nicht gestartet (%s)", fehler.grund)
            return None

    return starte


def _knopf(lang: str, schluessel: str, aktion: str, params: dict[str, Any]) -> str:
    label = bot_text(lang, schluessel).replace("|", "/")
    return f"__action__|{label}|{aktion}|" + json.dumps(params, ensure_ascii=False)


def knopf(ablauf_id: str, lang: str) -> str:
    return _knopf(lang, "action.ablauf.auftragKnopf", AKTION, {"ablauf": ablauf_id})


def knoepfe(ablauf_id: str, lang: str) -> list[str]:
    """„Stand prüfen“ und „Auftrag abbrechen“ (K2b) — der Abbruch fragt erst nach."""
    return [knopf(ablauf_id, lang),
            _knopf(lang, "action.ablauf.auftragAbbrechenKnopf", AKTION_ABBRECHEN,
                   {"ablauf": ablauf_id})]


def _wartend(session_id: str, session_state: dict[str, Any]) -> tuple[dict[str, Any], Any] | None:
    """Lauf und Ablauf, solange ein Lauf dieser Person auf einen Auftrag wartet — nur der Verweis,
    ohne Datenbank (Preflight, Schnellantworten)."""
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id))
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_AUFTRAG:
        return None
    # Review K1a, Befund 11: wie ``ki_schritt.aktueller`` — nur, solange der Ablauf gilt.
    ablauf = laden(lauf.get("ablauf"))
    if ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf):
        return None
    return lauf, ablauf


def ist_knopf(schnellantwort: str) -> bool:
    """Ist das „Stand prüfen“ oder „Auftrag abbrechen“? (Der Deckel der Schnellantworten lässt sie
    im gesperrten Lauf stehen — zweites Review K2b, Befund 3.)"""
    teile = schnellantwort.split("|", 3)
    return (len(teile) == 4 and teile[0] == "__action__"
            and teile[2] in (AKTION, AKTION_ABBRECHEN))


def pruefen_knoepfe(session_id: str, session_state: dict[str, Any], lang: str) -> list[str]:
    """:func:`knoepfe`, solange ein Lauf dieser Person auf einen Auftrag wartet — sonst leer."""
    wartend = _wartend(session_id, session_state)
    return knoepfe(wartend[1].id, lang) if wartend is not None else []


def _sperr_marke(session_id: str, session_state: dict[str, Any]) -> str | None:
    """Dieses Warten: Vorgang, Schritt und Fassung — ``None``, wenn kein Lauf auf einen Auftrag
    wartet."""
    wartend = _wartend(session_id, session_state)
    if wartend is None:
        return None
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id)) or {}
    lauf = wartend[0]
    return f"{vw.get('id')}:{lauf.get('schritt')}:{lauf.get('fassung')}"


def sperre_aussetzen(session_id: str, session_state: dict[str, Any]) -> None:
    """Nach einer Krise im gesperrten Lauf ruht die Sperre bis zum Ende dieses Wartens."""
    if (marke := _sperr_marke(session_id, session_state)) is not None:
        session_state[SPERRE_RUHT] = marke


def sperre_aufraeumen(session_id: str, session_state: dict[str, Any]) -> None:
    """Die Marke von :func:`sperre_aussetzen` gilt nur für ihr Warten — danach weg."""
    if (SPERRE_RUHT in session_state
            and session_state[SPERRE_RUHT] != _sperr_marke(session_id, session_state)):
        session_state.pop(SPERRE_RUHT, None)


def gesperrt(session_id: str, session_state: dict[str, Any]) -> str | None:
    """Die Kennung des Ablaufs, wenn ein Lauf dieser Person an einem Auftragsschritt mit
    ``warten: gesperrt`` wartet (K2b) — sonst ``None``, auch solange die Sperre nach einer Krise
    ruht. Ein veralteter Verweis (eine zweite Sitzung holte ab) zeigt höchstens einmal den
    Hinweis; „Stand prüfen“ frischt ihn auf."""
    wartend = _wartend(session_id, session_state)
    if wartend is None:
        return None
    if (session_state.get(SPERRE_RUHT) is not None
            and session_state.get(SPERRE_RUHT) == _sperr_marke(session_id, session_state)):
        return None
    lauf, ablauf = wartend
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    return ablauf.id if schritt is not None and schritt.warten == "gesperrt" else None


async def gesperrt_antwort(session: Any, req: ChatRequest, ablauf_id: str) -> ChatResponse:
    """Der Hinweis auf eine getippte Nachricht oder einen anderen Knopf im gesperrten Lauf."""
    return await _mit_knopf(session, req, "action.ablauf.auftragGesperrt", ablauf_id)


async def _mit_knopf(session: Any, req: ChatRequest, schluessel: str,
                     ablauf_id: str) -> ChatResponse:
    antwort = await basis.nur_text(session, req, schluessel)
    antwort.quick_replies = knoepfe(ablauf_id, resolve_locale(req.environment.locale))
    return antwort


async def abbrechen(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse:
    """Direktaktion ``ablauf_auftrag_abbrechen {ablauf}`` (K2b): ohne ``bestaetigt`` die Rückfrage,
    sonst endet der wartende Lauf samt Auftrag (``zug_basis.abbrechen``)."""
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    params = req.action_params or {}
    gewollt = params.get("ablauf")
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_AUFTRAG):
        basis.verweis_auffrischen(entities, v, aufrufer)
        # Review K2b (Nit): ein zweites „Ja“ nach dem Abbruch — der Ablauf gibt es ja noch. Ebenso
        # ein Knopf, dessen Arbeitsstand inzwischen gelöscht ist (zweites Review, Befund 9).
        beendet = ((isinstance(lauf, dict) and lauf.get("ablauf") == gewollt)
                   or (v is None and isinstance(gewollt, str) and laden(gewollt) is not None))
        return await basis.nur_text(
            session, req, "action.ablauf.auftragSchonBeendet" if beendet
            else "action.ablauf.unbekannt", entities)
    lang = resolve_locale(req.environment.locale)
    offen = await ablage.offen(session, v.id)
    jetzt = client.kuerzel(offen.job_id) if offen is not None else ""
    # Review K2b, Befund 2: die Bestätigung gilt nur für DIESEN Auftrag — ein altes „Ja,
    # abbrechen“ im Verlauf beendete sonst still einen späteren Lauf desselben Ablaufs.
    if params.get("bestaetigt") is not True or params.get("kuerzel") != jetzt:
        antwort = await basis.nur_text(session, req, "action.ablauf.auftragAbbrechenFrage")
        antwort.quick_replies = [
            _knopf(lang, "action.ablauf.auftragAbbrechenJa", AKTION_ABBRECHEN,
                   {"ablauf": gewollt, "bestaetigt": True, "kuerzel": jetzt}),
            knopf(gewollt, lang)]
        return antwort
    if not await basis.abbrechen(session, v, lauf, entities, aufrufer):
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    from boerdi.services import vorgang_aktion

    # Zweites Review K2b, Befund 8: ohne den Schlüssel der Person (Anmeldung abgelaufen) endet der
    # Auftrag nur hier — bei der b-api läuft er weiter. Das sagt die Antwort.
    schluessel = ("action.ablauf.auftragAbgebrochen" if hat_zug_schluessel()
                  else "action.ablauf.auftragNurHierAbgebrochen")
    antwort = await basis.nur_text(session, req, schluessel, entities)
    antwort.quick_replies = vorgang_aktion.knoepfe(lang)
    return antwort


async def pruefen(session: Any, req: ChatRequest, session_state: dict, *,
                  blocked_tools: Iterable[str] = ()) -> ChatResponse:
    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    gewollt = (req.action_params or {}).get("ablauf")
    if (not isinstance(lauf, dict) or lauf.get("ablauf") != gewollt
            or lauf.get("status") != treiber.WARTET_AUFTRAG):
        # Querschnitts-Review M5: der Verweis folgt dem Vorgang (zweite Sitzung, verdrängt).
        basis.verweis_auffrischen(entities, v, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    ablauf = laden(gewollt)
    auftrag = await ablage.offen(session, v.id)
    if (ablauf is None or not ablauf.aktiv or lauf.get("fassung") != treiber.fassung(ablauf)
            or auftrag is None or auftrag.schritt != lauf.get("schritt")):
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    if not hat_zug_schluessel():
        # Mit ``B_API_KEY`` sähe der Chatbot den Auftrag der Person nicht (K22) — und fragte nicht.
        return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id)
    await basis.frei(session)             # M7: die b-api-Abfrage hält keine DB-Verbindung
    try:
        stand = await client.stand(auftrag.job_id)
    except client.AuftragFehler as fehler:
        logger.info("Auftrag: Stand nicht abrufbar (%s)", fehler.grund)
        if fehler.grund == "abgewiesen":
            # Ein abgewiesener Schlüssel heilt kein zweiter Klick — der Lauf endet, damit ein
            # Neustart (Wendung, Modul) nicht am wartenden Lauf hängt (Review Q2, Befund 1).
            # Kein DELETE mit dem Schlüssel, den die b-api eben abwies (Review Job-Vertrag, 5).
            await basis.abbrechen(session, v, lauf, entities, aufrufer, bei_der_b_api=False)
            return await basis.nur_text(session, req, "action.ablauf.auftragAbgewiesen", entities)
        if fehler.grund not in ENDGUELTIG:
            return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id)
        stand = client.Stand("fehler")    # Auftrag weg (30 Tage) oder Aufträge aus: gescheitert
    if stand.status == "laeuft":
        return await _mit_knopf(session, req, "action.ablauf.auftragLaeuft", ablauf.id)
    # Job-Vertrag 2026-11-07: ``warnings`` (einzelne Iterationen scheiterten) reist im Teil mit —
    # ein Folgeschritt soll einen Teilerfolg erkennen können.
    ergebnis = ({"outputs": stand.outputs, "dateien": stand.dateien,
                 **({"warnungen": True} if stand.warnungen else {})}
                if stand.status == "fertig" else None)
    # Paket K2d-2: die Dateien, die der Schritt nennt — ihr Text unter ``texte.<outputId>``, was
    # nicht ging, unter ``dateien_fehlen.<outputId>``. Noch ohne DB-Verbindung (M7).
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if ergebnis is not None and schritt is not None and schritt.dateien_holen:
        texte, fehlen = await dateien.holen(auftrag.job_id, stand.dateien, schritt.dateien_holen)
        # Review K2d-2, Befund 1: ein vorübergehender Fehler (B-API voll, Netz, Umwandlung
        # ausgelastet oder zu langsam) verbraucht das Ergebnis nicht — die Datei liegt noch
        # 7 Tage bei der B-API. „Stand prüfen“ versucht es erneut, höchstens DATEI_VERSUCHE-mal.
        # Zweites Review K2d-2, Befund 3: gezählt unter dem Kürzel (die Job-ID bleibt in der DB),
        # und nur für einen Auftrag — ein anderer fängt neu an, nichts bleibt liegen.
        merk = entities.get(DATEI_VERSUCHE_KEY)
        kurz = client.kuerzel(auftrag.job_id)
        bisher = merk.get("n") if isinstance(merk, dict) and merk.get("auftrag") == kurz else 0
        n = (bisher if isinstance(bisher, int) else 0) + 1
        if set(fehlen.values()) & dateien.VORUEBERGEHEND and n < DATEI_VERSUCHE:
            entities[DATEI_VERSUCHE_KEY] = {"auftrag": kurz, "n": n}
            antwort = await basis.nur_text(session, req, "action.ablauf.dateienSpaeter", entities)
            antwort.quick_replies = knoepfe(ablauf.id, resolve_locale(req.environment.locale))
            return antwort
        entities.pop(DATEI_VERSUCHE_KEY, None)
        ergebnis["texte"] = texte
        if fehlen:
            ergebnis["dateien_fehlen"] = fehlen
    aus = await basis.rechne(session, ablauf, treiber.weiter_auftrag(
        ablauf, dict(lauf), ergebnis, basis.umgebung(session, req, entities, blocked_tools)))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        await ablage.abschliessen(session, auftrag, stand.status)
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.VorgangKonflikt:
        await session.rollback()
        basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    return await basis.antwort(session, req, session_state, aus, ablauf)
