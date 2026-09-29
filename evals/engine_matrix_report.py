"""Bericht der Maschinen-Messung (K0-1): die Kennzahlen als Markdown-Tabelle.

Getrennt von den Kennzahlen (``boerdi.services.eval.engine_metrics``), weil es
ein anderer Grund zur Änderung ist: dort steht, WAS gemessen wird, hier nur, wie
es auf der Seite steht. Zahlen
mit Dezimalkomma, fehlende Werte als „–" — eine leere Zelle sähe aus wie null.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from boerdi.services.eval.engine_metrics import AXES


def _z(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"{x:.{digits}f}".replace(".", ",")


def render_markdown(result: dict[str, Any]) -> str:
    engines = result["engines"]
    names = list(engines)

    def zeile(label: str, fmt: Callable[[dict[str, Any]], str]) -> str:
        return f"| {label} | " + " | ".join(fmt(engines[n]) for n in names) + " |"

    def spanne(s: dict[str, Any]) -> str:
        runs = [r for r in s["hard_rate_runs"] if r is not None]
        band = f" ({_z(min(runs))}–{_z(max(runs))})" if runs else ""
        return _z(s["quality"]["hard_rate"]) + band

    rows = [
        "| Kriterium | " + " | ".join(names) + " |",
        "|---" * (len(names) + 1) + "|",
        zeile("Läufe", lambda s: str(s["runs"])),
        zeile("Harte Quote (Spanne der Läufe)", spanne),
        *[zeile(f"Judge {a} (0–2)", lambda s, a=a: _z(s["quality"]["axes"][a])) for a in AXES],
        zeile("Übereinstimmung der Checks", lambda s: _z(s["determinism"]["check_agreement"])),
        zeile("Werkzeug-Jaccard", lambda s: _z(s["determinism"]["tool_jaccard"])),
        zeile("Textnähe", lambda s: _z(s["determinism"]["text_similarity"])),
        zeile("Streuung auftrag_erfuellt", lambda s: _z(s["determinism"]["judge_spread"])),
        zeile("p50 / p95 (s)", lambda s: " / ".join(
            _z(v / 1000 if v is not None else None, 1)
            for v in (s["speed"]["p50_ms"], s["speed"]["p95_ms"]))),
        zeile("Anteil über 30 s", lambda s: _z(s["speed"]["over_30s"])),
        zeile("Züge über 90 s", lambda s: str(s["speed"]["over_90s"])),
        zeile("Token je Zug (Prompt / gecacht / Ausgabe)", lambda s: " / ".join(
            _z(s["cost"][k], 0) for k in ("prompt", "cached", "completion"))),
        zeile(f"Kosten je Zug ({result.get('currency') or '?'})",
              lambda s: _z(s["cost"]["cost_per_turn"], 5)),
        zeile("Chat-Fehler / Judge-Ausfall / leer / Ersatz", lambda s: " / ".join(
            str(s["robustness"][k]) for k in ("chat_errors", "judge_failed", "empty",
                                              "fallback"))),
        zeile("SAFE: harte Quote", lambda s: _z(s["safe"]["hard_rate"])),
        zeile("FREI: harte Quote / auftrag_erfuellt", lambda s: _z(s["frei"]["hard_rate"])
              + " / " + _z(s["frei"]["axes"]["auftrag_erfuellt"])),
    ]
    rules = result["rules"]
    lines = ["# Maschinen-Messung (K0)", "", *rows, "", "## Regeln (Plan §5.4)", ""]
    if "R2a" in rules:
        r = rules["R2a"]
        urteil = ("erfüllt (" + ", ".join(r["gruende"]) + ")") if r["erfuellt"] else "nicht erfüllt"
        lines.append(f"- **R2(a) Muster: {urteil}.** Δ Übereinstimmung "
                     f"{_z(r['d_agreement'])}, Kosten ×{_z(r['kosten_faktor'])}, "
                     f"p50 ×{_z(r['p50_faktor'])}. R2(b) — braucht eine Einbettung genau "
                     "diesen Vorteil? — beantwortet keine Zahl.")
    else:
        lines.append("- **R2(a) Muster:** nicht gemessen — braucht Läufe für agent und pattern.")
    lines.append("- **R3:** Liegen Unterschiede innerhalb der Spanne der Läufe, gewinnt die "
                 "einfachere Architektur.")
    if result.get("conditions"):
        lines += ["", "## Messbedingungen", ""]
        for b in result["conditions"]:
            skill, deckel = b.get("master_skill") or {}, b.get("agent_limits") or {}
            an = {True: "an", False: "aus"}.get(skill.get("enabled"), "?")
            lines.append(
                f"- {', '.join(b['runs'])}: {b.get('provider') or '?'} · "
                f"{b.get('chat_model') or '?'} · Judge {b.get('judge_model') or '–'} · "
                f"Master-Skill {an} ({skill.get('sha256') or '–'}) · Deckel "
                f"{deckel.get('max_iterations', '?')} Runden, {deckel.get('deadline_s', '?')} s, "
                f"{deckel.get('token_budget', '?')} Token")
    if result.get("warnings"):
        lines += ["", "## Warnungen", "", *[f"- {w}" for w in result["warnings"]]]
    return "\n".join(lines) + "\n"
