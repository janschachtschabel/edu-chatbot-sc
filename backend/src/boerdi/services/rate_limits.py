"""Config-driven in-band throttle — the consumer of ``rate_limits`` (C6).

Port of ALT ``app/services/rate_limiter.py``. The safety-config block
(per-session/per-IP windows, IP whitelist, blocked text) is editable in the
studio; until C6 no line read it, so the editor's numbers did nothing and the
safety-log counter ``rate_limited`` could never move. This module is the
missing reader; ``graph/nodes/preflight`` is the caller (ALT's placement — the
guard runs before the direct-action dispatch, for every turn on both
``/api/chat`` and ``/api/chat/stream``).

**Two windows, two jobs.** ``api/ratelimit.py`` is the outer HTTP guard: one
per-IP limit, answered with 429, protecting the process. This one is the inner
courtesy brake the editorial team tunes: per session as well as per IP, and it
answers with a friendly bubble in the chat instead of an HTTP error.

**Not ALT's counter.** ALT kept a module-global ``dict`` of deques, which this
build forbids (rule 3) and which would be wrong anyway: with N replicas every
limit would effectively be N times as high. The counter here is the ``limits``
moving window — already a dependency via slowapi, same sliding-window
semantics as ALT's deque, and shared across replicas when
``RATE_LIMIT_STORAGE_URI`` points at Valkey. ALT's amortised ``_sweep_stale``
housekeeping therefore has no counterpart: expiry belongs to the store.

**Deliberately not ported:** ``reset_session()`` and the ``retry_after`` field.
Measured 2026-07-31 — neither has a caller anywhere in ALT (``retry_after`` is
computed into a dict nobody reads), and porting dead code is exactly the defect
C6 exists to fix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from limits import RateLimitItem, RateLimitItemPerHour, RateLimitItemPerMinute
from limits.aio.strategies import MovingWindowRateLimiter
from limits.storage import storage_from_string

from boerdi.i18n import DEFAULT, Locale, pick_localized
from boerdi.services.config_loader import load_safety_config
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

# ALT's wording, used when the editor leaves the field empty (the area model
# defaults it to "", which would render an empty bubble).
_DEFAULT_BLOCKED = "Zu viele Anfragen — bitte kurz warten."


@dataclass(frozen=True, slots=True)
class RateVerdict:
    """Outcome of one check. ``reason`` names the window that fired."""

    allowed: bool
    reason: str = ""
    blocked_message: str = ""


@lru_cache
def _limiter() -> MovingWindowRateLimiter:
    """The shared window store. ``async+`` selects the async storage backend for
    the URI slowapi already uses (``memory://`` per process, ``valkey://`` for
    the cluster); both implement ``MovingWindowSupport``."""
    uri = get_settings().rate_limit_storage_uri
    return MovingWindowRateLimiter(storage_from_string(f"async+{uri}"))


def _window(block: Any, key: str) -> int:
    """One ``requests_per_*`` number, defensively — config_store returns what is
    stored, and a wrong type must degrade to "no limit", not raise per turn."""
    try:
        return int((block or {}).get(key, 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _enabled(block: Any) -> bool:
    return bool((block or {}).get("enabled", True)) if isinstance(block, dict) else True


def _checks(cfg: dict, session_id: str, ip: str) -> list[tuple[str, RateLimitItem, str]]:
    """ALT's ``checks`` list: (label, limit item, bucket identifier), in order.

    Session windows first, then IP — so a session that blows its own limit is
    named as such even when the address is at its ceiling too.

    The limit VALUE is part of the item's storage key, so editing a window in
    the studio starts counting fresh instead of inheriting the old window — the
    behaviour an editor expects when they widen a limit to unblock someone.
    """
    per_session = cfg.get("per_session")
    per_ip = cfg.get("per_ip")
    whitelist = set(cfg.get("ip_whitelist") or [])
    out: list[tuple[str, int, str]] = []

    if _enabled(per_session):
        bucket = f"s:{session_id}"
        out.append(("session_minute", _window(per_session, "requests_per_minute"), bucket))
        out.append(("session_hour", _window(per_session, "requests_per_hour"), bucket))
    # ALT guards with ``if ip and …``: an empty peer IP must not create one
    # shared "" bucket that throttles every anonymous caller together.
    if ip and _enabled(per_ip) and ip not in whitelist:
        out.append(("ip_minute", _window(per_ip, "requests_per_minute"), f"i:{ip}"))
        out.append(("ip_hour", _window(per_ip, "requests_per_hour"), f"i:{ip}"))

    items: list[tuple[str, RateLimitItem, str]] = []
    for label, amount, bucket in out:
        if amount <= 0:
            continue  # ALT: ``max_requests <= 0`` means no limit
        factory = RateLimitItemPerHour if label.endswith("_hour") else RateLimitItemPerMinute
        items.append((label, factory(amount), bucket))
    return items


async def check_rate_limit(
    session_id: str, ip: str = "", lang: Locale = DEFAULT,
) -> RateVerdict:
    """Count this turn against the configured windows and decide.

    Every window the turn passes is counted before a later one can block it —
    ALT's behaviour, and the reason the labels are ordered session-before-IP.
    A storage outage fails OPEN: a courtesy brake whose counter is unreachable
    must not take the chat down, and the HTTP limiter remains the hard floor.

    ``lang`` picks the editor's text (C1-g2c). ``_DEFAULT_BLOCKED`` stays German
    on purpose: it only fires when the field is cleared, and a fallback is a
    safety net, not a second place to maintain wording.
    """
    raw = load_safety_config().get("rate_limits")
    cfg = raw if isinstance(raw, dict) else {}
    if not cfg.get("enabled", False):
        return RateVerdict(allowed=True)

    limiter = _limiter()
    for label, item, bucket in _checks(cfg, session_id, ip):
        try:
            passed = await limiter.hit(item, bucket)
        except Exception as err:
            logger.warning("rate-limit store unreachable, letting the turn through: %s", err)
            return RateVerdict(allowed=True)
        if not passed:
            return RateVerdict(
                allowed=False,
                reason=label,
                blocked_message=pick_localized(
                    str(cfg.get("blocked_message") or "").strip(),
                    str(cfg.get("blocked_message_en") or "").strip(),
                    lang,
                ) or _DEFAULT_BLOCKED,
            )
    return RateVerdict(allowed=True)
