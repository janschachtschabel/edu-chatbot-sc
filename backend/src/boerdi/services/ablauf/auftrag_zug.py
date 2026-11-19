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
  lässt, solange er wartet, nur die Auftrags- und Vorgangs-Knöpfe durch. Paket K7 (E16): dazu
  „Später weitermachen“ (``auftrag_spaeter``) — die Sperre ruht für diese Sitzung (Marke
  :data:`SPAETER` in ``entities``), bis „Stand prüfen“ zum Auftrag zurückführt.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, probe, vorgaenge
from boerdi.services.ablauf import auftrag_teile, treiber, typen
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.auftraege import ablage, client, dateien, mcp_starter
from boerdi.services.llm_auth import darf_jobs, zug_art
from boerdi.services.mcp import faehigkeiten
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)

AKTION: Final = "ablauf_auftrag_pruefen"
AKTION_ABBRECHEN: Final = "ablauf_auftrag_abbrechen"
#: Paket K7 (E16): „Später weitermachen“ (``services/ablauf/auftrag_spaeter``).
AKTION_SPAETER: Final = "ablauf_auftrag_spaeter"
#: Paket K7: die Marke „später“ — in ``entities`` (die Sitzung lädt je Zug nur sie neu), nur für
#: ihr Warten (:func:`_sperr_marke`).
SPAETER: Final = "_auftrag_spaeter"
#: Zweites Review K2b, Befund 2: nach einer Nachricht mit hohem Risiko (Krise) ruht die Sperre,
#: solange DIESES Warten dauert — die Person soll auf die Krisenantwort antworten können.
#: Nachtrag K7: in ``entities`` wie :data:`SPAETER` — im Wurzel-Dict von ``session_state``
#: überlebte sie den Zug nicht, die Sperre griff schon im nächsten Zug wieder.
SPERRE_RUHT: Final = "_auftrag_sperre_ruht"
#: Die Marken, mit denen die Sperre eines Wartens ruht — „Stand prüfen“ nimmt beide zurück.
_RUHT: Final = (SPERRE_RUHT, SPAETER)
#: Gründe des Clients, die kein neuer Versuch heilt — der Auftrag gilt als gescheitert
#: (``bei_fehler``), statt dass „Stand prüfen“ endlos wiederkommt (Querschnitts-Review).
ENDGUELTIG: Final = frozenset({"unbekannt", "aus"})
#: Paket K2d-2 (Review, Befund 1): so oft holt „Stand prüfen“ Dateien nach einem vorübergehenden
#: Fehler, bevor das Ergebnis ohne sie weitergeht; je Job in ``entities`` gezählt.
DATEI_VERSUCHE: Final = 3
DATEI_VERSUCHE_KEY: Final = "_auftrag_dateien_versuche"
#: Durchtest Paket K (19.11.): diese Fehlercodes eines gescheiterten Flows nennt der Satz
#: ``auftragFehlgeschlagen`` — andere nicht (ein Code des Trägers ist kein Text für die Person).
FEHLERCODES: Final = frozenset({"TIMEOUT", "FLOW_FAILED"})



#: Paket K2: die Träger eines Auftrags.
MCP: Final = "mcp"
DIREKT: Final = "direkt"
#: Review A2: kein Träger, weil die Flow-Werkzeuge des MCP gerade fehlen, eben aber noch da waren
#: (Neustart des MCP) — der Start meldet „gleich noch einmal“ statt eines Fehlschlags.
MCP_KURZ_WEG: Final = "mcp_kurz_weg"


