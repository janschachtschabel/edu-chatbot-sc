"""Start-Vorwärmung (W1) — ALT ``main.py:173-178`` fuhr sechs Hintergrund-Warmups,
NEU hatte nur den Config-Preload.

Warum das zählt: der erste Zug einer frischen Instanz zahlt sonst die kalten
Kosten. Am 2026-07-27 live gemessen: erster Zug ``safety_classify`` bei 1,22 s,
zweiter bei 0,10 s. NEU skaliert horizontal (``compose.prod.yml``: backend ×N) —
jede Replica und jedes Rolling-Deploy zahlt diesen Aufschlag erneut.

**Der Kern dieser Datei ist der Verdrahtungs-Test.** ``prewarm_vocabularies``
existierte fertig und getestet, und ``mcp/tool_cache.py`` behauptete sogar, sie
laufe beim Start — nur rief sie niemand. Ein Test, der nur das Modul prüft, hätte
das nie gefunden. Deshalb wird hier der echte ``_lifespan`` gefahren.

Bewusst NICHT vorgewärmt: ALTs ``_embed_seed_chunks`` (Nutzer-Entscheid
2026-07-27) — bei N Replicas würden alle gleichzeitig dieselben Embeddings
berechnen und schreiben. Das bleibt beim Admin-Endpunkt ``/api/rag/embed``.
Ebenfalls entfallen: ``_warmup_reranker`` (V13: kein CPU-Reranker) und
``_warmup_tokenizer`` (keine tiktoken-Infra in NEU) — beides dokumentierte
``simplify:``-Entscheide, nicht Vergessenes.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import warmup as warmup_mod

# ── Die einzelnen Warmups ───────────────────────────────────────────────────

def test_vocabulary_warmup_delegates_to_the_existing_prewarm(monkeypatch):
    """``prewarm_vocabularies`` lädt die vier WLO-Vokabulare parallel — ohne sie
    kostet der erste Such-Zug mehrere MCP-Round-Trips."""
    called: list[bool] = []

    async def _fake():
        called.append(True)

    monkeypatch.setattr(warmup_mod, "prewarm_vocabularies", _fake)
    asyncio.run(warmup_mod.warm_vocabularies())
    assert called == [True]


def test_llm_warmup_pings_moderation(monkeypatch):
    """ALT-Port: ein Moderations-Ping ist bei OpenAI kostenlos und wärmt
    Verbindung + TLS-Handshake."""
    seen: list[str] = []

    async def _fake_moderate(message):
        seen.append(message)
        return {}

    monkeypatch.setattr(warmup_mod, "moderate", _fake_moderate)
    asyncio.run(warmup_mod.warm_llm_connection())
    assert seen == ["warmup"]


def test_llm_warmup_gives_up_instead_of_hanging(monkeypatch):
    """Ein hängender Anbieter darf keinen Task dauerhaft am Leben halten
    (ALT: ``asyncio.wait_for(..., timeout=10.0)``)."""
    monkeypatch.setattr(warmup_mod, "_WARMUP_TIMEOUT_SECONDS", 0.01)

    async def _hang(message):
        await asyncio.Event().wait()

    monkeypatch.setattr(warmup_mod, "moderate", _hang)
    asyncio.run(warmup_mod.warm_llm_connection())  # darf nicht werfen/hängen


def test_a_failing_warmup_is_swallowed(monkeypatch):
    """Vorwärmung ist reine Beschleunigung — ein kaltes MCP oder ein fehlender
    Schlüssel darf den Start nicht gefährden."""
    async def _boom():
        raise RuntimeError("MCP unreachable")

    monkeypatch.setattr(warmup_mod, "prewarm_vocabularies", _boom)
    asyncio.run(warmup_mod.warm_vocabularies())


# ── Der Spawner ─────────────────────────────────────────────────────────────

async def test_spawn_does_not_await_the_warmups():
    """Die Warmups laufen im Hintergrund: der Start darf nicht auf einen MCP-
    Round-Trip warten, sonst verzögert die Vorwärmung genau das, was sie
    beschleunigen soll."""
    started = asyncio.Event()

    async def _slow():
        started.set()
        await asyncio.sleep(5)

    warmup_mod.spawn_startup_warmups(tasks=[_slow()])
    await asyncio.wait_for(started.wait(), timeout=1.0)  # läuft, aber blockiert nicht


async def test_spawn_starts_every_task():
    ran: list[str] = []

    async def _one():
        ran.append("one")

    async def _two():
        ran.append("two")

    warmup_mod.spawn_startup_warmups(tasks=[_one(), _two()])
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert sorted(ran) == ["one", "two"]


# ── Die Verdrahtung (der eigentliche Punkt) ─────────────────────────────────

@pytest.fixture()
def fake_infra(monkeypatch):
    """Postgres/ConfigStore durch Attrappen ersetzen, damit ``_lifespan`` ohne DB
    läuft. Alles, was der Lifespan importiert, wird am Quell-Modul gepatcht."""
    from boerdi.db import notify as notify_mod
    from boerdi.db import session as session_mod
    from boerdi.services import config_loader, config_store
    from boerdi.services import loadtest as loadtest_mod

    class _Store:
        async def start(self): return None
        async def list_areas(self): return []
        async def preload(self, areas): return None
        async def stop(self): return None

    class _Engine:
        async def dispose(self): return None

    monkeypatch.setattr(session_mod, "make_engine", lambda s: _Engine())
    monkeypatch.setattr(session_mod, "make_session_factory", lambda e: None)
    monkeypatch.setattr(notify_mod, "asyncpg_dsn", lambda url: "postgresql://x/y")
    monkeypatch.setattr(config_store, "ConfigStore", lambda *a, **k: _Store())
    monkeypatch.setattr(config_loader, "bind_store", lambda s: None)

    async def _sweep(session): return 0
    monkeypatch.setattr(loadtest_mod, "sweep_orphaned_loadtests", _sweep)


async def test_lifespan_actually_spawns_the_warmups(monkeypatch, fake_infra):
    """Der Test, den es für ``prewarm_vocabularies`` nie gab: die Funktion war
    gebaut, getestet und im Kommentar als „beim Backend-Start vorgewärmt"
    beschrieben — gerufen hat sie niemand. Hier läuft der echte Lifespan."""
    import boerdi.main as main_mod

    spawned: list[bool] = []
    monkeypatch.setattr(main_mod, "spawn_startup_warmups", lambda: spawned.append(True))

    async with main_mod._lifespan(_FakeApp()):
        pass
    assert spawned == [True]


class _FakeApp:
    """Minimaler FastAPI-Ersatz: der Lifespan schreibt nur auf ``app.state``."""

    class _State:
        pass

    def __init__(self):
        self.state = _FakeApp._State()
