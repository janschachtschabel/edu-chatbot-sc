"""K0-2 (2026-09-26): die Messbedingungen eines Gold-Laufs.

Ein Vergleich der drei Maschinen taugt nur, wenn jeder Lauf sagt, womit er lief:
Anbieter und Chat-Modell, Judge-Modell, welcher Master-Skill (Prüfsumme) und
welche Deckel die Schleife hatte. Und er misst frisch: der MCP-Werkzeug-Cache
wird zu Beginn geleert, sonst bekäme ein Lauf die Treffer des vorigen geschenkt
und wäre schneller, ohne besser zu sein.
"""

from __future__ import annotations

import asyncio

import pytest

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


def _ohne_skill(monkeypatch) -> None:
    async def anzeige():
        return {"enabled": False, "node_id": ""}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)


def test_bedingungen_nennen_maschine_weg_und_app(monkeypatch) -> None:
    """Paket 13 (A2): womit ein Lauf das Modell erreichte und welcher Stand lief."""
    _modelle(monkeypatch)
    monkeypatch.setenv("BOERDI_VERSION", "0.5")
    monkeypatch.setenv("GIT_SHA", "dfd7152")
    get_settings.cache_clear()
    _ohne_skill(monkeypatch)
    b = asyncio.run(rc.run_conditions(judge_enabled=True, engine="pattern"))
    assert b["maschine"] == "pattern"
    assert b["weg"]["api"] == "responses"
    assert b["weg"]["modell"] == "gpt-6-luna"
    assert b["judge_weg"]["modell"] == "gpt-4o-mini"
    assert b["app"] == {"version": "0.5", "commit": "dfd7152"}


def test_vorgabe_maschine_ist_die_des_servers(monkeypatch) -> None:
    _modelle(monkeypatch)
    _ohne_skill(monkeypatch)
    monkeypatch.setattr(rc, "choose_engine", lambda wunsch: "agent")
    b = asyncio.run(rc.run_conditions(judge_enabled=False))
    assert b["maschine"] == "agent"
    assert b["judge_weg"] is None
    assert b["app"] == {"version": "", "commit": ""}


def test_bedingungen_tragen_konfiguration_und_gold_fassung(monkeypatch) -> None:
    """Paket 13 (A3): ohne Konfigurationsstand und Testfall-Fassung sagt ein Vergleich
    nicht, ob sich zwischen zwei Läufen der Bot oder der Test änderte."""
    _modelle(monkeypatch)
    _ohne_skill(monkeypatch)

    class Store:
        async def fassungen(self):
            return [{"area": "01-base/x", "data": {"a": 1}, "version": 3,
                     "updated_by": "studio", "werk_hash": None, "hat_eigene_fassung": False}]

    monkeypatch.setattr(rc.cl, "bound_store", lambda: Store())

    async def werk():
        return {"01-base/x": {"a": 1}}

    monkeypatch.setattr(rc, "_werk", werk)
    flows = [{"id": "GV-1", "turns": [{"message": "hallo"}]}]
    b = asyncio.run(rc.run_conditions(judge_enabled=False, flows=flows))
    assert b["konfiguration"]["bereiche"]["01-base/x"]["stand"] == "werk"
    assert b["konfiguration"]["bereiche"]["01-base/x"]["version"] == 3
    assert b["gold_flows"] == {"hash": rc.fingerprint.gold_flows_hash(flows), "ids": ["GV-1"]}


def test_ein_unlesbarer_store_haelt_den_lauf_nicht_auf(monkeypatch) -> None:
    _modelle(monkeypatch)
    _ohne_skill(monkeypatch)

    def kaputt():
        raise RuntimeError("config store not bound")

    monkeypatch.setattr(rc.cl, "bound_store", kaputt)
    b = asyncio.run(rc.run_conditions(judge_enabled=False))
    assert "not bound" in b["konfiguration"]["fehler"]
    assert b["gold_flows"] is None


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

    async def bedingungen(*, judge_enabled, engine="default", flows=None):
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
    # Paket 13 (D5): auch ohne Judge — Latenz, Kosten und Prompt-Fassungen für die Trends.
    assert ende["summary"]["kennzahlen_v2"]["gesamt_mittel"] is None
    assert ende["summary"]["kennzahlen_v2"]["prompts"] == {}


