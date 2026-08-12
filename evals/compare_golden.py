#!/usr/bin/env python
"""A/B-Abweichungs-Report zweier Golden-Läufe (P11, Spec §9-Schritt 4).

``run_golden.py`` fährt die Suite gegen EIN Backend und schreibt einen Report.
Der Parallelbetrieb verlangt den Vergleich: was tut NEU anders als ALT, pro Flow
und pro Turn. Dieses Modul liest zwei solche Reports und meldet die Abweichung.

    cd backend && uv run python ../evals/compare_golden.py \
        --ref ../evals/reports/golden-<utc>-ref-alt.json \
        --new ../evals/reports/golden-<utc>-neu.json

    # Muster-Engine gegen Agent-Modus derselben Anlage (A5):
    cd backend && uv run python ../evals/compare_golden.py \
        --ref ../evals/reports/golden-<utc>-pattern.json \
        --new ../evals/reports/golden-<utc>-agent.json \
        --ignore-classification

Exit-Code 0 = keine Regression und beide Läufe deckungsgleich; 1 = mindestens
eine harte Regression, ein Fehl-Turn in NEU oder ein Strukturbruch (ein Flow/Turn
nur auf einer Seite — dann ist der Vergleich selbst nicht mehr belastbar).

**Was verglichen wird und was nicht.** Verglichen werden die Check-Ergebnisse
(pass/fail je Kategorie) sowie Klassifikation und Struktur (persona, intent,
pattern, cards, idocs, qr). NICHT verglichen werden Wortlaut, Textlänge und die
Sie/du-Zähler: das Modell ist nichtdeterministisch, diese Werte weichen bei
JEDEM Turn ab, und ein Report, der bei jedem Turn anschlägt, verdeckt die eine
Abweichung, auf die es ankommt. Für die in §9-4 geforderte Stichproben-Redaktion
trägt der JSON-Report die beiden Wortlaute der abweichenden Turns mit — dort
gehören sie hin, weil sie dort gelesen werden.

``--ignore-classification`` (A5) nimmt Persona, Intent und Muster ganz heraus.
Das ist der Schalter für den zweiten Vergleichszweck: **Muster-Engine gegen
Agent-Modus** derselben Anlage. Der Agent klassifiziert nicht (A4b) und wählt
kein Muster (A4c-1) — diese drei weichen dort an fast jedem Zug ab, von Bauart
wegen und nicht als Befund; ungefiltert überdeckt das Rauschen genau die Frage,
um die es geht. Für den ursprünglichen ALT↔NEU-Vergleich bleibt der Schalter
aus, denn dort IST eine andere Klassifikation ein Befund.

Framework-frei wie der Runner (nur stdlib), damit er gegen jedes Backend läuft.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# Die Kategorien-Aufteilung (hart vs. weich) gehört dem Runner. Sie hier zu
# kopieren hieße, sie driften zu lassen; ihn zu importieren geht nur PER PFAD,
# weil beide Dateien ohne Installation dieses Projekts lauffähig bleiben müssen
# (run_golden.py begründet dieselbe Einschränkung in seinem Kopf).
_spec = importlib.util.spec_from_file_location("run_golden", HERE / "run_golden.py")
_rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rg)
GOLDEN_CATS: list[str] = _rg.GOLDEN_CATS
GOLDEN_HARD: list[str] = _rg.GOLDEN_HARD

CLASSIFICATION = ("persona", "intent", "pattern")
STRUCTURE = ("cards", "idocs", "qr")

#: Die Check-Kategorien, die aus dem Klassifikator kommen (``pattern`` ist keine
#: Kategorie, sondern nur ein beobachteter Wert). Nur diese blendet
#: ``--ignore-classification`` aus — Register, Struktur, Quick-Replies und Host
#: beschreiben die ANTWORT und bleiben.
CLASSIFICATION_CHECKS = ("persona", "intent")

TurnKey = tuple[str, int]


def flow_ids(report: dict[str, Any]) -> list[str]:
    """Flow-IDs in Report-Reihenfolge, ohne Dubletten."""
    seen: list[str] = []
    for conv in report.get("conversations") or []:
        fid = str(conv.get("flow_id") or "?")
        if fid not in seen:
            seen.append(fid)
    return seen


def index_turns(report: dict[str, Any]) -> dict[TurnKey, dict[str, Any]]:
    """(flow_id, turn_nr) -> Turn-Record. Die Turn-Nummer ist die Position im
    Flow, genau wie sie ``aggregate_golden`` vergibt."""
    out: dict[TurnKey, dict[str, Any]] = {}
    for conv in report.get("conversations") or []:
        fid = str(conv.get("flow_id") or "?")
        for i, turn in enumerate(conv.get("turns") or [], start=1):
            out[(fid, i)] = turn
    return out


def compare_turn(
    ref_turn: dict[str, Any], new_turn: dict[str, Any], *,
    ignore_classification: bool = False,
) -> dict[str, Any]:
    """Ein Turn-Paar vergleichen.

    Eine Regression ist ausschließlich True→False. None heißt „für diesen Turn
    nicht geprüft" (Wildcard-Persona, leerer Intent, kartenloser Turn bei
    ``host``) — daraus kann weder Regression noch Verbesserung werden, sonst
    zählt der Report Beobachtungslücken als Fehler.

    ``ignore_classification`` (A5) lässt Persona, Intent und Muster ganz aus dem
    Vergleich. Gedacht für Muster-Engine ↔ Agent-Modus: der Agent klassifiziert
    nicht (A4b) und wählt kein Muster (A4c-1), diese drei weichen also an fast
    jedem Zug ab — von Bauart wegen, nicht als Befund. Ungefiltert überdeckte
    das Rauschen genau die Frage, um die es geht: wird die ANTWORT besser oder
    schlechter.
    """
    ref_err, new_err = ref_turn.get("error"), new_turn.get("error")
    dev: dict[str, Any] = {
        "regressions": [], "improvements": [], "changed": {}, "error": None,
    }
    if ref_err or new_err:
        # Ein Turn, der nicht stattgefunden hat, hat keine Checks; ihn trotzdem
        # zu vergleichen erzeugt Phantom-Regressionen.
        dev["error"] = {"ref": ref_err, "new": new_err}
        return dev

    kategorien = [c for c in GOLDEN_CATS
                  if not (ignore_classification and c in CLASSIFICATION_CHECKS)]
    felder = (*STRUCTURE,) if ignore_classification else (*CLASSIFICATION, *STRUCTURE)

    ref_g = ref_turn.get("golden") or {}
    new_g = new_turn.get("golden") or {}
    ref_c, new_c = ref_g.get("checks") or {}, new_g.get("checks") or {}
    dev["regressions"] = [c for c in kategorien
                          if ref_c.get(c) is True and new_c.get(c) is False]
    dev["improvements"] = [c for c in kategorien
                           if ref_c.get(c) is False and new_c.get(c) is True]

    ref_o, new_o = ref_g.get("observed") or {}, new_g.get("observed") or {}
    dev["changed"] = {
        field: {"ref": ref_o.get(field), "new": new_o.get(field)}
        for field in felder
        if ref_o.get(field) != new_o.get(field)
    }
    return dev


def _empty_summary() -> dict[str, int]:
    return {
        "turns_compared": 0, "hard_regressions": 0, "soft_regressions": 0,
        "improvements": 0, "classification_changes": 0, "structure_changes": 0,
        "errors_ref": 0, "errors_new": 0,
    }


def compare_reports(
    ref: dict[str, Any], new: dict[str, Any], *,
    ignore_classification: bool = False,
) -> dict[str, Any]:
    """Vollständiger Abweichungs-Report über zwei Golden-Reports."""
    ref_flows, new_flows = flow_ids(ref), flow_ids(new)
    shared = [f for f in ref_flows if f in new_flows]
    ref_turns, new_turns = index_turns(ref), index_turns(new)

    # Turns fehlender Flows NICHT zusätzlich einzeln melden — der fehlende Flow
    # ist die Aussage, seine 4 Turns sind nur ihr Echo.
    only_ref_turns = [[f, i] for (f, i) in ref_turns
                      if f in shared and (f, i) not in new_turns]
    only_new_turns = [[f, i] for (f, i) in new_turns
                      if f in shared and (f, i) not in ref_turns]

    summary = _empty_summary()
    deviations: list[dict[str, Any]] = []
    for key in ref_turns:
        if key[0] not in shared or key not in new_turns:
            continue
        ref_turn, new_turn = ref_turns[key], new_turns[key]
        summary["turns_compared"] += 1
        dev = compare_turn(ref_turn, new_turn,
                           ignore_classification=ignore_classification)

        hard = [c for c in dev["regressions"] if c in GOLDEN_HARD]
        summary["hard_regressions"] += len(hard)
        summary["soft_regressions"] += len(dev["regressions"]) - len(hard)
        summary["improvements"] += len(dev["improvements"])
        summary["classification_changes"] += sum(
            1 for f in dev["changed"] if f in CLASSIFICATION)
        summary["structure_changes"] += sum(
            1 for f in dev["changed"] if f in STRUCTURE)
        if dev["error"]:
            summary["errors_ref"] += 1 if dev["error"]["ref"] else 0
            summary["errors_new"] += 1 if dev["error"]["new"] else 0

        if not (dev["regressions"] or dev["improvements"] or dev["changed"]
                or dev["error"]):
            continue
        deviations.append({
            "flow": key[0], "turn": key[1],
            "message": ref_turn.get("user", ""),
            **dev,
            # Beide Wortlaute NUR am abweichenden Turn: die Redaktion braucht
            # sie genau hier, und an allen Turns wäre der Report ein Duplikat
            # der beiden Eingangs-Reports.
            "texts": {"ref": ref_turn.get("bot", ""), "new": new_turn.get("bot", "")},
        })

    return {
        "flows": {
            "shared": shared,
            "only_ref": [f for f in ref_flows if f not in new_flows],
            "only_new": [f for f in new_flows if f not in ref_flows],
        },
        "turns": {"only_ref": only_ref_turns, "only_new": only_new_turns},
        # Gehört in den Report, nicht nur in den Aufruf: ein Vergleich, dem man
        # nicht ansieht, dass er filtert, behauptet mehr Deckungsgleichheit, als
        # er geprüft hat.
        "ignore_classification": ignore_classification,
        "summary": summary,
        "deviations": deviations,
    }


def is_blocking(diff: dict[str, Any]) -> bool:
    """Was die Abnahme verhindert: eine harte Regression, ein Fehl-Turn in NEU
    oder ein Strukturbruch. Weiche Regressionen (``host``), Verbesserungen und
    reine Klassifikations-Wechsel werden berichtet, blockieren aber nicht."""
    s = diff["summary"]
    return bool(
        s["hard_regressions"] or s["errors_new"]
        or diff["flows"]["only_ref"] or diff["flows"]["only_new"]
        or diff["turns"]["only_ref"] or diff["turns"]["only_new"]
    )


def render_console(diff: dict[str, Any]) -> str:
    s = diff["summary"]
    gefiltert = (
        "  (Klassifikation ausgeblendet: Persona, Intent und Muster)"
        if diff.get("ignore_classification") else ""
    )
    lines = [
        "",
        f"Verglichen: {s['turns_compared']} Turns in {len(diff['flows']['shared'])} Flows"
        f"{gefiltert}",
        f"  harte Regressionen   {s['hard_regressions']}",
        f"  weiche Regressionen  {s['soft_regressions']}  (host)",
        f"  Verbesserungen       {s['improvements']}",
        f"  Klassifikation ≠     {s['classification_changes']}",
        f"  Struktur ≠           {s['structure_changes']}",
        f"  Fehl-Turns ALT/NEU   {s['errors_ref']}/{s['errors_new']}",
    ]
    for side, label in (("only_ref", "nur in ALT"), ("only_new", "nur in NEU")):
        if diff["flows"][side]:
            lines.append(f"  Flows {label}: {', '.join(diff['flows'][side])}")
        if diff["turns"][side]:
            turns = ", ".join(f"{f} T{i}" for f, i in diff["turns"][side])
            lines.append(f"  Turns {label}: {turns}")

    if diff["deviations"]:
        lines.append("\nAbweichungen:")
        for dev in diff["deviations"]:
            head = f"  {dev['flow']} T{dev['turn']}"
            if dev["error"]:
                lines.append(f"{head}: Fehl-Turn ALT={dev['error']['ref']!r}"
                             f" NEU={dev['error']['new']!r}")
                continue
            parts = []
            if dev["regressions"]:
                parts.append("Regression: " + ", ".join(dev["regressions"]))
            if dev["improvements"]:
                parts.append("besser: " + ", ".join(dev["improvements"]))
            for field, pair in dev["changed"].items():
                parts.append(f"{field} {pair['ref']}→{pair['new']}")
            lines.append(f"{head}: " + "  |  ".join(parts))
    else:
        lines.append("\nKeine Abweichung.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # non-reconfigurable stream (e.g. under some test runners)
    p = argparse.ArgumentParser(description="Golden A/B-Abweichungs-Report (§9-4)")
    p.add_argument("--ref", required=True, help="Referenz-Report (ALT)")
    p.add_argument("--new", required=True, help="Vergleichs-Report (NEU)")
    p.add_argument("--out", default=str(HERE / "reports"))
    p.add_argument("--label", default="", help="Dateiname-Zusatz")
    p.add_argument(
        "--ignore-classification", action="store_true",
        help="Persona/Intent/Muster nicht vergleichen — für Muster-Engine "
             "gegen Agent-Modus, wo sie von Bauart wegen abweichen",
    )
    args = p.parse_args(argv)

    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    new = json.loads(Path(args.new).read_text(encoding="utf-8"))
    diff = compare_reports(ref, new,
                           ignore_classification=args.ignore_classification)
    diff["ref"] = {"path": args.ref, "chat_url": ref.get("chat_url", "")}
    diff["new"] = {"path": args.new, "chat_url": new.get("chat_url", "")}
    diff["blocking"] = is_blocking(diff)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    label = f"-{args.label}" if args.label else ""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"ab-{stamp}{label}.json"
    report_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print(render_console(diff))
    print(f"\nReport: {report_path}")
    return 1 if diff["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
