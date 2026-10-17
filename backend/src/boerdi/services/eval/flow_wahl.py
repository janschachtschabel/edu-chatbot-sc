"""Welche Gold-Flows ein Lauf fährt (aus ``golden_run`` gelöst, Paket 7, K3).

Ohne Auswahl laufen alle Flows — außer denen mit ``auf_abruf: true``: GV-RED-1
nimmt real Inhalte auf Staging auf und läuft nur noch, wenn man ihn ausdrücklich
wählt (Nutzer-Entscheid 2026-10-09). Die Kommandozeile ``evals/run_golden.py``
ist framework-frei und trägt dieselbe Regel als Zwilling (``flows_fuer_lauf``).
"""

from __future__ import annotations

from typing import Any


def flows_waehlen(
    alle: list[dict[str, Any]], flow_ids: list[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """(Flows des Laufs, Warnungen). Gewählte Kennungen laufen in der Reihenfolge
    der Gold-Flows; unbekannte werden gemeldet und übergangen."""
    if not flow_ids:
        return [f for f in alle if not f.get("auf_abruf")], []
    gewuenscht = set(flow_ids)
    unbekannt = sorted(gewuenscht - {str(f.get("id")) for f in alle})
    warnungen = [f"Unbekannte Flow-IDs ignoriert: {unbekannt}"] if unbekannt else []
    return [f for f in alle if str(f.get("id")) in gewuenscht], warnungen
