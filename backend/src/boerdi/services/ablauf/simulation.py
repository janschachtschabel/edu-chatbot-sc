"""Testfälle eines Ablaufs simulieren (Paket AS-1, Plan 2026-11-09 §5c).

Der echte Treiber (``treiber.starten`` und die ``weiter_*``) mit einer Attrappen-:class:`Umgebung`:
Teile aus dem Testfall, Werkzeug-Ergebnisse je Schritt (``ersatz``), Module ohne Dienst
(``simulation``), Aufträge mit einer Schein-Kennung und Freigaben mit einer Schein-Vorschau. Kein
LLM, kein MCP, kein Auftrag, keine Vorlage beim Server — wiederholbar und ohne Kosten. Antworten von
Modulen werden wie im Zug zu Teilen (``arbeitsstand_teile.teile_aus_antwort``); ein „nein“ zur
Freigabe lässt den Lauf warten (wie ``ablauf/freigabe_zug``).

Was abweicht, steht je Testfall als Text in :attr:`TestErgebnis.abweichungen` — anderer Weg,
Status oder Ende, fehlender Teil, eine Eingabe für einen anderen Schritt oder eine, die nicht zum
Wartepunkt passt, eine nicht verbrauchte Eingabe.

Wie im Betrieb (Review AS-1): lesende MCP-Werkzeuge liefern Text; ohne Anmeldung startet ein
Ablauf mit der Voraussetzung ``anmeldung`` nicht, Aufträge und Freigaben gehen zu ``bei_fehler``;
nach einem „nein“ legt „Vorschau erneut“ neu vor (eine folgende Eingabe „ja“ gilt der neuen
Vorlage); ein Testfall kann wie ein Modul-Auslöser nach einem Modul beginnen (``ab``,
``gewaehlt``). Ein Ablauf mit Befunden der Prüfung besteht keinen Testfall — er ließe sich so
nicht speichern. Je Ablauf gilt ein Zeitbudget (:data:`BUDGET_S`).

Querschnitts-Review AS-0…AS-2:
- Die Kette gibt die Ereignisschleife nie frei — ein ``asyncio.timeout`` griffe nicht. Die Frist
  prüft deshalb jeder besuchte Schritt selbst (``protokoll``) und jede Eingabe; dazu ein Deckel
  auf die besuchten Schritte je Testfall (:data:`MAX_SCHRITTE`). Der Endpunkt rechnet in einem
  eigenen Thread mit eigener Schleife (:func:`im_thread`), damit die Chat-Züge weiterlaufen.
- Eine Modul-Antwort prüft die Simulation wie der Betrieb gegen die offene Frage
  (``ui_module.antwort.antwort_pruefen``): eine Antwort, die der Betrieb verwürfe, ist eine
  Abweichung — sonst sagte ein grüner Test einen Weg voraus, den es nicht gibt.

Querschnitts-Review AS-D: reine Dienste (``werkzeuge.REINE_DIENSTE``, ohne Netz) rechnet die
Simulation selbst, ein Eintrag in ``werkzeuge`` des Testfalls überschreibt; das Ergebnis einer
Freigabe geht wie im Zug in den Lauf (``freigabe_ergebnis``); die Schein-Vorschau nennt die
eingesetzten Argumente.

Nicht abgebildet: „nichts zu ändern“ einer Freigabe-Vorschau (die Schein-Vorschau hat immer einen
Schlüssel) und Werkzeuge, die die Sicherheitsprüfung eines Zugs sperrt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any, Final

from boerdi.api.schemas_ui import UiAntwort
from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest, TestEingabe
from boerdi.services.ablauf import freigabe_ergebnis, pruefung, startdaten, treiber, werkzeuge
from boerdi.services.arbeitsstand_teile import teile_aus_antwort
from boerdi.ui_module.antwort import OFFENE_FRAGE, antwort_pruefen, merke_frage

logger = logging.getLogger(__name__)

#: Höchstens so lange je Ablauf (alle Testfälle).
BUDGET_S: Final = 5.0
#: Höchstens so viele besuchte Schritte je Testfall — ein Lauf, der kreist, endet hier.
MAX_SCHRITTE: Final = 500
#: So viele Texte (je so lang) gibt ein Testfall höchstens zurück.
MAX_TEXTE: Final = 40
TEXT_ZEICHEN: Final = 500
NICHT_GESTARTET: Final = "nicht_gestartet"

#: Die Statuswerte, an denen der Lauf auf eine Eingabe wartet.
_WARTEND: Final = treiber.WARTEND

_T: Final[dict[str, dict[str, str]]] = {
    "weg": {"de": "Weg: erwartet {soll}, war {ist}", "en": "Path: expected {soll}, got {ist}"},
    "status": {"de": "Status: erwartet {soll}, war {ist}",
               "en": "Status: expected {soll}, got {ist}"},
    "ende": {"de": "Ende: erwartet „{soll}“, war „{ist}“",
             "en": "End: expected “{soll}”, got “{ist}”"},
    "teil": {"de": "Teil fehlt am Ende: {name}", "en": "Part missing at the end: {name}"},
    "falsch": {"de": "Eingabe für „{bei}“, der Lauf wartet aber an „{ist}“",
               "en": "Input for “{bei}”, but the run waits at “{ist}”"},
    "uebrig": {"de": "Eingabe für „{bei}“ nicht verbraucht",
               "en": "Input for “{bei}” not used"},
    "passt": {"de": "Eingabe für „{bei}“ passt nicht zum Wartepunkt — erwartet: {was}",
              "en": "Input for “{bei}” does not fit the waiting point — expected: {was}"},
    "ab": {"de": "Start-Schritt „{ab}“ gibt es nicht", "en": "Start step “{ab}” does not exist"},
    "start": {"de": "Startdaten abgewiesen: {f}", "en": "Start data rejected: {f}"},
    "start_ohne_extern": {"de": "Startdaten gibt es nur beim Start von der Gastseite (Auslöser "
                                "extern) oder durch die KI (Auslöser agent, Herkunft ki) — ohne "
                                "„Beginnen ab“",
                          "en": "Start data only come with a start from the host page (trigger "
                                "extern) or from the AI (trigger agent, origin ki) — without "
                                "“start at”"},
    "befunde": {"de": "„Prüfen“ meldet {n} Befund(e) — so lässt sich der Ablauf nicht speichern: "
                      "{erster}",
                "en": "“Check” reports {n} finding(s) — the workflow cannot be saved like this: "
                      "{erster}"},
    "abbruch": {"de": "Die Simulation brach ab ({art})", "en": "The simulation stopped ({art})"},
    "budget": {"de": "Zeitbudget ({s:g} s) erschöpft — nicht ausgeführt",
               "en": "Time budget ({s:g} s) used up — not run"},
    "schritte": {"de": "Mehr als {n} Schritte — der Lauf kreist vermutlich",
                 "en": "More than {n} steps — the run probably loops"},
    "antwort": {"de": "Antwort für „{bei}“ passt nicht zur Frage — der Betrieb verwürfe sie",
                "en": "Answer for “{bei}” does not fit the question — production would drop it"},
    "wahl": {"de": "„{bei}“ bietet diese Wahl nicht an (bzw. keinen Freitext)",
             "en": "“{bei}” does not offer this choice (or no free text)"},
    "seite": {"de": "Die Seite für „{bei}“ passt nicht zur Ankunft — der Lauf wartet weiter",
              "en": "The page for “{bei}” does not match the arrival — the run keeps waiting"},
}


class _ZeitUm(Exception):
    """Die Frist des Ablaufs ist vorbei."""


class _ZuLang(Exception):
    """Der Testfall besuchte mehr als :data:`MAX_SCHRITTE` Schritte."""

#: Was am Wartepunkt einzugeben ist.
_ERWARTET: Final[dict[str, dict[str, str]]] = {
    treiber.WARTET: {"de": "eine Antwort", "en": "an answer"},
    treiber.WARTET_AUFTRAG: {"de": "ein Ergebnis oder „Gescheitert“",
                             "en": "a result or “Failed”"},
    treiber.WARTET_FREIGABE: {"de": "Freigabe ja oder nein", "en": "approval yes or no"},
    treiber.WARTET_WAHL: {"de": "eine Wahl oder Text", "en": "a choice or text"},
    treiber.WARTET_SEITE: {"de": "eine Seite", "en": "a page"},
}

#: Der Status in Worten — wie die Auswahl im Studio (``feld.TestErwartung.status.wahl.…``).
_STATUS: Final[dict[str, dict[str, str]]] = {
    "fertig": {"de": "fertig", "en": "finished"},
    "fehler": {"de": "mit Fehler beendet", "en": "ended with an error"},
    treiber.WARTET: {"de": "wartet auf die Person", "en": "waits for the person"},
    treiber.WARTET_KI: {"de": "wartet auf die KI", "en": "waits for the AI"},
    treiber.WARTET_AUFTRAG: {"de": "wartet auf einen Auftrag", "en": "waits for a job"},
    treiber.WARTET_FREIGABE: {"de": "wartet auf eine Freigabe", "en": "waits for an approval"},
    treiber.WARTET_WAHL: {"de": "wartet auf eine Wahl", "en": "waits for a choice"},
    treiber.WARTET_SEITE: {"de": "wartet auf den Seitenwechsel", "en": "waits for a page change"},
    NICHT_GESTARTET: {"de": "nicht gestartet", "en": "not started"},
}


def _status(lang: str, code: str) -> str:
    worte = _STATUS.get(code)
    return worte.get(lang, worte["de"]) if worte else code


def _t(lang: str, key: str, **werte: Any) -> str:
    texte = _T[key]
    return texte.get(lang, texte["de"]).format(**werte)


@dataclass
class TestErgebnis:
    name: str
    ok: bool
    status: str
    weg: list[str]
    ende: str
    abweichungen: list[str] = field(default_factory=list)
    #: Review AS-3b, Befund 4: was der Lauf ausgab (mit eingesetzten Platzhaltern), gekürzt.
    texte: list[str] = field(default_factory=list)


class _Stand:
    """Teile und Weg eines simulierten Laufs."""

    def __init__(self, test: AblaufTest, frist: float) -> None:
        self.teile: dict[str, Any] = dict(test.teile)
        self.weg: list[str] = []
        self.texte: list[str] = []
        self.werkzeuge = test.werkzeuge
        self.frist = frist
        #: Die offene Frage des letzten abfragenden Blocks — wie ``entities`` im Betrieb.
        self.fragen: dict[str, Any] = {}

    def besucht(self, schritt: str) -> None:
        """Jeder Schritt des Treibers: Weg merken, Frist und Deckel prüfen (hart, ohne Schleife)."""
        self.weg.append(schritt)
        if len(self.weg) > MAX_SCHRITTE:
            raise _ZuLang
        self.fristen()

    def fristen(self) -> None:
        if time.monotonic() > self.frist:
            raise _ZeitUm

    def geprueft(self, lauf: dict[str, Any], e: TestEingabe) -> dict[str, Any] | None:
        """Die Antwort, wie der Betrieb sie prüft — ``None``, wenn er sie verwürfe."""
        block_id = lauf.get("offener_block")
        if not isinstance(block_id, str):
            return None
        try:
            antwort = UiAntwort(block_id=block_id, daten=e.antwort or {})
        except ValueError:
            return None
        return antwort_pruefen(self.fragen.get(OFFENE_FRAGE), antwort)

    async def teil(self, name: str) -> Any:
        return self.teile.get(name)

    async def ersatz(self, schritt: str, name: str, args: dict[str, Any]) -> Any:
        # Querschnitts-Review AS-D, Befund 1: ein reiner Dienst rechnet wie im Betrieb — ein Eintrag
        # des Testfalls (auch ``null``) überschreibt ihn
        if schritt not in self.werkzeuge and name in werkzeuge.REINE_DIENSTE:
            return await werkzeuge.DIENSTE[name](args)
        wert = self.werkzeuge.get(schritt)
        # Review AS-1, Befund 2: im Betrieb liefert ein lesendes MCP-Werkzeug Text (``zug_basis``)
        if name in werkzeuge.LESENDE_MCP and wert is not None and not isinstance(wert, str):
            return json.dumps(wert, ensure_ascii=False)
        return wert

    @staticmethod
    async def auftrag(flow: str, _args: dict[str, Any]) -> str:
        return f"simulation-{flow}"

    @staticmethod
    async def vorlegen(name: str, args: dict[str, Any]) -> treiber.Vorlage:
        # Befund 4b: die eingesetzten Argumente sichtbar — was eine Auswahl ergab, sieht man sonst
        # nirgends (gekürzt in ``uebernehmen``)
        eingesetzt = json.dumps(args, ensure_ascii=False, default=str)
        return treiber.Vorlage(f"(Simulation) {name}: {eingesetzt}", "simulation")

    def umgebung(self, sprache: str, angemeldet: bool, seite: str = "/") -> treiber.Umgebung:
        # ohne Anmeldung gibt es im Betrieb weder Aufträge noch Vorlagen (``auftrag_zug.starter``)
        return treiber.Umgebung(
            teile=self.teil, sprache=sprache, ersatz=self.ersatz, simulation=True,
            protokoll=self.besucht, auftrag_starten=self.auftrag if angemeldet else None,
            vorlegen=self.vorlegen if angemeldet else None, seite=seite)

    def uebernehmen(self, aus: treiber.Ausgabe | None) -> None:
        for name, _typ, wert, _z in (aus.neue_teile if aus else []):
            self.teile[name] = wert
        vorschau = [aus.freigabe["vorschau"]] if aus and aus.freigabe else []
        for text in [*(aus.texte if aus else []), *vorschau]:
            if len(self.texte) < MAX_TEXTE:
                self.texte.append(text[:TEXT_ZEICHEN])
        for block in (aus.bloecke if aus else []):
            if block.art == "abfragen":
                merke_frage(self.fragen, block)


def _passt(status: Any, e: TestEingabe) -> bool:
    """Trägt die Eingabe, was der Wartepunkt braucht (Review AS-1, Befund 4)?"""
    if status == treiber.WARTET:
        return e.antwort is not None
    if status == treiber.WARTET_AUFTRAG:
        return e.ergebnis is not None or e.fehler
    if status == treiber.WARTET_FREIGABE:
        return e.freigabe is not None
    if status == treiber.WARTET_WAHL:
        return e.option is not None or e.text is not None
    if status == treiber.WARTET_SEITE:
        return e.seite is not None
    return True


async def _eingeben(ablauf: AblaufArea, lauf: dict[str, Any], e: TestEingabe, stand: _Stand,
                    umgebung: treiber.Umgebung) -> treiber.Ausgabe | None:
    """Eine Eingabe am wartenden Schritt — wie der Zug des Betriebs sie dem Treiber reicht."""
    status = lauf.get("status")
    if status == treiber.WARTET:
        modul = next((s.modul for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
        for name, _typ, wert, _z in teile_aus_antwort({"modul": modul, "daten": e.antwort or {}}):
            stand.teile[name] = wert
        return await treiber.weiter(ablauf, lauf, e.antwort or {}, umgebung)
    if status == treiber.WARTET_WAHL:
        # wie ``wahl_zug.getippt``: Text gleich einem Label ist diese Wahl (Querschnitts-Review
        # AS-3, Befund 2)
        schritt = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
        wahl = e.option or (treiber.wahl_aus_text(schritt, e.text) if schritt else None)
        return await treiber.weiter_wahl(ablauf, lauf, wahl, None if wahl else e.text, umgebung)
    if status == treiber.WARTET_SEITE:
        # AS-7a: wie der Seiten-Ping — die Seite dieser Eingabe gilt ab hier (auch für
        # ``wenn_seite`` danach)
        return await treiber.weiter_seite(ablauf, lauf, replace(umgebung, seite=e.seite or "/"))
    if status == treiber.WARTET_KI:
        stand.teile.update(e.teile)
        return await treiber.weiter_ki(ablauf, lauf, umgebung)
    if status == treiber.WARTET_AUFTRAG:
        return await treiber.weiter_auftrag(
            ablauf, lauf, None if e.fehler else (e.ergebnis or {}), umgebung)
    if e.freigabe == "nein":
        # die Abnahme verfällt, der Lauf wartet — „Vorschau erneut“ legt neu vor (Befund 3)
        return await treiber.erneut_vorlegen(ablauf, lauf, umgebung)
    # wie der Zug: ohne Schlüssel, alle gescheitert → ``bei_fehler`` (Querschnitts-Review AS-D,
    # Befund 3)
    return await treiber.weiter_freigabe(
        ablauf, lauf, None if e.fehler else freigabe_ergebnis.fuer_lauf(e.ergebnis or {}),
        umgebung)


#: Startdaten, die die Prüfung abweist — der Lauf beginnt nicht (wie im Zug).
_UNGUELTIG: Final = object()


def _startdaten(ablauf: AblaufArea, test: AblaufTest, lang: str,
                abweichungen: list[str]) -> Any:
    """AS-4a: die Startdaten des Testfalls, geprüft wie im Zug (``startdaten.pruefen``) — ``None``
    ohne Startschema und ohne Daten, :data:`_UNGUELTIG` bei einem Fehler (eine Abweichung)."""
    if not ablauf.start and test.start is None:
        return None
    art = "extern" if test.quelle == startdaten.QUELLE_GASTSEITE else "agent"
    if test.start is not None and (test.ab is not None
                                   or not any(a.art == art for a in ablauf.ausloeser)):
        # Review AS-4a, Befund 9: Daten bringen nur die Gastseite (Auslöser extern) und seit AS-5a
        # der Vorschlag der KI (agent) — nie ein Knopf, eine Wendung oder ein Modul („Beginnen ab“)
        abweichungen.append(_t(lang, "start_ohne_extern"))
        return _UNGUELTIG
    sauber, fehler = startdaten.pruefen(ablauf, test.start)
    if fehler:
        abweichungen.append(_t(lang, "start", f=", ".join(fehler)[:160]))
        return _UNGUELTIG
    return sauber if ablauf.start else None


async def testen(ablauf: AblaufArea, test: AblaufTest, lang: str = "de",
                 frist: float | None = None) -> TestErgebnis:
    """Einen Testfall durchspielen. ``frist`` (``time.monotonic``): danach :class:`_ZeitUm`."""
    stand = _Stand(test, time.monotonic() + BUDGET_S if frist is None else frist)
    umgebung = stand.umgebung(lang, test.angemeldet, test.seite)
    abweichungen: list[str] = []
    eingaben = list(test.eingaben)
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    if "anmeldung" in ablauf.voraussetzungen and not test.angemeldet:
        lauf: dict[str, Any] = {"status": NICHT_GESTARTET, "schritt": ""}
    elif test.ab is not None and test.ab not in index:
        abweichungen.append(_t(lang, "ab", ab=test.ab))
        lauf = {"status": NICHT_GESTARTET, "schritt": ""}
    elif (start := _startdaten(ablauf, test, lang, abweichungen)) is _UNGUELTIG:
        lauf = {"status": NICHT_GESTARTET, "schritt": ""}
    else:
        aus = await treiber.starten(ablauf, umgebung, ab=index.get(test.ab or "", 0),
                                    gewaehlt=list(test.gewaehlt), start=start,
                                    start_quelle=test.quelle
                                    if test.start is not None else None)
        stand.uebernehmen(aus)
        lauf = aus.lauf
    while eingaben and lauf.get("status") in _WARTEND:
        stand.fristen()
        e = eingaben.pop(0)
        if e.bei != lauf.get("schritt"):
            # die Eingabe gehört zu einem anderen Schritt — der Testfall hält hier an
            abweichungen.append(_t(lang, "falsch", bei=e.bei, ist=lauf.get("schritt")))
            break
        if not _passt(lauf.get("status"), e):
            was = _ERWARTET.get(str(lauf.get("status")), {})
            abweichungen.append(_t(lang, "passt", bei=e.bei, was=was.get(lang, was.get("de", ""))))
            break
        if lauf.get("status") == treiber.WARTET:
            if (geprueft := stand.geprueft(lauf, e)) is None:
                abweichungen.append(_t(lang, "antwort", bei=e.bei))
                break
            e = e.model_copy(update={"antwort": geprueft.get("daten") or {}})
        weiter = await _eingeben(ablauf, dict(lauf), e, stand, umgebung)
        if weiter is None:
            if lauf.get("status") == treiber.WARTET_WAHL:
                # AS-3a: wie im Betrieb — eine Wahl, die der Schritt nicht anbietet, setzt
                # nicht fort
                abweichungen.append(_t(lang, "wahl", bei=e.bei))
            elif lauf.get("status") == treiber.WARTET_SEITE:
                abweichungen.append(_t(lang, "seite", bei=e.bei))
            break
        if lauf.get("status") == treiber.WARTET_SEITE:
            umgebung = replace(umgebung, seite=e.seite or "/")
        stand.uebernehmen(weiter)
        lauf = weiter.lauf
    abweichungen += [_t(lang, "uebrig", bei=e.bei) for e in eingaben]
    status, ende = str(lauf.get("status") or ""), str(lauf.get("schritt") or "")
    soll = test.erwartet
    if soll.weg and soll.weg != stand.weg:
        abweichungen.append(_t(lang, "weg", soll=" → ".join(soll.weg),
                               ist=" → ".join(stand.weg) or "—"))
    if soll.status and soll.status != status:
        abweichungen.append(_t(lang, "status", soll=_status(lang, soll.status),
                               ist=_status(lang, status)))
    if soll.ende and soll.ende != ende:
        abweichungen.append(_t(lang, "ende", soll=soll.ende, ist=ende))
    abweichungen += [_t(lang, "teil", name=n) for n in soll.teile if stand.teile.get(n) is None]
    return TestErgebnis(name=test.name, ok=not abweichungen, status=status, weg=stand.weg,
                        ende=ende, abweichungen=abweichungen, texte=stand.texte)


def _nicht_ausgefuehrt(test: AblaufTest, grund: str) -> TestErgebnis:
    return TestErgebnis(name=test.name, ok=False, status="", weg=[], ende="", abweichungen=[grund])


async def alle(ablauf: AblaufArea, lang: str = "de") -> list[TestErgebnis]:
    """Alle Testfälle des Ablaufs, in ihrer Reihenfolge.

    Review AS-1, Befund 5: hat „Prüfen“ Befunde, besteht kein Testfall — der Ablauf ließe sich so
    nicht speichern (und ohne Schritte nicht starten). Bricht ein Testfall ab, steht das bei ihm;
    die anderen laufen. Befund 9: höchstens :data:`BUDGET_S` für alle zusammen."""
    if befunde := pruefung.pruefe(ablauf, lang):
        grund = _t(lang, "befunde", n=len(befunde), erster=befunde[0])
        return [_nicht_ausgefuehrt(t, grund) for t in ablauf.tests]
    ergebnisse: list[TestErgebnis] = []
    frist = time.monotonic() + BUDGET_S
    for test in ablauf.tests:
        if time.monotonic() > frist:
            ergebnisse.append(_nicht_ausgefuehrt(test, _t(lang, "budget", s=BUDGET_S)))
            continue
        try:
            ergebnisse.append(await testen(ablauf, test, lang, frist))
        except _ZeitUm:
            ergebnisse.append(_nicht_ausgefuehrt(test, _t(lang, "budget", s=BUDGET_S)))
        except _ZuLang:
            ergebnisse.append(_nicht_ausgefuehrt(test, _t(lang, "schritte", n=MAX_SCHRITTE)))
        except Exception as fehler:  # noqa: BLE001 — ein kaputter Testfall kippt nicht die anderen
            art = type(fehler).__name__
            logger.warning("Ablauf-Simulation %s: Testfall brach ab (%s)", ablauf.id, art)
            ergebnisse.append(_nicht_ausgefuehrt(test, _t(lang, "abbruch", art=art)))
    return ergebnisse


async def im_thread(ablauf: AblaufArea, lang: str = "de") -> list[TestErgebnis]:
    """:func:`alle` in einem eigenen Thread mit eigener Schleife (wie ``seed_sync._lesen``) — die
    Simulation rechnet ohne Pause und hielte sonst die Chat-Züge dieser Replika an."""
    return await asyncio.to_thread(asyncio.run, alle(ablauf, lang))
