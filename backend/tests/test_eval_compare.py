"""ST-7c (2026-09-27): Läufe im Studio vergleichen — mit der Rechnung von K0-1.

Bis dahin verglich nur das Werkzeug ``evals/engine_matrix.py`` Maschinen, als
Markdown auf der Platte. ``GET /api/eval/compare?ids=…`` rechnet dieselbe
Auswertung (``engine_metrics.evaluate``) über Läufe, die das Studio auswählt,
gruppiert nach der Maschine jedes Laufs. Warnungen kommen als Codes: das Studio
spricht zwei Sprachen, K0-1s Sätze nur eine.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

import boerdi.services.eval.engine_compare as compare_mod
from boerdi.api.deps import get_session
from boerdi.db.models import EvalRun
from boerdi.domain.config_models import PricingArea
from boerdi.main import create_app
from boerdi.services.eval.engine_compare import compare_runs
from boerdi.settings import get_settings

_TAFEL = PricingArea.model_validate({
    "currency": "USD",
    "models": {"gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50}},
})


def _zug(ok: bool, latency: int, model: str = "gpt-6-luna") -> dict:
    return {"user": "u", "bot": "Antwort", "latency_ms": latency,
            "judge": {"auftrag_erfuellt": 2 if ok else 0},
            "debug": {"token_usage": {
                "prompt_tokens": 1000, "cached_tokens": 0, "completion_tokens": 100,
                "models": {model: {"prompt": 1000, "cached": 0, "completion": 100}}}},
            "golden": {"checks": {"qr": ok},
                       "observed": {"tools_called": [], "content_len": 7}}}


def _lauf(run_id: str, engine: str, *, ok: bool = True, latency: int = 1000,
          status: str = "done", skill: bool | None = True, sha: str = "aaa",
          model: str = "gpt-6-luna", config: dict | None = None) -> EvalRun:
    return EvalRun(
        id=run_id, status=status, mode="golden",
        config=config if config is not None else {"engine": engine,
                                                  "engine_effective": engine},
        totals={"total_turns": 1, "avg_score": 1.0},
        summary={"engine": engine, "messbedingungen": {
            "provider": "openai", "chat_model": "gpt-6-luna",
            "master_skill": {"enabled": skill, "sha256": sha}}},
        conversations=[{"flow_id": "GV-LEH-1", "turns": [_zug(ok, latency, model)]}],
    )


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Session:
    """Liefert die Zeilen, deren Kennung die Anfrage nennt — die Auswahl selbst
    ist SQL (``id IN (…)``) und im pg-Test abgedeckt."""

    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _Result(self.rows)


@pytest.fixture(autouse=True)
def _preistafel(monkeypatch):
    monkeypatch.setattr(compare_mod, "load_pricing", lambda: _TAFEL)


def _vergleich(rows, ids):
    return asyncio.run(compare_runs(_Session(rows), ids))


def test_gruppiert_nach_maschine_und_rechnet_k0_kennzahlen() -> None:
    rows = [_lauf("eval-m1", "pattern"), _lauf("eval-m2", "pattern", ok=False),
            _lauf("eval-a1", "agent", latency=4000), _lauf("eval-a2", "agent", latency=6000)]

    out = _vergleich(rows, ["eval-m1", "eval-m2", "eval-a1", "eval-a2"])

    assert set(out["engines"]) == {"pattern", "agent"}
    muster, agent = out["engines"]["pattern"], out["engines"]["agent"]
    assert muster["runs"] == 2 and agent["runs"] == 2
    assert muster["quality"]["hard_rate"] == 0.5
    assert muster["hard_rate_runs"] == [1.0, 0.0]
    # Derselbe Zug kippt zwischen den Wiederholungen — die Übereinstimmung sagt es.
    assert muster["determinism"]["check_agreement"] == 0.0
    assert agent["determinism"]["check_agreement"] == 1.0
    assert agent["speed"]["p50_ms"] == 4000
    assert agent["cost"]["cost_per_turn"] == pytest.approx(150e-6)
    assert out["currency"] == "USD"
    assert "R2a" in out["rules"]
    assert [(r["id"], r["engine"], r["counted"]) for r in out["runs"]] == [
        ("eval-m1", "pattern", True), ("eval-m2", "pattern", True),
        ("eval-a1", "agent", True), ("eval-a2", "agent", True)]
    assert out["warnings"] == []


def test_unfertige_unbekannte_und_fehlende_laeufe_zaehlen_nicht_und_sagen_warum() -> None:
    rows = [_lauf("eval-m1", "pattern"), _lauf("eval-m2", "pattern"),
            _lauf("eval-lauf", "agent", status="running"),
            _lauf("eval-alt", "", config={"engine": "default"})]

    out = _vergleich(rows, ["eval-m1", "eval-m2", "eval-lauf", "eval-alt", "eval-weg"])

    assert set(out["engines"]) == {"pattern"}
    assert {"code": "not_done", "run": "eval-lauf", "status": "running"} in out["warnings"]
    assert {"code": "engine_unknown", "run": "eval-alt"} in out["warnings"]
    assert {"code": "not_found", "run": "eval-weg"} in out["warnings"]
    gezaehlt = {r["id"]: r["counted"] for r in out["runs"]}
    assert gezaehlt == {"eval-m1": True, "eval-m2": True,
                        "eval-lauf": False, "eval-alt": False}


def test_verschiedene_bedingungen_und_agent_ohne_master_skill() -> None:
    rows = [_lauf("eval-a1", "agent", sha="aaa"), _lauf("eval-a2", "agent", sha="bbb",
                                                        skill=False)]

    out = _vergleich(rows, ["eval-a1", "eval-a2"])

    assert {"code": "conditions_differ"} in out["warnings"]
    assert {"code": "master_skill_off", "runs": ["eval-a2"]} in out["warnings"]
    assert sorted(len(g["runs"]) for g in out["conditions"]) == [1, 1]


def test_skalen_und_unterschiede_der_messbedingungen() -> None:
    # Paket 13 (D4): Bewertung je Lauf und Maschine, und was sich gegen den ersten Lauf änderte.
    rows = [_lauf("eval-a1", "agent", sha="aaa"), _lauf("eval-a2", "agent", sha="bbb")]
    for row, note in zip(rows, (4, 2), strict=True):
        conv = row.conversations[0]
        conv["urteil"] = {"gesamt": note, "skalen": {"ton": {"note": note}}}
        conv["turns"][0]["judge"] = {"gesamt": note}

    out = _vergleich(rows, ["eval-a1", "eval-a2"])

    assert [r["bewertung"]["gesamt_mittel"] for r in out["runs"]] == [4.0, 2.0]
    assert out["bewertung_je_maschine"]["agent"]["gesamt_mittel"] == 3.0
    assert out["unterschiede"]["referenz"] == "eval-a1"
    assert out["unterschiede"]["laeufe"][0]["felder"] == [
        {"feld": "master_skill", "a": "an:aaa", "b": "an:bbb"}]


def test_modelle_ohne_preis_und_unlesbare_preistafel(monkeypatch) -> None:
    rows = [_lauf("eval-a1", "agent", model="unbekannt-1"),
            _lauf("eval-a2", "agent", model="unbekannt-1")]

    ohne_preis = _vergleich(rows, ["eval-a1", "eval-a2"])
    assert {"code": "price_missing", "models": ["unbekannt-1"]} in ohne_preis["warnings"]
    assert ohne_preis["engines"]["agent"]["cost"]["cost_per_turn"] is None

    monkeypatch.setattr(compare_mod, "load_pricing", lambda: None)
    unlesbar = _vergleich(rows, ["eval-a1", "eval-a2"])
    assert {"code": "pricing_unreadable"} in unlesbar["warnings"]
    assert unlesbar["currency"] is None


def test_rechnet_neben_dem_event_loop(monkeypatch) -> None:
    """Die Textnähe vergleicht jede Antwort mit jeder (difflib, quadratisch):
    sechs echte Gold-Läufe brauchten gemessen 14,5 s. Im Event-Loop stünde so
    lange jeder Chat-Zug still — der Loop muss während der Rechnung weiterlaufen."""
    def langsam(*_args, **_kwargs):
        time.sleep(0.3)
        return {"engines": {}, "rules": {}, "warnings": []}

    monkeypatch.setattr(compare_mod.engine_metrics, "evaluate", langsam)

    async def szenario() -> int:
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(ticker())
        await compare_runs(_Session([_lauf("eval-a1", "agent"), _lauf("eval-a2", "agent")]),
                           ["eval-a1", "eval-a2"])
        task.cancel()
        return ticks

    assert asyncio.run(szenario()) >= 10


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: "S"
    return TestClient(app)


def test_route_reicht_die_kennungen_weiter(client, monkeypatch) -> None:
    import boerdi.api.eval as eval_api

    aufrufe: list[tuple] = []

    async def fake(*args):
        aufrufe.append(args)
        return {"engines": {}}

    monkeypatch.setattr(eval_api, "compare_runs", fake)
    r = client.get("/api/eval/compare", params={"ids": "eval-a,eval-b,eval-a"},
                   headers={"X-Studio-Key": "k-studio-testkey"})

    assert r.status_code == 200
    # Doppelte Kennung zählt einmal — ein Lauf zweimal wäre eine erfundene Wiederholung.
    assert aufrufe == [("S", ["eval-a", "eval-b"])]


@pytest.mark.parametrize("ids", [
    "eval-a",                                   # einer ist kein Vergleich
    ",".join(f"eval-{i}" for i in range(21)),   # mehr als 20
    "eval-a,../etc",                            # nur Kennungen, keine Pfade
    "eval-a,eval-a",                            # zwei gleiche = einer
])
def test_route_weist_unbrauchbare_auswahl_ab(client, monkeypatch, ids) -> None:
    import boerdi.api.eval as eval_api

    async def fake(*args):
        return {"engines": {}}

    monkeypatch.setattr(eval_api, "compare_runs", fake)
    r = client.get("/api/eval/compare", params={"ids": ids},
                   headers={"X-Studio-Key": "k-studio-testkey"})
    assert r.status_code == 422


def test_route_verlangt_den_studio_schluessel(client) -> None:
    assert client.get("/api/eval/compare", params={"ids": "eval-a,eval-b"}).status_code == 401
