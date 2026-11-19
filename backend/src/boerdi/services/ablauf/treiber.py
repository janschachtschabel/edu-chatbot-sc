"""Der lokale Treiber eines Ablaufs (Paket A1, Plan 2026-11-05 §4, §9) — rechnet ohne Modell.

:func:`starten` und :func:`weiter` gehen die Schritte durch, bis ein abfragendes Modul auf die
Person wartet (``offener_block``) oder ein ``ende`` kommt; höchstens ``RECHENSCHRITTE`` je Aufruf
(die Prüfung beim Speichern hält jeden Weg darunter). Daten lesen Schritte über ``{"$teil": …}``
aus dem Vorgang (der Lader der :class:`Umgebung`, davor die in diesem Aufruf neu entstandenen
Teile); ein Werkzeug-Ergebnis mit ``schreibt`` wird ein neuer Teil (:attr:`Ausgabe.neue_teile` —
gespeichert wird beim Aufrufer). Ein fehlender Teil oder ein leeres
Ergebnis geht zu ``bei_fehler``, sonst endet der Lauf mit ``fehler``.

Grenzen der Umgebung: Werkzeuge, die die Sicherheitsprüfung dieses Zugs sperrt (``gesperrt``), und
ausgeschaltete Module (Studio-Schalter) liefern nichts; lesende WLO-Werkzeuge bekommen keine Teile
(``teil_verweise.darf``) — außer einer Kennung aus den Startdaten der Gastseite (Entscheid AS-4a,
Befund 10; :func:`_start_kennungen`); über seinen Dienst baut der Treiber nur Module ohne
Sprachmodell.

Der Lauf selbst ist ein kleines Dict (``akte.lauf`` im Vorgang): Ablauf, Fassung (Streuwert der
Schritte — geänderte Schritte setzen einen alten Lauf nicht fort; Titel und Schalter zählen nicht),
Schritt, offener Block, Status, letzte Wahl. Reine Funktionen bis auf die Nähte der Umgebung.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any, Final, TypeGuard

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain import seiten_muster
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.domain.write_confirm import SCHLUESSEL_FELDER
from boerdi.services import teil_verweise
from boerdi.services.ablauf import (
    auftrag_teile,
    platzhalter,
    startdaten,
    typen,
    vergleich,
    werkzeuge,
)
from boerdi.services.ablauf.pruefung import (
    RECHENSCHRITTE,
    mit_wahl,
    nachfolger,
    schreibt_mit_freigabe,
    wendung,
)
from boerdi.services.ablauf.treiber_bloecke import fortschritt as _fortschritt
from boerdi.services.ablauf.treiber_bloecke import modul_block as _modul_block
from boerdi.services.arbeitsstand_teile import Teil  # R2-h: eine Definition

logger = logging.getLogger(__name__)

#: Status eines wartenden Laufs (weitere: ``laeuft``, ``fertig``, ``fehler``, ``abgebrochen`` —
#: Schritte geändert oder Ablauf ausgeschaltet, während er wartete).
WARTET: Final = "wartet_person"
#: Paket A2b: ein ``agent``-Schritt — die KI arbeitet mit der Person, „Weiter“ setzt fort.
WARTET_KI: Final = "wartet_ki"
#: Paket K1a: ein ``auftrag``-Schritt — ein b-api-Auftrag läuft, „Stand prüfen“ holt ihn ab.
WARTET_AUFTRAG: Final = "wartet_auftrag"
#: Paket S: ein schreibender ``werkzeug``-Schritt hat seine Änderung vorgelegt — er wartet auf die
#: Freigabe der Person (das „ja“ löst der Vorlauf ein wie im Chat, ``ablauf/freigabe_zug``).
WARTET_FREIGABE: Final = "wartet_freigabe"
#: AS-3a: ein Schritt mit Schnellantworten oder Freitext wartet auf die Wahl der Person.
WARTET_WAHL: Final = "wartet_wahl"
#: AS-7a (F-1): ein ``seite``-Schritt mit ``ankunft`` wartet, bis die Person auf der Seite ist.
WARTET_SEITE: Final = "wartet_seite"
#: Alle Status, an denen ein Lauf auf etwas wartet — die EINE Liste (Review AS-7a, Befund 2: ein
#: neuer Status fehlte in ``zug.lauf_wartet`` und ließ Wendungen einen wartenden Lauf ersetzen).
WARTEND: Final = (WARTET, WARTET_KI, WARTET_AUFTRAG, WARTET_FREIGABE, WARTET_WAHL, WARTET_SEITE)
#: AS-3a: so lang wird ein getippter Freitext höchstens als Teil gemerkt.
FREITEXT_ZEICHEN: Final = 2000
#: WF-2: ein Synonym oder eine Beschriftung zählt als Teilwort erst ab dieser Länge (wie die
#: Gruppenwahl der eingebauten Führung).
_TEILWORT_MIN: Final = 3



@dataclass(frozen=True)
class Vorlage:
    """Paket S: die Vorschau eines schreibenden Werkzeugs — der Text (ohne Schlüssel) und der
    Schlüssel, mit dem die Freigabe einlöst; ``schluessel`` ``None``: es gibt nichts zu ändern.
    ``ausfall`` (Review S2/S3, Befunde 8/9): ``voruebergehend`` — WLO ausgelastet, keine Antwort,
    Anmeldung abgewiesen: der Lauf wartet, ``text`` sagt es; ``abgelehnt`` — der Server lehnt die
    Änderung ab: ``text`` nennt den Grund, dann ``bei_fehler``."""

    text: str
    schluessel: str | None
    ausfall: str | None = None


@dataclass(frozen=True)
class Umgebung:
    teile: Callable[[str], Awaitable[Any]]
    sprache: str = "de"
    #: Ein lesendes MCP-Werkzeug rufen → Text (oder ``None``).
    mcp: Callable[[str, dict[str, Any]], Awaitable[Any]] | None = None
    #: Von der Sicherheitsprüfung dieses Zugs gesperrte Werkzeuge (Review A1, Befund 2).
    gesperrt: frozenset[str] = frozenset()
    #: Paket K1a: einen Auftrag starten (Flow, Eingaben) → Job-ID oder ``None``; ``None`` als Naht =
    #: Aufträge hier nicht möglich (nicht eingerichtet oder ohne Anmeldung).
    auftrag_starten: Callable[[str, dict[str, Any]], Awaitable[str | None]] | None = None
    #: Paket S: ein schreibendes Werkzeug OHNE Schlüssel rufen (Vorschau) → :class:`Vorlage` oder
    #: ``None`` (Fehler, keine Antwort, ohne Schreibrecht); ``None`` als Naht = hier nicht möglich.
    vorlegen: Callable[[str, dict[str, Any]], Awaitable[Vorlage | None]] | None = None
    #: AS-1, nur die Simulation (``simulation``): das Ergebnis eines Werkzeug-Schritts
    #: (Schritt-ID, Werkzeug, Argumente) statt Dienst oder MCP — im Betrieb ``None``.
    ersatz: Callable[[str, str, dict[str, Any]], Awaitable[Any]] | None = None
    #: AS-1, nur die Simulation: Module ohne ihren Dienst — passen die Daten nicht zum Vertrag,
    #: steht ein Platzhalter-Block da (die Simulation prüft den Weg, nicht das Modul).
    simulation: bool = False
    #: AS-1: jeder besuchte Schritt (der Weg eines Testfalls); im Betrieb ``None``.
    protokoll: Callable[[str], None] | None = None
    #: AS-7a (F-6): die Seite der Person in diesem Zug (``Environment.page``) — für ``wenn_seite``
    #: und die Ankunft an einem ``seite``-Schritt. Eingabe des Widgets, nur ein Vergleich.
    seite: str = "/"
    #: AS-8a (P-6): Probe der Studio-Vorschau — der neue Lauf trägt ``probe`` und darf damit auch
    #: einen ausgeschalteten Ablauf weiterführen (:func:`gilt`).
    probe: bool = False
    #: Zweites Review TG-2: die Kennung des lesbaren Dokuments der Sitzung (für den Dienst
    #: ``bereitgestellt``); ``None`` = nicht prüfbar (Simulation, Studio-Probe).
    dokument_id: Callable[[], Awaitable[str | None]] | None = None
    #: Plan 2026-11-16, TG-3e: die Kennungen aller lesbaren Dokumente der Sitzung.
    dokument_ids: Callable[[], Awaitable[list[str]]] | None = None
    #: Plan 2026-11-16, TG-6: bietet das Upload-Feld die Ablage in WLO an (für ``bereitgestellt``,
    #: ``werkzeuge.DienstKontext.wlo_ablage``); ``None`` = nein.
    wlo_ablage: Callable[[], bool] | None = None
    #: Review TG-4–6, MINOR 8: geht der gründliche Weg ganz (Ablage, Auftrag, Flow freigegeben)?
    wlo_erschliessen: Callable[[], bool] | None = None
    #: Durchtest Paket K (19.11.): öffnete eine Anmeldung den gründlichen Weg
    #: (``werkzeuge.DienstKontext.nach_anmeldung``)?
    nach_anmeldung: Callable[[], bool] | None = None
    #: Review Paket U (19.11.), MAJOR 3: die Belegung der Sitzung für das Upload-Feld
    #: (``ui_module/aufruf.Umgebung.belegung``); ``None`` = nicht gezählt (Simulation, Probe).
    belegung: Callable[[], Awaitable[tuple[int, int]]] | None = None


@dataclass
class Ausgabe:
    lauf: dict[str, Any]
    texte: list[str] = field(default_factory=list)
    bloecke: list[UiBlock] = field(default_factory=list)
    neue_teile: list[Teil] = field(default_factory=list)
    #: Schritt-ID, an dem der Lauf mit Fehler endete.
    fehler: str | None = None
    #: Paket A2b: „Weiter“ am ``agent``-Schritt, aber dessen ``ausgabe`` fehlt noch (Lauf wartet).
    fehlt_teil: str | None = None
    #: Paket K1a: gestarteter Auftrag ``{flow, job_id, schritt}`` — der Aufrufer hält ihn fest.
    auftrag: dict[str, str] | None = None
    #: Paket S: die vorgelegte Änderung ``{werkzeug, args, schluessel, vorschau, schritt}`` — der
    #: Aufrufer merkt sie als offene Abnahme und zeigt die Vorschau (nie dem Modell).
    freigabe: dict[str, Any] | None = None
    #: AS-3a: die angebotene Wahl ``{schritt, optionen: [(id, label)], freitext}`` — der Aufrufer
    #: zeigt sie als Chips.
    wahl: dict[str, Any] | None = None
    #: AS-Ua (Review, Befund 2): ein Text setzte Inhalt ein, der von einer KI stammen kann — ein
    #: Teil (``{teil.…}``) oder Startdaten eines KI-Vorschlags (``{start.…}``). Dann kein
    #: ``fester_text``.
    ki_inhalt: bool = False
    #: AS-7a (F-2): die Wege der ``seite``-Schritte dieses Aufrufs ``[{url, label}]`` — der Aufrufer
    #: zeigt sie als Navigations-Chips (``__fuehrung__``, ``seite_zug.knopf``).
    navigation: list[dict[str, str]] = field(default_factory=list)
    #: Zweites Review TG-2 (MAJOR 1): Teile, die eine gewählte Schnellantwort verwirft
    #: (``verwirft``) — der Aufrufer entfernt sie aus dem Vorgang, VOR den ``neue_teile``.
    verworfen: list[str] = field(default_factory=list)
    #: Paket N4: die vorgelegte Freigabe eines schreibenden Auftrags ``{flow, erst, token,
    #: laeuft_ab, eintraege, probleme, schritt, id}`` — der Aufrufer merkt den Schlüssel in der
    #: Sitzung und zeigt die Box (``auftrag_freigabe.merken``), nie dem Modell.
    auftrag_freigabe: dict[str, Any] | None = None


#: Ein beendeter Lauf (für Leiste, Zug und Prüfungen — eine Stelle, Kleinigkeit 9 des zweiten
#: Reviews AS-U).
BEENDET: Final = ("fertig", "fehler", "abgebrochen")


def fassung(ablauf: AblaufArea) -> str:
    # ``exclude_none`` (Querschnitts-Review): ein neues Feld mit Vorgabe ``None`` änderte sonst die
    # Fassung jedes Ablaufs — jeder Deploy brach wartende Läufe ab. Felder mit anderer Vorgabe
    # (``[]``, ``False``, eine Zahl) ändern sie weiterhin; die Umstellung selbst ändert sie einmal
    # (Deploy-Notiz in ``docs/aenderungen/2026-11-06-paket-q2-ablaeufe.md``).
    roh = json.dumps([s.model_dump(mode="json", exclude_none=True) for s in ablauf.schritte],
                     sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(roh.encode()).hexdigest()[:12]


def _text(s: Schritt, sprache: str) -> str:
    texte = s.text or {}
    return (texte.get(sprache) or texte.get("de") or "").strip()


def _freigabe_satz(s: Schritt, sprache: str) -> str:
    texte = s.freigabe or {}
    return (texte.get(sprache) or texte.get("de") or "").strip()


class _Teile:
    """Die neuen Teile dieses Aufrufs vor dem Lader des Vorgangs."""

    def __init__(self, lader: Callable[[str], Awaitable[Any]]) -> None:
        self.lader, self.neu = lader, {}

    async def __call__(self, name: str) -> Any:
        return self.neu[name] if name in self.neu else await self.lader(name)


async def _daten(roh: dict[str, Any] | None, teile: _Teile) -> tuple[dict[str, Any], list[str]]:
    """Die Daten eines Modul-Schritts. Anders als bei der KI darf hier die oberste Ebene ein Verweis
    sein (``daten: {"$teil": "draft"}``, K2d-1 auch mit ``pfad``) — die Definition ist beim
    Speichern geprüft."""
    if (v := teil_verweise.verweis(roh)) is not None:
        name, pfad = v
        gefunden = await teile(name) if teil_verweise.NAME.match(name) else None
        wert = teil_verweise.aufloesen(gefunden, roh) if gefunden is not None else None
        return ((copy.deepcopy(wert), []) if isinstance(wert, dict)
                else ({}, [teil_verweise.bezeichnung(name, pfad)]))
    return await teil_verweise.einsetzen(dict(roh or {}), teile)


async def _werkzeug(s: Schritt, args: dict[str, Any], umgebung: Umgebung) -> Any:
    name = s.werkzeug or ""
    if name in umgebung.gesperrt or werkzeuge.DIENST_MCP.get(name, frozenset()) & umgebung.gesperrt:
        logger.info("Ablauf: Werkzeug %s von der Sicherheitsprüfung gesperrt", name)
        return None
    if umgebung.ersatz is not None:
        return await umgebung.ersatz(s.id, name, args)
    if name in werkzeuge.DIENSTE:
        return await werkzeuge.DIENSTE[name](args, dienst_kontext(umgebung))
    if name in werkzeuge.LESENDE_MCP and umgebung.mcp is not None:
        return await umgebung.mcp(name, args)
    return None


def dienst_kontext(umgebung: Umgebung) -> werkzeuge.DienstKontext:
    """Was ein Dienst außer seinen Argumenten liest (zweites Review TG-2) — aus der Umgebung."""
    return werkzeuge.DienstKontext(teile=umgebung.teile, sprache=umgebung.sprache,
                                   dokument_id=umgebung.dokument_id,
                                   dokument_ids=umgebung.dokument_ids,
                                   wlo_ablage=umgebung.wlo_ablage,
                                   wlo_erschliessen=umgebung.wlo_erschliessen,
                                   nach_anmeldung=umgebung.nach_anmeldung)


async def _start_kennungen(ablauf: AblaufArea, s: Schritt, teile: Callable[[str], Awaitable[Any]],
                           lauf: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Kennungen aus den Startdaten in die Argumente eines lesenden WLO-Werkzeugs setzen — nur von
    der Gastseite und nur als UUID; sonst fehlt das Argument (``bei_fehler``)."""
    args = dict(s.argumente or {})
    if s.werkzeug not in werkzeuge.LESENDE_MCP:
        return args, []
    felder = startdaten.kennungsfelder(ablauf)
    kaputt: list[str] = []
    for k, v in list(args.items()):
        if (feld := startdaten.kennung_verweis(felder, v)) is None:
            continue
        wert = teil_verweise.stelle(await teile(typen.START_TEIL), feld)
        if lauf.get("start_quelle") == startdaten.QUELLE_GASTSEITE and startdaten.ist_kennung(wert):
            args[k] = wert
        else:
            kaputt.append(f"start.{feld}")
    return args, kaputt


