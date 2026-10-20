"""Gesamt-Review Paket 17 (C2): beim Herunterfahren beendet ein Pod seine Läufe ehrlich.

Uvicorn schließt auf SIGTERM zuerst die Annahme. Ein Eval-Lauf ruft den Chat über die
Loopback-Adresse und sammelte bis zum Ende der Gnadenfrist nur Verbindungsfehler — der Lauf
endete womöglich als „done“ mit falscher Quote. Der Hauptserver ruft deshalb zu Beginn seines
Herunterfahrens den Abschluss der Läufe auf, bevor er die Annahme schließt.
"""

from __future__ import annotations

import pytest
import uvicorn
from fastapi import FastAPI

from boerdi import serve


@pytest.mark.asyncio
async def test_der_hauptserver_beendet_die_laeufe_vor_dem_herunterfahren(monkeypatch) -> None:
    folge: list[str] = []

    async def _uvicorn_shutdown(self, sockets=None):
        folge.append("annahme zu")

    monkeypatch.setattr(uvicorn.Server, "shutdown", _uvicorn_shutdown)
    haupt, _intern = serve.baue_server(FastAPI(), FastAPI())

    async def _laeufe():
        folge.append("laeufe beendet")

    haupt.bei_ende = _laeufe
    await haupt.shutdown()
    assert folge == ["laeufe beendet", "annahme zu"]


@pytest.mark.asyncio
async def test_ein_fehler_beim_abschluss_haelt_das_herunterfahren_nicht_auf(monkeypatch) -> None:
    folge: list[str] = []

    async def _uvicorn_shutdown(self, sockets=None):
        folge.append("annahme zu")

    monkeypatch.setattr(uvicorn.Server, "shutdown", _uvicorn_shutdown)
    haupt, _intern = serve.baue_server(FastAPI(), FastAPI())

    async def _kaputt():
        raise RuntimeError("Datenbank weg")

    haupt.bei_ende = _kaputt
    await haupt.shutdown()
    assert folge == ["annahme zu"]


def test_der_einstieg_verdrahtet_den_abschluss(monkeypatch) -> None:
    gefangen: dict = {}

    async def _laufen(haupt, intern):
        gefangen["haupt"] = haupt

    monkeypatch.setattr(serve, "laufen", _laufen)
    serve.main()
    assert gefangen["haupt"].bei_ende is not None


@pytest.mark.asyncio
async def test_ohne_datenbank_gibt_es_nichts_abzuschliessen() -> None:
    """Fehlstart: der Lebenszyklus hat keine Engine hinterlegt."""
    await serve.laeufe_der_app_beenden(FastAPI())
