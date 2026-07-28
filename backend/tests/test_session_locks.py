"""Behaviour pins for ``api/session_locks`` (port of the lock half of ALT
``chat_session_utils.py``): the per-session ``asyncio.Lock`` registry that
serialises concurrent turns from the same ``session_id``.

The contract worth pinning is the refcount lifecycle — bump on get, decrement on
release, pop at zero — because it is the documented TOCTOU fix: a plain
``not lock.locked()`` cleanup would race a concurrent ``_get_session_lock`` that
already holds the lock object but has not yet awaited ``async with``. The tests
also prove the returned lock genuinely provides mutual exclusion (timing-free:
``asyncio.sleep(0)`` is a scheduler yield, not a wall-clock wait).

The registry is module-global process state, so an autouse fixture clears it
around every test to keep them isolated and deterministic.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.api import session_locks as sl


@pytest.fixture(autouse=True)
def _clean_registry():
    sl._session_locks.clear()
    yield
    sl._session_locks.clear()


async def test_get_creates_lock_lazily_with_refcount_one():
    lock = await sl._get_session_lock("s1")
    assert isinstance(lock, asyncio.Lock)
    assert sl._session_locks["s1"] == (lock, 1)


async def test_get_same_session_returns_same_lock_and_bumps_refcount():
    first = await sl._get_session_lock("s1")
    second = await sl._get_session_lock("s1")
    assert first is second
    assert sl._session_locks["s1"] == (first, 2)


async def test_get_distinct_sessions_get_distinct_locks():
    a = await sl._get_session_lock("a")
    b = await sl._get_session_lock("b")
    assert a is not b
    assert set(sl._session_locks) == {"a", "b"}


async def test_release_decrements_refcount_and_keeps_entry():
    lock = await sl._get_session_lock("s1")
    await sl._get_session_lock("s1")  # refcount → 2
    await sl._release_session_lock("s1")
    assert sl._session_locks["s1"] == (lock, 1)


async def test_release_at_zero_pops_the_entry():
    await sl._get_session_lock("s1")  # refcount 1
    await sl._release_session_lock("s1")
    assert "s1" not in sl._session_locks


async def test_release_unknown_session_is_a_noop():
    # No entry for "ghost" — must not raise and must not create one.
    await sl._release_session_lock("ghost")
    assert "ghost" not in sl._session_locks
    assert sl._session_locks == {}


async def test_balanced_get_release_leaves_registry_empty():
    for _ in range(5):
        await sl._get_session_lock("s1")
        await sl._release_session_lock("s1")
    assert sl._session_locks == {}


async def test_returned_lock_blocks_a_second_acquire_while_held():
    # Timing-free proof of mutual exclusion: while the lock is held, a pending
    # acquire cannot complete; after release it does.
    lock = await sl._get_session_lock("s1")
    async with lock:
        assert lock.locked()
        pending = asyncio.ensure_future(lock.acquire())
        await asyncio.sleep(0)  # give the scheduler a turn
        assert not pending.done()  # still blocked — lock held
    await asyncio.wait_for(pending, timeout=1.0)
    assert pending.result() is True
    lock.release()


async def test_lock_serialises_critical_sections_without_interleaving():
    lock = await sl._get_session_lock("s1")
    order: list[str] = []

    async def worker(tag: str) -> None:
        async with lock:
            order.append(f"{tag}-enter")
            await asyncio.sleep(0)  # yield inside the critical section
            order.append(f"{tag}-exit")

    await asyncio.gather(worker("a"), worker("b"))
    # A working lock forbids interleaving regardless of scheduling order.
    assert order in (
        ["a-enter", "a-exit", "b-enter", "b-exit"],
        ["b-enter", "b-exit", "a-enter", "a-exit"],
    )


async def test_refcount_prevents_pop_while_a_second_holder_remains():
    # This is the documented race fix: get bumps the refcount so an early
    # release by one holder does not evict a lock a second holder still uses.
    lock1 = await sl._get_session_lock("s1")  # refcount 1
    lock2 = await sl._get_session_lock("s1")  # refcount 2, same object
    assert lock1 is lock2
    assert sl._session_locks["s1"][1] == 2

    await sl._release_session_lock("s1")  # first holder done → refcount 1
    assert sl._session_locks["s1"] == (lock1, 1)  # NOT popped

    await sl._release_session_lock("s1")  # second holder done → refcount 0
    assert "s1" not in sl._session_locks
