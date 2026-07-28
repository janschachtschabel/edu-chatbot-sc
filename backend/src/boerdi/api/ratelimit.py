"""HTTP-layer rate limiting (P1-4, improvement V7 — default ON).

slowapi limiter keyed by the ALT ``_peer_ip`` semantics (chat.py:120-133):
``X-Forwarded-For`` is honoured ONLY when TRUST_FORWARDED_FOR is set (own
reverse proxy) — otherwise the client-spoofable header is ignored.

Storage comes from RATE_LIMIT_STORAGE_URI: ``memory://`` per process,
``valkey://`` for the cluster (P10-6). **Valkey, not Redis**: Redis 8 is
RSALv2/SSPLv1/AGPLv3 — all three on the §0 rule-1 deny list — while Valkey is
BSD-3-Clause and speaks the same protocol. The scheme also picks the CLIENT:
``limits`` uses valkey-py for ``valkey://`` and redis-py for ``redis://``, and
only the former is a dependency here, so a leftover ``redis://`` URI fails
loudly at startup instead of silently counting per process. Off-switch:
RATE_LIMIT_CHAT=off|0|none|false|disabled (evaluated per request via
``exempt_when``).

**This is the only rate limit that exists in this build.** The safety-config
block ``rate_limits`` (per-session/per-IP windows) has no consumer — measured
2026-07-27: no ``RateLimitsBlock`` field is read outside the config model, and
nobody ever sets ``rate_limited=True`` on a safety event, so that counter can
never move. ALT's in-band guard was not ported. The block stays editable in the
studio, which is the honesty problem — tracked as C6.
"""

from slowapi import Limiter

from boerdi.settings import get_settings

_OFF_TOKENS = ("off", "0", "none", "false", "disabled")


def peer_ip(request) -> str:
    """Real connection IP for rate limit + logs (port of ALT ``_peer_ip``)."""
    if get_settings().trust_forwarded_for:
        xff = request.headers.get("x-forwarded-for", "")
        if xff.strip():
            return xff.split(",")[0].strip()
    try:
        return (request.client.host if request.client else "") or ""
    except Exception:
        return ""


def _chat_limit() -> str:
    return get_settings().rate_limit_chat


def _limit_disabled() -> bool:
    return get_settings().rate_limit_chat.strip().lower() in _OFF_TOKENS


# storage_uri is deployment-static (read once at import); the limit VALUE and
# the off-switch are evaluated per request, so env/settings changes in tests
# take effect without rebuilding the limiter.
limiter = Limiter(
    key_func=peer_ip,
    storage_uri=get_settings().rate_limit_storage_uri,
    headers_enabled=True,
)

# decorator for the public §5.1 endpoints (chat, stream, speech, history)
public_rate_limit = limiter.limit(_chat_limit, exempt_when=_limit_disabled)
