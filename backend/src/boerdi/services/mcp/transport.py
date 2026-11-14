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

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamablehttp_client
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_PARAMS, METHOD_NOT_FOUND

from boerdi.obs import metrics
from boerdi.obs.drossel import gedrosselt
from boerdi.obs.log_format import ausnahme_text
from boerdi.obs.log_inhalt import inhalt
from boerdi.services.mcp import schutz
from boerdi.services.mcp.http_fabrik import (
    McpHttpClientFactory,
    build_http_client_factory,
    mit_verbindungsfrist,
)
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
    client = create_mcp_http_client(headers=headers, timeout=mit_verbindungsfrist(timeout),
                                    auth=auth)
    client.follow_redirects = False
    return client


class _Sitzung(ClientSession):
    """Die SDK-Sitzung ohne Schema-Prüfung der Werkzeugantwort.

    Das SDK prüft eine erfolgreiche Antwort gegen das Ausgabeschema, wenn das Werkzeug eines
    veröffentlicht — und holt, um das zu wissen, ``tools/list``, sobald die Sitzung das Werkzeug
    nicht kennt. Wir öffnen je Aufruf eine frische Sitzung — die ganze Werkzeugliste kam also bei
    JEDEM Aufruf mit, auch ohne Schema: gemessen 2026-11-14 am Staging-MCP 0,25–0,33 s und
    171 KiB je Werkzeugaufruf (18 von 18).

    Gebraucht wird die Prüfung hier nicht: jede Antwort geht durch die eigenen Leser
    (``client``, ``parsers``), und eine Antwort, die ein nachhinkendes Schema knapp verfehlt,
    wurde durch sie zum Transportfehler statt zum Ergebnis. ``list_tools`` selbst bleibt
    (``discover_server_tools``).

    Die überschriebene Methode ist privat im SDK. Dass ``call_tool`` sie noch ruft, hält
    ``tests/test_mcp_keine_werkzeugliste_je_aufruf.py`` fest.
    """

    async def _validate_tool_result(self, name: str, result: Any) -> None:
        return None


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
        async with _Sitzung(read_stream, write_stream) as session:
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


