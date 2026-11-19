"""Review N3 (19.11.): Frist der Einbettung, Rechnen mit numpy, Schwelle je Modell, Grenzfälle der
Schwelle, node_ids aus ``metadaten`` beim Speichern."""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import time

import numpy as np

from boerdi.services import llm, llm_einbettungen, llm_parallel
from boerdi.services import strukturentwurf_zuordnung as zu
from boerdi.settings import get_settings
from tests import zuordnung_beispiel as bsp

_NODE = "33333333-3333-4333-8333-333333333333"


def _entwurf() -> dict:
    return {"titel": "Erdkunde", "quelle": "ki", "knoten": copy.deepcopy(bsp.PUNKTE)}


# ── MAJOR 1: Frist ───────────────────────────────────────────────────────────────────────────────

def test_eine_haengende_einbettung_endet_an_der_frist():
    async def haengt(_texte):
        await asyncio.Event().wait()

    async def lauf():
        t0 = time.monotonic()
        ende = asyncio.get_running_loop().time() + 2.0
        erg = await zu.zuordnen(_entwurf(), bsp.teil(), einbetten=haengt, frist_ende=ende)
        return erg, time.monotonic() - t0

    erg, dauer = asyncio.run(lauf())
    assert erg.einbettung == 0 and erg.uebrig == 16 and dauer < 3.0


def test_ohne_restzeit_kein_aufruf():
    gerufen: list = []

    async def einbetten(texte):
        gerufen.append(texte)
        return []

    async def lauf():
        ende = asyncio.get_running_loop().time() + zu.MINDEST_REST_S / 2
        return await zu.zuordnen(_entwurf(), bsp.teil(), einbetten=einbetten, frist_ende=ende)

    assert asyncio.run(lauf()).uebrig == 16 and gerufen == []


def test_ausgelastet_ohne_nachziehen_und_der_zug_bleibt_frei(monkeypatch):
    """Alle Plätze belegt: die Einbettung wartet nur kurz und scheitert allein — der Zug gilt
    nicht als ausgelastet (``llm_parallel._anstellen`` mit eigener, kürzerer Frist)."""
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "30")
    get_settings.cache_clear()

    async def nie(**_k):
        raise AssertionError("ohne Platz kein Aufruf")

    monkeypatch.setattr(llm, "_aembedding", nie)

    async def lauf():
        llm_parallel.binde_zug()
        sem = llm_parallel._semaphore("anbieter")
        await sem.acquire()
        t0 = time.monotonic()
        ende = asyncio.get_running_loop().time() + 2.0
        try:
            erg = await zu.zuordnen(_entwurf(), bsp.teil(),
                                    einbetten=zu.einbetten_mit(None, ende), frist_ende=ende)
        finally:
            sem.release()
        return erg, time.monotonic() - t0, llm_parallel.ausgelastet()

    erg, dauer, ausgelastet = asyncio.run(lauf())
    assert erg.einbettung == 0 and dauer < 3.0 and ausgelastet is False


def test_die_platzfrist_liegt_unter_der_frist_des_betriebs(monkeypatch):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "30")
    get_settings.cache_clear()
    gesehen: list = []

    class _Platz:
        def __init__(self, kanal, *, frist_s=None):
            gesehen.append(frist_s)

        async def __aenter__(self):
            return None

        async def __aexit__(self, *_a):
            return False

    async def fake(**_k):
        from types import SimpleNamespace
        return SimpleNamespace(model="m", data=[{"embedding": [1.0], "index": 0}])

    monkeypatch.setattr(llm_einbettungen, "platz", _Platz)
    monkeypatch.setattr(llm, "_aembedding", fake)

    async def lauf():
        ende = asyncio.get_running_loop().time() + 300
        return await zu.einbetten_mit(None, ende)(["x"])

    assert asyncio.run(lauf()) == [[1.0]]
    assert gesehen[0] is not None and 0 < gesehen[0] < 30


# ── MAJOR 2: numpy ───────────────────────────────────────────────────────────────────────────────

def test_500_materialien_mal_30_punkte_sind_schnell():
    rng = np.random.default_rng(7)
    punkte = [{"id": f"k{n}", "titel": f"Punkt {n}"} for n in range(1, 31)]
    teil = {"format": "wlo.metadaten@1", "inhalte": [
        {"i": n, "titel": f"Material {n}", "beschreibung": "x"} for n in range(500)]}
    vektoren = rng.normal(size=(530, 1536)).tolist()

    async def einbetten(texte):
        assert len(texte) == 530
        return vektoren

    t0 = time.perf_counter()
    erg = asyncio.run(zu.zuordnen({"titel": "T", "quelle": "ki", "knoten": punkte}, teil,
                                  einbetten=einbetten))
    assert time.perf_counter() - t0 < 1.0
    assert erg.einbettung + erg.uebrig == 500


def test_kosinus():
    assert math.isclose(zu.kosinus([1, 0], [1, 0]), 1.0)
    assert math.isclose(zu.kosinus([1, 0], [0, 1]), 0.0)
    assert zu.kosinus([0, 0], [1, 0]) == 0.0


# ── MAJOR 3: Schwelle je Modell ──────────────────────────────────────────────────────────────────

def test_schwelle_nur_fuer_gemessene_modelle():
    assert zu.schwelle("text-embedding-3-small") == 0.36
    assert zu.schwelle("openai/text-embedding-3-small") == 0.36
    assert zu.schwelle("bge-m3") is None and zu.schwelle("") is None


