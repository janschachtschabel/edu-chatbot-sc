"""C3: the golden run's soft layer (``services/eval/golden.py``).

Port of the judge + aggregation block of ALT ``eval_golden.execute_golden_run``
(assertions from ALT tests/test_eval_service.py:1148-1235). Two rules carry the
whole module:

* the headline ``avg_score`` stays the DETERMINISTIC hard pass rate — the judge
  average is reported beside it (``judge_avg``), never mixed into it, or the run
  list and the scorecard would show different numbers for the same run;
* a judge that fails costs its turn a score, not the run.

Offline: the judge v2 (``judge_zug``/``judge_ablauf``) is faked, and the IDs
are synthetic (``P-SYN``…) so no
assertion depends on the real persona/intent config — the same reason
test_eval_metrics.py uses them.
"""

from __future__ import annotations

import asyncio

from boerdi.services.eval import golden as eg

_DBG = {"pattern": "M-SYN (z)", "persona": "P-SYN (x)",
        "intent": "I-SYN (y)", "tools_called": []}

# What ``aggregate_golden`` (evals/run_golden.py, tested there) returns for two
# all-passing turns. Passed in rather than recomputed: this module composes the
# summary, it does not own the deterministic scorecard.
_GM = {"overall_pass_rate": 1.0, "turns": 2, "flows": 1,
       "hard_passed": 10, "hard_total": 10, "rates": {}, "per_turn": [],
       "per_flow": {}, "passed": {}, "totals": {}}


def _convs(*, error_turn: bool = False, persona: str = "P-SYN") -> list[dict]:
    turns: list[dict] = [
        {"user": "text eins", "bot": "b1", "debug": dict(_DBG),
         "expected_persona": persona, "expected_intent": "I-SYN"},
        {"user": "text zwei", "bot": "b2", "debug": dict(_DBG),
         "expected_persona": None, "expected_intent": None},
    ]
    if error_turn:
        turns.append({"user": "text drei", "bot": "(chat error: down)", "debug": {},
                      "error": "down", "expected_persona": persona,
                      "expected_intent": "I-SYN"})
    return [{"kind": "golden", "flow_id": "F1", "title": "Flow Eins",
             "persona_id": persona, "intent_id": "I-SYN", "turns": turns}]


def _patch_defs(monkeypatch) -> None:
    monkeypatch.setattr(eg, "load_persona_definitions", lambda: [
        {"id": "P-SYN", "label": "Synth-Persona", "description": "erfunden"},
    ])
    monkeypatch.setattr(eg, "_persona_erwartungen", lambda pid: f"Regeln {pid}")


def _judge_spy(monkeypatch, *, result=None, exc=None, ablauf_exc=None) -> dict:
    """Paket 13 (C5): die Attrappen folgen den ECHTEN Signaturen von ``judge_v2``."""
    calls: dict = {"zug": [], "ablauf": []}

    async def fake_zug(gespraech, index, zielgruppe, *, usage_acc=None):
        calls["zug"].append((gespraech, index, zielgruppe, usage_acc))
        if exc is not None:
            raise exc
        return dict(result or {"total": 0.5, "notes": "", "gesamt": 3})

    async def fake_ablauf(gespraech, zielgruppe, *, usage_acc=None):
        calls["ablauf"].append((gespraech, zielgruppe, usage_acc))
        if ablauf_exc is not None:
            raise ablauf_exc
        return {"gesamt": 4, "statement": "gut"}

    monkeypatch.setattr(eg, "judge_zug", fake_zug)
    monkeypatch.setattr(eg, "judge_ablauf", fake_ablauf)
    return calls


# ── bewerte_gespraeche (Judge v2, Paket 13) ──────────────────────────────
def test_bewertet_jeden_beantworteten_zug_und_den_ablauf(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)
    convs = _convs(error_turn=True)
    acc: dict = {}

    zahl = asyncio.run(eg.bewerte_gespraeche(convs, usage_acc=acc))

    assert zahl == {"zuege": 2, "ablaeufe": 1}
    assert [c[1] for c in calls["zug"]] == [0, 1]
    t1, t2, t3 = convs[0]["turns"]
    assert t1["judge"]["total"] == 0.5 and t2["judge"]["total"] == 0.5
    assert "judge" not in t3  # ein Zug ohne Antwort hat nichts zu bewerten
    assert convs[0]["urteil"] == {"gesamt": 4, "statement": "gut"}
    assert calls["zug"][0][3] is acc and calls["ablauf"][0][2] is acc


def test_die_zielgruppe_kommt_aus_der_konfiguration(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)
    convs = _convs()
    convs[0]["persona_id"] = "*"
    convs[0]["zielgruppe"] = "P-SYN"

    asyncio.run(eg.bewerte_gespraeche(convs))

    zielgruppe = calls["ablauf"][0][1]
    assert zielgruppe == {"id": "P-SYN", "label": "Synth-Persona", "description": "erfunden",
                          "erwartungen": "Regeln P-SYN"}
    assert calls["zug"][0][2] is zielgruppe