async def _einsetzen(aus: Ausgabe, text: str, teile: Callable[[str], Awaitable[Any]],
                     lauf: dict[str, Any], ablauf: AblaufArea, sprache: str) -> str:
    """Platzhalter einsetzen und merken, ob dabei Inhalt einer KI in den Text kommen kann."""
    arten = platzhalter.herkuenfte(text)
    if "teil" in arten or ("start" in arten
                           and lauf.get("start_quelle") != startdaten.QUELLE_GASTSEITE):
        aus.ki_inhalt = True
    text, fremd = await wahl_einsetzen(text, ablauf, sprache, teile)
    if fremd:
        aus.ki_inhalt = True
    return await platzhalter.einsetzen(text, teile)


#: WF-3 (Plan 2026-11-15): ``{wahl.<teil>}`` — die Beschriftung der gewählten Option.
#: Der Name wie ein Teil (``teil_verweise.NAME``; Review WF-3/4, NIT).
WAHL_PLATZHALTER: Final = re.compile(r"\{wahl\.([a-z][a-z0-9_]{1,29})\}")


async def wahl_einsetzen(text: str, ablauf: AblaufArea, sprache: str,
                         teile: Callable[[str], Awaitable[Any]]) -> tuple[str, bool]:
    """``{wahl.<teil>}`` durch die Beschriftung der gewählten Option in ``sprache`` ersetzen (WF-3).
    Der Teil trägt das deutsche Label (:func:`wahl_wert`); darüber wird die Option gefunden. Ist es
    keine Option (getippter Freitext), steht der Wert entschärft da — zweiter Rückgabewert
    ``True``: Eingabe der Person im Text (wie ``{teil.…}``, kein fester Text)."""
    namen = dict.fromkeys(WAHL_PLATZHALTER.findall(text or ""))
    if not namen:
        return text, False
    fremd = False
    ersatz: dict[str, str] = {}
    for name in namen:
        wert = await teile(name)
        option = next((o for s in ablauf.schritte if s.schreibt == name
                       for o in s.optionen or [] if wahl_wert(o) == wert), None)
        if option is not None:
            # Review 16.11. (Führung wie Tour, m2): die Beschriftung ist Text der Redaktion wie
            # der Schritt selbst — unverändert, sonst stünde „Content\-Abnehmer“ im Verlauf
            ersatz[name] = " ".join(_label(option, sprache).split())
        else:
            fremd = fremd or bool(wert)
            ersatz[name] = platzhalter.entschaerft(wert) if wert else "—"
    return WAHL_PLATZHALTER.sub(lambda m: ersatz[m.group(1)], text), fremd


