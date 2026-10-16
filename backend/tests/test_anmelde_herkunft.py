"""Anmeldung nur auf erlaubten Seiten, wenn die Anlage geschlossen ist (Nutzer 2026-10-15).

A-2 (Kurzaudit 2026-10-10): der Zugangsblock liegt im ``sessionStorage`` der Gastseite; jedes
Skript dort kann ihn lesen. Mit ``CORS_ALLOW_ALL=false`` bietet das Widget die Anmeldung (Knopf
und Ticket-Tausch) nur auf Seiten aus ``CORS_ORIGINS`` an — und, solange erlaubt, in Browser-
Erweiterungen. Mit der Vorgabe ``CORS_ALLOW_ALL=true`` bleibt alles wie bisher.

Bei geschlossenem CORS kann der Browser einer fremden Seite die Antwort ohnehin nicht lesen; die
Regel hier macht daraus eine Zusicherung des Backends (etwa gegen einen Proxy, der CORS-
Kopfzeilen ergänzt).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.domain.anmelde_herkunft import anmeldung_erlaubt

_REGEX = r"(safari-web-extension|chrome-extension)://.*"


def _regel(origin, *, offen=False, liste=("https://wirlernenonline.de",), regex=_REGEX):
    return anmeldung_erlaubt(origin, allow_all=offen, origins=list(liste), origin_regex=regex)


def test_offen_ist_alles_wie_bisher():
    assert _regel("https://fremd.example", offen=True)


@pytest.mark.parametrize("origin", [
    "https://wirlernenonline.de", "https://WirLernenOnline.de", "https://wirlernenonline.de/",
    None, "",  # gleiche Herkunft: der Browser schickt bei einem GET oft kein Origin
    "chrome-extension://abcdef", "safari-web-extension://72c621e2-0000",
])
def test_erlaubt_geschlossen(origin):
    assert _regel(origin)


@pytest.mark.parametrize("origin", [
    "https://fremd.example", "https://wirlernenonline.de.fremd.example",
    "http://wirlernenonline.de", "null",
])
def test_nicht_erlaubt_geschlossen(origin):
    assert not _regel(origin)


def test_ohne_erweiterungs_regel_keine_erweiterungen():
    assert not _regel("chrome-extension://abcdef", regex=None)


def test_eine_liste_mit_stern_gilt_als_offen():
    assert _regel("https://fremd.example", liste=("*",))


def _endpunkt(monkeypatch, *, origin, offen, liste="https://wirlernenonline.de"):
    from boerdi.api import config as api_config

    einstellungen = SimpleNamespace(
        mcp_server_url="https://mcp.example.org/mcp", cors_allow_all=offen,
        cors_origin_list=[t.strip() for t in liste.split(",")], cors_origin_regex=None)
    monkeypatch.setattr(api_config, "get_settings", lambda: einstellungen)
    monkeypatch.setattr(api_config.cl, "load_guide_mode_config", lambda: {})
    monkeypatch.setattr(api_config.cl, "load_header_nav_config", lambda: {})
    monkeypatch.setattr(api_config.cl, "load_welcome_config", lambda: {})
    anfrage = SimpleNamespace(headers={"origin": origin} if origin else {})
    return asyncio.run(api_config.get_guide_mode(anfrage))["mcp_auth_base"]


def test_das_buendel_nennt_die_anmeldung_nur_erlaubten_seiten(monkeypatch):
    assert _endpunkt(monkeypatch, origin="https://wirlernenonline.de", offen=False) == (
        "https://mcp.example.org")
    assert _endpunkt(monkeypatch, origin="https://fremd.example", offen=False) == ""
    assert _endpunkt(monkeypatch, origin="https://fremd.example", offen=True) == (
        "https://mcp.example.org")
