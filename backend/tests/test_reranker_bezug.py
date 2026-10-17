"""Das Reranker-Modell bezieht sich selbst (Nutzer-Entscheid 2026-10-15).

Vorgabe aus. Wird ``RAG_RERANKER_ENABLED`` eingeschaltet und fehlt das Modell, lädt das Backend
es beim Start im Hintergrund — feste Version auf Hugging Face, Größe und SHA-256 geprüft, atomar
abgelegt, mit Sperre gegen parallele Kopien. Solange es fehlt, rechnet nichts damit; danach
greift es ohne Neustart. Gefälscht ist nur das Netz (``httpx.MockTransport``)."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time

import httpx
import pytest

from boerdi.services.rag import rerank as rk
from boerdi.services.rag import reranker_bezug as rb
from boerdi.settings import get_settings

_ONNX = b"onnx-inhalt" * 100
_TOK = b'{"tokenizer": true}'


@pytest.fixture
def klein(monkeypatch, tmp_path):
    """Ein Manifest mit kleinen Dateien und ein leeres Modellverzeichnis."""
    dateien = (
        rb.Datei("onnx/model.onnx", "model_quint8_avx2.onnx", len(_ONNX),
                 hashlib.sha256(_ONNX).hexdigest()),
        rb.Datei("tokenizer.json", "tokenizer.json", len(_TOK), hashlib.sha256(_TOK).hexdigest()),
    )
    monkeypatch.setattr(rb, "DATEIEN", dateien)
    monkeypatch.setenv("RERANK_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    get_settings.cache_clear()
    rk._get_reranker.cache_clear()
    rb._zustand = ""
    yield tmp_path
    get_settings.cache_clear()
    rk._get_reranker.cache_clear()
    rb._zustand = ""


def _netz(antworten: dict[str, bytes], gesehen: list[str] | None = None):
    def antwort(request: httpx.Request) -> httpx.Response:
        if gesehen is not None:
            gesehen.append(request.url.path)
        for pfad, inhalt in antworten.items():
            if request.url.path.endswith(pfad):
                return httpx.Response(200, content=inhalt)
        return httpx.Response(404)

    return lambda **kw: httpx.Client(transport=httpx.MockTransport(antwort), **kw)


def test_vorgabe_ist_aus(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    get_settings.cache_clear()
    assert rk._reranker_enabled_via_env() is False
    assert rk.reranker_status() == "off"


def test_die_quelle_ist_gepinnt():
    assert len(rb.REVISION) == 40 and rb.REVISION in rb.QUELLE
    assert all(len(d.sha256) == 64 and d.groesse > 0 for d in rb.DATEIEN)


def test_laedt_prueft_und_legt_atomar_ab(klein):
    gesehen: list[str] = []
    ok = rb.beziehen(klein, client_fabrik=_netz(
        {"model.onnx": _ONNX, "tokenizer.json": _TOK}, gesehen))
    ziel = klein / rb.SLUG
    assert ok and (ziel / "model_quint8_avx2.onnx").read_bytes() == _ONNX
    assert (ziel / "tokenizer.json").read_bytes() == _TOK
    assert rk._reranker_model_dir() == str(ziel)
    assert not [p for p in klein.iterdir() if p.name.startswith(".")], "keine Reste"
    assert all(rb.REVISION in p for p in gesehen)


def test_falscher_pruefwert_legt_nichts_ab(klein):
    ok = rb.beziehen(klein, client_fabrik=_netz({"model.onnx": b"manipuliert",
                                                 "tokenizer.json": _TOK}))
    assert not ok and not (klein / rb.SLUG).exists()
    assert rk._reranker_model_dir() is None
    assert not [p for p in klein.iterdir() if p.name.startswith(".")]


def test_zu_grosse_antwort_wird_abgebrochen(klein):
    ok = rb.beziehen(klein, client_fabrik=_netz({"model.onnx": _ONNX + b"x" * 10_000,
                                                 "tokenizer.json": _TOK}))
    assert not ok and not (klein / rb.SLUG).exists()


def test_eine_frische_sperre_laesst_den_anderen_laden(klein):
    """Mehrere Kopien teilen ein Volume: nur eine lädt."""
    (klein / rb.SPERRE).write_text("123")
    gesehen: list[str] = []
    assert rb.beziehen(klein, client_fabrik=_netz({}, gesehen)) is False
    assert gesehen == []


def test_eine_alte_sperre_wird_uebernommen(klein):
    sperre = klein / rb.SPERRE
    sperre.write_text("123")
    alt = time.time() - rb.SPERRE_GILT_S - 60
    os.utime(sperre, (alt, alt))
    assert rb.beziehen(klein, client_fabrik=_netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    assert not sperre.exists()


def test_vorhandenes_modell_wird_nicht_erneut_geladen(klein):
    ziel = klein / rb.SLUG
    ziel.mkdir()
    (ziel / "model_quint8_avx2.onnx").write_bytes(_ONNX)
    gesehen: list[str] = []
    assert rb.beziehen(klein, client_fabrik=_netz({}, gesehen)) is True
    assert gesehen == []


class _Fake:
    def predict(self, pairs):
        return [0.0] * len(pairs)


def test_bereitstellen_laedt_und_schaltet_ohne_neustart_frei(klein, monkeypatch):
    monkeypatch.setattr(rk, "_OnnxReranker", lambda _d: _Fake())
    assert rk._get_reranker() is None, "ohne Modell rechnet nichts"
    assert rk.reranker_status() == "model-missing"
    monkeypatch.setattr(rb, "_client_fabrik", _netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    asyncio.run(rb.bereitstellen())
    assert rk.reranker_status() == "ready"
    assert isinstance(rk._get_reranker(), _Fake), "greift ohne Neustart"


def test_fehlschlag_wird_im_status_genannt(klein, monkeypatch):
    monkeypatch.setattr(rb, "_client_fabrik", _netz({}))
    asyncio.run(rb.bereitstellen())
    assert rk.reranker_status() == "download-failed"
    assert rk._get_reranker() is None


def test_ausgeschaltet_oder_ohne_selbstbezug_wird_nichts_geladen(klein, monkeypatch):
    gesehen: list[str] = []
    monkeypatch.setattr(rb, "_client_fabrik", _netz({}, gesehen))
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    asyncio.run(rb.bereitstellen())
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "true")
    monkeypatch.setenv("RERANK_AUTO_DOWNLOAD", "false")
    get_settings.cache_clear()
    asyncio.run(rb.bereitstellen())
    assert gesehen == []
    assert rk.reranker_status() == "model-missing"


def test_waehrend_des_ladens_meldet_der_status_downloading(klein, monkeypatch):
    rb._zustand = "downloading"
    assert rk.reranker_status() == "downloading"


def test_eine_wartende_kopie_uebernimmt_das_ergebnis_der_anderen(klein, monkeypatch):
    """Die Sperre hält eine andere Kopie; sie legt das Modell ab — diese hier schaltet es frei."""
    monkeypatch.setattr(rk, "_OnnxReranker", lambda _d: _Fake())
    monkeypatch.setattr(rb, "WARTE_TAKT_S", 0.01)
    (klein / rb.SPERRE).write_text("999999")
    ziel = klein / rb.SLUG

    async def szenario():
        async def andere_kopie():
            await asyncio.sleep(0.05)
            ziel.mkdir()
            (ziel / "model_quint8_avx2.onnx").write_bytes(_ONNX)
            (klein / rb.SPERRE).unlink()

        await asyncio.wait_for(asyncio.gather(rb.bereitstellen(), andere_kopie()), timeout=5)

    asyncio.run(szenario())
    assert rk.reranker_status() == "ready"
    assert isinstance(rk._get_reranker(), _Fake)


def test_eine_verwaiste_sperre_haelt_nicht_ewig_auf(klein, monkeypatch):
    """Stürzt die ladende Kopie ab, bleibt ihre Sperre liegen — die wartende übernimmt."""
    monkeypatch.setattr(rk, "_OnnxReranker", lambda _d: _Fake())
    monkeypatch.setattr(rb, "WARTE_TAKT_S", 0.01)
    monkeypatch.setattr(rb, "SPERRE_GILT_S", 0.2)
    monkeypatch.setattr(rb, "_client_fabrik", _netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    (klein / rb.SPERRE).write_text("999999")

    async def mit_frist():
        await asyncio.wait_for(rb.bereitstellen(), timeout=5)

    asyncio.run(mit_frist())
    assert rk.reranker_status() == "ready"


# ── Review Paket 11 I (2026-10-15) ──────────────────────────────────────────────
def test_r1_nicht_beschreibbares_verzeichnis_meldet_download_failed(klein, monkeypatch):
    """Ein schreibgeschützter Ordner (alter ``:ro``-Mount, Ordner gehört root) darf den Status nicht
    auf ``downloading`` stehen lassen."""
    def verboten(_basis):
        raise PermissionError("read-only file system")

    monkeypatch.setattr(rb, "_sperre_nehmen", verboten)
    asyncio.run(asyncio.wait_for(rb.bereitstellen(), timeout=5))
    assert rk.reranker_status() == "download-failed"


def test_r1_jede_ausnahme_endet_in_download_failed(klein, monkeypatch):
    def kaputt(_basis, **_kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(rb, "beziehen", kaputt)
    asyncio.run(asyncio.wait_for(rb.bereitstellen(), timeout=5))
    assert rk.reranker_status() == "download-failed"


def test_r2_der_sperr_inhalt_ist_je_versuch_eindeutig():
    """Im Container ist die Prozessnummer überall 1 — sie taugt nicht als Kennung."""
    import socket

    a, b = rb._sperr_kennung(), rb._sperr_kennung()
    assert a != b
    assert socket.gethostname() in a


def test_r2_zwei_gleichzeitige_kopien_mit_derselben_pid_laden_einmal(klein):
    """Zwei Threads im selben Prozess = zwei Container mit PID 1: genau einer lädt, das Ergebnis
    ist vollständig, es bleiben keine Reste."""
    import threading

    gesehen: list[str] = []
    langsam = _netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}, gesehen)
    ergebnisse: list[bool] = []

    def lauf():
        ergebnisse.append(rb.beziehen(klein, client_fabrik=langsam))

    t = [threading.Thread(target=lauf) for _ in range(2)]
    for x in t:
        x.start()
    for x in t:
        x.join(10)
    ziel = klein / rb.SLUG
    assert (ziel / "model_quint8_avx2.onnx").read_bytes() == _ONNX
    assert (ziel / "tokenizer.json").read_bytes() == _TOK
    assert not [p for p in klein.iterdir() if p.name.startswith(".")], "keine Reste"
    assert True in ergebnisse


def test_r3_die_sperre_bekommt_lebenszeichen(klein, monkeypatch):
    """Ein laufender Download erneuert seine Sperre — so darf die Verfallszeit kurz sein."""
    monkeypatch.setattr(rb, "LEBENSZEICHEN_S", 0.0)
    erneuert: list[float] = []
    original = rb._lebenszeichen

    def merken(pfad, kennung):
        erneuert.append(time.time())
        original(pfad, kennung)

    monkeypatch.setattr(rb, "_lebenszeichen", merken)
    assert rb.beziehen(klein, client_fabrik=_netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    assert erneuert, "keine Erneuerung der Sperre während des Ladens"
    assert rb.SPERRE_GILT_S <= 600, "eine verwaiste Sperre hält den nächsten Start nur kurz auf"


def test_r4_ein_troepfelnder_strom_endet_an_der_gesamtfrist(klein, monkeypatch):
    monkeypatch.setattr(rb, "FRIST_JE_DATEI_S", 0.0)
    ok = rb.beziehen(klein, client_fabrik=_netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    assert not ok and not (klein / rb.SLUG).exists()


def test_r5_ein_unvollstaendiger_zielordner_wird_ersetzt(klein):
    ziel = klein / rb.SLUG
    ziel.mkdir()
    (ziel / "tokenizer.json").write_bytes(b"halb")
    assert rb.beziehen(klein, client_fabrik=_netz({"model.onnx": _ONNX, "tokenizer.json": _TOK}))
    assert (ziel / "model_quint8_avx2.onnx").read_bytes() == _ONNX
    assert (ziel / "tokenizer.json").read_bytes() == _TOK

