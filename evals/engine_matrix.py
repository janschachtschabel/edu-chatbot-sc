#!/usr/bin/env python
"""Maschinen-Messung K0 (Plan docs/plans/2026-09-26-betriebsmodi-und-studio.md §5):
Studio-Gold-Läufe je Maschine starten, wiederholen und auswerten.

    cd backend
    uv run python ../evals/engine_matrix.py start --api http://127.0.0.1:8100 \\
        --engines pattern,agent --repeat 3 --exclude GV-RED-1
    uv run python ../evals/engine_matrix.py auswerten \\
        --matrix ../evals/reports/matrix-<utc>.json

``start`` fährt die Läufe VERSCHRÄNKT (pattern, agent, pattern, …), damit
Tageszeit und Auslastung des Anbieters jede Maschine gleich treffen. Es wartet je
Lauf auf dessen Ende — der Server lässt ohnehin nur einen Lauf zugleich zu — und
schreibt die Matrix nach jedem Schritt; ein Abbruch verliert nichts.

``auswerten`` holt Lauf-Details und Preistafel, rechnet mit den Kennzahlen aus
``boerdi.services.eval.engine_metrics`` (dieselben wie im Studio-Vergleich, ST-7)
und schreibt ``<matrix>-auswertung.md`` und ``.json``.

Der Studio-Schlüssel kommt aus ``STUDIO_API_KEY`` und wird nie ausgegeben; lokal
mit ``BOERDI_ALLOW_OPEN_ADMIN=1`` braucht es keinen. Das Werkzeug läuft in der
Backend-Umgebung (``uv run``): die Auswertung nutzt Preisrechnung und Ersatzsätze
der App, statt sie abzuschreiben.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent
#: K1-1 (2026-09-27): der Hybrid ist entfernt. Alte Matrizen mit Hybrid-Läufen
#: lassen sich weiter auswerten — ``auswerten`` liest die Maschinen aus der Matrix.
ENGINES = ("pattern", "agent")

#: Austauschbare HTTP-Grenze (Tests setzen ``httpx.MockTransport``).
_transport: httpx.BaseTransport | None = None


def client(api: str) -> httpx.Client:
    headers = {}
    key = os.getenv("STUDIO_API_KEY", "").strip()
    if key:
        headers["X-Studio-Key"] = key
    return httpx.Client(base_url=api.rstrip("/"), headers=headers, timeout=60,
                        transport=_transport)


def _liste(raw: str | None) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def plan(engines: list[str], repeat: int) -> list[tuple[int, str]]:
    """Verschränkt: (1, pattern), (1, agent), (2, pattern), …"""
    return [(rep, engine) for rep in range(1, repeat + 1) for engine in engines]


def flow_ids(c: httpx.Client, only: list[str], exclude: list[str]) -> list[str]:
    r = c.get("/api/eval/gold-flows")
    r.raise_for_status()
    ids = [str(f.get("id")) for f in r.json().get("flows") or []]
    if only:
        ids = [i for i in ids if i in only]
    return [i for i in ids if i not in exclude]


def start_run(c: httpx.Client, engine: str, ids: list[str], *, judge: bool, label: str,
              retries: int = 30, pause: float = 10.0) -> dict[str, Any]:
    """Einen Gold-Lauf starten; bei 409 (ein anderer Lauf läuft noch) warten."""
    body = {"flow_ids": ids, "judge": judge, "config_slug": label, "engine": engine}
    for _ in range(retries):
        r = c.post("/api/eval/runs/golden", json=body)
        if r.status_code != 409:
            r.raise_for_status()
            return r.json()
        time.sleep(pause)
    raise RuntimeError("Ein anderer Lauf blockiert seit Minuten (409) — im Studio prüfen.")


def _status(c: httpx.Client, run_id: str) -> str:
    # ``limit=1``: der eigene Lauf ist während der Messung der neueste, und die
    # Liste lädt je Zeile das ganze Transkript aus der Datenbank — im selben
    # Prozess, dessen Tempo gerade gemessen wird.
    r = c.get("/api/eval/runs", params={"limit": 1})
    r.raise_for_status()
    zeile = next((x for x in r.json().get("runs") or [] if x.get("id") == run_id), None)
    if zeile is None:  # nicht der neueste — dann das Detail fragen
        d = c.get(f"/api/eval/runs/{run_id}")
        d.raise_for_status()
        zeile = d.json()
    return str(zeile.get("status"))


def wait_run(c: httpx.Client, run_id: str, *, poll: float = 10.0,
             aussetzer: int = 30) -> str:
    """Bis der Lauf nicht mehr ``running`` ist. Kurze Aussetzer (Netz, 5xx)
    übersteht es; erst ``aussetzer`` Fehlschläge in Folge brechen ab — ein
    Wackler soll keine zweistündige Messreihe beenden."""
    fehler = 0
    while True:
        try:
            status = _status(c, run_id)
            fehler = 0
        except (httpx.TransportError, httpx.HTTPStatusError) as err:
            if isinstance(err, httpx.HTTPStatusError) and err.response.status_code < 500:
                raise
            fehler += 1
            if fehler >= aussetzer:
                raise
            print(f"    (Abfrage gescheitert: {type(err).__name__} — neuer Versuch)",
                  file=sys.stderr, flush=True)
            time.sleep(poll)
            continue
        if status != "running":
            return status
        time.sleep(poll)


def cmd_start(args: argparse.Namespace) -> int:
    engines = _liste(args.engines)
    fremd = [e for e in engines if e not in ENGINES]
    if fremd or args.repeat < 1:
        print(f"Unbekannte Maschine {fremd} oder --repeat < 1.", file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) / f"matrix-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    judge = not args.no_judge
    with client(args.api) as c:
        ids = flow_ids(c, _liste(args.only), _liste(args.exclude))
        if not ids:
            print("Nach dem Filter bleibt kein Flow.", file=sys.stderr)
            return 2
        matrix: dict[str, Any] = {"created": stamp, "api": args.api, "engines": engines,
                                  "repeat": args.repeat, "flows": ids, "judge": judge,
                                  "runs": []}
        schritte = plan(engines, args.repeat)
        for n, (rep, engine) in enumerate(schritte, start=1):
            label = f"{args.label}-{engine}-r{rep}"
            lauf = {"engine": engine, "rep": rep, "label": label, "status": "running",
                    "started": _jetzt()}
            lauf["run_id"] = start_run(c, engine, ids, judge=judge, label=label)["run_id"]
            matrix["runs"].append(lauf)
            out.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[{n}/{len(schritte)}] {label}: {lauf['run_id']} läuft …", flush=True)
            try:
                lauf["status"] = wait_run(c, lauf["run_id"], poll=args.poll)
            except KeyboardInterrupt:
                print(f"Abgebrochen. {lauf['run_id']} läuft auf dem Server weiter — "
                      f"im Studio stoppen. Matrix: {out}", file=sys.stderr)
                return 130
            lauf["finished"] = _jetzt()
            out.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"    → {lauf['status']}", flush=True)
    print(f"Matrix: {out}")
    return 0


def _preis(c: httpx.Client) -> tuple[Any, str | None, str | None]:
    """Preisfunktion aus der Preistafel DES GEMESSENEN Backends (per HTTP, nicht
    aus dem lokalen Speicher: ``--api`` kann auf Staging zeigen), dazu Währung
    und Warnung."""
    from boerdi.domain.config_models import PricingArea
    from boerdi.services.eval.run_profile import price_from_table

    r = c.get("/api/config/data/01-base/pricing")
    if r.status_code != 200:
        return (lambda *a: None), None, f"Preistafel nicht lesbar (HTTP {r.status_code})."
    tafel = PricingArea.model_validate(r.json().get("data") or {})
    return price_from_table(tafel), tafel.currency, None


def cmd_auswerten(args: argparse.Namespace) -> int:
    import engine_matrix_report as report

    from boerdi.services.eval import engine_metrics as mm
    from boerdi.services.eval.run_profile import fallback_texts

    pfad = Path(args.matrix)
    matrix = json.loads(pfad.read_text(encoding="utf-8"))
    warnungen: list[str] = []
    with client(args.api or matrix["api"]) as c:
        details = {}
        for lauf in matrix["runs"]:
            r = c.get(f"/api/eval/runs/{lauf['run_id']}")
            r.raise_for_status()
            details[lauf["run_id"]] = r.json()
        preis, waehrung, warnung = _preis(c)
    if warnung:
        warnungen.append(warnung)
    laeufe: dict[str, list] = {e: [] for e in matrix.get("engines") or ENGINES}
    fertig = {"runs": []}
    for lauf in matrix["runs"]:
        detail = details[lauf["run_id"]]
        if detail.get("status") != "done":
            warnungen.append(f"{lauf['label']}: Status {detail.get('status')} — nicht gewertet.")
            continue
        laeufe.setdefault(lauf["engine"], []).append(mm.turns_of(detail))
        fertig["runs"].append(lauf)
    ergebnis = mm.evaluate({e: r for e, r in laeufe.items() if r}, preis, fallback_texts())
    ergebnis["currency"] = waehrung
    ohne_preis = sorted({m for s in ergebnis["engines"].values()
                         for m in s["cost"]["price_unavailable"]})
    if ohne_preis:
        warnungen.append(f"Kein Preis gepflegt für {', '.join(ohne_preis)} — die "
                         "Kostenzeile bleibt leer, bis die Preistafel im Studio sie kennt.")
    bed_warnungen, ergebnis["conditions"] = mm.check_conditions(fertig["runs"], details)
    ergebnis["warnings"] = warnungen + bed_warnungen
    md = report.render_markdown(ergebnis)
    stamm = pfad.with_suffix("")
    Path(f"{stamm}-auswertung.md").write_text(md, encoding="utf-8")
    Path(f"{stamm}-auswertung.json").write_text(
        json.dumps(ergebnis, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(md)
    print(f"Bericht: {stamm}-auswertung.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="engine_matrix", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="Läufe verschränkt starten und abwarten")
    s.add_argument("--api", required=True, help="Backend, z. B. http://127.0.0.1:8100")
    s.add_argument("--engines", default=",".join(ENGINES))
    s.add_argument("--repeat", type=int, default=3)
    s.add_argument("--only", default="", help="nur diese Flow-IDs (Komma)")
    s.add_argument("--exclude", default="GV-RED-1", help="ohne diese Flow-IDs (Komma)")
    s.add_argument("--label", default="k0", help="Präfix für config_slug der Läufe")
    s.add_argument("--no-judge", action="store_true", help="ohne LLM-Judge")
    s.add_argument("--poll", type=float, default=10.0, help="Sekunden zwischen Abfragen")
    s.add_argument("--out", default=str(HERE / "reports"))
    a = sub.add_parser("auswerten", help="Läufe einer Matrix auswerten")
    a.add_argument("--matrix", required=True)
    a.add_argument("--api", default="", help="sonst die API aus der Matrix")
    args = ap.parse_args(argv)
    # Wie run_golden: eine umgeleitete Ausgabe unter Windows (cp1252) bräche
    # sonst am ersten „→" ab — mitten in einer Messreihe.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return cmd_start(args) if args.cmd == "start" else cmd_auswerten(args)


if __name__ == "__main__":
    sys.exit(main())
