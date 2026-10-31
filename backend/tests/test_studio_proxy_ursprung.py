"""Der Studio-Proxy weist ändernde Anfragen fremder Seiten ab (Paket 10, Audit 2026-10-10 M-2).

Der Proxy setzt bei gültigem Cookie den Admin-Schlüssel ein. Der Schutz gegen
fremde Seiten hing allein an ``SameSite=Strict`` — das hält fremde *Sites* ab, aber
nicht Seiten derselben Site (Subdomains). Ein Multipart-POST ohne Preflight
(Konfig-Wiederherstellung, RAG-Upload) liefe von dort mit Admin-Rechten.

Browser melden mit ``Sec-Fetch-Site``, woher eine Anfrage kommt; ältere schicken bei
ändernden Anfragen wenigstens ``Origin``. Fehlt beides, ist der Aufrufer kein
Browser — und damit keiner, der ein fremdes Cookie mitschicken könnte.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.api import ratelimit
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.main import create_app
from boerdi.settings import get_settings

_PASSWORT = "geheim-studio-pw"
_PROBE = "/studio/api/debug/mcp-test"


@pytest.fixture(autouse=True)
def _studio(monkeypatch):
    monkeypatch.setenv("STUDIO_PASSWORD", _PASSWORT)
    monkeypatch.setenv("STUDIO_API_KEY", "backend-key-0123")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture()
def angemeldet() -> TestClient:
    client = TestClient(create_app())
    client.cookies.set(COOKIE_NAME, studio_token(_PASSWORT))
    return client


@pytest.mark.parametrize("seite", ["cross-site", "same-site"])
def test_eine_aendernde_anfrage_einer_fremden_seite_wird_abgewiesen(angemeldet, seite):
    antwort = angemeldet.post(_PROBE, headers={"Sec-Fetch-Site": seite})
    assert antwort.status_code == 403


def test_ein_fremder_ursprung_ohne_fetch_metadaten_wird_abgewiesen(angemeldet):
    antwort = angemeldet.post(_PROBE, headers={"Origin": "https://studio.evil.example"})
    assert antwort.status_code == 403


@pytest.mark.parametrize("kopf", [
    {"Sec-Fetch-Site": "same-origin"},
    {"Origin": "http://testserver"},
    {},  # kein Browser
])
def test_dieselbe_herkunft_und_nicht_browser_kommen_durch(angemeldet, kopf):
    antwort = angemeldet.post(_PROBE, headers=kopf)
    assert antwort.status_code != 403


def test_lesende_anfragen_bleiben_unberuehrt(angemeldet):
    # Ein fremdes Skript kann eine Antwort ohne CORS-Freigabe nicht lesen.
    assert angemeldet.get(_PROBE, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 501
