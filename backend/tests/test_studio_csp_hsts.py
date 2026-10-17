"""Paket 8 (P1/P2): HSTS für jede Antwort, eine Content-Security-Policy für die Studio-Seite.

Audit 2026-09-29, Bedingung 3 (A-M6/F-M5): Studio, Demo-Seiten und das Rendering
fremder Inhalte teilen einen Ursprung — eine XSS im Studio ist Admin-Zugriff. Die CSP
gilt der Studio-Seite (``index.html`` und jedem SPA-Rückfall), nicht der API und nicht
den Demo-Seiten; HSTS gilt dem ganzen Host.

Ohne ``with``-Block: der Lebenszyklus braucht Postgres (wie ``test_studio_bff.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.settings import get_settings

_SEITEN = ("/studio/", "/studio/index.html", "/studio/bereich/01-base/welcome-config")


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    for name in ("STUDIO_CSP", "HSTS_MAX_AGE", "STUDIO_DIST_DIR", "MCP_SERVER_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _app(monkeypatch, tmp_path, **env: str) -> TestClient:
    dist = tmp_path / "studio_dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>Studio</h1>", encoding="utf-8")
    (dist / "main-3SIIJNXP.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("STUDIO_DIST_DIR", str(dist))
    for name, wert in env.items():
        monkeypatch.setenv(name, wert)
    get_settings.cache_clear()
    return TestClient(create_app())


def _direktiven(csp: str) -> dict[str, list[str]]:
    teile = (teil.split() for teil in csp.split(";") if teil.strip())
    return {name: werte for name, *werte in teile}


# ── P1: HSTS ──────────────────────────────────────────────────────────────


def test_hsts_steht_auf_jeder_antwort_einen_tag_lang(monkeypatch, tmp_path):
    """Vorgabe 1 Tag: bricht das Zertifikat, sperrt sich der Browser höchstens einen
    Tag lang aus. Über HTTP ignorieren Browser den Header (RFC 6797, 8.1) — lokal
    ohne TLS schadet er nicht."""
    client = _app(monkeypatch, tmp_path)
    for pfad in ("/health", "/studio/"):
        assert client.get(pfad).headers.get("strict-transport-security") == "max-age=86400", pfad


def test_hsts_laesst_sich_verlaengern(monkeypatch, tmp_path):
    client = _app(monkeypatch, tmp_path, HSTS_MAX_AGE="31536000")
    assert client.get("/health").headers["strict-transport-security"] == "max-age=31536000"


@pytest.mark.parametrize("wert", ["0", "-5"])
def test_hsts_null_oder_weniger_heisst_kein_header(monkeypatch, tmp_path, wert):
    client = _app(monkeypatch, tmp_path, HSTS_MAX_AGE=wert)
    assert "strict-transport-security" not in client.get("/health").headers


# ── P2: CSP der Studio-Seite ─────────────────────────────────────────────


def test_die_studio_seite_setzt_die_csp_durch(monkeypatch, tmp_path):
    client = _app(monkeypatch, tmp_path)
    for pfad in _SEITEN:
        antwort = client.get(pfad)
        assert antwort.text == "<h1>Studio</h1>", pfad
        assert "content-security-policy" in antwort.headers, pfad
        assert "content-security-policy-report-only" not in antwort.headers, pfad


def test_die_regel_laesst_kein_fremdes_und_kein_inline_skript_zu(monkeypatch, tmp_path):
    client = _app(monkeypatch, tmp_path, MCP_SERVER_URL="https://mcp.example.org:8443/mcp")
    regel = _direktiven(client.get("/studio/").headers["content-security-policy"])
    assert regel["default-src"] == ["'self'"]
    assert regel["script-src"] == ["'self'"]
    assert regel["object-src"] == ["'none'"]
    assert regel["base-uri"] == ["'self'"]
    assert regel["frame-ancestors"] == ["'self'"]   # wie X-Frame-Options SAMEORIGIN
    # Die Vorschau lädt das Widget in die Studio-Seite: die WLO-Anmeldung spricht den
    # MCP-Server direkt an (Entdeckung, Registrierung, Code-Tausch) — nur ihn.
    assert regel["connect-src"] == ["'self'", "https://mcp.example.org:8443"]
    # Vorlesen spielt ein blob:-Audio, Karten zeigen Vorschaubilder fremder Repositorien.
    assert "blob:" in regel["media-src"]
    assert "https:" in regel["img-src"]


def test_eine_kaputte_mcp_adresse_bricht_die_regel_nicht_auf(monkeypatch, tmp_path):
    """Ein Semikolon in ``MCP_SERVER_URL`` begänne sonst eine eigene Direktive."""
    client = _app(monkeypatch, tmp_path, MCP_SERVER_URL="https://mcp.example.org;script-src *")
    csp = client.get("/studio/").headers["content-security-policy"]
    assert _direktiven(csp)["connect-src"] == ["'self'"]
    assert _direktiven(csp)["script-src"] == ["'self'"]


def test_report_beobachtet_nur(monkeypatch, tmp_path):
    antwort = _app(monkeypatch, tmp_path, STUDIO_CSP="report").get("/studio/")
    assert "content-security-policy-report-only" in antwort.headers
    assert "content-security-policy" not in antwort.headers


def test_off_setzt_keine_regel(monkeypatch, tmp_path):
    antwort = _app(monkeypatch, tmp_path, STUDIO_CSP="off").get("/studio/")
    assert "content-security-policy" not in antwort.headers
    assert "content-security-policy-report-only" not in antwort.headers


def test_ein_tippfehler_setzt_die_regel_durch(monkeypatch, tmp_path):
    """Ein unbekannter Wert fällt auf die sichere Seite, nicht auf „aus“."""
    antwort = _app(monkeypatch, tmp_path, STUDIO_CSP="enforced").get("/studio/")
    assert "content-security-policy" in antwort.headers


def test_die_api_traegt_die_studio_regel_nicht(monkeypatch, tmp_path):
    """Die Regel ist auf die Studio-Seite zugeschnitten; Demo-Seiten und API bleiben
    unberührt (eine eigene Regel für sie wäre ein eigener Schritt)."""
    antwort = _app(monkeypatch, tmp_path).get("/health")
    assert "content-security-policy" not in antwort.headers


def test_der_studio_build_schreibt_kein_inline_skript():
    """Beasties (kritisches CSS) hängt beim Produktions-Build ein Inline-Skript an, das
    das Stylesheet von ``media="print"`` umschaltet — unter ``script-src 'self'`` liefe
    es nicht, und das Studio stünde ohne Stil da. Deshalb ``inlineCritical: false``."""
    angular = Path(__file__).resolve().parents[2] / "frontend" / "angular.json"
    if not angular.is_file():
        pytest.skip("frontend/angular.json fehlt (Backend allein ausgecheckt)")
    studio = json.loads(angular.read_text(encoding="utf-8"))["projects"]["studio"]
    stile = studio["architect"]["build"]["configurations"]["production"]["optimization"]["styles"]
    assert stile["inlineCritical"] is False


# ── Paket 9 (Review Paket 7, MINOR 21): die Herkunft ohne Zugangsdaten ──────────

@pytest.mark.parametrize(("url", "herkunft"), [
    ("https://nutzer:geheim@mcp.example.org:8443/mcp", "https://mcp.example.org:8443"),
    ("https://MCP.Example.org/mcp", "https://mcp.example.org"),
    ("http://[::1]:9000/mcp", "http://[::1]:9000"),
    ("https://mcp.example.org:99999/mcp", ""),
])
def test_die_mcp_herkunft_traegt_keine_zugangsdaten(url, herkunft):
    """``netloc`` enthielt ``nutzer:geheim@`` — und landete im öffentlichen Widget-Bündel."""
    from boerdi.domain.mcp_herkunft import mcp_herkunft

    assert mcp_herkunft(url) == herkunft


@pytest.mark.parametrize("mcp", ["http://[::1]:9000", "http://mcp_server:8000"])
def test_eine_nicht_ausdrueckbare_herkunft_wird_gemeldet(mcp, caplog):
    """IPv6-Literale und Unterstriche kennt die Host-Grammatik der CSP nicht; der
    Browser verwürfe die Quelle. Sie fällt weg — aber nicht mehr still."""
    from boerdi.api.studio_static import studio_csp

    with caplog.at_level("WARNING"):
        regel = studio_csp(mcp)
    assert "connect-src 'self';" in regel
    assert "lässt sich in der CSP nicht ausdrücken" in caplog.text
