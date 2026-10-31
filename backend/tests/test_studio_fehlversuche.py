"""Paket 19 (Audit 2026-10-31, H-3 / Entscheid P19-E2): Passwortraten am Studio wird gebremst.

Das Cookie ist eine reine Funktion des Passworts (``studio_auth.studio_token``), also ließ es sich
lokal raten und an ``/studio/api/auth/session`` oder jede Proxy-Route schicken — gedrosselt war nur
``POST /studio/api/auth/login``. Dasselbe galt für ``X-Studio-Key`` an allen Verwaltungsrouten und
an ``/api/agent`` (``require_agent_caller`` läuft vor dem Decorator).

Jetzt zählen fehlgeschlagene Prüfungen eines VORGELEGTEN Cookies bzw. Schlüssels je IP; nach
:data:`fehlversuche.GRENZE` antwortet jede weitere Prüfung mit 429 — auch eine richtige, sonst
verriete 429/200 den Treffer. Wer gar nichts vorlegt, rät nicht und zählt nicht (erster Besuch im
Studio). Dazu eine Mindestlänge von 12 Zeichen für ``STUDIO_PASSWORD`` und ``STUDIO_API_KEY``.

Offline wie ``test_studio_bff.py``: ``TestClient`` ohne ``with``; die Probe ``/api/debug/mcp-test``
antwortet 501, sobald der Schlüssel durchkam.
"""

from __future__ import annotations

import asyncio
import itertools
import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from boerdi.api import fehlversuche, ratelimit
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.main import _warn_insecure_config, create_app
from boerdi.settings import get_settings