def traeger(*, repo_schreibt: bool = False) -> tuple[str | None, str]:
    """Paket K2 (Plan 2026-11-17, E1/E2), Regel seit Review A4/A7 (19.11.): wer einen Auftrag
    dieses Zuges trägt — und ohne Träger, warum nicht.

    - Ein Schritt mit ``repo_schreibt`` geht **nur über den MCP** (``mcp``): er führt alle drei
      Flow-Werkzeuge und die Person ist bestätigt angemeldet — auch bei Delegation (der MCP
      startet mit der Anmeldung der Person). Nur dort ist die Rückfrage davor die Zustimmung, und
      der MCP führt den Start als schreibend. Fehlen die Werkzeuge kurz: :data:`MCP_KURZ_WEG`,
      sonst ``ohne_mcp``.
    - Ein Flow ohne ``repo_schreibt`` geht den Direktweg wie vor Paket K (``direkt``):
      eingerichtet und mit dem durchgereichten Schlüssel der Person (``darf_jobs``; nie
      ``B_API_KEY`` aller: Plan V-3, Review K1a, Befund 1). Geht der nicht: ``delegation``,
      ``nicht_eingerichtet`` bzw. ``ohne_schluessel``.
    - Ohne Anmeldung ``ohne_anmeldung``."""
    if not has_personal_auth():
        return None, "ohne_anmeldung"
    if repo_schreibt:
        if mcp_starter.verfuegbar():
            return MCP, ""
        return None, MCP_KURZ_WEG if mcp_starter.kuerzlich_verfuegbar() else "ohne_mcp"
    if client.freigeschaltet() and darf_jobs():
        return DIREKT, ""
    if zug_art() == "delegation":
        # Paket D (E1/E2): das Delegations-Token deckt keine Jobs
        return None, "delegation"
    return None, "nicht_eingerichtet" if not client.freigeschaltet() else "ohne_schluessel"


def starter() -> Callable[[str, dict[str, Any]], Awaitable[str | None]] | None:
    """Die Start-Naht für den Treiber — ``None`` ohne Anmeldung. Den Träger wählt der Treiber je
    Schritt (:meth:`_Wahl.fuer` mit ``repo_schreibt``, Review A4). In der Probe der
    Studio-Vorschau (AS-8a, P-5) startet nichts: eine Trocken-Kennung, ohne b-api und Schlüssel —
    die Anmeldung gilt aber wie im Betrieb (P-8, Querschnitts-Review AS-8, Befund 3: die Probe
    zeigt, was die Person sieht)."""
    if probe.aktiv():
        return _trocken_starten if has_personal_auth() else None
    if not has_personal_auth():
        logger.debug("Auftrag nicht möglich (ohne_anmeldung)")
        return None
    return _Wahl()


def kann_starten(flow: str, *, repo_schreibt: bool = False) -> bool:
    """Ließe sich ``flow`` in diesem Zug starten (Träger, Freigabe, ``repo_schreibt``)? Für
    ``zug_basis.wlo_erschliessen`` (K3)."""
    starte = starter()
    if starte is None:
        return False
    if not isinstance(starte, _Wahl):
        return client.erlaubt(flow)              # Probe: der Trockenlauf
    weg = starte.fuer(repo_schreibt).traeger
    if weg == MCP:
        return mcp_starter.flow_erlaubt(flow)
    return weg == DIREKT and client.erlaubt(flow)


#: Plan 2026-11-16, Durchtest TG-7 (m5): der Satz an die Person je Code der b-api.
_ABGELEHNT: Final = {"EDU_USER_NOT_VERIFIED": "action.ablauf.auftragAbgelehntKonto",
                     "EDU_USER_REQUIRED": "action.ablauf.auftragAbgelehntPerson",   # Paket D
                     "LEGACY_HEADERS": "action.ablauf.auftragAbgelehntTechnik"}
#: Paket K1: Sätze zu Gründen des MCP-Wegs (``offen``: Ausgang offen, nie neu starten). Review
#: A4: ``nicht_erlaubt`` — der MCP (``WLO_BAPI_FLOWS``) bzw. das Studio gibt den Flow nicht frei.
_HINWEISE: Final = {"offen": "action.ablauf.auftragOffen",
                    "nicht_verfuegbar": "action.ablauf.auftragNichtVerfuegbar",
                    "nicht_erlaubt": "action.ablauf.auftragNichtErlaubt"}


