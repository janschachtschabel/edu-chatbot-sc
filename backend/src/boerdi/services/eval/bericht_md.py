"""Ein Golden-Lauf als Markdown-Bericht (Paket 13, D3) — rein, ohne E/A.

Liest das Lauf-Detail, wie ``GET /eval/runs/{id}`` es liefert (``summary.messbedingungen``,
``summary.kurzbericht``, ``auswertung``), und setzt daraus einen Bericht zum Weitergeben:
Messbedingungen, Kurzbericht, Gesamt, Matrizen als Tabellen, je Ablauf Noten und Statement,
Zeiten. Text aus Judge und Konfiguration wird entschärft — ein ``|`` im Titel oder ein ``<b>``
im Statement darf weder eine Tabelle zerreißen noch als HTML ankommen.
"""

from __future__ import annotations

import re
from typing import Any

_SONDERZEICHEN = re.compile(r"([\\`*_\[\]<>|#])")


def _esc(wert: Any) -> str:
    """Markdown-Sonderzeichen entschärfen, Zeilenumbrüche falten."""
    text = " ".join(str("" if wert is None else wert).split())
    return _SONDERZEICHEN.sub(r"\\\1", text)


def _zahl(wert: Any) -> str:
    return "—" if wert is None else str(wert)


def _tabelle(kopf: list[str], zeilen: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf),
            *("| " + " | ".join(z) + " |" for z in zeilen), ""]


def _weg(weg: dict[str, Any] | None) -> str:
    if not weg:
        return "—"
    teile = [_esc(weg.get(k)) for k in ("anbieter", "modell", "api") if weg.get(k)]
    teile += [f"{k}={_esc(weg[k])}" for k in ("reasoning_effort", "verbosity", "service_tier")
              if weg.get(k)]
    return " · ".join(teile) or "—"


def _messbedingungen(summary: dict[str, Any]) -> list[str]:
    mb = summary.get("messbedingungen") or {}
    app = mb.get("app") or {}
    konfig = mb.get("konfiguration") or {}
    gold = mb.get("gold_flows") or {}
    skill = mb.get("master_skill") or {}
    zeilen = [
        ("Maschine", _esc(mb.get("maschine"))),
        ("Chat", _weg(mb.get("weg")) if mb.get("weg") else _esc(mb.get("chat_model"))),
        ("Judge", _weg(mb.get("judge_weg"))),
        ("App", f"{_esc(app.get('version')) or '—'} ({_esc(app.get('commit')) or '—'})"),
        ("Konfiguration", _esc(konfig.get("hash") or konfig.get("fehler")) or "—"),
        ("Master-Skill", _esc(skill.get("version")) or "—"),
        ("Golden-Abläufe", f"{_esc(gold.get('hash')) or '—'} ({len(gold.get('ids') or [])})"),
        ("Judge-Fassung", _esc(summary.get("judge_fassung")) or "—"),
    ]
    return ["## Messbedingungen", "", *(f"- **{k}:** {v}" for k, v in zeilen), ""]


def _kurzbericht(summary: dict[str, Any]) -> list[str]:
    bericht = summary.get("kurzbericht")
    if not isinstance(bericht, dict):
        grund = summary.get("kurzbericht_fehler") or "Lauf ohne Judge"
        return ["## Kurzbericht", "", f"Kein Kurzbericht: {_esc(grund)}", ""]
    zeilen = ["## Kurzbericht", "", _esc(bericht.get("text")), ""]
    for b in bericht.get("baustellen") or []:
        bezug = f" ({_esc(b['ablauf'])})" if b.get("ablauf") else ""
        zeilen.append(f"- **Baustelle{bezug}:** {_esc(b.get('text'))}")
    return [*zeilen, ""] if bericht.get("baustellen") else zeilen


def _gesamt(g: dict[str, Any]) -> list[str]:
    quote = g.get("harte_quote") or {}
    latenz = g.get("latenz") or {}
    zeilen = [
        ["Gesamt (Abläufe)", _zahl(g.get("gesamt_mittel"))],
        ["Mittel der Zug-Noten", _zahl(g.get("zug_mittel"))],
        *([f"Skala {_esc(k)}", _zahl(v)] for k, v in (g.get("skalen_mittel") or {}).items()),
        ["Harte Prüfungen", f"{quote.get('bestanden', 0)}/{quote.get('geprueft', 0)}"],
        ["Latenz p50 / p95 (ms)", f"{_zahl(latenz.get('p50_ms'))} / "
                                  f"{_zahl(latenz.get('p95_ms'))}"],
        ["Kosten je Zug", _zahl(g.get("kosten_je_zug"))],
        ["Judge-Kosten", _zahl(g.get("judge_kosten"))],
        ["Abläufe / Züge", f"{_zahl(g.get('ablaeufe'))} / {_zahl(g.get('zuege'))}"],
        ["Chat-Fehler / Judge-Fehler", f"{_zahl(g.get('chat_fehler'))} / "
                                       f"{_zahl(g.get('judge_fehler'))}"],
    ]
    return ["## Gesamt", "", *_tabelle(["Kennzahl", "Wert"], zeilen)]


