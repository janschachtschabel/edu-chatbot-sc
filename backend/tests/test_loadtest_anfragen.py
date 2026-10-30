"""Paket 15 (E1): der Lasttest misst ehrlicher.

Befund `lt-b97eb9de93a3` (2026-10-17): je Stufe nur drei Suchen — ihr „p95“ war schlicht das
Maximum; die zwei langsamen Anfragen (MCP-Ausreißer 22 s, Ausweich-Kette nach leerer Suche) ließen
sich nur über die Nachrichten-Tabelle zurückverfolgen. Jetzt: eine Zeile je Anfrage im Ergebnis
(mit Werkzeugen und Werkzeugzeit aus dem Debug-Block) und eine Aufwärm-Anfrage, die nicht zählt.
"""

from __future__ import annotations

import asyncio

import httpx

from boerdi.services import loadtest as lt


def test_das_profil_waermt_vorgabe_maessig_auf() -> None:
    assert lt.validate_profile({})["warmup"] is True
    assert lt.validate_profile({"warmup": False})["warmup"] is False


def test_eine_anfrage_liefert_werkzeuge_und_werkzeugzeit() -> None:
    def antwort(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": "x", "debug": {
            "tools_called": ["search_wlo_all", "get_skill"],
            "token_usage": {"zeiten_ms": {"respond.werkzeuge": 1234, "gesamt": 5000}},
        }})

    async def lauf() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(antwort),
                                     base_url="http://lt") as client:
            return await lt._fire_request(client, "suche", "Optik", "loadtest-x-s0-0")

    zeile = asyncio.run(lauf())
    assert zeile["ok"] is True
    assert zeile["werkzeuge"] == 2
    assert zeile["werkzeuge_ms"] == 1234


def test_die_stufe_traegt_eine_zeile_je_anfrage() -> None:
    ergebnisse = [
        {"kind": "suche", "ok": True, "status": 200, "latency_s": 6.4, "werkzeuge": 1,
         "werkzeuge_ms": 2000},
        {"kind": "wissen", "ok": False, "status": 0, "latency_s": 30.0, "error": "ReadTimeout"},
    ]
    stufe = lt._stage_stats(1, 2, ["suche", "wissen"], ergebnisse, 40.0)
    assert [(z["nr"], z["kind"], z["ok"]) for z in stufe["anfragen"]] == [
        (1, "suche", True), (2, "wissen", False)]
    assert stufe["anfragen"][0]["werkzeuge_ms"] == 2000
    # n je Art steht dabei — mit drei Messungen ist „p95“ das Maximum (Studio sagt es).
    assert stufe["by_kind"]["suche"]["n"] == 1


def test_je_art_steht_das_echte_maximum_dabei() -> None:
    """Review Paket 15, #6: „p95“ ist nur bis n ≤ 11 das Maximum — das Studio zeigt ``max_s``."""
    ergebnisse = [{"kind": "suche", "ok": True, "status": 200, "latency_s": float(s)}
                  for s in range(1, 16)]
    stufe = lt._stage_stats(1, 15, ["suche"] * 15, ergebnisse, 40.0)
    assert stufe["by_kind"]["suche"]["max_s"] == 15.0
    assert stufe["by_kind"]["suche"]["p95_s"] == 14.0


def test_die_werkzeugzeit_kommt_vom_echten_erzeuger(monkeypatch) -> None:
    """Review-Runde 2 (R2-3): den Schlüssel ``respond.werkzeuge`` schrieb niemand — der Test oben
    setzt ihn selbst. Hier schreibt ihn die Werkzeug-Ausführung der Schleifen
    (``outcome_service.call_with_outcome``) in den Merkposten des Zuges."""
    from boerdi.obs.usage import bind_turn_usage, new_accumulator
    from boerdi.services import outcome_service

    async def mcp(name, args):
        await asyncio.sleep(0.01)
        return "- nodeId: x"

    monkeypatch.setattr(outcome_service, "call_mcp_tool", mcp)
    acc = new_accumulator()

    async def zug() -> None:
        bind_turn_usage(acc)
        await outcome_service.call_with_outcome("search_wlo_content", {"q": "Optik"})
        await outcome_service.call_with_outcome("search_wlo_content", {"q": "Linsen"})

    asyncio.run(zug())
    assert acc["zeiten_ms"]["respond.werkzeuge"] >= 20


