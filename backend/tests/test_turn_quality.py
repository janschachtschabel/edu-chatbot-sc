"""Das Tor vor dem Qualitäts-Eintrag (2026-08-15).

Es stand bis dahin nur an einer Stelle ausgeschrieben (``turn_persist``) — und
genau deshalb fehlte der Eintrag überall dort, wo ein Zug früher endet. Beim
Zusammenziehen ist das Tor die eigentliche Zusicherung: ein Betreiber, der die
Protokollierung abschaltet, erwartet, dass sie **überall** aus ist.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import ChatRequest, DebugInfo
from boerdi.services import turn_quality as tq


class _Spy:
    def __init__(self):
        self.calls: list[tuple] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _req() -> ChatRequest:
    return ChatRequest(session_id="bb-1", message="ja")


@pytest.fixture
def _schreiber(monkeypatch):
    """Der dumme Schreiber als Attrappe — er wird funktionslokal importiert,
    also am Ursprung gepatcht (Hauskonvention für LAZY-Importe)."""
    spy = _Spy()
    monkeypatch.setattr("boerdi.obs.quality_events.log_quality_event", spy)
    return spy


def _konfig(monkeypatch, *, enabled=True, privacy=True):
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_quality_log_config",
        lambda: {"logging": {"enabled": enabled}})
    monkeypatch.setattr(
        "boerdi.services.config_loader.load_privacy_config",
        lambda: {"quality": privacy})


@pytest.mark.asyncio
async def test_bei_offenen_toren_wird_geschrieben(monkeypatch, _schreiber):
    _konfig(monkeypatch)
    await tq.log_turn_quality(None, _req(), DebugInfo(pattern="M18"), turn_count=3)
    assert len(_schreiber.calls) == 1
    assert _schreiber.calls[0][0][3] == 3  # turn_count reicht durch


@pytest.mark.asyncio
async def test_abgeschaltete_protokollierung_schreibt_nichts(monkeypatch, _schreiber):
    _konfig(monkeypatch, enabled=False)
    await tq.log_turn_quality(None, _req(), DebugInfo(pattern="M18"))
    assert _schreiber.calls == []


@pytest.mark.asyncio
async def test_privatsphaere_sticht_die_protokollierung(monkeypatch, _schreiber):
    # Zwei Tore, UND-verknüpft: die Datenschutz-Einstellung darf die
    # Protokoll-Einstellung überstimmen, nicht umgekehrt.
    _konfig(monkeypatch, enabled=True, privacy=False)
    await tq.log_turn_quality(None, _req(), DebugInfo(pattern="M18"))
    assert _schreiber.calls == []


@pytest.mark.asyncio
async def test_ohne_debug_wird_trotzdem_gebucht(monkeypatch, _schreiber):
    # Die frühen Rückgaben der Direkt-Aktionen (fehlende collection_id) tragen
    # kein DebugInfo. Der Zug ist trotzdem passiert.
    _konfig(monkeypatch)
    await tq.log_turn_quality(None, _req(), None)
    assert len(_schreiber.calls) == 1
    assert _schreiber.calls[0][0][4] == {}


@pytest.mark.asyncio
async def test_ein_fehler_beim_buchen_bricht_den_zug_nicht(monkeypatch):
    # Ein Auswertungs-Eintrag ist Beiwerk; dass er fehlt, darf keine Antwort
    # kosten. Dieselbe Haltung wie ``_log_turn_safety`` im Graphen.
    _konfig(monkeypatch)

    async def _kaputt(*_a, **_k):
        raise RuntimeError("Tabelle weg")

    monkeypatch.setattr("boerdi.obs.quality_events.log_quality_event", _kaputt)
    await tq.log_turn_quality(None, _req(), DebugInfo(pattern="M18"))  # wirft nicht