def test_ein_ungemessenes_modell_zieht_nicht_nach(monkeypatch, caplog):
    monkeypatch.setenv("LLM_EMBED_MODEL", "bge-m3")
    get_settings.cache_clear()
    gerufen: list = []

    async def einbetten(texte):
        gerufen.append(texte)
        return []

    with caplog.at_level(logging.INFO, logger="boerdi.services.strukturentwurf_naehe"):
        erg = asyncio.run(zu.zuordnen(_entwurf(), bsp.teil(), einbetten=einbetten))
    assert gerufen == [] and erg.uebrig == 16
    assert any("bge-m3" in r.getMessage() and "Schwelle" in r.getMessage()
               for r in caplog.records)


# ── MINOR 5: Grenzfälle der Schwelle ─────────────────────────────────────────────────────────────

def _zwei(material: list[list[float]], punkte: list[list[float]]) -> zu.Zuordnung:
    daten = {"titel": "T", "quelle": "ki",
             "knoten": [{"id": "k1", "titel": "P1"}, {"id": "k2", "titel": "P2"}]}
    teil = {"format": "wlo.metadaten@1",
            "inhalte": [{"i": n, "titel": f"M{n}"} for n in range(len(material))]}

    async def einbetten(texte):
        return punkte + material

    return asyncio.run(zu.zuordnen(daten, teil, einbetten=einbetten))


def _bei(kosinus: float) -> list[float]:
    return [kosinus, math.sqrt(1 - kosinus * kosinus), 0.0]


def test_kosinus_genau_an_der_echten_schwelle():
    punkte = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    grenze = zu.schwelle("text-embedding-3-small")
    assert grenze == 0.36
    erg = _zwei([_bei(0.360), _bei(0.359)], punkte)
    assert [e["i"] for e in erg.daten["knoten"][0]["inhalte"]] == [0]   # 0,360 ≥ 0,36
    assert [e["i"] for e in erg.daten["nicht_zugeordnet"]] == [1]       # 0,359 < 0,36


def test_gleichstand_gewinnt_der_erste_punkt():
    """Zwei Punkte gleich ähnlich: der im Entwurf zuerst stehende (``argmax`` nimmt den ersten)."""
    erg = _zwei([[1.0, 1.0, 0.0]], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert [e["i"] for e in erg.daten["knoten"][0]["inhalte"]] == [0]
    assert "inhalte" not in erg.daten["knoten"][1]


# ── MINOR 6: node_ids aus ``metadaten`` beim Speichern ───────────────────────────────────────────

def _speichern(monkeypatch, teile: dict, entwurf: dict) -> dict:
    from boerdi.services import arbeitsstand

    async def teil_wert(s, v, name):
        return teile.get(name)

    monkeypatch.setattr(arbeitsstand.vorgaenge, "teil_wert", teil_wert)
    return asyncio.run(arbeitsstand._entwurf_mit_knoten(None, None, entwurf))


def _entwurf_mit(node_id: str | None = None) -> dict:
    inhalt = {"i": 4, "name": "Tsunami", **({"node_id": node_id} if node_id else {})}
    return {"titel": "E", "quelle": "ki", "quelle_block": "blockbsp01",
            "knoten": [{"id": "k1", "titel": "Erdbeben", "inhalte": [inhalt]}],
            "nicht_zugeordnet": [{"i": 5, "name": "Bruch", "node_id": _NODE}]}


def test_node_ids_kommen_auch_aus_metadaten_derselben_auswahl(monkeypatch):
    metadaten = {"format": "wlo.metadaten@1", "block_id": "blockbsp01", "inhalte": [
        {"i": 4, "node_id": _NODE, "titel": "Tsunami"}, {"i": 5, "node_id": "kaputt"}]}
    neu = _speichern(monkeypatch, {"metadaten": metadaten}, _entwurf_mit())
    assert neu["knoten"][0]["inhalte"][0]["node_id"] == _NODE
    # die des Clients gilt nie, eine ungültige aus ``metadaten`` auch nicht
    assert "node_id" not in neu["nicht_zugeordnet"][0]


def test_metadaten_einer_anderen_auswahl_zaehlen_nicht(monkeypatch):
    metadaten = {"format": "wlo.metadaten@1", "block_id": "anderes01", "inhalte": [
        {"i": 4, "node_id": _NODE}]}
    neu = _speichern(monkeypatch, {"metadaten": metadaten}, _entwurf_mit(_NODE))
    assert "node_id" not in neu["knoten"][0]["inhalte"][0]


# ── Zweites Review, MINOR 1: eigene Obergrenze ──────────────────────────────────────────────────

def test_ein_haengender_anbieter_endet_an_der_eigenen_obergrenze(monkeypatch):
    """Die Frist des Dienstes ist lang (Minuten): die Einbettung wartet trotzdem höchstens
    ``OBERGRENZE_S`` — der Entwurf kommt ohne Nachziehen."""
    from boerdi.services import strukturentwurf_naehe as naehe

    monkeypatch.setattr(naehe, "OBERGRENZE_S", 1.5)

    async def haengt(_texte):
        await asyncio.Event().wait()

    async def lauf(frist):
        t0 = time.monotonic()
        ende = None if frist is None else asyncio.get_running_loop().time() + frist
        erg = await zu.zuordnen(_entwurf(), bsp.teil(), einbetten=haengt, frist_ende=ende)
        return erg, time.monotonic() - t0

    for frist in (300.0, None):
        erg, dauer = asyncio.run(lauf(frist))
        assert erg.einbettung == 0 and erg.uebrig == 16 and dauer < 3.0


def test_die_platzfrist_ist_kurz(monkeypatch):
    from boerdi.services import strukturentwurf_naehe as naehe

    monkeypatch.setenv("LLM_SLOT_WAIT_S", "30")
    get_settings.cache_clear()
    assert 2.0 <= naehe._platz_frist(300.0) <= 3.0
    assert naehe._platz_frist(0.4) == 0.4
