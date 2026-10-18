"""Paket 13 (D1): Auswertung eines Golden-Laufs mit dem Judge v2 — rein, ohne Datenbank.

Je Ablauf (Skalen, Gesamt, Statement, harte Quote, Latenz, Kosten), gesamt, drei Matrizen
(Zielgruppe × Anwendungsfall aus den Zug-Noten, Ablauf × Skala, Persona × Intent nur für
Muster-Züge) und die Zeiten je Phase. Beim Lesen berechnet wie das Profil (``run_profile``):
eine später gepflegte Preistabelle gilt für alte Läufe mit.
"""

from __future__ import annotations

from boerdi.services.eval import auswertung_v2 as av


def _preis(model: str, prompt: int, cached: int, completion: int) -> float | None:
    return None if model == "unbekannt" else (prompt + completion) / 1000


def _zug(*, fall: str, gesamt: int | None, checks: dict, latenz: int, engine: str = "agent",
         persona: str = "", intent: str = "", fehler: bool = False, models=None) -> dict:
    zug: dict = {
        "user": "u", "bot": "b", "anwendungsfall": fall, "latency_ms": latenz,
        "golden": {"checks": checks, "observed": {"tools_called": ["search_wlo_all"]}},
        "debug": {"engine": engine, "persona": persona, "intent": intent,
                  "pattern": "M05 (Suche)" if engine == "pattern" else "AGENT",
                  "tools_called": ["search_wlo_all"],
                  "token_usage": {
                      "prompt_tokens": 1000, "completion_tokens": 200,
                      "models": models or {"gpt-6-luna": {"prompt": 1000, "cached": 0,
                                                          "completion": 200}},
                      "zeiten_ms": {"assess": 300, "respond": 4000, "respond.werkzeuge": 1500},
                      "per_phase": {"agent": {"ms": 3500, "calls": 2}}}},
    }
    if gesamt is not None:
        zug["judge"] = {"gesamt": gesamt, "total": (gesamt - 1) / 4}
    if fehler:
        zug["error"] = "down"
    return zug


def _lauf() -> dict:
    return {
        "summary": {
            "judge_fassung": "abc123def456",
            "judge_usage": {"calls": 4, "models": {"gpt-6-luna": {
                "prompt": 2000, "cached": 0, "completion": 1000}}},
        },
        "conversations": [
            {"flow_id": "GV-LEH-1", "title": "Lehrkraft", "zielgruppe": "P-LEH",
             "urteil": {"skalen": {"zielgruppe": {"note": 5}, "werkzeuge": {"note": 3}},
                        "gesamt": 4, "statement": "Gut.",
                        "auffaelligkeiten": [{"zug": 2, "art": "inhalt", "text": "dünn"}]},
             "turns": [
                 _zug(fall="suchen", gesamt=5, latenz=2000,
                      checks={"register": True, "structure": True, "host": False}),
                 _zug(fall="zusammenstellen", gesamt=3, latenz=6000,
                      checks={"register": True, "structure": False}),
             ]},
            {"flow_id": "GV-LER-1", "title": "Lernende", "zielgruppe": "P-LER",
             "urteil_fehler": "Judge weg",
             "turns": [
                 _zug(fall="suchen", gesamt=2, latenz=4000, engine="pattern",
                      persona="P-LER (Lernende)", intent="I03 (Suche)",
                      checks={"register": False}),
                 _zug(fall="erklaeren", gesamt=None, latenz=500, checks={}, fehler=True),
             ]},
        ],
    }


def test_je_ablauf() -> None:
    a = av.auswerten(_lauf(), _preis)
    leh, ler = a["je_ablauf"]
    assert leh["flow_id"] == "GV-LEH-1" and leh["zielgruppe"] == "P-LEH"
    assert leh["skalen"] == {"zielgruppe": 5, "werkzeuge": 3}
    assert leh["gesamt"] == 4 and leh["statement"] == "Gut."
    assert leh["auffaelligkeiten"][0]["zug"] == 2
    assert leh["harte_quote"] == {"bestanden": 3, "geprueft": 4}  # host zählt nicht
    assert leh["zug_mittel"] == 4.0
    assert leh["latenz_p50_ms"] == 2000
    assert leh["kosten"] == 2.4
    assert ler["gesamt"] is None and ler["urteil_fehler"] == "Judge weg"
    assert ler["chat_fehler"] == 1


def test_gesamt() -> None:
    g = av.auswerten(_lauf(), _preis)["gesamt"]
    assert g["ablaeufe"] == 2 and g["zuege"] == 4
    assert g["gesamt_mittel"] == 4.0            # nur bewertete Abläufe
    assert g["skalen_mittel"] == {"zielgruppe": 5.0, "werkzeuge": 3.0}
    assert g["zug_mittel"] == round((5 + 3 + 2) / 3, 2)
    assert g["harte_quote"] == {"bestanden": 3, "geprueft": 5}
    assert g["latenz"]["p50_ms"] == 2000 and g["latenz"]["p95_ms"] == 6000
    assert g["chat_fehler"] == 1 and g["judge_fehler"] == 1
    assert g["kosten_je_zug"] == 1.2
    assert g["judge_kosten"] == 3.0 and g["judge_aufrufe"] == 4
    assert g["judge_fassung"] == "abc123def456"


def test_matrizen() -> None:
    a = av.auswerten(_lauf(), _preis)
    za = a["matrix_zielgruppe_anwendungsfall"]
    assert za["P-LEH"]["suchen"] == {"mittel": 5.0, "n": 1}
    assert za["P-LEH"]["zusammenstellen"] == {"mittel": 3.0, "n": 1}
    assert za["P-LER"]["suchen"] == {"mittel": 2.0, "n": 1}
    assert "erklaeren" not in za["P-LER"]       # Fehlzug ohne Note
    assert a["matrix_ablauf_skala"]["GV-LEH-1"] == {"zielgruppe": 5, "werkzeuge": 3, "gesamt": 4}
    assert "GV-LER-1" not in a["matrix_ablauf_skala"]
    assert a["matrix_persona_intent"] == {"P-LER": {"I03": {"mittel": 2.0, "n": 1}}}


def test_zeiten_je_phase() -> None:
    z = av.auswerten(_lauf(), _preis)["zeiten"]
    assert z["knoten"]["respond"] == {"p50_ms": 4000, "p95_ms": 4000, "n": 3}
    assert "respond.werkzeuge" in z["schritte"]
    assert z["llm"]["agent"]["n"] == 3


def test_ein_unbekannter_preis_gibt_keine_kosten() -> None:
    lauf = _lauf()
    lauf["conversations"][0]["turns"][0]["debug"]["token_usage"]["models"] = {
        "unbekannt": {"prompt": 1, "cached": 0, "completion": 1}}
    a = av.auswerten(lauf, _preis)
    assert a["je_ablauf"][0]["kosten"] is None
    assert a["gesamt"]["kosten_je_zug"] is None


def test_ein_lauf_ohne_judge_v2_hat_leere_matrizen() -> None:
    a = av.auswerten({"summary": {}, "conversations": []}, _preis)
    assert a["je_ablauf"] == [] and a["matrix_zielgruppe_anwendungsfall"] == {}
    assert a["gesamt"]["gesamt_mittel"] is None and a["gesamt"]["judge_kosten"] is None
