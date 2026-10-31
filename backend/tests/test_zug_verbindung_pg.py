"""Ein Zug hält seine Datenbank-Verbindung nicht über LLM und MCP (Paket 19, Audit H-5).

Audit 2026-10-31: ``setup`` gab die Verbindung noch frei (``persist_user`` committet),
aber ``assess`` las über ``get_memory`` ohne Abschluss — die Verbindung stand „idle in
transaction“ bis ``persist``, über Klassifikation, Werkzeuge und Antwort hinweg. Bei
16+ gleichzeitigen Zügen je Kopie (Pool 5 + 10) wartete der nächste 30 s und bekam eine
Fehlerblase.

Bewiesen am Pool selbst (``checkedout()``) und an ``session.in_transaction()``, gegen das
echte Postgres: zwischen zwei Knoten, nach dem Gedächtnis-Lesen in ``assess``, vor der
Zustimmungs-Prüfung in ``setup``, nach den RAG-Abfragen (Muster- und Agent-Weg) und
während der Einbettung beim Import.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.graph.state import TurnContext
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p19_zug_verbindung"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _engine(url: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=url,
                                db_pool_size=2, db_max_overflow=0))


def _mit_sitzung(url: str, fn):
    from boerdi.db.session import make_session_factory

    async def ablauf():
        engine = _engine(url)
        try:
            async with make_session_factory(engine)() as session:
                return await fn(session, engine.sync_engine.pool)
        finally:
            await engine.dispose()

    return asyncio.run(ablauf())


def _req(sid: str) -> ChatRequest:
    return ChatRequest(session_id=sid, message="hallo", environment=Environment())


def test_freigeben_beendet_die_lese_transaktion(db_url):
    from boerdi.db.verbindung import verbindung_freigeben
    from boerdi.services.db_sessions import get_memory, get_or_create_session

    async def fn(session, pool):
        zeile = await get_or_create_session(session, "v-1")
        await get_memory(session, "v-1")
        vorher = (session.in_transaction(), pool.checkedout())
        await verbindung_freigeben(session)
        nachher = (session.in_transaction(), pool.checkedout())
        return vorher, nachher, zeile["session_id"]

    vorher, nachher, sid = _mit_sitzung(db_url, fn)
    assert vorher == (True, 1)
    assert nachher == (False, 0)
    assert sid == "v-1"


def test_ungespeicherte_aenderungen_beim_freigeben_werden_gemeldet(db_url, caplog):
    """Review 19-4: ein künftiger Schreibweg ohne eigenen Commit soll auffallen — die
    Freigabe schriebe ihn sonst still mit fest."""
    from boerdi.db.models import ChatSession
    from boerdi.db.verbindung import verbindung_freigeben
    from boerdi.services.db_sessions import get_memory

    async def fn(session, pool):
        await get_memory(session, "v-4")
        session.add(ChatSession(session_id="v-4-geheim"))
        await verbindung_freigeben(session)
        return session.in_transaction()

    with caplog.at_level("WARNING", logger="boerdi.db.verbindung"):
        assert _mit_sitzung(db_url, fn) is False
    meldungen = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(meldungen) == 1
    assert "v-4-geheim" not in meldungen[0]


def test_der_graph_gibt_die_verbindung_zwischen_den_knoten_frei(db_url, monkeypatch):
    from boerdi.graph import build as build_mod

    notiz: list[tuple[str, int]] = []

    def _spion(name, pool_ref):
        async def _knoten(ctx, session=None, peer_ip="", memory_fetch=None, on_token=None,
                          progress=None, engine="pattern"):
            notiz.append((f"{name}:anfang", pool_ref[0].checkedout()))
            if session is not None:
                await session.execute(text("SELECT 1"))  # ein Lesen wie in den Knoten
            if memory_fetch is not None:
                await memory_fetch(ctx.req.session_id)
                notiz.append((f"{name}:nach_gedaechtnis", pool_ref[0].checkedout()))
            return ctx

        return _knoten

    pool_ref: list = [None]
    for name in ("setup", "tour", "page_context_enrich", "context_greeting", "preflight",
                 "assess", "pruefung_fehlt", "merge", "route", "respond", "assemble",
                 "persist"):
        monkeypatch.setattr(build_mod, name, _spion(name, pool_ref))

    async def _still(*_a, **_k):
        return None

    monkeypatch.setattr(build_mod, "save_message", _still)
    monkeypatch.setattr(build_mod, "log_safety_event", _still)
    monkeypatch.setattr(build_mod, "load_safety_config",
                        lambda: {"logging": {"enabled": False}})

    async def fn(session, pool):
        pool_ref[0] = pool
        graph = build_mod.build_turn_graph(session=session)
        await graph.ainvoke(TurnContext(req=_req("v-2")))
        return pool.checkedout()

    am_ende = _mit_sitzung(db_url, fn)
    gehalten = [(schritt, n) for schritt, n in notiz if n]
    assert not gehalten, f"Verbindung über den Knoten hinaus gehalten: {gehalten}"
    assert ("assess:nach_gedaechtnis", 0) in notiz
    assert am_ende == 0


def test_setup_gibt_frei_bevor_die_zustimmung_geprueft_wird(db_url, monkeypatch):
    # ``discard_stale_approval`` fragt bei offenem Vorgang ein LLM (``zustimmung_pruefen``).
    from boerdi.graph.nodes import setup as setup_mod

    gesehen: list[tuple[bool, int]] = []

    async def fn(session, pool):
        async def _verwerfen(s, req, state, *, hintergrund=False):
            gesehen.append((s.in_transaction(), pool.checkedout()))
            return False

        monkeypatch.setattr(setup_mod, "discard_stale_approval", _verwerfen)
        await setup_mod.setup(TurnContext(req=_req("v-3")), session)

    _mit_sitzung(db_url, fn)
    assert gesehen == [(False, 0)]


def test_der_rag_kontext_gibt_nach_den_abfragen_frei(db_url, monkeypatch):
    # Muster-Weg (``tool_loop``/``tool_loop_messages``) und Agent-Weg (``agent_knowledge``)
    # lesen beide über ``get_rag_context`` — danach kommen Rerank und LLM.
    from boerdi.services.rag import retrieval

    async def _vektor(_text, kind="query"):
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(retrieval, "embed_text", _vektor)

    async def fn(session, pool):
        await retrieval.get_rag_context(session, "Frage", areas=["leer"])
        return session.in_transaction(), pool.checkedout()

    assert _mit_sitzung(db_url, fn) == (False, 0)


def test_der_import_bettet_ohne_offene_transaktion_ein(db_url, monkeypatch):
    # Bis zur Einbettung aller Abschnitte (Minuten bei großen Dokumenten) stand die
    # Verbindung „idle in transaction“ — mit ``DB_IDLE_IN_TRANSACTION_TIMEOUT_S`` beendet
    # der Server sie dann (M-10).
    from boerdi.services.rag import ingest

    gesehen: list[tuple[bool, int]] = []

    async def fn(session, pool):
        async def _einbetten(texte, kind="passage"):
            gesehen.append((session.in_transaction(), pool.checkedout()))
            return [None] * len(texte)

        monkeypatch.setattr(ingest, "embed_many", _einbetten)
        zahlen = await ingest.ingest_document(session, "p19", "Titel", "quelle", "# A\n\ntext")
        await ingest.embed_missing_chunks(session)
        return zahlen.chunks

    assert _mit_sitzung(db_url, fn) >= 1
    assert gesehen == [(False, 0), (False, 0)]
