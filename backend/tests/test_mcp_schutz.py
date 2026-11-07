"""Plan 2026-11-07 (Stabilität der MCP-Anbindung), Paket N1: Überlast und Ausfall.

* CB-2: 429/503 des Servers → Art ``busy`` mit der Wartezeit aus ``Retry-After``; der Client
  wiederholt nicht sofort, sondern wartet höchstens eine kurze Wartezeit ab.
* CB-3: Ausfall-Schalter je Server, Probe über ``GET /ready``.
* CB-5: Budget-Wächter — der Chatbot läuft nicht selbst in das 429.
* S1/CB-7: der Client-Schlüssel geht nur an den primären Server.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from boerdi.services.mcp import client, http_fabrik, schutz, transport, wiederholung

URL = transport.resolve_mcp_url()


def _status_fehler(status: int, retry_after: str | None = None) -> BaseException:
    anfrage = httpx.Request("POST", URL)
    koepfe = {"Retry-After": retry_after} if retry_after else {}
    fehler = httpx.HTTPStatusError("x", request=anfrage,
                                   response=httpx.Response(status, request=anfrage,
                                                           headers=koepfe))
    return ExceptionGroup("tg", [ExceptionGroup("tg", [fehler])])


class _Sitzung:
    def __init__(self, ausnahme: BaseException | None = None) -> None:
        self.ausnahme = ausnahme
        self.aufrufe = 0

    async def call_tool(self, name, arguments=None):
        self.aufrufe += 1
        if self.ausnahme is not None:
            raise self.ausnahme
        from mcp.types import CallToolResult, TextContent
        return CallToolResult(content=[TextContent(type="text", text="ok")])


def _sitzung(monkeypatch, sitzung: _Sitzung) -> list[str]:
    geoeffnet: list[str] = []

    @asynccontextmanager
    async def _open(url):
        geoeffnet.append(url)
        yield sitzung

    monkeypatch.setattr(transport, "_open_session", _open)
    return geoeffnet


# ── CB-2: 429/503 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("status", "grund"), [(429, "rate_limited"), (503, "unavailable")])
def test_429_und_503_heissen_ausgelastet_mit_wartezeit(monkeypatch, status, grund):
    _sitzung(monkeypatch, _Sitzung(_status_fehler(status, "17")))
    out = asyncio.run(transport.call_tool("search_wlo_all", {}))
    assert out["error"] == {"message": f"ausgelastet ({grund})", "kind": "busy",
                            "grund": grund, "retry_after": 17}


def test_eine_kurze_wartezeit_wird_einmal_abgewartet(monkeypatch):
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: URL)
    sitzung = _Sitzung(_status_fehler(429, "1"))
    _sitzung(monkeypatch, sitzung)
    geschlafen: list[float] = []

    async def _schlafen(s):
        geschlafen.append(s)
        sitzung.ausnahme = None  # danach ist wieder Platz

    monkeypatch.setattr(wiederholung.asyncio, "sleep", _schlafen)
    text, art = asyncio.run(client.call_mcp_tool_status("wlo_x", {}, use_cache=False))
    assert (text, art) == ("ok", "")
    assert geschlafen == [1.0]
    assert sitzung.aufrufe == 2


def test_eine_lange_wartezeit_beendet_den_aufruf_ohne_wiederholung(monkeypatch):
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: URL)
    sitzung = _Sitzung(_status_fehler(429, "40"))
    _sitzung(monkeypatch, sitzung)
    text, art = asyncio.run(client.call_mcp_tool_status("wlo_x", {}, use_cache=False))
    assert art == "busy"
    assert sitzung.aufrufe == 1
    assert "ausgelastet" in text and "nichts ausgeführt" in text


def test_upstream_busy_des_repositorys_ist_ausgelastet(monkeypatch):
    monkeypatch.setattr(client, "_get_server_url_for_tool", lambda t: URL)
    aufrufe: list[dict] = []

    async def _rufen(tool, args=None, *, url=None):
        aufrufe.append(args)
        return {"error": {"message": "busy", "kind": "tool", "structured": {
            "error": {"code": "upstream_busy", "retryAfter": 10, "message": "busy"}}}}

    monkeypatch.setattr(transport, "call_tool", _rufen)
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_x", {}, use_cache=False))
    assert (antwort.art, antwort.code) == ("busy", "upstream_busy")
    assert len(aufrufe) == 1  # 10 s > MCP_BUSY_RETRY_MAX_S


def test_upstream_busy_nach_der_einloesung_ist_keine_einladung(monkeypatch):
    """S3: ``requiresNewPreview`` — derselbe Aufruf bekäme nur dieselbe Antwort."""
    fehler = {"error": {"kind": "tool", "structured": {"error": {
        "code": "upstream_busy", "retryAfter": 1, "requiresNewPreview": True}}}}
    assert wiederholung.kurze_wartezeit(fehler) is None


# ── CB-3: Ausfall-Schalter ───────────────────────────────────────────────────
def test_drei_transportfehler_oeffnen_den_schalter(monkeypatch):
    sitzung = _Sitzung(OSError("weg"))
    geoeffnet = _sitzung(monkeypatch, sitzung)
    for _ in range(3):
        assert asyncio.run(transport.call_tool("wlo_x", {}))["error"]["kind"] == "transport"
    out = asyncio.run(transport.call_tool("wlo_x", {}))
    assert out["error"]["grund"] == "breaker"
    assert len(geoeffnet) == 3  # der vierte ging nicht hinaus


def test_nach_der_frist_entscheidet_die_bereitschaftsprobe(monkeypatch):
    uhr = [1000.0]
    monkeypatch.setattr(schutz, "_jetzt", lambda: uhr[0])
    sitzung = _Sitzung(OSError("weg"))
    _sitzung(monkeypatch, sitzung)
    for _ in range(3):
        asyncio.run(transport.call_tool("wlo_x", {}))
    proben: list[str] = []
    bereit = [False]

    async def _bereit(url):
        proben.append(url)
        return bereit[0]

    monkeypatch.setattr(schutz, "_bereit", _bereit)
    uhr[0] += 31
    assert asyncio.run(transport.call_tool("wlo_x", {}))["error"]["grund"] == "breaker"
    assert proben == [URL]
    uhr[0] += 31
    bereit[0] = True
    sitzung.ausnahme = None
    assert asyncio.run(transport.call_tool("wlo_x", {})) == {
        "result": {"content": [{"type": "text", "text": "ok"}]}}
    assert schutz.ist_offen(URL) is False


def test_eine_antwort_des_servers_setzt_die_fehler_zurueck(monkeypatch):
    sitzung = _Sitzung(OSError("weg"))
    _sitzung(monkeypatch, sitzung)
    asyncio.run(transport.call_tool("wlo_x", {}))
    asyncio.run(transport.call_tool("wlo_x", {}))
    sitzung.ausnahme = None
    asyncio.run(transport.call_tool("wlo_x", {}))
    sitzung.ausnahme = OSError("weg")
    asyncio.run(transport.call_tool("wlo_x", {}))
    assert schutz.ist_offen(URL) is False


def test_429_oeffnet_den_schalter_nicht(monkeypatch):
    _sitzung(monkeypatch, _Sitzung(_status_fehler(429, "30")))
    for _ in range(4):
        out = asyncio.run(transport.call_tool("wlo_x", {}))
    assert out["error"]["grund"] == "rate_limited"


@pytest.mark.parametrize(("status", "rumpf", "erwartet"), [
    (200, {"status": "ready", "upstream": "ok"}, True),
    (503, {"status": "not_ready", "upstream": "slow"}, True),
    (503, {"status": "not_ready", "upstream": "unreachable"}, False),
    (404, None, True),
])
def test_die_probe_liest_ready(monkeypatch, status, rumpf, erwartet):
    def _antwort(anfrage: httpx.Request) -> httpx.Response:
        assert anfrage.url.path == "/ready"
        return httpx.Response(status, json=rumpf) if rumpf else httpx.Response(status)

    echt = httpx.AsyncClient
    monkeypatch.setattr(schutz.httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(_antwort), **kw))
    assert asyncio.run(schutz._bereit("https://mcp.example/mcp")) is erwartet


def test_das_nachholen_geht_am_offenen_schalter_vorbei(monkeypatch):
    """Review 2026-11-07, Befund 3: der eigene Fehler eines bestätigten Schreibaufrufs öffnet den
    Schalter — die Antwort nachzuholen muss trotzdem gehen."""
    _sitzung(monkeypatch, _Sitzung())
    for _ in range(3):
        schutz.melde_fehler(URL)
    assert asyncio.run(transport.call_tool("wlo_x", {}))["error"]["grund"] == "breaker"
    assert "result" in asyncio.run(transport.call_tool("wlo_x", {}, nachholen=True))


@pytest.mark.parametrize(("url", "erwartet"), [
    ("https://mcp.example/mcp", "https://mcp.example"),
    ("https://gw.example/wlo/mcp/", "https://gw.example/wlo"),
    ("https://gw.example/wlo", "https://gw.example/wlo"),
])
def test_die_wurzel_behaelt_einen_pfad(url, erwartet):
    """Review 2026-11-07, Befund 5: Block und Client-Schlüssel nur an den eigenen Dienst."""
    assert schutz.wurzel(url) == erwartet


# ── CB-5: Budget ─────────────────────────────────────────────────────────────
def test_das_budget_laesst_hoechstens_rpm_aufrufe_je_minute(monkeypatch):
    monkeypatch.setenv("MCP_BUDGET_RPM", "2")
    monkeypatch.setenv("MCP_BUDGET_WAIT_S", "0")
    geoeffnet = _sitzung(monkeypatch, _Sitzung())
    ergebnisse = [asyncio.run(transport.call_tool("wlo_x", {})) for _ in range(3)]
    assert "result" in ergebnisse[0] and "result" in ergebnisse[1]
    assert ergebnisse[2]["error"]["grund"] == "budget"
    assert len(geoeffnet) == 2


def test_das_budget_wartet_auf_einen_freien_platz(monkeypatch):
    monkeypatch.setenv("MCP_BUDGET_RPM", "1")
    monkeypatch.setenv("MCP_BUDGET_WAIT_S", "5")
    uhr = [0.0]
    monkeypatch.setattr(schutz, "_jetzt", lambda: uhr[0])

    async def _schlafen(s):
        uhr[0] += s

    monkeypatch.setattr(schutz.asyncio, "sleep", _schlafen)
    assert asyncio.run(schutz.budget_platz(URL)) is True
    uhr[0] = 57.0  # in 3 s wird der Platz frei
    assert asyncio.run(schutz.budget_platz(URL)) is True
    assert uhr[0] == pytest.approx(60.0)


def test_fremde_server_zaehlen_nicht_am_budget(monkeypatch):
    monkeypatch.setenv("MCP_BUDGET_RPM", "1")
    monkeypatch.setenv("MCP_BUDGET_WAIT_S", "0")
    _sitzung(monkeypatch, _Sitzung())
    for _ in range(3):
        assert "result" in asyncio.run(
            transport.call_tool("x", {}, url="https://fremd.example/mcp"))


# ── S1/CB-7: Client-Schlüssel ────────────────────────────────────────────────
def test_der_client_schluessel_geht_an_den_primaeren_server(monkeypatch):
    monkeypatch.setenv("MCP_CLIENT_KEY", "k" * 40)
    c = transport._client_fabrik(URL)(headers={"A": "b"})
    assert c.headers[http_fabrik.CLIENT_KEY_HEADER] == "k" * 40
    assert c.timeout.connect == 5.0


def test_fremde_server_bekommen_keinen_client_schluessel(monkeypatch):
    monkeypatch.setenv("MCP_CLIENT_KEY", "k" * 40)
    c = transport._client_fabrik("https://fremd.example/mcp")(headers={})
    assert http_fabrik.CLIENT_KEY_HEADER not in c.headers
    assert c.timeout.connect == 5.0


def test_ohne_schluessel_kein_kopf(monkeypatch):
    monkeypatch.delenv("MCP_CLIENT_KEY", raising=False)
    assert http_fabrik.client_schluessel_kopf() == {}
