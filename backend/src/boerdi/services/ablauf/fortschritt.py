"""Der Stand eines laufenden Ablaufs für die Leiste im Widget (Paket AS-Ua, Plan 2026-11-09 §5h).

- :func:`position`: „Schritt n von m“ (U-3). ``n`` ist die Länge des längsten einfachen Wegs vom
  ersten Schritt bis hierher, ``m`` = ``n`` − 1 + der längste einfache Weg von hier bis zum Ende.
  So passt ``m`` zum Weg nach einer Verzweigung. Es zählen die regulären Kanten, keine
  ``ende``-Schritte und keine Verzweigungen (die sieht die Person nie); ein Schritt, der nur
  hinter ``bei_fehler`` liegt, zählt den Weg dorthin mit (Review AS-Ua, Befund 5). Der Weg ab hier
  läuft nicht über Schritte, von denen aus man hierher kommt: Ein Rückweg („Nochmal wählen“)
  verlängert ``m`` nicht (Rückmeldung 2026-11-15, WF-1 — vorher „Schritt 2 von 8“, dann
  „Schritt 4 von 11“).
- :func:`stand`: der öffentliche Stand ``ui.ablauf`` (U-1, U-2) aus dem Sitzungsverweis, ohne die
  Datenbank. Ohne den Teil ``start`` und ohne Kennungen in UUID-Form (D10: „ohne nodeIds“).

Die Suche nach längsten einfachen Wegen ist im schlimmsten Fall teuer. Darum (Review AS-Ua,
Befunde 3 und 4): je Suche ein eigenes Besuchsbudget, ``bis`` geht nur über Schritte, die das Ziel
erreichen können, und das Ergebnis ist je Fassung des Ablaufs zwischengespeichert — es ändert sich
nur mit den Schritten.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import ausloeser, treiber, typen
from boerdi.services.ablauf.pruefung import nachfolger, regulaere_nachfolger

#: Ein beendeter Lauf hat keine Leiste.
BEENDET: Final = frozenset(treiber.BEENDET)
#: Besuche je Suche. Ist es erschöpft, gilt für ``bis`` der bis dahin längste Weg und für ``ab``
#: eine obere Schätzung (die zählenden Schritte, die von hier erreichbar sind).
_BUDGET: Final = 20_000
_SPEICHER_HOECHSTENS: Final = 512
_UUID: Final = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}")
#: Kleinigkeit 11 (zweites Review AS-U): der Kurztext ist gekürzt — auch ein Bruchstück einer
#: Kennung am Ende fällt weg.
_UUID_REST: Final = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]*$")

#: Schritte, die nicht als „Schritt n“ zählen: das Ende und die unsichtbare Verzweigung (WF-1).
_ZAEHLT_NICHT: Final = frozenset({"ende", "verzweigung"})

_speicher: dict[tuple[str, str, str], tuple[int, int]] = {}
_gerechnet = 0


def zaehler() -> int:
    """Wie oft eine Position gerechnet (nicht aus dem Speicher genommen) wurde — für Tests."""
    return _gerechnet


class _Suche:
    """Längste einfache Wege über die Kanten ``kanten``."""

    def __init__(self, ablauf: AblaufArea,
                 kanten: Callable[[AblaufArea, int], list[str]]) -> None:
        self.ablauf = ablauf
        self.index = {s.id: i for i, s in enumerate(ablauf.schritte)}
        self.weiter = [[self.index[z] for z in kanten(ablauf, i) if z in self.index]
                       for i in range(len(ablauf.schritte))]

    def _zaehlt(self, i: int) -> int:
        return 0 if self.ablauf.schritte[i].typ in _ZAEHLT_NICHT else 1

    def _erreicht(self, ziel: int) -> set[int]:
        """Die Schritte, von denen aus ``ziel`` erreichbar ist (samt ``ziel``)."""
        rueck: dict[int, list[int]] = {}
        for i, ziele in enumerate(self.weiter):
            for j in ziele:
                rueck.setdefault(j, []).append(i)
        gesehen, offen = {ziel}, [ziel]
        while offen:
            for i in rueck.get(offen.pop(), []):
                if i not in gesehen:
                    gesehen.add(i)
                    offen.append(i)
        return gesehen

    def _vorher(self, start: int) -> set[int]:
        """Die Schritte vor ``start``: vom ersten Schritt aus erreichbar, ohne über ``start`` zu
        gehen."""
        if start == 0:
            return set()
        gesehen, offen = {0}, [0]
        while offen:
            for j in self.weiter[offen.pop()]:
                if j != start and j not in gesehen:
                    gesehen.add(j)
                    offen.append(j)
        return gesehen

    def _von(self, start: int, ohne: set[int] | None = None) -> set[int]:
        """Von ``start`` erreichbar — ohne ``ohne`` zu betreten (Review WF-1, Befund 5: sonst
        zählte die Schätzung den Weg über einen Rückweg mit)."""
        ohne = ohne or set()
        gesehen, offen = {start}, [start]
        while offen:
            for j in self.weiter[offen.pop()]:
                if j not in gesehen and j not in ohne:
                    gesehen.add(j)
                    offen.append(j)
        return gesehen

    def bis(self, ziel: int) -> int | None:
        """Längster Weg (in zählenden Schritten) vom ersten Schritt bis ``ziel``."""
        erlaubt = self._erreicht(ziel)
        if not self.ablauf.schritte or 0 not in erlaubt:
            return None
        bester: int | None = None
        besucht = 0

        def gehen(i: int, laenge: int, pfad: frozenset[int]) -> None:
            nonlocal bester, besucht
            besucht += 1
            laenge += self._zaehlt(i)
            if i == ziel:
                bester = laenge if bester is None else max(bester, laenge)
                return
            if besucht > _BUDGET:
                return
            for j in self.weiter[i]:
                if j in erlaubt and j not in pfad:
                    gehen(j, laenge, pfad | {j})

        gehen(0, 0, frozenset({0}))
        return bester

    def rueckwege(self, start: int) -> set[int]:
        """Ziele von Rückwegen ab ``start``: Schritte, die vor ``start`` liegen (:meth:`_vorher`)
        und wieder zu ``start`` führen (:meth:`_erreicht`). Beides zusammen: allein „liegt davor“
        träfe in einem stark verzweigten Ablauf fast alles, allein „führt zurück“ in einem Kreis
        auch den Weg nach vorn (WF-1). Über alle Kanten gerechnet, auch ``bei_fehler`` (Review
        WF-1, Befund 2: sonst fehlten die Rückwege eines Schritts hinter einem Fehlerzweig)."""
        return (self._vorher(start) & self._erreicht(start)) - {start}

    def ab(self, start: int, zurueck: set[int] | None = None) -> int:
        """Längster Weg (in zählenden Schritten) von ``start`` bis zu einem Ende — ohne die Ziele
        von Rückwegen (``zurueck``, :meth:`rueckwege`)."""
        zurueck = self.rueckwege(start) if zurueck is None else zurueck
        bester = 0
        besucht = 0

        def gehen(i: int, laenge: int, pfad: frozenset[int]) -> None:
            nonlocal bester, besucht
            besucht += 1
            laenge += self._zaehlt(i)
            bester = max(bester, laenge)
            if besucht > _BUDGET:
                return
            for j in self.weiter[i]:
                if j not in pfad and j not in zurueck:
                    gehen(j, laenge, pfad | {j})

        gehen(start, 0, frozenset({start}))
        if besucht > _BUDGET:
            bester = max(bester, sum(self._zaehlt(i) for i in self._von(start, zurueck)))
        return bester


def _rechnen(ablauf: AblaufArea, i: int) -> tuple[int, int]:
    global _gerechnet
    _gerechnet += 1
    regulaer, alle = _Suche(ablauf, regulaere_nachfolger), _Suche(ablauf, nachfolger)
    # ``bis`` kann 0 sein (nur Verzweigungen davor, die nicht zählen) — dann der Weg über alle
    # Kanten, zuletzt 1. Eine Verzweigung selbst wartet nie, steht also nie in der Leiste.
    nr = regulaer.bis(i) or alle.bis(i) or 1
    return nr, max(nr, nr - 1 + regulaer.ab(i, alle.rueckwege(i)))


def position(ablauf: AblaufArea, schritt: Any) -> tuple[int, int] | None:
    """``(n, m)`` für den Schritt ``schritt`` — ``None``, wenn es ihn nicht gibt."""
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    if not isinstance(schritt, str) or (i := index.get(schritt)) is None:
        return None
    schluessel = (ablauf.id, treiber.fassung(ablauf), schritt)
    if (gespeichert := _speicher.get(schluessel)) is not None:
        return gespeichert
    if len(_speicher) >= _SPEICHER_HOECHSTENS:
        _speicher.clear()
    _speicher[schluessel] = ergebnis = _rechnen(ablauf, i)
    return ergebnis


def stand(entities: dict[str, Any], aufrufer: str, lang: str) -> dict[str, Any] | None:
    """Der öffentliche Stand des Laufs dieses Gesprächs — ``None`` ohne nicht beendeten Lauf, ohne
    bekannten aktiven Ablauf, nach einer Änderung seiner Schritte (der nächste Zug bricht den Lauf
    ab; Review AS-Ua, Befund 9) oder mit einem Schritt, den der Ablauf nicht mehr hat."""
    vw = arbeitsstand.verweis(entities, aufrufer)
    lauf = (vw or {}).get("lauf")
    if not isinstance(lauf, dict) or lauf.get("status") in BEENDET:
        return None
    ablauf = ausloeser.laden(lauf.get("ablauf"))
    if not treiber.gilt(ablauf, lauf):
        return None
    if (pos := position(ablauf, lauf.get("schritt"))) is None:
        return None
    titel = (ablauf.titel.get(lang) or ablauf.titel.get("de") or ablauf.id).strip()
    teile = (vw or {}).get("teile") or {}
    return {
        "id": ablauf.id, "titel": titel, "nr": pos[0], "von": pos[1],
        "status": str(lauf.get("status") or ""), "lauf": str(lauf.get("start") or ""),
        # Zweites Review, Z-8: der Lauf einer angemeldeten Person — ohne ihre Anmeldung (abgemeldet)
        # blendet das Widget die Leiste aus; ihr Abbruch liefe anonym ins Leere.
        "persoenlich": arbeitsstand.ist_persoenlich(aufrufer),
        "teile": [{"name": name, "text": _UUID_REST.sub("…", _UUID.sub("…", str(t.get("z"))))}
                  for name, t in teile.items()
                  if name != typen.START_TEIL and isinstance(t, dict) and t.get("z")],
        **_weg(ablauf, lauf, lang),
    }


def _weg(ablauf: Any, lauf: dict[str, Any], lang: str) -> dict[str, Any]:
    """AS-7 (Querschnitts-Review, Befund 1): wartet eine Führung, der Weg zur Seite — die Chips der
    alten Blase sind nach dem Neuladen weg, die Leiste behält ihn."""
    if lauf.get("status") != treiber.WARTET_SEITE:
        return {}
    s = next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
    if s is None or s.typ != "seite" or not s.url:
        return {}
    return {"weg": {"label": treiber.seiten_label(s, lang), "url": s.url}}
