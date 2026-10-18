"""Paket 16, D4: wo ein Lasttest-Zug seine Zeit lässt — die Engstelle je Anfrageart.

Rundgang 3: der Lasttest nannte Dauer und Werkzeugzeit, aber nicht, ob LLM, Werkzeuge, das
Warten auf die Vorab-Suche, das Nachsortieren (Rerank, CPU) oder der Rest den Zug trug. Jetzt
teilt ``_zeit_angaben`` die Dauer aus dem Debug-Block auf, und je Art stehen Mediane und Anteile.
"""

from __future__ import annotations

import re
from pathlib import Path

from boerdi.services import loadtest as lt

_DEBUG = {"token_usage": {
    "per_phase": {"classify": {"calls": 1, "ms": 1000}, "response": {"calls": 2, "ms": 3000}},
    "zeiten_ms": {"respond": 6000, "respond.werkzeuge": 1500, "respond.vorabsuche": 500,
                  "respond.rerank": 800, "respond.rag": 200, "assess.rag_einbettung": 100,
                  "assess.safety": 300},
}}


def test_teilt_die_dauer_in_llm_werkzeuge_vorabsuche_rerank_rag_safety_und_rest():
    assert lt._zeit_angaben(_DEBUG, 10_000) == {
        "llm": 4000, "werkzeuge": 1500, "vorabsuche": 500, "rerank": 800, "rag": 300,
        "safety": 300, "rest": 2600}


def test_ueberlappende_teile_lassen_keinen_negativen_rest():
    # Die Vorab-Suche läuft neben der Einordnung: Teile können zusammen länger sein als der Zug.
    assert lt._zeit_angaben(_DEBUG, 5000)["rest"] == 0


def test_ohne_debug_keine_zeiten():
    assert lt._zeit_angaben({}, 5000) is None


def test_je_art_mediane_und_anteile_nur_aus_erfolgreichen_anfragen():
    def anfrage(llm: int, rerank: int, ok: bool = True) -> dict:
        zeiten = {"llm": llm, "werkzeuge": 0, "vorabsuche": 0, "rerank": rerank, "rag": 0,
                  "safety": 0, "rest": 0}
        return {"kind": "suche", "ok": ok, "status": 200 if ok else 500, "latency_s": 1.0,
                "zeiten": zeiten}

    ergebnisse = [anfrage(3000, 1000), anfrage(5000, 3000), anfrage(1, 99_999, ok=False)]
    art = lt._stage_stats(1, 3, ["suche"] * 3, ergebnisse, 10.0)["by_kind"]["suche"]
    assert art["zeiten_ms"]["llm"] == 4000 and art["zeiten_ms"]["rerank"] == 2000
    assert art["anteile"]["llm"] == 0.667 and art["anteile"]["rerank"] == 0.333


def test_ohne_zeiten_bleiben_die_anteile_leer():
    ergebnisse = [{"kind": "suche", "ok": True, "status": 200, "latency_s": 1.0}]
    art = lt._stage_stats(1, 1, ["suche"], ergebnisse, 10.0)["by_kind"]["suche"]
    assert art["anteile"] == {} and art["zeiten_ms"] == {}


def test_jeder_gelesene_schritt_wird_auch_geschrieben():
    """Wie R2-3 (Paket 15): ein Schlüssel, den niemand schreibt, misst still null."""
    quelle = "\n".join(p.read_text(encoding="utf-8")
                       for p in (Path(lt.__file__).parents[1]).rglob("*.py"))
    geschrieben = set(re.findall(r'schritt\("([a-z_.]+)"', quelle))
    gelesen = {s for schritte in lt.ZEIT_TEILE.values() for s in schritte}
    assert gelesen <= geschrieben, gelesen - geschrieben