def _status_fehler(exc: BaseException) -> httpx.HTTPStatusError | None:
    """Die HTTP-Antwort mit Fehlerstatus in ``exc`` — auch tief in einer ``ExceptionGroup`` des
    SDK (die ``initialize``-Anfrage läuft dort als Kind-Task)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc
    for sub in getattr(exc, "exceptions", None) or ():
        if (treffer := _status_fehler(sub)) is not None:
            return treffer
    return None


def _abgewiesen(exc: BaseException) -> int | None:
    """Der HTTP-Status, wenn der Server den Zugang abwies."""
    treffer = _status_fehler(exc)
    status = treffer.response.status_code if treffer is not None else None
    return status if status in _ABGEWIESEN else None


#: Plan 2026-11-07 (CB-2): 429 = Budget des Servers erschöpft, 503 = Server (oder sein
#: Vorschaltrechner) gerade nicht verfügbar. In beiden Fällen lief kein Werkzeug.
_AUSGELASTET = frozenset({429, 503})
#: So lange wartet niemand auf einen Server, der eine absurde Wartezeit nennt.
_WARTEZEIT_DECKEL_S = 600


def _wartezeit(antwort: httpx.Response) -> int | None:
    """``Retry-After`` in Sekunden (S2: der Rest des Fensters), gedeckelt — ``None`` ohne Angabe."""
    roh = (antwort.headers.get("retry-after") or "").strip()
    return min(int(roh), _WARTEZEIT_DECKEL_S) if roh.isdigit() else None


def ausgelastet(grund: str, retry_after: int | None = None) -> dict[str, Any]:
    """Das Fehler-Dict der Art ``busy``: nichts wurde ausgeführt, später noch einmal.

    ``grund``: ``rate_limited`` (429 des Servers), ``unavailable`` (503), ``budget`` (eigener
    Wächter, nichts gesendet), ``breaker`` (Ausfall-Schalter offen, nichts gesendet)."""
    fehler: dict[str, Any] = {"message": f"ausgelastet ({grund})", "kind": "busy",
                              "grund": grund}
    if retry_after is not None:
        fehler["retry_after"] = retry_after
    return {"error": fehler}


#: Paket 19 (N-15): Fehler, die der Betrieb kennt — Netz, Gegenstelle, Antwort des Servers.
#: Alles andere (``TypeError``, ``KeyError`` …) ist ein Programmfehler und bleibt ERROR.
_ERWARTBAR = (httpx.HTTPError, OSError, McpError, anyio.BrokenResourceError,
              anyio.ClosedResourceError, anyio.EndOfStream)
#: Höchstens eine Zeile je Server, Art und Minute; den Alarm trägt ``metrics.mcp_aufruf``.
_ABSTAND_S = 60.0


def _erwartbar(exc: BaseException) -> bool:
    """Ein Fehler aus :data:`_ERWARTBAR` — in einer Gruppe des SDK nur, wenn alle es sind."""
    kinder = getattr(exc, "exceptions", None)
    if kinder:
        return all(_erwartbar(k) for k in kinder)
    return isinstance(exc, _ERWARTBAR)


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
    tool_name: str, arguments: dict[str, Any] | None = None, *, url: str | None = None,
    nachholen: bool = False,
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
    ergebnis = await _call_tool(tool_name, arguments, target_url, nachholen=nachholen)
    # Paket 17 (D3): je Server und Art — ``ok`` oder die ``kind`` des Fehlers.
    art = ergebnis["error"].get("kind", "transport") if "error" in ergebnis else "ok"
    metrics.mcp_aufruf(target_url, art, time.perf_counter() - beginn)
    return ergebnis


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None, target_url: str, *, nachholen: bool = False,
) -> dict[str, Any]:
    # Plan 2026-11-07 (CB-3/CB-5): vor dem Senden — ein offener Schalter und ein volles Budget
    # beenden den Aufruf, ohne dass der Server ihn sieht. Außerhalb der Frist unten: Warten auf
    # einen Platz ist keine Zeitüberschreitung, nach der „vielleicht geschrieben“ gälte.
    # ``nachholen`` (S3, Review 2026-11-07, Befund 3): die Antwort eines bestätigten
    # Schreibaufrufs nachholen — auch wenn sein eigener Fehler den Schalter gerade geöffnet hat.
    if not nachholen and not await schutz.durchlassen(target_url):
        return ausgelastet("breaker")
    if target_url == resolve_mcp_url() and not await schutz.budget_platz(target_url):
        return ausgelastet("budget")
    ergebnis = await _call_tool_gesendet(tool_name, arguments, target_url)
    fehler = ergebnis.get("error") or {}
    if fehler.get("kind") in ("transport", "timeout") or fehler.get("grund") == "unavailable":
        schutz.melde_fehler(target_url)
    elif fehler.get("kind") != "busy":
        schutz.melde_erfolg(target_url)
    return ergebnis


async def _call_tool_gesendet(
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
            # Ohne Traceback (Paket 18E): die eigene Frist ist abgelaufen — ein
            # erwarteter Zustand, der Trace zeigte nur die Wartestelle. Paket 19 (N-15):
            # WARNING, gedrosselt je (Server, Art) — der Alarm hängt an ``mcp_aufruf``.
            gedrosselt(logger, logging.WARNING, f"mcp:{target_url}:timeout", _ABSTAND_S,
                       "MCP tool %s @ %s: keine Antwort binnen %g s", tool_name, target_url,
                       frist)
            return {"error": {"message": f"keine Antwort binnen {frist:g} s",
                              "kind": "timeout"}}
        status_fehler = _status_fehler(exc)
        if status_fehler is not None and status_fehler.response.status_code in _AUSGELASTET:
            # CB-2: kein Werkzeug lief. Nicht sofort wiederholen — ``client`` wartet höchstens
            # eine kurze ``Retry-After`` ab (S2: der Rest des Fensters, nicht pauschal 60 s).
            code = status_fehler.response.status_code
            gedrosselt(logger, logging.WARNING, f"mcp:{target_url}:busy", _ABSTAND_S,
                       "MCP tool %s @ %s: ausgelastet (%s)", tool_name, target_url, code)
            return ausgelastet("rate_limited" if code == 429 else "unavailable",
                               _wartezeit(status_fehler.response))
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
            # Ohne Traceback (Paket 18E): ``McpError.__str__`` brächte den ungekürzten
            # Text zurück, den ``inhalt`` hier gerade kürzt. Paket 19 (N-15): meist ein
            # Modellargument — WARNING, gedrosselt.
            gedrosselt(logger, logging.WARNING, f"mcp:{target_url}:abgelehnt", _ABSTAND_S,
                       "MCP tool %s rejected @ %s: %s", tool_name, target_url,
                       inhalt(abgelehnt.error.message))
            return {"error": {"message": abgelehnt.error.message, "kind": "tool"}}
        # Ohne Traceback (Paket 18E): die anyio-Gruppen-Traces wären lang und sagten nichts
        # dazu. Im Log der Grund ohne Fremdtexte (Review 2026-10-30): ein ``McpError`` außer
        # ``-32601``/``-32602`` (etwa ``-32603``) brächte sonst den Text des Servers samt
        # wiederholter Eingabe — von ihm nur Art und Code. Der volle Grund geht an den Aufrufer.
        # Paket 19 (N-15): Netz und Gegenstelle als gedrosselte Warnung, ein Programmfehler
        # bleibt ERROR.
        if _erwartbar(exc):
            gedrosselt(logger, logging.WARNING, f"mcp:{target_url}:transport", _ABSTAND_S,
                       "MCP tool %s transport error @ %s: %s", tool_name, target_url,
                       ausnahme_text(exc))
        else:
            logger.error("MCP tool %s transport error @ %s: %s",  # noqa: TRY400
                         tool_name, target_url, ausnahme_text(exc))
        return {"error": {"message": _cause_text(exc), "kind": "transport"}}

    if result.isError:
        message = " ".join(b["text"] for b in _text_blocks(result)) or "tool error"
        # Paket 18C/D: der Server wiederholt in Prüffehlern die Eingabe (-32602) — der Text
        # steht in der Zugakte des Zugs, hier nur seine Länge. Paket 19 (N-15): der Server
        # hat geantwortet — WARNING, gedrosselt.
        gedrosselt(logger, logging.WARNING, f"mcp:{target_url}:tool", _ABSTAND_S,
                   "MCP tool %s error @ %s: %s", tool_name, target_url, inhalt(message))
        fehler: dict[str, Any] = {"message": message, "kind": "tool"}
        # Der strukturierte Teil reist mit: seit dem MCP-Stand 2026-11-07 trägt ihn JEDER Fehler
        # (``error = {code, message, …}``, Paket M1 liest ihn im Client); die Stapel-Ablage dazu
        # ``status``/``reason`` (Paket U3-3a).
        if getattr(result, "structuredContent", None) is not None:
            fehler["structured"] = result.structuredContent
        return {"error": fehler}

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
    # Paket 19 (Audit 2026-10-31, N-27): dieselbe Gesamtfrist wie ``_call_tool`` — ohne sie
    # galt nur das SDK (``read=300``), und ``GET /mcp-servers`` fragt nacheinander.
    # ``TimeoutError`` geht an den Aufrufer wie jeder Transportfehler.
    async with asyncio.timeout(_frist_s()), _open_session(resolve_mcp_url(url)) as session:
        listing = await session.list_tools()
    # Paket 11 (E): Schema und Lesend-Markierung für „Werkzeuge übernehmen“ im Studio.
    return [
        {"name": tool.name, "description": tool.description or "",
         "input_schema": dict(tool.inputSchema or {}),
         "read_only": bool(tool.annotations and tool.annotations.readOnlyHint is True)}
        for tool in listing.tools
        if getattr(tool, "name", "")
    ]
