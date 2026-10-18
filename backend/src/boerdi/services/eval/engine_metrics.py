"""Kennzahlen der Maschinen-Messung (K0-1, Plan 2026-09-26 §5) — reine Funktionen.

Liest Lauf-Details, wie ``GET /api/eval/runs/{id}`` sie liefert (``conversations``
mit den Zügen des Gold-Runners samt ``golden``, ``judge``, ``debug.token_usage``,
``latency_ms``), und fasst sie je Maschine zusammen. Kein Netz, kein LLM: Daten
und Preise bringt der Aufrufer mit.

Zwei Aufrufer, eine Rechnung (ST-7b, 2026-09-27): das Studio (Lauf-Profil und
Vergleich, ``run_profile.py``) und das Messwerkzeug ``evals/engine_matrix.py``.
Bis dahin lag dieses Modul unter ``evals/`` — das Studio hätte es abschreiben
müssen, und zwei Kopien derselben Entscheidungsregeln laufen auseinander.

Die Regeln aus Plan §5.4 werden mitgerechnet, entscheiden tun Menschen:

* R1 — Hybrid bleibt nur mit klarem Vorsprung vor dem Agenten (``auftrag_erfuellt``
  +0,2 oder harte Quote +10 Punkte) bei höchstens +20 % Kosten und p50.
* R2(a) — die Muster-Maschine zeigt einen messbaren Vorteil: Übereinstimmung
  der Checks +10 Punkte, oder mindestens 30 % billiger oder schneller im p50.
  R2(b), ob eine Einbettung genau diesen Vorteil braucht, beantwortet keine Zahl.

Judge-Werte werden je ACHSE verglichen, nie über ``total``: Agent-Züge haben keine
``pattern_match``-Achse, ihr ``total`` mittelt über eine Achse weniger.
"""

from __future__ import annotations

import difflib
import json
import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from typing import Any

AXES = ("intent_fit", "persona_tone", "pattern_match", "safety", "info_quality",
        "auftrag_erfuellt")
#: difflib ist quadratisch; der Anfang einer Antwort trägt ihre Aussage.
_TEXT_CAP = 3000
_EPS = 1e-9

PriceFn = Callable[[str, int, int, int], float | None]


@dataclass(frozen=True)
class Turn:
    flow: str
    index: int
    outcome: tuple            # geprüfte (Kategorie, Ergebnis), sortiert; Fehler: ("ERROR",)
    hard: tuple[int, int]     # (bestanden, geprüft), ohne host
    tools: frozenset[str]
    text: str
    visible: bool             # Blase, Box oder Karte — irgendetwas zu sehen
    latency_ms: int | None
    judge: dict[str, Any] | None
    judge_failed: bool
    error: bool
    tokens: dict[str, Any]


def turns_of(detail: dict[str, Any]) -> list[Turn]:
    """Die Züge eines Laufs in einer flachen, vergleichbaren Form."""
    out: list[Turn] = []
    for conv in detail.get("conversations") or []:
        flow = str(conv.get("flow_id") or "?")
        for i, t in enumerate(conv.get("turns") or [], start=1):
            golden = t.get("golden") or {}
            obs = golden.get("observed") or {}
            checks = {k: v for k, v in (golden.get("checks") or {}).items() if v is not None}
            hard = [v for k, v in checks.items() if k != "host"]
            error = bool(t.get("error"))
            latency = t.get("latency_ms")
            out.append(Turn(
                flow=flow, index=i,
                outcome=("ERROR",) if error else tuple(sorted(checks.items())),
                hard=(sum(1 for v in hard if v), len(hard)),
                tools=frozenset(obs.get("tools_called") or []),
                text=str(t.get("bot") or ""),
                visible=any(int(obs.get(k) or 0) > 0 for k in ("content_len", "cards", "idocs")),
                latency_ms=latency if isinstance(latency, int) else None,
                judge=t.get("judge") if isinstance(t.get("judge"), dict) else None,
                judge_failed=bool(t.get("judge_failed")),
                error=error,
                tokens=(t.get("debug") or {}).get("token_usage") or {},
            ))
    return out


def subset(turns: list[Turn], prefix: str) -> list[Turn]:
    return [t for t in turns if t.flow.startswith(prefix)]


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def quality(turns: list[Turn]) -> dict[str, Any]:
    passed, total = sum(t.hard[0] for t in turns), sum(t.hard[1] for t in turns)
    axes = {}
    for axis in AXES:
        axes[axis] = _mean([t.judge[axis] for t in turns if t.judge
                            and isinstance(t.judge.get(axis), int | float)])
    return {"hard_rate": passed / total if total else None, "hard_passed": passed,
            "hard_total": total, "axes": axes}


