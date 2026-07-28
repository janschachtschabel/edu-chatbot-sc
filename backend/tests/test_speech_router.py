"""Speech router pins — port of ALT ``tests/test_speech_limits.py`` plus the
newly-visible status / success / enablement / upstream-failure behaviour.

ALT enforced the rate limit in-band (``_rate_limit_or_429`` → mocked to
always-allow in every test). NEU moves the HTTP rate limit to the
``@public_rate_limit`` slowapi decorator, which is pinned separately in
``tests/test_ratelimit.py``. The NEU analogue of ALT's always-allow mock is the
off-switch, so the ``client`` fixture sets ``RATE_LIMIT_CHAT=off`` — that way
each pin here checks exactly ONE thing (cap → 413, disabled → 503, upstream
fail → 502, success shape) without the limiter interfering.

The external STT/TTS boundary is faked (no network): the router calls are
patched via ``boerdi.api.speech`` (the task-blessed seam), and the proxy's own
HTTP round-trip (``speech_proxy._post``) is faked for the fallback/error pins.

Offline harness: ``create_app()`` + ``TestClient`` WITHOUT ``with`` (the
lifespan would demand Postgres; speech needs no DB).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import boerdi.api.speech as speech_api
from boerdi.api import ratelimit
from boerdi.main import create_app
from boerdi.services import speech_proxy
from boerdi.services.speech_proxy import SpeechProxyError
from boerdi.settings import get_settings


@pytest.fixture()
def client(monkeypatch):
    # Disable the HTTP limiter so cap/enablement/proxy behaviour is isolated —
    # the NEU analogue of ALT mocking check_rate_limit to always-allow. The
    # limiter itself is pinned in test_ratelimit.py.
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    app = create_app()
    yield TestClient(app)
    ratelimit.limiter.reset()
    get_settings.cache_clear()


# ── GET /api/speech/status ──────────────────────────────────────────────────
def test_status_reports_enabled_true_and_empty_reason(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    monkeypatch.setattr(speech_api, "speech_disabled_reason", lambda: "")
    r = client.get("/api/speech/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": True, "reason": ""}


def test_status_reports_disabled_with_reason(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: False)
    monkeypatch.setattr(speech_api, "speech_disabled_reason", lambda: "kein OpenAI-Key")
    r = client.get("/api/speech/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "reason": "kein OpenAI-Key"}


# ── POST /api/speech/transcribe ─────────────────────────────────────────────
def _fake_transcribe(monkeypatch, *, result=None, error=None):
    calls: list[tuple] = []

    async def fake(content, filename, language):
        calls.append((content, filename, language))
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(speech_api, "transcribe_audio", fake)
    return calls


def test_transcribe_success_returns_text_and_model_with_default_language(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    calls = _fake_transcribe(
        monkeypatch, result={"text": "hallo welt", "model": "gpt-4o-mini-transcribe"}
    )
    # No `language` field → the Form("de") default must reach the proxy.
    r = client.post(
        "/api/speech/transcribe", files={"audio": ("rec.webm", b"xxxx", "audio/webm")}
    )
    assert r.status_code == 200
    assert r.json() == {"text": "hallo welt", "model": "gpt-4o-mini-transcribe"}
    assert calls == [(b"xxxx", "rec.webm", "de")]


def test_transcribe_rejects_oversized_audio_before_upstream(client, monkeypatch):
    # ALT port: > 10 MB → 413, the paid upstream is NEVER touched.
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    calls = _fake_transcribe(monkeypatch, result={"text": "x", "model": "m"})
    big = b"x" * (10 * 1024 * 1024 + 100)
    r = client.post(
        "/api/speech/transcribe",
        files={"audio": ("a.webm", big, "audio/webm")},
        data={"language": "de"},
    )
    assert r.status_code == 413
    assert calls == []


def test_transcribe_disabled_returns_503_with_reason(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: False)
    monkeypatch.setattr(speech_api, "speech_disabled_reason", lambda: "aus (kein Key)")
    calls = _fake_transcribe(monkeypatch, result={"text": "x", "model": "m"})
    r = client.post(
        "/api/speech/transcribe",
        files={"audio": ("a.webm", b"xx", "audio/webm")},
        data={"language": "de"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "aus (kein Key)"
    assert calls == []


def test_transcribe_cap_fires_before_enablement(client, monkeypatch):
    # Order pin (ALT): read+cap (413) precedes the enablement gate (503).
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: False)
    big = b"x" * (10 * 1024 * 1024 + 100)
    r = client.post(
        "/api/speech/transcribe",
        files={"audio": ("a.webm", big, "audio/webm")},
        data={"language": "de"},
    )
    assert r.status_code == 413  # not 503


def test_transcribe_upstream_failure_returns_502_without_leak(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    _fake_transcribe(monkeypatch, error=SpeechProxyError("boom: secret-upstream-detail"))
    r = client.post(
        "/api/speech/transcribe",
        files={"audio": ("a.webm", b"xx", "audio/webm")},
        data={"language": "de"},
    )
    assert r.status_code == 502
    assert r.json()["detail"] == "Spracherkennung fehlgeschlagen."
    assert "secret" not in r.text  # internal detail must not reach the client


# ── POST /api/speech/synthesize ─────────────────────────────────────────────
def _fake_synthesize(monkeypatch, *, audio=b"", error=None):
    calls: list[tuple] = []

    async def fake(text, voice, speed):
        calls.append((text, voice, speed))
        if error is not None:
            raise error
        return audio

    monkeypatch.setattr(speech_api, "synthesize_speech", fake)
    return calls


def test_synthesize_success_returns_audio_mpeg_with_defaults(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    calls = _fake_synthesize(monkeypatch, audio=b"ID3-fake-mp3-bytes")
    r = client.post("/api/speech/synthesize", data={"text": "Hallo"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.headers["content-disposition"] == "inline; filename=speech.mp3"
    assert r.content == b"ID3-fake-mp3-bytes"
    # Form defaults ported verbatim: voice=nova, speed=1.0.
    assert calls == [("Hallo", "nova", 1.0)]


def test_synthesize_rejects_oversized_text_before_upstream(client, monkeypatch):
    # ALT port: > 2000 chars → 413, upstream NEVER touched.
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    calls = _fake_synthesize(monkeypatch, audio=b"x")
    r = client.post("/api/speech/synthesize", data={"text": "x" * 3000})
    assert r.status_code == 413
    assert calls == []


def test_synthesize_disabled_returns_503_with_reason(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: False)
    monkeypatch.setattr(speech_api, "speech_disabled_reason", lambda: "aus")
    calls = _fake_synthesize(monkeypatch, audio=b"x")
    r = client.post("/api/speech/synthesize", data={"text": "hallo"})
    assert r.status_code == 503
    assert r.json()["detail"] == "aus"
    assert calls == []


def test_synthesize_cap_fires_before_enablement(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: False)
    r = client.post("/api/speech/synthesize", data={"text": "x" * 3000})
    assert r.status_code == 413  # cap precedes enablement


def test_synthesize_upstream_failure_returns_502_without_leak(client, monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    _fake_synthesize(monkeypatch, error=SpeechProxyError("boom: secret"))
    r = client.post("/api/speech/synthesize", data={"text": "hallo"})
    assert r.status_code == 502
    assert r.json()["detail"] == "Sprachsynthese fehlgeschlagen."
    assert "secret" not in r.text


# ── success path under ACTIVE rate limiting (production default is ON) ───────
# Regression pins: with headers_enabled the slowapi decorator injects
# X-RateLimit-* headers into the response on the SUCCESS path, and raises unless
# a dict-returning endpoint exposes a FastAPI ``response: Response`` param
# (extension.py::_inject_headers). The other tests disable the limiter, so these
# are the only pins that would catch a regression of that param.
def _client_active_limit(monkeypatch, limit="5/minute"):
    monkeypatch.setenv("RATE_LIMIT_CHAT", limit)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    return TestClient(create_app())


def test_status_ok_and_ratelimited_headers_under_active_limit(monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    monkeypatch.setattr(speech_api, "speech_disabled_reason", lambda: "")
    c = _client_active_limit(monkeypatch)
    r = c.get("/api/speech/status")
    ratelimit.limiter.reset()
    assert r.status_code == 200  # NOT 500 — slowapi must find a Response to write
    assert r.json() == {"enabled": True, "reason": ""}
    assert "x-ratelimit-limit" in {k.lower() for k in r.headers}


def test_transcribe_ok_under_active_limit(monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    _fake_transcribe(monkeypatch, result={"text": "ok", "model": "m"})
    c = _client_active_limit(monkeypatch)
    r = c.post("/api/speech/transcribe", files={"audio": ("a.webm", b"xx", "audio/webm")})
    ratelimit.limiter.reset()
    assert r.status_code == 200
    assert r.json() == {"text": "ok", "model": "m"}


def test_synthesize_ok_under_active_limit(monkeypatch):
    monkeypatch.setattr(speech_api, "speech_enabled", lambda: True)
    _fake_synthesize(monkeypatch, audio=b"mp3")
    c = _client_active_limit(monkeypatch)
    r = c.post("/api/speech/synthesize", data={"text": "hi"})
    ratelimit.limiter.reset()
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"mp3"


# ── services/speech_proxy: enablement logic (pure, no network) ───────────────
def _fake_settings(**over):
    base = dict(
        speech_force_enable=False,
        openai_api_key=SecretStr(""),
        b_api_audio=False,
        b_api_key=SecretStr(""),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_speech_enabled_openai_requires_key(monkeypatch):
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "openai")
    monkeypatch.setattr(
        speech_proxy, "get_settings", lambda: _fake_settings(openai_api_key=SecretStr("sk-x"))
    )
    assert speech_proxy.speech_enabled() is True
    monkeypatch.setattr(
        speech_proxy, "get_settings", lambda: _fake_settings(openai_api_key=SecretStr(""))
    )
    assert speech_proxy.speech_enabled() is False


def test_speech_enabled_bapi_needs_audio_flag_and_key(monkeypatch):
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "b-api-openai")
    # audio flag off → disabled even with a key
    monkeypatch.setattr(
        speech_proxy,
        "get_settings",
        lambda: _fake_settings(b_api_audio=False, b_api_key=SecretStr("k")),
    )
    assert speech_proxy.speech_enabled() is False
    # flag on + key → enabled
    monkeypatch.setattr(
        speech_proxy,
        "get_settings",
        lambda: _fake_settings(b_api_audio=True, b_api_key=SecretStr("k")),
    )
    assert speech_proxy.speech_enabled() is True
    # flag on but no key → disabled
    monkeypatch.setattr(
        speech_proxy,
        "get_settings",
        lambda: _fake_settings(b_api_audio=True, b_api_key=SecretStr("")),
    )
    assert speech_proxy.speech_enabled() is False


def test_speech_force_enable_overrides_everything(monkeypatch):
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(
        speech_proxy, "get_settings", lambda: _fake_settings(speech_force_enable=True)
    )
    assert speech_proxy.speech_enabled() is True


def test_speech_enabled_academiccloud_never_audio(monkeypatch):
    # AcademicCloud has no OpenAI audio endpoints (only b-api-openai does), so
    # speech is honestly disabled there even with B_API_AUDIO=1 + a key — option B
    # (exclude, no side-channel) rather than enable-then-502.
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(
        speech_proxy,
        "get_settings",
        lambda: _fake_settings(b_api_audio=True, b_api_key=SecretStr("k")),
    )
    assert speech_proxy.speech_enabled() is False


def test_speech_disabled_reason_variants(monkeypatch):
    # enabled → empty string
    monkeypatch.setattr(speech_proxy, "speech_enabled", lambda: True)
    assert speech_proxy.speech_disabled_reason() == ""
    # disabled + b-api-openai → the B-API opt-in hint (audio IS available there)
    monkeypatch.setattr(speech_proxy, "speech_enabled", lambda: False)
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "b-api-openai")
    assert "B_API_AUDIO=1" in speech_proxy.speech_disabled_reason()
    # disabled + b-api-academiccloud → honest "not available at AcademicCloud"; it
    # must NOT suggest B_API_AUDIO (that flag won't enable audio there).
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "b-api-academiccloud")
    _acc_reason = speech_proxy.speech_disabled_reason()
    assert "AcademicCloud" in _acc_reason
    assert "B_API_AUDIO" not in _acc_reason
    # disabled + openai → the missing-OpenAI-key hint
    monkeypatch.setattr(speech_proxy, "get_provider", lambda: "openai")
    assert "kein OpenAI-Key" in speech_proxy.speech_disabled_reason()


# ── services/speech_proxy: STT fallback chain + TTS (fake _post) ─────────────
class _FakeResp:
    def __init__(self, *, text="", content=b""):
        self.text = text
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        return None


def test_transcribe_audio_falls_back_to_next_model_on_error(monkeypatch):
    # Primary raises, the first fallback succeeds → returns the fallback's model.
    monkeypatch.setenv("STT_MODEL", "gpt-4o-mini-transcribe")
    get_settings.cache_clear()
    attempts: list[str] = []

    async def fake_post(url, **kw):
        assert url.endswith("/audio/transcriptions")
        attempts.append(kw["data"]["model"])
        if len(attempts) == 1:
            raise httpx.HTTPError("primary down")
        return _FakeResp(text="erkannter text")

    monkeypatch.setattr(speech_proxy, "_post", fake_post)
    out = asyncio.run(speech_proxy.transcribe_audio(b"audiobytes", "rec.webm", "de"))
    assert out == {"text": "erkannter text", "model": "gpt-4o-transcribe"}
    # ALT chain, verbatim order: primary first, then STT_FALLBACKS[0].
    assert attempts == ["gpt-4o-mini-transcribe", "gpt-4o-transcribe"]


def test_transcribe_audio_all_models_fail_raises_proxy_error(monkeypatch):
    async def fake_post(url, **kw):
        raise httpx.HTTPError("upstream down")

    monkeypatch.setattr(speech_proxy, "_post", fake_post)
    with pytest.raises(SpeechProxyError):
        asyncio.run(speech_proxy.transcribe_audio(b"x", "a.webm", "de"))


def test_synthesize_speech_returns_raw_bytes(monkeypatch):
    monkeypatch.setenv("TTS_MODEL", "tts-1")
    get_settings.cache_clear()

    async def fake_post(url, **kw):
        assert url.endswith("/audio/speech")
        assert kw["json"]["input"] == "Hallo"
        assert kw["json"]["voice"] == "nova"
        assert kw["json"]["model"] == "tts-1"
        return _FakeResp(content=b"mp3-bytes")

    monkeypatch.setattr(speech_proxy, "_post", fake_post)
    out = asyncio.run(speech_proxy.synthesize_speech("Hallo", "nova", 1.0))
    assert out == b"mp3-bytes"


def test_synthesize_speech_upstream_error_raises_proxy_error(monkeypatch):
    async def fake_post(url, **kw):
        raise httpx.HTTPError("upstream down")

    monkeypatch.setattr(speech_proxy, "_post", fake_post)
    with pytest.raises(SpeechProxyError):
        asyncio.run(speech_proxy.synthesize_speech("Hallo", "nova", 1.0))
