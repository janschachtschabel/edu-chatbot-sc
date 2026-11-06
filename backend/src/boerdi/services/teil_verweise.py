"""Teile des Vorgangs in Werkzeug-Argumenten (Paket V2, Plan 2026-11-05 §3).

Die KI kann einem Werkzeug Daten aus dem Arbeitsstand geben, ohne sie zu kennen: statt des Werts
schreibt sie ``{"$teil": "<name>"}`` (die Namen stehen in der Kennzeile ``[ARBEITSSTAND …]``). Das
Backend setzt den Wert **vor** Schreibsperre und Vorschau ein — die Person sieht, was wirklich
geschrieben würde, und der Fingerabdruck der Abnahme deckt den eingesetzten Wert, nicht den Namen.

Nur die reine Form ``{"$teil": "<name>"}`` (ein Schlüssel, Name nach :data:`NAME`)
**unterhalb** der obersten Ebene ist ein Verweis; alles andere bleibt, wie es ist. Fehlt ein Teil
(kein Vorgang, kein solcher Teil), wird das Werkzeug nicht gerufen (:func:`fehlertext`).
Verschachtelung über :data:`TIEFE` wird nicht durchsucht. Eingesetzt wird eine Kopie — ein Werkzeug,
das seine Argumente ändert, ändert nie die Akte.

**Wer einen Teil bekommt** (Review V2, Befund 1): nur ein Ziel nach :func:`darf` — ein kuratierendes
WLO-Werkzeug mit Vorschau und Abnahme (die Person sieht und bestätigt den Wert) oder ein UI-Modul,
dessen Manifest den Teil unter ``vorgang.liest`` nennt. Lesende Werkzeuge, auch die fremder
MCP-Server, bekommen nie einen Teil: ein Prompt-Injection-Treffer könnte sonst Ordner- und
Dokumentnamen ohne Zustimmung hinausschicken.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, Final

SCHLUESSEL: Final = "$teil"
NAME: Final = re.compile(r"^[a-z][a-z0-9_]{1,29}$")
TIEFE: Final = 6

TeilLader = Callable[[str], Awaitable[Any]]


def _verweis(wert: Any) -> str | None:
    if isinstance(wert, dict) and len(wert) == 1 and isinstance(wert.get(SCHLUESSEL), str):
        return wert[SCHLUESSEL]
    return None


def _hat_verweis(wert: Any, tiefe: int = 0) -> bool:
    if tiefe > TIEFE:
        return False
    if _verweis(wert) is not None:
        return True
    if isinstance(wert, dict):
        return any(_hat_verweis(v, tiefe + 1) for v in wert.values())
    if isinstance(wert, list):
        return any(_hat_verweis(v, tiefe + 1) for v in wert)
    return False


def darf(werkzeug: str, teil: str) -> bool:
    """Darf ``werkzeug`` den Teil ``teil`` bekommen? (siehe Modulkopf)"""
    from boerdi.domain.write_confirm import is_confirmable
    from boerdi.ui_module import katalog

    if is_confirmable(werkzeug):
        return True
    manifest = katalog.katalog().get(werkzeug) or {}
    return teil in ((manifest.get("vorgang") or {}).get("liest") or [])


#: Größter Teil, der an ein Werkzeug der KI geht (als JSON, Bytes).
MAX_BYTES: Final = 64_000


def _zu_gross(inhalt: Any) -> bool:
    return len(json.dumps(inhalt, ensure_ascii=False, default=str).encode()) > MAX_BYTES


async def einsetzen(args: dict[str, Any], teile: TeilLader | None, werkzeug: str | None = None
                    ) -> tuple[dict[str, Any], list[str]]:
    """``args`` mit eingesetzten Teilen und die Namen, die fehlten oder ``werkzeug`` nicht bekommen
    darf (:func:`darf`; ohne ``werkzeug`` keine Prüfung — für den Treiber eines geprüften Ablaufs).
    Ohne Verweis dasselbe Objekt."""
    if not isinstance(args, dict) or not any(_hat_verweis(v, 1) for v in args.values()):
        return args, []
    fehlt: list[str] = []

    async def ersetze(wert: Any, tiefe: int) -> Any:
        if tiefe > TIEFE:
            return wert
        if tiefe > 0 and (name := _verweis(wert)) is not None:
            erlaubt = werkzeug is None or darf(werkzeug, name)
            inhalt = (await teile(name) if erlaubt and teile is not None and NAME.match(name)
                      else None)
            # Querschnitts-Review 2026-11-06: an ein Werkzeug höchstens ``MAX_BYTES`` — ein
            # Auftragsergebnis (bis 1 MB) läge sonst im Abnahme-Merkposten der Sitzung und käme mit
            # der Vorschau zurück ans Modell. Das gilt auch für einen WLO-Werkzeug-Schritt eines
            # Ablaufs (der Treiber nennt sein Ziel); ohne ``werkzeug`` (Dienst-, Auftrags- und
            # Modul-Schritte des Treibers) geht der ganze Teil (Review Q3, Befund 13).
            if inhalt is None or (werkzeug is not None and _zu_gross(inhalt)):
                fehlt.append(name)
                return wert
            return copy.deepcopy(inhalt)
        if isinstance(wert, dict):
            return {k: await ersetze(v, tiefe + 1) for k, v in wert.items()}
        if isinstance(wert, list):
            return [await ersetze(v, tiefe + 1) for v in wert]
        return wert

    neu = await ersetze(args, 0)
    return neu, fehlt


def fehlertext(fehlt: list[str]) -> str:
    namen = ", ".join(sorted(set(fehlt)))[:200]
    return (f"Fehler: {namen} ist im Arbeitsstand nicht vorhanden, für dieses Werkzeug nicht "
            "freigegeben oder zu groß dafür. Rufe es nicht mit diesem Verweis; Teile bekommen nur "
            "Werkzeuge mit Vorschau und Module, die sie lesen.")
