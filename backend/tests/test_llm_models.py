"""P1-6: model/provider resolution — port of ALT llm_provider.py semantics
(chain LLM_CHAT_MODEL -> OPENAI_MODEL[openai only] -> provider default;
gpt5-param gate; embed-dim table).
"""

import pytest

from boerdi.services import llm_models as lm
from boerdi.settings import get_settings

ALL = ["LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "LLM_EMBED_MODEL", "EMBED_DIM",
       "LLM_VERBOSITY", "LLM_REASONING_EFFORT"]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ALL:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    return monkeypatch


def test_chat_model_chain_llm_chat_model_wins(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("LLM_CHAT_MODEL", "custom-x")
    monkeypatch.setenv("OPENAI_MODEL", "legacy-y")
    get_settings.cache_clear()
    assert lm.get_chat_model() == "custom-x"


def test_chat_model_chain_openai_model_only_for_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "legacy-y")
    get_settings.cache_clear()
    assert lm.get_chat_model() == "legacy-y"  # provider default = openai
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    assert lm.get_chat_model() == "gpt-5.4-mini"  # legacy var ignored off-openai


def test_provider_defaults():
    assert lm.get_chat_model() == "gpt-5.4-mini"
    assert lm.get_embed_model() == "text-embedding-3-small"


def test_academiccloud_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    assert lm.get_chat_model() == "mistral-large-3-675b-instruct-2512"
    assert lm.get_embed_model() == "e5-mistral-7b-instruct"


def test_is_gpt5_model_family():
    assert lm.is_gpt5_model("gpt-5.4-mini") is True
    assert lm.is_gpt5_model("o3-mini") is True
    assert lm.is_gpt5_model("gpt-4.1-mini") is False
    assert lm.is_gpt5_model("") is True  # falls back to default chat model (gpt-5.4-mini)


def test_supports_gpt5_params_provider_gate(monkeypatch):
    assert lm.supports_gpt5_params("gpt-5.4-mini") is True
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    assert lm.supports_gpt5_params("gpt-5.4-mini") is True
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    assert lm.supports_gpt5_params("gpt-5.4-mini") is False  # provider excluded


def test_embed_dim_resolution(monkeypatch):
    assert lm.get_embed_dim() == 1536  # default model
    assert lm.get_embed_dim("text-embedding-3-large") == 3072
    assert lm.get_embed_dim("openai/text-embedding-3-large") == 3072  # namespaced
    assert lm.get_embed_dim("e5-mistral-7b-instruct") == 4096
    assert lm.get_embed_dim("unknown-model") == 1536  # safe fallback
    monkeypatch.setenv("EMBED_DIM", "512")
    get_settings.cache_clear()
    assert lm.get_embed_dim("text-embedding-3-large") == 512  # escape hatch wins
