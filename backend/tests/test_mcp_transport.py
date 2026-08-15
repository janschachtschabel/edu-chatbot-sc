"""Charakterisierungs-Tests für die SDK-basierte MCP-Transportschicht (5-1b).

ALT ``mcp_transport.py`` war ein hand-gerolltes HTTP/JSON-RPC + SSE + Handshake
(317 Z.); im Neubau übernimmt das offizielle ``mcp``-SDK (streamable HTTP) diese
Arbeit. Die ALT-``_json_rpc``-Tests prüfen genau die entfernte Handroll-Schicht
und sind daher NICHT portierbar. Diese Tests pinnen stattdessen die verbliebene
Adapter-Logik: URL-Auflösung, Result-Normalisierung auf die ALT-``_json_rpc``-
Dict-Form (`{"result": {"content": …}}` / `{"error": {"message": …}}`, damit
5-1c ``call_mcp_tool`` nahezu verbatim portiert), Fehler-Mapping und das
Discovery-Mapping. Der SDK-Draht (``streamablehttp_client`` → ``ClientSession``
→ ``initialize``) steckt in ``_open_session`` und wird hier gefaked.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from boerdi.services.mcp import transport as transport_mod
from boerdi.services.mcp.transport import (
    _DEFAULT_MCP_URL,
    call_tool,
    discover_server_tools,
    resolve_mcp_url,
)


class _FakeSession:
    """Steht für eine initialisierte ``ClientSession``. Zeichnet den letzten
    ``call_tool``-Aufruf auf und liefert vorprogrammierte Ergebnisse."""

    def __init__(self, *, call_result=None, call_exc=None, tools=None):
        self._call_result = call_result
        self._call_exc = call_exc
        self._tools = tools or []
        self.received: tuple | None = None

    async def call_tool(self, name, arguments=None):
        self.received = (name, arguments)
        if self._call_exc is not None:
            raise self._call_exc
        return self._call_result

    async def list_tools(self):
        return ListToolsResult(tools=self._tools)


def _patch_session(monkeypatch, fake: _FakeSession) -> None:
    @asynccontextmanager
    async def _fake_open(url):
        yield fake

    monkeypatch.setattr(transport_mod, "_open_session", _fake_open)


def _patch_settings(monkeypatch, url: str) -> None:
    monkeypatch.setattr(
        transport_mod, "get_settings", lambda: SimpleNamespace(mcp_server_url=url)
    )


# ── resolve_mcp_url ─────────────────────────────────────────────────────
def test_resolve_url_explicit_override_strips_trailing_slash():
    assert resolve_mcp_url("https://other.example/mcp/") == "https://other.example/mcp"


def test_resolve_url_default_from_settings(monkeypatch):
    _patch_settings(monkeypatch, "https://configured.example/mcp/")
    assert resolve_mcp_url() == "https://configured.example/mcp"


def test_resolve_url_empty_setting_falls_back_to_default(monkeypatch):
    # Docker-Compose-Falle: ``${MCP_SERVER_URL:-}`` reicht einen leeren String
    # → wie unset behandeln und auf den Default-Server fallen.
    _patch_settings(monkeypatch, "")
    assert resolve_mcp_url() == _DEFAULT_MCP_URL


# ── call_tool: Result-Normalisierung ────────────────────────────────────
def test_call_tool_success_normalizes_text_content(monkeypatch):
    result = CallToolResult(
        content=[TextContent(type="text", text="ERGEBNIS")], isError=False
    )
    fake = _FakeSession(call_result=result)
    _patch_session(monkeypatch, fake)
    out = asyncio.run(call_tool("search_wlo_content", {"query": "x"}, url="https://u/mcp"))
    assert out == {"result": {"content": [{"type": "text", "text": "ERGEBNIS"}]}}


def test_call_tool_passes_name_and_args(monkeypatch):
    fake = _FakeSession(call_result=CallToolResult(content=[], isError=False))
    _patch_session(monkeypatch, fake)
    asyncio.run(call_tool("get_node_details", {"nodeId": "abc"}, url="https://u/mcp"))
    assert fake.received == ("get_node_details", {"nodeId": "abc"})


def test_call_tool_is_error_maps_to_error_dict(monkeypatch):
    result = CallToolResult(
        content=[TextContent(type="text", text="tool kaputt")], isError=True
    )
    _patch_session(monkeypatch, _FakeSession(call_result=result))
    out = asyncio.run(call_tool("search_wlo_content", {"query": "x"}))
    assert "error" in out and out["error"]["message"] == "tool kaputt"
    assert "result" not in out


def test_call_tool_transport_exception_maps_to_error_dict(monkeypatch):
    _patch_session(monkeypatch, _FakeSession(call_exc=RuntimeError("connect refused")))
    out = asyncio.run(call_tool("search_wlo_content", {"query": "x"}))
    assert "error" in out and "connect refused" in out["error"]["message"]


# ── Die Fehler-ART (2026-08-15) ─────────────────────────────────────────
#
# Beide Zweige oben liefern dasselbe Fehler-Dict — und genau daran scheiterte
# die Schreib-Abnahme: „der Server hat abgelehnt" und „wir haben nie etwas
# gehört" sind für den Aufrufer verschiedene Sachlagen. Beim ersten steht fest,
# dass nichts geändert wurde; beim zweiten steht das gerade NICHT fest.
#
# Nur der Transport kann sie unterscheiden — er weiss, welchen Zweig er nahm.


def test_ein_werkzeug_fehler_traegt_die_art_tool(monkeypatch):
    result = CallToolResult(
        content=[TextContent(type="text", text="Schlüssel abgelaufen")], isError=True
    )
    _patch_session(monkeypatch, _FakeSession(call_result=result))
    out = asyncio.run(call_tool("wlo_create_collection", {}))
    assert out["error"]["kind"] == "tool", (
        "Der Server hat geantwortet — es steht fest, dass er ablehnte"
    )


def test_ein_transport_fehler_traegt_die_art_transport(monkeypatch):
    _patch_session(monkeypatch, _FakeSession(call_exc=TimeoutError("read timeout")))
    out = asyncio.run(call_tool("wlo_create_collection", {}))
    assert out["error"]["kind"] == "transport", (
        "Keine Antwort — ob geschrieben wurde, ist von hier aus offen"
    )


def test_die_meldung_bleibt_neben_der_art_stehen(monkeypatch):
    # Gegenprobe: die Art kommt HINZU, sie ersetzt nichts. Der Text reist
    # weiter zum Modell und in die Protokolle.
    result = CallToolResult(
        content=[TextContent(type="text", text="tool kaputt")], isError=True
    )
    _patch_session(monkeypatch, _FakeSession(call_result=result))
    out = asyncio.run(call_tool("t", {}))
    assert out["error"]["message"] == "tool kaputt"


def test_call_tool_multiple_text_blocks_joined_in_order(monkeypatch):
    result = CallToolResult(
        content=[
            TextContent(type="text", text="A"),
            TextContent(type="text", text="B"),
        ],
        isError=False,
    )
    _patch_session(monkeypatch, _FakeSession(call_result=result))
    out = asyncio.run(call_tool("t", {}))
    assert out["result"]["content"] == [
        {"type": "text", "text": "A"},
        {"type": "text", "text": "B"},
    ]


# ── discover_server_tools ───────────────────────────────────────────────
def test_discover_maps_tools_and_filters_unnamed(monkeypatch):
    tools = [
        Tool(name="search_wlo_content", description="d1", inputSchema={"type": "object"}),
        Tool(name="", description="anon", inputSchema={"type": "object"}),
        Tool(name="wlo_health_check", description=None, inputSchema={"type": "object"}),
    ]
    _patch_session(monkeypatch, _FakeSession(tools=tools))
    out = asyncio.run(discover_server_tools("https://u/mcp"))
    assert out == [
        {"name": "search_wlo_content", "description": "d1"},
        {"name": "wlo_health_check", "description": ""},
    ]


# ── Die Vorgabe-Adresse steht an EINER Stelle ───────────────────────────

def test_die_vorgabe_adresse_steht_nur_an_einer_stelle():
    """Der Rückfall darf keine zweite Abschrift der URL sein.

    Er greift genau dann, wenn ``MCP_SERVER_URL`` leer ankommt — und leer
    reicht ``compose.prod.yml`` sie per Vorgabe durch (``${MCP_SERVER_URL:-}``).
    Stünde die Adresse hier ein zweites Mal, träfe ein Server-Wechsel, der nur
    ``settings.py`` anfasst, ausgerechnet diesen Fall nicht: das Deployment
    spräche still mit dem alten Server weiter. Genau davor warnte der Kommentar
    an dieser Stelle — jetzt trägt es der Code.
    """
    from pathlib import Path

    from boerdi.settings import Settings

    vorgabe = Settings.model_fields["mcp_server_url"].default
    quelle = Path(transport_mod.__file__).read_text(encoding="utf-8")

    assert vorgabe not in quelle, (
        "Die Vorgabe-Adresse steht als Literal in transport.py — sie gehört "
        "einmal nach settings.py und wird von dort gelesen."
    )
    # Und der Rückfall zeigt trotzdem dorthin.
    assert _DEFAULT_MCP_URL == vorgabe
