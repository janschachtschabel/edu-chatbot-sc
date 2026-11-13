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
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any, Final, TypeGuard

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain import seiten_muster
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
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
        return await werkzeuge.DIENSTE[name](args)
    if name in werkzeuge.LESENDE_MCP and umgebung.mcp is not None:
        return await umgebung.mcp(name, args)
    return None


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
                     lauf: dict[str, Any]) -> str:
    """Platzhalter einsetzen und merken, ob dabei Inhalt einer KI in den Text kommen kann."""
    arten = platzhalter.herkuenfte(text)
    if "teil" in arten or ("start" in arten
                           and lauf.get("start_quelle") != startdaten.QUELLE_GASTSEITE):
        aus.ki_inhalt = True
    return await platzhalter.einsetzen(text, teile)


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


async def _rechne(ablauf: AblaufArea, lauf: dict[str, Any], start: int,
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
                aus.texte.append(await _einsetzen(aus, text, teile, lauf))
        if s.typ == "ende":
            lauf["status"] = "fertig"
            return aus
        if s.typ == "agent":
            lauf["status"] = WARTET_KI
            return aus
        if s.typ == "modul":
            daten, fehlt = await _daten(s.daten, teile)
            block = None if fehlt else await _modul_block(s.modul or "", daten,
                                                          simulation=umgebung.simulation)
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
                    aus.texte.append(await _einsetzen(aus, text, teile, lauf))
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
                aus.neue_teile.append((s.schreibt, typ, wert, _zusammenfassung(wert)))
        elif s.typ == "auftrag":
            args, stuecke, fehlt = await _auftrag_stuecke(s, teile, umgebung.sprache)
            stapel = None
            if len(stuecke) > 1 and (
                    stapel := auftrag_teile.neuer_stapel(args, len(stuecke))) is None:
                logger.warning("Auftrag: Argumente zu groß zum Aufteilen — Schritt scheitert")
                fehlt = True
            job = (None if fehlt or umgebung.auftrag_starten is None
                   else await umgebung.auftrag_starten(s.flow or "", stuecke[0]))
            if job is None:
                fehler = True
            else:
                # Der Text erst nach dem Start — ein abgewiesener Auftrag kündigt nichts an.
                if text := _text(s, umgebung.sprache):
                    text = await _einsetzen(aus, text, teile, lauf)
                    aus.texte.append(text)
                if stapel is not None:
                    # Review R1, NIT 8: dass es mehrere Teile werden, steht gleich am Anfang
                    aus.texte.append(_teil_text(umgebung.sprache, "action.ablauf.auftragTeile",
                                                n=stapel["n"]))
                aus.auftrag = {"flow": s.flow or "", "job_id": job, "schritt": s.id}
                if (block := _fortschritt(ablauf.id, job, text, umgebung.sprache)) is not None:
                    aus.bloecke.append(block)
                lauf["status"] = WARTET_AUFTRAG
                # Paket R1: mehrere Teile — der Stapel zählt, „Stand prüfen“ startet den nächsten
                lauf.pop(auftrag_teile.STAPEL, None)
                if stapel is not None:
                    lauf[auftrag_teile.STAPEL] = stapel
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
            "start": secrets.token_hex(4)}
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


def wahl_aus_text(schritt: Schritt, text: str | None) -> str | None:
    """Die Kennung der Schnellantwort, deren Label (in einer Sprache) der getippte Text ist — wie
    eine Wendung verglichen (klein, Leerraum zusammengezogen). D2: Text, der einer Option
    entspricht, ist diese Wahl. Hier und nicht im Zug, damit die Simulation dasselbe tut
    (Querschnitts-Review AS-3, Befund 2)."""
    getippt = wendung(text or "")
    if not getippt:
        return None
    return next((o.id for o in schritt.optionen or []
                 if any(wendung(label) == getippt for label in o.label.values())), None)


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
    return s.freitext is not None and bool((text or "").strip())


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
    if option is not None:
        ziel, neu["gewaehlt"] = option.ziel, [option.id]
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
        # „Gesammelte Daten“, was gesammelt ist (Browser-Abnahme AS-U, L-1)
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
    if ziel not in index:
        neu["status"] = "fertig"
        return Ausgabe(lauf=neu, neue_teile=neue_teile)
    aus = await _rechne(ablauf, neu, index[ziel], umgebung)
    aus.neue_teile[:0] = neue_teile
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
                           ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Die eingesetzten Argumente, die Argumente je (Teil-)Auftrag und ob etwas fehlt (Paket R1:
    Sprache der Person, ``aufteilen``)."""
    args, fehlt = await teil_verweise.einsetzen(dict(s.argumente or {}), teile)
    args = auftrag_teile.sprache_einsetzen(args, sprache)
    fehlt_etwas = bool(fehlt) or _leere_auswahl(s.argumente, args)
    if s.aufteilen is None:
        return args, [args], fehlt_etwas
    return (args, auftrag_teile.teilen(args, s.aufteilen.argument, s.aufteilen.hoechstens),
            fehlt_etwas)


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
    job = (None if args is None or umgebung.auftrag_starten is None
           else await umgebung.auftrag_starten(s.flow or "", args))
    if job is None:
        stapel["offen"] = stapel["n"] - naechster
        return None
    text = _teil_text(umgebung.sprache, "action.ablauf.auftragTeilGescheitert" if gescheitert
                      else "action.ablauf.auftragTeil", fertig=naechster, n=stapel["n"],
                      naechster=naechster + 1)
    neu = {**lauf, "status": WARTET_AUFTRAG, auftrag_teile.STAPEL: {**stapel, "i": naechster}}
    aus = Ausgabe(lauf=neu, texte=[text],
                  auftrag={"flow": s.flow or "", "job_id": job, "schritt": s.id})
    if (block := _fortschritt(ablauf.id, job, text, umgebung.sprache)) is not None:
        aus.bloecke.append(block)
    return aus


async def weiter_auftrag(ablauf: AblaufArea, lauf: dict[str, Any], ergebnis: dict[str, Any] | None,
                         umgebung: Umgebung) -> Ausgabe | None:
    """Paket K1a: der Auftrag des wartenden ``auftrag``-Schritts ist fertig (``ergebnis``) oder
    gescheitert (``None``) — ``None``, wenn der Lauf dort nicht wartet oder sich die Schritte
    geändert haben. Das Ergebnis wird Teil ``schreibt`` (auch für die folgenden Schritte)."""
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
    return aus


def _am_freigabe_schritt(ablauf: AblaufArea, lauf: dict[str, Any]) -> int | None:
    """Die Stelle des Schritts, an dem der Lauf auf eine Freigabe wartet — ``None``, wenn er dort
    nicht wartet oder sich die Schritte geändert haben."""
    if lauf.get("status") != WARTET_FREIGABE or lauf.get("fassung") != fassung(ablauf):
        return None
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    i = index.get(str(lauf.get("schritt")))
    if i is None or not schreibt_mit_freigabe(ablauf.schritte[i]):
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
    if i is None:
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