def _zellen_matrix(titel: str, kopf: str, matrix: dict[str, dict[str, Any]]) -> list[str]:
    spalten = sorted({s for werte in matrix.values() for s in werte})
    zeilen = [[_esc(z), *(f"{_zahl(w['mittel'])} ({w['n']})" if (w := werte.get(s)) else "—"
                         for s in spalten)]
              for z, werte in sorted(matrix.items())]
    return [f"## {titel}", "", *_tabelle([kopf, *(_esc(s) for s in spalten)], zeilen)]


def _ablauf_skala(matrix: dict[str, dict[str, Any]]) -> list[str]:
    skalen = [s for s in dict.fromkeys(k for w in matrix.values() for k in w) if s != "gesamt"]
    zeilen = [[_esc(a), *(_zahl(w.get(s)) for s in [*skalen, "gesamt"])]
              for a, w in matrix.items()]
    return ["## Ablauf × Skala", "",
            *_tabelle(["Ablauf", *(_esc(s) for s in skalen), "gesamt"], zeilen)]


def _ablaeufe(je_ablauf: list[dict[str, Any]]) -> list[str]:
    zeilen = ["## Abläufe", ""]
    for e in je_ablauf:
        quote = e.get("harte_quote") or {}
        zeilen += [f"### {_esc(e.get('flow_id'))} — {_esc(e.get('title'))}", "",
                   f"Zielgruppe {_esc(e.get('zielgruppe'))} · Gesamt {_zahl(e.get('gesamt'))} · "
                   f"Zug-Mittel {_zahl(e.get('zug_mittel'))} · hart "
                   f"{quote.get('bestanden', 0)}/{quote.get('geprueft', 0)} · "
                   f"p50 {_zahl(e.get('latenz_p50_ms'))} ms · Kosten {_zahl(e.get('kosten'))}"]
        if e.get("skalen"):
            zeilen.append("Skalen: " + ", ".join(f"{_esc(k)} {v}"
                                                 for k, v in e["skalen"].items()))
        zeilen.append("")
        if e.get("urteil_fehler"):
            zeilen += [f"Kein Ablauf-Urteil: {_esc(e['urteil_fehler'])}", ""]
        elif e.get("statement"):
            zeilen += [f"> {_esc(e['statement'])}", ""]
        for a in e.get("auffaelligkeiten") or []:
            zug = f"Zug {a['zug']}, " if a.get("zug") else ""
            zeilen.append(f"- {zug}{_esc(a.get('art'))}: {_esc(a.get('text'))}")
        if e.get("auffaelligkeiten"):
            zeilen.append("")
    return zeilen


def _zeiten(zeiten: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    zeilen = [[_esc(art), _esc(name), _zahl(w.get("p50_ms")), _zahl(w.get("p95_ms")),
               _zahl(w.get("n"))]
              for art in ("knoten", "schritte", "llm")
              for name, w in sorted((zeiten.get(art) or {}).items())]
    return ["## Zeiten", "", *_tabelle(["Art", "Schritt", "p50 (ms)", "p95 (ms)", "n"], zeilen)]


def render(detail: dict[str, Any]) -> str:
    """Der Bericht eines gelesenen Laufs als Markdown-Text."""
    summary = detail.get("summary") or {}
    zeilen = [f"# Evaluationsbericht {_esc(detail.get('id'))}", "",
              f"{_esc(detail.get('created_at'))} · Maschine {_esc(detail.get('engine'))} · "
              f"Status {_esc(detail.get('status'))}", "",
              *_messbedingungen(summary), *_kurzbericht(summary)]
    auswertung = detail.get("auswertung")
    if not isinstance(auswertung, dict):
        return "\n".join([*zeilen, "Keine Auswertung (Lauf ohne Judge v2).", ""])
    zeilen += _gesamt(auswertung.get("gesamt") or {})
    zeilen += _zellen_matrix("Zielgruppe × Anwendungsfall", "Zielgruppe",
                             auswertung.get("matrix_zielgruppe_anwendungsfall") or {})
    zeilen += _ablauf_skala(auswertung.get("matrix_ablauf_skala") or {})
    if auswertung.get("matrix_persona_intent"):
        zeilen += _zellen_matrix("Persona × Intent (nur Muster)", "Persona",
                                 auswertung["matrix_persona_intent"])
    zeilen += _ablaeufe(auswertung.get("je_ablauf") or [])
    zeilen += _zeiten(auswertung.get("zeiten") or {})
    return "\n".join(zeilen)