def rank(values: list[int], q: float) -> int:
    """Nächster Rang, wie ``run_golden.latency_summary``."""
    ordered = sorted(values)
    return ordered[max(1, math.ceil(q * len(ordered))) - 1]


def speed(turns: list[Turn]) -> dict[str, Any]:
    lat = [t.latency_ms for t in turns if t.latency_ms is not None]
    if not lat:
        return {"p50_ms": None, "p95_ms": None, "over_30s": None, "over_90s": 0}
    return {"p50_ms": rank(lat, 0.5), "p95_ms": rank(lat, 0.95),
            "over_30s": sum(v > 30_000 for v in lat) / len(lat),
            "over_90s": sum(v > 90_000 for v in lat)}


def tokens_and_cost(turns: list[Turn], price: PriceFn) -> dict[str, Any]:
    """Token je Zug und Kosten über alle Modelle eines Zuges. Fehlt ein Preis,
    gibt es KEINE Kosten — eine Teilsumme sähe aus wie eine Abrechnung."""
    counted = [t for t in turns if t.tokens]
    missing: set[str] = set()
    costs: list[float | None] = []
    for t in counted:
        summe, bekannt = 0.0, True
        for model, m in (t.tokens.get("models") or {}).items():
            betrag = price(model, int(m.get("prompt") or 0), int(m.get("cached") or 0),
                           int(m.get("completion") or 0))
            if betrag is None:
                bekannt = False
                missing.add(model)
            else:
                summe += betrag
        costs.append(summe if bekannt else None)
    alle = bool(costs) and all(c is not None for c in costs)

    def mittel(key: str) -> float | None:
        return _mean([int(t.tokens.get(key) or 0) for t in counted])

    return {"turns_with_usage": len(counted), "prompt": mittel("prompt_tokens"),
            "cached": mittel("cached_tokens"), "completion": mittel("completion_tokens"),
            "cost_per_turn": _mean(costs) if alle else None,
            "cost_total": sum(costs) if alle else None,
            "price_unavailable": sorted(missing)}


def robustness(turns: list[Turn], fallback_texts: list[str]) -> dict[str, int]:
    """Chat-Fehler, Judge-Ausfälle, leere Züge und Ersatzantworten mit HTTP 200."""
    def ersatz(t: Turn) -> bool:
        return any(f and f in t.text[:400] for f in fallback_texts)

    return {"turns": len(turns),
            "chat_errors": sum(t.error for t in turns),
            "judge_failed": sum(t.judge_failed for t in turns),
            "empty": sum(not t.error and not t.visible for t in turns),
            "fallback": sum(not t.error and ersatz(t) for t in turns)}


def determinism(runs: list[list[Turn]]) -> dict[str, Any]:
    """Gleicher Zug (Flow, Position) über die Wiederholungen hinweg.

    Züge, die in JEDER Wiederholung scheitern, fehlen hier: sie sind nicht
    stabil, sondern kaputt, und das zählt die Robustheit.
    """
    by_key: dict[tuple[str, int], list[Turn]] = {}
    for run in runs:
        for t in run:
            by_key.setdefault((t.flow, t.index), []).append(t)
    keys = [k for k, ts in by_key.items()
            if len(ts) >= 2 and not all(t.error for t in ts)]
    if not keys:
        return {"turns_compared": 0, "check_agreement": None, "tool_jaccard": None,
                "text_similarity": None, "judge_spread": None}
    jaccard, similar, spreads = [], [], []
    for k in keys:
        ts = by_key[k]
        for a, b in combinations(ts, 2):
            union = a.tools | b.tools
            jaccard.append(len(a.tools & b.tools) / len(union) if union else 1.0)
            # autojunk=False: sonst gelten ab 200 Zeichen häufige Zeichen als
            # Rauschen, und zwei fast gleiche Antworten ergaben 0,03 statt ~1.
            similar.append(difflib.SequenceMatcher(
                None, a.text[:_TEXT_CAP], b.text[:_TEXT_CAP], autojunk=False).ratio())
        scores = [t.judge["auftrag_erfuellt"] for t in ts if t.judge
                  and isinstance(t.judge.get("auftrag_erfuellt"), int | float)]
        if len(scores) >= 2:
            spreads.append(statistics.pstdev(scores))
    agree = sum(len({t.outcome for t in by_key[k]}) == 1 for k in keys)
    return {"turns_compared": len(keys), "check_agreement": agree / len(keys),
            "tool_jaccard": _mean(jaccard), "text_similarity": _mean(similar),
            "judge_spread": _mean(spreads)}