def test_mit_judge_bewertet_der_lauf_mit_v2_und_haelt_kosten_und_fassung_fest(monkeypatch):
    """Paket 13 (C4/C5): Zug- und Ablauf-Urteil laufen über einen eigenen Merkposten — die
    Judge-Kosten stehen getrennt von den Chat-Zügen im Summary, dazu die Judge-Fassung."""
    from boerdi.services.eval import golden, prompts_v2

    _staende, ende = _verdrahte(monkeypatch, [])
    gesehen: dict = {}

    async def bewerte(conversations, *, usage_acc=None):
        gesehen["acc"] = usage_acc
        usage_acc["calls"] += 3
        return {"zuege": 2, "ablaeufe": 1}

    monkeypatch.setattr(golden, "bewerte_gespraeche", bewerte)

    async def bericht(conversations, *, usage_acc=None):
        assert usage_acc is gesehen["acc"]
        return {"text": "Solide.", "baustellen": []}

    monkeypatch.setattr(golden, "kurzbericht_erstellen", bericht)
    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-c5", [{"id": "A", "turns": []}], True))

    assert ende["summary"]["judge_usage"]["calls"] == 3
    assert ende["summary"]["judge_usage"] is gesehen["acc"]
    assert ende["summary"]["judge_fassung"] == prompts_v2.JUDGE_V2_FASSUNG
    assert ende["summary"]["judge_bewertet"] == {"zuege": 2, "ablaeufe": 1}
    assert ende["summary"]["kurzbericht"] == {"text": "Solide.", "baustellen": []}


def test_der_lauf_bucht_die_judge_kosten_in_die_kosten_seite(monkeypatch):
    """Paket 15 (A6): die Judge-Kosten standen nur im Summary des Laufs — die Kosten-Seite
    zählte sie nie. Gebucht ohne Sitzung unter ``eval-judge``, mit der Maschine des Laufs."""
    from boerdi.services.eval import golden

    _verdrahte(monkeypatch, [])
    gesehen: dict = {}

    async def bewerte(conversations, *, usage_acc=None):
        gesehen["acc"] = usage_acc
        return {"zuege": 1, "ablaeufe": 1}

    async def bericht(conversations, *, usage_acc=None):
        return {"text": "", "baustellen": []}

    monkeypatch.setattr(golden, "bewerte_gespraeche", bewerte)
    monkeypatch.setattr(golden, "kurzbericht_erstellen", bericht)
    gebucht: list = []

    async def buche(session, session_id, acc, engine=None, quelle=None):
        gebucht.append((session, session_id, acc, engine, quelle))
        return 1

    monkeypatch.setattr(golden_run, "record_turn_usage", buche)
    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-a6", [{"id": "A", "turns": []}], True, engine="agent"))

    assert gebucht == [("S", None, gesehen["acc"], "agent", "eval-judge")]



def test_die_judge_kosten_werden_auch_nach_einem_fehler_gebucht(monkeypatch):
    """Review Paket 15, #5: scheitert der Kurzbericht, waren die Judge-Aufrufe schon bezahlt —
    gebucht wie im generativen Lauf, nach dem Fehler, in eigener Sitzung."""
    from boerdi.services.eval import golden

    _verdrahte(monkeypatch, [])
    gesehen: dict = {}

    async def bewerte(conversations, *, usage_acc=None):
        gesehen["acc"] = usage_acc
        usage_acc["calls"] += 2
        return {"zuege": 1, "ablaeufe": 1}

    async def bericht(conversations, *, usage_acc=None):
        raise RuntimeError("Judge weg")

    monkeypatch.setattr(golden, "bewerte_gespraeche", bewerte)
    monkeypatch.setattr(golden, "kurzbericht_erstellen", bericht)
    gebucht: list = []

    async def buche(session, session_id, acc, engine=None, quelle=None):
        gebucht.append((session_id, acc, engine, quelle))
        return 1

    monkeypatch.setattr(golden_run, "record_turn_usage", buche)
    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-r5", [{"id": "A", "turns": []}], True, engine="agent"))

    assert gebucht == [(None, gesehen["acc"], "agent", "eval-judge")]

def test_ohne_judge_bucht_der_lauf_nichts_extra(monkeypatch):
    _verdrahte(monkeypatch, [])
    gebucht: list = []

    async def buche(*args, **kw):
        gebucht.append(args)
        return 0

    monkeypatch.setattr(golden_run, "record_turn_usage", buche)
    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-a6b", [{"id": "A", "turns": []}], False))
    assert gebucht == []


def test_ein_abgebrochener_gold_lauf_bucht_die_judge_kosten(monkeypatch):
    """Review-Runde 2 (R2-2): Abbruch während der Bewertung (``task.cancel()``) — die schon
    bezahlten Judge-Aufrufe werden gebucht."""
    from boerdi.services.eval import golden

    _verdrahte(monkeypatch, [])
    gesehen: dict = {}

    async def bewerte(conversations, *, usage_acc=None):
        gesehen["acc"] = usage_acc
        usage_acc["calls"] += 4
        await asyncio.sleep(30)

    monkeypatch.setattr(golden, "bewerte_gespraeche", bewerte)
    gebucht: list = []

    async def buche(session, session_id, acc, engine=None, quelle=None):
        gebucht.append((session_id, acc, engine, quelle))
        return 1

    monkeypatch.setattr(golden_run, "record_turn_usage", buche)

    async def lauf():
        task = asyncio.create_task(golden_run._execute_golden_run(
            lambda: _Ctx(), "eval-r2", [{"id": "A", "turns": []}], True, engine="agent"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(lauf())
    assert gebucht == [(None, gesehen["acc"], "agent", "eval-judge")]
