"""Läufe vergleichen mit dem Judge v2 (Paket 13, D4) — rein, ohne E/A.

Ergänzt den Vergleich (``engine_compare``) um zwei Fragen: Wie schnitten die Läufe auf den
Skalen ab, und **was war zwischen ihnen anders?** Ohne die zweite Antwort liest man eine
gestiegene Note als Verbesserung, obwohl nur das Modell wechselte.

Die Unterschiede stehen gegen den ersten Lauf (die Referenz): Felder der Messbedingungen,
geänderte Konfigurationsbereiche und Prompt-Bausteine mit beiden Prüfsummen — der Text-Unterschied
kommt aus ``GET /api/eval/prompt-diff``. Ein Lauf von vor Paket 13 kennt weder Bereiche noch
Prompts: dort wird nichts verglichen, statt einen Unterschied zu erfinden.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from boerdi.services.eval import auswertung_v2
from boerdi.services.eval import engine_metrics as em


def bewertung(detail: dict[str, Any], price: em.PriceFn) -> dict[str, Any] | None:
    """Gesamt, Skalen, Zug-Mittel und harte Quote eines Laufs — ``None`` ohne Judge-v2-Note."""
    g = auswertung_v2.auswerten(detail, price)["gesamt"]
    if g["gesamt_mittel"] is None and g["zug_mittel"] is None:
        return None
    return {k: g[k] for k in ("gesamt_mittel", "skalen_mittel", "zug_mittel", "harte_quote")}


def _mittel(werte: list[float]) -> float | None:
    return round(statistics.fmean(werte), 2) if werte else None


def je_maschine(eintraege: list[tuple[str, dict[str, Any] | None]]) -> dict[str, dict[str, Any]]:
    """Mittel der bewerteten Läufe je Maschine (Läufe ohne Bewertung zählen nicht)."""
    gruppen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for maschine, b in eintraege:
        if b is not None:
            gruppen[maschine].append(b)
    aus: dict[str, dict[str, Any]] = {}
    for maschine, liste in gruppen.items():
        skalen: dict[str, list[float]] = defaultdict(list)
        for b in liste:
            for k, v in (b.get("skalen_mittel") or {}).items():
                if v is not None:
                    skalen[k].append(v)
        aus[maschine] = {
            "laeufe": len(liste),
            "gesamt_mittel": _mittel([b["gesamt_mittel"] for b in liste
                                      if b["gesamt_mittel"] is not None]),
            "zug_mittel": _mittel([b["zug_mittel"] for b in liste
                                   if b["zug_mittel"] is not None]),
            "skalen_mittel": {k: _mittel(v) for k, v in skalen.items()},
        }
    return aus


def felder(summary: dict[str, Any]) -> dict[str, Any]:
    """Die vergleichbaren Felder der Messbedingungen (alte Läufe: was sie kannten)."""
    mb = summary.get("messbedingungen") or {}
    weg = mb.get("weg") or {}
    skill = mb.get("master_skill") or {}
    return {
        "maschine": mb.get("maschine") or summary.get("engine"),
        "anbieter": weg.get("anbieter") or mb.get("provider"),
        "modell": weg.get("modell") or mb.get("chat_model"),
        "api": weg.get("api"),
        # Paket 17 (A4): die Route des b-api-Routers kann still auf ein anderes Modell ausweichen.
        # Seither steht der Schlüssel immer im Weg — fehlt er, ist der Lauf älter (unbekannt).
        "route": (weg.get("route") or "ohne") if "route" in weg else None,
        "reasoning_effort": weg.get("reasoning_effort"),
        "verbosity": weg.get("verbosity"),
        "service_tier": weg.get("service_tier"),
        "judge_modell": (mb.get("judge_weg") or {}).get("modell") or mb.get("judge_model"),
        "app_version": (mb.get("app") or {}).get("version"),
        "app_commit": (mb.get("app") or {}).get("commit"),
        "konfiguration": (mb.get("konfiguration") or {}).get("hash"),
        "gold_flows": (mb.get("gold_flows") or {}).get("hash"),
        "judge_fassung": summary.get("judge_fassung"),
        "master_skill": None if not skill else
        f"{'an' if skill.get('enabled') else 'aus'}:{(skill.get('sha256') or '')[:12]}",
    }


def geaenderte_felder(fa: dict[str, Any], fb: dict[str, Any]) -> list[str]:
    """Die Felder, die beide Läufe kennen und die verschieden sind. Kannte ein Lauf ein Feld
    nicht (vor Paket 13: Weg-API, App, Konfiguration, Gold-Flows), ist es unbekannt — nicht
    geändert (Review PR #18)."""
    return [k for k in fa if fa[k] is not None and fb.get(k) is not None and fa[k] != fb[k]]


def _bereiche(summary: dict[str, Any]) -> dict[str, str]:
    roh = ((summary.get("messbedingungen") or {}).get("konfiguration") or {}).get("bereiche")
    return {a: str(e.get("hash")) for a, e in (roh or {}).items() if isinstance(e, dict)}


def prompt_fassungen(detail: dict[str, Any]) -> dict[str, list[str]]:
    """Je Baustein die Prüfsummen, mit denen die Züge des Laufs antworteten."""
    gesehen: dict[str, set[str]] = defaultdict(set)
    for conv in detail.get("conversations") or []:
        for turn in conv.get("turns") or []:
            usage = (turn.get("debug") or {}).get("token_usage") or {}
            for art, h in (usage.get("prompts") or {}).items():
                gesehen[art].add(str(h))
    return {art: sorted(hs) for art, hs in gesehen.items()}


def _gegen(ref: dict[str, Any], lauf: dict[str, Any]) -> dict[str, Any]:
    fa, fb = felder(ref.get("summary") or {}), felder(lauf.get("summary") or {})
    ba, bb = _bereiche(ref.get("summary") or {}), _bereiche(lauf.get("summary") or {})
    pa, pb = prompt_fassungen(ref), prompt_fassungen(lauf)
    return {
        "felder": [{"feld": k, "a": fa[k], "b": fb[k]} for k in geaenderte_felder(fa, fb)],
        "bereiche": sorted(a for a in ba.keys() | bb.keys() if ba.get(a) != bb.get(a))
        if ba and bb else [],
        "prompts": [{"art": art, "a": pa.get(art, []), "b": pb.get(art, [])}
                    for art in sorted(pa.keys() | pb.keys()) if pa.get(art) != pb.get(art)]
        if pa and pb else [],
    }


def unterschiede(laeufe: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Was jeder weitere Lauf gegenüber dem ersten anders hatte (``laeufe``: Kennung, Detail)."""
    if not laeufe:
        return {"referenz": None, "laeufe": []}
    ref_id, ref = laeufe[0]
    return {"referenz": ref_id,
            "laeufe": [{"run": run_id, **_gegen(ref, detail)} for run_id, detail in laeufe[1:]]}
