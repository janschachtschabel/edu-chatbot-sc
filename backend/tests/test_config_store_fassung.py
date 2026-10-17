"""Paket 12, W3: der Store kennt Werks-Prüfsumme, stillgelegte eigene Fassung und gelöschte
Werksbereiche. Gegen die Compose-Postgres (Wegwerf-Datenbank)."""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.config_conflict import ConfigConflict
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_w3_store_test"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _lauf(db: str, szenario):
    from boerdi.db.session import make_engine
    from boerdi.services.config_store import ConfigStore
    from boerdi.settings import Settings

    async def mit_store():
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))
        try:
            return await szenario(ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(db)))
        finally:
            await engine.dispose()

    return asyncio.run(mit_store())


def test_sammelschreiben_setzt_die_werks_pruefsumme_und_einfaches_schreiben_behaelt_sie(test_db):
    async def szenario(store):
        await store.put_many({"t/a": {"x": 1}}, updated_by="seed", werk_hashes={"t/a": "h1"})
        nach_seed = await store.fassung("t/a")
        await store.put("t/a", {"x": 2}, updated_by="studio")
        return nach_seed, await store.fassung("t/a")

    nach_seed, nach_studio = _lauf(test_db, szenario)
    assert nach_seed["werk_hash"] == "h1"
    assert nach_studio["werk_hash"] == "h1"  # Basis bleibt, die Anpassung ist eigen
    assert nach_studio["data"] == {"x": 2}


def test_loeschen_vermerkt_nur_werksbereiche_und_schreiben_traegt_aus(test_db):
    """Review #7: ein Bereich ohne Werksbasis (im Studio angelegt) bekommt keinen Vermerk —
    sonst käme ein später ausgelieferter Werksbereich gleichen Namens nie an."""
    async def szenario(store):
        await store.put_many({"t/b": {"x": 1}}, werk_hashes={"t/b": "hb"})
        await store.put("t/b-eigen", {"x": 1})
        await store.delete("t/b")
        await store.delete("t/b-eigen")
        nach_loeschen = await store.entfernte()
        await store.put_many({"t/c": {}}, delete=["t/c2"])  # Löschen eines Fehlenden: kein Vermerk
        await store.put("t/b", {"x": 1})
        return nach_loeschen, await store.entfernte()

    nach_loeschen, nach_schreiben = _lauf(test_db, szenario)
    assert "t/b" in nach_loeschen and "t/b-eigen" not in nach_loeschen
    assert "t/b" not in nach_schreiben and "t/c2" not in nach_schreiben


def test_umschalten_ist_bedingt_und_legt_die_eigene_fassung_still(test_db):
    from boerdi.services.werkfassung import Fassung

    async def szenario(store):
        v = await store.put("t/d", {"eigen": True})
        v2 = await store.umschalten(
            "t/d", Fassung({"werk": True}, "hw", {"eigen": True}, "h-alt"),
            expected_version=v, updated_by="werkfassung")
        mitte = await store.fassung("t/d")
        with pytest.raises(ConfigConflict):
            await store.umschalten("t/d", Fassung({"eigen": True}, "h-alt", None, None),
                                   expected_version=v, updated_by="x")
        await store.umschalten("t/d", Fassung({"eigen": True}, "h-alt", None, None),
                               expected_version=v2, updated_by="eigene-fassung")
        verlauf = [h["updated_by"] for h in await store.history("t/d")]
        return mitte, await store.fassung("t/d"), verlauf

    mitte, ende, verlauf = _lauf(test_db, szenario)
    assert mitte["data"] == {"werk": True} and mitte["eigene_fassung"] == {"eigen": True}
    assert mitte["werk_hash"] == "hw" and mitte["eigene_basis"] == "h-alt"
    assert ende["data"] == {"eigen": True} and ende["eigene_fassung"] is None
    assert ende["werk_hash"] == "h-alt"
    assert verlauf[:2] == ["eigene-fassung", "werkfassung"]


