"""Die OpenAI-Wege am Transport (Paket 7, L1/L2 und Responses-Plan Paket A).

Drei Dinge prüft diese Datei an den Parametern, die ``wire_transport`` an
LiteLLM übergibt:

* **Systemteil (Paket A, E-A1 = beide OpenAI-Wege):** LiteLLM 1.91 verbindet
  mehrere String-System-Nachrichten auf dem Weg über ``/v1/responses`` mit EINEM
  Leerzeichen zu ``instructions``; jede Block-Überschrift stand mitten in einer
  Zeile. ``llm_responses.systemteil_verbinden`` verbindet den Anfang vorher selbst.
* **Denktiefe und Ausführlichkeit (L2):** gemessen 2026-10-09 an einem lokalen
  Fang-Server — bei gpt-6 verwirft LiteLLM ``reasoning_effort`` und
  ``verbosity`` still, bei gpt-5.6 kam ``verbosity`` nie an. Sie gehen jetzt als
  ``extra_body`` dorthin, wo der Weg sie versteht.
* **Tarif (L1):** ``service_tier`` nur für die gpt-5- und gpt-6-Familie
  (Nutzer-Vorgabe 2026-10-09), nicht für Judge-Modelle wie gpt-4o-mini.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from litellm.completion_extras.litellm_responses_transformation.transformation import (
    LiteLLMResponsesTransformationHandler,
)

from boerdi.services import llm
from boerdi.services.llm_responses import systemteil_verbinden
from boerdi.settings import get_settings

KETTE = [
    {"role": "system", "content": "Du bist Boerdi.\nRegeln gelten vor jeder Anleitung."},
    {"role": "system", "content": "## Gesamtanleitung dieser Anlage\nInhalt."},
    {"role": "system", "content": "## Seitenkontext\nText."},
    {"role": "user", "content": "Hallo"},
]
WERKZEUG = [{"type": "function", "function": {
    "name": "suche", "description": "x", "parameters": {"type": "object", "properties": {}}}}]
_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY", "OPENAI_BASE_URL",
        "B_API_KEY", "B_API_BASE_URL", "B_API_CLEAR_CACHE", "LLM_VERBOSITY",
        "LLM_REASONING_EFFORT", "LLM_SERVICE_TIER")


def _instructions(messages: list[dict]) -> str | None:
    handler = LiteLLMResponsesTransformationHandler()
    return handler.convert_chat_completion_messages_to_responses_api(messages)[1]


# ── Systemteil: die reine Funktion ──────────────────────────────────────────
def test_litellm_verbindet_system_nachrichten_mit_einem_leerzeichen():
    """Kennlinie der Bibliothek — der Anlass für ``llm_responses``. Wird dieser
    Test nach einem LiteLLM-Update rot, verbindet LiteLLM anders: dann prüfen,
    ob ``systemteil_verbinden`` noch gebraucht wird."""
    assert _instructions(KETTE) == (
        "Du bist Boerdi.\nRegeln gelten vor jeder Anleitung. "
        "## Gesamtanleitung dieser Anlage\nInhalt. ## Seitenkontext\nText.")


def test_verbunden_beginnt_jede_ueberschrift_eine_zeile():
    assert _instructions(systemteil_verbinden(KETTE)) == (
        "Du bist Boerdi.\nRegeln gelten vor jeder Anleitung.\n\n"
        "## Gesamtanleitung dieser Anlage\nInhalt.\n\n## Seitenkontext\nText.")


def test_nur_der_anfang_wird_verbunden():
    """Eine System-Nachricht mitten in der Kette (Muster-Weg, UI-Box-Status)
    bleibt, wo sie ist: sie nach vorn zu holen wäre eine Änderung am Inhalt."""
    kette = [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "user", "content": "frage"},
        {"role": "tool", "tool_call_id": "t", "content": "treffer"},
        {"role": "system", "content": "Status"},
    ]
    assert systemteil_verbinden(kette) == [
        {"role": "system", "content": "A\n\nB"},
        {"role": "user", "content": "frage"},
        {"role": "tool", "tool_call_id": "t", "content": "treffer"},
        {"role": "system", "content": "Status"},
    ]


def test_ohne_zwei_system_texte_am_anfang_bleibt_die_liste():
    einer = [{"role": "system", "content": "A"}, {"role": "user", "content": "x"}]
    liste = [{"role": "system", "content": [{"type": "text", "text": "A"}]},
             {"role": "system", "content": "B"}, {"role": "user", "content": "x"}]
    assert systemteil_verbinden(einer) is einer
    assert systemteil_verbinden(liste) is liste
    assert systemteil_verbinden([]) == []


# ── am Transport ────────────────────────────────────────────────────────────
class _Fake:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        nachricht = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=nachricht)], usage=None, model="m")


@pytest.fixture
def senden(monkeypatch):
    def _senden(provider: str, modell: str, *, tarif: str = "", **aufruf) -> dict:
        for name in _ENV:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("LLM_CHAT_MODEL", modell)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("B_API_KEY", "bkey")
        monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
        monkeypatch.setenv("LLM_VERBOSITY", "low")
        if tarif:
            monkeypatch.setenv("LLM_SERVICE_TIER", tarif)
        get_settings.cache_clear()
        llm.reset()
        fake = _Fake()
        monkeypatch.setattr(llm, "_acompletion", fake)
        asyncio.run(llm.chat_completion(messages=[dict(m) for m in KETTE], **aufruf))
        return fake.calls[0]
    yield _senden
    get_settings.cache_clear()


@pytest.mark.parametrize(("provider", "modell"), [
    ("openai", "gpt-6-luna"),          # ausdrücklich über /v1/responses
    ("openai", "gpt-5.6-luna"),        # seit L2 ebenfalls ausdrücklich
    ("b-api-openai", "gpt-5.6-luna"),  # seit Paket 9 ebenfalls ausdrücklich
])
def test_openai_wege_senden_den_systemteil_verbunden(senden, provider, modell):
    gesendet = senden(provider, modell)
    assert [m["role"] for m in gesendet["messages"]] == ["system", "user"]
    assert gesendet["messages"][0]["content"].count("\n\n## ") == 2


def test_academiccloud_bekommt_die_nachrichten_einzeln(senden):
    gesendet = senden("b-api-academiccloud", "qwen3-30b-a3b-instruct-2507")
    assert gesendet["messages"] == KETTE


@pytest.mark.parametrize("provider", ["openai", "b-api-openai"])
@pytest.mark.parametrize("modell", ["gpt-6-luna", "gpt-5.6-luna"])
@pytest.mark.parametrize("tools", [None, WERKZEUG])
def test_responses_weg_bekommt_denktiefe_und_ausfuehrlichkeit_im_extra_body(
        senden, provider, modell, tools):
    gesendet = senden(provider, modell, tools=tools)
    assert gesendet["model"] == f"openai/responses/{modell}"
    assert gesendet["extra_body"]["reasoning"] == {"effort": "low"}
    assert gesendet["extra_body"]["text"] == {"verbosity": "low"}
    # Als eigene Parameter verwürfe LiteLLM sie (gpt-6) oder ließe sie fallen.
    assert "reasoning_effort" not in gesendet and "verbosity" not in gesendet


def test_mit_antwortformat_bleibt_text_frei(senden):
    # LiteLLM legt das Antwortformat in ``text.format``; ein ``text`` im
    # extra_body ersetzte es — die Ausführlichkeit entfällt hier.
    gesendet = senden("openai", "gpt-6-luna", response_format={"type": "json_object"})
    assert gesendet["extra_body"]["reasoning"] == {"effort": "low"}
    assert "text" not in gesendet["extra_body"]


@pytest.mark.parametrize(("provider", "modell"), [
    ("openai", "gpt-4o-mini"), ("openai", "gpt-4.1-mini"),
    ("b-api-academiccloud", "qwen3-30b-a3b-instruct-2507"),
])
def test_andere_modelle_bekommen_keine_gpt5_parameter(senden, provider, modell):
    gesendet = senden(provider, modell, tarif="flex")
    extra = gesendet.get("extra_body") or {}
    for name in ("reasoning", "text", "verbosity", "store"):  # store: Paket 19 (H-2)
        assert name not in extra, (modell, name)
    for name in ("reasoning_effort", "verbosity", "service_tier"):
        assert name not in gesendet, (modell, name)


@pytest.mark.parametrize("modell", ["gpt-6-luna", "gpt-5.6-luna", "gpt-5.4-mini", "gpt-5-mini"])
def test_der_tarif_gilt_nur_fuer_die_gpt5_und_gpt6_familie(senden, modell):
    assert senden("openai", modell, tarif="fast")["service_tier"] == "fast"


def test_der_tarif_gilt_nicht_hinter_der_b_api(senden):
    assert "service_tier" not in senden("b-api-openai", "gpt-5.6-luna", tarif="fast")
