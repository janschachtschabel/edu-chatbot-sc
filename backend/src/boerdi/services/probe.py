"""Paket AS-8a: Probe-Sitzungen aus der Studio-Vorschau — Trockenlauf (Plan 2026-11-09 §5n).

Die Redaktion probiert einen Ablauf im echten Widget aus. Ob ein Zug zu einer Probe gehört, stellt
der Chat-Endpunkt fest (``api/probe_anfrage``: Flag ``probe`` plus gültiges Studio-Cookie) und gibt
es über ``TurnContext.probe`` an :func:`binde` (``graph/build.begin_turn``). ``setup`` merkt die
Probe an der Sitzung (``entities._probe``) und hebt den Merker für jeden Folgezug dieser Sitzung —
die Probe klebt, auch wenn ein späterer Zug das Flag nicht mehr trägt.

Zwei Seiten (Review AS-8a, Befund 4): :func:`aktiv` **schränkt ein** (Trockenlauf) und gilt auch aus
der gemerkten Marke. :func:`recht` **erweitert** (ausgeschaltete Abläufe, Startdaten ohne Auslöser)
und gilt nur mit dem Studio-Cookie DIESES Zuges — eine Marke in den Entities, woher auch immer sie
käme, gibt nie mehr Rechte.

Der Merker ist ein geteiltes Objekt in einer ContextVar: LangGraph startet jeden Knoten in einer
Kopie des Kontexts, ein ``set`` in ``setup`` sähe der nächste Knoten nicht (Paket 10).

Was der Trockenlauf abschneidet: schreibende MCP-Aufrufe (:func:`trocken_noetig`, geprüft in
``services/mcp/client``), die Ablage (``api/ui_ablage``, liest :func:`in_sitzung`) und den Start
echter Aufträge (``services/ablauf/auftrag_zug.starter``).
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Final

from boerdi.domain.host_capabilities import LESENDE_WLO_WERKZEUGE
from boerdi.domain.write_confirm import CONFIRMABLE_TOOLS, SCHLUESSEL_FELDER
from boerdi.i18n.bot_text import bot_text
from boerdi.i18n.locale import Locale

#: In ``entities``: diese Sitzung ist eine Probe der Studio-Vorschau (nur ``True`` zählt).
ENTITY_KEY: Final = "_probe"
#: Plan 2026-11-10, TB-E2: diese Sitzung ist ein Gespräch der Studio-Vorschau — zählt nicht als
#: Betrieb (``services/session_origin``), schränkt aber nichts ein (kein Trockenlauf).
VORSCHAU_KEY: Final = "_vorschau"


@dataclass
class _Merker:
    aktiv: bool = False
    #: nur aus dem Cookie dieses Zuges (``binde``), nie aus der Sitzung
    recht: bool = False
    sprache: Locale = "de"
    #: TB-E2: nur aus dem Cookie dieses Zuges, wie ``recht``
    vorschau: bool = False


_merker: ContextVar[_Merker | None] = ContextVar("probe_merker", default=None)


def binde(aktiv: bool, sprache: Locale = "de", *, vorschau: bool = False) -> None:
    """Den Merker des Zuges binden — einmal, vor dem Graphen (``begin_turn``)."""
    _merker.set(_Merker(aktiv=aktiv, recht=aktiv, sprache=sprache, vorschau=vorschau or aktiv))


def aktiv() -> bool:
    """Läuft dieser Zug als Probe (Trockenlauf)? Ohne gebundenen Merker: nein."""
    merker = _merker.get()
    return merker is not None and merker.aktiv


def recht() -> bool:
    """Hat dieser Zug das Studio-Recht der Probe (Cookie geprüft)? Nur dann starten ausgeschaltete
    Abläufe und Startdaten ohne passenden Auslöser."""
    merker = _merker.get()
    return merker is not None and merker.recht


def in_sitzung(entities: dict[str, Any] | None) -> bool:
    """Ist die Sitzung eine Probe? Für Endpunkte außerhalb des Graphen (Ablage)."""
    return isinstance(entities, dict) and entities.get(ENTITY_KEY) is True


def uebernehmen(entities: dict[str, Any]) -> bool:
    """Merker und Sitzung abgleichen (``setup``): eine erkannte Probe kommt an die Sitzung, eine
    gemerkte hebt den Merker. ``True``, wenn die Marke neu gesetzt wurde — der Aufrufer schreibt sie
    dann sofort fest (nicht jeder Zug erreicht ``persist``)."""
    merker = _merker.get()
    if merker is None:
        return False
    neu = False
    # TB-E2: das Gespräch der Vorschau merkt sich die Sitzung (nur Herkunft, keine Einschränkung)
    if merker.vorschau and entities.get(VORSCHAU_KEY) is not True:
        entities[VORSCHAU_KEY] = True
        neu = True
    if in_sitzung(entities):
        merker.aktiv = True
        return neu
    if merker.aktiv:
        entities[ENTITY_KEY] = True
        return True
    return neu


def trocken_noetig(name: str, args: dict[str, Any]) -> bool:
    """Würde dieser Aufruf schreiben? Schreibend ist jedes ``wlo_``-Werkzeug außer den lesenden
    (``host_capabilities``); erlaubt bleibt nur die Vorschau eines bestätigbaren Werkzeugs, also ein
    Aufruf ohne Schlüssel — der Server schreibt dabei nichts und zeigt den echten Plan."""
    if not name.startswith("wlo_") or name in LESENDE_WLO_WERKZEUGE:
        return False
    vorschau = name in CONFIRMABLE_TOOLS and not any(k in args for k in SCHLUESSEL_FELDER)
    return not vorschau


def trocken_text(name: str) -> str:
    """Die Antwort an Stelle des Werkzeugs — in der Sprache des Zuges."""
    merker = _merker.get()
    return bot_text(merker.sprache if merker else "de", "probe.trocken", werkzeug=name)