def test_werk_schreiben_ist_bedingt(test_db):
    """Review #2/#5: der Werksabgleich schreibt nur, was er gelesen hat — eine Studio-Änderung
    oder ein Löschen dazwischen gewinnt."""
    async def szenario(store):
        v = await store.put("t/w1", {"alt": True})
        await store.put("t/w1", {"studio": True}, updated_by="studio")  # dazwischen gespeichert
        await store.put_many({"t/w2": {"x": 1}}, werk_hashes={"t/w2": "h2"})
        await store.delete("t/w2")                                        # dazwischen gelöscht
        await store.put("t/w4", {"da": True})
        geschrieben = await store.werk_schreiben({
            "t/w1": ({"werk": True}, "hw1", v, None),       # Version veraltet → übersprungen
            "t/w2": ({"werk": True}, "hw2", None, None),    # gelöscht → übersprungen
            "t/w3": ({"werk": True}, "hw3", None, None),    # fehlt → angelegt
            "t/w4": ({"werk": True}, "hw4", None, None),    # inzwischen angelegt → übersprungen
        }, updated_by="werksabgleich")
        wieder = await store.werk_schreiben({"t/w2": ({"werk": True}, "hw2", None, None)},
                                            updated_by="werkfassung", trotz_entfernt=True)
        return (geschrieben, wieder, await store.fassung("t/w1"), await store.fassung("t/w3"),
                await store.fassung("t/w4"), await store.entfernte())

    geschrieben, wieder, w1, w3, w4, entfernt = _lauf(test_db, szenario)
    assert sorted(geschrieben) == ["t/w3"]
    assert w1["data"] == {"studio": True}
    assert w3["data"] == {"werk": True} and w3["werk_hash"] == "hw3"
    assert w4["data"] == {"da": True}
    assert list(wieder) == ["t/w2"] and "t/w2" not in entfernt


def test_fassungen_listet_alle_bereiche_mit_metadaten(test_db):
    async def szenario(store):
        await store.put_many({"t/e": {"y": 1}}, werk_hashes={"t/e": "he"})
        return {z["area"]: z for z in await store.fassungen()}

    zeilen = _lauf(test_db, szenario)
    assert zeilen["t/e"]["werk_hash"] == "he"
    assert zeilen["t/e"]["data"] == {"y": 1}
    assert zeilen["t/e"]["hat_eigene_fassung"] is False
    assert zeilen["t/e"]["updated_by"] == ""


def test_stillgelegte_eigene_fassung_wird_nie_mitgeloescht(test_db):
    """Review 2 #1: Löschen nahm die stillgelegte Fassung mit — sie steht in keinem
    Schnappschuss."""
    from boerdi.services.config_store import EigeneFassungLiegtStill
    from boerdi.services.werkfassung import Fassung

    async def szenario(store):
        v = await store.put("t/s1", {"eigen": 1})
        await store.umschalten("t/s1", Fassung({"werk": 1}, "hw", {"eigen": 1}, None),
                               expected_version=v, updated_by="werkfassung")
        with pytest.raises(EigeneFassungLiegtStill):
            await store.delete("t/s1")
        await store.put_many({}, delete=["t/s1"])
        return await store.fassung("t/s1")

    zeile = _lauf(test_db, szenario)
    assert zeile is not None and zeile["eigene_fassung"] == {"eigen": 1}


def test_werksbereich_ohne_basis_bekommt_beim_loeschen_den_vermerk(test_db):
    """Review 2 #2: vor 0011 angepasste Werksbereiche haben keine Basis — der Aufrufer weiß, dass
    es ein Werksbereich ist, sonst legte der nächste Start ihn wieder an."""
    async def szenario(store):
        await store.put("t/alt1", {"x": 1}, updated_by="studio")
        await store.put("t/alt2", {"x": 1}, updated_by="studio")
        await store.delete("t/alt1", werksbereich=True)
        await store.put_many({}, delete=["t/alt2"], werk_bereiche={"t/alt2"})
        return await store.entfernte()

    entfernt = _lauf(test_db, szenario)
    assert {"t/alt1", "t/alt2"} <= entfernt


def test_werk_schreiben_legt_den_alten_inhalt_still_ohne_eine_vorhandene_zu_verdraengen(test_db):
    """Review 2 #4: beim Anheben über die Import-Kennung wird der alte Inhalt stillgelegt — eine
    schon stillgelegte Fassung bleibt dabei unangetastet."""
    from boerdi.services.werkfassung import Fassung

    async def szenario(store):
        v1 = await store.put("t/p1", {"alt": 1}, updated_by="import")
        await store.werk_schreiben({"t/p1": ({"werk": 1}, "hw", v1, {"alt": 1})},
                                   updated_by="werksabgleich")
        v2 = await store.put("t/p2", {"eigen": 1})
        v2 = await store.umschalten("t/p2", Fassung({"zwischen": 1}, None, {"eigen": 1}, None),
                                    expected_version=v2, updated_by="x")
        await store.werk_schreiben({"t/p2": ({"werk": 2}, "hw2", v2, {"zwischen": 1})},
                                   updated_by="werksabgleich")
        return await store.fassung("t/p1"), await store.fassung("t/p2")

    p1, p2 = _lauf(test_db, szenario)
    assert p1["data"] == {"werk": 1} and p1["eigene_fassung"] == {"alt": 1}
    assert p2["eigene_fassung"] == {"eigen": 1}
