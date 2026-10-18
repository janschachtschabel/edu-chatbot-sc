"""Paket 13 (A1): der Weg eines Modellaufrufs als Daten — für die Messbedingungen.

Ein Lauf soll sagen, *wie* er das Modell erreichte: Anbieter, Schnittstelle (Responses
oder Chat), Server und die Denkparameter, die wirklich mitgehen. ``llm.route`` entscheidet
das schon; ``weg_beschreibung`` liefert dieselbe Entscheidung ohne Schlüssel.
"""

from __future__ import annotations

from boerdi.services import llm_weg
from boerdi.settings import get_settings


def test_openai_direkt_gpt6_geht_ueber_responses(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-geheim")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    weg = llm_weg.weg_beschreibung("gpt-6-luna")
    assert weg["anbieter"] == "openai"
    assert weg["modell"] == "gpt-6-luna"
    assert weg["api"] == "responses"
    assert weg["basis"] == "api.openai.com/v1"
    assert weg["denkparameter"] is True


def test_academiccloud_bleibt_auf_chat(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example.org/api/v1/llm")
    get_settings.cache_clear()
    weg = llm_weg.weg_beschreibung("qwen3-30b-a3b-instruct-2507")
    assert weg["api"] == "chat"
    assert weg["basis"] == "b-api.example.org/api/v1/llm/academiccloud"
    assert weg["denkparameter"] is False
    assert weg["reasoning_effort"] is None


def test_kein_schluessel_in_der_beschreibung(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "b-geheim")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-geheim")
    get_settings.cache_clear()
    text = repr(llm_weg.weg_beschreibung("gpt-6-luna"))
    assert "geheim" not in text


def test_ohne_modell_gilt_das_chat_modell(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-6-luna")
    get_settings.cache_clear()
    assert llm_weg.weg_beschreibung()["modell"] == "gpt-6-luna"
