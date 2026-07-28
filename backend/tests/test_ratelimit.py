"""P1-4: HTTP-layer rate limit (slowapi, improvement V7 — default ON for
public endpoints) with ALT ``_peer_ip`` key semantics: X-Forwarded-For is
honoured ONLY when TRUST_FORWARDED_FOR is set (own reverse proxy), otherwise
the spoofable header is ignored.

The config-driven per-session sliding window (safety-config.yaml) is the P4
preflight port — this here is the outer HTTP guard.
"""

import pytest
from fastapi.testclient import TestClient

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
