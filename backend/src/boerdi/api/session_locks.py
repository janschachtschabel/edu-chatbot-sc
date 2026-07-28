"""Per-session request locks (port of the lock half of ALT ``chat_session_utils``).

``_get_session_lock`` / ``_release_session_lock`` serialise concurrent requests
from the same ``session_id`` behind a lazily-created ``asyncio.Lock`` so two turns
never read/write the same ``session_state`` in parallel; different sessions still
run fully in parallel. The chat endpoints (``POST /api/chat`` and its ``/stream``
sibling) wrap each turn in ``async with lock`` and release afterwards.

The refcount (not ``lock.locked()``) is the point: it closes a TOCTOU race between
a concurrent ``_get_session_lock`` — which already holds the lock object but has
not yet awaited ``async with`` — and the cleanup pop. Get bumps the count, release
decrements it, and the entry is dropped only at zero, so the registry stays bounded
under load without ever evicting a lock still in use.

**One registry, one home.** The state (``_session_locks`` / ``_session_locks_guard``)
lives ONLY here; the endpoint module imports the two functions. A second copy would
be two lock registries and therefore a race bug. Lives in ``api/`` — pure request
concurrency for the endpoint layer, its sole consumer (like ``api/deps`` /
``api/ratelimit``), and nothing inward depends on it.

**Verbatim port:** ``_get_session_lock`` / ``_release_session_lock`` use only
module-level bare names, so their AST is byte-identical to ALT with zero body edits
and no import swaps (pure stdlib ``asyncio``). The ALT siblings live elsewhere:
``_retrieve_task_exception`` in ``obs/tasks``; ``_peer_ip`` in ``api/ratelimit``;
``_spawn_background``/``_BG_TASKS`` deferred with their consumer (the quality-log
spawner, 3-5); ``save_message`` is DB-gated (a later slice).
"""

from __future__ import annotations

import asyncio

# ── Per-session locks (race-condition guard) ────────────────────
# Prevents two concurrent requests from the same session_id from clobbering
# each other's session_state. Locks are created lazily and cleaned up
# opportunistically when no waiters remain.
_session_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_session_locks_guard = asyncio.Lock()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Return (or lazily create) the per-session lock and bump its refcount.

    The refcount tracks how many concurrent requests are holding *or
    waiting on* this lock. ``_release_session_lock`` decrements it under
    the same guard and pops the entry once the count reaches zero, so
    the registry stays bounded under load and we never race with a
    parallel ``_get_session_lock`` that's already pulled the same lock
    object out of the dict.
    """
    async with _session_locks_guard:
        entry = _session_locks.get(session_id)
        if entry is None:
            lock = asyncio.Lock()
            _session_locks[session_id] = (lock, 1)
            return lock
        lock, count = entry
        _session_locks[session_id] = (lock, count + 1)
        return lock


async def _release_session_lock(session_id: str) -> None:
    """Decrement the lock's refcount; drop it from the registry at zero.

    Must be called *after* ``async with lock:`` has exited — calling it
    inside the ``async with`` block while ``lock.locked()`` is still
    True would simply skip the cleanup. Using a refcount instead of
    ``not lock.locked()`` avoids the TOCTOU race between a concurrent
    ``_get_session_lock`` (which has the lock object in hand but hasn't
    yet awaited ``async with``) and our pop.
    """
    async with _session_locks_guard:
        entry = _session_locks.get(session_id)
        if entry is None:
            return
        lock, count = entry
        new_count = count - 1
        if new_count <= 0:
            _session_locks.pop(session_id, None)
        else:
            _session_locks[session_id] = (lock, new_count)
