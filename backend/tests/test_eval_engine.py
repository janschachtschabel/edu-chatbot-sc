"""ST-7a (2026-09-27): welche Maschine einen Eval-Lauf beantwortet hat.

Bis dahin stand die Maschine nur bei Gold-Läufen mit ausdrücklicher Wahl fest.
„Server-Vorgabe" und jeder generative Lauf maßen still, was ``01-base/engine``
gerade sagte — die Lauf-Liste konnte weder zeigen noch filtern, was gemessen
wurde, und das Detail zeigte „default".

Seitdem hält der Start fest, wohin die Züge gehen (``config.engine_effective``,
aufgelöst wie im Chat), und eine Stelle liest es für Liste, Detail und Verlauf.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import boerdi.services.engine_choice as engine_choice
import boerdi.services.eval.generative_run as generative_run
import boerdi.services.eval.golden_run as golden_run
import boerdi.services.eval_service as svc
from boerdi.api.deps import get_session
from boerdi.api.eval import GoldenRunRequest, StartRequest
from boerdi.db.models import EvalRun
from boerdi.main import create_app
from boerdi.services.eval.queries import get_run, get_trends, list_runs
from boerdi.services.eval.run_engine import run_engine
from boerdi.settings import get_settings
from tests.test_eval_router import (
    _AUTH,
    _SESSION,
    _fake_async,
    _FakeSession,
    _golden_flows,
    _patch_guard_and_spawn,
)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


@pytest.mark.parametrize(("config", "erwartet"), [
    ({"engine_effective": "agent", "engine": "default"}, "agent"),
    ({"engine_effective": "pattern", "engine": "pattern"}, "pattern"),
    # Gold-Läufe vor ST-7 mit ausdrücklicher Wahl — auch der Hybrid der K0-Messung.
    ({"engine": "pattern"}, "pattern"),
    ({"engine": "hybrid"}, "hybrid"),
    # „Server-Vorgabe" vor ST-7 und alle älteren generativen Läufe: unbekannt,
    # nicht geraten.
    ({"engine": "default"}, ""),
    ({}, ""),
    (None, ""),
    ({"engine": "warp"}, ""),
])
def test_die_maschine_eines_laufs(config, erwartet) -> None:
    assert run_engine(config) == erwartet


def _vorgabe(monkeypatch, mode: str) -> None:
    """Die Server-Vorgabe aus ``01-base/engine`` — der einzige Eingang, den
    ``choose_engine`` ohne Kopfzeile liest."""
    monkeypatch.setattr(engine_choice, "load_engine", lambda: SimpleNamespace(mode=mode))


def test_gold_lauf_mit_vorgabe_haelt_die_aufgeloeste_maschine_fest(monkeypatch) -> None:
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    _patch_guard_and_spawn(monkeypatch, golden_run)
    _vorgabe(monkeypatch, "agent")
    session = _FakeSession()

    asyncio.run(svc.start_golden_eval_run(session, None, GoldenRunRequest()))

    config = session.added[0].config
    assert config["engine"] == "default"  # die Wahl bleibt, wie sie war
    assert config["engine_effective"] == "agent"


def test_gold_lauf_mit_ausdruecklicher_wahl_schlaegt_die_vorgabe(monkeypatch) -> None:
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    _patch_guard_and_spawn(monkeypatch, golden_run)
    _vorgabe(monkeypatch, "agent")
    session = _FakeSession()

    asyncio.run(svc.start_golden_eval_run(
        session, None, GoldenRunRequest(engine="pattern")))

    assert session.added[0].config["engine_effective"] == "pattern"


def test_generativer_lauf_haelt_die_vorgabe_fest(monkeypatch) -> None:
    """Der generative Lauf schickt keine Kopfzeile — er misst die Vorgabe."""
    monkeypatch.setattr(generative_run, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]})
    _patch_guard_and_spawn(monkeypatch, generative_run)
    _vorgabe(monkeypatch, "agent")
    session = _FakeSession()

    asyncio.run(svc.start_generative_run(session, None, StartRequest()))

    assert session.added[0].config["engine_effective"] == "agent"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _Result(self.rows)


def _lauf(run_id: str, config: dict) -> EvalRun:
    return EvalRun(id=run_id, status="done", mode="golden", config=config,
                   totals={"total_turns": 2, "avg_score": 1.0}, summary={})


def test_liste_detail_und_verlauf_nennen_die_maschine() -> None:
    rows = [_lauf("eval-a", {"engine": "default", "engine_effective": "agent"}),
            _lauf("eval-b", {"engine": "default"})]

    liste = asyncio.run(list_runs(_Session(rows), 50))
    verlauf = asyncio.run(get_trends(_Session(rows), 10))
    detail = asyncio.run(get_run(_Session(rows[:1]), "eval-a"))

    assert [r["engine"] for r in liste["runs"]] == ["agent", ""]
    assert {m["id"]: m["engine"] for m in verlauf["runs"]} == {"eval-a": "agent", "eval-b": ""}
    assert detail["engine"] == "agent"


def test_liste_und_verlauf_reichen_den_maschinen_filter_weiter(client, monkeypatch) -> None:
    liste = _fake_async(monkeypatch, "list_runs", {"runs": []})
    verlauf = _fake_async(monkeypatch, "get_trends", {"runs": []})

    assert client.get("/api/eval/runs", params={"engine": "agent"},
                      headers=_AUTH).status_code == 200
    assert client.get("/api/eval/trends", params={"engine": "pattern"},
                      headers=_AUTH).status_code == 200

    assert liste == [(_SESSION, 50, "agent")]
    assert verlauf == [(_SESSION, 10, "pattern")]


@pytest.mark.parametrize("pfad", ["/api/eval/runs", "/api/eval/trends"])
def test_unbekannte_maschine_im_filter_ist_422(client, monkeypatch, pfad) -> None:
    """Ein Tippfehler darf nicht still „alle" zeigen — der Filter sähe gesetzt
    aus und wäre es nicht."""
    _fake_async(monkeypatch, "list_runs", {"runs": []})
    _fake_async(monkeypatch, "get_trends", {"runs": []})

    assert client.get(pfad, params={"engine": "hybrid"}, headers=_AUTH).status_code == 422
