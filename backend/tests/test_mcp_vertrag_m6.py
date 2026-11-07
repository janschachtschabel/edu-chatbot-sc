"""Paket M6 (Plan 2026-11-07): die eigenen letzten Ablagen (``wlo_list_my_batches``, T1b).

Ohne Modell: ``vorbereiten`` bringt sie neben der Vorschau mit, damit dieselbe Auswahl nicht zweimal
im persönlichen Bereich landet. Nur Titel, Datum und Zahlen — keine Kennungen; nur mit bestätigter
Anmeldung; eine Liste, die nicht kommt, hält die Vorbereitung nicht auf.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.ablage import mcp_ablage
from tests.test_ablage_mcp import _ok, mcp  # noqa: F401 — Fixture
from tests.test_ui_ablage_api import _umgebung, _vorbereiten, client, lage  # noqa: F401

_ABLAGEN = {"batches": [
    {"manifestNodeId": "m-1", "folderNodeId": "f-1", "title": "Physik  7", "status": "ok",
     "createdAt": "2026-11-06T10:15:00.000Z",
     "counts": {"stored": 30, "dropped": 1, "unverified": 0, "failed": 2, "open": 3}},
    {"manifestNodeId": "m-2", "folderNodeId": None, "title": "Chemie", "status": "unreadable",
     "createdAt": "2026-11-05T08:00:00.000Z"},
], "scanTruncated": True}


def test_die_letzten_ablagen_ohne_kennungen(mcp):  # noqa: F811
    mcp["antworten"]["wlo_list_my_batches"] = _ok(_ABLAGEN)
    daten = asyncio.run(mcp_ablage.letzte_ablagen())
    assert mcp["gerufen"] == [("wlo_list_my_batches", {"limit": 5})]
    assert daten == {"gekappt": True, "ablagen": [
        {"titel": "Physik 7", "datum": "2026-11-06T10:15:00.000Z", "lesbar": True,
         "stored": 30, "dropped": 1, "unverified": 0, "failed": 2, "open": 3},
        {"titel": "Chemie", "datum": "2026-11-05T08:00:00.000Z", "lesbar": False},
    ]}
    assert "m-1" not in str(daten) and "f-1" not in str(daten)


def test_ohne_anmeldung_keine_liste(mcp, monkeypatch):  # noqa: F811
    monkeypatch.setattr(mcp_ablage, "has_personal_auth", lambda: False)
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.letzte_ablagen())
    assert fehler.value.code == "nur_angemeldet" and mcp["gerufen"] == []


def test_das_werkzeug_steht_in_keinem_angebot_an_die_ki():
    assert "wlo_list_my_batches" in mcp_ablage.WERKZEUGE


def test_vorbereiten_bringt_die_letzten_ablagen_mit(client, lage, monkeypatch):  # noqa: F811
    async def letzte():
        return {"ablagen": [{"titel": "Physik 7", "datum": "2026-11-06T10:15:00Z",
                             "lesbar": False}], "gekappt": False}

    monkeypatch.setattr(mcp_ablage, "letzte_ablagen", letzte)
    r = _vorbereiten(client)
    assert r.status_code == 200, r.text
    assert r.json()["letzte"]["ablagen"][0]["titel"] == "Physik 7"


def test_eine_fehlende_liste_haelt_die_vorbereitung_nicht_auf(client, lage, monkeypatch):  # noqa: F811
    async def kaputt():
        raise mcp_ablage.AblageFehler("abgewiesen")

    monkeypatch.setattr(mcp_ablage, "letzte_ablagen", kaputt)
    r = _vorbereiten(client)
    assert r.status_code == 200, r.text
    assert r.json()["letzte"] == {"ablagen": [], "gekappt": False}


def test_eine_haengende_liste_haelt_die_vorbereitung_nicht_auf(client, lage, monkeypatch):  # noqa: F811
    """Review M6 (Befund 1): nach der Freigabe bekommt die Liste nur noch eine kurze Restfrist."""
    import boerdi.api.ui_ablage as api

    async def haengt():
        await asyncio.sleep(30)

    monkeypatch.setattr(api, "_LETZTE_REST_S", 0.05)
    monkeypatch.setattr(mcp_ablage, "letzte_ablagen", haengt)
    r = _vorbereiten(client)
    assert r.status_code == 200, r.text
    assert r.json()["letzte"] == {"ablagen": [], "gekappt": False}
