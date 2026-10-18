"""Auswertung eines Golden-Laufs mit dem Judge v2 (Paket 13, D1) — rein, ohne E/A.

Je Ablauf, gesamt, drei Matrizen und die Zeiten je Phase. Wie das Profil (``run_profile``) beim
Lesen berechnet: eine später gepflegte Preistabelle gilt auch für alte Läufe, und ein Lauf ohne
Judge-v2-Urteile bekommt leere Matrizen statt einer Fehlermeldung.

Harte Quote, Latenz und Kosten rechnen wie das Profil (``engine_metrics``): ``host`` zählt nicht
zur harten Quote, ein unbekannter Preis gibt keine Kosten (keine Teilsumme, die wie eine
Abrechnung aussähe). Noten sind 1–5; gemittelt wird nur, was bewertet wurde.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from boerdi.services.eval import engine_metrics as em


def _mittel(werte: list[float]) -> float | None:
    return round(statistics.fmean(werte), 2) if werte else None


def _ohne_label(wert: Any) -> str:
    """``"P-LER (Lernende)"`` → ``"P-LER"`` — Debug-Felder tragen Kennung und Label."""
    return str(wert or "").split(" ", 1)[0]


def _quote(turns: list[em.Turn]) -> dict[str, int]:
    return {"bestanden": sum(t.hard[0] for t in turns),
            "geprueft": sum(t.hard[1] for t in turns)}


def _zug_note(turn: dict[str, Any]) -> int | None:
    judge = turn.get("judge")
    note = judge.get("gesamt") if isinstance(judge, dict) else None
    return note if isinstance(note, int) and not isinstance(note, bool) else None


def _skalen(urteil: dict[str, Any] | None) -> dict[str, int]:
    roh = (urteil or {}).get("skalen") or {}
    return {k: v["note"] for k, v in roh.items() if isinstance(v, dict) and "note" in v}


def _je_ablauf(conv: dict[str, Any], turns: list[em.Turn], price: em.PriceFn) -> dict[str, Any]:
    urteil = conv.get("urteil") if isinstance(conv.get("urteil"), dict) else None
    noten = [n for t in conv.get("turns") or [] if (n := _zug_note(t)) is not None]
    return {
        "flow_id": str(conv.get("flow_id") or "?"),
        "title": str(conv.get("title") or ""),
        "zielgruppe": str(conv.get("zielgruppe") or ""),
        "skalen": _skalen(urteil),
        "gesamt": (urteil or {}).get("gesamt"),
        "statement": (urteil or {}).get("statement") or "",
        "auffaelligkeiten": (urteil or {}).get("auffaelligkeiten") or [],
        "urteil_fehler": conv.get("urteil_fehler") or "",
        "harte_quote": _quote(turns),
        "zug_mittel": _mittel(noten),
        "zuege": len(turns),
        "chat_fehler": sum(t.error for t in turns),
        "latenz_p50_ms": em.speed(turns)["p50_ms"],
        "kosten": em.tokens_and_cost(turns, price)["cost_total"],
        "werkzeugaufrufe": sum(len(t.tools) for t in turns),
    }


def _matrix(eintraege: list[tuple[str, str, int]]) -> dict[str, dict[str, dict[str, Any]]]:
    sammlung: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for zeile, spalte, note in eintraege:
        sammlung[zeile][spalte].append(note)
    return {z: {s: {"mittel": _mittel(v), "n": len(v)} for s, v in spalten.items()}
            for z, spalten in sammlung.items()}


def _matrizen(convs: list[dict[str, Any]]) -> dict[str, Any]:
    za: list[tuple[str, str, int]] = []
    pi: list[tuple[str, str, int]] = []
    ablauf_skala: dict[str, dict[str, int]] = {}
    for conv in convs:
        urteil = conv.get("urteil") if isinstance(conv.get("urteil"), dict) else None
        if urteil:
            ablauf_skala[str(conv.get("flow_id") or "?")] = {
                **_skalen(urteil), "gesamt": urteil.get("gesamt")}
        for turn in conv.get("turns") or []:
            note = _zug_note(turn)
            if note is None:
                continue
            za.append((str(conv.get("zielgruppe") or "?"),
                       str(turn.get("anwendungsfall") or "sonstiges"), note))
            debug = turn.get("debug") or {}
            if debug.get("engine") == "pattern":
                pi.append((_ohne_label(debug.get("persona")) or "?",
                           _ohne_label(debug.get("intent")) or "?", note))
    return {"matrix_zielgruppe_anwendungsfall": _matrix(za),
            "matrix_ablauf_skala": ablauf_skala,
            "matrix_persona_intent": _matrix(pi)}


def _verteilung(werte: list[int]) -> dict[str, int]:
    geordnet = sorted(werte)
    return {"p50_ms": em._rank(geordnet, 0.5), "p95_ms": em._rank(geordnet, 0.95),
            "n": len(geordnet)}


def _zeiten(convs: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    """Knoten, Teilschritte (``knoten.schritt``) und LLM-Phasen — Fehlzüge zählen nicht."""
    knoten: dict[str, list[int]] = defaultdict(list)
    schritte: dict[str, list[int]] = defaultdict(list)
    llm: dict[str, list[int]] = defaultdict(list)
    for conv in convs:
        for turn in conv.get("turns") or []:
            if turn.get("error"):
                continue
            usage = (turn.get("debug") or {}).get("token_usage") or {}
            for name, ms in (usage.get("zeiten_ms") or {}).items():
                if isinstance(ms, int):
                    (schritte if "." in name else knoten)[name].append(ms)
            for phase, werte in (usage.get("per_phase") or {}).items():
                if isinstance(werte, dict) and isinstance(werte.get("ms"), int):
                    llm[phase].append(werte["ms"])
    return {art: {name: _verteilung(werte) for name, werte in gruppe.items()}
            for art, gruppe in (("knoten", knoten), ("schritte", schritte), ("llm", llm))}


def _judge_kosten(usage: dict[str, Any], price: em.PriceFn) -> float | None:
    summe = 0.0
    for model, m in (usage.get("models") or {}).items():
        betrag = price(model, int(m.get("prompt") or 0), int(m.get("cached") or 0),
                       int(m.get("completion") or 0))
        if betrag is None:
            return None
        summe += betrag
    return round(summe, 6) if usage.get("models") else None


def auswerten(detail: dict[str, Any], price: em.PriceFn) -> dict[str, Any]:
    """Die Auswertung v2 eines gelesenen Laufs (``detail`` wie ``GET /eval/runs/{id}``)."""
    convs = [c for c in detail.get("conversations") or [] if isinstance(c, dict)]
    alle = em.turns_of(detail)
    je_ablauf = [_je_ablauf(c, [t for t in alle if t.flow == str(c.get("flow_id") or "?")],
                            price) for c in convs]
    summary = detail.get("summary") or {}
    judge_usage = summary.get("judge_usage") or {}
    skalen: dict[str, list[int]] = defaultdict(list)
    for eintrag in je_ablauf:
        for k, v in eintrag["skalen"].items():
            skalen[k].append(v)
    zug_noten = [n for c in convs for t in c.get("turns") or []
                 if (n := _zug_note(t)) is not None]
    gesamt = {
        "ablaeufe": len(convs), "zuege": len(alle),
        "gesamt_mittel": _mittel([e["gesamt"] for e in je_ablauf
                                  if isinstance(e["gesamt"], int)]),
        "skalen_mittel": {k: _mittel(v) for k, v in skalen.items()},
        "zug_mittel": _mittel(zug_noten),
        "harte_quote": _quote(alle),
        "latenz": em.speed(alle),
        "kosten_je_zug": em.tokens_and_cost(alle, price)["cost_per_turn"],
        "chat_fehler": sum(t.error for t in alle),
        "judge_fehler": sum(bool(c.get("urteil_fehler")) for c in convs)
                        + sum(t.judge_failed for t in alle),
        "judge_kosten": _judge_kosten(judge_usage, price),
        "judge_aufrufe": judge_usage.get("calls"),
        "judge_fassung": summary.get("judge_fassung") or "",
    }
    return {"je_ablauf": je_ablauf, "gesamt": gesamt, **_matrizen(convs),
            "zeiten": _zeiten(convs)}
