"""Paket 17 (A1/A2): der B-API-Router als Ziel des Chat-Modells.

``B_API_ROUTE`` nennt eine Route der b-api (``/api/v1/llm/router``). Sie ersetzt nur den
Namen, unter dem das eingestellte Chat-Modell hinausgeht; die Parameterregeln bleiben die
des Chat-Modells (eine Route bündelt laut b-api nur Modelle EINER Familie). Einbettungen
und ausdrücklich andere Modelle (Judge, Simulator) bleiben auf ``/openai``.
"""

from __future__ import annotations

import logging

import pytest

from boerdi.main import _warn_insecure_config
from boerdi.services import llm, llm_weg
from boerdi.services.llm_models import get_chat_model
from boerdi.services.llm_responses import RESPONSES_PRAEFIX
from boerdi.settings import get_settings

BASIS = "https://b-api.example.org/api/v1/llm"


@pytest.fixture
def b_api(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_BASE_URL", BASIS)
    monkeypatch.setenv("B_API_KEY", "b-geheim")
    monkeypatch.delenv("LLM_CHAT_MODEL", raising=False)
    monkeypatch.delenv("B_API_ROUTE", raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _mit_route(mp, name: str = "boerdi-test-luna") -> None:
    mp.setenv("B_API_ROUTE", name)
    get_settings.cache_clear()


def test_ohne_route_bleibt_der_openai_pfad(b_api) -> None:
    modell, basis, _schluessel, _kopf = llm.route(get_chat_model())
    assert basis == f"{BASIS}/openai"
    assert modell == f"{RESPONSES_PRAEFIX}gpt-6-luna"


def test_mit_route_geht_das_chat_modell_an_den_router(b_api) -> None:
    _mit_route(b_api)
    modell, basis, _schluessel, _kopf = llm.route(get_chat_model())
    assert basis == f"{BASIS}/router"
    # gpt-6 geht über Responses — auch unter dem Routennamen.
    assert modell == f"{RESPONSES_PRAEFIX}boerdi-test-luna"


def test_route_traegt_die_parameter_des_chat_modells(b_api) -> None:
    _mit_route(b_api)
    kwargs = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "Hallo"}], temperature=0.4, max_tokens=50,
    )
    llm.wire_transport(get_chat_model(), kwargs)
    assert kwargs["model"].endswith("boerdi-test-luna")
    assert kwargs["api_base"] == f"{BASIS}/router"
    # GPT-5-Familie: weder ``max_tokens`` noch ``temperature`` (die Route lehnt sie mit 400 ab,
    # gemessen 2026-10-20) — dafür die Denkparameter.
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs


def test_einbettungen_bleiben_auf_dem_openai_pfad(b_api) -> None:
    _mit_route(b_api)
    modell, basis, _schluessel, _kopf = llm.route("text-embedding-3-small")
    assert basis == f"{BASIS}/openai"
    assert modell == "openai/text-embedding-3-small"


def test_ein_anderes_modell_geht_nicht_ueber_die_route(b_api) -> None:
    _mit_route(b_api)
    modell, basis, _schluessel, _kopf = llm.route("gpt-5.4-mini")
    assert basis == f"{BASIS}/openai"
    assert modell == "openai/gpt-5.4-mini"


def test_route_wirkt_nur_bei_b_api_openai(b_api) -> None:
    b_api.setenv("LLM_PROVIDER", "openai")
    b_api.setenv("OPENAI_API_KEY", "sk-geheim")
    _mit_route(b_api)
    _modell, basis, _schluessel, _kopf = llm.route(get_chat_model())
    assert basis == "https://api.openai.com/v1"


def test_warnung_wenn_die_route_nicht_wirkt(b_api, caplog) -> None:
    b_api.setenv("LLM_PROVIDER", "openai")
    _mit_route(b_api)
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert any("B_API_ROUTE" in r.getMessage() for r in caplog.records)


def test_keine_warnung_wenn_die_route_wirkt(b_api, caplog) -> None:
    _mit_route(b_api)
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert not any("B_API_ROUTE" in r.getMessage() for r in caplog.records)


def test_weg_nennt_die_route(b_api) -> None:
    _mit_route(b_api)
    weg = llm_weg.weg_beschreibung()
    assert weg["modell"] == "gpt-6-luna"
    assert weg["route"] == "boerdi-test-luna"
    assert weg["basis"] == "b-api.example.org/api/v1/llm/router"
    assert weg["api"] == "responses"


def test_weg_ohne_route(b_api) -> None:
    assert llm_weg.weg_beschreibung()["route"] is None


# ── A5-Befund (live, 2026-10-20): LiteLLM meldet den ROUTENNAMEN als ``resp.model``,
# das antwortende Upstream-Modell geht verloren. Gebucht wird darum unter dem Regel-Modell.

