"""Paket R1 (Plan 2026-11-12): Argumente eines ``auftrag``-Schritts — Teilaufträge und die Sprache.

- **Teilaufträge** (R-E13, N14): ``aufteilen: {argument, hoechstens}`` schneidet die Liste in
  ``argument`` in Stücke. Der Treiber startet sie nacheinander; der **Stapel** im Lauf
  (``lauf["auftrag_teile"]``) hält die eingefrorenen Argumente, zählt mit und sammelt die
  Ergebnisse (gedeckelt). Nach dem letzten Stück wird daraus EIN Ergebnis — der Teil ``schreibt``
  wie bei einem einzelnen Auftrag; Listen gleicher Schlüssel hängen aneinander.
- **Sprache** (R-E14): ``{"$sprache": true}`` als Wert eines Arguments wird die Sprache der Person
  (``de``/``en``) — ein Flow schreibt Metadaten sonst immer deutsch.
"""

from __future__ import annotations

import json
import math
from typing import Any, Final

#: Höchstens so viele Teilaufträge je Schritt — die B-API erlaubt 20 laufende Jobs je Schlüssel,
#: und je Teil braucht es ein „Stand prüfen“. Bei mehr werden die Teile größer.
MAX_TEILE: Final = 20
#: Der Schlüssel des Stapels im Lauf.
STAPEL: Final = "auftrag_teile"
SPRACHE: Final = "$sprache"
#: Review R1, Befund 3: so viele Bytes Teilergebnisse höchstens im Lauf (``akte.lauf`` liest jeder
#: Zug); darüber zählt ein Teil nur noch (``gekuerzt``).
MAX_STAPEL_BYTES: Final = 128 * 1024
#: Review R1, Befund 1: so groß dürfen die eingefrorenen Argumente höchstens sein — sonst wird nicht
#: aufgeteilt (der Schritt geht zu ``bei_fehler``). 200 Node-IDs brauchen rund 8 KB.
MAX_ARGS_BYTES: Final = 64 * 1024
MAX_DATEIEN: Final = 200


def ist_sprache(wert: Any) -> bool:
    return isinstance(wert, dict) and wert == {SPRACHE: True}


def sprache_einsetzen(args: dict[str, Any], sprache: str) -> dict[str, Any]:
    """``args`` mit der Sprache der Person statt ``{"$sprache": true}`` (oberste Ebene)."""
    return {k: (sprache if ist_sprache(v) else v) for k, v in args.items()}


def teilen(args: dict[str, Any], argument: str, hoechstens: int) -> list[dict[str, Any]]:
    """Die Argumente je Teilauftrag. Ist ``argument`` keine Liste oder kurz genug: ein Auftrag."""
    liste = args.get(argument)
    if not isinstance(liste, list) or len(liste) <= hoechstens:
        return [args]
    groesse = max(hoechstens, math.ceil(len(liste) / MAX_TEILE))
    return [{**args, argument: liste[i:i + groesse]} for i in range(0, len(liste), groesse)]


def _bytes(wert: Any) -> int:
    return len(json.dumps(wert, ensure_ascii=False, default=str).encode())


def neuer_stapel(args: dict[str, Any], n: int) -> dict[str, Any] | None:
    """Der Stapel für ``n`` Teile. Review R1, Befund 1: die eingesetzten Argumente (Liste und
    Sprache) werden beim ersten Teil **eingefroren** — ändert sich die Ablage während des Wartens,
    bleibt der Schnitt derselbe (sonst fielen IDs weg oder gingen doppelt an einen schreibenden
    Flow). ``None``: die Argumente sind zu groß für den Lauf (:data:`MAX_ARGS_BYTES`)."""
    if _bytes(args) > MAX_ARGS_BYTES:
        return None
    return {"n": n, "i": 0, "args": args, "ergebnisse": [], "bytes": 0, "gescheitert": 0,
            "gekuerzt": 0}


def ist_stapel(wert: Any) -> bool:
    return (isinstance(wert, dict) and isinstance(wert.get("n"), int)
            and isinstance(wert.get("i"), int) and isinstance(wert.get("ergebnisse"), list)
            and isinstance(wert.get("args"), dict))


def stueck(stapel: dict[str, Any], argument: str, hoechstens: int, i: int) -> dict[str, Any] | None:
    """Die Argumente des Teils ``i`` aus den eingefrorenen — ``None``, wenn es ihn nicht gibt."""
    stuecke = teilen(stapel["args"], argument, hoechstens)
    return stuecke[i] if 0 <= i < len(stuecke) else None


def mit_ergebnis(stapel: dict[str, Any], ergebnis: dict[str, Any] | None) -> dict[str, Any]:
    """Der Stapel nach dem Ergebnis des laufenden Teils (``None``: gescheitert). Review R1,
    Befund 3: der Lauf wird je Zug gelesen — über :data:`MAX_STAPEL_BYTES` hinaus zählt ein
    gelungener Teil nur noch (``gekuerzt``), seine Ausgaben bleiben weg."""
    neu = {**stapel, "ergebnisse": list(stapel["ergebnisse"])}
    if ergebnis is None:
        neu["gescheitert"] = int(stapel.get("gescheitert") or 0) + 1
        return neu
    outputs = ergebnis.get("outputs") or {}
    groesse = _bytes(outputs)
    if int(stapel.get("bytes") or 0) + groesse > MAX_STAPEL_BYTES:
        neu["gekuerzt"] = int(stapel.get("gekuerzt") or 0) + 1
    else:
        neu["ergebnisse"].append(outputs)
        neu["bytes"] = int(stapel.get("bytes") or 0) + groesse
    if ergebnis.get("warnungen"):
        neu["warnungen"] = True
    if ergebnis.get("dateien"):
        neu["dateien"] = [*(stapel.get("dateien") or []), *ergebnis["dateien"]][:MAX_DATEIEN]
    return neu


def _vereinen(ergebnisse: list[dict[str, Any]]) -> dict[str, Any]:
    """Review R1, Befund 4: Listen unter demselben Schlüssel hängen aneinander (etwa ``report``
    je Datei) — ein Bericht nur des letzten Teils hielte man für den ganzen Lauf. Sonst gilt der
    Wert des letzten Teils."""
    gesamt: dict[str, Any] = {}
    for outputs in ergebnisse:
        for k, v in outputs.items():
            bisher = gesamt.get(k)
            gesamt[k] = [*bisher, *v] if isinstance(bisher, list) and isinstance(v, list) else v
    return gesamt


def zusammenfuehren(stapel: dict[str, Any], *, nicht_gestartet: int = 0) -> dict[str, Any] | None:
    """Das eine Ergebnis aller Teile — ``None``, wenn keiner gelang (dann ``bei_fehler``). Ein
    gescheiterter, nicht gestarteter oder gekürzter Teil ist ein Teilerfolg (``warnungen``, wie
    beim Job-Vertrag 2026-11-07)."""
    gekuerzt = int(stapel.get("gekuerzt") or 0)
    if not stapel["ergebnisse"] and not gekuerzt:
        return None
    gescheitert = int(stapel.get("gescheitert") or 0) + nicht_gestartet
    gesamt: dict[str, Any] = {"outputs": _vereinen(stapel["ergebnisse"]),
                              "dateien": stapel.get("dateien") or [], "teile": stapel["n"]}
    if gescheitert:
        gesamt["gescheitert"] = gescheitert
    if gekuerzt:
        gesamt["gekuerzt"] = gekuerzt
    if gescheitert or gekuerzt or stapel.get("warnungen"):
        gesamt["warnungen"] = True
    return gesamt
