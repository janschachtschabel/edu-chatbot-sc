"""Plan 2026-11-19, Paket B4: der Anzeigename in einem echten Zug — nur in der Antwort.

Ein Zug mit persönlichem Block über ``POST /api/chat`` (Muster und Agent) und den Strom. Der
MCP-Server nennt für den Block einen Namen mit Markierwort; geprüft wird, wohin er gelangt:

* in die Antwort des Zuges (``auth_display_name``) — genau einmal;
* **nicht** in die Datenbank (jede Tabelle, jede Zeile als Text), nicht in den Verlauf
  (``GET /api/sessions/{id}/messages``), nicht ins Log (Mitschnitt wie beim Kanarienvogel), nicht
  an das Modell oder den Klassifikator (jeder Aufruf mitgeschnitten).

Welt, Attrappen und Mitschnitt stammen aus ``test_kanarienvogel_logs.py``; die Datenbank ist
eine eigene Wegwerf-Datenbank.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from boerdi.db.session import make_engine, make_session_factory
from boerdi.services import classify, llm
from boerdi.services.mcp import anmelde_endpunkte, anmeldung
from boerdi.settings import Settings
from tests import pg_utils
from tests import test_kanarienvogel_logs as kanarie

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_anzeigename_test"
_NAME = "Zora Namenkanarie7Q"
_MARKE = "Namenkanarie7Q"
_BLOCK = "wlo2.persoenlich-anzeigename-ende"
_ECHT_FRAGEN = anmeldung._fragen   # conftest ersetzt ``_fragen`` durch „immer Person“

# Welt und Werkskonfiguration des Kanarienvogels; ``welt`` nimmt die Datenbank dieses Moduls.
welt = kanarie.welt
werkskonfiguration = kanarie.werkskonfiguration


@pytest.fixture(scope="module")
def datenbank():
    pg_utils.create_migrated_db(_DB)
    engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
                         poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())
    pg_utils.drop_db(_DB)


@pytest.fixture
def mit_name(monkeypatch, welt):
    """Der MCP-Server bestätigt den Block als Person mit Namen; Modell und Klassifikator werden
    mitgeschnitten (alles, was sie bekommen, als Text)."""
    async def _status(_block, _frist):
        return "ok", {"mode": "user", "authenticated": True, "authority": "zora",
                      "displayName": _NAME, "credential": "access-block", "upstream": "ok"}

    monkeypatch.setattr(anmeldung, "_fragen", _ECHT_FRAGEN)
    monkeypatch.setattr(anmelde_endpunkte, "status_abfragen", _status)
    anmeldung._cache.clear()
    gesehen: list[str] = []

    def _spion(echt):
        async def aufruf(**kw: Any) -> Any:
            gesehen.append(json.dumps(kw, default=str, ensure_ascii=False))
            return await echt(**kw)
        return aufruf

    monkeypatch.setattr(llm, "_acompletion", _spion(welt.modell))
    monkeypatch.setattr(classify, "_acreate", _spion(welt.klassifikator))
    yield gesehen
    anmeldung._cache.clear()


def _alle_zeilen(engine) -> dict[str, str]:
    """Jede Tabelle des Schemas ``public`` als Text — wo stünde der Name, wenn irgendwo?"""
    async def lesen() -> dict[str, str]:
        async with engine.connect() as conn:
            tabellen = (await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"))).scalars().all()
            inhalt = {}
            for tabelle in tabellen:
                zeilen = await conn.execute(text(f'SELECT CAST(t AS text) FROM "{tabelle}" t'))
                inhalt[tabelle] = "\n".join(zeilen.scalars().all())
            return inhalt
    return asyncio.run(lesen())


def _pruefe_nur_in_der_antwort(welt, antwort: dict, eintraege, gesehen: list[str],
                               sid: str) -> None:
    assert antwort["auth_display_name"] == _NAME
    assert json.dumps(antwort, ensure_ascii=False).count(_MARKE) == 1, "nur im einen Feld"
    assert gesehen, "Modell bzw. Klassifikator wurden gerufen"
    assert not [g for g in gesehen if _MARKE in g], "an das Modell"
    assert not [e.text for e in eintraege if _MARKE in e.text], "ins Log"
    tabellen = _alle_zeilen(welt.engine)
    assert any(sid in zeilen for zeilen in tabellen.values()), "der Zug ist gespeichert"
    assert not [name for name, zeilen in tabellen.items() if _MARKE in zeilen], "in die DB"
    verlauf = welt.client.get(f"/api/sessions/{sid}/messages")
    assert verlauf.status_code == 200, verlauf.text
    assert _MARKE not in verlauf.text, "in den Verlauf"


@pytest.mark.parametrize("engine", ["pattern", "agent"])
def test_der_name_steht_nur_in_der_antwort_des_zuges(welt, mit_name, engine):
    if engine == "pattern":
        welt.klassifikator.ergebnis = kanarie._suche_klassifiziert()
    sid = f"bb-anzeigename-{engine}"
    with kanarie._mitschnitt() as eintraege:
        antwort = welt.client.post(
            "/api/chat", headers={"X-Boerdi-Engine": engine, "WLO-Access-Block": _BLOCK},
            json={"session_id": sid, "message": "Zeig mir Arbeitsblätter zur Optik",
                  "environment": dict(kanarie._UMGEBUNG)})
    assert antwort.status_code == 200, antwort.text
    _pruefe_nur_in_der_antwort(welt, antwort.json(), eintraege, mit_name, sid)


def test_im_strom_ebenso(welt, mit_name, monkeypatch):
    sid = "bb-anzeigename-strom"
    # Der Strom-Zug öffnet seine eigene Sitzung (Paket 7) — aus derselben Wegwerf-Datenbank.
    monkeypatch.setattr(welt.client.app.state, "session_factory",
                        make_session_factory(welt.engine), raising=False)
    with kanarie._mitschnitt() as eintraege:
        antwort = welt.client.post(
            "/api/chat/stream", headers={"X-Boerdi-Engine": "agent", "WLO-Access-Block": _BLOCK},
            json={"session_id": sid, "message": "Welche Materialien gibt es zur Optik?",
                  "environment": dict(kanarie._UMGEBUNG)})
    assert antwort.status_code == 200, antwort.text
    ergebnis = None
    for rahmen in antwort.text.split("\n\n"):
        zeilen = dict(z.split(": ", 1) for z in rahmen.splitlines() if ": " in z)
        if zeilen.get("event") == "result":
            ergebnis = json.loads(zeilen["data"])
    assert ergebnis is not None, antwort.text[:500]
    _pruefe_nur_in_der_antwort(welt, ergebnis, eintraege, mit_name, sid)


def test_ohne_block_kein_name(welt, mit_name):
    welt.klassifikator.ergebnis = kanarie._suche_klassifiziert()
    antwort = welt.client.post(
        "/api/chat", headers={"X-Boerdi-Engine": "pattern"},
        json={"session_id": "bb-anzeigename-ohne", "message": "Zeig mir Arbeitsblätter zur Optik",
              "environment": dict(kanarie._UMGEBUNG)})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["auth_display_name"] is None