def test_antwort_modell_unter_route_ist_das_chat_modell(b_api) -> None:
    _mit_route(b_api)
    assert llm.antwort_modell("boerdi-test-luna", "gpt-6-luna") == "gpt-6-luna"
    # Ein echter Upstream-Name bleibt stehen (falls die b-api ihn künftig meldet).
    assert llm.antwort_modell("gpt-5.6-luna", "gpt-6-luna") == "gpt-5.6-luna"


def test_antwort_modell_ohne_route_unveraendert(b_api) -> None:
    assert llm.antwort_modell("boerdi-test-luna", "gpt-6-luna") == "boerdi-test-luna"


async def test_buchung_unter_route_traegt_das_chat_modell(b_api) -> None:
    from types import SimpleNamespace

    from boerdi.obs import usage

    _mit_route(b_api)

    async def fake(**_kwargs):
        msg = SimpleNamespace(content="OK", tool_calls=None)
        return SimpleNamespace(
            model="boerdi-test-luna",
            choices=[SimpleNamespace(message=msg, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2,
                                  prompt_tokens_details=None, completion_tokens_details=None),
        )

    b_api.setattr(llm, "_acompletion", fake)
    acc = usage.new_accumulator()
    await llm.chat_completion(messages=[{"role": "user", "content": "x"}], usage_acc=acc)
    assert list(acc["models"]) == ["gpt-6-luna"]


# ── Review Phase A (2026-10-20) ─────────────────────────────────────────────

def test_route_bei_openai_direkt_geht_mit_dem_modellnamen_hinaus(b_api) -> None:
    """Befund 3: ohne die Anbieter-Prüfung ginge ``responses/<route>`` an OpenAI direkt."""
    b_api.setenv("LLM_PROVIDER", "openai")
    b_api.setenv("OPENAI_API_KEY", "sk-geheim")
    _mit_route(b_api)
    modell, _basis, _schluessel, _kopf = llm.route(get_chat_model())
    assert modell == f"{RESPONSES_PRAEFIX}gpt-6-luna"
    assert llm.router_route(get_chat_model()) is None


def test_route_auf_der_academiccloud_wirkt_nicht(b_api) -> None:
    b_api.setenv("LLM_PROVIDER", "b-api-academiccloud")
    _mit_route(b_api)
    modell, basis, _schluessel, _kopf = llm.route(get_chat_model())
    assert basis == f"{BASIS}/academiccloud"
    assert "boerdi-test-luna" not in modell


def test_warnung_wenn_das_chat_modell_der_routenname_ist(b_api, caplog) -> None:
    """Befund 2: ``LLM_CHAT_MODEL=<Route>`` ist die naheliegende Verwechslung — die Regeln
    fielen auf die klassischen (``temperature``/``max_tokens`` → 400 an einer gpt-6-Route)."""
    b_api.setenv("LLM_CHAT_MODEL", "boerdi-test-luna")
    _mit_route(b_api)
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert any("LLM_CHAT_MODEL" in r.getMessage() for r in caplog.records)


def test_ohne_route_keine_routen_warnung_fuer_einen_unbekannten_namen(b_api, caplog) -> None:
    """Ohne ``B_API_ROUTE`` ist ein unbekannter Modellname kein Routen-Fehler."""
    b_api.setenv("LLM_CHAT_MODEL", "boerdi-test-luna")
    get_settings.cache_clear()
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(get_settings())
    assert not any("LLM_CHAT_MODEL" in r.getMessage() for r in caplog.records), (
        "ohne Route ist ein unbekannter Modellname kein Routen-Fehler — keine Warnung")


async def test_strom_unter_route_bucht_das_chat_modell(b_api) -> None:
    """Befund 4: auch der Strom (``llm_streaming``) bildet den Routennamen zurück ab."""
    from types import SimpleNamespace

    from boerdi.obs import usage
    from boerdi.services.llm_streaming import _stream_completion

    _mit_route(b_api)

    async def _chunks():
        delta = SimpleNamespace(role="assistant", content="OK", tool_calls=None)
        yield SimpleNamespace(model="boerdi-test-luna", usage=None,
                              choices=[SimpleNamespace(delta=delta, finish_reason=None)])
        yield SimpleNamespace(
            model="boerdi-test-luna", choices=[],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=1,
                                  prompt_tokens_details=None, completion_tokens_details=None))

    async def fake(**_kwargs):
        return _chunks()

    b_api.setattr(llm, "_acompletion", fake)
    resp = await _stream_completion(lambda _t: None, messages=[{"role": "user", "content": "x"}])
    acc = usage.new_accumulator()
    usage.add_usage(acc, usage.extract_usage(resp))
    assert list(acc["models"]) == ["gpt-6-luna"]
