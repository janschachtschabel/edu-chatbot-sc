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


# ── Modell, Lader, Speichern ───────────────────────────────────────────────


@pytest.mark.parametrize("wert", ["", "off", "OFF", "30/minute", "10/second;500/hour"])
def test_gueltige_werte(wert):
    assert TurnLimitsBlock(anonymous=wert, authenticated=wert).anonymous == wert


@pytest.mark.parametrize("wert", ["viel", "30 pro minute", "30/fortnight"])
def test_ungueltige_werte_werden_beim_speichern_abgewiesen(wert):
    with pytest.raises(ValidationError):
        SafetyConfigArea.model_validate({"turn_limits": {"anonymous": wert}})
    fehler = modell_fehler(_SICHERHEIT, {"turn_limits": {"authenticated": wert}})
    assert fehler and "turn_limits" in str(fehler)


def test_vorgabe_beide_wie_rate_limit_chat(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "77/minute")
    get_settings.cache_clear()
    assert load_turn_limits() == {"anonymous": "77/minute", "authenticated": "77/minute"}
    _grenzen(anonym="", angemeldet="  ")
    assert load_turn_limits() == {"anonymous": "77/minute", "authenticated": "77/minute"}


def test_studio_werte_gelten(monkeypatch):
    _grenzen(anonym="5/minute", angemeldet="off")
    assert load_turn_limits() == {"anonymous": "5/minute", "authenticated": "off"}


def test_ein_kaputter_gespeicherter_wert_faellt_auf_die_vorgabe(monkeypatch):
    """Am Speichern vorbei (direkt in der DB) — der Zug darf daran nicht scheitern."""
    monkeypatch.setenv("RATE_LIMIT_CHAT", "77/minute")
    get_settings.cache_clear()
    config_loader.bind_store(_Store({_SICHERHEIT: {"turn_limits": {"anonymous": "kaputt",
                                                                    "authenticated": 5}}}))
    assert load_turn_limits() == {"anonymous": "77/minute", "authenticated": "77/minute"}


def test_der_startwaechter_fuer_rate_limit_chat_bleibt(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "kaputt")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


# ── Wirkung am Chat ────────────────────────────────────────────────────────


@pytest.fixture()
def chat(monkeypatch):
    class _Graph:
        async def ainvoke(self, state):
            return {"response": ChatResponse(session_id="bb-1", content="OK")}

    async def _pp(req, resp, *a, **k):
        return resp

    monkeypatch.setattr(chat_api, "build_turn_graph", lambda **k: _Graph())
    monkeypatch.setattr(chat_api, "_postprocess_response_for_widget_modes", _pp)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "100/minute")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    client = TestClient(app, raise_server_exceptions=False)

    def senden(**koepfe: str):
        return client.post("/api/chat", json={"session_id": "bb-zug-grenzen-test",
                                              "message": "hallo"}, headers=koepfe)

    return senden


def test_anonyme_zuege_folgen_der_anonymen_grenze(chat):
    _grenzen(anonym="2/minute", angemeldet="5/minute")
    assert chat().status_code == 200
    assert chat().status_code == 200
    assert chat().status_code == 429


def test_bestaetigte_personen_folgen_der_angemeldeten_grenze(chat):
    _grenzen(anonym="1/minute", angemeldet="3/minute")
    _als_bestaetigt(_BLOCK)
    for _ in range(3):
        assert chat(**{"WLO-Access-Block": _BLOCK}).status_code == 200
    assert chat(**{"WLO-Access-Block": _BLOCK}).status_code == 429


def test_ein_gefaelschter_block_zaehlt_anonym(chat):
    """Die Form allein reicht nicht — nur der Zwischenspeicher der Anmeldung zählt."""
    _grenzen(anonym="1/minute", angemeldet="50/minute")
    assert chat(**{"WLO-Access-Block": "wlo2.gefaelscht"}).status_code == 200
    assert chat(**{"WLO-Access-Block": "wlo2.gefaelscht-zwei"}).status_code == 429


def test_ein_abgelaufener_eintrag_zaehlt_anonym(chat):
    _grenzen(anonym="1/minute", angemeldet="50/minute")
    anmeldung._cache[auth.fingerabdruck(_BLOCK)] = (
        time.monotonic() - 1, anmeldung.Befund(person=True, kennung="p:x"))
    assert chat(**{"WLO-Access-Block": "wlo2.jemand-anderes"}).status_code == 200
    assert chat(**{"WLO-Access-Block": _BLOCK}).status_code == 429


def test_ein_interner_zug_folgt_der_angemeldeten_grenze(chat):
    _grenzen(anonym="1/minute", angemeldet="3/minute")
    for _ in range(3):
        assert chat(**{"X-Studio-Key": _SCHLUESSEL}).status_code == 200
    assert chat(**{"X-Studio-Key": _SCHLUESSEL}).status_code == 429


def test_aus_schaltet_nur_die_eine_stufe_ab(chat):
    _grenzen(anonym="off", angemeldet="1/minute")
    for _ in range(5):
        assert chat().status_code == 200
    r = chat()
    assert "x-ratelimit-limit" not in {k.lower() for k in r.headers}


def test_ohne_studio_wert_gilt_rate_limit_chat(chat, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()
    assert chat().status_code == 200
    assert chat().status_code == 200
    assert chat().status_code == 429


def test_die_aenderung_im_studio_wirkt_ohne_neustart(chat):
    _grenzen(anonym="1/minute")
    assert chat().status_code == 200
    assert chat().status_code == 429
    _grenzen(anonym="5/minute")
    assert chat().status_code == 200


# ── Review, Punkt 7: Studio lockert den Betreiber-Schutz ───────────────────


@pytest.mark.parametrize("wert,vorgabe,lockerer", [
    ("off", "120/minute", True),
    ("200/minute", "120/minute", True),
    ("120/minute", "120/minute", False),
    ("60/minute", "120/minute", False),
    ("3/second", "120/minute", True),       # 180 je Minute
    ("1/second", "120/minute", False),      # 60 je Minute
    ("10/second;100/minute", "120/minute", False),
    ("100/minute", "10/second;500/hour", True),  # 6 000 je Stunde
    ("100/minute", "off", False),
    ("off", "off", False),
])
def test_ist_lockerer(wert, vorgabe, lockerer):
    from boerdi.settings import ist_lockerer

    assert ist_lockerer(wert, vorgabe) is lockerer


def test_lockerer_wert_warnt_beim_laden(monkeypatch, caplog):
    from boerdi.obs import drossel

    drossel.zuruecksetzen()
    monkeypatch.setenv("RATE_LIMIT_CHAT", "120/minute")
    get_settings.cache_clear()
    _grenzen(anonym="off", angemeldet="60/minute")
    with caplog.at_level("WARNING"):
        load_turn_limits()
        load_turn_limits()
    meldungen = [r.getMessage() for r in caplog.records if "lockerer" in r.getMessage()]
    assert len(meldungen) == 1  # gedrosselt, nur die anonyme Stufe
    assert "anonymous" in meldungen[0]
    drossel.zuruecksetzen()


def test_lockerer_wert_warnt_beim_speichern(monkeypatch, caplog):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "120/minute")
    get_settings.cache_clear()
    with caplog.at_level("WARNING"):
        assert modell_fehler(_SICHERHEIT, {"turn_limits": {"authenticated": "500/minute"}}) == []
    assert any("lockerer" in r.getMessage() for r in caplog.records)
