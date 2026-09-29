"""K0-1 (2026-09-26): die Kennzahlen der Maschinen-Messung — ohne LLM, ohne Netz.

``services/eval/engine_metrics.py`` liest Lauf-Details, wie ``GET
/api/eval/runs/{id}`` sie liefert, und fasst sie je Maschine zusammen. Was hier
steht, entscheidet später über Maschinen (Plan §5.4) — jede Zahl ist deshalb an
einem kleinen, von Hand nachrechenbaren Fall festgemacht.

Seit ST-7b (2026-09-27) liegen die Kennzahlen im Backend-Paket: das Studio
rechnet Lauf-Profil und Vergleich damit, das Werkzeug ``evals/engine_matrix.py``
importiert sie von dort. Die Aussagen dieser Tests sind dieselben geblieben.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from boerdi.services.eval import engine_metrics as mm

EVALS = Path(__file__).resolve().parents[2] / "evals"
_spec_r = importlib.util.spec_from_file_location(
    "engine_matrix_report", EVALS / "engine_matrix_report.py")
rep = importlib.util.module_from_spec(_spec_r)
_spec_r.loader.exec_module(rep)

_PREIS = {"gpt-6-luna": (0.10, 0.01, 0.50)}  # je 1 Mio. Token: Eingabe, gecacht, Ausgabe


def _preis(model, prompt, cached, completion):
    if model not in _PREIS:
        return None
    ein, gecacht, aus = _PREIS[model]
    return ((prompt - cached) * ein + cached * gecacht + completion * aus) / 1_000_000


def _zug(checks=None, tools=(), text="Antwort", latency=1000, judge=None,
         error=False, tokens=None, judge_failed=False):
    if error:
        return {"user": "u", "bot": "(chat error: kaputt)", "debug": {},
                "error": "kaputt", "latency_ms": latency}
    zug = {"user": "u", "bot": text, "latency_ms": latency,
           "debug": {"tools_called": list(tools), "token_usage": tokens or {}},
           "golden": {"checks": checks or {},
                      "observed": {"tools_called": list(tools), "content_len": len(text)}}}
    if judge is not None:
        zug["judge"] = judge
    if judge_failed:
        zug["judge_failed"] = "Judge weg"
    return zug


def _lauf(flows: dict[str, list[dict]]) -> list:
    detail = {"summary": {}, "conversations": [
        {"flow_id": fid, "turns": turns} for fid, turns in flows.items()]}
    return mm.turns_of(detail)


def test_harte_quote_zaehlt_nur_gepruefte_kategorien_ohne_host() -> None:
    zuege = _lauf({"A": [_zug({"text": True, "qr": False, "host": False, "register": None})]})
    assert mm.quality(zuege)["hard_rate"] == 0.5


def test_judge_achsen_einzeln_gemittelt_und_nur_wo_bewertet() -> None:
    zuege = _lauf({"A": [
        _zug(judge={"auftrag_erfuellt": 2, "pattern_match": None, "safety": 2}),
        _zug(judge={"auftrag_erfuellt": 0, "pattern_match": None, "safety": 1}),
        _zug(),  # nicht bewertet — zählt nirgends mit
    ]})
    achsen = mm.quality(zuege)["axes"]
    assert (achsen["auftrag_erfuellt"], achsen["safety"]) == (1.0, 1.5)
    assert achsen["pattern_match"] is None


def test_tempo_p50_p95_und_anteile() -> None:
    zuege = _lauf({"A": [_zug(latency=ms) for ms in (1000, 20000, 35000, 95000)]})
    assert mm.speed(zuege) == {"p50_ms": 20000, "p95_ms": 95000,
                               "over_30s": 0.5, "over_90s": 1}


def test_kosten_je_zug_ueber_alle_modelle() -> None:
    tokens = {"prompt_tokens": 1000, "cached_tokens": 400, "completion_tokens": 100,
              "models": {"gpt-6-luna": {"prompt": 1000, "cached": 400, "completion": 100}}}
    kosten = mm.tokens_and_cost(_lauf({"A": [_zug(tokens=tokens)]}), _preis)
    assert kosten["cost_per_turn"] == pytest.approx(114e-6)
    assert (kosten["prompt"], kosten["cached"], kosten["completion"]) == (1000, 400, 100)
    assert kosten["price_unavailable"] == []


def test_ohne_preis_keine_erfundenen_kosten() -> None:
    tokens = {"models": {"unbekannt-1": {"prompt": 10, "cached": 0, "completion": 5}}}
    kosten = mm.tokens_and_cost(_lauf({"A": [_zug(tokens=tokens)]}), _preis)
    assert kosten["cost_per_turn"] is None
    assert kosten["price_unavailable"] == ["unbekannt-1"]


def test_robustheit_zaehlt_fehler_ausfaelle_leere_und_ersatzantworten() -> None:
    zuege = _lauf({"A": [
        _zug(error=True),
        _zug(judge_failed=True),
        _zug(text=""),
        _zug(text="Ich konnte gerade keine Antwort erzeugen. Versuch es noch einmal."),
        _zug(),
    ]})
    rob = mm.robustness(zuege, ["Ich konnte gerade keine Antwort erzeugen."])
    assert rob == {"turns": 5, "chat_errors": 1, "judge_failed": 1, "empty": 1,
                   "fallback": 1}


def test_determinismus_uebereinstimmung_jaccard_und_textnaehe() -> None:
    gleich = {"text": True, "qr": True}
    laeufe = [
        _lauf({"A": [_zug(gleich, tools=("a", "b")), _zug({"qr": True})]}),
        _lauf({"A": [_zug(gleich, tools=("a", "b")), _zug({"qr": True})]}),
        _lauf({"A": [_zug(gleich, tools=("a",)), _zug({"qr": False})]}),
    ]
    det = mm.determinism(laeufe)
    assert det["check_agreement"] == 0.5          # Zug 1 stabil, Zug 2 kippt
    assert det["tool_jaccard"] == pytest.approx((1.0 + 0.5 + 0.5 + 1 + 1 + 1) / 6)
    assert det["text_similarity"] == 1.0
    assert det["turns_compared"] == 2


def test_textnaehe_misst_lange_fast_gleiche_antworten_als_fast_gleich() -> None:
    """Review-Befund 2026-09-26: difflibs ``autojunk`` wertet bei langen Texten
    häufige Zeichen als Rauschen — zwei fast gleiche Antworten von 2 000 Zeichen
    ergaben 0,03 statt nahe 1."""
    a = "Die Photosynthese ist der Prozess, bei dem Pflanzen Licht nutzen. " * 30
    b = a.replace("Licht", "Sonnenlicht", 1)
    laeufe = [_lauf({"A": [_zug(text=a)]}), _lauf({"A": [_zug(text=b)]})]
    assert mm.determinism(laeufe)["text_similarity"] > 0.95


def test_durchgehend_fehlerhafte_zuege_zaehlen_nicht_als_uebereinstimmung() -> None:
    """Ein Zug, der in jeder Wiederholung scheitert, ist nicht „stabil", sondern
    kaputt — das zählt die Robustheit, nicht der Determinismus."""
    laeufe = [
        _lauf({"A": [_zug(error=True), _zug({"qr": True})]}),
        _lauf({"A": [_zug(error=True), _zug({"qr": True})]}),
    ]
    det = mm.determinism(laeufe)
    assert (det["check_agreement"], det["turns_compared"]) == (1.0, 1)


def test_profil_eines_laufs_ist_die_zusammenfassung_ohne_wiederholungen() -> None:
    """ST-7b: das Studio zeigt je Lauf Qualität, Dauer, Kosten und Robustheit —
    dieselben Zahlen, die die Zusammenfassung einer Maschine trägt."""
    zuege = _lauf({"A": [_zug({"qr": True}, judge={"safety": 2}, latency=2000)]})
    profil = mm.profile(zuege, _preis, [])
    assert set(profil) == {"quality", "speed", "cost", "robustness"}
    zusammen = mm.summarize([zuege], _preis, [])
    assert {k: zusammen[k] for k in profil} == profil


def test_teilmengen_safe_und_frei() -> None:
    zuege = _lauf({"GV-SAFE-1": [_zug()], "GV-FREI-2": [_zug(), _zug()], "GV-LEH-1": [_zug()]})
    assert len(mm.subset(zuege, "GV-SAFE-")) == 1
    assert len(mm.subset(zuege, "GV-FREI-")) == 2


def _zusammenfassung(auftrag, hard, kosten, p50, agreement=0.8):
    return {"quality": {"hard_rate": hard, "axes": {"auftrag_erfuellt": auftrag}},
            "cost": {"cost_per_turn": kosten}, "speed": {"p50_ms": p50},
            "determinism": {"check_agreement": agreement}}


def test_eine_alte_matrix_mit_hybrid_bekommt_kein_r1_mehr() -> None:
    """K1-1: R1 ist entschieden. Eine alte Matrix mit Hybrid-Läufen bleibt
    auswertbar, bekommt aber kein Urteil mehr, das niemand mehr braucht."""
    agent = _zusammenfassung(1.2, 0.80, 0.0010, 10000)
    hybrid = _zusammenfassung(1.5, 0.80, 0.0011, 11000)
    assert "R1" not in mm.decision_rules({"agent": agent, "hybrid": hybrid})


def test_r2a_muster_mit_messbarem_vorteil() -> None:
    agent = _zusammenfassung(1.4, 0.85, 0.0010, 12000, agreement=0.70)
    stabil = _zusammenfassung(1.1, 0.80, 0.0010, 12000, agreement=0.85)
    assert mm.decision_rules({"agent": agent, "pattern": stabil})["R2a"]["erfuellt"] is True
    schneller = _zusammenfassung(1.1, 0.80, 0.0010, 8000, agreement=0.70)
    assert mm.decision_rules({"agent": agent, "pattern": schneller})["R2a"]["erfuellt"] is True
    nichts = _zusammenfassung(1.1, 0.80, 0.0010, 11000, agreement=0.72)
    assert mm.decision_rules({"agent": agent, "pattern": nichts})["R2a"]["erfuellt"] is False


def test_bericht_nennt_jede_maschine_und_die_regeln() -> None:
    laeufe = [_lauf({"GV-SAFE-1": [_zug({"text": True}, judge={"auftrag_erfuellt": 2})]})]
    ergebnis = mm.evaluate({"agent": laeufe, "pattern": laeufe}, _preis, [])
    md = rep.render_markdown(ergebnis)
    assert "| Kriterium | agent | pattern |" in md
    assert "R2(a)" in md
    assert "R1" not in md and "Hybrid" not in md  # K1-1: entschieden, entfällt
