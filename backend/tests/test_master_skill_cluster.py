"""Paket 17 (C3): der Master-Skill bei mehreren Repliken — gegen echtes Postgres.

Bis Paket 17 holte jede Kopie im eigenen Takt (alle 5 min) und hielt ihren Stand allein:
N Kopien fragten N-mal ab, „Neu laden“ im Studio wirkte nur auf der Kopie, die die Anfrage
traf, und zwei Kopien konnten verschiedene Fassungen in den Prompt legen (dann trifft der
Prompt-Cache des Anbieters nicht). Seither steht der Stand in einer DB-Zeile; geholt wird nur
unter der Cluster-Sperre ``__lauf:master-skill``, die übrigen übernehmen die Zeile — sofort
über das NOTIFY-Signal, spätestens im eigenen Takt.

Eine „Kopie“ ist hier derselbe Prozess mit geleertem Speicher: der Stand einer Kopie lebt nur
im Speicher des Moduls, die gemeinsame Wahrheit in der Datenbank.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest
from sqlalchemy import text

from boerdi.services import master_skill, master_skill_stand
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p17_master_skill_test"
_KENNUNG = "knoten-1"


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


@pytest.fixture(autouse=True)
def _sauber(monkeypatch):
    from boerdi.settings import get_settings

    monkeypatch.setenv("MASTER_SKILL_ENABLED", "true")
    monkeypatch.setenv("MASTER_SKILL_NODE_ID", _KENNUNG)
    get_settings.cache_clear()
    master_skill.leere_den_zwischenspeicher()
    yield
    master_skill.binde(None)
    master_skill.leere_den_zwischenspeicher()
    get_settings.cache_clear()


def _mcp(monkeypatch, *antworten: str) -> list[str]:
    """``get_skill`` liefert der Reihe nach ``antworten``; die Liste zählt die Abrufe."""
    aufrufe: list[str] = []
    folge = iter(antworten)

    async def _fake(name, args, **_kw):
        aufrufe.append(name)
        return next(folge)

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)
    return aufrufe


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _lauf(fn):
    """``fn(engine)`` gegen eine leere Stand-Tabelle, die Engine an den Master-Skill gebunden."""
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    async def szenario():
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))
        try:
            async with engine.begin() as conn:
                await conn.execute(text("TRUNCATE master_skill_stand"))
                await conn.execute(text("DELETE FROM session_locks"))
            master_skill.binde(engine)
            return await fn(engine)
        finally:
            master_skill.binde(None)
            await engine.dispose()

    return asyncio.run(szenario())


async def _altere_den_stand(engine, sekunden: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            "UPDATE master_skill_stand SET geprueft_um = now() - make_interval(secs => :s)"),
            {"s": sekunden})


def test_im_takt_holt_nur_eine_kopie(test_db, monkeypatch) -> None:
    aufrufe = _mcp(monkeypatch, "# A\n\nv1", "# B\n\nv2")

    async def szenario(engine):
        await master_skill.auffrischen()          # Kopie 1 holt und teilt
        master_skill.leere_den_zwischenspeicher()  # Kopie 2: eigener, leerer Speicher
        await master_skill.auffrischen()          # Stand ist frisch → übernehmen
        return master_skill.zustand()

    zustand = _lauf(szenario)
    assert aufrufe == ["get_skill"]
    assert zustand["sha256"] == _sha("# A\n\nv1")
    assert zustand["fetched_at"] is not None


def test_ein_alter_stand_wird_im_takt_neu_geholt(test_db, monkeypatch) -> None:
    aufrufe = _mcp(monkeypatch, "# A\n\nv1", "# B\n\nv2")

    async def szenario(engine):
        await master_skill.auffrischen()
        await _altere_den_stand(engine, int(master_skill.TAKT_S))
        master_skill.leere_den_zwischenspeicher()
        await master_skill.auffrischen()
        return master_skill.zustand()["sha256"]

    assert _lauf(szenario) == _sha("# B\n\nv2")
    assert len(aufrufe) == 2


def test_haelt_eine_andere_kopie_die_sperre_holt_diese_nicht(test_db, monkeypatch) -> None:
    from boerdi.services.sitzungssperre import sitzungssperre

    aufrufe = _mcp(monkeypatch, "# A\n\nv1", "# B\n\nv2")

    async def szenario(engine):
        await master_skill.auffrischen()
        await _altere_den_stand(engine, int(master_skill.TAKT_S))
        master_skill.leere_den_zwischenspeicher()
        async with sitzungssperre(engine, master_skill_stand.SPERRE, warten_s=0.0):
            await master_skill.auffrischen()  # die andere Kopie holt gerade
        return master_skill.zustand()["sha256"]

    # Übernimmt den letzten Stand der Zeile, statt selbst abzufragen.
    assert _lauf(szenario) == _sha("# A\n\nv1")
    assert len(aufrufe) == 1


def test_nach_neu_laden_sehen_beide_kopien_denselben_stand(test_db, monkeypatch) -> None:
    _mcp(monkeypatch, "# A\n\nv1", "# B\n\nv2")

    async def szenario(engine):
        await master_skill.auffrischen()                # beide auf v1
        kopie2_vorher = master_skill.zustand()["sha256"]
        await master_skill.neu_laden()                  # Studio trifft Kopie 1
        kopie1 = master_skill.zustand()["sha256"]
        master_skill.leere_den_zwischenspeicher()       # Kopie 2 …
        await master_skill.uebernimm_stand()            # … bekommt das Signal
        return kopie2_vorher, kopie1, master_skill.zustand()["sha256"]

    vorher, kopie1, kopie2 = _lauf(szenario)
    assert vorher == _sha("# A\n\nv1")
    assert kopie1 == kopie2 == _sha("# B\n\nv2")


def test_neu_laden_sendet_das_signal(test_db, monkeypatch) -> None:
    import asyncpg

    _mcp(monkeypatch, "# A\n\nv1")

    async def szenario(engine):
        empfangen: asyncio.Queue[str] = asyncio.Queue()
        conn = await asyncpg.connect(pg_utils.asyncpg_dsn(_DB))
        try:
            await conn.add_listener("config_changed", lambda *a: empfangen.put_nowait(a[3]))
            await master_skill.neu_laden()
            return await asyncio.wait_for(empfangen.get(), 5)
        finally:
            await conn.close()

    assert _lauf(szenario) == master_skill_stand.SIGNAL


def test_der_erste_zug_einer_frischen_kopie_liest_die_zeile(test_db, monkeypatch) -> None:
    """Ein frischer Pod wartet nicht auf das Repositorium, wenn der Stand schon geteilt ist."""
    aufrufe = _mcp(monkeypatch, "# A\n\nv1")

    async def szenario(engine):
        await master_skill.auffrischen()
        master_skill.leere_den_zwischenspeicher()
        return await master_skill.prompt_block(None)

    block = _lauf(szenario)
    assert block is not None and "v1" in block
    assert len(aufrufe) == 1


def test_eine_geloeschte_anleitung_verschwindet_ueberall(test_db, monkeypatch) -> None:
    _mcp(monkeypatch, "# A\n\nv1", f"Skill {_KENNUNG} ist nicht abrufbar.")

    async def szenario(engine):
        await master_skill.auffrischen()
        await master_skill.neu_laden()                  # Server: keine Anleitung mehr
        master_skill.leere_den_zwischenspeicher()
        await master_skill.auffrischen()                # Kopie 2 übernimmt die leere Zeile
        return master_skill.zustand()

    zustand = _lauf(szenario)
    assert zustand["cached"] is False
    assert "keine Anleitung" in (zustand["last_error"] or "")


def test_ein_gescheiterter_abruf_behaelt_den_geteilten_stand(test_db, monkeypatch) -> None:
    folge = iter(["# A\n\nv1", RuntimeError("MCP weg")])

    async def _fake(name, args, **_kw):
        antwort = next(folge)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)

    async def szenario(engine):
        await master_skill.auffrischen()
        await master_skill.neu_laden()
        master_skill.leere_den_zwischenspeicher()
        await master_skill.uebernimm_stand()
        return master_skill.zustand()

    zustand = _lauf(szenario)
    assert zustand["sha256"] == _sha("# A\n\nv1")
    assert "MCP weg" in (zustand["last_error"] or "")


def test_ein_gescheiterter_abruf_einer_frischen_kopie_loescht_den_stand_nicht(
        test_db, monkeypatch) -> None:
    """Review C, Befund 1: eine frische Kopie (leerer Speicher) holt im Takt, weil die Zeile
    alt ist — und scheitert. Vorher schrieb sie ``text=NULL``, und ihr Signal nahm allen
    Kopien die Anleitung."""
    folge = iter(["# A\n\nv1", RuntimeError("MCP weg")])

    async def _fake(name, args, **_kw):
        antwort = next(folge)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)

    async def szenario(engine):
        await master_skill.auffrischen()                 # Kopie 1: v1, geteilt
        await _altere_den_stand(engine, int(master_skill.TAKT_S))
        master_skill.leere_den_zwischenspeicher()        # Kopie 2, frisch …
        await master_skill.auffrischen()                 # … holt und scheitert
        kopie2 = master_skill.zustand()
        stand = await master_skill_stand.lies(engine, _KENNUNG)
        return kopie2, stand

    kopie2, stand = _lauf(szenario)
    assert stand.text == "# A\n\nv1"
    assert "MCP weg" in (stand.letzter_fehler or "")
    assert kopie2["sha256"] == _sha("# A\n\nv1")


# ── Gesamt-Review Paket 17 ──────────────────────────────────────────────────


def test_ein_takt_waehrend_neu_laden_verliert_den_neuen_text_nicht(test_db, monkeypatch) -> None:
    """C1: ein Takt auf derselben Kopie übernahm mitten im Neu-Laden die alte Zeile; der neue
    Abruf galt danach als „überholt“, und geteilt wurde wieder der alte Text."""
    weiter = asyncio.Event()
    drin = asyncio.Event()
    aufrufe = {"n": 0}

    async def _fake(name, args, **_kw):
        aufrufe["n"] += 1
        if aufrufe["n"] == 1:
            return "# Alt\n\nv1"
        drin.set()
        await weiter.wait()
        return "# Neu\n\nv2"

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)

    async def szenario(engine):
        await master_skill.auffrischen()               # v1, geteilt (Zeile frisch)
        laden = asyncio.create_task(master_skill.neu_laden())
        await drin.wait()
        await master_skill.auffrischen()               # Takt mitten im Abruf: Zeile frisch
        weiter.set()
        await laden
        stand = await master_skill_stand.lies(engine, _KENNUNG)
        return stand.text, master_skill.zustand()["sha256"]

    zeile, sha = _lauf(szenario)
    assert zeile == "# Neu\n\nv2"
    assert sha == _sha("# Neu\n\nv2")


def test_der_abruf_im_zug_laeuft_ohne_die_anmeldung_der_person(test_db, monkeypatch) -> None:
    """C3: der Rückfall-Abruf eines Zugs lief mit dem WLO-Block der Person; ihr Text landete
    im Speicher (und über das Teilen in allen Kopien)."""
    from boerdi.services.mcp import auth

    gesehen: list[str] = []

    async def _fake(name, args, **_kw):
        gesehen.append(auth._turn_block.get())
        return "# A\n\nv1"

    monkeypatch.setattr(master_skill, "call_mcp_tool", _fake)

    async def szenario(engine):
        auth._turn_block.set("wlo2.persoenlicher-block")
        return await master_skill.prompt_block(None)   # leerer Speicher, keine Zeile

    assert _lauf(szenario) is not None
    assert gesehen == [""]
