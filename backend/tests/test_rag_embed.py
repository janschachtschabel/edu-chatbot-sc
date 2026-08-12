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

    async def fake(text):
        gesehen.append(text)
        return [0.1, 0.2]

    monkeypatch.setattr(eb, "_api_embedding", fake)
    assert asyncio.run(eb.embed_text("Bruchrechnung", kind="passage")) == [0.1, 0.2]
    assert gesehen == ["Bruchrechnung"]


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
