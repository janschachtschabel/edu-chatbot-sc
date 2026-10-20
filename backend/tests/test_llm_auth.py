"""Paket 17 (Phase B): den B-API-Schlüssel des Aufrufers durchreichen.

Kommt eine Anfrage über den b-api-Proxy (``/api/v1/proxy/badboerdichat/…`` mit
``forwardApiKey``), trägt sie ``Authorization: Bearer <key>`` — den Schlüssel, den
edu-sharing für die Person (oder den Gast) gewählt hat. Die b-api bucht Nutzung, Kosten
und Limits auf diesen Schlüssel. Regeln der b-api-Doku (gemessen 13.10.2026):
unverändert weitergeben, ``bearer`` kleingeschrieben → 401, genau EIN Kopf (ein
zusätzlicher ``X-API-KEY`` → 401), nie loggen, nie speichern. Ohne Kopf gilt wie bisher
``B_API_KEY`` (Direktaufruf, Hintergrundläufe).
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

import boerdi.api.chat as chat_api
from boerdi.api.deps import get_session
from boerdi.api.schemas import ChatResponse
from boerdi.main import create_app
from boerdi.services import llm, llm_auth
from boerdi.services.llm_models import get_chat_model
from boerdi.settings import get_settings

SCHLUESSEL = "k" * 36  # Form wie ein b-api-Schlüssel (36 Zeichen)
ENV_SCHLUESSEL = "env-schluessel-der-anlage"


@pytest.fixture
def b_api(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example.org/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", ENV_SCHLUESSEL)
    monkeypatch.delenv("B_API_ROUTE", raising=False)
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(None)
    yield monkeypatch
    llm_auth.setze_llm_schluessel(None)
    get_settings.cache_clear()


# ── Form ─────────────────────────────────────────────────────────────────────

def test_ein_gueltiger_kopf_gilt(b_api) -> None:
    assert llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}") is True
    assert llm_auth.b_api_schluessel() == SCHLUESSEL


@pytest.mark.parametrize("roh", [
    f"bearer {SCHLUESSEL}",           # kleingeschrieben → b-api 401
    f"Basic {SCHLUESSEL}",
    f"Bearer {SCHLUESSEL}\r\nX: y",   # Kopfzeilen-Einschleusung
    "Bearer " + "k" * 600,            # zu lang
    "Bearer kurz",                    # zu kurz
    f"Bearer  {SCHLUESSEL}",          # doppeltes Leerzeichen: nicht unverändert weiterzugeben
])
def test_ein_unbrauchbarer_kopf_faellt_auf_die_anlage_zurueck(b_api, roh) -> None:
    assert llm_auth.setze_llm_schluessel(roh) is False
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


def test_ein_leerer_kopf_loescht_den_vorigen(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    llm_auth.setze_llm_schluessel(None)
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


# ── Transport: genau EIN Kopf ────────────────────────────────────────────────

def test_route_nimmt_den_durchgereichten_schluessel(b_api) -> None:
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    _modell, _basis, schluessel, kopf = llm.route(get_chat_model())
    # Das SDK baut daraus ``Authorization: Bearer <key>`` — wörtlich der eingehende Kopf.
    assert schluessel == SCHLUESSEL
    assert kopf is None  # kein X-API-KEY daneben


def test_route_ohne_kopf_nimmt_die_anlage_ohne_x_api_key(b_api) -> None:
    _modell, _basis, schluessel, kopf = llm.route(get_chat_model())
    assert schluessel == ENV_SCHLUESSEL
    assert kopf is None


def test_bei_openai_direkt_zaehlt_der_kopf_nicht(b_api) -> None:
    b_api.setenv("LLM_PROVIDER", "openai")
    b_api.setenv("OPENAI_API_KEY", "sk-anlage")
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    _modell, _basis, schluessel, _kopf = llm.route(get_chat_model())
    assert schluessel == "sk-anlage"


def test_moderation_nimmt_den_durchgereichten_schluessel(b_api) -> None:
    from boerdi.services.safety import moderation

    b_api.setenv("B_API_KEY", "")
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    ziel = moderation._moderation_target()
    assert ziel is not None  # ohne Anlage-Schlüssel moderiert sie trotzdem über die b-api
    _basis, schluessel, kopf = ziel
    assert schluessel == SCHLUESSEL
    assert kopf is None


def test_sprache_mit_durchgereichtem_schluessel(b_api) -> None:
    from boerdi.services import speech_proxy

    b_api.setenv("B_API_KEY", "")
    b_api.setenv("B_API_AUDIO", "1")
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    assert speech_proxy.speech_enabled() is True
    _basis, koepfe = speech_proxy._auth_headers("gpt-4o-mini-transcribe")
    assert koepfe == {"Authorization": f"Bearer {SCHLUESSEL}"}


# ── Endpunkte ────────────────────────────────────────────────────────────────

@pytest.fixture
def client(b_api):
    b_api.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    return TestClient(app)


def _beobachter(monkeypatch, *, fehler: Exception | None = None) -> dict[str, str]:
    """Fährt einen Zug und hält fest, mit welchem Schlüssel das LLM gerufen würde."""
    gesehen: dict[str, str] = {}

    class _Graph:
        async def ainvoke(self, state):
            gesehen["schluessel"] = llm.route(get_chat_model())[2]
            if fehler is not None:
                raise fehler
            return {"response": ChatResponse(session_id="bb-1", content="X")}

    async def _fake_pp(req, resp, *a, **k):
        return resp

    async def _fake_save(*a, **k):
        return None

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "peer_ip", lambda request: "7.7.7.7")
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _fake_pp)
    monkeypatch.setattr(chat_api, "save_message", _fake_save)
    return gesehen


def _post(client, headers=None):
    return client.post(
        "/api/chat", json={"session_id": "bb-1", "message": "hallo", "environment": {}},
        headers=headers or {},
    )


def test_der_chat_zug_nimmt_den_schluessel_des_proxys(b_api, client) -> None:
    gesehen = _beobachter(b_api)
    r = _post(client, {"Authorization": f"Bearer {SCHLUESSEL}"})
    assert r.status_code == 200
    assert gesehen["schluessel"] == SCHLUESSEL


def test_der_schluessel_steht_in_keinem_log(b_api, client, caplog) -> None:
    _beobachter(b_api, fehler=RuntimeError("upstream antwortete 401"))
    with caplog.at_level(logging.DEBUG):
        r = _post(client, {"Authorization": f"Bearer {SCHLUESSEL}"})
        _post(client, {"Authorization": f"bearer {SCHLUESSEL}"})  # verworfen → Warnung
    assert r.status_code == 200  # Fehlerblase, keine 500
    assert SCHLUESSEL not in r.text
    assert all(SCHLUESSEL not in rec.getMessage() for rec in caplog.records)
    assert any("Authorization" in rec.getMessage() for rec in caplog.records)  # gemeldet


def test_der_studio_proxy_reicht_authorization_nicht_durch() -> None:
    from boerdi.api.studio_proxy import _forward_headers

    weiter = _forward_headers([(b"authorization", b"Bearer x"), (b"accept", b"*/*")])
    assert (b"authorization", b"Bearer x") not in weiter
    assert (b"accept", b"*/*") in weiter


# ── Review Phase B (2026-10-20) ─────────────────────────────────────────────

def test_eine_anfrage_ohne_kopf_loescht_den_schluessel_der_vorigen(b_api) -> None:
    """Review B, Befund 2: im SELBEN Kontext (so liefe ein Aufrufer, der die Übernahme
    zweimal ruft) muss eine Anfrage ohne Kopf den vorigen Schlüssel löschen. Ein Test über
    ``TestClient``/``ASGITransport`` sähe das nie: FastAPI führt den Endpunkt in eigenem
    Kontext aus (Mutationsprobe 2026-10-20: beide blieben grün ohne Löschen)."""
    from starlette.requests import Request

    from boerdi.api.turn_auth import uebernimm_llm_schluessel

    def anfrage(kopf: dict[str, str]) -> Request:
        roh = [(k.lower().encode(), v.encode()) for k, v in kopf.items()]
        return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": roh})

    uebernimm_llm_schluessel(anfrage({"Authorization": f"Bearer {SCHLUESSEL}"}))
    assert llm_auth.b_api_schluessel() == SCHLUESSEL
    uebernimm_llm_schluessel(anfrage({}))
    assert llm_auth.b_api_schluessel() == ENV_SCHLUESSEL


def test_sprachstatus_zaehlt_den_durchgereichten_schluessel(b_api, client) -> None:
    b_api.setenv("B_API_KEY", "")
    b_api.setenv("B_API_AUDIO", "1")
    get_settings.cache_clear()
    object.__setattr__(get_settings(), "b_api_key", __import__("pydantic").SecretStr(""))
    ohne = client.get("/api/speech/status").json()
    mit = client.get("/api/speech/status", headers={"Authorization": f"Bearer {SCHLUESSEL}"}).json()
    assert ohne["enabled"] is False
    assert mit["enabled"] is True


# Auf dem Draht (LiteLLM → lokaler Fang-Server): genau der eingehende Kopf, und ein 401
# der b-api (leerer Rumpf, wie gemessen) trägt den Schlüssel in keinen Fehlertext.

@pytest.fixture(scope="module")
def draht():
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    koepfe: list[dict[str, str]] = []
    antwort = {"id": "c", "object": "chat.completion", "created": 1, "model": "m",
               "choices": [{"index": 0, "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "ok"}}],
               "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    class Fang(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            kopf = {k.lower(): v for k, v in self.headers.items()}
            koepfe.append(kopf)
            if "falsch" in kopf.get("authorization", ""):
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            daten = json.dumps(antwort).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Fang)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", koepfe
    server.shutdown()


def _draht_anlage(b_api, basis: str) -> None:
    # Klassischer Chat-Weg (AcademicCloud-Modell) — der Weg, über den LiteLLM einen
    # eigenen Client je Schlüssel baut.
    b_api.setenv("LLM_PROVIDER", "b-api-academiccloud")
    b_api.setenv("LLM_CHAT_MODEL", "qwen3-30b-a3b-instruct-2507")
    b_api.setenv("B_API_BASE_URL", basis)
    get_settings.cache_clear()
    llm.reset()
    b_api.setattr(llm, "_acompletion", llm.litellm.acompletion)


def test_auf_dem_draht_genau_der_eingehende_kopf(b_api, draht) -> None:
    import asyncio

    basis, koepfe = draht
    _draht_anlage(b_api, basis)
    koepfe.clear()
    llm_auth.setze_llm_schluessel(f"Bearer {SCHLUESSEL}")
    asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "hi"}]))
    assert koepfe[-1]["authorization"] == f"Bearer {SCHLUESSEL}"
    assert "x-api-key" not in koepfe[-1]


def test_ein_401_traegt_den_schluessel_in_keinen_text(b_api, draht, caplog) -> None:
    import asyncio

    basis, _koepfe = draht
    _draht_anlage(b_api, basis)
    falsch = "falsch" + "x" * 30
    llm_auth.setze_llm_schluessel(f"Bearer {falsch}")
    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as fehler:  # noqa: PT011
        asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "hi"}]))
    assert falsch not in f"{type(fehler.value).__name__}: {fehler.value}"
    assert falsch not in repr(fehler.value)
    assert all(falsch not in rec.getMessage() for rec in caplog.records)


def test_sprache_eingeschaltet_ohne_schluessel_nennt_den_wahren_grund(b_api) -> None:
    """Review B (pre-existing): mit ``B_API_AUDIO=1`` riet der Text trotzdem „B_API_AUDIO=1
    setzen“ — seit Phase B (Direktaufruf ohne Anlage-Schlüssel) wahrscheinlicher."""
    from pydantic import SecretStr

    from boerdi.services import speech_proxy

    b_api.setenv("B_API_AUDIO", "1")
    get_settings.cache_clear()
    object.__setattr__(get_settings(), "b_api_key", SecretStr(""))
    grund = speech_proxy.speech_disabled_reason()
    assert "Schlüssel" in grund
    assert "B_API_AUDIO=1 setzen" not in grund


# ── Schlüssel-Modus B_API_KEY_MODE (Nutzer-Entscheid 2026-10-20, AB2) ─────────

@pytest.mark.parametrize("roh", [None, "", "  ", "unsinn"])
def test_ohne_gueltigen_modus_gilt_auto(b_api, roh) -> None:
    if roh is None:
        b_api.delenv("B_API_KEY_MODE", raising=False)
    else:
        b_api.setenv("B_API_KEY_MODE", roh)
    get_settings.cache_clear()
    assert get_settings().b_api_key_mode == "auto"


def test_auto_nimmt_den_kopf_vor_der_umgebung(b_api, client) -> None:
    gesehen = _beobachter(b_api)
    _post(client, {"Authorization": f"Bearer {SCHLUESSEL}"})
    assert gesehen["schluessel"] == SCHLUESSEL
    _post(client)
    assert gesehen["schluessel"] == ENV_SCHLUESSEL


def test_static_ignoriert_den_kopf(b_api, client, caplog) -> None:
    """Wie vor Paket 17: immer der Schlüssel der Anlage — auch keine Client-Flut durch
    beliebige Schlüssel direkter Aufrufer (Gesamt-Review AB2)."""
    b_api.setenv("B_API_KEY_MODE", "static")
    get_settings.cache_clear()
    gesehen = _beobachter(b_api)
    with caplog.at_level(logging.WARNING):
        r = _post(client, {"Authorization": f"Bearer {SCHLUESSEL}"})
    assert r.status_code == 200
    assert gesehen["schluessel"] == ENV_SCHLUESSEL
    assert not any("Authorization" in rec.getMessage() for rec in caplog.records)


def test_forward_verlangt_den_kopf(b_api, client) -> None:
    b_api.setenv("B_API_KEY_MODE", "forward")
    get_settings.cache_clear()
    gesehen = _beobachter(b_api)
    ohne = _post(client)
    assert ohne.status_code == 401
    assert ohne.headers.get("www-authenticate", "").startswith("Bearer")
    assert "schluessel" not in gesehen  # kein Zug ohne Schlüssel
    falsch = _post(client, {"Authorization": f"bearer {SCHLUESSEL}"})
    assert falsch.status_code == 401
    mit = _post(client, {"Authorization": f"Bearer {SCHLUESSEL}"})
    assert mit.status_code == 200
    assert gesehen["schluessel"] == SCHLUESSEL


def test_forward_ohne_b_api_verlangt_nichts(b_api, client) -> None:
    """Geht das LLM direkt zu OpenAI, gibt es keinen b-api-Schlüssel durchzureichen."""
    b_api.setenv("B_API_KEY_MODE", "forward")
    b_api.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    _beobachter(b_api)
    assert _post(client).status_code == 200


def test_forward_laesst_die_sprach_auskunft_offen(b_api, client) -> None:
    """``/api/speech/status`` ist eine Auskunft, kein Zug — das Widget fragt sie vorab."""
    b_api.setenv("B_API_KEY_MODE", "forward")
    get_settings.cache_clear()
    assert client.get("/api/speech/status").status_code == 200


def test_warnung_wenn_forward_nicht_wirkt(b_api, caplog) -> None:
    from boerdi.main import _warn_insecure_config

    b_api.setenv("B_API_KEY_MODE", "forward")
    b_api.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert any("B_API_KEY_MODE" in r.getMessage() for r in caplog.records)