class _Starter:
    """Der Starter eines Schritts (:meth:`_Wahl.fuer`). m5: nach einer Abweisung der b-api sagt
    :meth:`hinweis` der Person, warum — der Treiber stellt den Satz vor den Text des Ersatzwegs
    (``bei_fehler``), der sonst nur allgemeine Gründe nennt.

    Paket K1: über den MCP ist ein Ausgang ``offen`` (``error.outcomeOpen``) kein Fehlschlag — ein
    Job kann laufen. Dann nie neu starten: der Schritt wartet mit einer Kennung ohne jobId
    (``mcp_starter.offene_kennung``), „Stand prüfen“ liest die Datensätze; :meth:`hinweis` sagt
    es. Ohne Träger (``traeger`` ``None``) startet nichts; ``grund`` sagt warum."""

    def __init__(self, traeger: str | None = DIREKT, grund: str = "") -> None:
        self.traeger = traeger
        self.grund = grund
        self._fehler: client.AuftragFehler | None = None

    @property
    def nur_ueber_wlo(self) -> bool:
        """Review A4: ein Schritt mit ``repo_schreibt``, und der MCP ist nicht da — der Treiber
        sagt es (``auftragNurUeberWlo``)."""
        return self.traeger is None and self.grund == "ohne_mcp"

    async def __call__(self, flow: str, eingaben: dict[str, Any]) -> str | None:
        self._fehler = None
        if self.traeger is None and self.grund == MCP_KURZ_WEG:
            # Review A2: die Werkzeuge fehlen kurz (Neustart des MCP) — kurz neu fragen; sind sie
            # nicht zurück, „gleich noch einmal“ (zurück an die Rückfrage), nie der Direktweg
            if not await mcp_starter.nachholen():
                self._fehler = client.AuftragFehler("nicht_verfuegbar")
                return None
            self.traeger, self.grund = MCP, ""
        if self.traeger is None:
            return None
        try:
            if self.traeger == MCP:
                return await mcp_starter.starten(flow, eingaben)
            return await client.starten(flow, eingaben)
        except client.AuftragFehler as fehler:
            logger.info("Auftrag nicht gestartet (%s)", fehler.grund)
            self._fehler = fehler
            if fehler.grund == "offen":
                return mcp_starter.offene_kennung()
            return None

    def _voll(self) -> bool:
        """Zweites Review K (Z4): der MCP meldete 429 ohne offenen Ausgang — nichts gestartet."""
        return (self.traeger == MCP and self._fehler is not None
                and self._fehler.grund == "voll")

    def voruebergehend(self) -> bool:
        """Nachtrag MCP 18.11.: der MCP kannte das Werkzeug eben nicht (Neustart) — kein
        endgültiger Fehlschlag; der Treiber führt zurück an die Frage davor. Ebenso ein 429 ohne
        offenen Ausgang (zweites Review, Z4)."""
        return self._fehler is not None and (self._fehler.grund == "nicht_verfuegbar"
                                             or self._voll())

    def hinweis(self, sprache: str) -> str | None:
        fehler = self._fehler
        if fehler is None:
            return None
        if self._voll():
            if fehler.warte_s:
                return bot_text(sprache, "action.ablauf.auftragVoll",
                                minuten=max(1, math.ceil(fehler.warte_s / 60)))
            return bot_text(sprache, "action.ablauf.auftragVollOhneZeit")
        if fehler.grund == "nicht_erlaubt" and self.traeger != MCP:
            return None                     # Direktweg: unverändert, nur der Ersatzweg
        if fehler.grund in _HINWEISE:
            return bot_text(sprache, _HINWEISE[fehler.grund])
        if fehler.grund != "abgewiesen":
            return None
        if fehler.code == "EDU_USER_REQUIRED" and self.traeger == DIREKT:
            # Zweites Review K (Z1): auf dem Direktweg erkennt die b-api nie eine Person — neu
            # anmelden hilft dort nicht
            return bot_text(sprache, "action.ablauf.auftragAbgelehntDirekt")
        return bot_text(sprache, _ABGELEHNT.get(fehler.code or "",
                                                "action.ablauf.auftragAbgelehnt"))


