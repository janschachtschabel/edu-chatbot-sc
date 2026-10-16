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
    assert lm.get_chat_model() == "gpt-6-luna"  # legacy var ignored off-openai


def test_provider_defaults():
    # Paket 8 (Nutzer 2026-10-09): Standard ist gpt-6-luna — direkt wie über die b-api.
    assert lm.get_chat_model() == "gpt-6-luna"
    assert lm.get_embed_model() == "text-embedding-3-small"


def test_academiccloud_defaults(monkeypatch):
    """Paket 8 (L8): beide alten Vorgaben fehlen in ``/academiccloud/models``
    (Probe 2026-10-09). Die Einbettung bleibt im Raum der Wissensbasis und läuft
    über den OpenAI-Pfad der b-api (``llm.route``)."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    assert lm.get_chat_model() == "qwen3-30b-a3b-instruct-2507"
    assert lm.get_embed_model() == "text-embedding-3-small"
    assert lm.get_embed_dim() == 1536


def test_is_gpt5_model_family():
    assert lm.is_gpt5_model("gpt-5.6-luna") is True
    assert lm.is_gpt5_model("o3-mini") is True
    assert lm.is_gpt5_model("gpt-4.1-mini") is False
    assert lm.is_gpt5_model("") is True  # falls back to default chat model (gpt-6-luna)


def test_supports_gpt5_params_provider_gate(monkeypatch):
    assert lm.supports_gpt5_params("gpt-5.6-luna") is True
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    assert lm.supports_gpt5_params("gpt-5.6-luna") is True
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    assert lm.supports_gpt5_params("gpt-5.6-luna") is False  # provider excluded


def test_gpt6_hat_eine_eigene_regelgruppe():
    # Ohne Gruppe fiel gpt-6-luna auf _CLASSIC: temperature und max_tokens gingen
    # mit, reasoning_effort fehlte — jedes davon allein ein 400er (gemessen
    # 2026-09-26). Seit Paket 7 (L2) nimmt auch gpt-5.6 bei OpenAI direkt den
    # Responses-Weg ausdrücklich: nur dort kommen Denktiefe und Ausführlichkeit an.
    assert lm.param_rules("gpt-6-luna") == lm.ParamRules(
        gpt5_params=True, effort_with_tools=True, temperature_on_none=False,
        responses_api=True, gpt5_familie=True)
    assert lm.param_rules("gpt-5.6-luna").responses_api is True
    assert lm.is_gpt5_model("gpt-6-luna") is True
    # Ausführlichkeit und Tarif nur für die gpt-5-/gpt-6-Familie (Nutzer 2026-10-09).
    assert lm.param_rules("gpt-5.4-mini").gpt5_familie is True
    assert lm.param_rules("o3-mini").gpt5_familie is False


def test_embed_dim_resolution(monkeypatch):
    assert lm.get_embed_dim() == 1536  # default model
    assert lm.get_embed_dim("text-embedding-3-large") == 3072
    assert lm.get_embed_dim("openai/text-embedding-3-large") == 3072  # namespaced
    assert lm.get_embed_dim("e5-mistral-7b-instruct") == 4096
    assert lm.get_embed_dim("unknown-model") == 1536  # safe fallback
    monkeypatch.setenv("EMBED_DIM", "512")
    get_settings.cache_clear()
    assert lm.get_embed_dim("text-embedding-3-large") == 512  # escape hatch wins
