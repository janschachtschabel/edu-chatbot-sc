"""Paket 13 (D4): Läufe vergleichen — Skalen, Gesamt und was sich zwischen ihnen änderte.

``vergleich_v2`` ist rein: Bewertung je Lauf (aus ``auswertung_v2``), Mittel je Maschine und
die Unterschiede der Messbedingungen gegen den ersten Lauf — Modell, Weg, Stände, geänderte
Konfigurationsbereiche und Prompt-Bausteine (mit beiden Prüfsummen für den Text-Unterschied).
"""

from __future__ import annotations

from boerdi.services.eval import vergleich_v2 as vv


def _preis(model: str, prompt: int, cached: int, completion: int) -> float | None:
    return 0.0


def _lauf(*, gesamt: int | None = 4, modell: str = "gpt-6-luna", kopf: str = "aaa111",
          bereich_hash: str = "h1", commit: str = "c1") -> dict:
    turn = {"user": "u", "bot": "b", "anwendungsfall": "suchen", "latency_ms": 1000,
            "golden": {"checks": {"register": True}},
            "debug": {"engine": "agent", "token_usage": {
                "prompts": {"agent.kopf": kopf, "agent.master_skill": "sss222"}}}}
    conv = {"flow_id": "GV-1", "zielgruppe": "P-LEH", "turns": [turn]}
    if gesamt is not None:
        turn["judge"] = {"gesamt": gesamt}
        conv["urteil"] = {"gesamt": gesamt, "skalen": {"ton": {"note": gesamt}}}
    return {
        "summary": {
            "judge_fassung": "jf1",
            "messbedingungen": {
                "maschine": "agent",
                "weg": {"anbieter": "openai", "modell": modell, "api": "responses",
                        "reasoning_effort": "low"},
                "judge_weg": {"modell": "gpt-6-luna"},
                "app": {"version": "0.4", "commit": commit},
                "konfiguration": {"hash": "k-" + bereich_hash, "bereiche": {
                    "persona": {"hash": bereich_hash}, "routing": {"hash": "r1"}}},
                "gold_flows": {"hash": "g1"},
                "master_skill": {"enabled": True, "sha256": "abcdef123456789"},
            },
        },
        "conversations": [conv],
    }


def test_bewertung_je_lauf() -> None:
    b = vv.bewertung(_lauf(gesamt=4), _preis)
    assert b["gesamt_mittel"] == 4.0 and b["skalen_mittel"] == {"ton": 4.0}
    assert b["zug_mittel"] == 4.0 and b["harte_quote"] == {"bestanden": 1, "geprueft": 1}


def test_ohne_judge_v2_keine_bewertung() -> None:
    assert vv.bewertung(_lauf(gesamt=None), _preis) is None


def test_mittel_je_maschine() -> None:
    je = vv.je_maschine([("agent", vv.bewertung(_lauf(gesamt=4), _preis)),
                         ("agent", vv.bewertung(_lauf(gesamt=2), _preis)),
                         ("pattern", None)])
    assert je == {"agent": {"laeufe": 2, "gesamt_mittel": 3.0, "zug_mittel": 3.0,
                            "skalen_mittel": {"ton": 3.0}}}


def test_gleiche_bedingungen_keine_unterschiede() -> None:
    u = vv.unterschiede([("r1", _lauf()), ("r2", _lauf())])
    assert u == {"referenz": "r1", "laeufe": [
        {"run": "r2", "felder": [], "bereiche": [], "prompts": []}]}


def test_unterschiede_nennen_modell_bereich_und_prompt() -> None:
    u = vv.unterschiede([("r1", _lauf()),
                         ("r2", _lauf(modell="gpt-6", kopf="bbb222", bereich_hash="h2",
                                      commit="c2"))])
    lauf = u["laeufe"][0]
    assert {"feld": "modell", "a": "gpt-6-luna", "b": "gpt-6"} in lauf["felder"]
    assert {"feld": "app_commit", "a": "c1", "b": "c2"} in lauf["felder"]
    assert {"feld": "konfiguration", "a": "k-h1", "b": "k-h2"} in lauf["felder"]
    assert lauf["bereiche"] == ["persona"]
    assert lauf["prompts"] == [{"art": "agent.kopf", "a": ["aaa111"], "b": ["bbb222"]}]


def test_ein_lauf_ohne_messbedingungen_v2_vergleicht_was_da_ist() -> None:
    alt = {"summary": {"messbedingungen": {"chat_model": "gpt-5"}}, "conversations": []}
    u = vv.unterschiede([("r1", alt), ("r2", _lauf())])
    felder = {f["feld"]: f for f in u["laeufe"][0]["felder"]}
    assert felder["modell"] == {"feld": "modell", "a": "gpt-5", "b": "gpt-6-luna"}
    assert u["laeufe"][0]["bereiche"] == []   # alt kennt keine Bereiche: nichts erfinden
    # Review PR #18 (Eval #2): was der alte Lauf nicht kannte, ist unbekannt, nicht geändert.
    for unbekannt in ("api", "app_version", "app_commit", "konfiguration", "gold_flows"):
        assert unbekannt not in felder, unbekannt


def test_ein_lauf_ueber_die_route_ist_eine_andere_bedingung() -> None:
    """Gesamt-Review Paket 17 (AB1): die Route kann still auf ein anderes Modell ausweichen —
    ein Lauf mit und einer ohne Route galten als „gleiche Bedingungen“."""
    ohne, mit = _lauf(), _lauf()
    ohne["summary"]["messbedingungen"]["weg"]["route"] = None  # seit Paket 17: ohne Router
    mit["summary"]["messbedingungen"]["weg"]["route"] = "boerdi-test-luna"
    def felder(a, b):
        return [f["feld"] for f in vv.unterschiede([("r1", a), ("r2", b)])["laeufe"][0]["felder"]]

    assert "route" in felder(ohne, mit)
    # Ein Lauf von vor Paket 17 kennt das Feld nicht: unbekannt, nicht geändert.
    assert "route" not in felder(_lauf(), mit)