class _Wahl:
    """Review A4/A7: die Start-Naht des Treibers (``treiber.Umgebung.auftrag_starten``). Der
    Träger hängt am Schritt — der Treiber holt mit :meth:`fuer` den Starter für
    ``repo_schreibt``."""

    def fuer(self, repo_schreibt: bool) -> _Starter:
        weg, grund = traeger(repo_schreibt=repo_schreibt)
        if weg is None:
            logger.debug("Auftrag nicht möglich (%s)", grund)   # bleibt DEBUG (Review Paket D)
        return _Starter(weg, grund)

    async def __call__(self, flow: str, eingaben: dict[str, Any]) -> str | None:
        """Ohne Angabe des Schritts: ein lesender Flow (wie vor Paket K)."""
        return await self.fuer(False)(flow, eingaben)


async def _trocken_starten(flow: str, _eingaben: dict[str, Any]) -> str | None:
    # Review AS-8a, Befund 5: ist die b-api eingerichtet, scheitert ein nicht freigeschalteter Flow
    # wie im Betrieb (``bei_fehler``) — ohne Einrichtung bleibt die Probe trotzdem möglich.
    if client.freigeschaltet() and not client.erlaubt(flow):
        logger.info("Trockenlauf: Flow %s ist nicht freigeschaltet", flow)
        return None
    logger.info("Trockenlauf: Auftrag %s nicht gestartet", flow)
    return client.trocken_kennung()


def _knopf(lang: str, schluessel: str, aktion: str, params: dict[str, Any]) -> str:
    label = bot_text(lang, schluessel).replace("|", "/")
    return f"__action__|{label}|{aktion}|" + json.dumps(params, ensure_ascii=False)


def knopf(ablauf_id: str, lang: str) -> str:
    return _knopf(lang, "action.ablauf.auftragKnopf", AKTION, {"ablauf": ablauf_id})


def knoepfe(ablauf_id: str, lang: str, *, spaeter: bool = False) -> list[str]:
    """„Stand prüfen“ und „Auftrag abbrechen“ (K2b) — der Abbruch fragt erst nach. Paket K7: mit
    ``spaeter`` (die Eingabe ist gesperrt) dazwischen „Später weitermachen“."""
    return [knopf(ablauf_id, lang),
            *([_knopf(lang, "action.ablauf.auftragSpaeterKnopf", AKTION_SPAETER,
                      {"ablauf": ablauf_id})] if spaeter else []),
            _knopf(lang, "action.ablauf.auftragAbbrechenKnopf", AKTION_ABBRECHEN,
                   {"ablauf": ablauf_id})]


def sperrt(ablauf: Any, lauf: dict[str, Any]) -> bool:
    """Wartet ``lauf`` an einem Auftragsschritt mit ``warten: gesperrt``?"""
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    return schritt is not None and schritt.warten == "gesperrt"


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
    if not treiber.gilt(ablauf, lauf):
        return None
    return lauf, ablauf


def ist_knopf(schnellantwort: str) -> bool:
    """Ist das „Stand prüfen“ oder „Auftrag abbrechen“? (Der Deckel der Schnellantworten lässt sie
    im gesperrten Lauf stehen — zweites Review K2b, Befund 3.)"""
    teile = schnellantwort.split("|", 3)
    return (len(teile) == 4 and teile[0] == "__action__"
            and teile[2] in (AKTION, AKTION_ABBRECHEN, AKTION_SPAETER))


def pruefen_knoepfe(session_id: str, session_state: dict[str, Any], lang: str) -> list[str]:
    """:func:`knoepfe`, solange ein Lauf dieser Person auf einen Auftrag wartet — sonst leer.
    „Später weitermachen“ nur, solange die Eingabe gesperrt ist (K7)."""
    wartend = _wartend(session_id, session_state)
    if wartend is None:
        return []
    return knoepfe(wartend[1].id, lang, spaeter=gesperrt(session_id, session_state) is not None)


