"""services.rate_limits — the safety-config ``rate_limits`` block (C6).

The block (per-session/per-IP windows, whitelist, blocked text) was editable in
the studio from day one but read by no line; ALT's in-band throttle
(``app/services/rate_limiter.py``) was never ported. These tests pin the ported
semantics BEFORE the implementation exists:

* a disabled block never counts anything,
* ``requests_per_minute: 0`` means "no limit" (ALT ``max_requests <= 0``),
* a whitelisted IP is exempt from the IP window but not from the session one,
* the IP window is what catches a second session behind the same address,
* a blocked verdict names the window that fired and carries the editor's text,
* a storage outage does not block the chat (the HTTP limiter stays the floor).

The counter itself is the ``limits`` moving window (already a dependency via
slowapi) instead of ALT's module-global deque dict — same sliding semantics,
but shared across replicas and free of module-global mutable state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from boerdi.services import rate_limits as rl

SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def _cfg(**over) -> dict:
    """A rate_limits block in the seed's shape, overridable per test."""
    block = {
        "enabled": True,
        "per_session": {"enabled": True, "requests_per_minute": 3, "requests_per_hour": 0},
        "per_ip": {"enabled": True, "requests_per_minute": 0, "requests_per_hour": 0},
        "ip_whitelist": [],
        "blocked_message": "Bitte warte einen Moment.",
    }
    block.update(over)
    return {"rate_limits": block}


@pytest.fixture(autouse=True)
def _fresh_counter(monkeypatch):
    """Each test starts with an empty in-memory window store."""
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    from boerdi.settings import get_settings

    get_settings.cache_clear()
    rl._limiter.cache_clear()
    yield
    rl._limiter.cache_clear()
    get_settings.cache_clear()


def _patch_cfg(monkeypatch, cfg: dict) -> None:
    monkeypatch.setattr(rl, "load_safety_config", lambda: cfg)


async def test_disabled_block_counts_nothing(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(enabled=False))
    for _ in range(10):
        assert (await rl.check_rate_limit("s-1", "1.2.3.4")).allowed


async def test_session_window_blocks_after_the_configured_count(monkeypatch):
    _patch_cfg(monkeypatch, _cfg())
    for _ in range(3):
        assert (await rl.check_rate_limit("s-1")).allowed
    assert not (await rl.check_rate_limit("s-1")).allowed
    # a different session is untouched by the first one's window
    assert (await rl.check_rate_limit("s-2")).allowed


async def test_zero_means_unlimited(monkeypatch):
    # ALT ``_check_window``: ``max_requests <= 0`` short-circuits to allowed.
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 0, "requests_per_hour": 0},
    ))
    for _ in range(25):
        assert (await rl.check_rate_limit("s-1")).allowed


async def test_disabled_session_window_is_skipped(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": False, "requests_per_minute": 1, "requests_per_hour": 0},
    ))
    for _ in range(5):
        assert (await rl.check_rate_limit("s-1")).allowed


async def test_ip_window_catches_a_second_session_from_the_same_address(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": False, "requests_per_minute": 0, "requests_per_hour": 0},
        per_ip={"enabled": True, "requests_per_minute": 2, "requests_per_hour": 0},
    ))
    assert (await rl.check_rate_limit("s-1", "9.9.9.9")).allowed
    assert (await rl.check_rate_limit("s-2", "9.9.9.9")).allowed
    # third request from that address — different session, same window
    assert not (await rl.check_rate_limit("s-3", "9.9.9.9")).allowed


async def test_whitelisted_ip_is_exempt_from_the_ip_window(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": False, "requests_per_minute": 0, "requests_per_hour": 0},
        per_ip={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        ip_whitelist=["9.9.9.9"],
    ))
    for _ in range(5):
        assert (await rl.check_rate_limit("s-1", "9.9.9.9")).allowed
    # …but a non-whitelisted address still hits the same window
    assert (await rl.check_rate_limit("s-2", "8.8.8.8")).allowed
    assert not (await rl.check_rate_limit("s-2", "8.8.8.8")).allowed


async def test_missing_ip_skips_the_ip_window(monkeypatch):
    # ALT guards with ``if ip and …`` — an empty peer IP must not create a
    # shared "" bucket that throttles every anonymous caller together.
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": False, "requests_per_minute": 0, "requests_per_hour": 0},
        per_ip={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
    ))
    for _ in range(5):
        assert (await rl.check_rate_limit("s-1", "")).allowed


async def test_blocked_verdict_names_the_window_and_carries_the_editors_text(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        blocked_message="Zu schnell, kleiner Bördi.",
    ))
    assert (await rl.check_rate_limit("s-1")).allowed
    verdict = await rl.check_rate_limit("s-1")
    assert not verdict.allowed
    assert verdict.reason == "session_minute"
    assert verdict.blocked_message == "Zu schnell, kleiner Bördi."


