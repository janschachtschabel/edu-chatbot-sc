"""Paket 13 (D5): Trends je Skala, Gesamt, Latenz und Kosten — mit Wechselmarken.

``trends_v2`` liest nur Summaries (``kennzahlen_v2`` und ``messbedingungen``), wie die übrigen
Trends die Transkripte nicht laden. Ein Lauf ohne Kennzahlen v2 gibt keinen Punkt (Lücke statt
0,0). Eine Wechselmarke sagt, was sich gegenüber dem Lauf davor änderte — Modell, Weg,
Konfiguration, Master-Skill, Prompt-Bausteine —, damit ein Sprung nicht als Verbesserung gilt.
"""

from __future__ import annotations

from boerdi.services.eval import trends_v2


def _summary(*, gesamt=4.0, modell="gpt-6-luna", konfig="k1", kopf="aaa111",
             latenz=2000, kosten=0.01) -> dict:
    return {
        "messbedingungen": {"maschine": "agent", "weg": {"modell": modell},
                            "konfiguration": {"hash": konfig}},
        "kennzahlen_v2": {"gesamt_mittel": gesamt, "zug_mittel": gesamt,
                          "skalen_mittel": {"ton": gesamt, "verlauf": 3.0},
                          "latenz_p50_ms": latenz, "kosten_je_zug": kosten,
                          "prompts": {"agent.kopf": [kopf]}},
    }


def _laeufe() -> list[tuple[str, str, dict]]:
    return [("r1", "2026-10-01", _summary(gesamt=3.0)),
            ("r2", "2026-10-02", _summary(gesamt=4.0, modell="gpt-6", kopf="bbb222")),
            ("r3", "2026-10-03", _summary(gesamt=4.5, modell="gpt-6", kopf="bbb222",
                                          konfig="k2"))]


def test_reihen_je_kennzahl() -> None:
    t = trends_v2.reihen(_laeufe())
    assert [p["value"] for p in t["gesamt"]] == [3.0, 4.0, 4.5]
    assert [p["run_id"] for p in t["gesamt"]] == ["r1", "r2", "r3"]
    assert [p["value"] for p in t["skalen"]["verlauf"]] == [3.0, 3.0, 3.0]
    assert [p["value"] for p in t["latenz_p50_ms"]] == [2000, 2000, 2000]
    assert t["kosten_je_zug"][0] == {"run_id": "r1", "created_at": "2026-10-01", "value": 0.01}


def test_wechselmarken_nennen_was_sich_aenderte() -> None:
    t = trends_v2.reihen(_laeufe())
    assert t["wechsel"] == [
        {"run_id": "r2", "created_at": "2026-10-02",
         "felder": ["modell"], "prompts": ["agent.kopf"]},
        {"run_id": "r3", "created_at": "2026-10-03", "felder": ["konfiguration"], "prompts": []},
    ]


def test_laeufe_ohne_kennzahlen_v2_geben_keinen_punkt() -> None:
    laeufe = [("alt", "2026-09-01", {"messbedingungen": {"chat_model": "gpt-5"}}),
              *_laeufe()]
    t = trends_v2.reihen(laeufe)
    assert [p["run_id"] for p in t["gesamt"]] == ["r1", "r2", "r3"]
    # Gegen einen Lauf ohne Kennzahlen gibt es keine Prompt-Marke (nichts erfinden).
    assert t["wechsel"][0]["run_id"] == "r1" and t["wechsel"][0]["prompts"] == []


def test_lauf_ohne_judge_hat_latenz_aber_keine_note() -> None:
    t = trends_v2.reihen([("r1", "d", _summary(gesamt=None))])
    assert t["gesamt"] == [] and t["latenz_p50_ms"][0]["value"] == 2000
    assert t["wechsel"] == []
