"""Die E1-Wall für die Agent-Schleife (A2) — wer darf wann bestätigen.

Die kuratierenden MCP-Werkzeuge sind zweistufig: ohne ``confirmToken`` liefern
sie nur die Vorschau der Änderung, erst der zweite Aufruf mit dem Schlüssel
führt aus. Der Server nimmt an, zwischen beiden Schritten stehe ein Mensch
(``domain/write_confirm.py`` erklärt die Bindung im Detail).

**Im Chat setzt der Bestand den Menschen am Zugwechsel wieder ein.** Diese
Schleife hat keine Züge — sie läuft in einem Stück durch. Es gibt hier also
keine Zeitgrenze, hinter der ein Mensch stünde. Deshalb zwei Betriebsarten, und
die Vorgabe entscheidet sich für das Nichtstun:

``propose`` (Vorgabe)
    Es wird **nie** ein Schlüssel eingesetzt. Kuratierende Werkzeuge kommen bis
    zur Vorschau und keinen Schritt weiter; das Ergebnis ist ein Vorschlag, den
    ein Mensch andernorts annimmt. Nichts, was schreibt, schreibt von selbst.

``execute``
    Die Bestätigung darf im selben Lauf fallen. Das ist die bewusste
    Entscheidung eines Gastgebers, der eine angemeldete Person mit
    WLO-Rechten vor sich hat (App-Einbettung, Browser-Plugin) — dort ist der
    Mensch nicht *zwischen* den Schritten, sondern *vor* dem Lauf. Wer diese
    Betriebsart wählt, übernimmt genau diese Verantwortung.

**Regel 1 gilt in beiden Betriebsarten und ist die eigentliche Zusicherung:**
das Modell setzt nie selbst einen Schlüssel (Hinweg, :func:`strip_confirm_token`)
und sieht nie einen (Rückweg, :func:`redact_confirm_token`). Was ``execute``
ändert, ist allein, *wer* den Schlüssel einsetzen darf — wir, für dasselbe
Vorhaben, im selben Lauf.

Eine Instanz je Lauf, kein Modul-Zustand: der offene Vorgang gehört dem Lauf,
und zwei gleichzeitige Läufe dürfen sich ihre Schlüssel nicht teilen.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from boerdi.domain.config_models.engine import AgentLimits
from boerdi.domain.write_confirm import (
    extract_confirm_token,
    is_confirmable,
    redact_confirm_token,
    remember_pending,
    strip_confirm_token,
    token_for,
)
from boerdi.services.mcp.auth import has_personal_auth

logger = logging.getLogger(__name__)


def enforce_write_mode(
    vorgabe: AgentLimits, wunsch: str | None = None
) -> AgentLimits:
    """Die Betriebsart dieses Laufs — Konfiguration, wahlweise verschoben.

    **Die Prüfung sitzt am Ergebnis und nicht an der Übersteuerung.** Fragte sie
    nur ``wunsch`` ab, wäre ein redaktionell in ``01-base/engine`` gesetztes
    ``execute`` ein Loch: es käme ungeprüft durch, für jeden Aufrufer. So
    verlangt ``execute`` immer eine angemeldete Person, egal woher es kommt.

    Seit A4c-2b hier statt in ``agent_run``: mit dem Agent-Modus im Chat kam ein
    zweiter Aufrufer dazu, und eine Sicherheitsregel in zwei Fassungen ist eine
    Fassung zu viel. ``wunsch`` ist die Übersteuerung des Aufrufers
    (``AgentRequest.write_mode``); der Chat-Zug hat keine und reicht nichts
    herein.
    """
    gewuenscht = wunsch or vorgabe.write_mode
    if gewuenscht == "execute" and not has_personal_auth():
        logger.warning(
            "Agent-Lauf: write_mode=execute ohne persoenliche Anmeldung — der "
            "Lauf bleibt bei propose (nur Vorschau).")
        gewuenscht = "propose"
    if gewuenscht == vorgabe.write_mode:
        return vorgabe
    return vorgabe.model_copy(update={"write_mode": gewuenscht})


class WriteGate:
    """Entscheidet je Aufruf, welcher Schlüssel mitfährt — und ob überhaupt."""

    def __init__(self, mode: str, *, now: Callable[[], float] = time.time) -> None:
        self._execute = mode == "execute"
        self._now = now
        self._pending: dict[str, Any] | None = None

    def prepare(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Die Argumente, wie sie abgesetzt werden dürfen.

        Werkzeuge außerhalb der kuratierenden Oberfläche gehen unverändert
        durch — dort ist ``confirmToken`` ein gewöhnlicher Name ohne Bedeutung.
        """
        if not is_confirmable(tool_name):
            return args
        sauber = strip_confirm_token(tool_name, args)
        if not self._execute:
            return sauber
        schluessel = token_for(self._pending, tool_name, sauber, now=self._now())
        if not schluessel:
            return sauber
        # Ein Schlüssel gilt genau einmal; der Merkposten ist damit verbraucht.
        self._pending = None
        logger.info("Agent-Schleife: bestätige %s im selben Lauf (write_mode=execute)",
                    tool_name)
        return {**sauber, "confirmToken": schluessel}

    def observe(self, tool_name: str, args: dict[str, Any], result_text: str) -> str:
        """Das Ergebnis, wie es das Modell sehen darf — und was wir uns merken.

        Redigiert wird **zuerst**: danach kann kein Pfad mehr den rohen Text
        weiterreichen. In ``propose`` wird nichts gemerkt, weil es dort nichts
        einzulösen gibt; der Schlüssel verfällt beim Server.
        """
        if not is_confirmable(tool_name):
            return result_text
        gepraegt = extract_confirm_token(result_text)
        text = redact_confirm_token(result_text)
        if gepraegt and self._execute:
            self._pending = remember_pending(tool_name, args, gepraegt, now=self._now())
        elif not gepraegt and "confirmToken:" in text:
            # Der Server kündigt einen Schlüssel an, wir lesen keinen heraus:
            # sein Vorschautext hat sich geändert. Die Folge ist ein Ausfall,
            # kein Loch — der Hinweg trägt die Zusicherung —, aber ein stiller
            # Ausfall wäre der schlechtere von beiden.
            logger.warning(
                "Vorschautext von %s nennt confirmToken, enthält aber keinen "
                "lesbaren Schlüssel — Bestätigung nicht möglich", tool_name)
        return text