def _sperr_marke(session_id: str, session_state: dict[str, Any]) -> str | None:
    """Dieses Warten: Vorgang, Schritt, Fassung und (Review B3) der Teil eines Stapels — Teil 2
    wartet am selben Schritt; ohne seine Nummer bliebe eine Sitzung, die bei Teil 1 „Später“
    wählte, ungesperrt. ``None``, wenn kein Lauf auf einen Auftrag wartet."""
    wartend = _wartend(session_id, session_state)
    if wartend is None:
        return None
    vw = arbeitsstand.verweis(session_state.get("entities") or {},
                              arbeitsstand.aufrufer_fuer(session_id)) or {}
    lauf = wartend[0]
    return f"{vw.get('id')}:{lauf.get('schritt')}:{lauf.get('fassung')}:{lauf.get('teil', 0)}"


def sperre_aussetzen(session_id: str, session_state: dict[str, Any]) -> None:
    """Nach einer Krise im gesperrten Lauf ruht die Sperre bis zum Ende dieses Wartens."""
    if (marke := _sperr_marke(session_id, session_state)) is not None:
        session_state.setdefault("entities", {})[SPERRE_RUHT] = marke


def sperre_aufraeumen(session_id: str, session_state: dict[str, Any]) -> None:
    """Die Marken von :func:`sperre_aussetzen` und „später“ (K7) gelten nur für ihr Warten —
    danach weg."""
    marke = _sperr_marke(session_id, session_state)
    entities = session_state.get("entities")
    for name in _RUHT:
        if isinstance(entities, dict) and name in entities and entities[name] != marke:
            entities.pop(name, None)


def spaeter_merken(session_id: str, session_state: dict[str, Any]) -> bool:
    """Paket K7: die Sperre dieses Wartens ruht für diese Sitzung — ``False`` ohne Warten."""
    if (marke := _sperr_marke(session_id, session_state)) is None:
        return False
    session_state.setdefault("entities", {})[SPAETER] = marke
    return True


def gesperrt(session_id: str, session_state: dict[str, Any]) -> str | None:
    """Die Kennung des Ablaufs, wenn ein Lauf dieser Person an einem Auftragsschritt mit
    ``warten: gesperrt`` wartet (K2b) — sonst ``None``, auch solange die Sperre nach einer Krise
    ruht. Ein veralteter Verweis (eine zweite Sitzung holte ab) zeigt höchstens einmal den
    Hinweis; „Stand prüfen“ frischt ihn auf."""
    wartend = _wartend(session_id, session_state)
    if wartend is None:
        return None
    marke = _sperr_marke(session_id, session_state)
    entities = session_state.get("entities") or {}
    if any(entities.get(name) == marke for name in _RUHT):
        return None                     # nach einer Krise bzw. „Später weitermachen“ (K7)
    lauf, ablauf = wartend
    return ablauf.id if sperrt(ablauf, lauf) else None


async def gesperrt_antwort(session: Any, req: ChatRequest, ablauf_id: str) -> ChatResponse:
    """Der Hinweis auf eine getippte Nachricht oder einen anderen Knopf im gesperrten Lauf."""
    return await _mit_knopf(session, req, "action.ablauf.auftragGesperrt", ablauf_id,
                            spaeter=True)


async def _mit_knopf(session: Any, req: ChatRequest, schluessel: str,
                     ablauf_id: str, *, spaeter: bool = False) -> ChatResponse:
    antwort = await basis.nur_text(session, req, schluessel)
    antwort.quick_replies = knoepfe(ablauf_id, resolve_locale(req.environment.locale),
                                    spaeter=spaeter)
    return antwort


