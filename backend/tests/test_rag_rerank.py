"""Behavior pins for services/rag/rerank — der ONNX-Cross-Encoder (W7).

**Der frühere Kopf dieser Datei hielt eine Entscheidung fest, die revidiert
ist.** Er argumentierte, ein *Bi-Encoder*-Rerank mit demselben Embedder
reproduziere die pgvector-Reihenfolge — das stimmt und schliesst genau diese
eine Alternative aus. ALT benutzte aber einen **Cross-Encoder**, der Frage und
Textstück gemeinsam bewertet und die Embedding-Reihenfolge von der Bauart her
nicht reproduziert. ALTs eigene Messung
(`badboerdi/backend/scripts/eval_reranker_result.json`): 10 Anfragen, **8
Rerank-Siege, 0 Baseline-Siege, 2 Unentschieden**, zwei Judges je Anfrage.

Deshalb ist ``test_seam_has_no_backend_today`` ersetzt: er pinnte die
ABWESENHEIT des Backends. Der Test war nicht falsch, er hielt eine
Produktentscheidung fest — und die ist auf Nutzer-Wunsch 2026-08-09 gekippt.

``_reranker_enabled_via_env`` und ``rerank_results`` bleiben ALT-verbatim.
"""

from __future__ import annotations

import pytest

import boerdi.services.rag.rerank as rk
from boerdi.services.rag.rerank import (
    _get_reranker,
    _rerank_intra_op_threads,
    _rerank_max_concurrency,
    _reranker_enabled_via_env,
    _reranker_model_dir,
    rerank_results,
)
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _frischer_reranker():
    """Der Reranker ist ein Prozess-Cache — sonst schleppt ein Test die
    geladene Sitzung des vorigen mit und die Env-Schalter wirken nicht."""
    _get_reranker.cache_clear()
    get_settings.cache_clear()
    yield
    _get_reranker.cache_clear()
    get_settings.cache_clear()


# ── _reranker_enabled_via_env (ALT-verbatim) ─────────────────────────────
def test_unset_env_falls_through_to_the_settings_default(monkeypatch):
    """W10: bei UNBESETZTER Variable entscheiden die Settings, nicht ALTs True.

    Vorher stand hier ``return True`` — die Vorgabe lief an den Settings vorbei,
    und der Live-Start meldete „Reranker geladen", obwohl die Vorgabe False war.
    Zwei Leser derselben Env-Variablen, und der ALT-verbatim Zweig gewann.
    """
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    get_settings.cache_clear()
    assert _reranker_enabled_via_env() is True  # = Vorgabe seit W11 (wie ALT)


def test_disabled_values_case_and_whitespace_insensitive(monkeypatch):
    for raw in ("false", "0", "no", "off", " FALSE ", "Off"):
        monkeypatch.setenv("RAG_RERANKER_ENABLED", raw)
        assert _reranker_enabled_via_env() is False, raw


def test_other_values_stay_enabled(monkeypatch):
    for raw in ("true", "1", "yes", "banana"):
        monkeypatch.setenv("RAG_RERANKER_ENABLED", raw)
        assert _reranker_enabled_via_env() is True, raw