async def test_hour_window_is_reported_separately(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 0, "requests_per_hour": 2},
    ))
    assert (await rl.check_rate_limit("s-1")).allowed
    assert (await rl.check_rate_limit("s-1")).allowed
    assert (await rl.check_rate_limit("s-1")).reason == "session_hour"


async def test_empty_blocked_message_falls_back_to_a_real_sentence(monkeypatch):
    # The area model defaults ``blocked_message`` to "" — an editor who clears
    # the field must not produce an empty chat bubble.
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        blocked_message="",
    ))
    await rl.check_rate_limit("s-1")
    assert (await rl.check_rate_limit("s-1")).blocked_message.strip()


async def test_storage_outage_does_not_block_the_chat(monkeypatch):
    # Fail OPEN: a courtesy throttle whose counter is unreachable must not take
    # the chat down — the slowapi HTTP limit is the hard floor either way.
    _patch_cfg(monkeypatch, _cfg())

    async def _boom(*_a, **_k):
        raise RuntimeError("valkey unreachable")

    monkeypatch.setattr(rl._limiter(), "hit", _boom)
    assert (await rl.check_rate_limit("s-1", "1.2.3.4")).allowed


def test_the_shipped_seed_really_drives_the_windows():
    """The other tests hand in a hand-written block. This one takes the ACTUAL
    seed through the ACTUAL area model — the shape the studio saves and
    ``load_safety_config`` returns — so the reader cannot silently disagree with
    the file it is supposed to read (the failure mode that made two green test
    suites miss live defects in P11)."""
    import yaml

    from boerdi.domain.config_models.base_governance import SafetyConfigArea
    from boerdi.services.seed_io import normalize_json_keys

    raw = yaml.safe_load(
        (SEEDS / "01-base" / "safety-config.yaml").read_text(encoding="utf-8")
    )
    # …through the import's own key normalisation, so this really is the shape
    # the store holds (YAML 1.1 turns the preset key ``off`` into False).
    stored = normalize_json_keys(raw)
    cfg = SafetyConfigArea.model_validate(stored).model_dump()["rate_limits"]

    assert cfg["enabled"] is True  # shipped ON — the brake is live after import
    labels = {label: item.amount for label, item, _ in rl._checks(cfg, "s-1", "1.2.3.4")}
    assert labels == {
        "session_minute": 30, "session_hour": 600,
        "ip_minute": 1200, "ip_hour": 30000,
    }
    assert cfg["blocked_message"].strip()  # a real sentence, not the fallback


async def test_malformed_block_does_not_raise(monkeypatch):
    # config_store hands back whatever is stored; a wrong type must degrade to
    # "no limit", not to a 500 on every turn.
    _patch_cfg(monkeypatch, {"rate_limits": None})
    assert (await rl.check_rate_limit("s-1", "1.2.3.4")).allowed


# ── C1-g2c: der Drosselungs-Text je Sprache ────────────────────────────────

async def test_blocked_message_englisch_wenn_gepflegt(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        blocked_message="Zu schnell, kleiner Bördi.",
        blocked_message_en="Slow down a moment.",
    ))
    await rl.check_rate_limit("s-en")
    assert (await rl.check_rate_limit("s-en", lang="en")).blocked_message == (
        "Slow down a moment.")


async def test_blocked_message_ohne_englisch_bleibt_deutsch(monkeypatch):
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        blocked_message="Zu schnell, kleiner Bördi.",
    ))
    await rl.check_rate_limit("s-de")
    assert (await rl.check_rate_limit("s-de", lang="en")).blocked_message == (
        "Zu schnell, kleiner Bördi.")


async def test_beide_leer_faellt_auf_den_deutschen_notsatz(monkeypatch):
    # Der eingebaute Rückfall bleibt einsprachig: er greift nur, wenn die
    # Redaktion das Feld leert — eine Notbremse, kein Pflegeort (wie `_RULES`
    # im Lotsen-Injektor, C1-g2a). Leer wäre schlimmer als deutsch.
    _patch_cfg(monkeypatch, _cfg(
        per_session={"enabled": True, "requests_per_minute": 1, "requests_per_hour": 0},
        blocked_message="",
    ))
    await rl.check_rate_limit("s-leer")
    assert (await rl.check_rate_limit("s-leer", lang="en")).blocked_message == (
        rl._DEFAULT_BLOCKED)


def test_der_ausgelieferte_seed_traegt_beide_sprachen():
    import yaml
    cfg = yaml.safe_load(
        (SEEDS / "01-base" / "safety-config.yaml").read_text(encoding="utf-8")
    )["rate_limits"]
    assert cfg["blocked_message"].strip()
    assert cfg["blocked_message_en"].strip()
