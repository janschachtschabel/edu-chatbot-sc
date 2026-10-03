"""W8 — die Wahl des Embedding-Backends und die Fallen dabei.

Der Betrieb bleibt auf dem Anbieter (Nutzer-Entscheid 2026-08-09). Getestet wird
deshalb vor allem, dass die Vorgabe unverändert bleibt und dass die lokale
Option nicht STILL etwas Falsches tut — bei Embeddings ist genau das die
Gefahr: ein falsches Präfix oder ein anderer Vektorraum sieht aus wie Erfolg
und liefert schlechtere Treffer, ohne dass etwas rot wird.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.rag import embed as eb
from boerdi.services.rag import embed_local as el
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _frisch():
    get_settings.cache_clear()
    # `getattr`: ein Test ersetzt `get_local_embedder` durch eine Attrappe.
    getattr(el.get_local_embedder, "cache_clear", lambda: None)()
    yield
    get_settings.cache_clear()
    # `getattr`: ein Test ersetzt `get_local_embedder` durch eine Attrappe.
    getattr(el.get_local_embedder, "cache_clear", lambda: None)()


# ── Die Vorgabe: nichts ändert sich ohne ausdrückliche Umstellung ────────
def test_default_backend_is_the_provider(monkeypatch):
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    assert eb.embed_backend() == "api"


def test_default_path_calls_the_api_transport(monkeypatch):
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    gesehen: list[str] = []

    async def fake(text, *, kanal="live"):
        gesehen.append(text)
        return [0.1, 0.2]

    monkeypatch.setattr(eb, "_api_embedding", fake)
    assert asyncio.run(eb.embed_text("Bruchrechnung", kind="passage")) == [0.1, 0.2]
    assert gesehen == ["Bruchrechnung"]


# ── Eigener Kanal für den Import (Paket 4, C4; externes Audit F16) ───────


def _gleichzeitigkeit_messen(monkeypatch):
    """``llm._aembedding`` als Attrappe, die mitzählt, was gleichzeitig läuft
    und wie viele Live-Plätze dabei frei sind."""
    from types import SimpleNamespace

    from boerdi.services import llm

    llm.reset()
    stand = {"jetzt": 0, "max": 0, "live_frei": []}

    async def fake_aembedding(**_kwargs):
        stand["jetzt"] += 1
        stand["max"] = max(stand["max"], stand["jetzt"])
        stand["live_frei"].append(llm._semaphore("live")._value)
        await asyncio.sleep(0.01)
        stand["jetzt"] -= 1
        return SimpleNamespace(data=[{"embedding": [0.1]}])

    monkeypatch.setattr(llm, "_aembedding", fake_aembedding)
    monkeypatch.setattr(llm, "route", lambda _m: ("openai/x", "http://x", "k", None))
    return stand


def test_ein_import_belegt_keine_live_plaetze(monkeypatch):
    """Der Import legte je Aufruf einen eigenen Semaphor an, nahm aber in
    ``llm.embedding`` zusätzlich einen Live-Platz. Fünf Importe belegten so alle
    Plätze des Chats (Probe). Jetzt läuft er in einem eigenen, prozessweiten
    Kanal der Größe ``EMBED_INGEST_PARALLEL``."""
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    monkeypatch.setenv("EMBED_INGEST_PARALLEL", "2")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "4")
    stand = _gleichzeitigkeit_messen(monkeypatch)

    async def zwei_importe():
        return await asyncio.gather(eb.embed_many(["a"] * 6), eb.embed_many(["b"] * 6))

    erster, zweiter = asyncio.run(zwei_importe())
    assert erster == zweiter == [[0.1]] * 6
    assert stand["max"] <= 2                  # prozessweit, über beide Importe
    assert min(stand["live_frei"]) == 4       # kein Live-Platz belegt


def test_der_lokale_import_stellt_den_rerank_pool_nicht_voll(monkeypatch):
    """Prüfer 2026-10-04: Beim lokalen Backend ging jeder Abschnitt eines
    Imports sofort in den Rerank-Pool (FIFO, Vorgabe ein Arbeiter) — vor jede
    Suche eines echten Zugs. Jetzt gilt auch dort der Ingest-Deckel."""
    from boerdi.services import llm
    from boerdi.services.rag import rerank

    monkeypatch.setenv("EMBED_BACKEND", "local")
    monkeypatch.setenv("EMBED_INGEST_PARALLEL", "2")
    llm.reset()
    stand = {"jetzt": 0, "max": 0}

    async def fake_pool(_fn, *_args):
        stand["jetzt"] += 1
        stand["max"] = max(stand["max"], stand["jetzt"])
        await asyncio.sleep(0.01)
        stand["jetzt"] -= 1
        return [0.1]

    monkeypatch.setattr(rerank, "run_in_rerank_pool", fake_pool)
    assert asyncio.run(eb.embed_many(["a"] * 8)) == [[0.1]] * 8
    assert stand["max"] <= 2


def test_die_suchanfrage_bleibt_im_live_kanal(monkeypatch):
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "4")
    stand = _gleichzeitigkeit_messen(monkeypatch)

    asyncio.run(eb.embed_text("Wie suche ich?", kind="query"))
    assert stand["live_frei"] == [3]           # genau ein Live-Platz belegt


def test_unknown_backend_is_an_error_not_a_silent_fallback(monkeypatch):
    # Ein Tippfehler in der Env darf nicht dazu führen, dass Vektoren aus einem
    # anderen Raum in dieselbe pgvector-Spalte wandern.
    monkeypatch.setenv("EMBED_BACKEND", "lokal")
    with pytest.raises(ValueError, match="EMBED_BACKEND"):
        eb.embed_backend()


# ── Die Dimension ist die harte Grenze ───────────────────────────────────
def test_expected_dim_follows_the_backend(monkeypatch):
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    monkeypatch.setenv("LLM_EMBED_MODEL", "text-embedding-3-small")
    assert eb.expected_dim() == 1536

    monkeypatch.setenv("EMBED_BACKEND", "local")
    monkeypatch.setenv("EMBED_LOCAL_MODEL", "multilingual-e5-small")
    get_settings.cache_clear()
    assert eb.expected_dim() == 384


def test_all_local_candidates_share_one_dimension():
    # Sie sollen ohne Schema-Änderung gegeneinander austauschbar sein. Käme ein
    # 768er dazu, wäre das eine Migration — dieser Test macht es sichtbar.
    assert {m.dim for m in el.LOCAL_MODELS.values()} == {384}


def test_unknown_local_model_is_an_error(monkeypatch):
    monkeypatch.setenv("EMBED_LOCAL_MODEL", "gibt-es-nicht")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="EMBED_LOCAL_MODEL"):
        el._model_spec()


# ── Präfixe: der Unterschied, den man nicht raten darf ───────────────────
def test_e5_gets_its_prefixes_and_the_others_do_not(monkeypatch):
    """e5 ist auf ``query:``/``passage:`` trainiert, MiniLM und bekko nicht.

    Ohne Präfix sucht e5 messbar schlechter — und zwar lautlos. Deshalb steht
    die Eigenschaft in der Tabelle und nicht im Kopf des Betreibers.
    """
    e5 = el.LOCAL_MODELS["multilingual-e5-small"]
    assert (e5.query_prefix, e5.passage_prefix) == ("query: ", "passage: ")
    for name in ("paraphrase-multilingual-MiniLM-L12-v2", "bekko-embedding-v1-a8m"):
        m = el.LOCAL_MODELS[name]
        assert (m.query_prefix, m.passage_prefix) == ("", "")


def test_kind_picks_the_prefix(monkeypatch):
    monkeypatch.setenv("EMBED_LOCAL_MODEL", "multilingual-e5-small")
    get_settings.cache_clear()

    class _Attrappe:
        spec = el.LOCAL_MODELS["multilingual-e5-small"]

        def __init__(self):
            self.gesehen: list[str] = []

        def encode(self, texts):
            self.gesehen.extend(texts)
            return [[0.0] * 384 for _ in texts]

    attrappe = _Attrappe()
    monkeypatch.setattr(el, "get_local_embedder", lambda: attrappe)
    el.embed_local("Bruchrechnung", kind="query")
    el.embed_local("Brüche kürzt man …", kind="passage")
    assert attrappe.gesehen == ["query: Bruchrechnung", "passage: Brüche kürzt man …"]


def test_local_without_a_model_asset_raises_instead_of_returning_junk(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBED_LOCAL_MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert el.local_model_dir() is None
    with pytest.raises(RuntimeError, match="kein Modell"):
        el.embed_local("egal")
