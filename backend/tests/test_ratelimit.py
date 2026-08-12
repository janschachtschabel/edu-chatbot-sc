"""P1-4: HTTP-layer rate limit (slowapi, improvement V7 — default ON for
public endpoints) with ALT ``_peer_ip`` key semantics: X-Forwarded-For is
honoured ONLY when TRUST_FORWARDED_FOR is set (own reverse proxy), otherwise
the spoofable header is ignored.

This here is the OUTER HTTP guard. The config-driven per-session window from
safety-config.yaml is a separate, inner brake — built in C6, tested in
``test_rate_limits_config.py`` and wired in ``test_preflight_node.py``.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from limits import parse_many

from boerdi.api import ratelimit
from boerdi.main import create_app
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_limits(monkeypatch):
    for name in ("RATE_LIMIT_CHAT", "TRUST_FORWARDED_FOR"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


def _hit_limited(client, **headers):
    # The limiter mechanics need a PUBLIC, rate-limited route that answers
    # deterministically WITHOUT a DB session/lifespan. Post-P7 the only such route
    # is the speech status probe (@public_rate_limit, settings-only → 200). The
    # former stub targets (/api/speech/transcribe, /api/sessions/{id}/messages) are
    # now implemented and DB-backed, which would mask the limiter behind a 500/422.
    return client.get("/api/speech/status", headers=headers)


def test_limit_fires_on_public_stub(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert _hit_limited(client).status_code == 200
    assert _hit_limited(client).status_code == 200
    r = _hit_limited(client)
    assert r.status_code == 429


def test_xff_ignored_without_trust(monkeypatch):
    # spoofed X-Forwarded-For must NOT split the bucket
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert _hit_limited(client, **{"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert _hit_limited(client, **{"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert _hit_limited(client, **{"X-Forwarded-For": "3.3.3.3"}).status_code == 429


def test_xff_honoured_with_trust(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert _hit_limited(client, **{"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert _hit_limited(client, **{"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # same client IP, different trusted XFF => separate bucket, not limited
    assert _hit_limited(client, **{"X-Forwarded-For": "9.9.9.9"}).status_code == 200
    # but the exhausted bucket stays limited
    assert _hit_limited(client, **{"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_off_switch_disables_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    client = TestClient(create_app())
    for _ in range(5):
        assert _hit_limited(client).status_code == 200


def test_off_switch_is_silent_and_counts_nothing(monkeypatch, caplog):
    """"off" must not reach slowapi's parser — no ERROR line, no counting.

    Regression: ``_chat_limit`` used to hand the raw token to slowapi, whose
    dynamic-limit parse runs once PER REQUEST (extension.py:591-600). Every
    request logged ``failed to load ratelimit for view function … (couldn't
    parse rate limit string 'off')`` at ERROR, which makes a production log
    with the limit disabled unusable. The limit did not apply — but only as a
    side effect of that failure: the parse builds the ``Limit`` objects that
    carry ``exempt_when``, so the off-switch itself never ran.
    """
    monkeypatch.setenv("RATE_LIMIT_CHAT", "off")
    get_settings.cache_clear()
    client = TestClient(create_app())

    with caplog.at_level(logging.DEBUG, logger="slowapi"):
        for _ in range(3):
            r = _hit_limited(client)
            assert r.status_code == 200

    # WARNING+, not just ERROR: the "ratelimit … exceeded" line is a WARNING,
    # so this also pins that no limit fired.
    assert [
        rec.getMessage()
        for rec in caplog.records
        if rec.name == "slowapi" and rec.levelno >= logging.WARNING
    ] == []
    # An exempt limit is skipped before ``hit()``, leaving view_rate_limit None
    # => no headers. Their absence proves the placeholder is not being counted.
    assert "X-RateLimit-Limit" not in r.headers


@pytest.mark.parametrize("token", ratelimit._OFF_TOKENS)
def test_every_off_token_yields_a_parseable_limit(monkeypatch, token):
    # All five tokens hit the same parser, so pin all five, not just "off".
    monkeypatch.setenv("RATE_LIMIT_CHAT", token)
    get_settings.cache_clear()
    assert ratelimit._limit_disabled() is True
    parse_many(ratelimit._chat_limit())  # must not raise


def test_active_limit_is_passed_through_verbatim(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT", "7/minute")
    get_settings.cache_clear()
    assert ratelimit._limit_disabled() is False
    assert ratelimit._chat_limit() == "7/minute"


def test_public_history_route_is_limited(monkeypatch):
    # The sessions widget-history route (GET /{id}/messages) is public +
    # @public_rate_limit; it is DB-backed (R6/P7), so override the session dep and
    # fake the service — then the limiter (not a 500) is what the assertions see.
    # This pins the limiter on THIS route specifically (distinct from the
    # /api/speech/status mechanics tests above).
    import boerdi.api.sessions as sessions_api
    from boerdi.api.deps import get_session

    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()

    async def _fake_messages(*a, **k):
        return []

    monkeypatch.setattr(sessions_api, "get_messages", _fake_messages)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    client = TestClient(app)
    sid = "bb-0123456789abcdef0123456789abcdef"
    assert client.get(f"/api/sessions/{sid}/messages").status_code == 200
    assert client.get(f"/api/sessions/{sid}/messages").status_code == 200
    assert client.get(f"/api/sessions/{sid}/messages").status_code == 429


class _FakeRequest:
    def __init__(self, headers: dict[str, str], host: str = "10.0.0.5"):
        self.headers = headers

        class _C:  # request.client
            pass

        self.client = _C()
        self.client.host = host


def test_peer_ip_untrusted_uses_client_host(monkeypatch):
    monkeypatch.delenv("TRUST_FORWARDED_FOR", raising=False)
    get_settings.cache_clear()
    req = _FakeRequest({"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert ratelimit.peer_ip(req) == "10.0.0.5"


def test_peer_ip_trusted_takes_first_xff_entry(monkeypatch):
    monkeypatch.setenv("TRUST_FORWARDED_FOR", "true")
    get_settings.cache_clear()
    req = _FakeRequest({"x-forwarded-for": " 1.2.3.4 , 5.6.7.8"})
    assert ratelimit.peer_ip(req) == "1.2.3.4"