def abbruch_satz(ausgang: str) -> str:
    """Paket K4: der Satz nach dem Abbruch eines Auftrags des MCP (``zug_basis.auftraege_beenden``)
    — „Stand unklar“ ohne Antwort bzw. mit ``outcomeOpen``."""
    return {"offen": "action.ablauf.auftragStandUnklar",
            "weiter": "action.ablauf.auftragLaeuftWeiter"}.get(ausgang,
                                                              "action.ablauf.auftragAbgebrochen")


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
    ausgang = await basis.abbrechen(session, v, lauf, entities, aufrufer)
    if not ausgang:
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    from boerdi.services import vorgang_aktion

    # Zweites Review K2b, Befund 8: ohne den Schlüssel der Person (Anmeldung abgelaufen) endet der
    # Auftrag nur hier — bei der b-api läuft er weiter. Das sagt die Antwort.
    # Review AS-8a, Befund 6: einen Trocken-Auftrag gibt es bei der b-api gar nicht.
    # Paket K4: über den MCP sagt der Ausgang im Zug, was geschah.
    trocken = offen is not None and client.ist_trocken(offen.job_id)
    schluessel = (abbruch_satz(ausgang) if offen is not None and mcp_starter.ist_mcp(offen.job_id)
                  else "action.ablauf.auftragAbgebrochen" if darf_jobs() or trocken
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
    if (not treiber.gilt(ablauf, lauf)
            or auftrag is None or auftrag.schritt != lauf.get("schritt")):
        await basis.abbrechen(session, v, lauf, entities, aufrufer)
        return await basis.nur_text(session, req, "action.ablauf.unbekannt", entities)
    # Paket K7 (E17): „Stand prüfen“ (auch nach „Fortsetzen“) führt zum Auftrag zurück — nach
    # „Später weitermachen“ oder einer Krise greift die Sperre wieder, solange er läuft. Gleich
    # gespeichert: nicht jeder Weg unten schreibt ``entities``.
    geraeumt = False
    for name in _RUHT:
        if name in entities:
            entities.pop(name)
            geraeumt = True
    if geraeumt:
        await basis.update_session(session, req.session_id, entities=entities)
    spaeter = sperrt(ablauf, lauf)
    if mcp_starter.ist_mcp(auftrag.job_id) and has_personal_auth():
        await mcp_starter.nachholen()     # Review A2: fehlen die Werkzeuge kurz, neu fragen
    # Review AS-8a, Befund 2: einen Trocken-Auftrag beantwortet der Client selbst, ohne Schlüssel.
    if not abrufbar(auftrag.job_id):
        # Mit ``B_API_KEY`` sähe der Chatbot den Auftrag der Person nicht (K22) — und fragte nicht.
        return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id,
                                spaeter=spaeter)
    await basis.frei(session)             # M7: die b-api-Abfrage hält keine DB-Verbindung
    vorweg: list[str] = []
    vom_client = False                    # der Stand kam nicht vom Träger, sondern vom Client
    try:
        stand = await stand_von(auftrag.job_id)
    except client.AuftragFehler as fehler:
        logger.info("Auftrag: Stand nicht abrufbar (%s)", fehler.grund)
        if fehler.grund == "job_unbekannt":
            # Paket K8 (E17): den Stand eines Auftrags dieses Vorgangs kennt der MCP nicht mehr
            # (Neustart, Frist) bzw. der Start blieb ohne Antwort — kein Fehlschlag des Flows. Die
            # Ergebnisse stehen an den Datensätzen: weiter zum nächsten Schritt (``lesen``).
            vorweg.append(stand_weg_satz(auftrag.job_id, lauf,
                                         resolve_locale(req.environment.locale)))
            stand = client.Stand("fertig")
        elif fehler.grund == "abgewiesen":
            # Ein abgewiesener Schlüssel heilt kein zweiter Klick — der Lauf endet, damit ein
            # Neustart (Wendung, Modul) nicht am wartenden Lauf hängt (Review Q2, Befund 1).
            # Kein DELETE mit dem Schlüssel, den die b-api eben abwies (Review Job-Vertrag, 5).
            await basis.abbrechen(session, v, lauf, entities, aufrufer, bei_der_b_api=False)
            return await basis.nur_text(session, req, "action.ablauf.auftragAbgewiesen", entities)
        elif fehler.grund not in ENDGUELTIG:
            return await _mit_knopf(session, req, "action.ablauf.auftragNichtAbrufbar", ablauf.id,
                                    spaeter=spaeter)
        else:
            stand = client.Stand("fehler")  # Auftrag weg (30 Tage) oder Aufträge aus: gescheitert
            vom_client = True
    # Durchtest Paket K (19.11.): ein Flow, der beim Träger scheiterte, sagt es selbst — nicht nur
    # der Ersatzweg („nicht eingerichtet … Anmeldung abgelaufen“). Nicht, wenn der Stand oben aus
    # einem endgültigen Grund des Clients entstand (Auftrag weg, Aufträge aus).
    fehlschlag = (fehlschlag_satz(stand.fehlercode, resolve_locale(req.environment.locale))
                  if stand.status == "fehler" and not vom_client else None)
    if stand.status == "laeuft":
        if zahlen := client.fortschritt_zahlen(stand.fortschritt):
            # Paket K1 (E16): „k von n fertig“ aus ``progress``; gescheiterte getrennt (Durchtest),
            # geprüft wie in ``/api/ui/auftrag/stand`` (drittes Review)
            schluessel = ("action.ablauf.auftragLaeuftFortschrittFehler"
                          if "fehlgeschlagen" in zahlen
                          else "action.ablauf.auftragLaeuftFortschritt")
            antwort = await basis.fester_text(session, req, bot_text(
                resolve_locale(req.environment.locale), schluessel,
                **zahlen), knoepfe=knoepfe(ablauf.id,
                                                       resolve_locale(req.environment.locale),
                                                       spaeter=spaeter))
            return antwort
        return await _mit_knopf(session, req, "action.ablauf.auftragLaeuft", ablauf.id,
                                spaeter=spaeter)
    # Job-Vertrag 2026-11-07: ``warnings`` (einzelne Iterationen scheiterten) reist im Teil mit —
    # ein Folgeschritt soll einen Teilerfolg erkennen können.
    ergebnis = ({"outputs": stand.outputs, "dateien": stand.dateien,
                 **({"warnungen": True} if stand.warnungen else {})}
                if stand.status == "fertig" else None)
    # Paket K2d-2: die Dateien, die der Schritt nennt — ihr Text unter ``texte.<outputId>``, was
    # nicht ging, unter ``dateien_fehlen.<outputId>``. Noch ohne DB-Verbindung (M7).
    schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if (ergebnis is not None and schritt is not None and schritt.dateien_holen
            and mcp_starter.ist_mcp(auftrag.job_id)):
        # W5 (Datei eines Flows) baut der MCP erst, wenn ein Flow Dateien liefert
        ergebnis["texte"] = {}
        ergebnis["dateien_fehlen"] = dict.fromkeys(schritt.dateien_holen, "nicht_verfuegbar")
    elif ergebnis is not None and schritt is not None and schritt.dateien_holen:
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
            antwort.quick_replies = knoepfe(ablauf.id, resolve_locale(req.environment.locale),
                                            spaeter=spaeter)
            return antwort
        entities.pop(DATEI_VERSUCHE_KEY, None)
        ergebnis["texte"] = texte
        if fehlen:
            ergebnis["dateien_fehlen"] = fehlen
    aus = await basis.rechne(session, ablauf, treiber.weiter_auftrag(
        ablauf, dict(lauf), ergebnis, basis.umgebung(session, req, entities, blocked_tools),
        fehlschlag=fehlschlag))
    if aus is None:
        return await basis.nur_text(session, req, "action.ablauf.fehler", entities)
    try:
        await ablage.abschliessen(session, auftrag, stand.status)
        v = await basis.festhalten(session, v, aus, session_id=req.session_id)
        await session.commit()
    except vorgaenge.FESTHALTEN_KONFLIKTE:
        await session.rollback()
        await basis.nicht_festgehalten(aus)
        return await basis.nur_text(session, req, "action.ablauf.konflikt", entities)
    entities[arbeitsstand.VERWEIS] = arbeitsstand.verweis_fuer(v, aufrufer)
    if bericht := bericht_satz(aus, resolve_locale(req.environment.locale)):
        vorweg.append(bericht)
    aus.texte[:0] = vorweg
    return await basis.antwort(session, req, session_state, aus, ablauf)


