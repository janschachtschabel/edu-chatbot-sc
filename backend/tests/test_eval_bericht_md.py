"""Paket 13 (D3): ein Golden-Lauf als Markdown-Bericht — rein, ohne Datenbank.

Abschnitte in fester Reihenfolge (Messbedingungen, Kurzbericht, Gesamt, Matrizen, Abläufe,
Zeiten), Matrizen als Tabellen, und Text aus Judge oder Gesprächen kann die Struktur nicht
brechen: Sonderzeichen sind entschärft, Zeilenumbrüche in Zellen gefaltet.
"""

from __future__ import annotations

from boerdi.services.eval import bericht_md


def _detail() -> dict:
    return {
        "id": "run-1", "created_at": "2026-10-17T10:00:00Z", "status": "done",
        "mode": "golden", "engine": "agent",
        "summary": {
            "messbedingungen": {
                "provider": "openai", "chat_model": "gpt-6-luna", "maschine": "agent",
                "weg": {"anbieter": "openai", "modell": "gpt-6-luna", "api": "responses",
                        "reasoning_effort": "low"},
                "judge_weg": {"anbieter": "openai", "modell": "gpt-6-luna", "api": "responses"},
                "app": {"version": "0.4", "commit": "abc1234"},
                "konfiguration": {"hash": "k0nf1g", "bereiche": {}},
                "gold_flows": {"hash": "g0ld", "ids": ["GV-LEH-1"]},
                "master_skill": {"version": "7"},
            },
            "judge_fassung": "f4ssung",
            "kurzbericht": {"text": "Trägt meistens.",
                            "baustellen": [{"ablauf": "GV-LEH-1", "text": "Lernpfad fehlt"}]},
        },
        "auswertung": {
            "gesamt": {"gesamt_mittel": 3.5, "zug_mittel": 3.8, "ablaeufe": 1, "zuege": 2,
                       "skalen_mittel": {"zielgruppe": 4.0},
                       "harte_quote": {"bestanden": 3, "geprueft": 4},
                       "latenz": {"p50_ms": 2000, "p95_ms": 6000}, "kosten_je_zug": 0.0123,
                       "chat_fehler": 0, "judge_fehler": 0, "judge_kosten": 0.05},
            "je_ablauf": [{
                "flow_id": "GV-LEH-1", "title": "Lehrkraft | Lernpfad", "zielgruppe": "P-LEH",
                "skalen": {"zielgruppe": 4}, "gesamt": 3,
                "statement": "Gut *gestartet*,\naber <b>dünn</b>.",
                "auffaelligkeiten": [{"zug": 2, "art": "inhalt", "text": "kein [Link](x)"}],
                "urteil_fehler": "", "harte_quote": {"bestanden": 3, "geprueft": 4},
                "zug_mittel": 3.8, "latenz_p50_ms": 2000, "kosten": 0.02,
            }],
            "matrix_zielgruppe_anwendungsfall": {"P-LEH": {"suchen": {"mittel": 4.0, "n": 1},
                                                           "zusammenstellen": {"mittel": 2.0,
                                                                               "n": 1}}},
            "matrix_ablauf_skala": {"GV-LEH-1": {"zielgruppe": 4, "gesamt": 3}},
            "matrix_persona_intent": {},
            "zeiten": {"knoten": {"respond": {"p50_ms": 4000, "p95_ms": 5000, "n": 2}},
                       "schritte": {}, "llm": {}},
        },
    }


def test_abschnitte_in_fester_reihenfolge() -> None:
    md = bericht_md.render(_detail())
    titel = [z for z in md.splitlines() if z.startswith("## ")]
    assert titel == ["## Messbedingungen", "## Kurzbericht", "## Gesamt",
                     "## Zielgruppe × Anwendungsfall", "## Ablauf × Skala", "## Abläufe",
                     "## Zeiten"]
    assert md.startswith("# Evaluationsbericht run-1")


def test_messbedingungen_nennen_modell_weg_und_staende() -> None:
    md = bericht_md.render(_detail())
    assert "gpt-6-luna" in md and "responses" in md and "reasoning_effort=low" in md
    for stand in ("abc1234", "k0nf1g", "g0ld", "f4ssung"):
        assert stand in md


def test_matrizen_sind_tabellen() -> None:
    md = bericht_md.render(_detail())
    assert "| Zielgruppe | suchen | zusammenstellen |" in md
    assert "| P-LEH | 4.0 (1) | 2.0 (1) |" in md
    assert "| GV-LEH-1 | 4 | 3 |" in md


def test_text_bricht_die_struktur_nicht() -> None:
    md = bericht_md.render(_detail())
    assert "Lehrkraft \\| Lernpfad" in md
    assert "Gut \\*gestartet\\*, aber \\<b\\>dünn\\</b\\>." in md
    assert "kein \\[Link\\](x)" in md
    assert "<b>" not in md


def test_persona_intent_nur_mit_muster_zuegen() -> None:
    d = _detail()
    assert "## Persona × Intent" not in bericht_md.render(d)
    d["auswertung"]["matrix_persona_intent"] = {"P-LER": {"I03": {"mittel": 2.0, "n": 1}}}
    assert "## Persona × Intent (nur Muster)" in bericht_md.render(d)


def test_ohne_kurzbericht_und_auswertung_bleibt_der_bericht_lesbar() -> None:
    d = _detail()
    d["summary"].pop("kurzbericht")
    d["summary"]["kurzbericht_fehler"] = "Judge weg"
    d.pop("auswertung")
    md = bericht_md.render(d)
    assert "Kein Kurzbericht: Judge weg" in md
    assert "Keine Auswertung" in md


def test_der_weg_nennt_die_route() -> None:
    """Gesamt-Review Paket 17 (AB1)."""
    assert "route=boerdi-test-luna" in bericht_md._weg(
        {"anbieter": "b-api-openai", "modell": "gpt-6-luna", "route": "boerdi-test-luna"})
