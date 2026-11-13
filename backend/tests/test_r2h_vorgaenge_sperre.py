"""Paket R2-h (Querschnitts-Review 2026-11-06, Rest): Verdrängen in ``vorgaenge.anlegen`` sperrt
die Opfer in derselben Reihenfolge wie ``dokument_teile_entfernen`` (nach Kennung) — erst dann
wird gelöscht. Ein ``DELETE … IN (…)`` sperrt in Plan-Reihenfolge; gegen die sortierte Sperre
konnten sich zwei Transaktionen verklemmen. Dazu: ``Teil`` gibt es nur noch einmal."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import vorgaenge


class _Sitzung:
    def __init__(self, zeilen):
        self.zeilen = zeilen
        self.anweisungen: list[str] = []

    async def execute(self, stmt, *_a, **_k):
        self.anweisungen.append(str(stmt).upper())
        return SimpleNamespace(all=lambda: self.zeilen)

    def add(self, _v):
        pass

    async def flush(self):
        pass


def test_r2h_erst_sortiert_sperren_dann_loeschen(monkeypatch):
    monkeypatch.setattr(vorgaenge, "MAX_JE_PERSON", 2)
    zeilen = [SimpleNamespace(id=k, status="fertig") for k in ("v-c", "v-a", "v-b")]
    s = _Sitzung(zeilen)
    asyncio.run(vorgaenge.anlegen(s, aufrufer="p", session_id="s", titel="t", zweck="z", tage=3))
    sperre = next(i for i, a in enumerate(s.anweisungen) if "FOR UPDATE" in a)
    loeschen = next(i for i, a in enumerate(s.anweisungen) if a.startswith("DELETE"))
    assert sperre < loeschen and "ORDER BY" in s.anweisungen[sperre]


def test_r2h_teil_gibt_es_einmal():
    from boerdi.services import arbeitsstand_teile
    from boerdi.services.ablauf import treiber

    assert treiber.Teil is arbeitsstand_teile.Teil
