"""In-Prozess-Cross-Encoder — RAG-Rerank und Karten-Gate (W7, 2026-08-09).

**Warum es diesen Baustein wieder gibt.** Der V13-Entscheid (2026-07-12) hat den
TEI-Sidecar aus Kostengründen verworfen; gebaut wurde danach kein Ersatz, und
``_get_reranker`` gab dauerhaft ``None`` zurück. Die Begründung im damaligen
Kommentar verglich mit der falschen Alternative: ein *Bi-Encoder*-Rerank mit
demselben Embedder reproduziert die pgvector-Reihenfolge — richtig, und genau
deshalb sinnlos. ALT benutzte aber einen **Cross-Encoder**, der Frage und
Textstück GEMEINSAM durch ein Netz schickt und die Embedding-Reihenfolge von
der Bauart her nicht reproduzieren kann. ALTs eigene Messung liegt im Repo
(``badboerdi/backend/scripts/eval_reranker_result.json``): 10 Anfragen, **8
Rerank-Siege, 0 Baseline-Siege**, 2 Unentschieden, zwei Judges je Anfrage.

**Zwei Verbraucher, ein Modell** — das war schon in ALT so und ist der Grund,
warum dieser Baustein doppelt zählt:

1. ``rerank_results`` — die RAG-Chunks nach der pgvector-Suche.
2. ``services/card_reranker.rerank_gate_envelope`` — die WLO-Karten, mit einem
   ABSOLUTEN Schwellwert. Ohne Cross-Encoder fällt nicht nur die Sortierung
   weg, sondern das Wegwerfen thematisch verfehlter Treffer.

**Der Unterschied zu ALT: kein ``transformers``.** ALT lud den Tokenizer über
``transformers.AutoTokenizer`` und schleppte damit ein sehr grosses Paket mit.
Gemessen: die ``tokenizer.json`` des Exports reicht ``tokenizers`` allein, und
das Modell (XLM-R) kennt gar keine ``token_type_ids``. Laufzeit-Abhängigkeiten
sind damit ``onnxruntime`` (MIT), ``tokenizers`` (Apache-2.0) und ``numpy`` —
kein Torch.

**Das CPU-Budget ist der eigentlich heikle Teil.** ALTs Lasttest lt-e91ef209c1d6
zeigte: mit ORT-Vorgabe (jede Inferenz greift alle Kerne) brach der Durchsatz
bei 32 gleichzeitigen Suchzügen zusammen — CPU-Spitze 13 von 16 Kernen, Tail
85 s. Zwei Knöpfe spannen dasselbe Budget aus zwei Richtungen auf:

    Worker (RERANK_MAX_CONCURRENCY) × Threads je Inferenz (RERANK_INTRA_OP_THREADS)
    = beanspruchte Kerne.

Vorgabe: halbe System-CPU, verteilt auf Worker à einem Thread. Auf dieser
Maschine gemessen (25 Paare, Chunks à ~900 Zeichen):

    intra_op   1      2      3      4      6
    ms      3079   2138   1795   1489   1274

Ein Kartentext (~180 Zeichen) kostet nur ein Sechstel davon (507 ms bei
intra_op=1). Wer wenige Nutzer und kurze Antwortzeiten will, nimmt darum eher
``1 Worker × 3 Threads`` als ``3 Worker × 1 Thread`` — gleiches Budget, andere
Verteilung. Die Startzeile im Log nennt beide Zahlen und ihr Produkt.

Fehlt das Modell-Asset, loggt der Baustein eine WARNING und rankt embedding-only
weiter (ALT-Vertrag): ein Deploy ohne Asset antwortet, nur schlechter sortiert.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: ALT-Vorgabe. Seit W9 nur noch der Default von ``rerank_candidates`` — die
#: wirksame Zahl kommt aus der Config, weil sie die Latenz DOMINIERT (gemessen
#: bei 3 Threads: 25 Kandidaten = 1853 ms, 10 = 703 ms).
_RERANK_CANDIDATES = 25


def rerank_candidates() -> int:
    """Wie viele Chunks aus der Embedding-Suche in den Cross-Encoder gehen.

    **Achtung, Wechselwirkung:** der Aufrufer nimmt ``max(dieser Wert, top_k)``.
    Wer hier 10 setzt, aber ``RAG_TOP_K`` auf 15 stehen lässt, bekommt 15 —
    die Zahl wirkt dann nur halb. Steht auch im Feld-Text der Settings.
    """
    return max(1, get_settings().rerank_candidates)

#: Verzeichnisname des Exports. Regenerieren: ALTs ``scripts/export_reranker_onnx.py``.
_RERANK_MODEL_SLUG = "cross-encoder__mmarco-mMiniLMv2-L12-H384-v1-int8"

#: Reihenfolge der Dateinamen, die ein Export tragen kann (ALT-verbatim).
_ONNX_CANDIDATES = ("model_quantized.onnx", "model_int8.onnx", "model.onnx")

#: ALT-Deckel je Paar. 512 Tokens ≈ 1800 Zeichen — längere Chunks werden
#: abgeschnitten, nicht abgelehnt.
_MAX_TOKENS = 512


def _reranker_enabled_via_env() -> bool:
    """Return False wenn ``RAG_RERANKER_ENABLED`` per ENV explizit
    abgeschaltet wurde. Akzeptierte „false"-Werte: ``false``, ``0``,
    ``no``, ``off`` (case-insensitive, mit whitespace-Stripping).
    Alles andere (auch fehlende Variable) → True = Reranker aktiv.

    Use-Case: kleine RAM-Deployments (≤ 2 GB), in denen der ONNX-
    Reranker (~150-300 MB resident) zu OOM-Crashes führt. Embedding-
    only-Ranking ist die Fallback-Strategie — RAG-Antworten sind
    weiterhin nutzbar, nur die Top-1-Sortierung wird etwas weniger
    präzise als mit Cross-Encoder-Reranking.
    """
    raw = (os.getenv("RAG_RERANKER_ENABLED") or "").strip().lower()
    if not raw:
        # W10: war ALT-verbatim ``return True``. Dadurch lief die Vorgabe an den
        # Settings VORBEI — zwei Leser derselben Variablen, und der hier gewann.
        # Der Live-Start bewies es: „Reranker geladen" trotz Vorgabe False.
        # Bei gesetzter Variable bleibt ALTs Wertetabelle unveraendert.
        return get_settings().rag_reranker_enabled
    return raw not in ("false", "0", "no", "off")


def _rerank_intra_op_threads() -> int:
    """Kerne PRO Inferenz.

    **Vorgabe seit W11: das halbe System, gedeckelt auf 3.** Der Nutzer-Entscheid
    lautet „1 Worker x 3 Threads" fuer seinen 6-Kern-Server — als HARTE 3 waere
    das auf einem 2-Kern-Server Ueberbuchung, also genau der Fehler, den ALTs
    Lasttest teuer gelernt hat. Abgeleitet ergibt es auf 6 Kernen exakt 3 und
    bleibt ueberall sonst innerhalb der Haelfte. Wer einen festen Wert will,
    setzt ``RERANK_INTRA_OP_THREADS``.

    Der Deckel bei 3 ist gemessen: darueber wird es kaum noch schneller
    (25 Chunks: 1853 ms bei 3, 1628 ms bei 4).
    """
    gesetzt = get_settings().rerank_intra_op_threads
    if gesetzt:
        return max(1, gesetzt)
    return max(1, min(3, (os.cpu_count() or 2) // 2))


def _rerank_max_concurrency() -> int:
    """Gleichzeitige Inferenzen. **Vorgabe seit W11: 1 — Latenz vor Durchsatz.**

    Das Budget (halbe CPU) steckt jetzt in den Threads JE Inferenz, nicht in der
    Zahl gleichzeitiger Inferenzen. Gemessen ist das bei wenigen Nutzern die
    bessere Haelfte desselben Kuchens: eine RAG-Anfrage kostet 703 ms statt
    1471 ms. Steigt die Gleichzeitigkeit, dreht man es um.
    """
    gesetzt = get_settings().rerank_max_concurrency
    if gesetzt:
        return max(1, gesetzt)
    return 1


def _reranker_model_dir() -> str | None:
    """Pfad des Exports, oder None wenn er fehlt.

    ``RERANK_MODEL_DIR`` zeigt auf das ELTERN-Verzeichnis; darunter liegt der
    Slug. Ein direkt übergebenes Modellverzeichnis wird ebenfalls akzeptiert —
    im Container ist der Mount-Punkt oft schon das Modell selbst.
    """
    basis = Path(get_settings().rerank_model_dir)
    if not basis.is_absolute():
        # Relativ zu `backend/` auflösen, nicht zum Arbeitsverzeichnis: der
        # Prozess wird aus verschiedenen Verzeichnissen gestartet (uvicorn,
        # pytest, CLI), das Paket liegt immer gleich.
        basis = Path(__file__).resolve().parents[3].parent / basis
    for kandidat in (basis / _RERANK_MODEL_SLUG, basis):
        if kandidat.is_dir() and any(kandidat.glob("*.onnx")):
            return str(kandidat)
    return None


def reranker_status() -> str:
    """Was der Reranker im Betrieb WIRKLICH tut — für ``/api/health``.

    Drei Zustände, weil „eingeschaltet" und „einsatzbereit" verschiedene Dinge
    sind:

    * ``off`` — per ``RAG_RERANKER_ENABLED`` abgeschaltet (gewollt, z.B. auf
      kleinen Maschinen; RAG antwortet weiter, nur embedding-sortiert).
    * ``model-missing`` — eingeschaltet, aber unter ``RERANK_MODEL_DIR`` liegt
      kein Export. **Der stille Fall**: bisher merkte man ihn nur an einer
      Protokollzeile beim ersten Zug, und die Antworten waren unauffällig
      schlechter statt sichtbar kaputt.
    * ``ready`` — eingeschaltet und das Modell ist auffindbar.

    ``ready`` sagt bewusst nicht „geladen": das Modell wird erst beim ersten
    Zug in den Speicher geholt. Alles andere wäre eine Zusage, die dieser
    Aufruf nicht einlösen kann.
    """
    if not _reranker_enabled_via_env():
        return "off"
    return "ready" if _reranker_model_dir() else "model-missing"


class _OnnxReranker:
    """Cross-Encoder auf onnxruntime. Keine Torch-, keine Transformers-Abhängigkeit."""

    def __init__(self, model_dir: str) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = Path(model_dir)
        onnx_datei = next((d / n for n in _ONNX_CANDIDATES if (d / n).exists()), None)
        if onnx_datei is None:
            gefunden = sorted(d.glob("*.onnx"))
            if not gefunden:
                raise FileNotFoundError(f"keine .onnx-Datei in {model_dir}")
            onnx_datei = gefunden[0]

        self._tokenizer = Tokenizer.from_file(str(d / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=_MAX_TOKENS)
        self._tokenizer.enable_padding()

        opts = ort.SessionOptions()
        # ORT_ENABLE_ALL verschmilzt Operationen und ordnet Knoten um — auf der
        # CPU der grösste Einzelgewinn.
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = _rerank_intra_op_threads()
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            str(onnx_datei), sess_options=opts, providers=["CPUExecutionProvider"],
        )
        self._eingaben = {i.name for i in self._session.get_inputs()}

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Rohe Logits je (Frage, Textstück). Grösser = passender.

        Die Werte sind NICHT normiert — das ist Absicht: der Karten-Pfad gatet
        auf einen absoluten Schwellwert, und eine Normierung je Aufruf würde
        genau die Vergleichbarkeit zerstören, auf der er beruht.
        """
        import numpy as np

        if not pairs:
            return []
        encs = self._tokenizer.encode_batch([(f, t) for f, t in pairs])
        feed: dict[str, Any] = {
            "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
        }
        if "token_type_ids" in self._eingaben:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        logits = self._session.run(None, feed)[0]
        if logits.ndim == 2 and logits.shape[-1] == 1:
            logits = logits.squeeze(-1)
        return logits.tolist()