PASSWORT = "geheim-studio-pw"
SCHLUESSEL = "backend-key-0123456789"
PROBE_PROXY = "/studio/api/debug/mcp-test"
PROBE_DIREKT = "/api/debug/mcp-test"
SITZUNG = "/studio/api/auth/session"


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    monkeypatch.setenv("STUDIO_PASSWORD", PASSWORT)
    monkeypatch.setenv("STUDIO_API_KEY", SCHLUESSEL)
    for name in ("BOERDI_ALLOW_OPEN_ADMIN", "STUDIO_DIST_DIR", "AGENT_OPEN",
                 "TRUST_FORWARDED_FOR"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _mit_cookie(client: TestClient, pfad: str, wert: str):
    client.cookies.set(COOKIE_NAME, wert)
    try:
        return client.get(pfad)
    finally:
        client.cookies.clear()


_NUMMER = itertools.count()


def _falsches_cookie(client: TestClient, pfad: str = SITZUNG):
    """Jedes Mal ein ANDERER falscher Wert — derselbe zählt je IP nur einmal (Review, Punkt 3)."""
    return _mit_cookie(client, pfad, f"{next(_NUMMER):064d}")


def _falsch() -> dict[str, str]:
    return {"X-Studio-Key": f"falsch-{next(_NUMMER)}"}


# ── Cookie: Sitzungsabfrage und Proxy ──────────────────────────────────────


def test_falsche_cookies_an_der_sitzungsabfrage_enden_in_429(client):
    for _ in range(fehlversuche.GRENZE):
        assert _falsches_cookie(client).status_code == 401
    r = _falsches_cookie(client)
    assert r.status_code == 429
    assert r.headers.get("retry-after")


def test_nach_der_sperre_hilft_auch_das_richtige_cookie_nicht(client):
    """Sonst verriete 429 gegen 200 den Treffer — die Bremse wäre keine."""
    for _ in range(fehlversuche.GRENZE):
        _falsches_cookie(client)
    r = _mit_cookie(client, SITZUNG, studio_token(PASSWORT))
    assert r.status_code == 429


def test_falsche_cookies_am_proxy_zaehlen_mit(client):
    for _ in range(fehlversuche.GRENZE // 2):
        assert _falsches_cookie(client, PROBE_PROXY).status_code == 401
    for _ in range(fehlversuche.GRENZE - fehlversuche.GRENZE // 2):
        assert _falsches_cookie(client).status_code == 401
    assert _falsches_cookie(client, PROBE_PROXY).status_code == 429


def test_ohne_cookie_zaehlt_nichts(client):
    """Der erste Besuch fragt ohne Cookie — das ist kein Rateversuch."""
    for _ in range(fehlversuche.GRENZE + 3):
        assert client.get(SITZUNG).status_code == 401
    assert _mit_cookie(client, SITZUNG, studio_token(PASSWORT)).status_code == 200


def test_richtige_cookies_zaehlen_nicht(client):
    for _ in range(fehlversuche.GRENZE + 3):
        r = _mit_cookie(client, SITZUNG, studio_token(PASSWORT))
        assert r.status_code == 200


# ── X-Studio-Key: Verwaltungsrouten und /api/agent ─────────────────────────


def test_falsche_schluessel_an_verwaltungsrouten_enden_in_429(client):
    for _ in range(fehlversuche.GRENZE):
        assert client.get(PROBE_DIREKT, headers=_falsch()).status_code == 401
    assert client.get(PROBE_DIREKT, headers=_falsch()).status_code == 429
    # auch der richtige — dieselbe IP ist gesperrt
    assert client.get(PROBE_DIREKT, headers={"X-Studio-Key": SCHLUESSEL}).status_code == 429


def test_richtiger_schluessel_zaehlt_nicht(client):
    for _ in range(fehlversuche.GRENZE + 3):
        assert client.get(PROBE_DIREKT, headers={"X-Studio-Key": SCHLUESSEL}).status_code == 501


def test_falsche_schluessel_am_agent_endpunkt_zaehlen(client):
    """``require_agent_caller`` läuft vor dem slowapi-Decorator — dort griff keine Bremse."""
    koerper = {"instruction": "x"}
    for _ in range(fehlversuche.GRENZE):
        r = client.post("/api/agent", json=koerper, headers=_falsch())
        assert r.status_code == 401
    r = client.post("/api/agent", json=koerper, headers=_falsch())
    assert r.status_code == 429


def test_falsche_schluessel_am_chat_zaehlen_ohne_mehrfachzaehlung(monkeypatch):
    """``ist_interner_zug`` vergleicht den Schlüssel auch am Chat (Diagnose, Buchung) — sonst
    wäre der Chat ein ungebremstes Orakel. Gezählt wird einmal je Anfrage, egal wie oft die
    Prüfung im Zug läuft."""
    from boerdi.api.turn_auth import ist_interner_zug

    scope = {"type": "http", "method": "POST", "path": "/api/chat",
             "headers": [(b"x-studio-key", b"falsch")], "client": ("9.9.9.9", 1)}
    anfrage = Request(scope)
    for _ in range(5):
        assert ist_interner_zug(anfrage) is False
    zweite = Request(dict(scope, headers=[(b"x-studio-key", SCHLUESSEL.encode())]))
    # eine Fehlprüfung gezählt, nicht fünf: noch weit unter der Grenze
    assert ist_interner_zug(zweite) is True


def test_gesperrte_ip_bekommt_am_chat_429():
    from boerdi.api.turn_auth import ist_interner_zug

    def anfrage(schluessel: str) -> Request:
        return Request({"type": "http", "method": "POST", "path": "/api/chat",
                        "headers": [(b"x-studio-key", schluessel.encode())],
                        "client": ("9.9.9.8", 1)})

    for _ in range(fehlversuche.GRENZE):
        assert ist_interner_zug(anfrage(f"falsch-{next(_NUMMER)}")) is False
    # Review, Punkt 5: laut statt still — sonst sähen Eval und Lasttest ein irreführendes 422/401
    with pytest.raises(HTTPException) as e:
        ist_interner_zug(anfrage(SCHLUESSEL))
    assert e.value.status_code == 429


def test_die_sperre_gilt_je_ip(monkeypatch):
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    for _ in range(fehlversuche.GRENZE + 1):
        client.get(PROBE_DIREKT, headers={**_falsch(), "X-Forwarded-For": "1.1.1.1"})
    r = client.get(PROBE_DIREKT, headers={"X-Studio-Key": SCHLUESSEL,
                                          "X-Forwarded-For": "2.2.2.2"})
    assert r.status_code == 501


# ── Review-Nachbesserungen ─────────────────────────────────────────────────


@pytest.fixture()
def frische_drossel():
    from boerdi.obs import drossel

    drossel.zuruecksetzen()
    yield
    drossel.zuruecksetzen()


def test_derselbe_falsche_wert_zaehlt_nur_einmal(client):
    """Ein veraltetes Cookie im Browser, zwanzigmal neu geladen, sperrt niemanden aus."""
    for _ in range(fehlversuche.GRENZE + 5):
        assert _mit_cookie(client, SITZUNG, "f" * 64).status_code == 401
        r = client.get(PROBE_DIREKT, headers={"X-Studio-Key": "veraltet-1234"})
        assert r.status_code == 401
    assert _mit_cookie(client, SITZUNG, studio_token(PASSWORT)).status_code == 200


def test_eine_sperre_meldet_sich_im_log_und_im_zaehler(client, caplog, frische_drossel):
    from boerdi.obs import metrics

    vorher = metrics.STUDIO_FEHLVERSUCHE.labels("gesperrt")._value.get()
    fehl_vorher = metrics.STUDIO_FEHLVERSUCHE.labels("fehlversuch")._value.get()
    for _ in range(fehlversuche.GRENZE):
        _falsches_cookie(client)
    with caplog.at_level(logging.WARNING, logger="boerdi.api.fehlversuche"):
        for _ in range(3):
            assert _falsches_cookie(client).status_code == 429
    meldungen = [r for r in caplog.records if r.name == "boerdi.api.fehlversuche"]
    assert len(meldungen) == 1  # gedrosselt
    assert "testclient" not in meldungen[0].getMessage()  # ohne IP
    assert metrics.STUDIO_FEHLVERSUCHE.labels("gesperrt")._value.get() == vorher + 3
    assert metrics.STUDIO_FEHLVERSUCHE.labels("fehlversuch")._value.get() == (
        fehl_vorher + fehlversuche.GRENZE)


def test_faellt_der_zaehler_aus_bleibt_der_vergleich(client, monkeypatch, caplog,
                                                     frische_drossel):
    """Valkey weg: gezählt wird nicht (fail-open), geprüft wird weiter (fail-closed)."""
    def kaputt(*_a, **_k):
        raise ConnectionError("valkey weg")

    monkeypatch.setattr(ratelimit.limiter.limiter, "test", kaputt)
    monkeypatch.setattr(ratelimit.limiter.limiter, "hit", kaputt)
    with caplog.at_level(logging.WARNING, logger="boerdi.api.fehlversuche"):
        for _ in range(fehlversuche.GRENZE + 2):
            assert _falsches_cookie(client).status_code == 401
        assert _mit_cookie(client, SITZUNG, studio_token(PASSWORT)).status_code == 200
        assert client.get(PROBE_DIREKT, headers=_falsch()).status_code == 401
    meldungen = [r for r in caplog.records if r.name == "boerdi.api.fehlversuche"]
    assert len(meldungen) == 1
    assert not meldungen[0].exc_info


# ── Mindestlänge (P19-E2) ──────────────────────────────────────────────────


def test_ein_kurzes_passwort_haelt_das_studio_zu(monkeypatch, client):
    monkeypatch.setenv("STUDIO_PASSWORD", "kurz-11-zei")
    get_settings.cache_clear()
    r = _mit_cookie(client, SITZUNG, studio_token("kurz-11-zei"))
    assert r.status_code == 503
    assert "12" in r.json()["detail"]
    r = client.post("/studio/api/auth/login", json={"password": "kurz-11-zei"})
    assert r.status_code == 503
    assert "12" in r.json()["detail"]


def test_ein_kurzes_passwort_oeffnet_auch_mit_open_admin_nicht(monkeypatch, client):
    monkeypatch.setenv("STUDIO_PASSWORD", "kurz")
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    get_settings.cache_clear()
    assert client.get(SITZUNG).status_code == 503
    assert client.get(PROBE_PROXY).status_code == 503


def test_zwoelf_zeichen_genuegen(monkeypatch, client):
    monkeypatch.setenv("STUDIO_PASSWORD", "genau-12-zei")
    get_settings.cache_clear()
    r = _mit_cookie(client, SITZUNG, studio_token("genau-12-zei"))
    assert r.status_code == 200


def test_ein_kurzer_schluessel_haelt_die_verwaltung_zu(monkeypatch, client):
    monkeypatch.setenv("STUDIO_API_KEY", "kurz-11-zei")
    get_settings.cache_clear()
    r = client.get(PROBE_DIREKT, headers={"X-Studio-Key": "kurz-11-zei"})
    assert r.status_code == 503
    assert "12" in r.json()["detail"]


def test_ein_kurzer_schluessel_oeffnet_auch_mit_open_admin_nicht(monkeypatch):
    from boerdi.api.deps import require_studio_key
    from boerdi.api.turn_auth import darf_diagnose

    monkeypatch.setenv("STUDIO_API_KEY", "kurz")
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    get_settings.cache_clear()
    anfrage = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    with pytest.raises(HTTPException) as e:
        asyncio.run(require_studio_key(anfrage, None))
    assert e.value.status_code == 503
    # der Entwicklungsmodus (offen, OHNE Schlüssel) gilt nicht: ein Schlüssel ist gesetzt
    assert darf_diagnose(anfrage) is False


def test_der_start_meldet_kurze_geheimnisse_als_error(monkeypatch, caplog):
    monkeypatch.setenv("STUDIO_PASSWORD", "pw-xyz")
    monkeypatch.setenv("STUDIO_API_KEY", "key-xyz")
    get_settings.cache_clear()
    with caplog.at_level(logging.ERROR, logger="startup"):
        _warn_insecure_config(get_settings())
    fehler = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("STUDIO_PASSWORD" in m and "12" in m for m in fehler)
    assert any("STUDIO_API_KEY" in m and "12" in m for m in fehler)
    # nie der Wert selbst
    assert not any("pw-xyz" in m or "key-xyz" in m for m in fehler)
