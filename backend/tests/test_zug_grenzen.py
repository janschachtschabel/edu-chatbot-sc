"""Paket 19 (Audit 2026-10-31, M-4 / Entscheid P19-E3): Zug-Grenzen anonym und angemeldet.

Die äußere HTTP-Grenze der Züge (``/api/chat``, ``/api/chat/stream``, ``/api/agent``,
``/api/agent/stream``) ist im Studio einstellbar, getrennt für anonyme und angemeldete Aufrufer
(``01-base/safety-config`` → ``turn_limits``). Leer = ``RATE_LIMIT_CHAT`` wie bisher; gezählt wird
weiter je Route. „Angemeldet“ gilt nur, wenn der Zwischenspeicher von ``services/mcp/anmeldung``
die Person bestätigt hat, oder für einen internen Zug — ein gefälschter Block zählt anonym.

Dazu IPv6: der Schlüssel der Drosselung ist das /64-Netz (``ratelimit.drossel_schluessel``);
``peer_ip`` für die Logs bleibt die volle Adresse.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import boerdi.api.chat as chat_api
from boerdi.api import ratelimit
from boerdi.api.config_guards import modell_fehler
from boerdi.api.deps import get_session
from boerdi.api.schemas import ChatResponse
from boerdi.domain.config_models.base_governance import SafetyConfigArea, TurnLimitsBlock
from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.config_loader import load_turn_limits
from boerdi.services.mcp import anmeldung, auth
from boerdi.settings import get_settings

_SICHERHEIT = "01-base/safety-config"
_BLOCK = "wlo2.persoenlich-fuer-den-test"
_SCHLUESSEL = "studio-schluessel-fuer-zug-grenzen"


class _Store:
    def __init__(self, areas: dict) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    for name in ("RATE_LIMIT_CHAT", "TRUST_FORWARDED_FOR", "STUDIO_PASSWORD",
                 "BOERDI_ALLOW_OPEN_ADMIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STUDIO_API_KEY", _SCHLUESSEL)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    anmeldung._cache.clear()
    yield
    config_loader.bind_store(None)
    anmeldung._cache.clear()
    ratelimit.limiter.reset()


def _grenzen(anonym: str | None = None, angemeldet: str | None = None) -> None:
    block = {}
    if anonym is not None:
        block["anonymous"] = anonym
    if angemeldet is not None:
        block["authenticated"] = angemeldet
    config_loader.bind_store(_Store({_SICHERHEIT: {"turn_limits": block}}))


def _als_bestaetigt(block: str) -> None:
    anmeldung._cache[auth.fingerabdruck(block)] = (
        time.monotonic() + 300, anmeldung.Befund(person=True, kennung="p:x"))


# ── IPv6 /64 ───────────────────────────────────────────────────────────────


class _Anfrage:
    def __init__(self, host: str) -> None:
        self.headers: dict[str, str] = {}

        class _C:
            pass

        self.client = _C()
        self.client.host = host


def test_ipv6_zaehlt_je_64er_netz():
    a = ratelimit.drossel_schluessel(_Anfrage("2001:db8:1:2:aaaa::1"))
    b = ratelimit.drossel_schluessel(_Anfrage("2001:db8:1:2:bbbb:cccc:dddd:2"))
    c = ratelimit.drossel_schluessel(_Anfrage("2001:db8:1:3::1"))
    assert a == b == "2001:db8:1:2::/64"
    assert c != a


def test_ipv4_und_eingebettetes_ipv4_bleiben_die_adresse():
    assert ratelimit.drossel_schluessel(_Anfrage("10.0.0.5")) == "10.0.0.5"
    assert ratelimit.drossel_schluessel(_Anfrage("::ffff:10.0.0.5")) == "10.0.0.5"
    assert ratelimit.drossel_schluessel(_Anfrage("testclient")) == "testclient"


def test_peer_ip_fuer_die_logs_bleibt_die_volle_adresse():
    assert ratelimit.peer_ip(_Anfrage("2001:db8:1:2:aaaa::1")) == "2001:db8:1:2:aaaa::1"


def test_der_limiter_zaehlt_ipv6_je_netz():
    assert ratelimit.limiter._key_func is ratelimit.drossel_schluessel
