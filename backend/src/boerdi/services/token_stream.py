"""Der Token-Strom eines Chat-Zugs (Plan ``docs/plans/2026-10-01-token-streaming.md``, T6).

Eine Instanz je Anfrage (CLAUDE.md, Regel 3): ``api/chat._stream_turn`` legt sie
an und reicht sie als ``on_token`` in den Graphen. ``respond`` entscheidet, ob
der Zug streamt — :meth:`TokenStrom.oeffnen` mit der Umformung der
Endverarbeitung oder :meth:`TokenStrom.sperren` mit dem Grund. Danach ist die
Instanz das ``on_token`` der Antwortrunde.

Was hinausgeht, bestimmt :class:`~boerdi.domain.stream_preview.VorschauStrom`.
Hier wohnt nur der Takt — das erste Stück sofort, danach höchstens alle
``takt_s`` Sekunden, gemessen beim Eintreffen eines Stücks (kein Timer, keine
eigene Task) — und die Messung am Ende: passt ``result.content`` zum
Gesendeten, oder springt die Blase beim Austausch (Drift)?
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from boerdi.domain.stream_preview import VorschauStrom
from boerdi.obs.progress import TurnProgress

logger = logging.getLogger(__name__)


def _flach(text: str) -> str:
    """Leerraum zählt für die Drift nicht — Umbrüche richtet die Endverarbeitung."""
    return " ".join((text or "").split())


class TokenStrom:
    """Taktet den Vorschautext einer Antwortrunde in ``text_delta``-Ereignisse."""

    def __init__(self, progress: TurnProgress, *, takt_s: float = 0.05,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self._progress = progress
        self._takt_s = takt_s
        self._uhr = uhr
        self._start = uhr()
        self._vorschau: VorschauStrom | None = None
        self._grund: str | None = None
        self._muster = ""
        self._roh = ""     # Rohstücke seit der letzten Rechnung
        self._puffer = ""  # fertiger, noch nicht gesendeter Vorschautext
        self._pos = 0
        self._zuletzt: float | None = None  # letzte Rechnung — der Takt
        self._erstes_ms: int | None = None
        self._rahmen = 0

    def oeffnen(self, umformen: Callable[[str], str], *, muster: str = "") -> None:
        """Der Zug streamt; ``umformen`` ist die Umformung der Endverarbeitung."""
        self._vorschau = VorschauStrom(umformen)
        self._grund = None
        self._muster = muster

    def sperren(self, grund: str, *, muster: str = "") -> None:
        """Der Zug streamt nicht — ``grund`` erscheint in der Logzeile."""
        self._vorschau = None
        self._grund = grund
        self._muster = muster

    def __call__(self, stueck: str) -> None:
        """Das ``on_token``-Protokoll: ein Stück des rohen Antworttexts.

        Gerechnet wird höchstens einmal je Takt (Review L4): die Umformung läuft
        über den ganzen bisherigen Text, je Stück kostete sie bei langen
        Antworten spürbar Zeit auf der Ereignisschleife.
        """
        if self._vorschau is None:
            return
        self._roh += stueck
        jetzt = self._uhr()
        if self._zuletzt is not None and jetzt - self._zuletzt < self._takt_s:
            return
        self._zuletzt = jetzt
        self._puffer += self._vorschau.weiter(self._roh)
        self._roh = ""
        if self._puffer:
            self._senden(jetzt)

    def schliessen(self) -> None:
        """Den Rest senden — am Ende ist nichts mehr offen."""
        if self._vorschau is None:
            return
        self._puffer += self._vorschau.weiter(self._roh)
        self._roh = ""
        self._puffer += self._vorschau.ende()
        if self._puffer:
            self._senden(self._uhr())

    def _senden(self, jetzt: float) -> None:
        self._progress.text(self._puffer, self._pos)
        if self._erstes_ms is None:
            self._erstes_ms = int((jetzt - self._start) * 1000)
        self._pos += len(self._puffer)
        self._puffer = ""
        self._rahmen += 1

    @property
    def gesendet(self) -> str:
        """Was tatsächlich hinausging (ohne den noch gepufferten Rest)."""
        return self._vorschau.gesendet[:self._pos] if self._vorschau else ""

    def abschluss(self, endtext: str) -> dict[str, Any]:
        """Kennzahlen des Zugs und die Logzeile; ``endtext`` ist ``result.content``.

        Drift heißt: die fertige Antwort beginnt nicht mit dem Gesendeten — der
        Austausch am Ende ist sichtbar (Plan §9, A2).
        """
        if self._vorschau is None:
            if self._grund is not None:
                logger.info("Token-Strom: gesperrt (%s) muster=%s", self._grund, self._muster)
                return {"gesperrt": self._grund, "muster": self._muster}
            return {"gesperrt": "nicht_geoeffnet"}
        kennzahlen = {
            "muster": self._muster,
            "rahmen": self._rahmen,
            "zeichen": self._pos,
            "erstes_ms": self._erstes_ms,
            "rueckschritte": self._vorschau.rueckschritte,
            "drift": not _flach(endtext).startswith(_flach(self.gesendet)),
        }
        logger.info(
            "Token-Strom: muster=%s rahmen=%d zeichen=%d erstes=%sms rueckschritte=%d drift=%s",
            self._muster, self._rahmen, self._pos, self._erstes_ms,
            kennzahlen["rueckschritte"], "ja" if kennzahlen["drift"] else "nein")
        return kennzahlen
