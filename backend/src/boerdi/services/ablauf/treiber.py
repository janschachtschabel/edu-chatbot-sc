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
(``teil_verweise.darf``); über seinen Dienst baut der Treiber nur Module ohne Sprachmodell.

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
from typing import Any, Final

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.domain.write_confirm import SCHLUESSEL_FELDER
from boerdi.services import teil_verweise
from boerdi.services.ablauf import werkzeuge
from boerdi.services.ablauf.pruefung import RECHENSCHRITTE, nachfolger, schreibt_mit_freigabe
from boerdi.services.ablauf.treiber_bloecke import fortschritt as _fortschritt
from boerdi.services.ablauf.treiber_bloecke import modul_block as _modul_block

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

Teil = tuple[str, str, Any, str]


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
        wert = teil_verweise.stelle(gefunden, pfad) if gefunden is not None else None
        return ((copy.deepcopy(wert), []) if isinstance(wert, dict)
                else ({}, [teil_verweise.bezeichnung(name, pfad)]))
    return await teil_verweise.einsetzen(dict(roh or {}), teile)


async def _werkzeug(s: Schritt, args: dict[str, Any], umgebung: Umgebung) -> Any:
    name = s.werkzeug or ""
    if name in umgebung.gesperrt or werkzeuge.DIENST_MCP.get(name, frozenset()) & umgebung.gesperrt:
        logger.info("Ablauf: Werkzeug %s von der Sicherheitsprüfung gesperrt", name)
        return None
    if name in werkzeuge.DIENSTE:
        return await werkzeuge.DIENSTE[name](args)
    if name in werkzeuge.LESENDE_MCP and umgebung.mcp is not None:
        return await umgebung.mcp(name, args)
    return None


def _zusammenfassung(wert: Any) -> str:
    if isinstance(wert, dict) and isinstance(wert.get("titel"), str):
        return wert["titel"][:80]
    return type(wert).__name__


async def _waehle(s: Schritt, teile: _Teile, gewaehlt: list[str]) -> str | None:
    for regel in s.weiter if isinstance(s.weiter, list) else []:
        if regel.sonst:
            return regel.sonst
        if regel.wenn_teil and await teile(regel.wenn_teil) is not None:
            return regel.dann
        if regel.wenn_gewaehlt and regel.wenn_gewaehlt in gewaehlt:
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
        naechster = (nachfolger(ablauf, i) or [""])[0]
        fehler = False
        if s.typ in ("nachricht", "ende", "agent") or (s.typ == "modul" and s.text):
            if text := _text(s, umgebung.sprache):
                aus.texte.append(text)
        if s.typ == "ende":
            lauf["status"] = "fertig"
            return aus
        if s.typ == "agent":
            lauf["status"] = WARTET_KI
            return aus
        if s.typ == "modul":
            daten, fehlt = await _daten(s.daten, teile)
            block = None if fehlt else await _modul_block(s.modul or "", daten)
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
                    aus.neue_teile.append((s.schreibt, f"{name}@1", {"unveraendert": True},
                                           "unverändert"))
            else:
                if text := _freigabe_satz(s, umgebung.sprache):
                    aus.texte.append(text)
                # Review S2/S3, Befund 6: jede Vorlage hat eine Kennung — ein „ja“ zu einer alten
                # setzt keinen neu gestarteten Lauf fort
                kennung = secrets.token_hex(6)
                aus.freigabe = {"werkzeug": name, "args": args, "schluessel": vorlage.schluessel,
                                "vorschau": vorlage.text, "schritt": s.id, "id": kennung}
                lauf.update(status=WARTET_FREIGABE, freigabe_id=kennung)
                return aus
        elif s.typ == "werkzeug":
            # Dienste bekommen Teile (geprüfte Definition), lesende WLO-Werkzeuge nicht (``darf``).
            ziel = None if s.werkzeug in werkzeuge.DIENSTE else s.werkzeug
            args, fehlt = await teil_verweise.einsetzen(dict(s.argumente or {}), teile, ziel)
            wert = None if fehlt else await _werkzeug(s, args, umgebung)
            if wert is None:
                fehler = True
            elif s.schreibt:
                typ = "text" if isinstance(wert, str) else f"{s.werkzeug}@1"
                teile.neu[s.schreibt] = wert
                aus.neue_teile.append((s.schreibt, typ, wert, _zusammenfassung(wert)))
        elif s.typ == "auftrag":
            args, fehlt = await teil_verweise.einsetzen(dict(s.argumente or {}), teile)
            job = (None if fehlt or umgebung.auftrag_starten is None
                   else await umgebung.auftrag_starten(s.flow or "", args))
            if job is None:
                fehler = True
            else:
                # Der Text erst nach dem Start — ein abgewiesener Auftrag kündigt nichts an.
                if text := _text(s, umgebung.sprache):
                    aus.texte.append(text)
                aus.auftrag = {"flow": s.flow or "", "job_id": job, "schritt": s.id}
                if (block := _fortschritt(ablauf.id, job, text, umgebung.sprache)) is not None:
                    aus.bloecke.append(block)
                lauf["status"] = WARTET_AUFTRAG
                return aus
        elif s.typ == "verzweigung":
            naechster = await _waehle(s, teile, list(lauf.get("gewaehlt") or [])) or ""
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
                  gewaehlt: list[str] | None = None) -> Ausgabe:
    """Einen Lauf beginnen — ab Schritt ``ab`` (Modul-Auslöser: nach dem schon beantworteten
    Modul, mit dessen Wahl ``gewaehlt``)."""
    lauf = {"ablauf": ablauf.id, "fassung": fassung(ablauf), "schritt": ablauf.schritte[ab].id,
            "offener_block": None, "status": "laeuft", "gewaehlt": list(gewaehlt or [])}
    return await _rechne(ablauf, lauf, ab, umgebung)


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
    neu = {**lauf, "status": "laeuft"}
    teil: Teil | None = None
    if ergebnis is None:
        if not s.bei_fehler:
            neu["status"] = "fehler"
            return Ausgabe(lauf=neu, fehler=s.id)
        ziel = s.bei_fehler
    else:
        ziel = (nachfolger(ablauf, i) or [""])[0]
        teil = (s.schreibt or "", "wlo.auftrag@1", ergebnis, f"Ergebnis von {s.flow}"[:80])
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
            teil = (s.schreibt, f"{s.werkzeug}@1", ergebnis, f"Ergebnis von {s.werkzeug}"[:80])
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