def test_eine_unbekannte_zielgruppe_wird_zum_stub(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)

    asyncio.run(eg.bewerte_gespraeche(_convs(persona="P-XX")))

    assert calls["ablauf"][0][1] == {"id": "P-XX", "label": "P-XX", "description": "",
                                     "erwartungen": ""}


def test_die_konfiguration_wird_einmal_je_lauf_gelesen(monkeypatch) -> None:
    lesen: list[str] = []
    monkeypatch.setattr(eg, "load_persona_definitions", lambda: (lesen.append("p"), [])[1])
    monkeypatch.setattr(eg, "_persona_erwartungen", lambda pid: "")
    _judge_spy(monkeypatch)

    asyncio.run(eg.bewerte_gespraeche(_convs() + _convs()))

    assert lesen == ["p"]


def test_ein_ausfall_des_zug_judges_wird_vermerkt(monkeypatch) -> None:
    """GV4 bleibt: ein ausgefallener Gutachter kostet keine Note, sondern wird gezählt."""
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch, exc=RuntimeError("judge provider 500"))
    convs = _convs()

    zahl = asyncio.run(eg.bewerte_gespraeche(convs))

    assert zahl == {"zuege": 0, "ablaeufe": 1}
    for turn in convs[0]["turns"]:
        assert "judge" not in turn
        assert "judge provider 500" in turn["judge_failed"]


def test_ein_ausfall_des_ablauf_judges_wird_vermerkt(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch, ablauf_exc=RuntimeError("zu lang"))
    convs = _convs()

    zahl = asyncio.run(eg.bewerte_gespraeche(convs))

    assert zahl == {"zuege": 2, "ablaeufe": 0}
    assert "urteil" not in convs[0]
    assert "zu lang" in convs[0]["urteil_fehler"]


def test_ein_ablauf_ohne_antwort_bekommt_kein_urteil(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)
    convs = _convs()
    for turn in convs[0]["turns"]:
        turn["error"] = "down"

    asyncio.run(eg.bewerte_gespraeche(convs))

    assert calls["ablauf"] == [] and calls["zug"] == []
    assert convs[0]["urteil_fehler"] == "keine beantworteten Züge"


# ── summarize_golden_run ─────────────────────────────────────────────────
def test_headline_stays_deterministic_and_judge_is_reported_beside_it(
    monkeypatch,
) -> None:
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch)
    convs = _convs()
    asyncio.run(eg.bewerte_gespraeche(convs))
    gm = dict(_GM)

    summary = eg.summarize_golden_run(convs, target_turns=2, golden_metrics=gm)

    assert summary["avg_score"] == 1.0 == gm["overall_pass_rate"]
    assert summary["judge_avg"] == 0.5
    assert gm["judge_avg"] == 0.5 and gm["judged_turns"] == 2
    assert summary["golden_metrics"] is gm
    assert summary["target_turns"] == 2 and summary["current_activity"] == "Fertig"


def test_unjudged_run_carries_no_judge_average() -> None:
    gm = dict(_GM)

    summary = eg.summarize_golden_run(_convs(), target_turns=2, golden_metrics=gm)

    assert summary["avg_score"] == 1.0  # deterministic rate, unchanged
    assert "judge_avg" not in summary and "judge_avg" not in gm
    assert summary["total_judged_turns"] == 0
    assert summary["judge_failed_turns"] == 0
    assert summary["chat_error_turns"] == 0
    assert "chat_error_turns" not in gm


def test_chat_fehler_zuege_stehen_gezaehlt_im_summary() -> None:
    """Review-Befund 4 (2026-08-22): die CLI meldet Fehl-Züge über Exit 1 und
    stderr — der GESPEICHERTE Lauf hatte keinen Zähler und stand mit grüner
    harter Quote da, obwohl N Züge nie stattfanden. Gezählt wie
    ``judge_failed_turns``: immer im Summary, in der Scorecard nur wenn >0."""
    convs = _convs()
    convs[0]["turns"].append({"user": "x", "bot": "(chat error: weg)",
                              "debug": {}, "error": "weg"})
    gm = dict(_GM)

    summary = eg.summarize_golden_run(convs, target_turns=3, golden_metrics=gm)

    assert summary["chat_error_turns"] == 1
    assert gm["chat_error_turns"] == 1


def test_judge_failures_are_counted_not_averaged(monkeypatch) -> None:
    """GV4: fallen ALLE Judge-Aufrufe aus, bleibt ``judge_avg`` weg (nichts
    wurde bewertet) — aber der Ausfall steht gezählt im Summary und in der
    Scorecard, statt als 0.0-Schnitt wie ein Bot-Versagen auszusehen."""
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch, exc=RuntimeError("judge down"))
    convs = _convs()
    asyncio.run(eg.bewerte_gespraeche(convs))
    gm = dict(_GM)

    summary = eg.summarize_golden_run(convs, target_turns=2, golden_metrics=gm)

    assert summary["judge_failed_turns"] == 2
    assert gm["judge_failed_turns"] == 2
    assert "judge_avg" not in summary and "judge_avg" not in gm
    assert summary["avg_score"] == 1.0  # deterministisch, unberührt


