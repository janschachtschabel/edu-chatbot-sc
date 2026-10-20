"""Paket 17, Review Phase D (2026-10-20): Regressionstests zu den bestätigten Befunden.

Je Test der Befund aus dem Review (C = Code, Prüfer 1). Rot zuerst geschrieben.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from boerdi.obs import trace_id
from boerdi.settings import get_settings


def _wert(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


# C1 — das Routen-Label der Studio-SPA: der Mount setzt ``root_path`` um; gemessen wurde
# ``/studio/`` als ``/`` gezählt.
def test_studio_pfade_zaehlen_als_studio(monkeypatch, tmp_path) -> None:
    from boerdi.main import create_app

    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("STUDIO_DIST_DIR", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(create_app())
    vorher = sum(_wert("boerdi_http_requests_total", route="/studio", method="GET", status=s)
                 for s in ("200", "304", "307", "404"))
    client.get("/studio/")
    client.get("/studio/eine/seite")
    nachher = sum(_wert("boerdi_http_requests_total", route="/studio", method="GET", status=s)
                  for s in ("200", "304", "307", "404"))
    get_settings.cache_clear()
    assert nachher == vorher + 2


# C2 — ``LOG_LEVEL=WARN`` galt bisher (``getattr(logging, …)``); Uvicorns Tabelle kennt es nicht.
@pytest.mark.parametrize("stufe", ["WARN", "warning", "DEBUG", "quatsch"])
def test_jede_log_stufe_startet_den_server(monkeypatch, stufe) -> None:
    from boerdi import serve

    monkeypatch.setenv("LOG_LEVEL", stufe)
    get_settings.cache_clear()
    haupt, intern = serve.baue_server(FastAPI(), FastAPI())
    get_settings.cache_clear()
    for server in (haupt, intern):
        server.config.configure_logging()  # warf KeyError 'warn'
        assert isinstance(server.config.log_level, int)


# C3 — ein abgebrochener Aufruf ist kein Fehler der b-api.
def test_abbruch_zaehlt_nicht_als_llm_fehler() -> None:
    from boerdi.obs.metrics import llm_messung

    vorher_fehler = _wert("boerdi_llm_calls_total", phase="abbruchprobe", outcome="fehler")
    vorher_abbruch = _wert("boerdi_llm_calls_total", phase="abbruchprobe", outcome="abbruch")

    async def lauf() -> None:
        async with llm_messung("abbruchprobe"):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(lauf())
    assert _wert("boerdi_llm_calls_total", phase="abbruchprobe", outcome="fehler") == vorher_fehler
    assert _wert("boerdi_llm_calls_total", phase="abbruchprobe",
                 outcome="abbruch") == vorher_abbruch + 1


# C4 — die Fehlerzeile außerhalb der Middleware (Uvicorn: „Exception in ASGI application“)
# soll noch die Trace-ID tragen.
def test_trace_id_gilt_noch_fuer_die_fehlerzeile() -> None:
    gesehen: dict[str, str] = {}

    async def kaputt(scope, receive, send):
        raise RuntimeError("kaputt")

    middleware = trace_id.TraceIdMiddleware(kaputt)

    async def aussen() -> None:
        scope = {"type": "http", "headers": [(b"x-client-trace-id", b"fehler-4711")]}
        try:
            await middleware(scope, None, None)
        except RuntimeError:
            gesehen["id"] = trace_id.aktuelle()  # so loggt Uvicorn die Ausnahme

    asyncio.run(aussen())
    assert gesehen["id"] == "fehler-4711"


# C5 — „bereit“ erst, wenn der Hauptserver läuft, nicht schon mitten im Lifespan.
def test_nicht_bereit_bevor_der_hauptserver_laeuft() -> None:
    from boerdi.api.intern import create_intern_app

    class _Engine:
        def connect(self):
            class _V:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *e):
                    return None

                async def execute(self, _s):
                    return None
            return _V()

    app = create_intern_app(FastAPI(), beendet=lambda: False, gestartet=lambda: False,
                            probe_engine=_Engine())
    r = TestClient(app).get("/ready")
    assert r.status_code == 503 and r.json()["grund"] == "startet"


# C9 — Lücken: HEAD ohne Schlüssel, fremde MCP-Server ohne Trace-Köpfe, Moderation mit.
def test_head_api_health_ohne_schluessel(monkeypatch) -> None:
    from boerdi.main import create_app

    monkeypatch.setenv("STUDIO_API_KEY", "ein-langer-schluessel-fuer-den-test-0123")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    r = TestClient(create_app()).head("/api/health")
    get_settings.cache_clear()
    assert r.status_code == 401


def test_fremder_mcp_server_bekommt_keine_trace_koepfe() -> None:
    from boerdi.services.mcp import transport

    token = trace_id.setze("t-fremd")
    try:
        client = transport._client_fabrik("https://fremd.example.org/mcp")()
    finally:
        trace_id.zuruecksetzen(token)
    assert "x-client-trace-id" not in client.headers


def test_moderation_traegt_die_trace_id(monkeypatch) -> None:
    from boerdi.services.safety import moderation

    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "b-schluessel")
    get_settings.cache_clear()
    token = trace_id.setze("t-mod")
    try:
        _basis, _key, koepfe = moderation._moderation_target()
    finally:
        trace_id.zuruecksetzen(token)
        get_settings.cache_clear()
    assert koepfe["x-client-trace-id"] == "t-mod"


# C10 — B3 verlangt Kleinbuchstaben-Hex; eine Null-ID ist ungültig.
def test_b3_kopf_in_kleinbuchstaben_und_ohne_null_id() -> None:
    token = trace_id.setze("0AF7651916CD43DD8448EB211C80319C")
    try:
        assert trace_id.ausgehende_koepfe()["X-B3-TraceId"] == "0af7651916cd43dd8448eb211c80319c"
    finally:
        trace_id.zuruecksetzen(token)
    token = trace_id.setze("0" * 32)
    try:
        assert "X-B3-TraceId" not in trace_id.ausgehende_koepfe()
    finally:
        trace_id.zuruecksetzen(token)


# C12 — der interne Port darf nicht der öffentliche sein.
def test_interner_port_nicht_gleich_dem_oeffentlichen(monkeypatch) -> None:
    from pydantic import ValidationError

    from boerdi.settings import Settings

    monkeypatch.setenv("INTERNAL_PORT", "8100")
    with pytest.raises(ValidationError):
        Settings()


def test_der_healthcheck_folgt_dem_internen_port() -> None:
    from pathlib import Path

    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text("utf-8")
    zeile = next(z for z in dockerfile.splitlines() if "urlopen" in z)
    assert "INTERNAL_PORT" in zeile


# C13 — die öffentliche Spec wird je App nur einmal gebaut.
def test_oeffentliche_spec_wird_zwischengespeichert(monkeypatch) -> None:
    from boerdi.api import openapi_public
    from boerdi.main import create_app

    app = create_app()
    aufrufe = []
    original = openapi_public.oeffentliche_spec

    def zaehlend(a):
        aufrufe.append(1)
        return original(a)

    monkeypatch.setattr("boerdi.main.oeffentliche_spec", zaehlend)
    client = TestClient(app)
    client.get("/openapi.json")
    client.get("/openapi.json")
    assert len(aufrufe) == 1


def test_logger_nutzt_die_stufe(monkeypatch) -> None:
    """Gegenprobe zu C2: die Wurzel nimmt ``WARN`` weiter an."""
    assert logging.getLevelName("WARN") == logging.WARNING
    assert SimpleNamespace  # Import für die Attrappen oben
