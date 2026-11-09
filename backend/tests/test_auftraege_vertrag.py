"""Der Job-Vertrag der B-API (Handbuch vom 07.11.2026, am Staging gemessen).

- Start ``POST /api/v1/jobs/flows/{namespace}/{flowId}`` → 202 mit ``jobId`` (Bearer geht).
- Status ``GET /api/v1/jobs/{jobId}``: ``QUEUED``, ``RUNNING``, ``SUCCEEDED``, ``FAILED``,
  ``CANCELLED``. Der Client kannte bis hier nur die Kestra-Namen ``SUCCESS``/``WARNING`` — ein
  fertiger Job blieb „unbekannt“. Dazu ``warnings``, ``error.code`` (dokumentiert nur ``TIMEOUT``),
  ``files`` mit ``available``/``reason``.
- 400 beim Start: Eingaben passen nicht (auch: Repository-Scope ohne ``X-Edu-User-Id``); 429 mit
  ``Retry-After`` (mehr als 20 offene Jobs je Schlüssel).
- Abbrechen ``DELETE /api/v1/jobs/{jobId}``: 200/202 = abgebrochen, 409 = schon beendet.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from boerdi.services.auftraege import client
from boerdi.settings import get_settings

FLOW = "edusharing.support/test-mit-jan"
START = "/api/v1/jobs/flows/edusharing.support/test-mit-jan"


@pytest.fixture
def bapi(monkeypatch):
    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api/v1/llm")
    monkeypatch.setenv("B_API_KEY", "schluessel-der-anlage")
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", FLOW)
    get_settings.cache_clear()
    gesehen: list[httpx.Request] = []
    antworten: dict[tuple[str, str], httpx.Response] = {}

    def behandle(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return antworten.get((request.method, request.url.path),
                             httpx.Response(404, json={"error": "fehlt"}))

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(behandle))
    yield {"gesehen": gesehen, "antworten": antworten}
    get_settings.cache_clear()


def _job(status: str, **mehr) -> httpx.Response:
    return httpx.Response(200, json={"jobId": "job-1", "flow": FLOW, "status": status,
                                     "outputs": None, "files": None, "warnings": False,
                                     "error": None, **mehr})


def test_der_start_trifft_den_echten_pfad(bapi):
    bapi["antworten"][("POST", START)] = httpx.Response(
        202, json={"jobId": "168bfecf-d755-4b6f-9888-3654740a38fa", "status": "RUNNING"})
    assert asyncio.run(client.starten(FLOW, {"api_url": "https://dummyjson.com/products"})) == (
        "168bfecf-d755-4b6f-9888-3654740a38fa")


@pytest.mark.parametrize(("status", "erwartet"), [
    ("QUEUED", "laeuft"), ("RUNNING", "laeuft"), ("SUCCEEDED", "fertig"),
    ("FAILED", "fehler"), ("CANCELLED", "fehler"),
])
def test_die_statuswerte_der_b_api(bapi, status, erwartet):
    bapi["antworten"][("GET", "/api/v1/jobs/job-1")] = _job(status)
    assert asyncio.run(client.stand("job-1")).status == erwartet


def test_ein_fertiger_job_mit_ausgaben_dateien_und_warnung(bapi):
    """Gemessen 2026-11-07: ``outputs.status_code`` kam als Text ``"200"``."""
    bapi["antworten"][("GET", "/api/v1/jobs/job-1")] = _job(
        "SUCCEEDED", outputs={"status_code": "200", "content": "x"}, warnings=True,
        files=[{"outputId": "report", "name": "report.html", "size": 1234, "available": True,
                "downloadUrl": "/api/v1/jobs/job-1/files/report"},
               {"outputId": "alt", "name": "alt.ndjson", "size": 9, "available": False,
                "reason": "EXPIRED"}])
    stand = asyncio.run(client.stand("job-1"))
    assert stand.status == "fertig" and stand.warnungen is True
    assert stand.outputs == {"status_code": "200", "content": "x"}
    # K2d-2: mit der Kennung (``outputId``) — geholt wird über eine selbst gebildete Adresse
    assert stand.dateien == [
        {"name": "report.html", "groesse": 1234, "kennung": "report", "verfuegbar": True},
        {"name": "alt.ndjson", "groesse": 9, "kennung": "alt", "verfuegbar": False,
         "grund": "EXPIRED"}]
    assert "downloadUrl" not in str(stand.dateien)


def test_ein_gescheiterter_job_nennt_seinen_code(bapi):
    bapi["antworten"][("GET", "/api/v1/jobs/job-1")] = _job("FAILED", error={"code": "TIMEOUT"})
    stand = asyncio.run(client.stand("job-1"))
    assert (stand.status, stand.fehlercode) == ("fehler", "TIMEOUT")


def test_ein_unbekannter_fehlercode_bleibt_ein_fehler(bapi):
    bapi["antworten"][("GET", "/api/v1/jobs/job-1")] = _job("FAILED", error={"code": "NEU_ABC"})
    stand = asyncio.run(client.stand("job-1"))
    assert (stand.status, stand.fehlercode) == ("fehler", "NEU_ABC")


def test_400_beim_start_heisst_eingaben(bapi):
    bapi["antworten"][("POST", START)] = httpx.Response(400, json={"error": "invalid"})
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.starten(FLOW, {}))
    assert fehler.value.grund == "eingaben"


def test_429_nennt_die_wartezeit(bapi):
    bapi["antworten"][("POST", START)] = httpx.Response(429, headers={"Retry-After": "30"})
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.starten(FLOW, {}))
    assert (fehler.value.grund, fehler.value.warte_s) == ("voll", 30)


@pytest.mark.parametrize(("code", "erwartet"), [
    (202, "abgebrochen"), (200, "abgebrochen"), (409, "schon_fertig"),
])
def test_abbrechen(bapi, code, erwartet):
    bapi["antworten"][("DELETE", "/api/v1/jobs/job-1")] = httpx.Response(code, json={})
    assert asyncio.run(client.abbrechen("job-1")) == erwartet
    assert bapi["gesehen"][-1].method == "DELETE"


def test_abbrechen_eines_fremden_jobs(bapi):
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(client.abbrechen("job-1"))
    assert fehler.value.grund == "unbekannt"


def test_abbrechen_im_hintergrund_wirft_nie(bapi):
    """Beim Ersetzen oder Abbrechen eines wartenden Laufs: die B-API soll den Job beenden, ohne
    dass der Zug darauf wartet oder an einem Fehler scheitert."""
    async def lauf():
        client.abbrechen_im_hintergrund("job-1")        # 404 → AuftragFehler, geschluckt
        await asyncio.gather(*client._abbrueche)
    asyncio.run(lauf())
    assert [r.method for r in bapi["gesehen"]] == ["DELETE"]


def test_abbrechen_im_hintergrund_schluckt_auch_unerwartetes(bapi, monkeypatch, caplog):
    """Review Job-Vertrag, Befund 4: „wirft nie“ gilt auch für andere Fehler — geloggt wird nur
    die Art."""
    async def kaputt(job_id):
        raise RuntimeError("geheim-xyz")

    monkeypatch.setattr(client, "abbrechen", kaputt)

    async def lauf():
        client.abbrechen_im_hintergrund("job-1")
        ergebnisse = await asyncio.gather(*client._abbrueche, return_exceptions=True)
        assert ergebnisse == [None]
    asyncio.run(lauf())
    assert "RuntimeError" in caplog.text and "geheim-xyz" not in caplog.text


def test_abbrechen_mit_204(bapi):
    bapi["antworten"][("DELETE", "/api/v1/jobs/job-1")] = httpx.Response(204)
    assert asyncio.run(client.abbrechen("job-1")) == "abgebrochen"


def test_abbrechen_im_hintergrund_mit_unbrauchbarer_id_tut_nichts(bapi):
    async def lauf():
        client.abbrechen_im_hintergrund("../admin")
        await asyncio.sleep(0.01)
    asyncio.run(lauf())
    assert bapi["gesehen"] == []
