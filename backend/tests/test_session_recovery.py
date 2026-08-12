"""Audit F-1: ein geschluckter DB-Fehler darf die geteilte Sitzung nicht vergiften.

Beide Stellen fangen einen DB-Fehler bewusst ab und machen weiter — der Zug soll
an einem Lesefehler nicht scheitern. Ohne Rollback bleibt die anfragegebundene
``AsyncSession`` aber in einer abgebrochenen Transaktion zurück, und *danach*
scheitert jeder weitere Schreibvorgang desselben Zuges: Sitzungszustand und
Assistenz-Antwort gingen verloren. Aus einem folgenlosen Lese-Aussetzer würde so
ein Komplettausfall.

Diese Tests brauchen keine DB (Attrappen-Sitzung) und laufen darum immer — genau
wie der Fehlerpfad in ``test_usage_store.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.run(coro)


class _FehlerSession:
    """Eine Sitzung, deren ``execute`` scheitert und die den Rollback mitschreibt."""

    def __init__(self) -> None:
        self.rollbacks = 0

    async def execute(self, _stmt):
        raise RuntimeError("Verbindung weg")

    async def commit(self):
        raise RuntimeError("Verbindung weg")

    async def rollback(self):
        self.rollbacks += 1


# ── get_memory: der Lesepfad aus dem assess-Knoten ──────────────────────

def test_get_memory_raeumt_die_sitzung_auf_und_meldet_weiter() -> None:
    """Der Fehler muss beim Aufrufer ankommen (``assess`` fällt auf ``[]``
    zurück) — aber die Sitzung muss danach wieder benutzbar sein."""
    from boerdi.services.db_sessions import get_memory

    sess = _FehlerSession()
    with pytest.raises(RuntimeError):
        _run(get_memory(sess, "bb-1"))
    assert sess.rollbacks == 1, "ohne Rollback scheitert die spätere Persistenz"


def test_get_memory_rollt_im_gutfall_nicht_zurueck() -> None:
    """Kein Rollback auf dem heißen Pfad: er kostet eine Rundreise und würde
    fremde offene Arbeit mitnehmen."""
    from boerdi.services.db_sessions import get_memory

    class _Gut(_FehlerSession):
        async def execute(self, _stmt):
            return SimpleNamespace(all=lambda: [])

    sess = _Gut()
    assert _run(get_memory(sess, "bb-1")) == []
    assert sess.rollbacks == 0


# ── _log_turn_safety: der Schreibpfad zwischen assess und route ─────────

def test_safety_log_fehler_raeumt_die_sitzung_auf(monkeypatch) -> None:
    """Das Safety-Log ist Telemetrie und darf den Zug nicht anhalten — aber sein
    gescheiterter ``commit`` darf auch nicht die Persistenz danach mitreißen."""
    from boerdi.graph import build as build_mod

    async def _kaputt(*_a, **_kw):
        raise RuntimeError("commit gescheitert")

    monkeypatch.setattr(build_mod, "log_safety_event", _kaputt)
    monkeypatch.setattr(build_mod, "load_safety_config", lambda: {"logging": {"enabled": True}})

    ctx = SimpleNamespace(
        safety=SimpleNamespace(risk_level="high"),
        req=SimpleNamespace(session_id="bb-1", message="hallo"),
        client_ip="",
    )
    sess = _FehlerSession()

    assert _run(build_mod._log_turn_safety(ctx, sess)) is ctx  # Zug läuft weiter
    assert sess.rollbacks == 1, "ohne Rollback scheitert die spätere Persistenz"