@lru_cache(maxsize=1)
def _get_reranker() -> _OnnxReranker | None:
    """Das geladene Backend, oder None = embedding-only.

    Prozess-Cache statt Modul-Global: ``cache_clear()`` ist der einzige Weg,
    es zurückzusetzen, und Tests haben ihn. Ein Ladefehler wird EINMAL geloggt
    und dann als None gemerkt — ohne den Cache probierte jeder Zug es erneut.
    """
    if not _reranker_enabled_via_env():
        logger.info("Reranker per RAG_RERANKER_ENABLED abgeschaltet — embedding-only")
        return None
    model_dir = _reranker_model_dir()
    if model_dir is None:
        logger.warning(
            "Reranker-Modell nicht gefunden (RERANK_MODEL_DIR=%r, erwartet %s/) — "
            "embedding-only. Das Ranking bleibt nutzbar, ist aber schlechter.",
            get_settings().rerank_model_dir, _RERANK_MODEL_SLUG,
        )
        return None
    try:
        rr = _OnnxReranker(model_dir)
    except Exception as err:  # noqa: BLE001 — Beschleunigung, kein Pflichtpfad
        logger.warning("Reranker konnte nicht laden (%s) — embedding-only", err)
        return None
    logger.info(
        "Reranker geladen: %s · %d Worker × %d Thread(e) = %d von %d Kernen",
        Path(model_dir).name, _rerank_max_concurrency(), _rerank_intra_op_threads(),
        _rerank_max_concurrency() * _rerank_intra_op_threads(), os.cpu_count() or 0,
    )
    return rr


