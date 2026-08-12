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
``exempt_when``; the token itself never reaches slowapi's parser — see
``_chat_limit``).

**This is the OUTER limit.** It protects the process: one per-IP window,
deployment-tuned via env, answered with HTTP 429 before the graph starts. The
inner, editorially-tuned brake is ``services/rate_limits`` — per-session
windows from the safety config, answered with a friendly bubble in the chat
(C6, built 2026-07-31; until then that config block had no reader at all).
Both count independently and are meant to: env is the operator's knob, the
safety config is the editorial team's.
"""

from slowapi import Limiter

from boerdi.settings import get_settings

_OFF_TOKENS = ("off", "0", "none", "false", "disabled")

# Stand-in fed to slowapi while the switch is off; see ``_chat_limit``.
_OFF_PLACEHOLDER = "1000000/second"


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


def _limit_disabled() -> bool:
    return get_settings().rate_limit_chat.strip().lower() in _OFF_TOKENS


def _chat_limit() -> str:
    """Limit string for slowapi — never one that ``limits.parse_many`` rejects.

    slowapi has no "no limit" limit string. Handing it an unparseable value
    (``off``) made the PER-REQUEST parse in ``Limiter._check_request_limit``
    throw, and slowapi logs that at ERROR once per request
    (extension.py:596) — a production log with the limit disabled was
    unusable. Worse, that parse is what builds the ``Limit`` objects carrying
    ``exempt_when``, so it died before the off-switch above was ever
    consulted: "off" worked by accident, as a side effect of the failure.

    So when the switch is off we return a parseable placeholder and let
    ``exempt_when=_limit_disabled`` do the disabling for real — slowapi skips
    the limit before ``hit()``, so no bucket is touched and (with
    ``view_rate_limit`` staying None) no X-RateLimit headers are emitted. The
    amount is absurdly high on purpose: should the exemption ever be dropped,
    the fallback is a practically unreachable limit, not a lockout.
    """
    if _limit_disabled():
        return _OFF_PLACEHOLDER
    return get_settings().rate_limit_chat


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