def _leere_auswahl(definition: dict[str, Any] | None, args: dict[str, Any]) -> bool:
    """Querschnitts-Review F/T, Befund 1: ein Argument, das eine Auswahl aus einem Teil ist
    (``liste``), ergab nichts — ein Auftrag über null Einträge startet nicht (``bei_fehler``) und
    belegt keinen der offenen Jobs."""
    return any(isinstance(d, dict) and "liste" in d and args.get(k) == []
               for k, d in (definition or {}).items())


def _zusammenfassung(wert: Any) -> str:
    if isinstance(wert, dict) and isinstance(wert.get("titel"), str):
        return wert["titel"][:80]
    return type(wert).__name__


async def _waehle(s: Schritt, teile: _Teile, gewaehlt: list[str], seite: str) -> str | None:
    for regel in s.weiter if isinstance(s.weiter, list) else []:
        if regel.sonst:
            return regel.sonst
        if regel.wenn_teil and await teile(regel.wenn_teil) is not None:
            return regel.dann
        if regel.wenn_gewaehlt and regel.wenn_gewaehlt in gewaehlt:
            return regel.dann
        w = regel.wenn_wert
        if w is not None and await vergleich.greift(w.quelle, w.vergleich, w.wert, teile):
            return regel.dann
        if regel.wenn_seite and seiten_muster.passt(seite, regel.wenn_seite):
            return regel.dann
    return None


#: Plan 2026-11-16, Review TG-4–6, Befund 10: an diesen Status wartet der Lauf auf die Person —
#: ein Halt, den die Leiste zählt (``lauf["halte"]``, ``fortschritt.position``).
_HALT_STATUS: Final = frozenset({WARTET, WARTET_KI, WARTET_AUFTRAG, WARTET_FREIGABE,
                                 WARTET_WAHL, WARTET_SEITE})


async def _rechne(ablauf: AblaufArea, lauf: dict[str, Any], start: int,
                  umgebung: Umgebung) -> Ausgabe:
    """Die Schritte ab ``start`` rechnen (:func:`_rechne_schritte`) und den Halt zählen.

    Befund 10: Ein Lauf mit ``halte`` (seit dieser Fassung, :func:`starten`) zählt jeden Halt —
    nicht, wenn er am selben Schritt wieder hält, an dem er wartete (``erneut_vorlegen``, eine Wahl
    auf sich selbst), und nicht an einer Frage, die nur eine andere wiederholt (Hilfetext der
    Führung, ``fortschritt.wiederholt``). Ein älterer Lauf ohne ``halte`` bleibt ohne."""
    vorher = lauf.get("schritt")
    zaehlt = isinstance(lauf.get("halte"), int)
    erneut = zaehlt and lauf["halte"] > 0 and vorher == ablauf.schritte[start].id
    aus = await _rechne_schritte(ablauf, lauf, start, umgebung)
    neu = aus.lauf
    if zaehlt and neu.get("status") in _HALT_STATUS and not (
            erneut and neu.get("schritt") == vorher):
        from boerdi.services.ablauf.fortschritt import wiederholt

        if neu.get("schritt") not in wiederholt(ablauf):
            neu["halte"] = int(neu.get("halte") or 0) + 1
    return aus


