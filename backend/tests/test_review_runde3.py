"""Paket 17, Review-Runde 3 (nach Gesamt-Review und AB2-Schalter): jeder Test hielt einen
Befund fest und war zuerst rot."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from boerdi.api.deps import get_session, get_session_factory
from boerdi.main import create_app
from boerdi.services import llm_auth
from boerdi.settings import get_settings

_PROXY_SCHLUESSEL = "k" * 36
_ENV_SCHLUESSEL = "schluessel-der-anlage"
_STUDIO = "studio-schluessel-fuer-tests-0123456789"


@pytest.fixture
def forward(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example.org/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", _ENV_SCHLUESSEL)
    monkeypatch.setenv("B_API_KEY_MODE", "forward")
    monkeypatch.setenv("STUDIO_API_KEY", _STUDIO)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    monkeypatch.setenv("AGENT_OPEN", "1")  # die Aufrufer-Prüfung des Agenten soll nicht verdecken
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(None)
    yield monkeypatch
    llm_auth.setze_llm_schluessel(None)
    get_settings.cache_clear()


@contextlib.asynccontextmanager
async def _sitzung():
    yield object()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_session_factory] = lambda: _sitzung
    return TestClient(app, raise_server_exceptions=False)


def _zug_beobachten(monkeypatch) -> dict:
    """Hält fest, ob ein Zug startet und mit welchem Schlüssel."""
    from boerdi.api import agent as agent_api
    from boerdi.api import chat as chat_api
    from boerdi.api import speech as speech_api
    from boerdi.api.schemas import ChatResponse
    from boerdi.api.schemas_agent import AgentResponse

    gesehen: dict = {}

    class _Graph:
        async def ainvoke(self, state):
            gesehen["schluessel"] = llm_auth.b_api_schluessel()
            return {"response": ChatResponse(session_id="bb-1", content="X")}

    async def _pp(req, resp, *a, **k):
        return resp

    async def _speichern(*a, **k):
        return None

    async def _agent(req, *, progress=None, usage_acc=None):
        gesehen["schluessel"] = llm_auth.b_api_schluessel()
        return AgentResponse(text="x", result={}, stop_reason="submit", iterations=1,
                             tools_called=[])

    async def _hoeren(*a):
        gesehen["schluessel"] = llm_auth.b_api_schluessel()
        return {"text": "x", "model": "m"}

    async def _sprechen(*a):
        gesehen["schluessel"] = llm_auth.b_api_schluessel()
        return b"ID3"

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _pp)
    monkeypatch.setattr(chat_api, "save_message", _speichern)
    monkeypatch.setattr(agent_api, "run_agent", _agent)
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    monkeypatch.setattr(speech_api, "transcribe_audio", _hoeren)
    monkeypatch.setattr(speech_api, "synthesize_speech", _sprechen)
    return gesehen


_CHAT = {"session_id": "bb-1", "message": "hallo", "environment": {}}
_WEGE = {
    "chat": ("post", "/api/chat", {"json": _CHAT}),
    "chat-strom": ("post", "/api/chat/stream", {"json": _CHAT}),
    "agent": ("post", "/api/agent", {"json": {"instruction": "Pruefe."}}),
    "agent-strom": ("post", "/api/agent/stream", {"json": {"instruction": "Pruefe."}}),
    "hoeren": ("post", "/api/speech/transcribe",
               {"files": {"audio": ("rec.webm", b"xxxx", "audio/webm")}}),
    "sprechen": ("post", "/api/speech/synthesize", {"data": {"text": "Hallo"}}),
}


@pytest.mark.parametrize("weg", list(_WEGE))
def test_forward_weist_jeden_zug_ohne_schluessel_ab(forward, weg) -> None:
    """Befund 5: bisher nur ``/api/chat`` belegt."""
    gesehen = _zug_beobachten(forward)
    methode, pfad, rumpf = _WEGE[weg]
    r = getattr(_client(), methode)(pfad, **rumpf)
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").startswith("Bearer")
    assert "schluessel" not in gesehen  # kein Zug, kein Lauf


@pytest.mark.parametrize("weg", list(_WEGE))
def test_forward_nimmt_den_schluessel_auf_jedem_weg(forward, weg) -> None:
    gesehen = _zug_beobachten(forward)
    methode, pfad, rumpf = _WEGE[weg]
    getattr(_client(), methode)(pfad, headers={"Authorization": f"Bearer {_PROXY_SCHLUESSEL}"},
                                **rumpf)
    assert gesehen.get("schluessel") == _PROXY_SCHLUESSEL


def test_forward_laesst_interne_zuege_mit_studio_schluessel_durch(forward) -> None:
    """Befund 1 (MAJOR): Evaluation und Lasttest fahren ihre Züge ohne Proxy-Kopf — mit
    ``forward`` scheiterten sie alle an 401. Mit gültigem Studio-Schlüssel laufen sie auf
    ``B_API_KEY``."""
    gesehen = _zug_beobachten(forward)
    r = _client().post("/api/chat", json=_CHAT, headers={"X-Studio-Key": _STUDIO})
    assert r.status_code == 200
    assert gesehen["schluessel"] == _ENV_SCHLUESSEL


def test_ein_falscher_studio_schluessel_hilft_nicht(forward) -> None:
    _zug_beobachten(forward)
    r = _client().post("/api/chat", json=_CHAT, headers={"X-Studio-Key": "geraten"})
    assert r.status_code == 401


def test_forward_laesst_studio_proben_durch(forward) -> None:
    """Befund 1: der Studio-Proxy reicht ``Authorization`` nie durch."""
    from starlette.requests import Request

    from boerdi.api.studio_proxy import _UEBER_STUDIO
    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    anfrage = Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": [],
                       _UEBER_STUDIO: True})
    uebernimm_llm_schluessel(anfrage)  # keine 401
    assert llm_auth.b_api_schluessel() == _ENV_SCHLUESSEL


@pytest.mark.asyncio
async def test_der_lasttest_kommt_unter_forward_durch(forward) -> None:
    """Befund 1, Nachweis wie der Prüfer: ein Lasttest-Zug gegen die App."""
    import httpx

    from boerdi.services import loadtest

    _zug_beobachten(forward)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    transport = httpx.ASGITransport(app=app, client=("10.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://lt") as client:
        ergebnis = await loadtest._fire_request(client, "wissen", "Optik", "lt-s-1")
    assert ergebnis["status"] != 401


def test_der_eval_runner_schickt_den_studio_schluessel_nur_an_die_eigene_adresse(forward) -> None:
    """Befund 1: ``EVAL_CHAT_URL`` kann fremd sein — das Admin-Geheimnis geht nur an die
    Loopback-Adresse."""
    from boerdi.services.eval import runner

    assert runner._interne_koepfe("http://127.0.0.1:8100/api/chat") == {"X-Studio-Key": _STUDIO}
    assert runner._interne_koepfe("http://localhost:8100/api/chat") == {"X-Studio-Key": _STUDIO}
    assert runner._interne_koepfe("https://chat.example.org/api/chat") == {}


def test_ein_vertippter_modus_wird_gemeldet(forward, caplog) -> None:
    """Befund 4: ``foward`` fiel still auf ``auto`` zurück — die 401-Pflicht war aus."""
    from boerdi.main import _warn_insecure_config

    forward.setenv("B_API_KEY_MODE", "foward")
    get_settings.cache_clear()
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert get_settings().b_api_key_mode == "auto"
    assert any("B_API_KEY_MODE" in r.getMessage() and "foward" in r.getMessage()
               for r in caplog.records)


def test_static_meldet_auch_einen_kaputten_kopf_nicht(forward, caplog) -> None:
    """Befund 8: im Modus static wird der Kopf gar nicht gelesen."""
    forward.setenv("B_API_KEY_MODE", "static")
    get_settings.cache_clear()
    _zug_beobachten(forward)
    with caplog.at_level(logging.WARNING):
        r = _client().post("/api/chat", json=_CHAT, headers={"Authorization": "bearer x"})
    assert r.status_code == 200
    assert not any("Authorization" in rec.getMessage() for rec in caplog.records)


def test_ein_aelterer_stand_ueberschreibt_keinen_neueren() -> None:
    """Befund 2: ein Takt, dessen Lesen vor dem Signal begann, legte den alten Text zurück."""
    from boerdi.services import master_skill, master_skill_stand

    master_skill.leere_den_zwischenspeicher()
    jetzt = datetime.now(UTC)
    try:
        neu = master_skill_stand.Stand(text="# Neu", abgerufen_um=jetzt, letzter_fehler=None,
                                       alter_s=0.0, geprueft_um=jetzt)
        alt = master_skill_stand.Stand(text="# Alt", abgerufen_um=jetzt - timedelta(minutes=4),
                                       letzter_fehler=None, alter_s=240.0,
                                       geprueft_um=jetzt - timedelta(minutes=4))
        master_skill._uebernimm("k", neu)
        master_skill._uebernimm("k", alt)
        assert master_skill._gespeichert("k") == "# Neu"
    finally:
        master_skill.leere_den_zwischenspeicher()


def test_der_einstieg_verdrahtet_genau_den_lauf_abschluss(monkeypatch) -> None:
    """Befund 7: ``bei_ende is not None`` hätte jede Attrappe bestanden."""
    import asyncio

    from boerdi import serve
    from boerdi.main import app

    gefangen: dict = {}
    aufgerufen: list = []

    async def _laufen(haupt, intern):
        gefangen["haupt"] = haupt

    async def _abschluss(a):
        aufgerufen.append(a)

    monkeypatch.setattr(serve, "laufen", _laufen)
    monkeypatch.setattr(serve, "laeufe_der_app_beenden", _abschluss)
    serve.main()
    asyncio.run(gefangen["haupt"].bei_ende())
    assert aufgerufen == [app]
