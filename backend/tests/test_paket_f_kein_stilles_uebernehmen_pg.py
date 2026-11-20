"""Plan 2026-11-20 §6, Entscheid E-F, gegen das echte Postgres: ein neues Gespräch übernimmt einen
Vorgang nie still, und eine Nachricht zählt nie als Antwort auf eine Frage aus einem anderen
Gespräch.

Gesehen im Durchtest R3 (20.11.): angemeldet holte ``arbeitsstand.auffrischen`` den jüngsten
offenen Vorgang (``vorgaenge.juengster``) in eine neue Sitzung; ihr erstes „Hallo“ wurde die
Freitext-Antwort auf die offene Frage des alten Laufs. Jetzt:

- neue Sitzung mit Anmeldung → kein Verweis, kein Lauf, „Hallo“ ist ein gewöhnlicher Zug; ``offene``
  nennt den wartenden Vorgang (Hinweis „Fortsetzen“);
- „Fortsetzen“ wechselt in das Gespräch des Vorgangs (dessen ``session_id``) → der Lauf ist da, die
  Antwort zählt;
- zeigt ein Verweis eines anderen Gesprächs auf den Vorgang (alter Stand), wird weder Freitext noch
  eine Wahl dort gespeichert.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from boerdi.api.schemas import ChatRequest
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ausloeser, wahl_zug, zug, zug_basis
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_e_f_uebernehmen_pg"
_A = "sitzung-ef-aaaaaaaaaa"          # das Gespräch, in dem die Frage gestellt wurde
_B = "sitzung-ef-bbbbbbbbbb"          # ein neues Gespräch derselben Person
_WER = "person-e-f"

_WAHL = {"id": "wahl", "titel": {"de": "Wahl"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
         "schritte": [
             {"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?"},
              "optionen": [{"id": "neu", "label": {"de": "Neu"}, "ziel": "neu"}],
              "freitext": {"ziel": "notiz", "schreibt": "wunsch"}},
             {"id": "neu", "typ": "ende", "text": {"de": "Neu."}},
             {"id": "notiz", "typ": "ende", "text": {"de": "Notiert."}}]}


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


@pytest.fixture
def welt(monkeypatch, db_url):
    for modul in (arbeitsstand, ausloeser):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: _WER)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(zug_basis, "save_message", nichts)
    monkeypatch.setattr(zug_basis, "update_session", nichts)
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: [_WAHL])
    return SimpleNamespace(url=db_url)


def _lauf(welt, ablauf):
    async def huelle():
        engine = create_async_engine(welt.url)
        sitzungen = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sitzungen() as s:
                for sid in (_A, _B):
                    await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                         "ON CONFLICT DO NOTHING"), {"s": sid})
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            async with sitzungen() as s:
                return await ablauf(s)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


def _req(sid: str, **mehr) -> ChatRequest:
    return ChatRequest(session_id=sid, message=mehr.pop("message", ""), **mehr)


async def _akte(s):
    z = (await s.execute(text("SELECT status, session_id, akte FROM vorgaenge"))).one()
    return z.status, z.session_id, z.akte


async def _frage_in_a(s) -> dict:
    """Ein Lauf in Gespräch A wartet an der Frage mit Freitext — die Sitzung A danach."""
    state: dict = {"entities": {}}
    await zug.starten(s, _req(_A, action=zug.AKTION, action_params={"ablauf": "wahl"}), state)
    return state


def test_e_f_neue_sitzung_kein_lauf_und_fortsetzen_bietet_ihn_an(welt):
    async def ablauf(s):
        await _frage_in_a(s)
        neu: dict = {"entities": {}}
        await arbeitsstand.auffrischen(s, _B, neu["entities"])
        nimmt = wahl_zug.nimmt_getippt(_B, neu, "Hallo")
        antwort = await wahl_zug.getippt(s, _req(_B, message="Hallo"), neu)
        offen = await vorgaenge.offene(s, _WER, ohne=_B)
        return neu, nimmt, antwort, [(o.session_id, o.status) for o in offen], await _akte(s)

    neu, nimmt, antwort, offen, (status, sitzung, akte) = _lauf(welt, ablauf)
    assert arbeitsstand.VERWEIS not in neu["entities"]
    assert nimmt is False and antwort is None              # „Hallo“ ist ein gewöhnlicher Zug
    assert offen == [(_A, "wartet_person")]                # „Fortsetzen“ führt nach A
    assert status == "wartet_person" and sitzung == _A
    assert akte["lauf"]["status"] == "wartet_wahl" and "wunsch" not in akte["teile"]


def test_e_f_nach_fortsetzen_ist_der_lauf_da_und_die_antwort_zaehlt(welt):
    """„Fortsetzen“ wechselt das Widget auf die Kennung des Vorgangs (A) — dort gilt der Verweis."""
    async def ablauf(s):
        state = await _frage_in_a(s)
        await arbeitsstand.auffrischen(s, _A, state["entities"])
        nimmt = wahl_zug.nimmt_getippt(_A, state, "Optik, Klasse 7")
        antwort = await wahl_zug.getippt(s, _req(_A, message="Optik, Klasse 7"), state)
        return nimmt, antwort, await _akte(s)

    nimmt, antwort, (_status, _sitzung, akte) = _lauf(welt, ablauf)
    assert nimmt is True and antwort.content.startswith("Notiert.")
    assert "wunsch" in akte["teile"] and akte["lauf"]["status"] == "fertig"


def test_e_f_freitext_in_einer_anderen_sitzung_ist_nie_die_antwort(welt):
    """Sicherung: auch wenn ein Verweis des neuen Gesprächs auf den Vorgang zeigt (Stand von vor
    E-F), ist weder ein Text noch ein Chip dort die Antwort auf die Frage aus A."""
    async def ablauf(s):
        state_a = await _frage_in_a(s)
        fremd: dict = {"entities": {arbeitsstand.VERWEIS: dict(
            state_a["entities"][arbeitsstand.VERWEIS])}}
        getippt = await wahl_zug.getippt(s, _req(_B, message="Hallo"), fremd)
        gewaehlt = await wahl_zug.waehlen(s, _req(_B, action=wahl_zug.AKTION, action_params={
            "ablauf": "wahl", "schritt": "frage", "wahl": "neu"}), fremd)
        return getippt, gewaehlt, await _akte(s)

    getippt, gewaehlt, (status, sitzung, akte) = _lauf(welt, ablauf)
    assert getippt is None
    assert gewaehlt.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert status == "wartet_person" and sitzung == _A
    assert akte["lauf"]["status"] == "wartet_wahl" and akte["lauf"]["schritt"] == "frage"
    assert "wunsch" not in akte["teile"] and not akte["lauf"].get("gewaehlt")
