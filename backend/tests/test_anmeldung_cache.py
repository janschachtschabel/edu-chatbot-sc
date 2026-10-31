"""Paket 19 (Audit 2026-10-31, N-10): der Zwischenspeicher der Anmeldung verdrängt, statt zu leeren.

Bis hier leerte ``_cache.clear()`` bei 1024 Einträgen alles — auch die bestätigten Personen, die
danach ihren nächsten Zug mit einem ``wlo_auth_status``-Rundlauf (bis 5 s) bezahlten. Und jeder
neue ``wlo…``-Block (beliebig fälschbar) legte einen Eintrag an. Jetzt: LRU-Verdrängung, negative
Einträge zuerst, und für negative eine eigene, kleinere Obergrenze.

Dazu :func:`anmeldung.ist_bestaetigte_person` für die Drosselung (M-4): liest nur den Speicher,
fragt nie den Server.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from boerdi.services.mcp import anmeldung, auth


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    monkeypatch.setattr(anmeldung, "HOECHSTENS", 6)
    monkeypatch.setattr(anmeldung, "HOECHSTENS_NEGATIV", 3)
    monkeypatch.setattr(anmeldung, "_fragen", _fragen)
    anmeldung._cache.clear()
    auth.set_turn_auth_block(None)
    yield
    anmeldung._cache.clear()
    auth.set_turn_auth_block(None)


_ANTWORT: dict[str, bool] = {}


async def _fragen() -> anmeldung.Befund:
    person = _ANTWORT["person"]
    return anmeldung.Befund(person=person, kennung="p:x" if person else "")


def _zug(block: str, person: bool) -> None:
    async def lauf() -> None:
        auth.set_turn_auth_block(block)
        await anmeldung.bestaetige_anmeldung()

    _ANTWORT["person"] = person
    asyncio.run(lauf())


def _fp(block: str) -> str:
    return auth.fingerabdruck(block)


def test_volle_liste_verdraengt_statt_alles_zu_leeren():
    for i in range(6):
        _zug(f"wlo2.person-{i}", person=True)
    _zug("wlo2.person-6", person=True)
    assert len(anmeldung._cache) == 6
    assert _fp("wlo2.person-0") not in anmeldung._cache  # der älteste ging
    assert _fp("wlo2.person-6") in anmeldung._cache


def test_negative_eintraege_gehen_zuerst():
    for i in range(3):
        _zug(f"wlo2.person-{i}", person=True)
    for i in range(3):
        _zug(f"wlo2.falsch-{i}", person=False)
    _zug("wlo2.person-neu", person=True)
    # voll (6): ein negativer musste gehen, keine Person
    assert all(_fp(f"wlo2.person-{i}") in anmeldung._cache for i in range(3))
    assert _fp("wlo2.falsch-0") not in anmeldung._cache


def test_negative_haben_eine_eigene_obergrenze():
    _zug("wlo2.person-a", person=True)
    for i in range(10):
        _zug(f"wlo2.falsch-{i}", person=False)
    negativ = [e for e in anmeldung._cache.values() if not e[1].person]
    assert len(negativ) == 3
    assert _fp("wlo2.person-a") in anmeldung._cache
    assert _fp("wlo2.falsch-9") in anmeldung._cache


def test_ein_treffer_frischt_die_reihenfolge_auf():
    for i in range(6):
        _zug(f"wlo2.person-{i}", person=True)
    _zug("wlo2.person-0", person=True)  # Treffer aus dem Speicher
    _zug("wlo2.person-6", person=True)
    assert _fp("wlo2.person-0") in anmeldung._cache
    assert _fp("wlo2.person-1") not in anmeldung._cache
