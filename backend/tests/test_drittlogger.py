"""Paket 18C/D (2.2/2.3): Fremd-Logger tragen keine Inhalte ins Log.

Laufzeitprobe 2026-10-29 (Grundlage §5.1): LiteLLM schreibt auf DEBUG ganze Anfragen samt
Prompt, das OpenAI-SDK die Request-Optionen, der MCP-Client die JSON-RPC-Nachrichten samt
Argumenten und Ergebnissen. LiteLLM hängt dazu einen eigenen stderr-Handler an — jede Zeile
erschien zweimal, einmal am JSON-Format und an jeder Deckelung vorbei. ``slowapi`` meldet jede
Drosselung mit der IP als Schlüssel.

Ohne ``LOG_CONTENT`` stehen die inhaltstragenden Logger auf WARNING; mit dem Schalter folgen sie
der Wurzel. Rauschen und Adressen (``httpx``, ``httpcore``, ``h11``, ``uvicorn.access``,
``slowapi``) bleiben auch mit Schalter gedeckelt — der Schalter gilt Inhalten, nicht IPs.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from boerdi.obs import drittlogger

_LITELLM = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")


@pytest.fixture(autouse=True)
def _zustand_zurueck():
    namen = [*drittlogger.INHALT_LOGGER, *drittlogger.GEDECKELT]
    vorher = {n: (logging.getLogger(n).level, list(logging.getLogger(n).handlers),
                  logging.getLogger(n).propagate) for n in namen}
    yield
    for name, (stufe, handler, weiter) in vorher.items():
        lg = logging.getLogger(name)
        lg.setLevel(stufe)
        lg.handlers[:] = handler
        lg.propagate = weiter


@pytest.mark.parametrize("name", drittlogger.INHALT_LOGGER)
def test_inhaltstragende_logger_stehen_ohne_schalter_auf_warning(name):
    drittlogger.drittlogger_einstellen(log_content=False)
    assert logging.getLogger(name).level == logging.WARNING


@pytest.mark.parametrize("name", drittlogger.INHALT_LOGGER)
def test_mit_schalter_folgen_sie_der_wurzel(name):
    drittlogger.drittlogger_einstellen(log_content=True)
    assert logging.getLogger(name).level == logging.NOTSET


@pytest.mark.parametrize("log_content", [False, True])
def test_rauschen_und_adressen_bleiben_auch_mit_schalter_gedeckelt(log_content):
    drittlogger.drittlogger_einstellen(log_content=log_content)
    assert {n: logging.getLogger(n).level for n in drittlogger.GEDECKELT} == drittlogger.GEDECKELT
    assert drittlogger.GEDECKELT["slowapi"] == logging.ERROR


def test_litellm_ohne_eigenen_handler_auch_nach_einem_aufruf():
    import litellm

    drittlogger.drittlogger_einstellen(log_content=False)
    asyncio.run(litellm.acompletion(model="gpt-4o-mini", mock_response="ok",
                                    messages=[{"role": "user", "content": "x"}]))
    for name in _LITELLM:
        lg = logging.getLogger(name)
        assert (lg.handlers, lg.propagate, lg.level) == ([], True, logging.WARNING), name


def test_die_logging_einrichtung_stellt_sie_ein(monkeypatch):
    from boerdi.main import _configure_logging
    from boerdi.settings import Settings

    wurzel = logging.getLogger()
    alte = wurzel.handlers[:]
    try:
        _configure_logging(Settings(_env_file=None))
    finally:
        wurzel.handlers[:] = alte
    assert logging.getLogger("LiteLLM").handlers == []
    assert logging.getLogger("mcp").level == logging.WARNING


def test_der_schalter_ist_vorgabe_aus_und_laesst_sich_setzen(monkeypatch):
    from boerdi.settings import Settings

    assert Settings(_env_file=None).log_content is False
    monkeypatch.setenv("LOG_CONTENT", "true")
    assert Settings(_env_file=None).log_content is True


def test_mit_schalter_warnt_der_start(monkeypatch, caplog):
    from boerdi.main import _warn_insecure_config
    from boerdi.settings import Settings

    monkeypatch.setenv("LOG_CONTENT", "true")
    with caplog.at_level(logging.WARNING, logger="boerdi.main"):
        _warn_insecure_config(Settings(_env_file=None))
    assert any("LOG_CONTENT" in r.getMessage() for r in caplog.records)
