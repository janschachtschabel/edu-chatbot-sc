"""P1-3: Studio-API-Key-Auth — port of ALT tests/test_auth.py.

Fail-closed (ALT Audit T1): no configured key => 503 unless the explicit
dev opt-in BOERDI_ALLOW_OPEN_ADMIN is set; configured key => timing-safe
compare, header-only (never query params).
"""

from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from boerdi.api import deps


def _call(header=None):
    return asyncio.run(deps.require_studio_key(x_studio_key=header))


def test_no_key_configured_fails_closed(monkeypatch):
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _call(header=None)
    assert exc.value.status_code == 503


def test_no_key_with_dev_optin_is_noop(monkeypatch):
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    assert _call(header=None) is None


def test_change_me_placeholder_fails_closed(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "CHANGE_ME")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _call(header="CHANGE_ME")
    assert exc.value.status_code == 503


def test_correct_key_in_header_passes(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    assert _call(header="s3cr3t") is None


def test_query_key_not_accepted(monkeypatch):
    # key is header-only (never query params -> proxy/Referer logs)
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    assert "key" not in inspect.signature(deps.require_studio_key).parameters


def test_wrong_key_raises_401(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    with pytest.raises(HTTPException) as exc:
        _call(header="falsch")
    assert exc.value.status_code == 401


def test_missing_key_when_configured_raises_401(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    with pytest.raises(HTTPException):
        _call(header=None)


def test_key_is_stripped(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "  s3cr3t  ")
    assert _call(header="s3cr3t") is None


def test_http_matrix_on_studio_route(monkeypatch):
    """401/403-Matrix (spec P1-3) over a real studio-gated route. Post-P7 all the
    studio ROUTERS are implemented; the remaining studio-gated 501 stub is
    GET /api/debug/mcp-test (P5-1).

    **Der Cache muss hier von Hand fallen** (gemessen 2026-08-18). Der
    autouse-``_fresh_settings_cache`` leert ihn zwar, aber die Fixture-Phase
    fuellt ihn danach wieder: am Rumpfbeginn steht ``currsize=1`` mit dem LEEREN
    Schluessel. Ohne den Aufruf unten liest ``require_studio_key`` genau diesen
    und antwortet 503 („Admin abgeschaltet, fail-closed") statt 401 — der Test
    mass also die Testumgebung, nicht das Produkt. Gegenprobe: derselbe Ablauf
    ausserhalb von pytest liefert 401/501 wie erwartet.
    """
    from fastapi.testclient import TestClient

    from boerdi.main import create_app
    from boerdi.settings import get_settings

    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/api/debug/mcp-test").status_code == 401
    assert client.get("/api/debug/mcp-test", headers={"X-Studio-Key": "falsch"}).status_code == 401
    # correct key reaches the stub (501 until P5-1)
    assert client.get("/api/debug/mcp-test", headers={"X-Studio-Key": "s3cr3t"}).status_code == 501
    # Eine oeffentliche Route bleibt offen: ohne Schluessel erreicht die Anfrage
    # ihren Handler. Geprueft wird genau das — NICHT, was der Handler dann sagt.
    #
    # Bis 2026-08-18 stand hier ``== 503`` mit der Begruendung „im Test gibt es
    # kein Widget-Bundle". Das war eine Aussage ueber die WERKBANK, nicht ueber
    # den Code: wer einmal ``npm run build:widget`` laufen liess, bekam 200 und
    # einen roten Test. Beide Antworten beweisen dasselbe — ein gesperrter
    # Endpunkt haette laengst 401 gesagt.
    assert client.get("/widget/boerdi-widget.js").status_code in (200, 503)
