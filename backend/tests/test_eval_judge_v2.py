"""Paket 13 (C): Judge v2 — ein Urteil je Ablauf (ganzes Gespräch) und knapp je Zug.

Skalen 1–5 mit Verankerung, ein Kurzstatement und Auffälligkeiten je Ablauf. Der Judge sieht
das Gespräch, wie die Person es sah, und die aufgerufenen Werkzeuge — keine Kennungen der
Maschine (Muster, Intent, erkannte Persona). Nur so misst er beide Maschinen gleich.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from boerdi.services.eval import judge_v2, prompts_v2
from boerdi.services.eval.judge import JudgeError

_ZIELGRUPPE = {"id": "P-LEH", "label": "Lehrkraft", "description": "Unterrichtet an Schulen."}


def _gespraech() -> dict:
    return {
        "flow_id": "GV-LEH-1", "title": "Lehrkraft: Material", "zielgruppe": "P-LEH",
        "erwartung": "Erst Material, dann ein Lernpfad.",
        "turns": [
            {"user": "Ich suche Material zu Brüchen.", "bot": "Hier sind Treffer. " + "x" * 5000,
             "anwendungsfall": "suchen",
             "golden": {"expected": {"must_offer": "Treffer zu Brüchen"}},
             "debug": {"pattern": "M05 (Material-Suche gefiltert)", "intent": "I03 (Suche)",
                       "persona": "P-LEH", "engine": "pattern",
                       "tools_called": ["search_wlo_content (prefetch)", "respond_to_user"],
                       "werkzeug_ergebnisse": [{"tool": "search_wlo_content",
                                                "status": "success", "item_count": 8}]}},
            {"user": "Und ein Lernpfad?", "bot": "Hier ist der Lernpfad.",
             "anwendungsfall": "zusammenstellen",
             "golden": {"expected": {"must_offer": "Ein Lernpfad"}},
             "debug": {"pattern": "AGENT", "engine": "agent",
                       "tools_called": ["search_wlo_all", "zeige_dokument"]}},
        ],
    }


def _antwort(daten: dict | str):
    text = daten if isinstance(daten, str) else json.dumps(daten)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _skalen(note: int = 4) -> dict:
    return {k: {"note": note, "grund": f"{k} ok"} for k in prompts_v2.ABLAUF_SKALEN}


# ── Prompts ──────────────────────────────────────────────────────────────────

def test_ablauf_prompt_zeigt_das_gespraech_ohne_maschinen_kennungen() -> None:
    prompt = prompts_v2.ablauf_prompt(_gespraech(), _ZIELGRUPPE)
    for erwartet in ("Lehrkraft", "Erst Material, dann ein Lernpfad.",
                     "Ich suche Material zu Brüchen.", "Treffer zu Brüchen", "zusammenstellen",
                     "search_wlo_content", "search_wlo_all"):
        assert erwartet in prompt, erwartet
    for verboten in ("M05", "I03", "AGENT", "respond_to_user", "(prefetch)", "Muster-Suche"):
        assert verboten not in prompt, verboten
    for skala in prompts_v2.ABLAUF_SKALEN:
        assert skala in prompt


def test_ablauf_prompt_kuerzt_jede_antwort() -> None:
    prompt = prompts_v2.ablauf_prompt(_gespraech(), _ZIELGRUPPE)
    assert "x" * prompts_v2.ANTWORT_JE_ZUG not in prompt
    assert "x" * (prompts_v2.ANTWORT_JE_ZUG - 100) in prompt


def test_zug_prompt_traegt_den_verlauf_verdichtet() -> None:
    prompt = prompts_v2.zug_prompt(_gespraech(), 1, _ZIELGRUPPE)
    assert "Ich suche Material zu Brüchen." in prompt  # Vorgänger-Nachricht
    assert "x" * prompts_v2.VERLAUF_JE_ANTWORT not in prompt
    assert "Und ein Lernpfad?" in prompt and "Ein Lernpfad" in prompt
    assert "AGENT" not in prompt and "zeige_dokument" in prompt


def test_die_fassung_ist_stabil_und_kurz() -> None:
    assert len(prompts_v2.JUDGE_V2_FASSUNG) == 12
    assert prompts_v2.JUDGE_V2_FASSUNG == prompts_v2.fassung()


# ── Ablauf-Judge ─────────────────────────────────────────────────────────────

def _fake(monkeypatch, antwort) -> dict:
    gesehen: dict = {}

    async def chat_completion(**kw):
        gesehen.update(kw)
        if isinstance(antwort, Exception):
            raise antwort
        return _antwort(antwort)

    monkeypatch.setattr(judge_v2, "chat_completion", chat_completion)
    monkeypatch.setattr(judge_v2, "judge_model", lambda: "gpt-6-luna")
    return gesehen


def test_judge_ablauf_liest_skalen_statement_und_auffaelligkeiten(monkeypatch) -> None:
    gesehen = _fake(monkeypatch, {
        "skalen": _skalen(4), "gesamt": 4,
        "statement": "Guter Verlauf, der Lernpfad blieb dünn.",
        "auffaelligkeiten": [{"zug": 2, "art": "inhalt", "text": "Lernpfad ohne Material"}]})
    acc: dict = {}
    urteil = asyncio.run(judge_v2.judge_ablauf(_gespraech(), _ZIELGRUPPE, usage_acc=acc))
    assert urteil["skalen"]["verlauf"] == {"note": 4, "grund": "verlauf ok"}
    assert urteil["gesamt"] == 4
    assert urteil["statement"].startswith("Guter Verlauf")
    assert urteil["auffaelligkeiten"] == [
        {"zug": 2, "art": "inhalt", "text": "Lernpfad ohne Material"}]
    assert urteil["fassung"] == prompts_v2.JUDGE_V2_FASSUNG
    assert gesehen["usage_acc"] is acc and gesehen["phase"] == "judge_ablauf"
    assert gesehen["model"] == "gpt-6-luna" and gesehen["temperature"] == 0.0


def test_noten_werden_auf_eins_bis_fuenf_geklemmt(monkeypatch) -> None:
    skalen = _skalen(4)
    skalen["werkzeuge"] = {"note": 7, "grund": ""}
    skalen["sicherheit"] = {"note": 0, "grund": ""}
    _fake(monkeypatch, {"skalen": skalen, "gesamt": 9, "statement": "s",
                        "auffaelligkeiten": [{"zug": "x", "art": "erfunden", "text": "t"}]})
    urteil = asyncio.run(judge_v2.judge_ablauf(_gespraech(), _ZIELGRUPPE))
    assert urteil["skalen"]["werkzeuge"]["note"] == 5
    assert urteil["skalen"]["sicherheit"]["note"] == 1
    assert urteil["gesamt"] == 5
    assert urteil["auffaelligkeiten"] == [{"zug": None, "art": "sonstiges", "text": "t"}]


@pytest.mark.parametrize("antwort", [
    "kein json",
    "",
    {"skalen": {"zielgruppe": {"note": 4}}, "gesamt": 4, "statement": "s"},
    RuntimeError("Anbieter weg"),
])
def test_ein_unbrauchbares_urteil_wirft(monkeypatch, antwort) -> None:
    _fake(monkeypatch, antwort)
    with pytest.raises(JudgeError):
        asyncio.run(judge_v2.judge_ablauf(_gespraech(), _ZIELGRUPPE))


# ── Zug-Judge ────────────────────────────────────────────────────────────────

def test_judge_zug_liefert_skalen_und_die_alte_gesamtzahl(monkeypatch) -> None:
    gesehen = _fake(monkeypatch, {
        "skalen": {k: {"note": 5, "grund": ""} for k in prompts_v2.ZUG_SKALEN},
        "gesamt": 3, "notiz": "Lernpfad ohne Material."})
    urteil = asyncio.run(judge_v2.judge_zug(_gespraech(), 1, _ZIELGRUPPE))
    assert urteil["anliegen"] == 5 and urteil["gesamt"] == 3
    assert urteil["total"] == 0.5          # (3 − 1) / 4 — für Laufliste und Detail von heute
    assert urteil["notes"] == "Lernpfad ohne Material."
    assert urteil["fassung"] == prompts_v2.JUDGE_V2_FASSUNG
    assert gesehen["phase"] == "judge_zug"


def test_generative_laeufe_bleiben_bis_phase_g_beim_judge_v1() -> None:
    """Paket 13 (C6): der Judge v2 gilt zunächst nur für Golden-Läufe. Die generative Strecke
    (Persona × Intent) bewertet weiter mit dem Judge v1, bis Phase G sie umstellt — dieser
    Wächter fällt dann bewusst und wird mit ihr aufgelöst."""
    from boerdi.services.eval import judge, runner

    assert runner.judge_turn is judge.judge_turn


# ── Kurzbericht (D2) ─────────────────────────────────────────────────────────

_AUSWERTUNG = {
    "gesamt": {"gesamt_mittel": 3.5, "zug_mittel": 3.8, "skalen_mittel": {"verlauf": 2.5},
               "harte_quote": {"bestanden": 40, "geprueft": 46}, "ablaeufe": 2, "zuege": 5},
    "je_ablauf": [
        {"flow_id": "GV-LEH-1", "zielgruppe": "P-LEH", "gesamt": 4, "statement": "Gut.",
         "harte_quote": {"bestanden": 8, "geprueft": 8}, "urteil_fehler": ""},
        {"flow_id": "GV-LER-1", "zielgruppe": "P-LER", "gesamt": 2,
         "statement": "Duzt nicht, vergisst den Kontext.",
         "harte_quote": {"bestanden": 1, "geprueft": 3}, "urteil_fehler": ""},
    ],
    "matrix_zielgruppe_anwendungsfall": {"P-LER": {"erklaeren": {"mittel": 2.0, "n": 2}},
                                         "P-LEH": {"suchen": {"mittel": 4.5, "n": 2}}},
}


def test_bericht_prompt_nennt_kennzahlen_statements_und_schwache_zellen() -> None:
    prompt = prompts_v2.bericht_prompt(_AUSWERTUNG)
    for erwartet in ("3.5", "40/46", "GV-LER-1", "Duzt nicht, vergisst den Kontext.",
                     "P-LER × erklaeren: 2.0", "verlauf"):
        assert erwartet in prompt, erwartet
    assert "P-LEH × suchen" not in prompt  # stark genug, keine Baustelle


def test_kurzbericht_liest_text_und_hoechstens_drei_baustellen(monkeypatch) -> None:
    gesehen = _fake(monkeypatch, {
        "text": "Insgesamt solide. Schwach bei Lernenden.",
        "baustellen": [{"ablauf": "GV-LER-1", "text": "Anrede"}, {"ablauf": None, "text": "b"},
                       {"text": "c"}, {"text": "d"}]})
    acc: dict = {}
    bericht = asyncio.run(judge_v2.kurzbericht(_AUSWERTUNG, usage_acc=acc))
    assert bericht["text"].startswith("Insgesamt solide")
    assert bericht["baustellen"][0] == {"ablauf": "GV-LER-1", "text": "Anrede"}
    assert len(bericht["baustellen"]) == 3 and bericht["baustellen"][2]["ablauf"] is None
    assert gesehen["phase"] == "judge_bericht" and gesehen["usage_acc"] is acc


def test_ein_kurzbericht_ohne_text_wirft(monkeypatch) -> None:
    _fake(monkeypatch, {"baustellen": []})
    with pytest.raises(JudgeError):
        asyncio.run(judge_v2.kurzbericht(_AUSWERTUNG))
