"""Paket K9 (Plan 2026-11-17): der Flow-Katalog im Studio.

Das Studio hat keine Person (keinen Zugangsblock) — die Flow-Liste kommt weiter über ``B_API_KEY``
(``wlo_list_flows`` des MCP bräuchte eine Anmeldung). Ohne Schlüssel der Anlage schlägt der Katalog
die Werksvorgabe (``client.WERKSVORGABE``) vor, dazu bleibt die freie Eingabe; die Obergrenze
``B_API_JOBS_FLOWS`` gilt auch dann. Welche Flows der MCP wirklich startet, legt dort
``WLO_BAPI_FLOWS`` fest (Hinweis im Studio-Katalog).
"""

from __future__ import annotations

import asyncio

from boerdi.services.auftraege import client, flow_katalog
from boerdi.settings import get_settings
from tests.test_kf_kestra_flows import _bapi, umgebung  # noqa: F401 — Fixture

_WERK = sorted(client.WERKSVORGABE)


def _ohne_schluessel(monkeypatch):
    monkeypatch.setenv("B_API_KEY", "")
    get_settings.cache_clear()


def test_ohne_schluessel_die_werksvorgabe_ohne_abruf(umgebung, monkeypatch):  # noqa: F811
    _ohne_schluessel(monkeypatch)
    gesehen = _bapi(monkeypatch)
    assert [w for w, _ in asyncio.run(flow_katalog.vorschlaege())] == _WERK
    assert gesehen == []


def test_ohne_schluessel_dazu_die_freigegebenen(umgebung, monkeypatch):  # noqa: F811
    _ohne_schluessel(monkeypatch)
    umgebung.append("wlo/volltext")
    _bapi(monkeypatch)
    assert [w for w, _ in asyncio.run(flow_katalog.vorschlaege())] == [*_WERK, "wlo/volltext"]


def test_ohne_schluessel_gilt_die_obergrenze(umgebung, monkeypatch):  # noqa: F811
    _ohne_schluessel(monkeypatch)
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    _bapi(monkeypatch)
    assert asyncio.run(flow_katalog.vorschlaege()) == []


def test_mit_schluessel_bleibt_es_bei_der_liste_der_bapi(umgebung, monkeypatch):  # noqa: F811
    _bapi(monkeypatch, [{"namespace": "wlo", "flowId": "volltext", "active": True}])
    assert [w for w, _ in asyncio.run(flow_katalog.vorschlaege())] == ["wlo/volltext"]
