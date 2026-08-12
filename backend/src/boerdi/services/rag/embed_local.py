"""Lokales ONNX-Embedding — die Option ohne Anbieter (W8, 2026-08-09).

**Warum als Option und nicht als Umstellung.** Nutzer-Entscheid 2026-08-09: der
Betrieb bleibt auf den Anbieter-Embeddings (OpenAI/Mistral über die B-API), weil
der Chat zeitkritisch ist und ein API-Aufruf nebenläufig über viele Worker geht,
während lokale Inferenz das CPU-Budget des Servers teilt. Der lokale Weg soll
trotzdem im Code stehen — als Ausweichmöglichkeit, wenn ein Anbieter wegfällt,
und für Betriebe, die keine Dokumenttexte nach draussen geben wollen.

**Was dieser Baustein NICHT löst.** Vektoren zweier Modelle liegen in
verschiedenen Räumen, auch bei gleicher Dimension. Ein Wechsel des Backends
bedeutet: alles neu einbetten. Die Dimension der pgvector-Spalte ist die harte
Grenze — deshalb tragen alle drei Kandidaten hier **384** und deshalb prüft
``services/rag/embed`` sie beim Start.

**Warum drei Kandidaten und nicht einer.** Sie unterscheiden sich in genau der
Eigenschaft, die man nicht raten darf: e5 verlangt Präfixe (``query:`` /
``passage:``), die anderen nicht. Wer das übersieht, bekommt ein Modell, das
lädt, rechnet, plausible Zahlen liefert — und schlechter sucht, ohne dass etwas
rot wird. Genau dafür ist die Tabelle da.

Laufzeit: ``onnxruntime`` + ``tokenizers`` + ``numpy`` — dieselben drei wie beim
Cross-Encoder, kein Torch. Die Inferenz läuft im **selben** gedeckelten Pool wie
das Reranking (``rerank.run_in_rerank_pool``): das CPU-Budget des Servers ist
eines, nicht zwei.

**Das Modell-Asset wird NICHT mitgeliefert.** ``EMBED_LOCAL_MODEL_DIR`` zeigt
darauf; fehlt es, bleibt der lokale Weg aus und der Anbieter-Weg trägt weiter.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

from boerdi.settings import get_settings

logger = logging.getLogger(__name__)


class LocalEmbedModel(NamedTuple):
    """Was man über ein Embedding-Modell wissen MUSS, um es richtig zu füttern."""

    #: Verzeichnisname des Exports unter ``EMBED_LOCAL_MODEL_DIR``.
    slug: str
    #: Vektorlänge — muss zur pgvector-Spalte passen.
    dim: int
    #: Präfix für den Suchtext (leer = keins).
    query_prefix: str
    #: Präfix für den gespeicherten Textabschnitt (leer = keins).
    passage_prefix: str
    #: Kurzbegründung für die Auswahlliste.
    note: str


#: Die Kandidaten. Alle 384-dimensional und mehrsprachig — Voraussetzung, damit
#: sie ohne Schema-Änderung gegeneinander austauschbar sind.
LOCAL_MODELS: dict[str, LocalEmbedModel] = {
    "multilingual-e5-small": LocalEmbedModel(
        slug="multilingual-e5-small", dim=384,
        query_prefix="query: ", passage_prefix="passage: ",
        note="intfloat, 118M — verlangt Präfixe; ohne sie sucht es messbar schlechter",
    ),
    "paraphrase-multilingual-MiniLM-L12-v2": LocalEmbedModel(
        slug="paraphrase-multilingual-MiniLM-L12-v2", dim=384,
        query_prefix="", passage_prefix="",
        note="sentence-transformers, 118M — ohne Präfixe, sehr verbreitet",
    ),
    "bekko-embedding-v1-a8m": LocalEmbedModel(
        slug="bekko-embedding-v1-a8m", dim=384,
        query_prefix="", passage_prefix="",
        note="hotchpotch, 7,7M aktiv, 8192 Tokens, MIT — kleinstes Asset (~124 MiB)",
    ),
}

#: Deckel je Text. 512 Tokens ist die Grenze von e5/MiniLM; bekko könnte mehr,
#: aber ein gemeinsamer Deckel hält die Kandidaten vergleichbar.
_MAX_TOKENS = 512

_ONNX_CANDIDATES = ("model.onnx", "model_quantized.onnx", "model_int8.onnx")


def _model_spec() -> LocalEmbedModel:
    """Der konfigurierte Kandidat. Unbekannter Name ist ein harter Fehler —
    stiller Rückfall auf einen anderen Vektorraum wäre das Schlimmste."""
    name = (get_settings().embed_local_model or "").strip()
    if name not in LOCAL_MODELS:
        raise ValueError(
            f"EMBED_LOCAL_MODEL={name!r} unbekannt. Bekannt: {sorted(LOCAL_MODELS)}",
        )
    return LOCAL_MODELS[name]


def local_model_dir() -> str | None:
    """Pfad des Exports, oder None wenn er fehlt (dann bleibt der lokale Weg aus)."""
    basis = Path(get_settings().embed_local_model_dir)
    if not basis.is_absolute():
        basis = Path(__file__).resolve().parents[3].parent / basis
    for kandidat in (basis / _model_spec().slug, basis):
        if kandidat.is_dir() and any(kandidat.glob("*.onnx")):
            return str(kandidat)
    return None


class _LocalEmbedder:
    """Satz-Embedding auf onnxruntime: Mittelwert über die Token, dann L2.

    Mittelwert-Pooling und L2-Normierung sind das, was sentence-transformers für
    diese drei Modelle tut. Beides gehört zum Modell, nicht zum Geschmack: ohne
    die Normierung ist die Kosinus-Ähnlichkeit in pgvector nicht mehr das, was
    das Modell gelernt hat.
    """

    def __init__(self, model_dir: str, spec: LocalEmbedModel) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from boerdi.services.rag.rerank import _rerank_intra_op_threads

        d = Path(model_dir)
        onnx_datei = next((d / n for n in _ONNX_CANDIDATES if (d / n).exists()), None)
        if onnx_datei is None:
            gefunden = sorted(d.glob("*.onnx"))
            if not gefunden:
                raise FileNotFoundError(f"keine .onnx-Datei in {model_dir}")
            onnx_datei = gefunden[0]

        self.spec = spec
        self._tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=_MAX_TOKENS)
        self._tokenizer.enable_padding()

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Dasselbe CPU-Budget wie der Reranker — es ist EIN Server.
        opts.intra_op_num_threads = _rerank_intra_op_threads()
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            str(onnx_datei), sess_options=opts, providers=["CPUExecutionProvider"],
        )
        self._eingaben = {i.name for i in self._session.get_inputs()}

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Ein Vektor je Text, L2-normiert."""
        import numpy as np

        if not texts:
            return []
        encs = self._tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        maske = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feed: dict[str, Any] = {"input_ids": ids, "attention_mask": maske}
        if "token_type_ids" in self._eingaben:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)

        ausgabe = self._session.run(None, feed)[0]  # (batch, tokens, hidden)
        if ausgabe.ndim == 2:  # manche Exporte poolen schon selbst
            vektoren = ausgabe
        else:
            m = maske[..., None].astype(ausgabe.dtype)
            vektoren = (ausgabe * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        norm = np.linalg.norm(vektoren, axis=1, keepdims=True)
        return (vektoren / np.clip(norm, 1e-12, None)).astype(float).tolist()


@lru_cache(maxsize=1)
def get_local_embedder() -> _LocalEmbedder | None:
    """Der geladene lokale Embedder, oder None = nicht verfügbar."""
    model_dir = local_model_dir()
    if model_dir is None:
        logger.warning(
            "Lokales Embedding-Modell nicht gefunden (EMBED_LOCAL_MODEL_DIR=%r, "
            "erwartet %s/) — der Anbieter-Weg trägt weiter.",
            get_settings().embed_local_model_dir, _model_spec().slug,
        )
        return None
    try:
        emb = _LocalEmbedder(model_dir, _model_spec())
    except Exception as err:  # noqa: BLE001
        logger.warning("Lokales Embedding-Modell konnte nicht laden: %s", err)
        return None
    logger.info(
        "Lokales Embedding geladen: %s (%d Dimensionen)", emb.spec.slug, emb.spec.dim,
    )
    return emb


def embed_local(text: str, *, kind: str = "query") -> list[float]:
    """Ein Vektor für ``text``. ``kind`` entscheidet über das Präfix.

    ``kind`` ist kein Vorrat: e5 unterscheidet Frage und Textabschnitt
    ausdrücklich, und die Aufrufer wissen es ohnehin — die Suche fragt, der
    Ingest speichert.
    """
    emb = get_local_embedder()
    if emb is None:
        raise RuntimeError("lokales Embedding angefordert, aber kein Modell geladen")
    praefix = emb.spec.query_prefix if kind == "query" else emb.spec.passage_prefix
    return emb.encode([praefix + text])[0]
