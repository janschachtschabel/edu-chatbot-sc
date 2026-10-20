"""Paket 17 (D3): Prometheus-Metriken — nur am internen Port.

Leitfaden „Übergabe an Team 6“: Basis-Metriken über die Standard-Bibliothek, wenige gezielte
Applikationsmetriken, ausschließlich am internen Port. Die Labels bleiben endlich: Routen
als Pfad-Vorlage (nie mit Sitzungs-ID), MCP-Server als Host, LLM-Aufrufe je Phase.
Zähler sind prozessweit — die Tests vergleichen deshalb vorher/nachher.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from boerdi.api.intern import create_intern_app
from boerdi.main import create_app
from boerdi.settings import get_settings


def _wert(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metriken_nur_am_internen_port() -> None:
    assert TestClient(create_app()).get("/metrics").status_code == 404
    r = TestClient(create_intern_app(FastAPI(), beendet=lambda: False)).get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "boerdi_build_info" in r.text
    assert "process_" in r.text or "python_info" in r.text  # Basis-Metriken der Bibliothek


def test_http_zaehler_mit_pfad_vorlage_statt_kennung(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PUBLIC", "off")
    get_settings.cache_clear()
    # Ohne Datenbank endet die Anfrage mit 500 — gezählt wird sie trotzdem, und um die
    # Pfad-Vorlage geht es hier.
    client = TestClient(create_app(), raise_server_exceptions=False)
    vorlage = "/api/sessions/{session_id}/messages"
    vorher = sum(_wert("boerdi_http_requests_total", route=vorlage, method="GET", status=s)
                 for s in ("200", "404", "422", "500", "503"))
    client.get("/api/sessions/bb-0815/messages")
    nachher = sum(_wert("boerdi_http_requests_total", route=vorlage, method="GET", status=s)
                  for s in ("200", "404", "422", "500", "503"))
    assert nachher == vorher + 1
    text = TestClient(create_intern_app(FastAPI(), beendet=lambda: False)).get("/metrics").text
    assert "bb-0815" not in text  # keine Kennung als Label


def test_unbekannter_pfad_bekommt_ein_sammel_label() -> None:
    client = TestClient(create_app())
    vorher = _wert("boerdi_http_requests_total", route="andere", method="GET", status="404")
    client.get("/gibt-es-nicht-4711")
    assert _wert("boerdi_http_requests_total", route="andere", method="GET",
                 status="404") == vorher + 1


def test_llm_aufrufe_je_phase_und_ausgang(monkeypatch) -> None:
    from boerdi.services import llm

    async def gut(**_k):
        msg = SimpleNamespace(content="OK", tool_calls=None)
        return SimpleNamespace(model="m", choices=[SimpleNamespace(message=msg,
                                                                   finish_reason="stop")])

    async def schlecht(**_k):
        raise RuntimeError("upstream 503")

    ok_vorher = _wert("boerdi_llm_calls_total", phase="probe", outcome="ok")
    fehler_vorher = _wert("boerdi_llm_calls_total", phase="probe", outcome="fehler")
    monkeypatch.setattr(llm, "_acompletion", gut)
    asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}], phase="probe"))
    monkeypatch.setattr(llm, "_acompletion", schlecht)
    try:
        asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}],
                                        phase="probe"))
    except RuntimeError:
        pass
    assert _wert("boerdi_llm_calls_total", phase="probe", outcome="ok") == ok_vorher + 1
    assert _wert("boerdi_llm_calls_total", phase="probe", outcome="fehler") == fehler_vorher + 1


def test_mcp_aufrufe_je_server_und_art(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    from boerdi.services.mcp import transport

    @asynccontextmanager
    async def kaputt(_url):
        raise ConnectionError("weg")
        yield  # pragma: no cover

    monkeypatch.setattr(transport, "_open_session", kaputt)
    url = "https://mcp.example.org/mcp"
    vorher = _wert("boerdi_mcp_calls_total", server="mcp.example.org", outcome="transport")
    ergebnis = asyncio.run(transport.call_tool("suche", {}, url=url))
    assert ergebnis["error"]["kind"] == "transport"
    assert _wert("boerdi_mcp_calls_total", server="mcp.example.org",
                 outcome="transport") == vorher + 1


def test_zuege_je_maschine() -> None:
    from boerdi.api import chat as chat_api
    from boerdi.api.schemas import ChatResponse, DebugInfo

    vorher = _wert("boerdi_turns_total", engine="agent")

    class _Sitzung:
        async def execute(self, *_a, **_k):
            return None

        async def commit(self):
            return None

        def add(self, *_a):
            return None

    antwort = ChatResponse(session_id="bb-1", content="x", debug=DebugInfo(engine="agent"))
    asyncio.run(chat_api._record_usage(_Sitzung(), "bb-1", {"response": antwort, "usage": {}}))
    assert _wert("boerdi_turns_total", engine="agent") == vorher + 1


def test_eine_kaputte_spec_kostet_keine_anfrage() -> None:
    """Die Zählung läuft im ``finally`` jeder Anfrage — scheitert die Pfad-Vorlage, darf das
    nur das Label kosten, nie die Antwort."""
    from boerdi.obs.metrics import MetrikMiddleware

    app = FastAPI()

    @app.get("/x")
    def x() -> dict:
        return {"ok": True}

    def kaputt() -> dict:
        raise RuntimeError("spec kaputt")

    app.openapi = kaputt  # type: ignore[method-assign]
    app.add_middleware(MetrikMiddleware)
    vorher = _wert("boerdi_http_requests_total", route="andere", method="GET", status="200")
    r = TestClient(app).get("/x")
    assert r.status_code == 200
    assert _wert("boerdi_http_requests_total", route="andere", method="GET",
                 status="200") == vorher + 1


def test_strom_und_klassifikator_werden_gezaehlt(monkeypatch) -> None:
    """Beide laufen an ``chat_completion`` vorbei (Strom: eigener Transport; Klassifikator:
    instructor) — ohne eigene Zählung fehlte der größte Teil der Muster-Züge."""
    from boerdi.services import classify, llm
    from boerdi.services.llm_streaming import _stream_completion

    async def _chunks():
        delta = SimpleNamespace(role="assistant", content="OK", tool_calls=None)
        yield SimpleNamespace(model="m", usage=None,
                              choices=[SimpleNamespace(delta=delta, finish_reason="stop")])

    async def strom(**_k):
        return _chunks()

    monkeypatch.setattr(llm, "_acompletion", strom)
    vorher = _wert("boerdi_llm_calls_total", phase="strom", outcome="ok")
    asyncio.run(_stream_completion(lambda _t: None, messages=[{"role": "user", "content": "x"}]))
    assert _wert("boerdi_llm_calls_total", phase="strom", outcome="ok") == vorher + 1

    from boerdi.api.schemas import ClassificationResult

    async def acreate(**_k):
        return ClassificationResult(persona_id="P-LER", intent_id="I01"), SimpleNamespace(
            model="m", usage=None)

    monkeypatch.setattr(classify, "_acreate", acreate)
    monkeypatch.setattr(classify, "build_classify_system_prompt", lambda: "SYS")
    monkeypatch.setattr(classify, "build_classify_turn_context", lambda ss, env, cs=None: "C")
    vorher = _wert("boerdi_llm_calls_total", phase="classify", outcome="ok")
    asyncio.run(classify.classify_input("hi", [], {}, {}))
    assert _wert("boerdi_llm_calls_total", phase="classify", outcome="ok") == vorher + 1
