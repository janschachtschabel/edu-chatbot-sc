"""Fingerabdruck von Konfiguration und Golden-Abläufen eines Laufs (Paket 13, A3).

Rein und ohne Datenbank: der Aufrufer reicht die Bereiche (``ConfigStore.fassungen``) und die
Werksfassung (``seed_sync.seed_lesen``). Der Abdruck sagt je Bereich Version, Inhalts-Prüfsumme
und Stand gegen die Werksfassung — genug, um im Vergleich zweier Läufe die geänderten Bereiche
zu nennen, ohne Inhalte in jeden Lauf zu kopieren.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from boerdi.services import werkfassung

#: Länge der gekürzten Prüfsummen — 48 Bit reichen, um Fassungen zu unterscheiden.
KURZ = 12


def kurz(daten: Any) -> str:
    """Gekürzte SHA-256 über kanonisches JSON (unabhängig von der Schlüssel-Reihenfolge)."""
    return werkfassung.pruefsumme(daten)[:KURZ]


def konfig_fingerprint(
    zeilen: Iterable[Mapping[str, Any]], *, werk: Mapping[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """``{"hash": <gesamt>, "bereiche": {area: {"version", "hash", "stand"}}}``.

    ``stand`` ist ``werkfassung.status`` gegen ``werk``; ohne Werksfassung (``None``, etwa wenn
    der Seed nicht lesbar war) bleibt er leer, statt geraten zu werden.
    """
    bereiche: dict[str, dict[str, Any]] = {}
    for zeile in zeilen:
        area = str(zeile["area"])
        data = zeile.get("data")
        stand = "" if werk is None else werkfassung.status(
            data=data, werk_hash=zeile.get("werk_hash"), werk=werk.get(area),
            entfernt=False, updated_by=str(zeile.get("updated_by") or ""))
        bereiche[area] = {"version": zeile.get("version"), "hash": kurz(data), "stand": stand}
    gesamt = kurz({area: eintrag["hash"] for area, eintrag in bereiche.items()})
    return {"hash": gesamt, "bereiche": dict(sorted(bereiche.items()))}


def gold_flows_hash(flows: Iterable[Mapping[str, Any]]) -> str:
    """Prüfsumme der ausgewählten Abläufe — ändert sich mit jedem Wort eines Testfalls."""
    return kurz(list(flows))
