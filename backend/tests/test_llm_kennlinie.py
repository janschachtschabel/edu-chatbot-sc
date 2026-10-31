"""Was LiteLLM wirklich verschickt — der Weg der App an einem lokalen Fang-Server.

Paket 7 (L1/L2, 2026-10-09). Die Unit-Tests in ``test_llm_responses.py`` prüfen,
was ``wire_transport`` an LiteLLM übergibt. Ob es dort ankommt, entscheidet
LiteLLM: Bei gpt-6 verwarf es ``reasoning_effort`` und ``verbosity`` still, bei
gpt-5.6 kam ``verbosity`` nie an, und ``service_tier`` ging an jedes Modell.
Dieser Test lässt ``llm.chat_completion`` gegen einen HTTP-Server auf 127.0.0.1
laufen und liest den Body mit — kein Netz nach außen. Wird er nach einem
LiteLLM-Update rot, hat sich die Kennlinie geändert.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from boerdi.services import llm
from boerdi.settings import get_settings

_CHAT = {"id": "c", "object": "chat.completion", "created": 1, "model": "m",
         "choices": [{"index": 0, "finish_reason": "stop",
                      "message": {"role": "assistant", "content": "ok"}}],
         "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
_RESP = {"id": "r", "object": "response", "created_at": 1, "status": "completed", "model": "m",
         "output": [{"type": "message", "id": "m1", "status": "completed", "role": "assistant",
                     "content": [{"type": "output_text", "text": "ok", "annotations": []}]}],
         "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                   "input_tokens_details": {"cached_tokens": 0},
                   "output_tokens_details": {"reasoning_tokens": 0}}}
_WERKZEUG = [{"type": "function", "function": {
    "name": "suche", "description": "x", "parameters": {"type": "object", "properties": {}}}}]
_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL",
        "B_API_KEY", "B_API_BASE_URL", "B_API_CLEAR_CACHE", "LLM_VERBOSITY",
        "LLM_REASONING_EFFORT", "LLM_SERVICE_TIER")


@pytest.fixture(scope="module")
def fang() -> Iterator[tuple[str, list[tuple[str, dict]], list[dict[str, str]]]]:
    gefangen: list[tuple[str, dict]] = []
    koepfe: list[dict[str, str]] = []

    class Fang(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 — Name der Basisklasse
            laenge = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(laenge) or b"{}")
            gefangen.append((self.path, body))
            koepfe.append({k.lower(): v for k, v in self.headers.items()})
            daten = json.dumps(_RESP if self.path.endswith("/responses") else _CHAT).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)

        def log_message(self, *args: object) -> None:  # leise
            pass

    server = HTTPServer(("127.0.0.1", 0), Fang)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", gefangen, koepfe
    server.shutdown()


@pytest.fixture
def senden(fang, monkeypatch):
    basis, gefangen, koepfe = fang

    def _senden(provider: str, modell: str, *, tarif: str = "", tools=None) -> tuple[str, dict]:
        for name in _ENV:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("LLM_CHAT_MODEL", modell)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", f"{basis}/v1")
        monkeypatch.setenv("B_API_BASE_URL", basis)
        monkeypatch.setenv("B_API_KEY", "bkey")
        monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
        monkeypatch.setenv("LLM_VERBOSITY", "low")
        if tarif:
            monkeypatch.setenv("LLM_SERVICE_TIER", tarif)
        get_settings.cache_clear()
        llm.reset()
        monkeypatch.setattr(llm, "_acompletion", llm.litellm.acompletion)
        gefangen.clear()
        koepfe.clear()
        asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "hi"}], tools=tools))
        assert len(gefangen) == 1, gefangen
        return gefangen[0]

    yield _senden
    get_settings.cache_clear()


@pytest.mark.parametrize("tools", [None, _WERKZEUG])
@pytest.mark.parametrize("modell", ["gpt-6-luna", "gpt-5.6-luna"])
def test_openai_direkt_bekommt_denktiefe_und_ausfuehrlichkeit(senden, modell, tools):
    pfad, body = senden("openai", modell, tools=tools)
    assert pfad == "/v1/responses"
    assert body["reasoning"] == {"effort": "low"}
    assert body["text"] == {"verbosity": "low"}


@pytest.mark.parametrize("tools", [None, _WERKZEUG])
@pytest.mark.parametrize("modell", ["gpt-6-luna", "gpt-5.6-luna"])
def test_b_api_openai_geht_wie_openai_direkt_ueber_responses(senden, fang, modell, tools):
    """Paket 9 (Review, CRITICAL): gpt-6-luna weist auf ``/openai/chat/completions``
    Werkzeuge ab (Probe 2026-10-09). Hinter der b-api steht dasselbe OpenAI — also
    derselbe Weg. Seit Paket 17 mit GENAU einem Kopf (``Authorization: Bearer``) —
    ein zusätzlicher ``X-API-KEY`` ergäbe bei durchgereichtem Schlüssel 401."""
    pfad, body = senden("b-api-openai", modell, tools=tools)
    assert pfad == "/openai/responses"
    assert body["reasoning"] == {"effort": "low"}
    assert body["text"] == {"verbosity": "low"}
    kopf = fang[2][0]
    assert "x-api-key" not in kopf
    assert kopf["authorization"] == "Bearer bkey"


def test_academiccloud_bleibt_auf_chat_completions(senden):
    pfad, body = senden("b-api-academiccloud", "qwen3-30b-a3b-instruct-2507", tools=_WERKZEUG)
    assert pfad == "/academiccloud/chat/completions"
    for name in ("verbosity", "reasoning_effort", "reasoning", "text"):
        assert name not in body, name


def test_der_tarif_erreicht_nur_die_gpt5_und_gpt6_familie(senden):
    assert senden("openai", "gpt-6-luna", tarif="fast")[1]["service_tier"] == "fast"
    pfad, body = senden("openai", "gpt-4o-mini", tarif="fast")
    assert pfad == "/v1/chat/completions"
    for name in ("service_tier", "verbosity", "reasoning_effort", "reasoning", "text"):
        assert name not in body, name


# ── Paket 19 (H-2): nichts bei OpenAI ablegen ───────────────────────────────
# ``/v1/responses`` legt Anfrage und Antwort ohne ``store: false`` 30 Tage ab (Vorgabe ``true``),
# sichtbar im Dashboard — Nachricht, Verlauf, Seitentext. LiteLLM setzt den Parameter nicht.
@pytest.mark.parametrize("tools", [None, _WERKZEUG])
@pytest.mark.parametrize("provider", ["openai", "b-api-openai"])
@pytest.mark.parametrize("modell", ["gpt-6-luna", "gpt-5.6-luna"])
def test_der_responses_weg_legt_nichts_bei_openai_ab(senden, provider, modell, tools):
    pfad, body = senden(provider, modell, tools=tools)
    assert pfad.endswith("/responses")
    assert body["store"] is False


def test_die_gpt5_familie_legt_auch_auf_chat_completions_nichts_ab(senden):
    """gpt-5.4 bleibt am eigenen Endpunkt auf Chat-Completions — gegen ``api.openai.com`` leitet
    LiteLLM es mit Werkzeugen still nach ``/v1/responses`` um (``responses_api_bridge_check``)."""
    pfad, body = senden("openai", "gpt-5.4-mini", tools=_WERKZEUG)
    assert pfad == "/v1/chat/completions"
    assert body["store"] is False


def test_die_academiccloud_bekommt_kein_store(senden):
    assert "store" not in senden("b-api-academiccloud", "qwen3-30b-a3b-instruct-2507")[1]


def test_auch_der_klassifikator_legt_nichts_ab(fang, monkeypatch):
    """Der Klassifikator geht über instructor an ``wire_transport`` vorbei an LiteLLM — jeder
    Versuch (instructor wiederholt bei unbrauchbarer Antwort) trägt ``store: false``."""
    from boerdi.services import classify

    basis, gefangen, _koepfe = fang
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", f"{basis}/v1")
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(classify, "build_classify_system_prompt", lambda: "SYS")
    monkeypatch.setattr(classify, "build_classify_turn_context", lambda ss, env, cs=None: "CTX")
    gefangen.clear()
    try:
        # Die Antwort des Fangs ist keine Klassifikation — instructor gibt auf, der
        # Klassifikator nimmt die Vorgabe. Gezählt werden die Anfragen.
        asyncio.run(classify.classify_input("hi", [], {}, {}))
    finally:
        get_settings.cache_clear()
    assert gefangen, "keine Anfrage am Fang"
    for pfad, body in gefangen:
        assert pfad == "/v1/responses" and body["store"] is False
