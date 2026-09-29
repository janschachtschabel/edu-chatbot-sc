"""Welche Maschine diesen Zug beantwortet (A4a).

Der Umschalter liegt **zweifach**, und das ist Absicht:

* ``01-base/engine`` (Studio, redaktionell pflegbar) ist die **Vorgabe**.
* Die Kopfzeile ``X-Boerdi-Engine`` ist die **Übersteuerung je Anfrage**. Ohne
  sie ließe sich im Golden-Lauf nicht *eine* Suite gegen *beide* Maschinen
  fahren, und im Betrieb keine Stichprobe ziehen. Undeklariert aus ``Request``
  gelesen, also null Vertragsänderung — Präzedenz ``Accept-Language`` (C1-e1)
  und ``WLO-Access-Block`` (C5-a).

Dieselbe Schichtung wie ``MCP_AUTH_TOKEN`` (Anlage) ↔ ``WLO-Access-Block`` (Zug).

**Unbekannte Werte fallen auf die Vorgabe zurück, nicht auf einen Fehler.** Ein
Tippfehler in einer Kopfzeile darf einen Zug nicht abbrechen — und schon gar
nicht still auf den jeweils anderen Weg schalten. Die Übersteuerung wirkt in
beide Richtungen: eine auf ``agent`` gestellte Anlage muss sich stichprobenweise
gegen den Bestand messen lassen.
"""

from __future__ import annotations

import logging
from typing import Final

from boerdi.domain.config_models.engine import warne_hybrid_einmal as _warne_einmal
from boerdi.services.config_loader import load_engine

logger = logging.getLogger(__name__)

#: Die Kopfzeile der Übersteuerung. Bewusst NICHT als ``Header()``-Parameter
#: deklariert — das trüge sie in das eingefrorene OpenAPI-Dokument ein.
ENGINE_HEADER: Final = "X-Boerdi-Engine"

PATTERN: Final = "pattern"
AGENT: Final = "agent"

_ERLAUBT: Final = frozenset({PATTERN, AGENT})

#: K1-1 (2026-09-27): der Hybrid ist entfernt — die K0-Messung zeigte ihn
#: zwischen den beiden anderen, ohne eigenen Mehrwert. Eine Einbettung, die ihn
#: noch anfordert, bekommt die Schleife statt der Vorgabe: sie hatte eine
#: Schleife bestellt, und still auf die Muster-Maschine zu fallen, wäre der
#: größere Bruch.
_ALIASE: Final = {"hybrid": AGENT}


def laeuft_ueber_die_schleife(engine: str) -> bool:
    """Beantwortet diese Maschine den Zug über die Agent-Schleife?

    Vier Knoten fragen danach (``assess``, ``merge``, ``route``, ``respond``) —
    an einer Stelle statt als Vergleich gegen Literale je Knoten, damit ein
    künftiger Modus keine stille Auslassung wird.

    Ob die Schleife einen einzelnen ZUG beantwortet, sagt
    :func:`zug_laeuft_ueber_die_schleife` — dort geht die Sicherheit vor.
    """
    return engine == AGENT


def zug_laeuft_ueber_die_schleife(engine: str, erzwungenes_muster: str | None) -> bool:
    """Beantwortet die Schleife DIESEN Zug? (SF-1, 2026-09-26)

    Nein, sobald das Sicherheits-Gate ein Muster erzwungen hat (M01 Krise, M02
    Drohung) — gleich, welche Maschine gewählt ist. Die Schutzantworten gibt es
    nur im Muster-Weg; in der Schleife kamen von ihnen allein die gesperrten
    Such-Werkzeuge an, die Hilfsnummern und die Ablehnung nie.

    ``route`` (Musterwahl) und ``respond`` (Übergabe an ``respond_agent``)
    fragen beide HIER. Fragte einer nach der Maschine und der andere nach dem
    Zug, bekäme die Schleife das Schutzmuster oder der Muster-Weg das
    synthetische. Die Schnellwege fragen bewusst weiter nach der Maschine und
    bleiben in den Schleifen aus; zusätzlich schaltet ``route`` sie bei jeder
    Erzwingung ab, auch in der Muster-Maschine (SF-1b). Ein erzwungener Zug
    bekommt die Musterwahl, keinen Lernpfad und kein Canvas-Material.
    """
    return laeuft_ueber_die_schleife(engine) and not erzwungenes_muster


def choose_engine(header: str | None) -> str:
    """``"pattern"`` oder ``"agent"`` für diesen Zug.

    Ein unlesbarer Konfigurationsbereich endet bei der Muster-Engine: der
    Bestand ist der sichere Weg, und ein Zug soll nicht deshalb anders
    beantwortet werden, weil gerade die Datenbank hakt.
    """
    gewuenscht = (header or "").strip().lower()
    if gewuenscht in _ERLAUBT:
        return gewuenscht
    if gewuenscht in _ALIASE:
        _warne_einmal(f"Kopfzeile {ENGINE_HEADER}")
        return _ALIASE[gewuenscht]
    if gewuenscht:
        logger.info(
            "Kopfzeile %s mit unbekanntem Wert vorgelegt — es gilt die Vorgabe "
            "aus 01-base/engine.", ENGINE_HEADER)
    try:
        return load_engine().mode
    except Exception:
        logger.warning(
            "01-base/engine nicht lesbar — dieser Zug läuft über die "
            "Muster-Engine.", exc_info=True)
        return PATTERN
