"""K0-2 (2026-09-26): die Messbedingungen eines Gold-Laufs.

Ein Vergleich der drei Maschinen taugt nur, wenn jeder Lauf sagt, womit er lief:
Anbieter und Chat-Modell, Judge-Modell, welcher Master-Skill (Prüfsumme) und
welche Deckel die Schleife hatte. Und er misst frisch: der MCP-Werkzeug-Cache
wird zu Beginn geleert, sonst bekäme ein Lauf die Treffer des vorigen geschenkt
und wäre schneller, ohne besser zu sein.
"""

from __future__ import annotations

import asyncio

from boerdi.services.eval import golden_run
from boerdi.services.eval import run_conditions as rc
from boerdi.settings import get_settings


def _modelle(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-6-luna")
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "gpt-4o-mini")
    get_settings.cache_clear()


def test_bedingungen_nennen_modelle_master_skill_und_deckel(monkeypatch) -> None:
    _modelle(monkeypatch)

    async def anzeige():
        return {"enabled": True, "node_id": "k1", "sha256": "ab" * 32,
                "length": 10, "text": "Wortlaut"}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)
    b = asyncio.run(rc.run_conditions(judge_enabled=True))

    assert (b["provider"], b["chat_model"], b["judge_model"]) == (
        "openai", "gpt-6-luna", "gpt-4o-mini")
    assert b["master_skill"]["sha256"] == "ab" * 32
    assert "text" not in b["master_skill"]  # der Wortlaut gehört nicht in jeden Lauf
    assert set(b["agent_limits"]) == {"max_iterations", "deadline_s", "token_budget",
                                      "write_mode"}


def test_ohne_judge_steht_kein_judge_modell_da(monkeypatch) -> None:
    _modelle(monkeypatch)

    async def anzeige():
        return {"enabled": False, "node_id": ""}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)
    assert asyncio.run(rc.run_conditions(judge_enabled=False))["judge_model"] == ""


def test_ein_ausfall_des_master_skill_abrufs_haelt_den_lauf_nicht_auf(monkeypatch) -> None:
    _modelle(monkeypatch)

    async def kaputt():
        raise TimeoutError("MCP weg")

    monkeypatch.setattr(rc.master_skill, "anzeige", kaputt)
    b = asyncio.run(rc.run_conditions(judge_enabled=False))
    assert "MCP weg" in b["master_skill"]["last_error"]


# ── der Job: Cache zuerst leeren, Bedingungen in jeden Stand schreiben ──────

class _Ctx:
    async def __aenter__(self):
        return "S"

    async def __aexit__(self, *exc):
        return False


def _verdrahte(monkeypatch, reihenfolge: list[str]) -> tuple[list[dict], dict]:
    class Runner:
        async def run_flows(self, url, flows, *, headers=None):
            reihenfolge.append("flow")
            return [{"flow_id": flows[0]["id"], "turns": []}]

        def aggregate_golden(self, convs):
            return {"overall_pass_rate": 1.0, "turns": 0, "flows": len(convs)}

    monkeypatch.setattr(golden_run, "_load_golden_runner", lambda: Runner())
    staende: list[dict] = []

    async def stand(session_factory, run_id, **kw):
        staende.append(kw)
        return True

    monkeypatch.setattr(golden_run, "_write_golden_progress", stand)
    ende: dict = {}

    async def abschluss(session, run_id, **kw):
        ende.update(kw)
        return True

    monkeypatch.setattr(golden_run, "_finalize_run", abschluss)

    async def bedingungen(*, judge_enabled):
        return {"chat_model": "gpt-6-luna", "judge_model": ""}

    monkeypatch.setattr(golden_run, "run_conditions", bedingungen)

    def frisch(run_id):
        reihenfolge.append("cache")

    monkeypatch.setattr(golden_run, "fresh_tool_cache", frisch)
    monkeypatch.setattr(golden_run, "tool_cache_stats", lambda: {"hits": 2, "misses": 5})
    return staende, ende


def test_der_lauf_leert_den_werkzeug_cache_vor_dem_ersten_flow(monkeypatch) -> None:
    reihenfolge: list[str] = []
    _verdrahte(monkeypatch, reihenfolge)
    flows = [{"id": "A", "turns": []}, {"id": "B", "turns": []}]

    asyncio.run(golden_run._execute_golden_run(lambda: _Ctx(), "eval-k0", flows, False))

    assert reihenfolge == ["cache", "flow", "flow"]


def test_jeder_stand_traegt_die_messbedingungen(monkeypatch) -> None:
    """Auch ein abgebrochener Lauf sagt, womit er lief — deshalb schon im
    Zwischenstand, nicht erst im Abschluss."""
    staende, ende = _verdrahte(monkeypatch, [])

    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-k0", [{"id": "A", "turns": []}], False))

    assert staende[0]["conditions"]["chat_model"] == "gpt-6-luna"
    assert ende["summary"]["messbedingungen"]["chat_model"] == "gpt-6-luna"
    assert ende["summary"]["tool_cache"] == {"hits": 2, "misses": 5}
