"""MCP-Transportschicht auf Basis des offiziellen ``mcp``-SDK (streamable HTTP).

Ersetzt ALT ``app/services/mcp_transport.py`` (317 Z. hand-gerolltes HTTP/JSON-RPC
2.0 + SSE-Parsing + Protokoll-Handshake + Per-URL-Session-State): das SDK
übernimmt Framing, SSE, Handshake und Session-ID-Verwaltung, sodass
``_json_rpc``/``_parse_sse``/``_parse_response``/``_ensure_initialized_with_session``
ersatzlos entfallen. Übrig bleibt ein dünner Adapter.

Bewusste Design-Entscheidungen ggü. ALT (Transport-Swap ist laut Spec §5-1 die
gewollte Verbesserung — funktionale Parität bleibt: jeder Call macht weiterhin
Handshake→Call→Result):

* **Session pro Call statt ALT-Keep-Alive.** ALTs geteilter httpx-Pool + Session-
  ID-Header war unter Nebenläufigkeit sicher (httpx ist thread-/task-safe, der
  Server hält den Session-State). Die SDK-``ClientSession`` ist dagegen ein
  *statefuller* Client-seitiger Protokoll-Objekt (eigene Streams + Request-ID-
  Zähler) — sie über nebenläufige Multi-User-Requests zu teilen würde die
  Nachrichten verschränken. Pro-Call-Session ist daher hier die KORREKTE Wahl
  (und Regel-3-sauber: kein modul-globaler Session-State). Der 5-1a-TTL-Cache
  sitzt VOR dem Transport → Handshakes fallen nur bei Cache-Misses an.
* **Rück-Normalisierung auf die ALT-``_json_rpc``-Dict-Form** (`{"result":
  {"content": [...]}}` bzw. `{"error": {"message": ...}}`). So bleibt die
  SDK-Kopplung ausschließlich in diesem Modul, und 5-1c ``call_mcp_tool`` (das
  auf ``result["result"]["content"]`` arbeitet) portiert nahezu verbatim.

``httpx_client_factory`` ist seit C1 (2026-08-10) belegt: ``services/mcp/auth``
liefert die Fabrik, die den Zugangsblock als ``Authorization``-Kopfzeile
mitschickt (ohne Block ist es die SDK-Standardfabrik, unverändert). Alle
Aufrufwege — ``call_tool`` wie ``discover_server_tools`` — laufen über
``_open_session``, also über genau diese eine Naht. Den Block bekommt dort nur
der primäre Server (:func:`_client_fabrik`).

``simplify:`` (Perf-Feinschliff, spätere P5-Iteration): geteilter httpx-Keep-
Alive-Pool — dieselbe Fabrik könnte einen wiederverwendeten Client liefern und
so TCP/TLS über Cache-Miss-Calls amortisieren (ALTs ``MCP_MAX_CONNECTIONS``/
5s-Connect-Cap würden dort andocken). Aktuell: ein Client pro Call —
einfachste, cluster-saubere Variante.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamablehttp_client
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_PARAMS, METHOD_NOT_FOUND

from boerdi.obs import metrics
from boerdi.obs.log_inhalt import inhalt
from boerdi.services.mcp.http_fabrik import McpHttpClientFactory, build_http_client_factory
from boerdi.settings import Settings, get_settings

logger = logging.getLogger(__name__)


# Default-MCP-URL (Fallback), wenn weder eine explizite URL noch die Einstellung
# ``mcp_server_url`` etwas Nutzbares liefert — robust gegen die Docker-Compose-
# Falle ``${MCP_SERVER_URL:-}`` (leerer String) und Trailing-Slashes.
#
# GELESEN, nicht abgeschrieben (2026-08-12). Bis hierher stand die Adresse ein
# zweites Mal als Literal da, gleichgehalten nur durch einen Kommentar. Ein
# Server-Wechsel, der ``settings.py`` anfasst und diese Zeile übersieht, träfe
# ausgerechnet den Fall nicht, für den der Rückfall existiert — und
# ``compose.prod.yml`` reicht ``MCP_SERVER_URL`` per Vorgabe leer durch, also
# spräche das Deployment still mit dem alten Server weiter. Genau davor warnte
# der frühere Kommentar (W7b); jetzt trägt es der Code. Wächter:
# ``test_die_vorgabe_adresse_steht_nur_an_einer_stelle``.
#
# Die KLASSE, nicht ``get_settings()``: gefragt ist die Vorgabe des Feldes, nicht
# der geladene Wert — der ist an dieser Stelle ja gerade leer.
_DEFAULT_MCP_URL: str = str(Settings.model_fields["mcp_server_url"].default)


def resolve_mcp_url(url: str | None = None) -> str:
    """Eine explizite URL oder die konfigurierte Default-MCP-URL, ohne Trailing-Slash.

    Leerer/whitespace-only Konfigurationswert wird wie „unset" behandelt und
    fällt auf ``_DEFAULT_MCP_URL`` zurück (ALT-Parität).
    """
    if url:
        return url.rstrip("/")
    configured = (get_settings().mcp_server_url or "").strip().rstrip("/")
    return configured or _DEFAULT_MCP_URL


def _client_fabrik(url: str) -> McpHttpClientFactory:
    """Die httpx-Fabrik für ``url``: mit Zugangsblock nur für den primären Server.

    Weitere Server der Registry und die Discover-Adresse aus dem Studio sind
    fremde Gegenstellen. Mit derselben Fabrik bekämen sie das Dienst-Token oder
    den persönlichen Zugangsblock der Person (Audit 2026-09-29, A-M2/B-M2).
    """
    if url.rstrip("/") == resolve_mcp_url().rstrip("/"):
        return build_http_client_factory()
    return _ohne_umleitung


def _ohne_umleitung(headers=None, timeout=None, auth=None):  # noqa: ANN001 — SDK-Fabrikform
    """Die SDK-Fabrik ohne Umleitungen (Review Paket 11, #2).

    ``create_mcp_http_client`` folgt Umleitungen immer. Ein fremder Server könnte mit 307/308 —
    Methode und Rumpf bleiben — auf eine interne Adresse weiterleiten und so die Adressprüfung
    (``assert_public_url``) umgehen; die Antwort käme ins Modell.
    """
    client = create_mcp_http_client(headers=headers, timeout=timeout, auth=auth)
    client.follow_redirects = False
    return client


@asynccontextmanager
async def _open_session(url: str) -> AsyncIterator[ClientSession]:
    """Öffne eine frisch initialisierte ``ClientSession`` gegen ``url``.

    Der SDK-Draht (streamable-HTTP-Streams → Session → Handshake). Pro Call
    geöffnet und wieder geschlossen (siehe Modul-Docstring). Reiner SDK-Seam —
    in Tests durch eine Fake-Session ersetzt.
    """
    async with streamablehttp_client(
        url, httpx_client_factory=_client_fabrik(url)
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def _frist_s() -> float:
    """Gesamtfrist eines Werkzeugaufrufs (``MCP_CALL_TIMEOUT_S``) — Test-Naht."""
    return get_settings().mcp_call_timeout_s


def _cause_text(exc: BaseException) -> str:
    """Die lesbare Ursache einer Transport-Ausnahme.

    Das SDK bündelt Fehler in einer ``ExceptionGroup``, deren ``str()`` nur
    „unhandled errors in a TaskGroup (1 sub-exception)" lautet — die eigentliche
    Ursache steckt in der Unterausnahme. Gemessen 2026-08-10 mit einem
    unbrauchbaren Zugangsblock gegen den echten Server: der ``401 Unauthorized``
    war so nicht sichtbar, und ein Betreiber mit falschem Block hätte bei jeder
    Suche nur den nichtssagenden Satz gesehen.

    Gewöhnliche Ausnahmen bleiben wortgleich ``str(exc)`` (Bestandsverhalten).
    """
    subs = getattr(exc, "exceptions", None)
    if subs:
        return "; ".join(_cause_text(sub) for sub in subs)
    return str(exc)


#: JSON-RPC-Fehler, bei denen der Server nachweislich nichts ausgeführt hat:
#: unbekannte Methode bzw. unbekanntes Werkzeug, ungültige Parameter.
_NICHT_AUSGEFUEHRT = frozenset({METHOD_NOT_FOUND, INVALID_PARAMS})


def _abgelehnt_ohne_ausfuehrung(exc: BaseException) -> McpError | None:
    """Der ``McpError`` in ``exc``, wenn der Server damit ablehnte, ohne
    auszuführen (Paket 6, B4) — auch in einer ``ExceptionGroup`` des SDK.

    Ein interner Fehler (-32603) zählt nicht: der Server kann mitten im
    Werkzeug gescheitert sein, ob geschrieben wurde, ist offen.
    """
    if isinstance(exc, McpError):
        return exc if exc.error.code in _NICHT_AUSGEFUEHRT else None
    for sub in getattr(exc, "exceptions", None) or ():
        treffer = _abgelehnt_ohne_ausfuehrung(sub)
        if treffer is not None:
            return treffer
    return None


#: HTTP-Status, mit dem der Server den Zugangsblock abweist (Paket 10, Kurzaudit A-3).
_ABGEWIESEN = frozenset({401, 403})


def _abgewiesen(exc: BaseException) -> int | None:
    """Der HTTP-Status, wenn der Server den Zugang abwies — auch tief in einer
    ``ExceptionGroup`` des SDK (die ``initialize``-Anfrage läuft dort als Kind-Task)."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _ABGEWIESEN:
        return exc.response.status_code
    for sub in getattr(exc, "exceptions", None) or ():
        if (status := _abgewiesen(sub)) is not None:
            return status
    return None


def _text_blocks(result: Any) -> list[dict[str, str]]:
    """Text-Content-Blöcke eines ``CallToolResult`` in die ALT-Dict-Form bringen.

    Nur Text-Blöcke (``type == "text"``) — wie ALT, das Nicht-Text-Parts verwarf;
    die WLO-Tools liefern ausschließlich Text.
    """
    return [
        {"type": "text", "text": block.text}
        for block in result.content
        if getattr(block, "type", None) == "text"
    ]


async def call_tool(
    tool_name: str, arguments: dict[str, Any] | None = None, *, url: str | None = None
) -> dict[str, Any]:
    """Rufe ein MCP-Tool über das SDK und liefere das ALT-``_json_rpc``-Result-Dict.

    Erfolg → ``{"result": {"content": [{"type": "text", "text": …}, …]}}``.
    Tool-Fehler (``isError``) oder Transportfehler (Exception) →
    ``{"error": {"message": …, "kind": …}}`` — genau die Form, die
    ``call_mcp_tool`` (5-1c) für seinen Retry-/Fehlerpfad erwartet.

    **``kind`` ist neu (2026-08-15)** und trennt zwei Sachlagen, die für einen
    Aufrufer ohne Modell dahinter verschieden sind:

    * ``"tool"`` — der Server hat **geantwortet** und abgelehnt. Bei einem
      Schreibwerkzeug steht damit fest, dass nichts geändert wurde.
    * ``"transport"`` — es kam **keine Antwort** (Verbindung, Zeitüberschreitung,
      Abbruch). Ob geschrieben wurde, ist offen.
    * ``"timeout"`` — Sonderfall davon (Paket 4, B2): die Gesamtfrist
      ``MCP_CALL_TIMEOUT_S`` lief ab. Ob geschrieben wurde, ist ebenso offen; ein
      zweiter Versuch hinge aber genauso lange und unterbleibt deshalb.
    * ``"auth"`` — der Server weist den Zugangsblock ab (401/403, Paket 10). Nichts
      wurde ausgeführt; ein zweiter Versuch mit demselben Block hülfe nicht.

    Nur diese Funktion kann das unterscheiden: eine Ebene höher sind beide Fälle
    dasselbe Dict und danach derselbe String. Gelesen wird es über
    ``client.call_mcp_tool_status``; daran hängt, ob die Schreib-Abnahme dem
    Nutzer „es wurde nichts geändert" sagen darf oder „bitte nachsehen".
    """
    target_url = resolve_mcp_url(url)
    beginn = time.perf_counter()
    ergebnis = await _call_tool(tool_name, arguments, target_url)
    # Paket 17 (D3): je Server und Art — ``ok`` oder die ``kind`` des Fehlers.
    art = ergebnis["error"].get("kind", "transport") if "error" in ergebnis else "ok"
    metrics.mcp_aufruf(target_url, art, time.perf_counter() - beginn)
    return ergebnis


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None, target_url: str
) -> dict[str, Any]:
    frist = _frist_s()
    grenze = asyncio.timeout(frist)
    try:
        async with grenze, _open_session(target_url) as session:
            result = await session.call_tool(tool_name, arguments or {})
    except Exception as exc:  # noqa: BLE001 — Transportfehler → Fehler-Dict (ALT-Parität)
        if isinstance(exc, TimeoutError) and grenze.expired():
            # Die EIGENE Frist (Paket 4, B2) — nicht eine Zeitüberschreitung aus
            # dem SDK, die bleibt ``transport``. Eigene Art, weil ein zweiter
            # Versuch genauso lange hinge (``client.call_mcp_tool_status``).
            logger.error("MCP tool %s @ %s: keine Antwort binnen %g s",
                         tool_name, target_url, frist)
            return {"error": {"message": f"keine Antwort binnen {frist:g} s",
                              "kind": "timeout"}}
        status = _abgewiesen(exc)
        if status is not None:
            # Kein Block im Log — nur, dass er abgewiesen wurde (``services/mcp/auth``).
            logger.warning("MCP tool %s @ %s: Zugang abgewiesen (%s)",
                           tool_name, target_url, status)
            return {"error": {"message": f"Zugang abgewiesen ({status})", "kind": "auth"}}
        abgelehnt = _abgelehnt_ohne_ausfuehrung(exc)
        if abgelehnt is not None:
            # Der Server hat geantwortet und nichts ausgeführt — wie ``isError``
            # unten, nur als JSON-RPC-Fehler gemeldet. Kein ``transport``: der
            # Aufrufer wiederholte sonst dieselbe Ablehnung.
            # Paket 18C/D: ``-32602`` wiederholt die Eingabe — der Text steht in der Zugakte.
            logger.error("MCP tool %s rejected @ %s: %s", tool_name, target_url,
                         inhalt(abgelehnt.error.message))
            return {"error": {"message": abgelehnt.error.message, "kind": "tool"}}
        grund = _cause_text(exc)
        logger.error("MCP tool %s transport error @ %s: %s", tool_name, target_url, grund)
        return {"error": {"message": grund, "kind": "transport"}}

    if result.isError:
        message = " ".join(b["text"] for b in _text_blocks(result)) or "tool error"
        # Paket 18C/D: der Server wiederholt in Prüffehlern die Eingabe (-32602) — der Text
        # steht in der Zugakte des Zugs, hier nur seine Länge.
        logger.error("MCP tool %s error @ %s: %s", tool_name, target_url, inhalt(message))
        return {"error": {"message": message, "kind": "tool"}}

    normalisiert: dict[str, Any] = {"content": _text_blocks(result)}
    # Der strukturierte Teil reist nur mit, wenn das Werkzeug einen geschickt
    # hat (E3). 40 der 41 Werkzeuge tun das nicht, und ein Schlüssel mit
    # ``None`` wäre für jeden Leser eine Formänderung ohne Gegenwert. Wer ihn
    # auswertet: ``client.call_mcp_tool`` → ``domain/prepared_write.py``.
    if getattr(result, "structuredContent", None) is not None:
        normalisiert["structuredContent"] = result.structuredContent
    return {"result": normalisiert}


async def discover_server_tools(url: str) -> list[dict[str, str]]:
    """Verbinde zu einem MCP-Server, handshake, liste die Tools.

    Liefert ``[{"name", "description", "input_schema", "read_only"}, …]`` (namenlose Tools
    verworfen). Genutzt
    vom Studio beim Registrieren eines neuen MCP-Servers. Transportfehler
    propagieren (der aufrufende Endpoint fängt sie) — wie ALTs raise-on-failure.
    """
    async with _open_session(resolve_mcp_url(url)) as session:
        listing = await session.list_tools()
    # Paket 11 (E): Schema und Lesend-Markierung für „Werkzeuge übernehmen“ im Studio.
    return [
        {"name": tool.name, "description": tool.description or "",
         "input_schema": dict(tool.inputSchema or {}),
         "read_only": bool(tool.annotations and tool.annotations.readOnlyHint is True)}
        for tool in listing.tools
        if getattr(tool, "name", "")
    ]
