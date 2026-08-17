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

from boerdi.services.config_loader import load_engine

logger = logging.getLogger(__name__)

#: Die Kopfzeile der Übersteuerung. Bewusst NICHT als ``Header()``-Parameter
#: deklariert — das trüge sie in das eingefrorene OpenAPI-Dokument ein.
ENGINE_HEADER: Final = "X-Boerdi-Engine"

PATTERN: Final = "pattern"
AGENT: Final = "agent"

#: Die dritte Maschine: Agent-Schleife, aber mit dem Musterkatalog als Werkzeug.
#: Sie wählt kein Muster im Voraus, sondern lässt das Modell eines ziehen, wenn es
#: die Trefferlage kennt — deshalb steht sie zwischen den beiden anderen und nicht
#: neben ihnen.
HYBRID: Final = "hybrid"

_ERLAUBT: Final = frozenset({PATTERN, AGENT, HYBRID})

#: Die Maschinen, die einen Zug über die Agent-Schleife beantworten.
_UEBER_DIE_SCHLEIFE: Final = frozenset({AGENT, HYBRID})


def laeuft_ueber_die_schleife(engine: str) -> bool:
    """Beantwortet diese Maschine den Zug über die Agent-Schleife?

    ``agent`` und ``hybrid`` teilen sich die Schleife, ihre Deckel und den
    Verzicht auf den Klassifikator; verschieden ist allein, ob der Musterkatalog
    als Werkzeug danebenliegt. **Vier** Knoten fragen danach (``assess``,
    ``route`` zweimal, ``respond``) — als Vergleich gegen Literale geschrieben,
    wäre der nächste Modus vier stille Auslassungen, und jede einzelne davon
    ließe den Zug halb über die eine und halb über die andere Maschine laufen.
    """
    return engine in _UEBER_DIE_SCHLEIFE


def choose_engine(header: str | None) -> str:
    """``"pattern"``, ``"agent"`` oder ``"hybrid"`` für diesen Zug.

    Ein unlesbarer Konfigurationsbereich endet bei der Muster-Engine: der
    Bestand ist der sichere Weg, und ein Zug soll nicht deshalb anders
    beantwortet werden, weil gerade die Datenbank hakt.
    """
    gewuenscht = (header or "").strip().lower()
    if gewuenscht in _ERLAUBT:
        return gewuenscht
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