def test_summary_fills_the_source_of_the_five_trend_series() -> None:
    summary = eg.summarize_golden_run(
        _convs(), target_turns=2, golden_metrics=dict(_GM),
    )

    # GET /eval/trends reads nothing but summary.classification_metrics; a gold
    # run that omits it leaves all five series permanently empty.
    cm = summary["classification_metrics"]
    assert cm["persona_total_judged"] == 2 and cm["persona_correct_rate"] == 1.0
    # Turn 2 asserts nothing, so the conversation-level intent stands in.
    assert cm["intent_total_judged"] == 2 and cm["intent_correct_rate"] == 1.0
    assert cm["llm_hint_present_count"] == 0  # no hint in the faked debug
    assert "matrix" in summary and "pattern_usage" in summary


def test_failed_run_still_summarizes_what_was_collected() -> None:
    summary = eg.summarize_golden_run(
        _convs(), target_turns=9, golden_metrics=dict(_GM),
        current_activity="Fehler: down",
    )

    assert summary["current_activity"] == "Fehler: down"
    assert summary["target_turns"] == 9
    assert summary["golden_metrics"]["turns"] == 2


# ── Kurzbericht (Paket 13, D2) ───────────────────────────────────────────
def test_der_kurzbericht_sieht_die_auswertung_des_laufs(monkeypatch) -> None:
    gesehen: dict = {}

    async def fake_bericht(auswertung, *, usage_acc=None):
        gesehen["auswertung"], gesehen["acc"] = auswertung, usage_acc
        return {"text": "Solide.", "baustellen": []}

    monkeypatch.setattr(eg, "kurzbericht", fake_bericht)
    convs = _convs()
    convs[0]["urteil"] = {"gesamt": 4, "statement": "gut", "skalen": {}}
    acc: dict = {}

    bericht = asyncio.run(eg.kurzbericht_erstellen(convs, usage_acc=acc))

    assert bericht == {"text": "Solide.", "baustellen": []}
    assert gesehen["auswertung"]["je_ablauf"][0]["statement"] == "gut"
    assert gesehen["acc"] is acc


def test_ein_ausfall_des_kurzberichts_wird_vermerkt(monkeypatch) -> None:
    async def kaputt(auswertung, *, usage_acc=None):
        raise RuntimeError("Bericht weg")

    monkeypatch.setattr(eg, "kurzbericht", kaputt)
    convs = _convs()
    convs[0]["urteil"] = {"gesamt": 4, "statement": "gut", "skalen": {}}
    bericht = asyncio.run(eg.kurzbericht_erstellen(convs))
    assert "Bericht weg" in bericht["fehler"]


def test_ohne_jedes_urteil_kein_kurzbericht(monkeypatch) -> None:
    """Review PR #18 (Eval #4): fiel der Judge ganz aus, schrieb ein bezahlter Aufruf eine
    Zusammenfassung von nichts."""
    aufrufe: list = []

    async def bericht(auswertung, *, usage_acc=None):
        aufrufe.append(auswertung)
        return {"text": "Alles bestens.", "baustellen": []}

    monkeypatch.setattr(eg, "kurzbericht", bericht)
    assert asyncio.run(eg.kurzbericht_erstellen(_convs())) == {"fehler": "keine Urteile"}
    assert aufrufe == []


# ── Kennzahlen für die Trends (Paket 13, D5) ─────────────────────────────
def test_kennzahlen_des_laufs_fuer_die_trends(monkeypatch) -> None:
    monkeypatch.setattr(eg, "load_pricing", lambda: None)
    convs = _convs()
    convs[0]["urteil"] = {"gesamt": 4, "skalen": {"ton": {"note": 5}}}
    convs[0]["turns"][0]["judge"] = {"gesamt": 3}
    convs[0]["turns"][0]["latency_ms"] = 1200
    convs[0]["turns"][0]["debug"] = {"token_usage": {
        "prompt_tokens": 100, "models": {"gpt-6-luna": {"prompt": 100, "completion": 10}},
        "prompts": {"agent.kopf": "aaa111"}}}

    k = eg.kennzahlen_des_laufs(convs)

    assert k["gesamt_mittel"] == 4.0 and k["skalen_mittel"] == {"ton": 5.0}
    assert k["zug_mittel"] == 3.0
    assert k["latenz_p50_ms"] == 1200
    assert k["kosten_je_zug"] is None          # ohne Preistafel kein Preis
    assert k["prompts"] == {"agent.kopf": ["aaa111"]}
