"""Paket U3-3a: die Stapel-Ablage über das MCP (``services/ablage/mcp_ablage``).

Die drei MCP-Werkzeuge (``wlo_prepare_file_batch``, ``wlo_store_batch_file``,
``wlo_store_batch_manifest``, MA-3/MA-4) ruft das Backend selbst — mit dem Zugangsblock der Person,
nie der Anlage — und liest ihr ``structuredContent``. Die Bytes gehen als Strom an ``POST
/api/uploads`` des MCP-Servers (MA-2). Fehler werden zu festen Codes, nie zu Servertext. Die
Werkzeuge stehen in keinem Werkzeug-Angebot an die KI.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from boerdi.services.ablage import mcp_ablage


@pytest.fixture
def mcp(monkeypatch):
    gerufen: list = []
    antworten: dict = {}

    async def call_tool(name, args, **_k):
        gerufen.append((name, args))
        return antworten.get(name, {"error": {"message": "x", "kind": "tool"}})

    monkeypatch.setattr(mcp_ablage.transport, "call_tool", call_tool)
    monkeypatch.setattr(mcp_ablage, "has_personal_auth", lambda: True)
    monkeypatch.setattr(mcp_ablage, "_zug_block", lambda: "wlo2.block-der-person")
    return {"gerufen": gerufen, "antworten": antworten}


def _ok(structured):
    return {"result": {"content": [{"type": "text", "text": "ok"}],
                       "structuredContent": structured}}


def test_vorbereiten_gibt_den_plan_des_servers_zurueck(mcp):
    mcp["antworten"]["wlo_prepare_file_batch"] = _ok({
        "batchToken": "tok-1234567890", "layout": "folder", "folderName": "Physik 7", "count": 1,
        "totalBytes": 5, "entries": [{"index": 0, "title": "Mechanik", "ext": "pdf", "size": 5,
                                     "fileName": "mechanik.pdf"}]})
    plan = asyncio.run(mcp_ablage.vorbereiten("Physik 7", [
        {"titel": "Mechanik", "sha256": "a" * 64, "groesse": 5, "art": "pdf"}]))
    assert plan["batchToken"] == "tok-1234567890"
    assert plan["entries"][0]["fileName"] == "mechanik.pdf"
    [(name, args)] = mcp["gerufen"]
    assert name == "wlo_prepare_file_batch"
    assert args == {"target": "home", "folderName": "Physik 7", "entries": [
        {"title": "Mechanik", "sha256": "a" * 64, "size": 5, "ext": "pdf", "role": "content"}]}


@pytest.mark.parametrize(("antwort", "code"), [
    ({"error": {"message": "x", "kind": "auth"}}, "kein_recht"),
    ({"error": {"message": "x", "kind": "tool"}}, "abgewiesen"),
    ({"error": {"message": "x", "kind": "timeout"}}, "zu_langsam"),
    ({"error": {"message": "x", "kind": "transport"}}, "nicht_erreichbar"),
    (_ok({"etwas": "anderes"}), "abgewiesen"),
])
def test_fehler_werden_codes(mcp, antwort, code):
    mcp["antworten"]["wlo_prepare_file_batch"] = antwort
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.vorbereiten("X", [{"titel": "a", "sha256": "a" * 64, "groesse": 1,
                                                    "art": "pdf"}]))
    assert fehler.value.code == code


def test_ohne_anmeldung_kein_aufruf(mcp, monkeypatch):
    monkeypatch.setattr(mcp_ablage, "has_personal_auth", lambda: False)
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.vorbereiten("X", []))
    assert fehler.value.code == "nur_angemeldet" and mcp["gerufen"] == []


def _upload_server(monkeypatch, antwort):
    gesehen: list = []

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return antwort

    monkeypatch.setattr(mcp_ablage, "_transport", httpx.MockTransport(behandle))
    monkeypatch.setattr(mcp_ablage, "_mcp_wurzel", lambda: "http://mcp.test")
    return gesehen


async def _strom(*teile):
    for t in teile:
        yield t


def test_datei_hochladen_als_strom_mit_dem_block_der_person(mcp, monkeypatch):
    gesehen = _upload_server(monkeypatch, httpx.Response(201, json={
        "ref": "r" * 24, "sha256": "a" * 64, "size": 6, "mimeType": "application/pdf",
        "ext": "pdf"}))
    slot = asyncio.run(mcp_ablage.datei_hochladen(_strom(b"%PDF", b"-1"), 6, "a.pdf"))
    assert slot["ref"] == "r" * 24
    [anfrage] = gesehen
    assert str(anfrage.url) == "http://mcp.test/api/uploads"
    assert anfrage.headers["authorization"] == "Bearer wlo2.block-der-person"
    assert anfrage.headers["content-type"] == "application/octet-stream"
    assert anfrage.headers["content-length"] == "6"
    assert anfrage.headers["x-upload-name"] == "a.pdf"


@pytest.mark.parametrize(("status", "code"), [
    (403, "kein_recht"), (413, "zu_gross"), (415, "art"), (429, "voll"), (408, "zu_langsam"),
    (500, "fehler"),
])
def test_upload_fehler(mcp, monkeypatch, status, code):
    _upload_server(monkeypatch, httpx.Response(status, json={"error": "x"}))
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.datei_hochladen(_strom(b"x"), 1, "a.pdf"))
    assert fehler.value.code == code


def test_ablegen_und_abschliessen(mcp):
    mcp["antworten"]["wlo_store_batch_file"] = _ok({"status": "stored", "nodeId": "n-1",
                                                    "folderDenied": False})
    mcp["antworten"]["wlo_store_batch_manifest"] = _ok({"status": "stored", "nodeId": "n-2"})
    assert asyncio.run(mcp_ablage.datei_ablegen("tok-1234567890", 0, "r" * 24))["nodeId"] == "n-1"
    assert asyncio.run(mcp_ablage.abschliessen("tok-1234567890"))["status"] == "stored"
    assert mcp["gerufen"][1] == ("wlo_store_batch_manifest", {"batchToken": "tok-1234567890"})


def test_die_stapel_werkzeuge_stehen_in_keinem_angebot_an_die_ki():
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

    namen = {t["function"]["name"] for t in [*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS]}
    assert not namen & mcp_ablage.WERKZEUGE


# ── Review U3-3a ────────────────────────────────────────────────────────────────────────────

def test_eine_ablehnung_mit_grund_kommt_als_ergebnis(mcp):
    """Befund 2: der Grund des MCP (``reason``) geht nicht als „abgewiesen“ verloren."""
    mcp["antworten"]["wlo_store_batch_file"] = {"error": {"message": "x", "kind": "tool",
                                                         "structured": {"status": "failed",
                                                                        "reason": "slot_missing"}}}
    ergebnis = asyncio.run(mcp_ablage.datei_ablegen("tok-1234567890", 0, "r" * 24))
    assert mcp_ablage.grund(ergebnis) == "erneut"
    assert mcp_ablage.grund({"status": "failed", "reason": "expired"}) == "neu_vorbereiten"
    assert mcp_ablage.grund({"status": "failed", "reason": "mismatch_bytes"}) == "passt_nicht"
    assert mcp_ablage.grund({"status": "failed"}) is None        # ein Stand, kein Grund
    assert mcp_ablage.grund({"status": "stored"}) is None


def test_zu_viele_anmeldungen_ist_kein_voll(mcp, monkeypatch, caplog):
    """Befund 6: eine Betriebs-Einstellung des MCP — gewarnt, nicht „voll“."""
    _upload_server(monkeypatch, httpx.Response(429, json={"error": "too_many_logins"}))
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.datei_hochladen(_strom(b"x"), 1, "Geheimer Name.pdf"))
    assert fehler.value.code == "anmeldungen"
    assert "AUTH_CREDENTIAL_LIMIT" in caplog.text and "Geheimer" not in caplog.text


@pytest.mark.parametrize(("antwort", "code"), [
    # Zweite Antwort des MCP-Teams (2026-11-07): edu-sharing beantwortete die Anmeldeprüfung nicht.
    (httpx.Response(503, headers={"Retry-After": "10"},
                    json={"error": "upstream_unreachable", "code": "upstream_unreachable",
                          "retryAfter": 10}), "nicht_erreichbar"),
    # Neu: ``code`` neben ``error``.
    (httpx.Response(429, json={"error": "Zu viele", "code": "too_many_logins", "retryAfter": 60}),
     "anmeldungen"),
    (httpx.Response(429, json={"error": "rate_limited", "code": "rate_limited", "retryAfter": 5}),
     "voll"),
], ids=["503-unerreichbar", "429-anmeldungen-code", "429-budget"])
def test_ablehnungen_des_upload_platzes(mcp, monkeypatch, antwort, code):
    _upload_server(monkeypatch, antwort)
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.datei_hochladen(_strom(b"x"), 1, "a.pdf"))
    assert fehler.value.code == code


def test_eine_zeitueberschreitung_beim_hochladen(mcp, monkeypatch):
    def langsam(request):
        raise httpx.ReadTimeout("zu langsam", request=request)

    monkeypatch.setattr(mcp_ablage, "_transport", httpx.MockTransport(langsam))
    monkeypatch.setattr(mcp_ablage, "_mcp_wurzel", lambda: "http://mcp.test")
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.datei_hochladen(_strom(b"x"), 1, "a.pdf"))
    assert fehler.value.code == "zu_langsam"


def test_die_wurzel_folgt_dem_werkzeug_weg(monkeypatch):
    """Befund 7: dieselbe Adresse wie die Werkzeug-Aufrufe (auch mit leerer Einstellung)."""
    monkeypatch.setattr(mcp_ablage.transport, "resolve_mcp_url", lambda: "https://mcp.example/mcp")
    assert mcp_ablage._mcp_wurzel() == "https://mcp.example"


@pytest.mark.parametrize(("code", "erwartet"), [
    ("login_rejected", "kein_recht"), ("login_required", "nur_angemeldet"),
    ("timeout", "zu_langsam"), ("invalid_input", "abgewiesen"), ("upstream_error", "abgewiesen"),
])
def test_der_neue_fehlervertrag_wird_ein_code(mcp, code, erwartet):
    """Paket M1, Review Befund 2: seit 2026-11-07 trägt JEDER Fehler ``structured.error`` — nur
    die Stapel-Ablehnungen (``status``/``reason``) sind ein Ergebnis, der Rest ein Code."""
    mcp["antworten"]["wlo_prepare_file_batch"] = {"error": {
        "message": "x", "kind": "tool", "structured": {"error": {"code": code, "message": "x"}}}}
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.vorbereiten("X", [{"titel": "a", "sha256": "a" * 64, "groesse": 1,
                                                    "art": "pdf"}]))
    assert fehler.value.code == erwartet


def test_eine_stapel_ablehnung_bleibt_ein_ergebnis(mcp):
    mcp["antworten"]["wlo_store_batch_file"] = {"error": {
        "message": "x", "kind": "tool", "structured": {
            "status": "failed", "reason": "batch_expired",
            "error": {"code": "batch_expired", "message": "x"}}}}
    ergebnis = asyncio.run(mcp_ablage.datei_ablegen("tok-1234567890", 0, "r" * 24))
    assert mcp_ablage.grund(ergebnis) == "neu_vorbereiten"
