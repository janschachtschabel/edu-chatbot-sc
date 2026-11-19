"""Paket U5 (Plan 2026-11-17, Nachtrag aus U6): Schließt ein Start den Vorgang, nimmt der neue die
hier im Chat gelesenen Angaben (``metadaten`` mit ``quelle: chatbot``) mit wie die Auswahl —
Metadaten aus WLO nicht (sie hängen an ``ablage``, N14)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services.ablauf import zug


def _v(teile: dict) -> SimpleNamespace:
    return SimpleNamespace(akte={"teile": {n: {"typ": "t", "zusammenfassung": "z"} for n in teile}},
                           werte=teile)


def _mit(monkeypatch, teile: dict) -> list[str]:
    async def teil_wert(s, v, name):
        return v.werte.get(name)

    monkeypatch.setattr(zug.vorgaenge, "teil_wert", teil_wert)
    return [t[0] for t in asyncio.run(zug._bereitstellung(None, _v(teile)))]


def test_lokale_metadaten_gehen_mit(monkeypatch):
    lokal = {"format": "wlo.metadaten@1", "quelle": "chatbot", "inhalte": []}
    assert _mit(monkeypatch, {"struktur": {"x": 1}, "metadaten": lokal}) == ["struktur",
                                                                            "metadaten"]


def test_metadaten_aus_wlo_bleiben(monkeypatch):
    wlo = {"format": "wlo.metadaten@1", "inhalte": [{"node_id": "n"}]}
    assert _mit(monkeypatch, {"struktur": {"x": 1}, "metadaten": wlo}) == ["struktur"]
