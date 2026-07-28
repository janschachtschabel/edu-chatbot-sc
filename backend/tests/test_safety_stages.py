"""Safety-Layer — die beiden LLM-Stufenmodule direkt (moderation + legal).

Neu in 3-4: der Transport wandert von ALT ``llm_provider`` auf die NEU-Fassaden
(``litellm.amoderation`` / ``services.llm.chat_completion``). Diese Datei pinnt
(a) die 3-Zweig-Credential-Auflösung ``moderation._moderation_target`` (Port von
ALT ``get_moderation_client``), (b) das Parsing der Moderation-Antwort und
(c) die Fail-Open-Garantie beider Stufen ({} statt Ausnahme → Regex bleibt Floor).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from pydantic import SecretStr

from boerdi.services.safety import legal as legal_mod
from boerdi.services.safety import moderation as mod


def _settings(*, openai="", b_api="", openai_base="", b_base="https://b-api.example"):
    return SimpleNamespace(
        openai_api_key=SecretStr(openai),
        openai_base_url=openai_base,
        b_api_key=SecretStr(b_api),
        b_api_base_url=b_base,
    )


# ── _moderation_target: 3-Zweig-Routing (Port von get_moderation_client) ──

def test_target_openai_with_key(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(openai="sk-abc"))
    base, key, headers = mod._moderation_target()
    assert base == "https://api.openai.com/v1"  # openai_base_url leer → Default
    assert key == "sk-abc"
    assert headers is None


def test_target_openai_without_key_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(openai=""))
    assert mod._moderation_target() is None


def test_target_b_api_openai_passthrough_uses_b_key(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings",
                        lambda: _settings(b_api="b-key", b_base="https://b-api.example/"))
    base, key, headers = mod._moderation_target()
    assert base == "https://b-api.example/openai"  # trailing slash gestript + /openai
    assert key == "b-key"
    assert headers == {"X-API-KEY": "b-key"}


def test_target_b_api_openai_falls_back_to_native_openai(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(b_api="", openai="sk-native"))
    base, key, headers = mod._moderation_target()
    assert base == "https://api.openai.com/v1"
    assert key == "sk-native"
    assert headers is None


def test_target_b_api_openai_no_keys_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings())
    assert mod._moderation_target() is None


def test_target_academiccloud_uses_native_openai(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(mod, "get_settings",
                        lambda: _settings(openai="sk-x", openai_base="https://proxy/v1/"))
    base, key, headers = mod._moderation_target()
    assert base == "https://proxy/v1"  # explizite openai_base_url gewinnt (Trailing-Slash gestript)
    assert key == "sk-x"
    assert headers is None


def test_target_academiccloud_without_openai_key_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings())
    assert mod._moderation_target() is None


# ── moderate(): Parsing + Fail-Open ──────────────────────────────────────

class _Bag:
    """Objekt-Form mit ``model_dump()`` — die Form, die ALT vom nativen
    OpenAI-SDK bekam. Wird nur noch im Gegenprobe-Test benutzt, damit der
    tolerante Zweig in ``moderate()`` nicht ungeprüft bleibt."""

    def __init__(self, d):
        self._d = d

    def model_dump(self):
        return self._d


def _fake_moderation_response(*, flagged, categories, scores):
    """Gemessen am 2026-07-27 gegen omni-moderation-latest: ``results[0]`` ist
    ein **Objekt** (``OpenAIModerationResult``) — ``.flagged``/``.categories``/
    ``.category_scores`` tragen —, aber ``categories`` und ``category_scores``
    sind darin **plain dicts** ohne ``model_dump()``.

    Die frühere Attrappe legte hier ``_Bag`` hinein und war deshalb dauerhaft
    grün, während jeder echte Aufruf mit ``'dict' object has no attribute
    'model_dump'`` im Fail-Open landete: die Moderationsstufe war im Betrieb
    tot, ohne dass ein Test es merkte.
    """
    result = SimpleNamespace(
        flagged=flagged,
        categories=dict(categories),
        category_scores=dict(scores),
    )
    return SimpleNamespace(results=[result])


def test_moderate_also_parses_the_model_shape(monkeypatch):
    """Gegenprobe zur gemessenen dict-Form: liefert ein Anbieter Modelle mit
    ``model_dump()``, darf die Stufe nicht wieder still ausfallen. Ohne diesen
    Test wäre der tolerante Zweig ungeprüfter Vorratscode."""
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _fake(**_kwargs):
        result = SimpleNamespace(
            flagged=True, categories=_Bag({"hate": True}), category_scores=_Bag({"hate": 0.9})
        )
        return SimpleNamespace(results=[result])

    monkeypatch.setattr(mod, "_amoderation", _fake)
    out = asyncio.run(mod.moderate("x"))
    assert out == {"flagged": True, "categories": {"hate": True}, "scores": {"hate": 0.9}}


def test_moderate_parses_flagged_categories_and_scores(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _fake(**kwargs):
        assert kwargs["model"] == "omni-moderation-latest"
        return _fake_moderation_response(
            flagged=True,
            categories={"violence": True, "hate": False},
            scores={"violence": 0.9, "hate": 0.1},
        )

    monkeypatch.setattr(mod, "_amoderation", _fake)
    out = asyncio.run(mod.moderate("etwas gewalttätiges"))
    assert out["flagged"] is True
    assert out["categories"] == {"violence": True, "hate": False}
    assert out["scores"] == {"violence": 0.9, "hate": 0.1}


def test_moderate_no_target_returns_empty(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target", lambda: None)
    assert asyncio.run(mod.moderate("x")) == {}


def test_moderate_error_returns_empty(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _boom(**kwargs):
        raise RuntimeError("upstream 500")

    monkeypatch.setattr(mod, "_amoderation", _boom)
    assert asyncio.run(mod.moderate("x")) == {}


def test_moderate_passes_b_api_headers(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://b-api.example/openai", "b-key", {"X-API-KEY": "b-key"}))
    seen = {}

    async def _fake(**kwargs):
        seen.update(kwargs)
        return _fake_moderation_response(flagged=False, categories={}, scores={})

    monkeypatch.setattr(mod, "_amoderation", _fake)
    asyncio.run(mod.moderate("x"))
    assert seen["api_base"] == "https://b-api.example/openai"
    assert seen["extra_headers"] == {"X-API-KEY": "b-key"}


# ── classify_legal(): Parsing + Fail-Open ────────────────────────────────

def test_classify_legal_parses_categories(monkeypatch):
    payload = ('{"strafrecht": {"risk": 0.8, "reason": "Bedrohung"},'
               ' "jugendschutz": {"risk": 0.0, "reason": ""},'
               ' "persoenlichkeitsrechte": {"risk": 0.1, "reason": ""},'
               ' "datenschutz": {"risk": 0.0, "reason": ""}}')

    async def _fake(**kwargs):
        msg = SimpleNamespace(content=payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(legal_mod, "chat_completion", _fake)
    out = asyncio.run(legal_mod.classify_legal("ich bedrohe dich"))
    assert out["strafrecht"]["risk"] == 0.8
    assert out["strafrecht"]["reason"] == "Bedrohung"
    assert set(out) == {"strafrecht", "jugendschutz", "persoenlichkeitsrechte", "datenschutz"}


def test_classify_legal_error_returns_empty(monkeypatch):
    async def _boom(**kwargs):
        raise RuntimeError("no transport")

    monkeypatch.setattr(legal_mod, "chat_completion", _boom)
    assert asyncio.run(legal_mod.classify_legal("x")) == {}
