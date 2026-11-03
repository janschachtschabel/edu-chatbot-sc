"""Studio-Schalter der UI-Module (Paket U1-f, Plan §16 F-1).

Gespeichert in ``01-base/display-rules`` unter ``display_rules.ui_module``, gelesen aber hier und
nicht in ``load_display_rules_config``: dessen kuratiertes Ergebnis reist in jeder Antwort mit
(``display_rules``), die Schalter sind Betriebswissen des Studios.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def _namen(roh: Any) -> frozenset[str]:
    """Nur eine Liste von Texten zählt — Bestand am Validator vorbei (Rohtext, alte Sicherung)
    bricht keine Antwort, er schaltet nur nichts ab."""
    if not isinstance(roh, list):
        return frozenset()
    return frozenset(n.strip() for n in roh if isinstance(n, str) and n.strip())


def load_ui_modul_schalter() -> dict[str, frozenset[str]]:
    """``{"aus": …, "agent_aus": …}`` — die abgeschalteten Modulnamen; leer = alle an."""
    regeln = area("01-base/display-rules").get("display_rules")
    roh = regeln.get("ui_module") if isinstance(regeln, dict) else None
    roh = roh if isinstance(roh, dict) else {}
    return {"aus": _namen(roh.get("aus")), "agent_aus": _namen(roh.get("agent_aus"))}
