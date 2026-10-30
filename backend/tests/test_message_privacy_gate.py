"""Datenschutz-Schalter ``privacy-config.logging.messages`` (Port-Regression).

**Der Befund** (2026-09-27): ALT hielt sich an den Schalter —
``app/routers/chat_session_utils.py:37`` machte jedes Speichern einer
Chatnachricht zum No-op, sobald ``logging.messages: false`` stand. Im NEU las
niemand den Wert; ``db_sessions.save_message`` speicherte immer, und das Studio
bot einen Schalter an, der nichts tat.

Wiederhergestellt ist genau das ALT-Verhalten: der Schalter unterbindet nur die
Nachrichten (Person UND Bot, samt Karten und Debug). Sitzungszeile, Gedächtnis,
Qualitäts- und Sicherheitsprotokoll haben ihre eigenen Tore bzw. bleiben.

Ohne DB (Attrappen-Sitzung), läuft darum immer. Der Schalter wird über einen
gebundenen Attrappen-Store gesetzt, nicht per Patch am Lader — so prüft der
Test auch die Verdrahtung zum echten ``load_privacy_config``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from boerdi.services import config_loader as cl
from boerdi.services import db_sessions


class _Store:
    def __init__(self, areas: dict[str, dict[str, Any]]) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


class _Sitzung:
    """Merkt sich, was gespeichert werden sollte."""

    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        obj.id = 4711
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture()
def schalter():
    """Bindet einen Store mit ``logging.messages`` = dem übergebenen Wert."""

    def _setze(messages: bool) -> None:
        cl.bind_store(_Store({
            "01-base/privacy-config": {"logging": {"messages": messages}},
        }))

    yield _setze
    cl.bind_store(None)


def _speichere(sess: _Sitzung, role: str) -> int | None:
    return asyncio.run(db_sessions.save_message(
        sess, "bb-1", role, "geheim", cards=[{"id": "a"}], debug={"x": 1},
    ))


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_aus_speichert_keine_nachricht(schalter, role) -> None:
    schalter(False)
    sess = _Sitzung()
    assert _speichere(sess, role) is None
    assert sess.added == []
    assert sess.commits == 0


def test_an_speichert_wie_bisher(schalter) -> None:
    schalter(True)
    sess = _Sitzung()
    assert _speichere(sess, "user") == 4711
    assert [m.content for m in sess.added] == ["geheim"]
    assert sess.commits == 1


def test_ohne_eintrag_wird_gespeichert() -> None:
    """Fehlt der Bereich (oder der Schlüssel), gilt ALTs Vorgabe: speichern."""
    cl.bind_store(_Store({}))
    try:
        sess = _Sitzung()
        assert _speichere(sess, "user") == 4711
    finally:
        cl.bind_store(None)


def test_scheitert_die_abfrage_wird_nicht_gespeichert(monkeypatch, caplog) -> None:
    """Paket 18E (F1, Nutzer-Entscheid 2026-10-30): fail-closed. Bis dahin speicherte NEU wie
    ALT („Loader failure → default to logging") — ein ausdrückliches „aus“ scheiterte dann an
    einer kaputten Konfiguration, und es stand nur eine DEBUG-Zeile im Log."""
    from boerdi.obs import drossel

    drossel.zuruecksetzen()

    def _kaputt() -> dict:
        raise RuntimeError("config kaputt")

    monkeypatch.setattr(db_sessions, "load_privacy_config", _kaputt)
    sess = _Sitzung()
    with caplog.at_level("WARNING"):
        assert _speichere(sess, "assistant") is None
        assert _speichere(sess, "user") is None
    assert sess.added == []
    warnungen = [r for r in caplog.records if "Datenschutz-Konfiguration" in r.getMessage()]
    assert len(warnungen) == 1  # gedrosselt


def test_aus_als_text_speichert_keine_nachricht() -> None:
    """Paket 18E (N1): ``messages: "false"`` aus dem Rohtext-Editor heißt „aus“."""
    cl.bind_store(_Store({"01-base/privacy-config": {"logging": {"messages": "false"}}}))
    try:
        sess = _Sitzung()
        assert _speichere(sess, "user") is None
    finally:
        cl.bind_store(None)
