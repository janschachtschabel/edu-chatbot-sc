"""Studio-Schalter der UI-Module: „aktiv“ und „für den Agenten“ (Paket U1-f, Plan §16).

- **aktiv = aus** (``display_rules.ui_module.aus``): neue Antworten zeigen das Modul nicht — kein
  Werkzeug (Agent- und Muster-Modus), kein abgeleiteter Block, keine Direktaktion, die es baut.
  Gespeicherte Blöcke im Verlauf bleiben, wie sie gezeigt wurden.
- **für den Agenten = aus** (``agent_aus``): nur der Agent-Modus bietet es nicht an; ein Muster,
  das es unter ``tools:`` nennt, weiter (U-F4).
- **fest** (``namen.FEST``, der Inhaltsrahmen): beide Schalter gelten nicht.

Gelesen bei jedem Aufruf über den Lader (Cache des Speichers) — eine Änderung im Studio wirkt ab
dem nächsten Zug, ohne Neustart.
"""

from __future__ import annotations

from boerdi.ui_module import katalog
from boerdi.ui_module.namen import ABGELEITETE, FEST, INHALTSRAHMEN


def _gelesen() -> dict[str, frozenset[str]]:
    from boerdi.services.config_loader import load_ui_modul_schalter

    return load_ui_modul_schalter()


def aktiv(name: str) -> bool:
    """Darf das Modul in neuen Antworten erscheinen?"""
    return name in FEST or name not in _gelesen()["aus"]


def fuer_agent(name: str) -> bool:
    """Darf der Agent das Modul als Werkzeug bekommen? (aktiv und nicht ``agent_aus``)"""
    if name in FEST:
        return True
    gelesen = _gelesen()
    return name not in gelesen["aus"] and name not in gelesen["agent_aus"]


def schaltbar(name: str) -> dict[str, bool]:
    """Welche Schalter das Studio für das Modul zeigt. ``agent`` nur bei einem eigenen
    Modul-Werkzeug (``agent: true``, kein Inhaltsrahmen, nicht abgeleitet)."""
    if name in FEST:
        return {"aktiv": False, "agent": False}
    manifest = katalog.katalog().get(name) or {}
    eigenes_werkzeug = bool(manifest.get("agent")) and name not in (INHALTSRAHMEN, *ABGELEITETE)
    return {"aktiv": True, "agent": eigenes_werkzeug}
