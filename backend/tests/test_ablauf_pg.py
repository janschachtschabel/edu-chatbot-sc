"""Querschnitts-Review 2026-11-06 (Q4): Ablauf, Auftrag und Ablage gegen das echte Postgres.

Die übrigen Ablauf-Tests ersetzen die Datenbank durch einen Speicher im Arbeitsspeicher —
Savepoints, bedingte Updates und Kaskaden sehen sie nicht (so blieb Befund 1 der Nachprüfung von Q3
unbemerkt). Hier laufen dieselben Wege mit echten Vorgängen: Start und Fortsetzen, ein neuer Ablauf
auf einem Vorgang mit beendetem Lauf (M6), ein Konflikt mit einer zweiten Sitzung während des
Treibers, ein Auftrag bis zum Abholen, ein Zug mitten in einem Ablage-Stapel, zwei Schreiber
zugleich auf einem Stapel, die Grenze je Person samt Kaskade der Aufträge.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import auftrag_zug, ausloeser, zug, zug_basis
from boerdi.services.auftraege import client
from tests import pg_utils
from tests.test_ablauf_auftrag import _SCHRITTE, _roh
from tests.test_ablauf_zug import _geprueft, _katalog, _req

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_q4_ablauf_pg"
_SID = "sitzung-0123456789"          # wie ``_req``
_WER = "person-pg"


@pytest.fixture(scope="module")
def db_url():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


@pytest.fixture
def welt(monkeypatch, db_url):
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/flows/{flow}/jobs")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    from boerdi.settings import get_settings

    get_settings.cache_clear()
    for modul in (arbeitsstand, ausloeser, auftrag_zug):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: True)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: _WER)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(zug_basis, "save_message", nichts)
    monkeypatch.setattr(zug_basis, "update_session", nichts)
    katalog = _katalog()
    katalog["ablaeufe"].append(_roh(schritte=[{**_SCHRITTE[0], "argumente": {"text": "fest"}},
                                              *_SCHRITTE[1:]]))
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    staende: list = []

    async def starten(flow, eingaben):
        return "job-pg-1"

    async def stand(job_id):
        return staende.pop(0)

    monkeypatch.setattr(client, "starten", starten)
    monkeypatch.setattr(client, "stand", stand)
    yield SimpleNamespace(url=db_url, staende=staende)
    get_settings.cache_clear()


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
                return await ablauf(s, sitzungen)
        finally:
            await engine.dispose()
    return asyncio.run(huelle())


async def _vorgaenge(s):
    zeilen = await s.execute(text("SELECT status, akte FROM vorgaenge ORDER BY erstellt"))
    return [(z.status, z.akte) for z in zeilen]


def test_start_und_fortsetzen_mit_echtem_vorgang(welt):
    async def ablauf(s, _sitzungen):
        state: dict = {"entities": {}}
        start = await zug.starten(s, _req(action=zug.AKTION,
                                          action_params={"ablauf": "sammlungsstruktur"}), state)
        geprueft = _geprueft(start.ui.ui_bloecke[0], "erfasst")
        assert await zug.wartet_auf(s, _SID, state, geprueft) is True
        await zug.fortsetzen(s, _req(), state, geprueft)
        return await _vorgaenge(s)

    [(status, akte)] = _lauf(welt, ablauf)
    assert set(akte["teile"]) == {"structure", "draft"}
    assert akte["lauf"]["schritt"] == "bearbeiten" and status == "wartet_person"


def test_ein_anderer_ablauf_schliesst_den_vorgang_und_beginnt_einen_neuen(welt):
    async def ablauf(s, _sitzungen):
        state: dict = {"entities": {}}
        await zug.starten(s, _req(action=zug.AKTION,
                                  action_params={"ablauf": "sammlungsstruktur"}), state)
        await zug.starten(s, _req(action=zug.AKTION, action_params={"ablauf": "lesen"}), state)
        auftraege = (await s.execute(text("SELECT status FROM vorgang_auftraege"))).scalars()
        return await _vorgaenge(s), list(auftraege)

    [(alt_status, alt), (neu_status, neu)], auftraege = _lauf(welt, ablauf)
    assert alt_status == "fertig" and alt["lauf"]["status"] == "abgebrochen"
    assert neu_status == "wartet_auftrag" and neu["lauf"]["ablauf"] == "lesen"
    assert auftraege == ["laeuft"]


def test_eine_zweite_sitzung_waehrend_des_treibers_ist_ein_konflikt(welt, monkeypatch):
    async def ablauf(s, sitzungen):
        state: dict = {"entities": {}}
        start = await zug.starten(s, _req(action=zug.AKTION,
                                          action_params={"ablauf": "sammlungsstruktur"}), state)
        echt = zug_basis.rechne

        async def und_daneben(*a, **k):
            aus = await echt(*a, **k)
            async with sitzungen() as zweite:       # eine zweite Sitzung derselben Person
                await zweite.execute(text("UPDATE vorgaenge SET akte_version = akte_version + 1"))
                await zweite.commit()
            return aus

        monkeypatch.setattr(zug_basis, "rechne", und_daneben)
        antwort = await zug.fortsetzen(s, _req(), state,
                                       _geprueft(start.ui.ui_bloecke[0], "erfasst"))
        return antwort.content, await _vorgaenge(s)

    inhalt, [(_status, akte)] = _lauf(welt, ablauf)
    assert inhalt == bot_text("de", "action.ablauf.konflikt")
    assert akte["lauf"]["schritt"] == "erfassen"         # nicht mit altem Stand überschrieben
    assert "draft" not in akte["teile"]


def test_ein_auftrag_bis_zum_abholen(welt):
    welt.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))

    async def ablauf(s, _sitzungen):
        state: dict = {"entities": {}}
        await zug.starten(s, _req(action=zug.AKTION, action_params={"ablauf": "lesen"}), state)
        antwort = await auftrag_zug.pruefen(
            s, _req(action=auftrag_zug.AKTION, action_params={"ablauf": "lesen"}), state)
        auftraege = (await s.execute(text("SELECT status FROM vorgang_auftraege"))).scalars()
        return antwort.content, await _vorgaenge(s), list(auftraege)

    inhalt, [(status, akte)], auftraege = _lauf(welt, ablauf)
    assert inhalt == "Gelesen." and auftraege == ["fertig"]
    assert akte["teile"]["volltext"]["wert"]["outputs"] == {"markdown": "# T"}
    assert akte["lauf"]["status"] == "fertig" and status == "aktiv"     # bleibt offen (M6)


def test_ein_zug_mitten_im_ablage_stapel_laesst_ihn_stehen(welt):
    """Der Stapel ist Teil ``ablage``; dazwischen speichert ein Chat-Zug eine Modul-Antwort, danach
    kommt der Stand einer Datei (Rückruf unter der Sperre) — beides bleibt."""

    async def ablauf(s, _sitzungen):
        entities: dict = {}
        await arbeitsstand.teile_speichern(s, _SID, entities,
                                           [("ablage", "t", {"dateien": 0, "token": "k1"}, "z")])
        block = type("B", (), {"block_id": "frei0001"})()
        assert await arbeitsstand.uebernehmen(s, _SID, entities, _geprueft(block, "erfasst"))

        async def neu():
            stapel = await arbeitsstand.teil_lader(s, _SID, entities)("ablage")
            return [("ablage", "t", {**stapel, "dateien": stapel["dateien"] + 1}, "z")]

        ok = await arbeitsstand.teile_speichern(s, _SID, entities, [], neu=neu, nur_dieser=True)
        return ok, await _vorgaenge(s)

    ok, [(_status, akte)] = _lauf(welt, ablauf)
    assert ok is True and set(akte["teile"]) == {"ablage", "structure"}
    assert akte["teile"]["ablage"]["wert"] == {"dateien": 1, "token": "k1"}


def test_vorgaenge_der_person_bleiben_unter_der_grenze(welt):
    async def ablauf(s, _sitzungen):
        state: dict = {"entities": {}}
        for _ in range(vorgaenge.MAX_JE_PERSON + 2):
            await zug.starten(s, _req(action=zug.AKTION, action_params={"ablauf": "lesen"}), state)
            await zug.starten(s, _req(action=zug.AKTION,
                                      action_params={"ablauf": "sammlungsstruktur"}), state)
        return await _vorgaenge(s)

    alle = _lauf(welt, ablauf)
    assert len(alle) == vorgaenge.MAX_JE_PERSON
    assert [st for st, _ in alle].count("wartet_person") == 1


def test_verdraengte_vorgaenge_nehmen_ihre_auftraege_mit(welt):
    """Review Q4, Befund 6: die Kaskade auf ``vorgang_auftraege`` beim Verdrängen."""

    async def ablauf(s, _sitzungen):
        state: dict = {"entities": {}}
        for _ in range(vorgaenge.MAX_JE_PERSON + 2):
            await zug.starten(s, _req(action=zug.AKTION, action_params={"ablauf": "lesen"}), state)
            await zug.starten(s, _req(action=zug.AKTION,
                                      action_params={"ablauf": "sammlungsstruktur"}), state)
        waisen = await s.execute(text(
            "SELECT count(*) FROM vorgang_auftraege a "
            "WHERE NOT EXISTS (SELECT 1 FROM vorgaenge v WHERE v.id = a.vorgang_id)"))
        alle = await s.execute(text("SELECT count(*) FROM vorgang_auftraege"))
        return waisen.scalar_one(), alle.scalar_one()

    waisen, alle = _lauf(welt, ablauf)
    assert waisen == 0 and alle <= vorgaenge.MAX_JE_PERSON


def test_zwei_schreiber_zugleich_verlieren_keinen_stand(welt):
    """Review Q4, Befund 6: zwei Sitzungen rechnen denselben Stapel zugleich neu — beide Schritte
    zählen. Das sichert die Zeilensperre (``vorgaenge.sperren``): der zweite Schreiber wartet am
    ``FOR UPDATE``; die Wiederholung nach einem Konflikt allein reichte nicht (``_speichern`` liest
    neu, die Versionsprüfung deckt das Lesen in ``neu()`` nicht)."""

    async def ablauf(s, sitzungen):
        entities: dict = {}
        await arbeitsstand.teile_speichern(s, _SID, entities, [("ablage", "t", {"n": 0}, "z")])

        async def schreiber():
            async with sitzungen() as eigene:
                eigen = dict(entities)

                async def neu():
                    stapel = await arbeitsstand.teil_lader(eigene, _SID, eigen)("ablage")
                    await asyncio.sleep(0.05)   # ohne Sperre läsen beide, bevor einer schreibt
                    return [("ablage", "t", {"n": stapel["n"] + 1}, "z")]

                return await arbeitsstand.teile_speichern(eigene, _SID, eigen, [], neu=neu,
                                                          nur_dieser=True)

        ergebnisse = await asyncio.gather(schreiber(), schreiber())
        [(_status, akte)] = await _vorgaenge(s)
        return ergebnisse, akte["teile"]["ablage"]["wert"]

    ergebnisse, wert = _lauf(welt, ablauf)
    assert ergebnisse == [True, True] and wert == {"n": 2}
