"""A3b — die HTTP-Grenze des Agenten (``api/agent.py``).

Geprüft wird nur, was der Router selbst verantwortet: dass er hinter dem
Schlüssel liegt, dass der Zugangsblock an der HTTP-Grenze übernommen wird, dass
die Antwortform stimmt und der Strom den Rahmenvertrag einhält. Der Lauf selbst
ist in A3a belegt und hier gefälscht.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from boerdi.api import agent as agent_api
from boerdi.api import ratelimit
from boerdi.api.schemas_agent import AgentResponse
from boerdi.main import create_app
from boerdi.services.mcp import auth
from boerdi.settings import get_settings
from tests import pg_utils

# Der Router hängt an ``create_app``, dessen Start ``config_areas`` liest. Ohne
# migrierte + geseedete Standard-DB kippte die Datei bisher mit 13 Fehlern, die
# nach Code-Fehler aussahen — es fehlte nur die Bereitstellung.
pytestmark = pytest.mark.skipif(
    not pg_utils.dev_db_ready(), reason=pg_utils.DEV_DB_SKIP_REASON)

_ANTWORT = AgentResponse(
    text="Sachlich richtig.", result={"note": 4}, stop_reason="submit",
    iterations=2, tools_called=["get_nodes_details"])


@pytest.fixture(autouse=True)
def _frische_drosselung(monkeypatch):
    """Der Zähler der Drosselung lebt im Modul, also über Tests hinweg.

    Seit der Endpunkt gedrosselt ist (Nutzer-Entscheid 2026-08-12), teilen sich
    alle Tests dieser Datei einen Eimer — ohne Rücksetzen hinge das Ergebnis an
    der Reihenfolge. Muster aus ``test_ratelimit.py``.
    """
    monkeypatch.delenv("RATE_LIMIT_CHAT", raising=False)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def _fake_run(monkeypatch, antwort=_ANTWORT, gesehen=None):
    async def _run(req, *, progress=None, usage_acc=None):
        if gesehen is not None:
            gesehen["req"] = req
            gesehen["personal"] = auth.has_personal_auth()
            if progress is not None:
                progress.record("agent_tool", "Werkzeug: x", {"tool": "x"})
        return antwort
    monkeypatch.setattr(agent_api, "run_agent", _run)


def test_der_endpunkt_traegt_eine_sicherheitsmarke():
    """Kein ``public_router``: ein Lauf kostet ein Dutzend LLM-Runden und darf
    schreiben. Der Wächter prüft die Marke, nicht nur die Erreichbarkeit.

    Seit dem Nutzer-Entscheid 2026-08-12 ist der Studio-Schlüssel nicht mehr der
    einzige Weg herein (siehe „Wer darf rufen" unten) — die Marke bleibt aber,
    denn ohne Anmeldung kommt nach wie vor niemand durch.
    """
    from boerdi.main import create_app as _app
    spec = _app().openapi()
    for pfad in ("/api/agent", "/api/agent/stream"):
        assert spec["paths"][pfad]["post"].get("security"), (
            f"{pfad} traegt keine Sicherheitsmarke — waere oeffentlich")


def test_post_gibt_text_und_struktur_zurueck(monkeypatch, client):
    _fake_run(monkeypatch)
    r = client.post("/api/agent", json={"instruction": "Pruefe das."})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Sachlich richtig."
    assert body["result"] == {"note": 4}
    assert body["stop_reason"] == "submit"
    assert body["tools_called"] == ["get_nodes_details"]


def test_leere_anweisung_wird_abgewiesen(monkeypatch, client):
    _fake_run(monkeypatch)
    r = client.post("/api/agent", json={"instruction": "   "})
    assert r.status_code == 422


def test_der_zugangsblock_wird_an_der_http_grenze_uebernommen(monkeypatch, client):
    gesehen: dict = {}
    _fake_run(monkeypatch, gesehen=gesehen)
    r = client.post(
        "/api/agent", json={"instruction": "Lege an."},
        headers={"WLO-Access-Block": "wlo2.abc.def.ghi"})
    assert r.status_code == 200
    assert gesehen["personal"] is True


def test_ohne_kopfzeile_keine_persoenliche_anmeldung(monkeypatch, client):
    """Die Gegenrichtung: der ContextVar überlebt die Task, also muss jede
    Anfrage ohne Kopfzeile ihn löschen — sonst hinge sie an der vorigen."""
    gesehen: dict = {}
    _fake_run(monkeypatch, gesehen=gesehen)
    client.post("/api/agent", json={"instruction": "A."},
                headers={"WLO-Access-Block": "wlo2.abc.def.ghi"})
    client.post("/api/agent", json={"instruction": "B."}, headers={})
    assert gesehen["personal"] is False


def test_die_angaben_erreichen_den_lauf(monkeypatch, client):
    gesehen: dict = {}
    _fake_run(monkeypatch, gesehen=gesehen)
    client.post("/api/agent", json={
        "instruction": "Bewerte.", "collection_id": "c1", "node_ids": ["n1"],
        "result_schema": {"type": "object"}, "write_mode": "execute",
    })
    req = gesehen["req"]
    assert req.collection_id == "c1"
    assert req.node_ids == ["n1"]
    assert req.result_schema == {"type": "object"}
    assert req.write_mode == "execute"


# ── Der Strom ────────────────────────────────────────────────────────────


def _frames(text: str) -> list[tuple[str, str]]:
    out = []
    for block in text.split("\n\n"):
        if not block.startswith("event: "):
            continue
        zeilen = block.split("\n")
        out.append((zeilen[0][len("event: "):], zeilen[1][len("data: "):]))
    return out


def test_strom_haelt_den_rahmenvertrag(monkeypatch, client):
    gesehen: dict = {}
    _fake_run(monkeypatch, gesehen=gesehen)
    r = client.post("/api/agent/stream", json={"instruction": "Pruefe."})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    rahmen = _frames(r.text)
    assert rahmen[0][0] == "connected"
    assert [n for n, _ in rahmen] == ["connected", "phase", "result"]
    daten = json.loads(rahmen[-1][1])
    assert daten["text"] == "Sachlich richtig."
    assert daten["result"] == {"note": 4}


def test_ein_fehler_wird_zum_error_rahmen(monkeypatch, client):
    async def _boom(req, *, progress=None, usage_acc=None):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(agent_api, "run_agent", _boom)
    r = client.post("/api/agent/stream", json={"instruction": "Pruefe."})
    rahmen = _frames(r.text)
    assert [n for n, _ in rahmen] == ["connected", "error"]
    assert "RuntimeError" in json.loads(rahmen[-1][1])["message"]


# ── Wer darf rufen? (Nutzer-Entscheid 2026-08-12) ────────────────────────
#
# Der Endpunkt lag hinter dem Studio-Schlüssel, also dem ADMIN-Schlüssel — in
# einem Browser-Plugin hätte der nichts zu suchen. Neue Regel, in dieser
# Reihenfolge: Test-Schalter · persönliche Anmeldung · Studio-Schlüssel.

_SCHLUESSEL = "schluessel-fuer-den-test"
_PERSOENLICH = {"WLO-Access-Block": "wlo2.abc.def.ghi"}
#: Der anonyme Block ist eine bekannte Konstante des MCP-Servers
#: (`auth/credential.ts: ANONYMOUS_ACCESS_TOKEN`) und wohlgeformt.
_ANONYM = {"WLO-Access-Block": "wlo-anon.v1"}


@pytest.fixture
def verschlossen(monkeypatch):
    """Anlage mit gesetztem Schlüssel und ohne Test-Schalter — hier greift er."""
    monkeypatch.setenv("STUDIO_API_KEY", _SCHLUESSEL)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    monkeypatch.delenv("AGENT_OPEN", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_ohne_jede_anmeldung_abgewiesen(monkeypatch, verschlossen):
    _fake_run(monkeypatch)
    r = verschlossen.post("/api/agent", json={"instruction": "Pruefe."})
    assert r.status_code == 401


def test_persoenliche_anmeldung_reicht(monkeypatch, verschlossen):
    """Der Kern des Entscheids: ein Plugin kommt mit der Anmeldung der Person
    durch und braucht den Admin-Schlüssel nicht mehr."""
    _fake_run(monkeypatch)
    r = verschlossen.post("/api/agent", json={"instruction": "Pruefe."},
                          headers=_PERSOENLICH)
    assert r.status_code == 200


def test_anonymer_block_reicht_nicht(monkeypatch, verschlossen):
    """`wlo-anon.v1` ist wohlgeformt und trotzdem keine Anmeldung.

    Ohne diese Unterscheidung wäre der Riegel eine Formalie — die Konstante
    steht in der öffentlichen `AUTH.md` des MCP-Servers.
    """
    _fake_run(monkeypatch)
    r = verschlossen.post("/api/agent", json={"instruction": "Pruefe."},
                          headers=_ANONYM)
    assert r.status_code == 401


def test_studio_schluessel_bleibt_gueltig(monkeypatch, verschlossen):
    """Server-zu-Server lief schon; der Entscheid darf das nicht zerschlagen."""
    _fake_run(monkeypatch)
    r = verschlossen.post("/api/agent", json={"instruction": "Pruefe."},
                          headers={"X-Studio-Key": _SCHLUESSEL})
    assert r.status_code == 200


def test_auch_der_strom_liegt_hinter_dem_riegel(monkeypatch, verschlossen):
    _fake_run(monkeypatch)
    r = verschlossen.post("/api/agent/stream", json={"instruction": "Pruefe."})
    assert r.status_code == 401


def test_env_schalter_oeffnet_fuer_tests(monkeypatch):
    """Der ausdrückliche Ausweg für Testläufe — Vorgabe ist AUS."""
    _fake_run(monkeypatch)
    monkeypatch.setenv("STUDIO_API_KEY", _SCHLUESSEL)
    monkeypatch.setenv("AGENT_OPEN", "1")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        r = c.post("/api/agent", json={"instruction": "Pruefe."})
    get_settings.cache_clear()
    assert r.status_code == 200


def test_die_drosselung_gilt_jetzt_auch_hier(monkeypatch, client):
    """Sobald jemand ohne Studio-Schlüssel herein darf, ist die ZAHL der Läufe
    die eigentliche Grenze — nicht mehr der Kreis der Aufrufer. Das
    Modul-Docstring hatte genau diesen Tag benannt."""
    _fake_run(monkeypatch)
    monkeypatch.setenv("RATE_LIMIT_CHAT", "2/minute")
    get_settings.cache_clear()
    assert client.post("/api/agent", json={"instruction": "A."}).status_code == 200
    assert client.post("/api/agent", json={"instruction": "B."}).status_code == 200
    assert client.post("/api/agent", json={"instruction": "C."}).status_code == 429
