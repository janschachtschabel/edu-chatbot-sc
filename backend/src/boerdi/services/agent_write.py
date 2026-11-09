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
    CONFIRM_TOKEN_FIELD,
    PLAN_ZU_GROSS_TEXT,
    extract_confirm_token,
    is_confirmable,
    is_plan,
    plan_zu_gross,
    redact_confirm_token,
    remember_pending,
    strip_confirm_token,
    token_for,
)
from boerdi.services.mcp.auth import aufrufer_kennung, has_personal_auth
from boerdi.services.mcp.client import ausgelastet_ohne_aufruf, is_mcp_error, nimm_bestaetigung

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
        #: Die redigierte Vorschau zum offenen Vorgang — für die Box im Chat-Zug.
        self._vorschau = ""
        #: Der eben eingelöste Merkposten — kommt zurück, wenn der Aufruf nie hinausging
        #: (ausgelastet ohne Code; :meth:`observe`).
        self._eingeloest: tuple[dict[str, Any], str] | None = None

    def prepare(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Die Argumente, wie sie abgesetzt werden dürfen.

        Werkzeuge außerhalb der kuratierenden Oberfläche gehen unverändert
        durch — dort ist ``confirmToken`` ein gewöhnlicher Name ohne Bedeutung.
        """
        if not is_confirmable(tool_name):
            return args
        sauber = strip_confirm_token(tool_name, args)
        # Paket M5 (Re-Review, Befund 1): einen Plan löst nur der Vorlauf ein (Fortsetzen).
        if not self._execute or is_plan(tool_name):
            return sauber
        schluessel = token_for(self._pending, tool_name, sauber, now=self._now())
        if not schluessel:
            return sauber
        # Ein Schlüssel gilt genau einmal; der Merkposten ist damit verbraucht.
        self._eingeloest = (self._pending, self._vorschau) if self._pending else None
        self._pending = None
        self._vorschau = ""
        logger.info("Agent-Schleife: bestätige %s im selben Lauf (write_mode=execute)",
                    tool_name)
        return {**sauber, "confirmToken": schluessel}

    def observe(self, tool_name: str, args: dict[str, Any], result_text: str) -> str:
        """Das Ergebnis, wie es das Modell sehen darf — und was wir uns merken.

        Redigiert wird **zuerst**: danach kann kein Pfad mehr den rohen Text
        weiterreichen. Gemerkt wird in **beiden** Betriebsarten (Paket 2): in
        ``execute`` löst die Schleife selbst ein (:meth:`prepare`), in
        ``propose`` nimmt die Person im nächsten Zug an — dafür reicht
        :meth:`offene_abnahme` den Vorgang hinaus. ``prepare`` setzt in
        ``propose`` trotzdem nie einen Schlüssel ein.
        """
        if not is_confirmable(tool_name):
            return result_text
        eingeloest, self._eingeloest = self._eingeloest, None
        if (eingeloest is not None and CONFIRM_TOKEN_FIELD in args
                and ausgelastet_ohne_aufruf(result_text)):
            # Der Aufruf ging nie hinaus — die Freigabe gilt weiter (im Chat liegt sie ebenso
            # wieder bereit, ``write_approval._liegen_lassen``). Ein zweiter gleicher Aufruf im
            # selben Lauf endet am Stillstands-Wächter der Schleife.
            self._pending, self._vorschau = eingeloest
            logger.info("Agent-Schleife: %s ausgelastet — Freigabe bleibt", tool_name)
            return redact_confirm_token(result_text)
        # Paket M2: der Schlüssel aus ``structuredContent.confirm``, der Text ist Rückfall.
        # Aus einer Fehlermeldung nie (Review M2, Befund 7: fremder Titel darin).
        gepraegt = nimm_bestaetigung(tool_name, args)
        if gepraegt is None and not is_mcp_error(result_text):
            gepraegt = extract_confirm_token(result_text)
        text = redact_confirm_token(result_text)
        if gepraegt:
            merk = remember_pending(
                tool_name, args, gepraegt, now=self._now(), caller=aufrufer_kennung())
            if plan_zu_gross(merk):
                # Paket K2d-3 (Review, Befund 2): nie bestätigbar — das Modell teilt auf.
                return PLAN_ZU_GROSS_TEXT
            # Die letzte Vorschau gewinnt: ein neuer Schlüssel ersetzt den alten.
            self._pending = merk
            self._vorschau = text
        elif "confirmToken:" in text:
            # Der Server kündigt einen Schlüssel an, wir lesen keinen heraus:
            # sein Vorschautext hat sich geändert. Die Folge ist ein Ausfall,
            # kein Loch — der Hinweg trägt die Zusicherung —, aber ein stiller
            # Ausfall wäre der schlechtere von beiden.
            logger.warning(
                "Vorschautext von %s nennt confirmToken, enthält aber keinen "
                "lesbaren Schlüssel — Bestätigung nicht möglich", tool_name)
        return text

    def offene_abnahme(self) -> tuple[dict[str, Any], str] | None:
        """Der nicht eingelöste Vorgang samt redigierter Vorschau — oder ``None``.

        Der Merkposten trägt den Schlüssel: er gehört in die Sitzung
        (``entities``), nie in die Kette des Modells. Eingelöst heißt verbraucht.
        """
        if self._pending is None:
            return None
        return self._pending, self._vorschau
