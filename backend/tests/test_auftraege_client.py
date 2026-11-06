"""Paket K1a: der B-API-Client für Aufträge (Kestra-Flows) — gegen eine Vertrags-Attrappe.

Bekannt (Team-Info 2026-11-03, Konzept §16.15): Abfrage ``GET /api/v1/jobs/{jobId}`` → ``status``,
``outputs``, ``files``; 20 offene Jobs je Schlüssel (dann 429). Offen (K16): der Start-Pfad — daher
``B_API_JOBS_START_PATH`` (leer = Aufträge aus). Der Betrieb schaltet Flows frei
(``B_API_JOBS_FLOWS``); der Schlüssel ist der des Zuges (nie gespeichert), kein ``X-Edu-User-Id``
(K18 offen).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from boerdi.services.auftraege import client
from boerdi.settings import get_settings


@pytest.fixture
def betrieb(monkeypatch):
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", "schluessel-der-anlage")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/flows/{flow}/jobs")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/datei-zu-markdown, wlo/volltext")
    get_settings.cache_clear()
    gesehen: list[httpx.Request] = []
    antworten: dict[str, httpx.Response] = {}

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return antworten.get(request.url.path, httpx.Response(404, json={"error": "fehlt"}))

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    yield {"gesehen": gesehen, "antworten": antworten}
    get_settings.cache_clear()


def test_ohne_start_pfad_sind_auftraege_aus(monkeypatch):
    monkeypatch.delenv("B_API_JOBS_START_PATH", raising=False)
    get_settings.cache_clear()
    assert client.freigeschaltet() is False
    assert client.erlaubt("wlo/datei-zu-markdown") is False


def test_nur_freigeschaltete_flows(betrieb):
    assert client.freigeschaltet() and client.erlaubt("wlo/volltext")
    assert not client.erlaubt("wlo/schreibt-alles") and not client.erlaubt("")


def test_der_start_schickt_eingaben_mit_dem_schluessel_des_zuges(betrieb):
    betrieb["antworten"]["/api/v1/flows/wlo/datei-zu-markdown/jobs"] = httpx.Response(
        200, json={"jobId": "job-123"})
    job = asyncio.run(client.starten("wlo/datei-zu-markdown", {"knoten": "abc"}))
    assert job == "job-123"
    [anfrage] = betrieb["gesehen"]
    assert anfrage.method == "POST" and anfrage.url.host == "b-api.example"
    assert anfrage.headers["Authorization"] == "Bearer schluessel-der-anlage"
    assert "X-Edu-User-Id" not in anfrage.headers
    assert json.loads(anfrage.content) == {"knoten": "abc"}


def test_ein_nicht_freigeschalteter_flow_wird_nicht_gestartet(betrieb):
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.starten("wlo/schreibt-alles", {}))
    assert fehler.value.grund == "nicht_erlaubt" and betrieb["gesehen"] == []


@pytest.mark.parametrize(("antwort", "grund"), [
    (httpx.Response(429, json={}), "voll"),
    (httpx.Response(401, json={}), "abgewiesen"),
    (httpx.Response(500, json={}), "fehler"),
    (httpx.Response(200, json={"etwas": "anderes"}), "fehler"),
    (httpx.Response(200, content=b"kein json"), "fehler"),
])
def test_fehler_beim_start(betrieb, antwort, grund):
    betrieb["antworten"]["/api/v1/flows/wlo/volltext/jobs"] = antwort
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.starten("wlo/volltext", {}))
    assert fehler.value.grund == grund


@pytest.mark.parametrize(("status", "erwartet"), [
    ("RUNNING", "laeuft"), ("CREATED", "laeuft"), ("QUEUED", "laeuft"),
    ("SUCCESS", "fertig"), ("WARNING", "fertig"),
    ("FAILED", "fehler"), ("KILLED", "fehler"), ("CANCELLED", "fehler"),
])
def test_der_stand_eines_auftrags(betrieb, status, erwartet):
    betrieb["antworten"]["/api/v1/jobs/job-123"] = httpx.Response(200, json={
        "status": status, "outputs": {"markdown": "# Titel"},
        "files": [{"name": "a.md", "size": 12, "downloadUrl": "https://x/geheim?token=1"}]})
    stand = asyncio.run(client.stand("job-123"))
    assert stand.status == erwartet
    if erwartet == "fertig":
        assert stand.outputs == {"markdown": "# Titel"}
        # Dateien nur mit Name und Größe — die Adresse kann ein Token tragen.
        assert stand.dateien == [{"name": "a.md", "groesse": 12}]


def test_eine_job_id_wird_nicht_in_den_pfad_geschmuggelt(betrieb):
    with pytest.raises(client.AuftragFehler):
        asyncio.run(client.stand("../admin"))
    assert betrieb["gesehen"] == []


def test_ein_unbekannter_job(betrieb):
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.stand("job-fehlt"))
    assert fehler.value.grund == "unbekannt"


# ── Review K1a ───────────────────────────────────────────────────────────────────────────────

def test_der_durchgereichte_schluessel_gewinnt(betrieb):
    from boerdi.services import llm_auth

    betrieb["antworten"]["/api/v1/flows/wlo/volltext/jobs"] = httpx.Response(
        200, json={"jobId": "job-9"})
    llm_auth.setze_llm_schluessel("Bearer schluessel-der-person")
    try:
        asyncio.run(client.starten("wlo/volltext", {}))
    finally:
        llm_auth.setze_llm_schluessel(None)
    assert betrieb["gesehen"][0].headers["Authorization"] == "Bearer schluessel-der-person"


@pytest.mark.parametrize("status", ["", "COMPLETED", "PENDING"])
def test_ein_unbekannter_stand_ist_erneut_abfragbar(betrieb, status):
    """Befund 2: kein endgültiger Fehlschlag — der Vertrag ist erst eine Attrappe (K16)."""
    betrieb["antworten"]["/api/v1/jobs/job-123"] = httpx.Response(200, json={"status": status})
    with pytest.raises(client.AuftragFehler):
        asyncio.run(client.stand("job-123"))


def test_eine_zu_grosse_ausgabe_gilt_als_gescheitert(betrieb):
    """Befund 4."""
    betrieb["antworten"]["/api/v1/jobs/job-123"] = httpx.Response(200, json={
        "status": "SUCCESS", "outputs": {"text": "x" * (client.MAX_AUSGABE_BYTES + 1)}})
    assert asyncio.run(client.stand("job-123")).status == "fehler"


@pytest.mark.parametrize("vorlage", ["api/v1/x/{flow}", "/@boese.example/{flow}",
                                     "//boese.example/{flow}", "/x?y={flow}", "/x#{flow}"])
def test_eine_unsichere_pfad_vorlage_schaltet_aus(monkeypatch, betrieb, vorlage):
    """Befund 5: der Schlüssel geht nie an einen anderen Server."""
    monkeypatch.setenv("B_API_JOBS_START_PATH", vorlage)
    get_settings.cache_clear()
    assert client.freigeschaltet() is False
    with pytest.raises(client.AuftragFehler):
        asyncio.run(client.starten("wlo/volltext", {}))
    assert betrieb["gesehen"] == []


def test_die_wurzel_ohne_llm_pfad(monkeypatch, betrieb):
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm/")
    get_settings.cache_clear()
    assert client._wurzel() == "https://b-api.example"


@pytest.mark.parametrize("job", ["..", ".", "a/b", "x" * 201])
def test_unbrauchbare_job_ids(betrieb, job):
    with pytest.raises(client.AuftragFehler):
        asyncio.run(client.stand(job))
    assert betrieb["gesehen"] == []


def test_die_grenze_zaehlt_bytes_nicht_zeichen(betrieb):
    """Querschnitts-Review (NIT): 600 000 „ä“ sind 1,2 MB — mehr als die Grenze, auch wenn es
    weniger Zeichen sind."""
    betrieb["antworten"]["/api/v1/jobs/job-123"] = httpx.Response(200, json={
        "status": "SUCCESS", "outputs": {"text": "ä" * 600_000}})
    assert asyncio.run(client.stand("job-123")).status == "fehler"
