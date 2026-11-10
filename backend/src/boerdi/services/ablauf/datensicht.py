"""Die Sicht „Daten“ eines Ablaufs (Paket AS-Dc, Plan 2026-11-09 §5e, D8).

Je Teil: die Typen seiner Schreiber, die schreibenden und die lesenden Schritte (Stellen in
``schritte``), ob er vor dem Start da ist (Modul-Auslöser) und ein Beispielwert aus den
Testfällen. Gelesen wird über ``$teil``-Verweise (auch Auswahlen), Platzhalter in ``text`` und
``freigabe``, ``wenn_teil`` und die Quelle von ``wenn_wert``.

Im Backend gerechnet und mit „Prüfen“ geliefert: die Typen kommen aus derselben Quelle wie die
Prüfung (``typen``) — eine zweite Tabelle im Studio liefe auseinander (Review AS-Db, Befund 6).
Rein, ohne I/O außer dem Katalog der Module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import typen
from boerdi.services.ablauf.pruefung import MAX_SCHRITTE, schreibt_mit_freigabe

#: So lang wird ein Beispielwert höchstens (als JSON).
BEISPIEL_ZEICHEN: Final = 160
#: Ausgabe einer KI — kein fester Typ.
KI: Final = "?"
#: Ein Teil eines Moduls ohne bekannte Normalform (Review AS-Dc, Befund 7).
UNBEKANNT: Final = "…"


@dataclass
class Zeile:
    name: str
    typen: list[str] = field(default_factory=list)
    schreiber: list[int] = field(default_factory=list)
    leser: list[int] = field(default_factory=list)
    vor_dem_start: bool = False
    #: Kann ein Modul im Gespräch hinterlassen (Review AS-Dc, Befund 1: sonst schreibt ihn nichts).
    aus_gespraech: bool = False
    beispiel: str | None = None


def _werte(ablauf: AblaufArea, test: Any) -> dict[str, Any]:
    """Was ein Testfall an Werten nennt, je Teil — vor dem Start, Ergebnisse der Werkzeuge, die
    Eingaben (Teile einer KI, Freitext, Ergebnis eines Auftrags oder einer Freigabe; Review AS-Dc,
    Befund 3). Ein schreibendes Werkzeug mit Freigabe nimmt ``werkzeuge`` nicht (Simulation)."""
    nach_id = {s.id: s for s in ablauf.schritte}
    werte: dict[str, Any] = dict(test.teile)
    if test.start is not None and ablauf.start:
        werte.setdefault(typen.START_TEIL, test.start)   # Review AS-4a, Befund 7
    for s in ablauf.schritte:
        if (s.typ == "werkzeug" and s.schreibt and not schreibt_mit_freigabe(s)
                and test.werkzeuge.get(s.id) is not None):
            werte.setdefault(s.schreibt, test.werkzeuge[s.id])
    for e in test.eingaben:
        for name, wert in e.teile.items():
            werte.setdefault(name, wert)
        s = nach_id.get(e.bei)
        if s is None:
            continue
        if e.text and s.freitext:
            werte.setdefault(s.freitext.schreibt, e.text)
        if e.option and s.typ == "nachricht" and s.schreibt:   # TB-T1
            option = next((o for o in s.optionen or [] if o.id == e.option), None)
            if option is not None:
                from boerdi.services.ablauf.treiber import wahl_wert

                werte.setdefault(s.schreibt, wahl_wert(option))
        if e.ergebnis is not None and s.schreibt:
            werte.setdefault(s.schreibt, e.ergebnis)
    return werte


def _beispiel(ablauf: AblaufArea, name: str) -> str | None:
    """Der erste Wert aus den Testfällen (in ihrer Reihenfolge), gekürzt."""
    for test in ablauf.tests:
        werte = _werte(ablauf, test)
        if name not in werte or werte[name] is None:
            continue
        wert = werte[name]
        text = wert if isinstance(wert, str) else json.dumps(wert, ensure_ascii=False, default=str)
        return text if len(text) <= BEISPIEL_ZEICHEN else text[:BEISPIEL_ZEICHEN - 1] + "…"
    return None


def tabelle(ablauf: AblaufArea, module: dict[str, Any] | None = None) -> list[Zeile]:
    """Die Zeilen der Sicht „Daten“, nach Teilname sortiert (leer bei zu vielen Schritten, wie die
    Prüfung, Befund 8)."""
    if not 1 <= len(ablauf.schritte) <= MAX_SCHRITTE:
        return []
    if module is None:
        from boerdi.ui_module import katalog

        module = katalog.katalog()
    zeilen: dict[str, Zeile] = {}

    def zeile(name: str) -> Zeile:
        return zeilen.setdefault(name, Zeile(name=name))

    for name, typ in typen.start_teile(ablauf, module).items():
        z = zeile(name)
        z.vor_dem_start = True
        z.typen.append(typ or UNBEKANNT)
    for i, s in enumerate(ablauf.schritte):
        ki = s.agent.ausgabe if s.typ == "agent" and s.agent else None
        for name, typ in typen.schritt_ausgaben(s, module).items():
            z = zeile(name)
            z.schreiber.append(i)
            z.typen.append(typ or (KI if name == ki else UNBEKANNT))
        for name in typen.gelesene_teile(s):
            zeile(name).leser.append(i)
    gespraech = typen.teile_aus_dem_gespraech(module)
    for z in zeilen.values():
        z.aus_gespraech = z.name in gespraech
        if not z.typen and z.aus_gespraech:
            z.typen.append(gespraech[z.name] or UNBEKANNT)
        z.typen = list(dict.fromkeys(z.typen))
        z.beispiel = _beispiel(ablauf, z.name)
    return [zeilen[n] for n in sorted(zeilen)]
