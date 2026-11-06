"""Querschnitts-Review 2026-11-06 (V-3): nach einem Konflikt rechnet ``teile_speichern`` neu.

Wer liest, ändert und zurückschreibt (Ablage: Stand je Datei), darf nach ``VorgangKonflikt``
nicht den vorher berechneten Wert blind schreiben — sonst überschreibt die zweite Datei den Stand
der ersten.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import arbeitsstand
from boerdi.services.vorgaenge import VorgangKonflikt


class _S:
    def begin_nested(self):
        return _Nested()

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def _lage(monkeypatch, konflikte: int):
    geschrieben: list = []

    async def sperren(s, vorgang_id, aufrufer):
        geschrieben.append(("sperre", vorgang_id))

    async def speichern(s, session_id, entities, teile, nur_dieser=False):
        if sum(1 for g in geschrieben if g[0] == "konflikt") < konflikte:
            geschrieben.append(("konflikt", teile))
            raise VorgangKonflikt("v-1")
        geschrieben.append(("ok", teile))
        return SimpleNamespace(id="v-1")

    monkeypatch.setattr(arbeitsstand, "_speichern", speichern)
    monkeypatch.setattr(arbeitsstand.vorgaenge, "sperren", sperren)
    monkeypatch.setattr(arbeitsstand, "verweis", lambda entities, aufrufer: {"id": "v-1"})
    monkeypatch.setattr(arbeitsstand, "_verweis_aus", lambda v, a: {"id": v.id})
    monkeypatch.setattr(arbeitsstand, "aufrufer_fuer", lambda sid: "sitzung:x")
    return geschrieben


def test_mit_rueckruf_wird_unter_der_sperre_gerechnet_auch_beim_zweiten_versuch(monkeypatch):
    """Review Q1, Befund 3: das Lesen des Aufrufers lag vor dem Neulesen in ``_speichern`` — erst
    die Zeilensperre schließt das Fenster dazwischen."""
    geschrieben = _lage(monkeypatch, konflikte=1)
    alt = [("ablage", "t", {"stand": "alt"}, "z")]
    staende = iter(["erst", "frisch"])

    async def neu_rechnen():
        return [("ablage", "t", {"stand": next(staende)}, "z")]

    ok = asyncio.run(arbeitsstand.teile_speichern(_S(), "s", {}, alt, neu=neu_rechnen))
    assert ok is True
    assert [g[0] for g in geschrieben] == ["sperre", "konflikt", "sperre", "ok"]
    assert geschrieben[1][1][0][2] == {"stand": "erst"}
    assert geschrieben[3][1][0][2] == {"stand": "frisch"}


def test_ohne_rueckruf_bleibt_der_alte_wert(monkeypatch):
    geschrieben = _lage(monkeypatch, konflikte=1)
    alt = [("draft", "t", {"x": 1}, "z")]
    assert asyncio.run(arbeitsstand.teile_speichern(_S(), "s", {}, alt)) is True
    assert geschrieben[-1] == ("ok", alt)


def test_gibt_der_rueckruf_nichts_zurueck_wird_nichts_geschrieben(monkeypatch):
    geschrieben = _lage(monkeypatch, konflikte=1)

    async def nichts():
        return None

    alt = [("ablage", "t", {}, "z")]
    assert asyncio.run(arbeitsstand.teile_speichern(_S(), "s", {}, alt, neu=nichts)) is False
    assert [g[0] for g in geschrieben] == ["sperre"]
