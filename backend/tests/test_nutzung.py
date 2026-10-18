"""Paket 16, D3: Nutzung im Überblick (``services/nutzung.py``) — aus dem Qualitätsprotokoll.

Gegen die echte Compose-Postgres: Tag, Stunde und Wochentag rechnet die Datenbank in
Europe/Berlin. Kleine Zellen (1 bis 4) kommen als ``None`` zurück — eine Zählung, die einzelne
Besuche erkennbar machte, zeigt die Seite als „<5“.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p16_nutzung"
_VON = datetime(2026, 3, 9, tzinfo=UTC)
_BIS = datetime(2026, 3, 12, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def db():
    pg_utils.create_migrated_db(_DB)
    yield pg_utils.sqlalchemy_url(_DB)
    pg_utils.drop_db(_DB)


def _muster(**extra) -> dict:
    return {"engine": "pattern", "locale": "de", "device": "desktop", "page_type": "themenseite",
            "persona_id": "P-LK", **extra}


# (Sitzung, Zeitpunkt, data, intent_id, Anzahl)
_ZEILEN = [
    # Di 10:15 Berlin (MEZ = UTC+1): fünf Sitzungen mit je einem Zug.
    *[(f"bb-a{i}", datetime(2026, 3, 10, 9, 15, tzinfo=UTC), _muster(), "I01 (Suche)", 1)
      for i in range(5)],
    # Mi 21:00 Berlin
    ("bb-b", datetime(2026, 3, 11, 20, tzinfo=UTC),
     {"engine": "agent", "locale": "en", "device": "mobile", "page_type": ""}, "", 1),
    ("eval-1", datetime(2026, 3, 10, 9, 30, tzinfo=UTC), _muster(), "I01 (Suche)", 1),
    # Vor Paket 16: nur im Debug.
    ("bb-alt", datetime(2026, 3, 12, 8, tzinfo=UTC),
     {"debug": {"engine": "pattern", "context": {"locale": "de"}}}, "", 1),
]


def _lauf(db, **kwargs):
    async def wrapper():
        from sqlalchemy import text

        from boerdi.db.models import QualityLog
        from boerdi.db.session import make_engine, make_session_factory
        from boerdi.services.nutzung import ueberblick
        from boerdi.settings import Settings

        engine = make_engine(Settings(_env_file=None, database_url=db))
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                await s.execute(text("DELETE FROM quality_logs"))
                for sitzung, wann, data, intent, anzahl in _ZEILEN:
                    for _ in range(anzahl):
                        s.add(QualityLog(session_id=sitzung, intent_id=intent, data=data,
                                         created_at=wann))
                await s.commit()
            async with factory() as s:
                return await ueberblick(s, _VON, _BIS, **kwargs)
        finally:
            await engine.dispose()
    return asyncio.run(wrapper())


def test_zuege_sitzungen_und_zuege_je_sitzung(db):
    u = _lauf(db, scope="production")
    assert u["zuege"] == 7 and u["sitzungen"] == 7
    assert u["zuege_je_sitzung"] == {"mittel": 1.0, "median": 1.0}
    assert _lauf(db)["zuege"] == 8                      # „alle“ zählt den Eval-Lauf mit


def test_je_tag_in_berlin_mit_luecken(db):
    tage = _lauf(db, scope="production")["tage"]
    assert tage == [
        {"tag": "2026-03-09", "sitzungen": 0, "zuege": 0},
        {"tag": "2026-03-10", "sitzungen": 5, "zuege": 5},
        {"tag": "2026-03-11", "sitzungen": 1, "zuege": 1},
        {"tag": "2026-03-12", "sitzungen": 1, "zuege": 1},
    ]


def test_wochentag_mal_stunde_mit_kleinen_zellen_als_none(db):
    raster = _lauf(db, scope="production")["raster"]
    assert len(raster) == 7 and all(len(zeile) == 24 for zeile in raster)
    assert raster[1][10] == 5            # Dienstag, 10 Uhr
    assert raster[2][21] is None         # Mittwoch, 21 Uhr: ein Zug → „<5“
    assert raster[0][0] == 0


def test_verteilungen_nach_haeufigkeit_kleine_als_none(db):
    v = _lauf(db, scope="production")["verteilungen"]
    assert v["maschine"] == [{"wert": "pattern", "anzahl": 6}, {"wert": "agent", "anzahl": None}]
    assert v["sprache"] == [{"wert": "de", "anzahl": 6}, {"wert": "en", "anzahl": None}]
    assert v["geraet"][0] == {"wert": "desktop", "anzahl": 5}
    assert v["seitenart"][0] == {"wert": "themenseite", "anzahl": 5}
    # Zielgruppe und Anliegen nur aus Muster-Zügen — die Agent-Schleife setzt sie fest.
    assert v["persona"] == [{"wert": "P-LK", "anzahl": 5}, {"wert": "", "anzahl": None}]
    assert v["anliegen"][0] == {"wert": "I01 (Suche)", "anzahl": 5}


def test_der_maschinen_filter(db):
    u = _lauf(db, scope="production", engine="agent")
    assert u["zuege"] == 1 and u["sitzungen"] == 1
    assert u["klein_unter"] == 5


def test_klein_heisst_wenige_sitzungen_nicht_wenige_zuege(db):
    """Review B-3a: eine einzelne Sitzung mit vielen Zügen bleibt erkennbar, wenn nach Zügen
    abgerundet wird — maßgeblich ist die Zahl der Sitzungen in der Zelle."""
    viel = [("bb-solo", datetime(2026, 3, 9, 2, tzinfo=UTC), _muster(locale="fr"), "", 8)]
    alt, _ZEILEN[:] = list(_ZEILEN), viel
    try:
        u = _lauf(db, scope="production")
    finally:
        _ZEILEN[:] = alt
    assert u["zuege"] == 8                              # die Summe bleibt genau
    assert u["raster"][0][3] is None                    # Mo 03:00 Berlin, eine Sitzung
    assert u["verteilungen"]["sprache"] == [{"wert": "fr", "anzahl": None}]