def fehlschlag_satz(fehlercode: str | None, sprache: str) -> str:
    """Durchtest Paket K (19.11.): der Satz zu einem gescheiterten Flow — mit dem Code nur, wenn er
    in :data:`FEHLERCODES` steht."""
    code = f" ({fehlercode})" if fehlercode in FEHLERCODES else ""
    return bot_text(sprache, "action.ablauf.auftragFehlgeschlagen", code=code)


def stand_weg_satz(job_id: str, lauf: dict[str, Any], sprache: str) -> str:
    """Der Satz, wenn der Stand nicht (mehr) abrufbar ist und der Lauf weiter liest (K8/E17).

    - Review A1: ein offener Start (etwa 429 mit ``outcomeOpen``) lief vielleicht nie —
      ``auftragOffenGelesen``; folgt im Stapel noch ein Teil (zweites Review, Z2),
      ``auftragTeilUnklar`` (es geht mit dem nächsten Teil weiter).
    - Sonst (``unknown_job``, etwa nach einem Neustart des MCP) ``auftragStandWeg``."""
    if not mcp_starter.ist_offen(job_id):
        return bot_text(sprache, "action.ablauf.auftragStandWeg")
    stapel = lauf.get(auftrag_teile.STAPEL)
    if auftrag_teile.ist_stapel(stapel) and stapel["i"] + 1 < stapel["n"]:
        return bot_text(sprache, "action.ablauf.auftragTeilUnklar", teil=stapel["i"] + 1,
                        naechster=stapel["i"] + 2)
    return bot_text(sprache, "action.ablauf.auftragOffenGelesen")