@lru_cache(maxsize=1)
def _get_rerank_executor() -> ThreadPoolExecutor:
    """Gedeckelter Threadpool NUR für ONNX-Inferenz — geteilt von RAG-Rerank
    und Karten-Gate, damit die SUMME gleichzeitiger Inferenzen begrenzt bleibt.
    Zwei getrennte Pools würden das Budget still verdoppeln."""
    n = _rerank_max_concurrency()
    logger.info("Rerank-Threadpool: max_workers=%d", n)
    return ThreadPoolExecutor(max_workers=n, thread_name_prefix="rerank")


async def run_in_rerank_pool(fn, *args):
    """Eine synchrone Inferenz-Funktion im gedeckelten Pool ausführen.

    Pflicht für jeden Aufruf aus dem Event-Loop: eine Inferenz kostet je nach
    Textlänge 0,2–3 s CPU. Direkt im Loop aufgerufen steht in dieser Zeit der
    ganze Worker — auch die SSE-Ströme anderer Nutzer.

    Funktionen mit Keyword-Argumenten bitte als ``functools.partial`` übergeben;
    der Executor reicht nur positionale Argumente durch.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_get_rerank_executor(), fn, *args)


def warm_reranker() -> None:
    """Modell laden und einmal durchrechnen (Start-Vorwärmung).

    Der erste Aufruf zahlt Sitzungsaufbau und Speicherzuteilung. In ALT hing
    das an ``main.py``; hier ruft es ``services/warmup``.
    """
    rr = _get_reranker()
    if rr is not None:
        rr.predict([("Aufwärmen", "Ein kurzer Satz, damit die Sitzung warm ist.")])


def rerank_results(query: str, results: list[dict], top_n: int) -> list[dict]:
    """Rerank retrieval results with a cross-encoder. Falls back to
    embedding-score sort if the reranker is unavailable.
    """
    if not results or top_n <= 0:
        return results[:top_n] if results else []
    # W9: eigener Schalter fuer DIESEN Pfad. Er kostet das Achtfache des
    # Karten-Gates (gemessen bei 3 Threads, je 25 Elemente: 1853 ms gegen
    # 227 ms), und beide sollen unabhaengig voneinander entscheidbar sein —
    # sonst zahlt man das Karten-Gate mit, um den RAG-Rerank loszuwerden.
    rr = _get_reranker() if get_settings().rag_chunk_reranker_enabled else None
    if rr is None:
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return results[:top_n]
    pairs = [(query, r.get("chunk") or "") for r in results]
    try:
        scores = rr.predict(pairs)
    except Exception as e:
        logger.warning("Reranker predict failed: %s", e)
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return results[:top_n]
    for r, s in zip(results, scores):  # noqa: B905 (verbatim ALT)
        r["rerank_score"] = float(s)
    results.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return results[:top_n]
