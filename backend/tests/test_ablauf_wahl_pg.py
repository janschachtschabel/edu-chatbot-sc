"""Paket AS-3a: Schnellantworten im Zug gegen das echte Postgres.

Der Start zeigt die Optionen als Direktaktion-Chips (``ablauf_wahl``), der Vorgang wartet auf die
Person. Die Wahl setzt fort; eine Wahl für einen anderen Schritt sagt „unbekannt“ und lässt den Lauf
stehen. Getippter Text an einem Schritt mit ``freitext`` wird ein Teil. Solange der Lauf wartet,
stehen die Chips auch unter einer Antwort der KI (der Weg zurück zum Ablauf).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import ausloeser, wahl_zug, zug, zug_basis
from tests import pg_utils
from tests.test_ablauf_zug import _req

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_as3a_wahl_pg"
_SID = "sitzung-0123456789"          # wie ``_req``

_WAHL = {"id": "wahl", "titel": {"de": "Wahl"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
         "schritte": [
             {"id": "frage", "typ": "nachricht", "text": {"de": "Wie weiter?"},
              "optionen": [{"id": "neu", "label": {"de": "Neu | anlegen"}, "ziel": "neu"},
                           {"id": "alt", "label": {"de": "Bestehende"}, "ziel": "alt"}],
              "freitext": {"ziel": "notiz", "schreibt": "wunsch"}},
             {"id": "neu", "typ": "ende", "text": {"de": "Neu."}},
             {"id": "alt", "typ": "ende", "text": {"de": "Alt."}},
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
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-wahl")

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
                await s.execute(text("INSERT INTO sessions (session_id) VALUES (:s) "
                                     "ON CONFLICT DO NOTHING"), {"s": _SID})
                await s.execute(text("DELETE FROM vorgaenge"))
                await s.commit()
            async with sitzungen() as s:
                return await ablauf(s)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


async def _vorgang(s):
    z = (await s.execute(text("SELECT status, akte FROM vorgaenge"))).one()
    return z.status, z.akte


def _chip(antwort, kennung):
    for chip in antwort.quick_replies:
        _praefix, label, aktion, params = chip.split("|", 3)
        if aktion == wahl_zug.AKTION and json.loads(params)["wahl"] == kennung:
            return label, json.loads(params)
    raise AssertionError(antwort.quick_replies)


def _start(s, state):
    return zug.starten(s, _req(action=zug.AKTION, action_params={"ablauf": "wahl"}), state)


def test_der_start_zeigt_die_chips_und_die_wahl_setzt_fort(welt):
    async def ablauf(s):
        state: dict = {"entities": {}}
        start = await _start(s, state)
        label, params = _chip(start, "neu")
        wartend = await _vorgang(s)
        # dieselben Chips auch ohne Datenbank (unter einer Antwort der KI)
        zwischendurch = wahl_zug.aktuelle_knoepfe(_SID, state, "de")
        weiter = await wahl_zug.waehlen(s, _req(action=wahl_zug.AKTION, action_params=params),
                                        state)
        return start, label, params, wartend, zwischendurch, weiter, await _vorgang(s)

    start, label, params, wartend, zwischendurch, weiter, ende = _lauf(welt, ablauf)
    assert start.content.startswith("Wie weiter?")
    assert label == "Neu / anlegen"                     # ein „|“ zerlegte sonst den Chip
    assert params == {"ablauf": "wahl", "schritt": "frage", "wahl": "neu"}
    assert wartend[0] == "wartet_person" and wartend[1]["lauf"]["status"] == "wartet_wahl"
    assert zwischendurch == start.quick_replies
    assert weiter.content.startswith("Neu.")
    assert ende[1]["lauf"]["status"] == "fertig"


def test_eine_wahl_fuer_einen_anderen_schritt_laesst_den_lauf_stehen(welt):
    async def ablauf(s):
        state: dict = {"entities": {}}
        await _start(s, state)
        antwort = await wahl_zug.waehlen(s, _req(action=wahl_zug.AKTION, action_params={
            "ablauf": "wahl", "schritt": "neu", "wahl": "neu"}), state)
        return antwort, await _vorgang(s)

    antwort, (_status, akte) = _lauf(welt, ablauf)
    # Review AS-3a, Befund 4: ein eigener Text statt „Ablauf gibt es nicht“
    assert antwort.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert akte["lauf"]["status"] == "wartet_wahl" and akte["lauf"]["schritt"] == "frage"


def test_freitext_wird_ein_teil(welt):
    async def ablauf(s):
        state: dict = {"entities": {}}
        await _start(s, state)
        assert wahl_zug.nimmt_getippt(_SID, state, "Optik, Klasse 7") is True
        antwort = await wahl_zug.getippt(
            s, _req().model_copy(update={"message": "Optik, Klasse 7"}), state)
        return antwort, await _vorgang(s), wahl_zug.nimmt_getippt(_SID, state, "x")

    antwort, (_status, akte), danach = _lauf(welt, ablauf)
    assert antwort.content.startswith("Notiert.")
    assert "wunsch" in akte["teile"]
    assert akte["lauf"]["status"] == "fertig" and danach is False


def test_ohne_wartenden_lauf_ist_freitext_ein_gewoehnlicher_zug(welt):
    async def ablauf(s):
        state: dict = {"entities": {}}
        return await wahl_zug.getippt(s, _req().model_copy(update={"message": "Hallo"}), state)

    assert _lauf(welt, ablauf) is None


# ── Review AS-3a ───────────────────────────────────────────────────────────

def test_ein_getipptes_label_ist_die_wahl(welt):
    """Befund 7 (D2): Text, der einer Option entspricht, ist diese Wahl — auch anders
    geschrieben."""
    async def ablauf(s):
        state: dict = {"entities": {}}
        await _start(s, state)
        antwort = await wahl_zug.getippt(s, _req().model_copy(update={"message": "  bestehende "}),
                                         state)
        return antwort, await _vorgang(s)

    antwort, (_status, akte) = _lauf(welt, ablauf)
    assert antwort.content.startswith("Alt.")
    assert "wunsch" not in akte["teile"] and akte["lauf"]["gewaehlt"] == ["alt"]


def test_ein_alter_chip_sagt_es_und_zeigt_die_geltenden(welt):
    """Befund 4: ein Chip für einen Schritt, an dem der Lauf nicht (mehr) steht, und für einen
    fremden Ablauf — „gilt nicht mehr“, dazu die Chips, die jetzt gelten; der Lauf bleibt."""
    async def ablauf(s):
        state: dict = {"entities": {}}
        start = await _start(s, state)
        alt = await wahl_zug.waehlen(s, _req(action=wahl_zug.AKTION, action_params={
            "ablauf": "wahl", "schritt": "neu", "wahl": "neu"}), state)
        fremd = await wahl_zug.waehlen(s, _req(action=wahl_zug.AKTION, action_params={
            "ablauf": "anderer", "schritt": "frage", "wahl": "neu"}), state)
        return start, alt, fremd, await _vorgang(s)

    start, alt, fremd, (_status, akte) = _lauf(welt, ablauf)
    for antwort in (alt, fremd):
        assert antwort.content == bot_text("de", "action.ablauf.wahlVeraltet")
        assert antwort.quick_replies == start.quick_replies
    assert akte["lauf"]["status"] == "wartet_wahl"


def test_ein_geaenderter_ablauf_raeumt_den_wartenden_lauf_auf(welt, monkeypatch):
    """Befund 3: nach einer Änderung der Schritte führt kein Chip mehr zurück — der Lauf wird
    abgebrochen, statt Wendungen und Modul-Auslöser für immer zu sperren."""
    async def ablauf(s):
        state: dict = {"entities": {}}
        await _start(s, state)
        geaendert = {**_WAHL, "schritte": [{**_WAHL["schritte"][0], "text": {"de": "Anders?"}},
                                           *_WAHL["schritte"][1:]]}
        monkeypatch.setattr(ausloeser, "_roh_liste", lambda: [geaendert])
        assert zug.lauf_wartet(_SID, state) is True
        await wahl_zug.aufraeumen(s, _SID, state)
        return await _vorgang(s), zug.lauf_wartet(_SID, state)

    (_status, akte), wartet = _lauf(welt, ablauf)
    assert akte["lauf"]["status"] == "abgebrochen" and wartet is False