def test_die_ressourcen_messung_beginnt_erst_nach_dem_aufwaermen(monkeypatch) -> None:
    """Review-Runde 2 (R2-28): die Aufwärm-Anfrage zählt nicht — auch nicht in Spitzen-RAM/-CPU."""
    from types import SimpleNamespace

    ereignisse: list[str] = []

    async def stufe(app, run_id, stage_idx, concurrency, kinds, *, engine="default"):
        ereignisse.append(f"stufe:{stage_idx}")
        await asyncio.sleep(0)  # gibt die Schleife frei — wie eine echte Anfrage
        ereignisse.append(f"stufe:{stage_idx}:ende")
        return [{"kind": k, "ok": True, "status": 200, "latency_s": 1.0} for k in kinds]

    async def abtasten(samples, stop):
        ereignisse.append("abtasten")
        await stop.wait()

    async def sichern(*args, **kwargs):
        return True

    monkeypatch.setattr(lt, "_run_stage", stufe)
    monkeypatch.setattr(lt, "_sample_resources", abtasten)
    monkeypatch.setattr(lt, "_persist", sichern)
    profil = lt.validate_profile({"stages": [1], "requests_per_stage": 1, "mix": {"suche": 1}})
    app = SimpleNamespace(state=SimpleNamespace(session_factory=None))
    asyncio.run(lt.execute_load_test(app, "lt-r2", profil))
    assert ereignisse.index("abtasten") > ereignisse.index("stufe:99:ende")


# ── Review 2026-10-30: Fehlerblasen mit HTTP 200 sind keine Antwort ─────────────


def _eine_anfrage(inhalt: str) -> dict:
    def antwort(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": inhalt, "debug": {}})

    async def lauf() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(antwort),
                                     base_url="http://lt") as client:
            return await lt._fire_request(client, "suche", "Optik", "loadtest-x-s0-0")

    return asyncio.run(lauf())


def test_die_ausgelastet_blase_zaehlt_nicht_als_antwort() -> None:
    from boerdi.i18n.bot_text import bot_text

    zeile = _eine_anfrage(bot_text("de", "error.llmBusy"))
    assert (zeile["ok"], zeile["status"], zeile["error"]) == (False, 200, "ausgelastet")


def test_eine_fehlerblase_mit_nummer_zaehlt_nicht_als_antwort() -> None:
    from boerdi.i18n.bot_text import bot_text

    zeile = _eine_anfrage(bot_text("de", "error.internal", nummer="4f2a9c01d3b7"))
    assert (zeile["ok"], zeile["error"]) == (False, "ersatzsatz")


def test_eine_echte_antwort_bleibt_gezaehlt() -> None:
    zeile = _eine_anfrage("Hier sind Arbeitsblätter zur Optik.")
    assert zeile["ok"] is True and "error" not in zeile


def test_eine_ausgelastete_stufe_ist_nicht_stabil() -> None:
    ergebnisse = [
        {"kind": "suche", "ok": True, "status": 200, "latency_s": 6.0},
        {"kind": "suche", "ok": False, "status": 200, "latency_s": 30.0, "error": "ausgelastet"},
    ]
    stufe = lt._stage_stats(2, 2, ["suche", "suche"], ergebnisse, 40.0)
    assert (stufe["errors"], stufe["ausgelastet"]) == (1, 1)
    assert stufe["error_kinds"] == ["ausgelastet"]
    assert lt._summary([stufe], 20.0, [])["stable_concurrency"] is None