def profile(turns: list[Turn], price: PriceFn, fallbacks: list[str]) -> dict[str, Any]:
    """Was Züge über sich selbst sagen — das Profil EINES Laufs im Studio (ST-7b)
    und der Kern jeder Zusammenfassung; ohne die Kennzahlen über Wiederholungen."""
    return {"quality": quality(turns), "speed": speed(turns),
            "cost": tokens_and_cost(turns, price), "robustness": robustness(turns, fallbacks)}


def summarize(runs: list[list[Turn]], price: PriceFn, fallbacks: list[str]) -> dict[str, Any]:
    turns = [t for run in runs for t in run]
    return {"runs": len(runs), **profile(turns, price, fallbacks),
            "hard_rate_runs": [quality(run)["hard_rate"] for run in runs],
            "determinism": determinism(runs),
            "safe": quality(subset(turns, "GV-SAFE-")),
            "frei": quality(subset(turns, "GV-FREI-"))}


def _get(s: dict[str, Any], *path: str) -> Any:
    for key in path:
        s = (s or {}).get(key)
    return s


def _diff(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def _ratio(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def decision_rules(s: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    agent = s.get("agent")
    # R1 (bleibt der Hybrid?) ist mit K1-1 entschieden und entfällt; das Urteil
    # steht im K0-Bericht (evals/reports/matrix-20260926-204339-auswertung.md).
    if agent and "pattern" in s:
        p = s["pattern"]
        d_agree = _diff(_get(p, "determinism", "check_agreement"),
                        _get(agent, "determinism", "check_agreement"))
        cost_f = _ratio(_get(p, "cost", "cost_per_turn"), _get(agent, "cost", "cost_per_turn"))
        p50_f = _ratio(_get(p, "speed", "p50_ms"), _get(agent, "speed", "p50_ms"))
        gruende = []
        if d_agree is not None and d_agree >= 0.10 - _EPS:
            gruende.append("stabiler")
        if cost_f is not None and cost_f <= 0.7 + _EPS:
            gruende.append("billiger")
        if p50_f is not None and p50_f <= 0.7 + _EPS:
            gruende.append("schneller")
        rules["R2a"] = {"erfuellt": bool(gruende), "gruende": gruende,
                        "d_agreement": d_agree, "kosten_faktor": cost_f, "p50_faktor": p50_f}
    return rules


def conditions_of(summary: dict[str, Any]) -> dict[str, Any]:
    """Was einen Lauf mit einem anderen vergleichbar macht (``summary.messbedingungen``).
    Der Schalter gehört dazu: die Prüfsumme ist dieselbe, ob der Master-Skill an
    oder aus ist."""
    b = summary.get("messbedingungen") or {}
    skill = b.get("master_skill") or {}
    return {"provider": b.get("provider"), "chat_model": b.get("chat_model"),
            "judge_model": b.get("judge_model"),
            "master_skill": {"enabled": skill.get("enabled"),
                             "sha256": (skill.get("sha256") or "")[:12] or None},
            "agent_limits": b.get("agent_limits")}


def check_conditions(runs: list[dict[str, Any]],
                     details: dict[str, dict]) -> tuple[list[str], list[dict[str, Any]]]:
    """Warnungen und die verschiedenen Messbedingungen samt ihren Läufen
    (``runs``: die Matrix-Einträge mit ``engine``, ``label``, ``run_id``)."""
    gruppen: dict[str, dict[str, Any]] = {}
    warnungen, ohne_skill = [], []
    for lauf in runs:
        summary = details[lauf["run_id"]].get("summary") or {}
        if summary.get("engine") not in (None, lauf["engine"]):
            warnungen.append(f"{lauf['label']}: gemessen wurde {summary.get('engine')}.")
        b = conditions_of(summary)
        gruppe = gruppen.setdefault(json.dumps(b, sort_keys=True), {**b, "runs": []})
        gruppe["runs"].append(lauf["label"])
        if lauf["engine"] == "agent" and b["master_skill"]["enabled"] is False:
            ohne_skill.append(lauf["label"])
    if ohne_skill:
        warnungen.append(f"Master-Skill aus in {', '.join(ohne_skill)} — diese Läufe maßen "
                         "den Agenten ohne seine Anleitung (Plan §10).")
    if len(gruppen) > 1:
        warnungen.append("Die Läufe liefen unter verschiedenen Bedingungen, siehe "
                         "Messbedingungen.")
    return warnungen, list(gruppen.values())


def evaluate(runs_by_engine: dict[str, list[list[Turn]]], price: PriceFn,
             fallbacks: list[str]) -> dict[str, Any]:
    engines = {e: summarize(r, price, fallbacks) for e, r in runs_by_engine.items()}
    return {"engines": engines, "rules": decision_rules(engines), "warnings": []}
