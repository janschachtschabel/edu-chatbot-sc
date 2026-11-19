"""Paket K, Review-Befunde vom 19.11. an ``POST /api/ui/auftrag/stand`` (A1, B6). Ohne Postgres."""

from __future__ import annotations

import json
from types import SimpleNamespace

from boerdi.services.auftraege import client, mcp_starter
from tests.test_ui_auftrag_api import _stand, _umgebung, lage, web  # noqa: F401 — Fixtures


def test_a1_stand_mit_offener_kennung_antwortet_409_ohne_abfrage(web, lage, monkeypatch):  # noqa: F811
    offen = mcp_starter.offene_kennung()
    lage.auftrag = SimpleNamespace(job_id=offen, schritt="lesen", status="laeuft")
    gefragt: list = []

    async def stand(job_id):
        gefragt.append(job_id)
        raise client.AuftragFehler("job_unbekannt")

    monkeypatch.setattr(mcp_starter, "stand", stand)
    r = _stand(web, kuerzel=client.kuerzel(offen))
    assert r.status_code == 409 and r.json()["detail"] == "kein_auftrag"
    assert gefragt == [] and lage.abfragen == []


def test_b6_das_antwortmodell_steht_im_vertrag(web):  # noqa: F811
    schema = web.app.openapi()
    antwort = schema["paths"]["/api/ui/auftrag/stand"]["post"]["responses"]["200"]
    ref = antwort["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    modell = schema["components"]["schemas"][ref]
    assert modell["properties"]["stand"]["enum"] == ["laeuft", "fertig", "fehler"]
    assert modell["required"] == ["stand"]
    for feld in ("fertig", "gesamt"):
        assert {"type": "integer", "minimum": 0} in modell["properties"][feld]["anyOf"]


def test_b6_ohne_zahlen_bleibt_die_antwort_ohne_null(web, lage):  # noqa: F811
    lage.stand = client.Stand("laeuft")
    r = _stand(web)
    assert r.json() == {"stand": "laeuft"} and "null" not in r.text
    assert json.loads(r.text) == {"stand": "laeuft"}