async def _rechne_schritte(ablauf: AblaufArea, lauf: dict[str, Any], start: int,
                           umgebung: Umgebung) -> Ausgabe:
    aus = Ausgabe(lauf=lauf)
    teile = _Teile(umgebung.teile)
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i: int | None = start
    for _ in range(RECHENSCHRITTE):
        if i is None or i >= len(ablauf.schritte):
            break
        s = ablauf.schritte[i]
        lauf.update(schritt=s.id, offener_block=None)
        if umgebung.protokoll is not None:
            umgebung.protokoll(s.id)
        naechster = (nachfolger(ablauf, i) or [""])[0]
        fehler = False
        if s.typ in ("nachricht", "ende", "agent", "seite") or (s.typ == "modul" and s.text):
            if text := _text(s, umgebung.sprache):
                # AS-3b: Platzhalter aus den Teilen — auch aus diesem Zug (``teile``)
                aus.texte.append(await _einsetzen(aus, text, teile, lauf, ablauf, umgebung.sprache))
        if s.typ == "ende":
            lauf["status"] = "fertig"
            return aus
        if s.typ == "agent":
            lauf["status"] = WARTET_KI
            return aus
        if s.typ == "modul":
            daten, fehlt = await _daten(s.daten, teile)
            block = None if fehlt else await _modul_block(s.modul or "", daten,
                                                          simulation=umgebung.simulation,
                                                          belegung=umgebung.belegung)
            if block is None:
                fehler = True
            else:
                aus.bloecke.append(block)
                if block.art == "abfragen":
                    lauf.update(status=WARTET, offener_block=block.block_id)
                    return aus
        elif s.typ == "werkzeug" and schreibt_mit_freigabe(s):
            # Paket S: vorlegen, nie schreiben — der Schlüssel geht an die Abnahme, nicht zurück an
            # den Server. Teile wie für ein bestätigbares Werkzeug (``darf``, ``MAX_BYTES``).
            name = s.werkzeug or ""
            args, fehlt = await teil_verweise.einsetzen(dict(s.argumente or {}), teile, name)
            # nie mit Schlüssel (Review S1, Befund 1 — die Prüfung meldet ihn schon)
            args = {k: v for k, v in args.items() if k not in SCHLUESSEL_FELDER}
            vorlage = (None if fehlt or umgebung.vorlegen is None or name in umgebung.gesperrt
                       else await umgebung.vorlegen(name, args))
            if vorlage is None:
                fehler = True
            elif vorlage.ausfall == "voruebergehend":
                aus.texte.append(vorlage.text)
                lauf.update(status=WARTET_FREIGABE, freigabe_id=None)
                return aus
            elif vorlage.ausfall is not None:
                aus.texte.append(vorlage.text)
                fehler = True
            elif vorlage.schluessel is None:
                # nichts zu ändern — der gewünschte Stand gilt schon (FS-9)
                if s.schreibt:
                    teile.neu[s.schreibt] = {"unveraendert": True}
                    aus.neue_teile.append((s.schreibt, typen.dienst_typ(name),
                                           {"unveraendert": True},
                                           "unverändert"))
            else:
                if text := _freigabe_satz(s, umgebung.sprache):
                    aus.texte.append(await _einsetzen(aus, text, teile, lauf, ablauf,
                                                      umgebung.sprache))
                # Review S2/S3, Befund 6: jede Vorlage hat eine Kennung — ein „ja“ zu einer alten
                # setzt keinen neu gestarteten Lauf fort
                kennung = secrets.token_hex(6)
                aus.freigabe = {"werkzeug": name, "args": args, "schluessel": vorlage.schluessel,
                                "vorschau": vorlage.text, "schritt": s.id, "id": kennung}
                lauf.update(status=WARTET_FREIGABE, freigabe_id=kennung)
                return aus
        elif s.typ == "werkzeug":
            # Dienste bekommen Teile (geprüfte Definition), lesende WLO-Werkzeuge nicht (``darf``) —
            # außer einer Kennung aus den Startdaten der Gastseite (Entscheid AS-4a, Befund 10).
            ziel = None if s.werkzeug in werkzeuge.DIENSTE else s.werkzeug
            args, kaputt = await _start_kennungen(ablauf, s, teile, lauf)
            args, fehlt = await teil_verweise.einsetzen(args, teile, ziel)
            fehlt = fehlt or kaputt
            wert = None if fehlt else await _werkzeug(s, args, umgebung)
            if wert is None:
                fehler = True
            elif s.schreibt:
                # Review AS-Db, Befund 3: derselbe Typ wie in der Prüfung (``typen``)
                typ = "text" if isinstance(wert, str) else typen.dienst_typ(s.werkzeug or "")
                teile.neu[s.schreibt] = wert
                kurz = werkzeuge.ZUSAMMENFASSUNG.get(s.werkzeug or "", _zusammenfassung)
                aus.neue_teile.append((s.schreibt, typ, wert, kurz(wert)[:80]))
        elif s.typ == "auftrag":
            args, stuecke, fehlt, ohne = await _auftrag_stuecke(s, teile, umgebung.sprache)
            if ohne:
                # Durchtest Paket K (19.11.): md/txt gingen nicht an den Metadaten-Flow — vor dem
                # Start bzw. vor dem Ersatzweg, wenn keiner übrig blieb
                aus.texte.append(_teil_text(umgebung.sprache, "action.ablauf.metadatenOhneText"))
            stapel = None
            if len(stuecke) > 1 and (
                    stapel := auftrag_teile.neuer_stapel(args, len(stuecke))) is None:
                logger.warning("Auftrag: Argumente zu groß zum Aufteilen — Schritt scheitert")
                fehlt = True
            starte = _starter_fuer(umgebung.auftrag_starten, s)
            if getattr(starte, "nur_ueber_wlo", False):
                # Paket K2, Review A4: ein Flow, der ins Repository schreibt, geht nur über den
                # MCP (mit der Anmeldung der Person) — der ist hier nicht da
                aus.texte.append(_teil_text(umgebung.sprache, "action.ablauf.auftragNurUeberWlo"))
                starte = None
            # Paket N4: ein Schritt mit ``repo_schreibt`` über den MCP legt erst vor (Freigabe-Box)
            vorlegen = getattr(starte, "vorlegen", None) if s.repo_schreibt else None
            vorlage = (await vorlegen(s.flow or "", args, s.aufteilen)
                       if not fehlt and callable(vorlegen) else None)
            if vorlage is not None and vorlage.ausfall is None:
                kennung = secrets.token_hex(6)
                aus.auftrag_freigabe = {
                    "flow": s.flow or "", "erst": vorlage.erst, "token": vorlage.token,
                    "laeuft_ab": vorlage.laeuft_ab, "eintraege": vorlage.eintraege,
                    "probleme": vorlage.probleme, "schritt": s.id, "id": kennung}
                lauf.update(status=WARTET_FREIGABE, freigabe_id=kennung,
                            freigabe_args=vorlage.args)
                return aus
            if vorlage is not None and not vorlage.fehler and vorlage.probleme:
                aus.texte.append(_teil_text(umgebung.sprache, "action.ablauf.auftragFreigabeKeins",
                                            n=len(vorlage.probleme)))
            job = (None if fehlt or starte is None or vorlage is not None
                   else await starte(s.flow or "", stuecke[0]))
            # Plan 2026-11-16, Durchtest TG-7 (m5): hat die b-api abgewiesen, sagt die Naht
            # warum (``auftrag_zug._Starter.hinweis``) — vor dem Text des Ersatzwegs. Paket K1:
            # auch nach einem Start mit offenem Ausgang (dann gibt es eine Kennung)
            hinweis = getattr(starte, "hinweis", None)
            satz = hinweis(umgebung.sprache) if callable(hinweis) else None
            if job is None:
                fehler = True
                if satz:
                    aus.texte.append(satz)
                vorlaeufig = getattr(starte, "voruebergehend", None)
                if callable(vorlaeufig) and vorlaeufig() and (
                        frage := _rueckfrage(ablauf, s.id)) is not None:
                    # Paket K (Nachtrag MCP 18.11.): der Träger ist gerade nicht verfügbar — kein
                    # endgültiger Fehlschlag; zurück an die Frage davor, die Person versucht es
                    # gleich noch einmal
                    fehler, naechster = False, frage
            else:
                await _gestartet(aus, ablauf, s, job, stapel, satz, teile, umgebung.sprache)
                return aus
        elif s.typ == "verzweigung":
            naechster = await _waehle(s, teile, list(lauf.get("gewaehlt") or []),
                                      umgebung.seite) or ""
        elif s.typ == "seite":
            weg = {"url": s.url or "", "label": seiten_label(s, umgebung.sprache)}
            if not s.ankunft:
                aus.navigation.append(weg)
            elif not seiten_muster.passt(umgebung.seite, s.ankunft):
                aus.navigation.append(weg)
                lauf["status"] = WARTET_SEITE
                return aus
            # Querschnitts-Review AS-7, Befund 2: schon dort — ein Chip zur eigenen Seite stünde
            # vor dem eigentlichen nächsten Weg und lüde nur neu
        if not fehler and mit_wahl(s):
            # AS-3a: Text und Block stehen da — jetzt entscheidet die Person
            lauf["status"] = WARTET_WAHL
            aus.wahl = wahl_angebot(s, umgebung.sprache)
            return aus
        if fehler:
            logger.info("Ablauf %s: Schritt %s ohne Ergebnis", ablauf.id, s.id)
            if not s.bei_fehler:
                lauf["status"] = "fehler"
                aus.fehler = s.id
                return aus
            naechster = s.bei_fehler
        i = index.get(naechster)
    logger.warning("Ablauf %s: Schrittgrenze (%d) bei %s erreicht", ablauf.id, RECHENSCHRITTE,
                   lauf.get("schritt"))
    lauf["status"] = "fehler"
    aus.fehler = lauf.get("schritt")
    return aus


async def starten(ablauf: AblaufArea, umgebung: Umgebung, ab: int = 0,
                  gewaehlt: list[str] | None = None, start: dict[str, Any] | None = None,
                  start_quelle: str | None = None) -> Ausgabe:
    """Einen Lauf beginnen — ab Schritt ``ab`` (Modul-Auslöser: nach dem schon beantworteten
    Modul, mit dessen Wahl ``gewaehlt``). ``start`` (AS-4a, geprüft von ``startdaten``) wird vor
    dem ersten Schritt der Teil ``start`` — ``{start.feld}`` liest ihn wie ``{teil.start.feld}``."""
    # ``start`` (zweites Review AS-U, Befund 2): eine Marke je Lauf — die Leiste im Widget erkennt
    # daran einen neuen Lauf desselben Ablaufs (sonst bliebe sie nach „Neu starten“ zugeklappt).
    lauf = {"ablauf": ablauf.id, "fassung": fassung(ablauf), "schritt": ablauf.schritte[ab].id,
            "offener_block": None, "status": "laeuft", "gewaehlt": list(gewaehlt or []),
            "start": secrets.token_hex(4),
            # Befund 10 (Review TG-4–6): die Halte des Laufs für die Leiste (``_rechne``)
            "halte": 0}
    if umgebung.probe:
        lauf["probe"] = True
    if start is not None:
        # Woher die Daten kamen (Entscheid AS-4a, Befund 10): nur Kennungen der Gastseite dürfen
        # an lesende Werkzeuge
        lauf["start_quelle"] = start_quelle
        lader = umgebung.teile

        async def mit_start(name: str) -> Any:
            return start if name == typen.START_TEIL else await lader(name)

        umgebung = replace(umgebung, teile=mit_start)
    aus = await _rechne(ablauf, lauf, ab, umgebung)
    if start is not None:
        aus.neue_teile.insert(0, (typen.START_TEIL, typen.START, start, "Startdaten"))
    return aus


