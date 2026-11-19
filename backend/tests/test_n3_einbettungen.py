"""Paket N3: viele Texte in EINEM Einbettungsaufruf, der Verbrauch im Zähler des Zugs."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.obs.usage import new_accumulator
from boerdi.services import llm, llm_einbettungen
from boerdi.settings import get_settings


class _Fake:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        # absichtlich vertauscht: die Reihenfolge gilt nach ``index``, nicht nach Lage
        return SimpleNamespace(
            model="text-embedding-3-small",
            usage=SimpleNamespace(prompt_tokens=42, completion_tokens=0),
            data=[{"embedding": [0.0, 1.0], "index": 1, "object": "embedding"},
                  {"embedding": [1.0, 0.0], "index": 0, "object": "embedding"}])


def test_ein_aufruf_fuer_alle_texte_und_der_verbrauch_ist_gebucht(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    fake = _Fake()
    monkeypatch.setattr(llm, "_aembedding", fake)
    acc = new_accumulator()
    vektoren = asyncio.run(llm_einbettungen.einbettungen(
        ["eins", "x" * 9000], usage_acc=acc, phase="zuordnung"))
    assert vektoren == [[1.0, 0.0], [0.0, 1.0]]
    assert len(fake.calls) == 1
    gesendet = fake.calls[0]
    assert gesendet["model"] == "openai/text-embedding-3-small"
    assert gesendet["input"][0] == "eins" and len(gesendet["input"][1]) == 8000
    assert acc["prompt_tokens"] == 42 and acc["calls"] == 1
    assert acc["per_phase"]["zuordnung"]["prompt"] == 42
    assert acc["models"]["text-embedding-3-small"]["prompt"] == 42


def test_ohne_texte_kein_aufruf(monkeypatch):
    fake = _Fake()
    monkeypatch.setattr(llm, "_aembedding", fake)
    assert asyncio.run(llm_einbettungen.einbettungen([])) == []
    assert fake.calls == []


def test_fehler_laufen_durch(monkeypatch):
    async def kaputt(**_k):
        raise RuntimeError("weg")

    monkeypatch.setattr(llm, "_aembedding", kaputt)
    with pytest.raises(RuntimeError):
        asyncio.run(llm_einbettungen.einbettungen(["a"]))
