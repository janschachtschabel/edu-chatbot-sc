"""ST-7b (2026-09-27): das Profil eines Eval-Laufs im Studio.

Judge-Achsen, Zugdauer, Token und Kosten standen in den gespeicherten Läufen,
gezeigt hat sie das Studio nicht; Kosten rechnete nur das Werkzeug K0-1. Das
Detail eines Laufs trägt jetzt ``profile`` — mit denselben Kennzahlen, die K0-1
je Maschine rechnet, und nach der gepflegten Preistafel.
"""

from __future__ import annotations

import asyncio

import pytest

import boerdi.services.eval.run_profile as run_profile_mod
from boerdi.db.models import EvalRun
from boerdi.domain.config_models import PricingArea
from boerdi.services.eval.run_profile import (
    fallback_texts,
    get_run_with_profile,
    price_from_table,
    run_profile,
)

_TAFEL = PricingArea.model_validate({
    "currency": "USD",
    "models": {"gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50}},
})


def _zug(latency: int, judge: dict | None = None, *, model: str = "gpt-6-luna") -> dict:
    zug = {"user": "u", "bot": "Antwort", "latency_ms": latency,
           "debug": {"token_usage": {
               "prompt_tokens": 1000, "cached_tokens": 0, "completion_tokens": 100,
               "models": {model: {"prompt": 1000, "cached": 0, "completion": 100}}}},
           "golden": {"checks": {"qr": True, "text": False},
                      "observed": {"tools_called": [], "content_len": 7}}}
    if judge is not None:
        zug["judge"] = judge
    return zug


def _detail(*zuege: dict) -> dict:
    return {"id": "eval-1", "status": "done", "summary": {},
            "conversations": [{"flow_id": "GV-LEH-1", "turns": list(zuege)}]}


def test_ersatzsaetze_erkennen_eine_gerenderte_interne_fehlerblase() -> None:
    """Review-Befund 2026-09-26 (umgezogen aus dem K0-1-Werkzeug): die Vorlage
    trägt ``({kind})``, die echte Blase „(RuntimeError)" — der wörtliche
    Vergleich traf nie."""
    from boerdi.i18n.bot_text import bot_text

    blase = bot_text("de", "error.internal", nummer="4f2a9c01d3b7")
    assert any(satz in blase for satz in fallback_texts())


@pytest.mark.parametrize("schluessel", ["error.internal", "error.answerFailed"])
@pytest.mark.parametrize("sprache", ["de", "en"])
def test_die_auswertung_erkennt_die_blasen_mit_fehlernummer(schluessel, sprache) -> None:
    """Paket 18C/D (3.4): die Nummer steht am Satzende, der Satz davor wird erkannt."""
    from boerdi.i18n.bot_text import bot_text

    blase = bot_text(sprache, schluessel, nummer="4f2a9c01d3b7")
    assert any(satz in blase for satz in fallback_texts())


def test_preis_aus_der_tafel_und_keiner_ohne_tafel() -> None:
    preis = price_from_table(_TAFEL)
    assert preis("gpt-6-luna", 1000, 0, 100) == pytest.approx(150e-6)
    assert preis("unbekannt-1", 1000, 0, 100) is None
    # Unlesbare Tafel: kein Preis, aber auch kein Absturz des Details.
    assert price_from_table(None)("gpt-6-luna", 1000, 0, 100) is None


def test_profil_nennt_qualitaet_dauer_kosten_und_robustheit(monkeypatch) -> None:
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: _TAFEL)

    profil = run_profile(_detail(
        _zug(2000, {"safety": 2, "auftrag_erfuellt": 1, "pattern_match": None}),
        _zug(40000, {"safety": 1, "auftrag_erfuellt": 2, "pattern_match": None}),
    ))

    assert profil["currency"] == "USD"
    assert profil["quality"]["hard_rate"] == 0.5          # qr ja, text nein
    assert profil["quality"]["axes"]["safety"] == 1.5
    assert profil["quality"]["axes"]["pattern_match"] is None  # Agent: nicht bewertet
    assert profil["speed"] == {"p50_ms": 2000, "p95_ms": 40000,
                               "over_30s": 0.5, "over_90s": 0}
    assert profil["cost"]["cost_per_turn"] == pytest.approx(150e-6)
    assert profil["cost"]["cost_total"] == pytest.approx(300e-6)
    assert profil["robustness"]["turns"] == 2


