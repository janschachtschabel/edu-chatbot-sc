"""Trends mit dem Judge v2 (Paket 13, D5) — rein, ohne E/A.

Reihen je Skala, Gesamt, Zug-Mittel, Latenz p50 und Kosten je Zug, dazu **Wechselmarken**: an
welchem Lauf sich gegenüber dem Lauf davor Modell, Weg, Konfiguration, Master-Skill oder ein
Prompt-Baustein änderte. Ohne Marke liest man den Sprung nach einem Modellwechsel als
Verbesserung.

Liest nur Summaries (``kennzahlen_v2`` aus ``golden.kennzahlen_des_laufs`` und
``messbedingungen``), wie die übrigen Trends ohne Transkripte. Ein Lauf ohne Wert gibt keinen
Punkt — eine Lücke statt einer 0,0, die wie ein Absturz aussähe (dieselbe Regel wie GV6).
"""

from __future__ import annotations

from typing import Any

from boerdi.services.eval import vergleich_v2

#: Reihe → Schlüssel in ``kennzahlen_v2``.
_REIHEN = {"gesamt": "gesamt_mittel", "zug_mittel": "zug_mittel",
           "latenz_p50_ms": "latenz_p50_ms", "kosten_je_zug": "kosten_je_zug"}


def _punkt(run_id: str, created_at: str | None, wert: Any) -> dict[str, Any]:
    return {"run_id": run_id, "created_at": created_at, "value": wert}


def _wechsel(vorher: dict[str, Any], nachher: dict[str, Any]) -> tuple[list[str], list[str]]:
    fa, fb = vergleich_v2.felder(vorher), vergleich_v2.felder(nachher)
    pa = (vorher.get("kennzahlen_v2") or {}).get("prompts") or {}
    pb = (nachher.get("kennzahlen_v2") or {}).get("prompts") or {}
    felder = vergleich_v2.geaenderte_felder(fa, fb)
    prompts = [art for art in sorted(pa.keys() | pb.keys()) if pa.get(art) != pb.get(art)]
    return felder, prompts if pa and pb else []


def reihen(laeufe: list[tuple[str, str | None, dict[str, Any]]]) -> dict[str, Any]:
    """Die Reihen über ``laeufe`` (Kennung, Zeitpunkt, Summary; älteste zuerst)."""
    aus: dict[str, Any] = {name: [] for name in _REIHEN}
    skalen: dict[str, list[dict[str, Any]]] = {}
    wechsel: list[dict[str, Any]] = []
    vorher: dict[str, Any] | None = None
    for run_id, created_at, summary in laeufe:
        k = summary.get("kennzahlen_v2") or {}
        for name, schluessel in _REIHEN.items():
            if k.get(schluessel) is not None:
                aus[name].append(_punkt(run_id, created_at, k[schluessel]))
        for skala, wert in (k.get("skalen_mittel") or {}).items():
            if wert is not None:
                skalen.setdefault(skala, []).append(_punkt(run_id, created_at, wert))
        # Nur Läufe mit Messbedingungen (Golden) sind Vergleichspartner — ein generativer Lauf
        # dazwischen schrieb keine und setzte sonst Marken „alles geändert“ (Review PR #18).
        if not summary.get("messbedingungen"):
            continue
        if vorher is not None:
            felder, prompts = _wechsel(vorher, summary)
            if felder or prompts:
                wechsel.append({"run_id": run_id, "created_at": created_at,
                                "felder": felder, "prompts": prompts})
        vorher = summary
    return {**aus, "skalen": skalen, "wechsel": wechsel}