def abrufbar(job_id: str) -> bool:
    """Darf dieser Zug den Stand abfragen? Trocken: immer; über den MCP: bestätigte Anmeldung
    (Review A8: auch für eine offene Kennung) und das Werkzeug ``wlo_flow_status`` (die offene
    Kennung fragt den MCP nicht); direkt: der durchgereichte Schlüssel (``darf_jobs``)."""
    if client.ist_trocken(job_id):
        return True
    if mcp_starter.ist_mcp(job_id):
        return has_personal_auth() and (mcp_starter.ist_offen(job_id)
                                        or faehigkeiten.kennt_werkzeug(mcp_starter.STAND))
    return darf_jobs()


async def stand_von(job_id: str) -> client.Stand:
    """Paket K1: der Stand beim Träger, der den Auftrag gestartet hat (Kennung mit ``mcp:``)."""
    if mcp_starter.ist_mcp(job_id):
        return await mcp_starter.stand(job_id)
    return await client.stand(job_id)


def _erschlossen(eintrag: Any) -> bool:
    if not isinstance(eintrag, dict):
        return False
    geschrieben = eintrag.get("written")
    geaendert = geschrieben.get("changedKeys") if isinstance(geschrieben, dict) else None
    return bool(isinstance(geaendert, list) and geaendert) or str(
        eintrag.get("status") or "").lower() in ("ok", "success", "succeeded", "written")


def bericht_satz(aus: Any, sprache: str) -> str | None:
    """Paket K8: der Bericht des Flows je Knoten (``outputs.report``) an die Person nur als Zahlen —
    „n Materialien erschlossen, m nicht“. Ohne Bericht ``None``."""
    teil = next((wert for _n, typ, wert, _z in aus.neue_teile if typ == typen.AUFTRAG), None)
    outputs = teil.get("outputs") if isinstance(teil, dict) else None
    bericht = outputs.get("report") if isinstance(outputs, dict) else None
    if not isinstance(bericht, list) or not bericht:
        return None
    n = sum(1 for e in bericht if _erschlossen(e))
    return bot_text(sprache, "action.ablauf.auftragBericht", n=n, m=len(bericht) - n)