def test_ohne_gepflegten_preis_keine_kosten_aber_die_modellnamen(monkeypatch) -> None:
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: _TAFEL)

    profil = run_profile(_detail(_zug(1000, model="unbekannt-1")))

    assert profil["cost"]["cost_per_turn"] is None
    assert profil["cost"]["price_unavailable"] == ["unbekannt-1"]


def test_unlesbare_preistafel_nennt_keine_waehrung(monkeypatch) -> None:
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: None)

    profil = run_profile(_detail(_zug(1000)))

    assert profil["currency"] is None
    assert profil["cost"]["cost_per_turn"] is None


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    def __init__(self, row):
        self.row = row

    async def execute(self, _stmt):
        return _Result(self.row)


def test_das_detail_traegt_das_profil(monkeypatch) -> None:
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: _TAFEL)
    zeile = EvalRun(id="eval-1", status="done", mode="golden", config={"engine": "agent"},
                    totals={"total_turns": 1, "avg_score": 1.0}, summary={},
                    conversations=_detail(_zug(1000))["conversations"])

    detail = asyncio.run(get_run_with_profile(_Session(zeile), "eval-1"))

    assert detail["id"] == "eval-1" and detail["engine"] == "agent"
    assert detail["profile"]["speed"]["p50_ms"] == 1000



def test_ein_golden_detail_traegt_die_auswertung_v2(monkeypatch) -> None:
    """Paket 13 (D1): beim Lesen berechnet wie das Profil, mit derselben Preistafel."""
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: _TAFEL)
    convs = _detail(_zug(1000, {"gesamt": 4, "total": 0.75}))["conversations"]
    convs[0]["zielgruppe"] = "P-LEH"
    convs[0]["turns"][0]["anwendungsfall"] = "suchen"
    zeile = EvalRun(id="eval-2", status="done", mode="golden", config={"engine": "agent"},
                    totals={}, summary={}, conversations=convs)

    detail = asyncio.run(get_run_with_profile(_Session(zeile), "eval-2"))

    assert detail["auswertung"]["matrix_zielgruppe_anwendungsfall"]["P-LEH"]["suchen"] == {
        "mittel": 4.0, "n": 1}
    assert detail["auswertung"]["gesamt"]["kosten_je_zug"] == detail["profile"]["cost"][
        "cost_per_turn"]


def test_ein_generativer_lauf_hat_keine_auswertung_v2(monkeypatch) -> None:
    monkeypatch.setattr(run_profile_mod, "load_pricing", lambda: _TAFEL)
    zeile = EvalRun(id="eval-3", status="done", mode="generative", config={},
                    totals={}, summary={}, conversations=[])
    detail = asyncio.run(get_run_with_profile(_Session(zeile), "eval-3"))
    assert "auswertung" not in detail


@pytest.mark.parametrize("blase", [
    "Da ist intern etwas schiefgelaufen (RuntimeError). Versuch es nochmal — wenn es bestehen "
    "bleibt, gib mir kurz Bescheid.",
    "Something went wrong on our side (RuntimeError). Try again — if it keeps happening, let "
    "me know.",
    "Ich konnte gerade keine Antwort erzeugen (TimeoutError). Versuch es nochmal — meistens "
    "klappt es beim zweiten Anlauf.",
])
def test_auch_blasen_von_vor_der_fehlernummer_werden_erkannt(blase) -> None:
    """Review Phase 3: das Profil alter Läufe wird beim Lesen neu gerechnet — ohne die alten
    Satzanfänge fiele ihre Robustheit nach dem Deploy still."""
    assert any(satz in blase for satz in fallback_texts())