def seiten_label(s: Schritt, sprache: str) -> str:
    """AS-7a: die Aufschrift des Navigations-Chips — in der Sprache, sonst Deutsch."""
    texte = s.label or {}
    return ((texte.get(sprache) or "").strip() or (texte.get("de") or "").strip() or s.id)


async def weiter_seite(ablauf: AblaufArea, lauf: dict[str, Any], umgebung: Umgebung
                       ) -> Ausgabe | None:
    """AS-7a (F-4): die Person ist auf einer Seite angekommen (Seiten-Ping). ``None``, wenn der
    Lauf nicht an einem ``seite``-Schritt wartet, die Fassung nicht mehr gilt oder die Seite nicht
    passt — dann bleibt alles, wie es ist."""
    if lauf.get("status") != WARTET_SEITE or lauf.get("fassung") != fassung(ablauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index.get(str(lauf.get("schritt")))
    if i is None:
        return None
    s = ablauf.schritte[i]
    if s.typ != "seite" or not s.ankunft or not seiten_muster.passt(umgebung.seite, s.ankunft):
        return None
    naechster = (nachfolger(ablauf, i) or [""])[0]
    neu = {**lauf, "status": "laeuft"}
    if naechster not in index:
        # wie ``_rechne`` (Review AS-7a, Kleinigkeit 9): ohne Nachfolger endet der Lauf mit Fehler
        neu["status"] = "fehler"
        return Ausgabe(lauf=neu, fehler=s.id)
    return await _rechne(ablauf, neu, index[naechster], umgebung)


def wahl_wert(o: Any) -> str:
    """TB-T1: der Wert des Teils einer Wahl — das deutsche Label (sonst die Kennung), in jeder
    Sprache gleich (Review TB-T1, Befund 2); Simulation und Datensicht nutzen dieselbe Regel."""
    return _label(o, "de")


def _label(o: Any, sprache: str) -> str:
    """Das Label in der Sprache, sonst Deutsch, sonst die Kennung — ein Label nur aus Leerraum
    zählt nicht (Review AS-3a: sonst ein leerer Chip)."""
    return ((o.label.get(sprache) or "").strip() or (o.label.get("de") or "").strip() or o.id)


def wahl_angebot(s: Schritt, sprache: str) -> dict[str, Any]:
    """Die Wahl eines Schritts mit Schnellantworten — Label in der Sprache, sonst Deutsch."""
    return {"schritt": s.id, "freitext": s.freitext is not None,
            "optionen": [(o.id, _label(o, sprache)) for o in s.optionen or []]}


def wahl_aus_text(schritt: Schritt, text: str | None, sprache: str | None = None) -> str | None:
    """Die Kennung der Schnellantwort, deren Label (in einer Sprache) der getippte Text ist — wie
    eine Wendung verglichen (klein, Leerraum zusammengezogen). D2: Text, der einer Option
    entspricht, ist diese Wahl. Hier und nicht im Zug, damit die Simulation dasselbe tut
    (Querschnitts-Review AS-3, Befund 2).

    WF-2 (Plan 2026-11-15): ohne genauen Treffer die erste Option mit ``synonyme``, deren
    Beschriftung oder Synonym im Text steht (ab 3 Zeichen) — wie die Gruppenwahl der eingebauten
    Führung. Optionen ohne Synonyme treffen nur genau; bestehende Abläufe ändern sich nicht.

    Review 16.11. (Führung wie Tour, m1): Mit ``sprache`` sieht eine Option mit ``synonyme`` nur
    ihre Beschriftung in dieser Sprache (dazu die Synonyme) — wie die Tour, die nur die Beschriftung
    der Zugsprache kennt; sonst traf „Impressum“ über das englische „Press“. Optionen ohne
    Synonyme treffen weiter genau in jeder Sprache."""
    getippt = wendung(text or "")
    if not getippt:
        return None
    optionen = schritt.optionen or []
    genau = next((o.id for o in optionen
                  if any(wendung(label) == getippt for label in _labels(o, sprache))), None)
    if genau is not None:
        return genau
    if schritt.freitext is not None:
        return _mit_freitext(schritt, getippt, sprache)
    for o in optionen:
        if not o.synonyme:
            continue
        kandidaten = [wendung(w) for w in (*_labels(o, sprache), *o.synonyme)]
        if any(len(k) >= _TEILWORT_MIN and k in getippt for k in kandidaten):
            return o.id
    return None


def _labels(o: Any, sprache: str | None) -> list[str]:
    """Die Beschriftungen, die getippter Text treffen kann (Review 16.11., m1: mit Synonymen nur
    die der Zugsprache)."""
    if sprache is None or not o.synonyme:
        return list(o.label.values())
    return [o.label.get(sprache) or o.label.get("de") or ""]


def mehrdeutig(schritt: Schritt, text: str | None, sprache: str | None = None) -> bool:
    """Plan 2026-11-16, Nachprüfung TG-4–6 (MINOR 3): trifft der Satz an einer Frage mit
    ``synonyme_im_satz`` mehrere Optionen („Dateien aus meinem Ordner“, „meine PDF-Dateien“)? Dann
    ist er weder Wahl noch Freitext — die Frage zeigt ihren Hinweis ``kein_treffer`` und wartet
    weiter (``wahl_zug.getippt``; ``wahl_gilt`` lehnt den Text ab, die Simulation wartet)."""
    getippt = wendung(text or "")
    if not getippt or not schritt.synonyme_im_satz:
        return False
    if any(wendung(label) == getippt
           for o in schritt.optionen or [] for label in _labels(o, sprache)):
        return False
    return len(_satz_treffer(schritt, getippt, sprache)) > 1


#: Zweites Review TG-4–6, A/D: ein Treffer hinter einer Verneinung zählt nicht („Ich habe keinen
#: Lehrplan“). Nachprüfung, MINOR 2: nur im selben Satzteil (bis zu ``_SATZTEIL``) — in den zwei
#: Wörtern davor oder im Wort direkt dahinter („Lehrplan nicht, Ordner“); „nicht nur“ bejaht.
_VERNEINT: Final = frozenset({"kein", "keine", "keinen", "keinem", "keiner", "keines", "nicht",
                              "ohne", "no", "not", "without"})
_NUR: Final = frozenset({"nur", "bloß", "bloss", "only", "just"})
_SATZTEIL: Final = re.compile(r"[,;.!?]")


def _ganz(text: str) -> str:
    """Nachprüfung TG-4–6, NIT 8: die Wörter eines Texts ohne Satzzeichen — „nein, danke!“ und
    „Nein danke“ sind gleich."""
    return " ".join(re.findall(r"\w+", wendung(text)))


def _mit_freitext(schritt: Schritt, getippt: str, sprache: str | None) -> str | None:
    """Plan 2026-11-16, Review TG-4–6 (MAJOR 3) und zweites Review (A): an einem Schritt, der auch
    Freitext annimmt, ist ein Satz eine freie Antwort — „Keine Atomphysik“ ist ein Hinweis, nicht
    die Option „Nein, weiter“, „Passt nicht, bitte verfeinern“ nicht „So lassen“. Darum trifft dort
    ein Synonym nur, wenn der **ganze** Text gleich dem Synonym ist (die Wörter ohne Satzzeichen,
    :func:`_ganz`).

    Ausnahme ``synonyme_im_satz`` (die Frage ordnet einen Satz einer Option zu, etwa die Grundlage
    „aus meinem Lehrplan“): ein Synonym trifft als ganzes Wort im Satz, nicht verneint
    (:func:`_im_satz`). Trifft der Satz mehrere Optionen, ist er keine Wahl (:func:`mehrdeutig`)."""
    if not schritt.synonyme_im_satz:
        kern = _ganz(getippt)
        for o in schritt.optionen or []:
            if any(_ganz(w) == kern for w in (*_labels(o, sprache), *(o.synonyme or ())) if w):
                return o.id
        return None
    getroffen = _satz_treffer(schritt, getippt, sprache)
    return getroffen[0] if len(getroffen) == 1 else None


def _satz_treffer(schritt: Schritt, getippt: str, sprache: str | None) -> list[str]:
    """Die Optionen, deren Beschriftung oder Synonym im Satz steht (``synonyme_im_satz``)."""
    return [o.id for o in schritt.optionen or []
            if o.synonyme and any(len(k) >= _TEILWORT_MIN and _im_satz(k, getippt)
                                  for k in (wendung(w)
                                            for w in (*_labels(o, sprache), *o.synonyme)))]


def _im_satz(k: str, getippt: str) -> bool:
    """``k`` als ganzes Wort (bzw. Wortfolge) in ``getippt``, nicht verneint: im selben Satzteil
    weder in den zwei Wörtern davor (außer „nicht nur“) noch im Wort direkt dahinter."""
    for treffer in re.finditer(rf"(?<!\w){re.escape(k)}(?!\w)", getippt):
        anfang = max((m.end() for m in _SATZTEIL.finditer(getippt, 0, treffer.start())),
                     default=0)
        schluss = _SATZTEIL.search(getippt, treffer.end())
        davor = re.findall(r"\w+", getippt[anfang:treffer.start()])[-2:]
        danach = re.findall(r"\w+", getippt[treffer.end():schluss.start() if schluss
                                            else len(getippt)])[:1]
        verneint = any(w in _VERNEINT and (davor[n + 1:n + 2] or [""])[0] not in _NUR
                       for n, w in enumerate(davor))
        if not (verneint or _VERNEINT & set(danach)):
            return True
    return False


def wahl_gilt(ablauf: AblaufArea, lauf: dict[str, Any], wahl: str | None,
              text: str | None) -> bool:
    """Wartet der Lauf hier auf eine Wahl, und bietet der Schritt diese an (bzw. nimmt er Text)?
    Rein — der Zug unterscheidet so „passt nicht“ von einem Fehler beim Rechnen."""
    if lauf.get("status") != WARTET_WAHL or lauf.get("fassung") != fassung(ablauf):
        return False
    s = next((x for x in ablauf.schritte if x.id == lauf.get("schritt")), None)
    if s is None or not mit_wahl(s):
        return False
    if wahl is not None:
        return any(o.id == wahl for o in s.optionen or [])
    # Nachprüfung TG-4–6, MINOR 3: ein mehrdeutiger Satz ist kein Freitext
    return (s.freitext is not None and bool((text or "").strip())
            and not mehrdeutig(s, text))


async def weiter_wahl(ablauf: AblaufArea, lauf: dict[str, Any], wahl: str | None,
                      text: str | None, umgebung: Umgebung) -> Ausgabe | None:
    """AS-3a: mit der Wahl (Kennung einer Schnellantwort) oder dem getippten Freitext fortsetzen.

    ``None``, wenn der Lauf hier nicht auf eine Wahl wartet (anderer Status, geänderte Fassung,
    Schritt weg) oder der Schritt sie nicht anbietet — der Aufrufer entscheidet dann (Hinweis,
    Abweichung). Freitext wird der Teil ``freitext.schreibt`` (Text, gekürzt) und gilt schon für die
    Schritte dieses Zugs."""
    if not wahl_gilt(ablauf, lauf, wahl, text):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    s = ablauf.schritte[index[str(lauf.get("schritt"))]]
    neu = {**lauf, "status": "laeuft"}
    neue_teile: list[Teil] = []
    option = next((o for o in s.optionen or [] if o.id == wahl), None)
    # TB-T1: nur an einer ``nachricht`` schreibt die Wahl ihr Label (Review TB-T1, Befund 5)
    wahl_teil = s.schreibt if s.typ == "nachricht" else None
    verworfen: list[str] = []
    if option is not None:
        ziel, neu["gewaehlt"] = option.ziel, [option.id]
        if option.verwirft:
            # Zweites Review TG-2, MAJOR 1: die verworfenen Teile gibt es ab hier nicht mehr — auch
            # nicht für die Schritte dieses Zugs (``wenn_teil`` sähe sonst das abgelehnte Dokument)
            # Review TG-3a–c, R3-5: mit den Alias-Partnern (``structure`` ↔ ``struktur``,
            # ``document`` ↔ ``strukturdokument``)
            verworfen = typen.mit_aliassen(option.verwirft)
            lader_vorher = umgebung.teile

            async def ohne_verworfene(teil: str) -> Any:
                return None if teil in verworfen else await lader_vorher(teil)

            umgebung = replace(umgebung, teile=ohne_verworfene)
        if (s.freitext is not None and s.freitext.schreibt != wahl_teil
                and await umgebung.teile(s.freitext.schreibt) not in (None, "")):
            # Querschnitts-Review AS-3, Befund 3: ein Freitext aus einem früheren Durchgang gilt
            # nach einer Wahl nicht mehr — der Teil wird leer (``vorhanden`` greift nicht, ein
            # Platzhalter zeigt „—“); gab es keinen, entsteht auch kein leerer
            name = s.freitext.schreibt
            neue_teile.append((name, typen.TEXT, "", "—"))
            lader_wahl = umgebung.teile

            async def ohne_freitext(teil: str) -> Any:
                return "" if teil == name else await lader_wahl(teil)

            umgebung = replace(umgebung, teile=ohne_freitext)
        if wahl_teil:
            # TB-T1: das Label (Text der Redaktion, nie Eingabe der Person) wird ein Teil — mit dem
            # Namen des Freitexts ergibt Wahl oder Tippen denselben Teil. Immer das deutsche Label
            # (Review TB-T1, Befund 2): sprachfest für ``wenn_wert`` und die Simulation
            label, name_wahl = wahl_wert(option), wahl_teil
            neue_teile.append((name_wahl, typen.TEXT, label, f"Wahl: {label}"[:80]))
            lader_label = umgebung.teile

            async def mit_label(teil: str) -> Any:
                return label if teil == name_wahl else await lader_label(teil)

            umgebung = replace(umgebung, teile=mit_label)
    elif s.freitext is not None and text is not None:   # ``wahl_gilt`` hat es geprüft
        wert = text.strip()[:FREITEXT_ZEICHEN]
        ziel, name = s.freitext.ziel, s.freitext.schreibt
        # Review AS-3a, Befund 6: eine frühere Wahl gilt nach dem Freitext nicht mehr
        neu["gewaehlt"] = []
        # nur „Text“ und der Name des Teils in der Kennzeile — der Inhalt (Eingabe der Person)
        # bleibt im Teil (Befund 11); der Name kommt von der Redaktion und sagt der Person in
        # „Gesammelte Daten“, was gesammelt ist (Browser-Abnahme AS-U, L-1). Bewusste Ausnahme
        # seit 13.11.: am ``agent``-Schritt desselben Laufs liest ``ki_schritt.daten_zeile`` den
        # Wert aus dem Vorgang — der Verlauf (10 Nachrichten) trug ihn nicht verlässlich.
        neue_teile.append((name, typen.TEXT, wert, f"Text: {name}"))
        lader = umgebung.teile
        # Review TB-T1, Befund 3: eine Wahl aus einem früheren Durchgang (anderer Teil) gilt nach
        # dem Freitext nicht mehr — wie umgekehrt der Freitext nach einer Wahl
        alt_wahl = (wahl_teil if wahl_teil and wahl_teil != name
                    and await lader(wahl_teil) not in (None, "") else None)
        if alt_wahl:
            neue_teile.append((alt_wahl, typen.TEXT, "", "—"))

        async def mit_freitext(teil: str) -> Any:
            if teil == alt_wahl:
                return ""
            return wert if teil == name else await lader(teil)

        umgebung = replace(umgebung, teile=mit_freitext)
    else:
        return None
    # Review 13.11.: der Lauf merkt sich, welche Teile in IHM beantwortet wurden (nur Namen) —
    # ``ki_schritt.daten_zeile`` zeigt der KI nur diese; ein Neustart im selben Vorgang trüge
    # sonst die Antworten des vorigen Laufs weiter.
    if beantwortet := [n for n, _typ, wert_neu, _kurz in neue_teile if wert_neu != ""]:
        neu["antworten"] = list(dict.fromkeys([*(lauf.get("antworten") or []), *beantwortet]))
    if ziel not in index:
        neu["status"] = "fertig"
        return Ausgabe(lauf=neu, neue_teile=neue_teile, verworfen=verworfen)
    aus = await _rechne(ablauf, neu, index[ziel], umgebung)
    aus.neue_teile[:0] = neue_teile
    aus.verworfen = verworfen
    return aus


def gilt(ablauf: AblaufArea | None, lauf: dict[str, Any]) -> TypeGuard[AblaufArea]:
    """Kann der Lauf mit diesem Ablauf weiter? Den Ablauf gibt es, er ist eingeschaltet (oder der
    Lauf ist eine Probe der Studio-Vorschau, AS-8a P-6), und seine Schritte sind unverändert."""
    return (ablauf is not None and (ablauf.aktiv or lauf.get("probe") is True)
            and lauf.get("fassung") == fassung(ablauf))


def kann_weiter(ablauf: AblaufArea, lauf: dict[str, Any]) -> bool:
    """Wartet der Lauf, auf unveränderte Schritte, an einem Schritt, den es noch gibt?"""
    return (lauf.get("status") == WARTET and lauf.get("fassung") == fassung(ablauf)
            and any(s.id == lauf.get("schritt") for s in ablauf.schritte))


def gewaehlt_aus(antwort: dict[str, Any] | None) -> list[str]:
    roh = (antwort or {}).get("gewaehlt")
    return [g for g in roh if isinstance(g, str)][:20] if isinstance(roh, list) else []


async def weiter(ablauf: AblaufArea, lauf: dict[str, Any], antwort: dict[str, Any] | None,
                 umgebung: Umgebung) -> Ausgabe | None:
    """Mit der Antwort auf den offenen Block fortsetzen — ``None``, wenn :func:`kann_weiter` nein
    sagt."""
    if not kann_weiter(ablauf, lauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index[str(lauf.get("schritt"))]
    neu = {**lauf, "status": "laeuft", "gewaehlt": gewaehlt_aus(antwort)}
    ziel = (nachfolger(ablauf, i) or [""])[0]
    if ziel not in index:
        neu["status"] = "fertig"
        return Ausgabe(lauf=neu)
    return await _rechne(ablauf, neu, index[ziel], umgebung)


async def weiter_ki(ablauf: AblaufArea, lauf: dict[str, Any], umgebung: Umgebung
                    ) -> Ausgabe | None:
    """Paket A2b: „Weiter“ am wartenden ``agent``-Schritt — ``None``, wenn der Lauf dort nicht
    wartet oder sich die Schritte geändert haben. Fehlt der Teil ``ausgabe``: ``bei_fehler``, sonst
    weiter warten (:attr:`Ausgabe.fehlt_teil`)."""
    if lauf.get("status") != WARTET_KI or lauf.get("fassung") != fassung(ablauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index.get(str(lauf.get("schritt")))
    if i is None or ablauf.schritte[i].typ != "agent":
        return None
    s = ablauf.schritte[i]
    neu = {**lauf, "status": "laeuft"}
    ausgabe = s.agent.ausgabe if s.agent else None
    if ausgabe and await umgebung.teile(ausgabe) is None:
        if not s.bei_fehler:
            return Ausgabe(lauf=dict(lauf), fehlt_teil=ausgabe)
        ziel = s.bei_fehler
    else:
        ziel = (nachfolger(ablauf, i) or [""])[0]
    if ziel not in index:
        neu["status"] = "fertig"
        return Ausgabe(lauf=neu)
    return await _rechne(ablauf, neu, index[ziel], umgebung)


async def _auftrag_stuecke(s: Schritt, teile: Any, sprache: str
                           ) -> tuple[dict[str, Any], list[dict[str, Any]], bool, int]:
    """Die eingesetzten Argumente, die Argumente je (Teil-)Auftrag, ob etwas fehlt (Paket R1:
    Sprache der Person, ``aufteilen``) und wie viele Knoten der Metadaten-Flow nicht bekommt
    (Durchtest Paket K, ``auftrag_teile.ohne_textdateien``) — bleibt keiner, fehlt etwas."""
    args, fehlt = await teil_verweise.einsetzen(dict(s.argumente or {}), teile)
    args = auftrag_teile.sprache_einsetzen(args, sprache)
    ohne = 0
    if s.flow == METADATEN_FLOW:
        args, ohne = auftrag_teile.ohne_textdateien(s.flow, args,
                                                    await teile(auftrag_teile.ABLAGE_TEIL))
    fehlt_etwas = bool(fehlt) or _leere_auswahl(s.argumente, args)
    if s.aufteilen is None:
        return args, [args], fehlt_etwas, ohne
    return (args, auftrag_teile.teilen(args, s.aufteilen.argument, s.aufteilen.hoechstens),
            fehlt_etwas, ohne)


def _rueckfrage(ablauf: AblaufArea, schritt_id: str) -> str | None:
    """Die Frage, deren Wahl direkt zu ``schritt_id`` führt (die Rückfrage vor einem schreibenden
    Flow, Prüfung ``auftrag_rueckfrage``) — ``None`` ohne."""
    return next((v.id for v in ablauf.schritte if mit_wahl(v)
                 and any(o.ziel == schritt_id for o in v.optionen or [])), None)


async def _gestartet(aus: Ausgabe, ablauf: AblaufArea, s: Schritt, job: str,
                     stapel: dict[str, Any] | None, satz: str | None, teile: Any,
                     sprache: str) -> None:
    """Der Auftrag läuft: Text, Fortschritt, ``wartet_auftrag`` und der Stapel — beim Start und
    nach der Freigabe (Paket N4) gleich."""
    lauf = aus.lauf
    # Der Text erst nach dem Start — ein abgewiesener Auftrag kündigt nichts an.
    if text := _text(s, sprache):
        text = await _einsetzen(aus, text, teile, lauf, ablauf, sprache)
        aus.texte.append(text)
    if stapel is not None:
        # Review R1, NIT 8: dass es mehrere Teile werden, steht gleich am Anfang
        aus.texte.append(_teil_text(sprache, "action.ablauf.auftragTeile", n=stapel["n"]))
    if satz:
        aus.texte.append(satz)
    aus.auftrag = {"flow": s.flow or "", "job_id": job, "schritt": s.id}
    if (block := _fortschritt(ablauf.id, job, text, sprache)) is not None:
        aus.bloecke.append(block)
    lauf["status"] = WARTET_AUFTRAG
    # Paket R1: mehrere Teile — der Stapel zählt, „Stand prüfen“ startet den nächsten
    lauf.pop(auftrag_teile.STAPEL, None)
    if stapel is not None:
        lauf[auftrag_teile.STAPEL] = stapel


async def weiter_nach_freigabe(ablauf: AblaufArea, lauf: dict[str, Any], umgebung: Umgebung,
                               job: str | None, satz: str | None = None, *,
                               zurueck: bool = False) -> Ausgabe | None:
    """Paket N4: die Freigabe des wartenden Auftragsschritts ist entschieden — ``job`` gestartet
    (wie ein Start, mit den freigegebenen Argumenten als Stapel) oder ``None`` (abgebrochen bzw.
    nicht gestartet: ``satz``, dann ``bei_fehler``). ``zurueck`` (vorübergehend, etwa 429 ohne
    offenen Ausgang): wie beim Start zurück an die Rückfrage davor, wenn es eine gibt. ``None``,
    wenn der Lauf dort nicht wartet."""
    i = _am_freigabe_schritt(ablauf, lauf)
    if i is None or ablauf.schritte[i].typ != "auftrag":
        return None
    s = ablauf.schritte[i]
    args = lauf.get("freigabe_args") if isinstance(lauf.get("freigabe_args"), dict) else {}
    neu = {**lauf, "status": "laeuft", "freigabe_id": None}
    neu.pop("freigabe_args", None)
    if job is None:
        frage = _rueckfrage(ablauf, s.id) if zurueck else None
        if not s.bei_fehler and frage is None:
            neu["status"] = "fehler"
            return Ausgabe(lauf=neu, texte=[satz] if satz else [], fehler=s.id)
        index = {x.id: n for n, x in enumerate(ablauf.schritte)}
        aus = await _rechne(ablauf, neu, index[frage or s.bei_fehler or ""], umgebung)
        if satz:
            aus.texte.insert(0, satz)
        return aus
    stuecke = (auftrag_teile.teilen(args, s.aufteilen.argument, s.aufteilen.hoechstens)
               if s.aufteilen is not None else [args])
    stapel = auftrag_teile.neuer_stapel(args, len(stuecke)) if len(stuecke) > 1 else None
    aus = Ausgabe(lauf=neu)
    await _gestartet(aus, ablauf, s, job, stapel, satz, _Teile(umgebung.teile), umgebung.sprache)
    return aus


def _starter_fuer(starte: Any, s: Schritt) -> Any:
    """Review A4/A7: der Starter für diesen Schritt — der Träger hängt an ``repo_schreibt``
    (``auftrag_zug._Wahl.fuer``). Eine Naht ohne Wahl (Trockenlauf, Simulation) gilt so."""
    waehle = getattr(starte, "fuer", None)
    return waehle(s.repo_schreibt) if callable(waehle) else starte


def _teil_text(sprache: str, schluessel: str, **werte: Any) -> str:
    from boerdi.i18n import bot_text  # nur für Teilaufträge gebraucht

    return bot_text(sprache, schluessel, **werte)


async def _naechster_teil(ablauf: AblaufArea, s: Schritt, lauf: dict[str, Any],
                          stapel: dict[str, Any], umgebung: Umgebung, *,
                          gescheitert: bool) -> Ausgabe | None:
    """Paket R1: den nächsten Teilauftrag starten — aus den beim ersten Teil eingefrorenen
    Argumenten (Review R1, Befund 1). ``None``, wenn keiner mehr kommt oder der Start scheitert
    (dann zählen die übrigen als gescheitert, ``stapel["offen"]``)."""
    naechster = stapel["i"] + 1
    if naechster >= stapel["n"] or s.aufteilen is None:
        return None
    args = auftrag_teile.stueck(stapel, s.aufteilen.argument, s.aufteilen.hoechstens, naechster)
    starte = _starter_fuer(umgebung.auftrag_starten, s)
    if getattr(starte, "nur_ueber_wlo", False):
        starte = None                       # Paket K2: wie beim ersten Teil
    job = (None if args is None or starte is None else await starte(s.flow or "", args))
    if job is None:
        stapel["offen"] = stapel["n"] - naechster
        return None
    text = _teil_text(umgebung.sprache, "action.ablauf.auftragTeilGescheitert" if gescheitert
                      else "action.ablauf.auftragTeil", fertig=naechster, n=stapel["n"],
                      naechster=naechster + 1)
    neu = {**lauf, "status": WARTET_AUFTRAG, auftrag_teile.STAPEL: {**stapel, "i": naechster}}
    aus = Ausgabe(lauf=neu, texte=[text],
                  auftrag={"flow": s.flow or "", "job_id": job, "schritt": s.id})
    # Zweites Review K (Z2): wie beim ersten Teil — ein Start mit offenem Ausgang sagt es
    hinweis = getattr(starte, "hinweis", None)
    if callable(hinweis) and (satz := hinweis(umgebung.sprache)):
        aus.texte.append(satz)
    if (block := _fortschritt(ablauf.id, job, text, umgebung.sprache)) is not None:
        aus.bloecke.append(block)
    return aus


async def weiter_auftrag(ablauf: AblaufArea, lauf: dict[str, Any], ergebnis: dict[str, Any] | None,
                         umgebung: Umgebung, *, fehlschlag: str | None = None) -> Ausgabe | None:
    """Paket K1a: der Auftrag des wartenden ``auftrag``-Schritts ist fertig (``ergebnis``) oder
    gescheitert (``None``) — ``None``, wenn der Lauf dort nicht wartet oder sich die Schritte
    geändert haben. Das Ergebnis wird Teil ``schreibt`` (auch für die folgenden Schritte).
    ``fehlschlag`` (Durchtest Paket K, 19.11.): der Satz zu einem gescheiterten Flow — er steht vor
    dem Ersatzweg ``bei_fehler``, nur wenn der Lauf ihn wirklich nimmt."""
    if lauf.get("status") != WARTET_AUFTRAG or lauf.get("fassung") != fassung(ablauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index.get(str(lauf.get("schritt")))
    if i is None or ablauf.schritte[i].typ != "auftrag":
        return None
    s = ablauf.schritte[i]
    if auftrag_teile.ist_stapel(stapel := lauf.get(auftrag_teile.STAPEL)):
        stapel = auftrag_teile.mit_ergebnis(stapel, ergebnis)
        if (weiter := await _naechster_teil(ablauf, s, lauf, stapel, umgebung,
                                            gescheitert=ergebnis is None)) is not None:
            return weiter
        ergebnis = auftrag_teile.zusammenfuehren(
            stapel, nicht_gestartet=int(stapel.get("offen") or 0))
    neu = {**lauf, "status": "laeuft"}
    neu.pop(auftrag_teile.STAPEL, None)
    teil: Teil | None = None
    if ergebnis is None:
        if not s.bei_fehler:
            neu["status"] = "fehler"
            return Ausgabe(lauf=neu, fehler=s.id)
        ziel = s.bei_fehler
    else:
        ziel = (nachfolger(ablauf, i) or [""])[0]
        teil = (s.schreibt or "", typen.AUFTRAG, ergebnis, f"Ergebnis von {s.flow}"[:80])
        lader = umgebung.teile

        async def mit_ergebnis(name: str) -> Any:
            return ergebnis if name == s.schreibt else await lader(name)

        umgebung = replace(umgebung, teile=mit_ergebnis)
    if ziel not in index:
        neu["status"] = "fertig"
        aus = Ausgabe(lauf=neu)
    else:
        aus = await _rechne(ablauf, neu, index[ziel], umgebung)
    if teil is not None:
        aus.neue_teile.insert(0, teil)
    elif fehlschlag:
        aus.texte.insert(0, fehlschlag)
    return aus


def _am_freigabe_schritt(ablauf: AblaufArea, lauf: dict[str, Any]) -> int | None:
    """Die Stelle des Schritts, an dem der Lauf auf eine Freigabe wartet — ``None``, wenn er dort
    nicht wartet oder sich die Schritte geändert haben."""
    if lauf.get("status") != WARTET_FREIGABE or lauf.get("fassung") != fassung(ablauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index.get(str(lauf.get("schritt")))
    if i is None:
        return None
    s = ablauf.schritte[i]
    # Paket N4: auch ein Auftrag mit ``repo_schreibt`` wartet an seiner Freigabe-Box
    if not schreibt_mit_freigabe(s) and not (s.typ == "auftrag" and s.repo_schreibt):
        return None
    return i


async def erneut_vorlegen(ablauf: AblaufArea, lauf: dict[str, Any], umgebung: Umgebung
                          ) -> Ausgabe | None:
    """Paket S (FS-6): die Vorschau des wartenden Freigabe-Schritts neu holen — mit den Teilen von
    jetzt (eine Änderung seitdem gilt). ``None``, wenn der Lauf dort nicht wartet."""
    i = _am_freigabe_schritt(ablauf, lauf)
    if i is None:
        return None
    return await _rechne(ablauf, {**lauf, "status": "laeuft"}, i, umgebung)


async def weiter_freigabe(ablauf: AblaufArea, lauf: dict[str, Any], ergebnis: dict[str, Any] | None,
                          umgebung: Umgebung) -> Ausgabe | None:
    """Paket S: die Freigabe ist eingelöst (``ergebnis``, der strukturierte Teil der Antwort) oder
    vom Server abgelehnt (``None``: ``bei_fehler``, sonst Ende mit Fehler, FS-8). ``None``, wenn der
    Lauf dort nicht wartet. Das Ergebnis wird Teil ``schreibt``."""
    i = _am_freigabe_schritt(ablauf, lauf)
    if i is None or ablauf.schritte[i].typ == "auftrag":     # N4: :func:`weiter_nach_freigabe`
        return None
    s = ablauf.schritte[i]
    index = {x.id: n for n, x in enumerate(ablauf.schritte)}
    neu = {**lauf, "status": "laeuft", "freigabe_id": None, "plan_angelaufen": None}
    teil: Teil | None = None
    if ergebnis is None:
        if not s.bei_fehler:
            neu["status"] = "fehler"
            return Ausgabe(lauf=neu, fehler=s.id)
        ziel = s.bei_fehler
    else:
        ziel = (nachfolger(ablauf, i) or [""])[0]
        if s.schreibt:
            # eine Quelle für den Typ (Review AS-Dd, Befund 9)
            teil = (s.schreibt, typen.dienst_typ(s.werkzeug or ""), ergebnis,
                    f"Ergebnis von {s.werkzeug}"[:80])
            lader = umgebung.teile

            async def mit_ergebnis(name: str) -> Any:
                return ergebnis if name == s.schreibt else await lader(name)

            umgebung = replace(umgebung, teile=mit_ergebnis)
    if ziel not in index:
        neu["status"] = "fertig"
        aus = Ausgabe(lauf=neu)
    else:
        aus = await _rechne(ablauf, neu, index[ziel], umgebung)
    if teil is not None:
        aus.neue_teile.insert(0, teil)
    return aus
