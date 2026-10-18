"""Betriebsschalter: im Studio gepflegt, die Umgebung geht vor (Paket 7, S1–S3).

Fast-Modus, Token-Streaming und die Schnellantworten des Agenten waren reine
Umgebungsvariablen. Seit Paket 7 stehen sie im Bereich ``01-base/engine``
(``betrieb``) und wirken ohne Neustart. Eine gesetzte Umgebungsvariable gilt
weiter — für einen Betrieb ohne Studio und als Notbremse.
"""

from __future__ import annotations

import pytest

from boerdi.domain.config_models.engine import EngineArea
from boerdi.services import betriebsschalter as bs
from boerdi.settings import get_settings

_UMGEBUNG = ("CHAT_TOKEN_STREAMING", "AGENT_INLINE_QUICK_REPLIES", "LLM_SERVICE_TIER")


@pytest.fixture(autouse=True)
def _ohne_umgebung(monkeypatch):
    for name in _UMGEBUNG:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _studio(monkeypatch, **betrieb) -> None:
    monkeypatch.setattr(bs, "load_engine",
                        lambda: EngineArea.model_validate({"betrieb": betrieb}))


def _umgebung(monkeypatch, name: str, wert: str) -> None:
    monkeypatch.setenv(name, wert)
    get_settings.cache_clear()


def test_die_vorgaben_ohne_studio_und_umgebung(monkeypatch):
    _studio(monkeypatch)
    assert bs.token_streaming() is True          # S2: Vorgabe an
    # S3: an seit Paket 15 — sonst streamt der Agent nicht (nur `respond_to_user` streamt).
    assert bs.agent_schnellantworten() is True
    assert bs.service_tier() == ""                # S1: Standard-Tarif


def test_das_studio_schaltet(monkeypatch):
    _studio(monkeypatch, fast_modus=True, token_streaming=False,
            agent_schnellantworten=True)
    assert bs.service_tier() == "fast"
    assert bs.token_streaming() is False
    assert bs.agent_schnellantworten() is True


@pytest.mark.parametrize(("umgebung", "studio", "erwartet"), [
    ("0", True, False), ("1", False, True),
])
def test_die_umgebung_geht_beim_streaming_vor(monkeypatch, umgebung, studio, erwartet):
    _studio(monkeypatch, token_streaming=studio)
    _umgebung(monkeypatch, "CHAT_TOKEN_STREAMING", umgebung)
    assert bs.token_streaming() is erwartet


@pytest.mark.parametrize(("umgebung", "studio", "erwartet"), [
    ("0", True, False), ("1", False, True),
])
def test_die_umgebung_geht_bei_den_schnellantworten_vor(monkeypatch, umgebung, studio,
                                                        erwartet):
    _studio(monkeypatch, agent_schnellantworten=studio)
    _umgebung(monkeypatch, "AGENT_INLINE_QUICK_REPLIES", umgebung)
    assert bs.agent_schnellantworten() is erwartet


def test_ein_gesetzter_tarif_geht_dem_studio_vor(monkeypatch):
    _studio(monkeypatch, fast_modus=True)
    _umgebung(monkeypatch, "LLM_SERVICE_TIER", "default")
    assert bs.service_tier() == "default"


def test_ein_unbekannter_tarif_gilt_als_nicht_gesetzt(monkeypatch):
    # Der Validator macht aus einem Tippfehler "" — dann entscheidet das Studio.
    _studio(monkeypatch, fast_modus=True)
    _umgebung(monkeypatch, "LLM_SERVICE_TIER", "schnell")
    assert bs.service_tier() == "fast"


def test_ein_leerer_wert_in_der_umgebung_gilt_als_nicht_gesetzt(monkeypatch):
    # compose reicht ``${CHAT_TOKEN_STREAMING:-}`` durch; ``env_ignore_empty``.
    _studio(monkeypatch, token_streaming=False)
    _umgebung(monkeypatch, "CHAT_TOKEN_STREAMING", "")
    assert bs.token_streaming() is False
