"""Die Spur der Agent-Schleife (AG-1, Plan 2026-09-26 §8).

Bis hier kannte ein Zug nur Summen: Runden, Ende-Grund, echte Werkzeuge. Welche
Runde was gerufen hat, wie lange sie lief und was sie gekostet hat, ging
verloren — und die virtuellen Werkzeuge (``zeige_dokument``,
``liefere_ergebnis`` …) tauchten nirgends auf, weil ``AgentRun.tools_called``
bewusst nur die echten führt.

**Nur die Namen der Argumente.** Die Werte können Nutzerinhalt tragen (eine
Suchanfrage, ein Dokumenttitel mit Namen) oder einen Bestätigungs-Schlüssel,
und der Debug-Block ist über ``GET /api/sessions/{id}/messages`` für jeden
lesbar, der die Sitzungskennung hat. Dieselbe Linie wie bei den
Fortschritts-Ereignissen der Schleife.

Getrennt von ``agent_loop``, weil es ein anderer Grund zur Änderung ist: dort
steht, wann ein Lauf endet, hier nur, was davon festgehalten wird.
"""

from __future__ import annotations

import copy
from typing import Any

from boerdi.api.schemas import TraceEntry


def _stand(acc: dict[str, Any]) -> tuple[int, int, int]:
    """Zählerstand (Prompt, davon gecacht, Ausgabe) des Zug-Zählers."""
    return (int(acc.get("prompt_tokens", 0)), int(acc.get("cached_tokens", 0)),
            int(acc.get("completion_tokens", 0)))


class Rundenbuch:
    """Führt die Runden eines Laufs in ``runden`` (= ``AgentRun.runden``).

    Eine Runde endet, wenn die nächste beginnt oder der Lauf endet. Die Token
    einer Runde sind die Differenz des Zug-Zählers — alles, was in ihr gebucht
    wurde, auch eine Wissenssuche, und nichts aus früheren Schritten des Zugs.
    """

    def __init__(self, runden: list[dict[str, Any]], acc: dict[str, Any]) -> None:
        self._runden = runden
        self._acc = acc
        self._offen: dict[str, Any] | None = None
        self._beginn = 0.0
        self._stand = (0, 0, 0)

    def beginnen(self, nummer: int, jetzt: float) -> None:
        self.schliessen(jetzt)
        self._offen = {"runde": nummer, "werkzeuge": []}
        self._runden.append(self._offen)
        self._beginn, self._stand = jetzt, _stand(self._acc)

    def aufruf(self, name: str, args: dict[str, Any]) -> None:
        """Ein Aufruf des Modells — auch ein virtueller oder ein unlesbarer."""
        if self._offen is not None:
            self._offen["werkzeuge"].append({"name": name, "argumente": sorted(args)})

    def schliessen(self, jetzt: float) -> None:
        """Die offene Runde abschließen; ohne offene Runde ohne Wirkung."""
        if self._offen is None:
            return
        vorher, nachher = self._stand, _stand(self._acc)
        self._offen["dauer_ms"] = max(0, round((jetzt - self._beginn) * 1000))
        self._offen["prompt_tokens"] = nachher[0] - vorher[0]
        self._offen["cached_tokens"] = nachher[1] - vorher[1]
        self._offen["completion_tokens"] = nachher[2] - vorher[2]
        self._offen = None


def spur(runden: list[dict[str, Any]], stop_reason: str) -> list[TraceEntry]:
    """Die Runden als ``TraceEntry``-Zeilen des Debug-Blocks.

    Je Runde ``agent_round``, zum Schluss ``agent_stop`` mit Ende-Grund und
    Rundenzahl. Das Debug-Panel des Widgets zeigt Beschriftung und Dauer schon
    heute an; die Zahlen stehen vollstaendig in ``data``. Die Zeilen tragen
    Kopien, damit eine Nachbearbeitung der Spur den Lauf nicht mitveraendert.
    """
    zeilen = []
    for runde in runden:
        namen = ", ".join(w["name"] for w in runde["werkzeuge"]) or "ohne Werkzeug"
        zeilen.append(TraceEntry(
            step="agent_round", label=f"Runde {runde['runde']}: {namen}",
            duration_ms=runde.get("dauer_ms", 0), data=copy.deepcopy(runde)))
    zeilen.append(TraceEntry(
        step="agent_stop", label=f"Ende: {stop_reason}",
        duration_ms=sum(r.get("dauer_ms", 0) for r in runden),
        data={"stop_reason": stop_reason, "runden": len(runden)}))
    return zeilen