# ── CPU-Budget: Worker × Threads-je-Inferenz ─────────────────────────────
#
# Nutzer-Vorgabe 2026-08-09: „die halbe CPU des Systems für Reranking und
# Embedding". Der Default muss diese Regel selbst herstellen — ein Server, auf
# dem niemand die Env setzt, ist der Normalfall, nicht die Ausnahme.
def test_default_concurrency_is_one_latency_before_throughput(monkeypatch):
    """W11: das Budget steckt in den Threads JE Inferenz, nicht in der Zahl
    gleichzeitiger Inferenzen. Bei wenigen Nutzern ist das die bessere Haelfte
    desselben Kuchens — 703 ms je RAG-Anfrage statt 1471 ms."""
    monkeypatch.delenv("RERANK_MAX_CONCURRENCY", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(rk.os, "cpu_count", lambda: 6)
    assert _rerank_max_concurrency() == 1


def test_threads_never_exceed_half_the_machine(monkeypatch):
    """Der Nutzer-Entscheid lautet „3 Threads" — fuer SEINEN 6-Kern-Server.
    Hart verdrahtet waere das auf 2 Kernen Ueberbuchung, also genau der Fehler
    aus ALTs Lasttest lt-e91ef209c1d6. Abgeleitet trifft es 6 Kerne exakt."""
    monkeypatch.delenv("RERANK_INTRA_OP_THREADS", raising=False)
    get_settings.cache_clear()
    for kerne, erwartet in ((6, 3), (8, 3), (16, 3), (4, 2), (2, 1), (1, 1)):
        monkeypatch.setattr(rk.os, "cpu_count", lambda k=kerne: k)
        assert _rerank_intra_op_threads() == erwartet, kerne


def test_concurrency_from_env_wins(monkeypatch):
    monkeypatch.setenv("RERANK_MAX_CONCURRENCY", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(rk.os, "cpu_count", lambda: 16)
    assert _rerank_max_concurrency() == 2


def test_the_standard_config_of_a_six_core_server(monkeypatch):
    """Die vom Nutzer bestaetigte Standard-Config, an einem Ort nachlesbar.

    1 Worker x 3 Threads = 3 von 6 Kernen — die halbe Maschine, auf Latenz
    verteilt statt auf Durchsatz. Gemessen: RAG-Pfad 703 ms, Karten-Gate 90 ms.
    """
    for name in ("RERANK_INTRA_OP_THREADS", "RERANK_MAX_CONCURRENCY",
                 "RERANK_CANDIDATES", "RAG_RERANKER_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(rk.os, "cpu_count", lambda: 6)
    assert _rerank_max_concurrency() == 1
    assert _rerank_intra_op_threads() == 3
    assert _rerank_max_concurrency() * _rerank_intra_op_threads() == 3  # halbe CPU
    assert rk.rerank_candidates() == 10
    assert _reranker_enabled_via_env() is True


def test_intra_op_from_env_wins(monkeypatch):
    monkeypatch.setenv("RERANK_INTRA_OP_THREADS", "3")
    get_settings.cache_clear()
    assert _rerank_intra_op_threads() == 3


# ── _get_reranker: jetzt mit echtem Backend ──────────────────────────────
def test_seam_none_when_disabled(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    assert _get_reranker() is None


def test_seam_none_without_the_model_asset(monkeypatch, tmp_path):
    # Fehlendes Modell ist kein Absturz: ALT loggte eine WARNING und rankte
    # embedding-only weiter. Das bleibt der Vertrag — ein Deploy ohne Asset
    # muss antworten können, nur etwas schlechter sortiert.
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    monkeypatch.setenv("RERANK_MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert _reranker_model_dir() is None
    assert _get_reranker() is None


def test_the_onnx_backend_ranks_german_relevance(monkeypatch):
    """Der eigentliche Wirknachweis — mit dem echten Modell.

    Gepinnt wird nicht eine Zahl, sondern die ORDNUNG und das Vorzeichen des
    Abstands: der Cross-Encoder muss thematisch passende Textstücke über
    unpassende setzen, und zwar deutlich. Genau darauf ruht das absolute
    Gate im Karten-Pfad (``card_reranker``).
    """
    # Ausdruecklich EIN — seit W10 ist die Vorgabe aus, und dieser Test prueft
    # gerade den eingeschalteten Zustand.
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    get_settings.cache_clear()
    if _reranker_model_dir() is None:
        pytest.skip("Modell-Asset nicht da (models/…-int8) — siehe deploy/README")
    rr = _get_reranker()
    assert rr is not None

    frage = "Wie funktioniert Bruchrechnung?"
    passend = "Brüche kürzt man, indem man Zähler und Nenner durch denselben Teiler teilt."
    unpassend = "Der Zweite Weltkrieg begann 1939 mit dem Überfall auf Polen."
    gut, schlecht = rr.predict([(frage, passend), (frage, unpassend)])
    assert gut > schlecht
    assert gut - schlecht > 2.0, (gut, schlecht)


# ── rerank_results (ALT-verbatim) ────────────────────────────────────────
def _r(chunk, score):
    return {"chunk": chunk, "score": score}


def test_empty_results_and_nonpositive_top_n():
    assert rerank_results("q", [], 3) == []
    assert rerank_results("q", [_r("a", 0.9)], 0) == []


def test_fallback_sorts_by_embedding_score_and_truncates(monkeypatch):
    # W7: früher stand hier `delenv(...)` — der Test verliess sich darauf, dass
    # es GAR KEIN Backend gibt. Seit es eines gibt, muss der Fallback-Pfad
    # ausdrücklich hergestellt werden, sonst prüft der Test den anderen Zweig.
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    out = rerank_results("q", [_r("low", 0.1), _r("high", 0.9), _r("mid", 0.5)], 2)
    assert [r["chunk"] for r in out] == ["high", "mid"]
    assert all("rerank_score" not in r for r in out)


class _FakeBackend:
    """predict() scores the pairs; here: reverse of embedding order."""

    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        return self.scores[: len(pairs)]


def test_backend_reorders_by_rerank_score(monkeypatch):
    fake = _FakeBackend([0.1, 0.9])  # first input scores low, second high
    monkeypatch.setattr(rk, "_get_reranker", lambda: fake)
    out = rerank_results("q", [_r("emb-best", 0.9), _r("emb-worst", 0.2)], 2)
    assert [r["chunk"] for r in out] == ["emb-worst", "emb-best"]  # CE wins
    assert out[0]["rerank_score"] == 0.9
    assert fake.pairs == [("q", "emb-best"), ("q", "emb-worst")]


def test_backend_predict_error_falls_back_to_score_sort(monkeypatch):
    class _Boom:
        def predict(self, pairs):
            raise RuntimeError("onnx down")

    monkeypatch.setattr(rk, "_get_reranker", lambda: _Boom())
    out = rerank_results("q", [_r("low", 0.1), _r("high", 0.9)], 2)
    assert [r["chunk"] for r in out] == ["high", "low"]


# ── W9: die Kandidatenzahl ist der Latenz-Hebel ──────────────────────────
def test_candidates_default_is_ten_not_alts_twentyfive(monkeypatch):
    """Bewusste ALT-Abweichung (Nutzer-Vorgabe 2026-08-09).

    ALT nahm 25. Gemessen bei 3 Threads kostet das 1853 ms gegen 703 ms bei 10 —
    die Kandidatenzahl dominiert die Latenz des RAG-Pfads. `_RAG_DEFAULTS`
    zieht mit (top_k 15 -> 10), sonst greift `max(candidates, top_k)` die 10 ab.
    """
    monkeypatch.delenv("RERANK_CANDIDATES", raising=False)
    get_settings.cache_clear()
    assert rk.rerank_candidates() == 10
    assert rk._RERANK_CANDIDATES == 25  # ALT-Wert bleibt als Beleg dokumentiert


def test_candidates_from_env(monkeypatch):
    # Gemessen bei 3 Threads: 25 Kandidaten = 1853 ms, 10 = 703 ms. Die Zahl
    # dominiert die Latenz des RAG-Pfads — deshalb gehört sie in die Config.
    monkeypatch.setenv("RERANK_CANDIDATES", "10")
    get_settings.cache_clear()
    assert rk.rerank_candidates() == 10


def test_the_two_paths_switch_independently(monkeypatch):
    """„Karten an, RAG aus" muss ausdrückbar sein.

    Vor W9 gab es nur den Hauptschalter: wer den teuren RAG-Rerank loswerden
    wollte, verlor das billige Off-Topic-Gate der Karten gleich mit. Die Kosten
    stehen 8:1 (1853 ms gegen 227 ms bei 3 Threads) — eine gemeinsame
    Entscheidung wäre für beide die falsche.
    """
    monkeypatch.setattr(rk, "_get_reranker", lambda: _FakeBackend([0.1, 0.9]))
    monkeypatch.setenv("RAG_CHUNK_RERANKER_ENABLED", "false")
    get_settings.cache_clear()
    out = rerank_results("q", [_r("emb-best", 0.9), _r("emb-worst", 0.2)], 2)
    assert [r["chunk"] for r in out] == ["emb-best", "emb-worst"]  # Embedding-Ordnung
    assert all("rerank_score" not in r for r in out)

    monkeypatch.setenv("RAG_CHUNK_RERANKER_ENABLED", "true")
    get_settings.cache_clear()
    out = rerank_results("q", [_r("emb-best", 0.9), _r("emb-worst", 0.2)], 2)
    assert [r["chunk"] for r in out] == ["emb-worst", "emb-best"]  # CE entscheidet


# ── Betriebs-Sichtbarkeit (2026-08-11) ─────────────────────────────────────
# Eingeschaltet ist nicht dasselbe wie einsatzbereit: fehlt das Modell, sagt
# der Code das heute nur in einer Protokollzeile beim ERSTEN Zug — wer nach
# einem Deploy wissen will, ob der Reranker greift, hat keine Handhabe.
# `reranker_status()` macht die drei Fälle abfragbar.

def test_reranker_status_off_wenn_abgeschaltet(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    assert rk.reranker_status() == "off"


def test_reranker_status_meldet_fehlendes_modell(monkeypatch):
    # Der stille Fall: eingeschaltet, aber im Verzeichnis liegt kein Export.
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    monkeypatch.setattr(rk, "_reranker_model_dir", lambda: None)
    assert rk.reranker_status() == "model-missing"


def test_reranker_status_ready_wenn_modell_da(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    monkeypatch.setattr(rk, "_reranker_model_dir", lambda: "/models/irgendwo")
    assert rk.reranker_status() == "ready"
