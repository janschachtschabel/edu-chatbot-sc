"""MCP-Client-Kern: ``call_mcp_tool`` verdrahtet die 5-1-Bausteine.

Port aus ALT ``app/services/mcp_client.py`` — dort war das Modul zusätzlich eine
Re-Export-Fassade über tool_defs/transport/tool_cache/arg_resolvers/parsers. Im
NEU-Baum importieren Konsumenten direkt aus den Leaf-Modulen (spec §4), sodass
hier nur der EIGEN-Code des Clients verbleibt:

* ``call_mcp_tool`` — die Orchestrierung: Server-URL-Lookup → ``validate_tool_args``
  → ``TOOL_PREPROCESSORS``-Pipeline → outputFormat-json-Injektion → Cache-Lookup
  (Blocklist/Meta-Re-Emit) → ``transport.call_tool`` → Fehler→Retry-once (nur
  ohne Antwort, nie nach einer Ablehnung) → ``_queryMeta``-Extraktion →
  ``get_subject_portals``-Kompaktierung → cache_set.
* ``_query_metas`` (ContextVar) + ``reset_query_metas`` + ``get_query_metas`` —
  Per-Request-Akkumulator der ``_queryMeta``-Blöcke (die Route/SSE-Schicht liest
  + leert ihn pro Turn). Wie ``_request_hints`` in arg_resolvers per-Task-scoped.
* ``_compact_subject_portals`` — schlankt das bulkige get_subject_portals-Envelope.
* ``_get_server_url_for_tool`` — Tool→Server-URL über die Studio-MCP-Registry.

Bewusste Abweichungen ggü. ALT (dokumentiert, funktional äquivalent):
* **Transport-Seam.** ALTs ``_ensure_initialized_with_session`` + ``_json_rpc(
  "tools/call", {"name","arguments"}, url=)`` werden durch ``transport.call_tool(
  tool_name, arguments, url=)`` ersetzt (5-1b). Das Result-Dict hat exakt die
  ALT-``_json_rpc``-Form (``{"result": {"content": […]}}`` / ``{"error": …}``),
  daher portiert der Extraktions-/Cache-Rumpf nahezu verbatim.
* **Retry ohne Session-Reset.** ALT nullte vor dem Retry den Per-URL-Session-Slot;
  der SDK-Transport öffnet ohnehin pro Call eine frische Session, sodass der Retry
  ein simpler Zweit-Call ist (kein modul-globaler Session-State — Regel 3).
* **Weggelassen:** der PEP-562-``__getattr__``-Shim (``_session_id``/``_initialized``)
  und der ``resolve_discipline_labels``-No-op — beides ALT-Altlasten für Legacy-
  Importer ohne NEU-Konsument (MCP-v2 liefert saubere Labels; kein Session-State).
"""

from __future__ import annotations

import asyncio
import contextvars as _ctxvars
import json
import logging
import time as _time
from typing import Any

from boerdi.domain.fremdwerkzeug import ist_fremd
from boerdi.domain.prepared_write import PreparedWrite, read_prepared_write
from boerdi.domain.werkzeug_freigabe import uebernommen
from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD
from boerdi.obs.log_inhalt import ereignis, filterwerte
from boerdi.services.mcp import anmeldung, fremdwerkzeuge, transport
from boerdi.services.mcp.arg_resolvers import TOOL_PREPROCESSORS
from boerdi.services.mcp.listen_argumente import braucht_umformung, mit_listen
from boerdi.services.mcp.tool_args import (
    _JSON_CAPABLE_TOOLS,
    validate_tool_args,
)
from boerdi.services.mcp.tool_cache import (
    _TOOL_CACHE,
    _TOOL_CACHE_BLOCKLIST,
    _TOOL_META_CACHE,
    _cache_get,
    _cache_key,
    _cache_set,
    darf_cachen,
)
from boerdi.services.zugakte import aktuelle_zugakte
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)


# Wie ein Fehlschlag aussieht — und warum das eine Zeichenkette ist.
#
# ``call_mcp_tool`` gibt IMMER einen String zurück, auch im Fehlerfall: das
# Modell sieht ihn als gewöhnliches Werkzeug-Ergebnis und kann ihn einordnen.
# ``transport.call_tool`` fängt dafür jede Ausnahme ab (auch Zeitüberschreitung
# und „Server weg") und macht ein Fehler-Dict daraus — geworfen wird hier also
# praktisch nie.
#
# Für jeden Aufrufer, der KEIN Modell dahinter hat, ist das eine Falle: ein
# Fehlschlag sieht aus wie ein Ergebnis. Vier Stellen prüften den Präfix bis
# 2026-08-15 mit einer eigenen Kopie des Literals, eine fünfte (die
# Schreib-Abnahme) vergass es und meldete Fehlschläge als Vollzug. Deshalb
# steht die Frage jetzt beim Erzeuger, nicht bei den Lesern.
_MCP_ERROR_PREFIX = "MCP error"


def is_mcp_error(text: str | None) -> bool:
    """Ist ``text`` die Fehler-Antwort von :func:`call_mcp_tool` statt eines Ergebnisses?

    Am Präfix erkannt, nicht am Vorkommen: ein Servertext, der die Worte
    irgendwo in der Mitte führt, ist ein Ergebnis.
    """
    return bool(text) and str(text).startswith(_MCP_ERROR_PREFIX)


# Die Argument-Zeile in ``call_mcp_tool`` ist für die Fehlersuche an Filtern da,
# und Filter sind kurz. Zwei Dinge gehören trotzdem nicht ins INFO-Protokoll
# (offener Befund 1.3, 2026-09-29): der ``confirmToken`` — er löst eine
# bestätigte Änderung aus — und lange Nutzlasten wie ``content``/``fileBase64``
# (bis 256 KB, also ein hochgeladenes Dokument). Beide werden ersetzt; die
# Schlüssel bleiben stehen, damit sichtbar ist, WAS mitgeschickt wurde.
_LOG_VALUE_MAX_CHARS = 500


def _args_for_log(arguments: Any) -> Any:
    """``arguments`` mit Werten fürs Protokoll — nur mit ``LOG_CONTENT`` und auf DEBUG:
    Schlüssel geschwärzt, lange Werte gekürzt."""
    if not isinstance(arguments, dict):
        return arguments
    zeile: dict[str, Any] = {}
    for key, value in arguments.items():
        if key == CONFIRM_TOKEN_FIELD:
            zeile[key] = "‹geschwärzt›"
        elif isinstance(value, str) and len(value) > _LOG_VALUE_MAX_CHARS:
            zeile[key] = f"‹{len(value)} Zeichen›"
        else:
            zeile[key] = value
    return zeile


# Per-request accumulator for MCP query metadata (_queryMeta blocks).
# Each MCP tool call that returns a _queryMeta content block gets appended
# here. The route/SSE layer reads + clears it to forward as SSE events / debug
# info. Per-async-task scoped via ContextVar so concurrent sessions don't bleed.
# B039 is safe here: the mutable default is never mutated in place —
# reset_query_metas always rebinds via .set([]), get_query_metas reads through
# ``.get([])`` and copies, and call_mcp_tool appends to the ``.get([])`` result
# (a fresh list when unset) then rebinds — so the shared default cannot leak.
_query_metas: _ctxvars.ContextVar[list[dict[str, Any]]] = _ctxvars.ContextVar(
    "_query_metas", default=[],  # noqa: B039 — read-only default (see note)
)


def reset_query_metas() -> None:
    """Clear the per-request query-meta accumulator (call at turn start)."""
    _query_metas.set([])


def get_query_metas() -> list[dict[str, Any]]:
    """Return accumulated query metas for the current request."""
    return list(_query_metas.get([]))


# Zweiter Sammler gleicher Bauart, für die vorbereiteten Schreibzugriffe (E3).
# Im eingebetteten Betrieb führt der MCP-Server eine bestätigte Änderung nicht
# aus, sondern beschreibt sie; abgesetzt wird sie später in der
# Repository-Seite. Getrennt von ``_query_metas``, weil es eine andere Sache
# ist: Metas beschreiben eine gelaufene Suche, dies eine Änderung, die noch
# aussteht. Zur B039-Sicherheit gilt die Notiz oben unverändert.
_prepared_writes: _ctxvars.ContextVar[list[PreparedWrite]] = _ctxvars.ContextVar(
    "_prepared_writes", default=[],  # noqa: B039 — read-only default (siehe oben)
)


def reset_prepared_writes() -> None:
    """Sammler der vorbereiteten Schreibzugriffe leeren (zu Zugbeginn)."""
    _prepared_writes.set([])


def get_prepared_writes() -> list[PreparedWrite]:
    """Die in diesem Zug vorbereiteten Schreibzugriffe."""
    return list(_prepared_writes.get([]))


# Registry-Lookup Tool-Name → Server-URL (config-gekoppelt). ALTs Modul-Konstante
# ``MCP_URL`` (Import-Zeit) wird durch ``transport.resolve_mcp_url()`` ersetzt:
# gleiche Semantik (konfigurierte oder Default-MCP-URL, Trailing-Slash-frei),
# aber pro Aufruf ausgewertet → kein modul-globaler URL-State.
_PRIMAER = "wlo-mcp"


def _get_server_url_for_tool(tool_name: str) -> str:
    """Look up which MCP server provides a given tool.

    Falls back to the configured default MCP URL if no registry match is found.
    """
    from boerdi.services.config_loader import get_enabled_mcp_servers

    default_url = transport.resolve_mcp_url()
    for server in get_enabled_mcp_servers():
        server_tools = server.get("tools", [])
        # Review Paket 11, #1: übernommene Werkzeuge eines weiteren Servers laufen über
        # ``fremdwerkzeuge`` — ihr Name leitet keinen gleichnamigen WLO-Aufruf um.
        if server.get("id") != _PRIMAER and tool_name in uebernommen(server):
            continue
        if tool_name in server_tools:
            return server.get("url", default_url)

    return default_url


def _compact_subject_portals(raw_response: str) -> str:
    """Slim the bulky marketing fields from a ``get_subject_portals``
    response. Each Fachportal's ``description`` is multi-paragraph
    marketing copy (~1-2 KB per item, ~50 KB total) that buries the
    crucial ``nodeId`` so deeply that the LLM emits placeholder UUIDs
    when asked to drill down. We keep:
      * ``nodeId``, ``title``, ``contentCount`` — for the Fach→UUID lookup
      * ``description`` truncated to 220 chars — for downstream
        ``parse_wlo_cards`` which renders subject-portal cards in the UI
      * ``disciplines`` / ``educationalContexts`` (top 4 each) — same
        reason; the cards display them as chips
    Drops keywords, userRoles, learningResourceTypes and any unknown
    extra fields. ~50 KB → ~6 KB for 30 portals: small enough that the
    LLM can scan it for Mathematik in one read.
    """
    parsed = json.loads(raw_response)
    items = parsed.get("results") or parsed.get("items") or []
    compact_items = []
    for it in items:
        if not isinstance(it, dict):
            continue
        slim: dict[str, Any] = {}
        for key in ("nodeId", "title", "contentCount"):
            if key in it:
                slim[key] = it[key]
        # Fachportale SIND Sammlungen (ccm:map) → nodeType erhalten/setzen, sonst
        # defaultet parse_wlo_cards auf "content" → falsche Box (Materialien
        # statt Sammlungen) + Render- statt Collections-Browse-Link.
        slim["nodeType"] = it.get("nodeType") or "collection"
        # Truncate description so cards still render but the LLM doesn't
        # have to wade through a paragraph each.
        desc = it.get("description") or ""
        if isinstance(desc, str) and desc:
            slim["description"] = desc if len(desc) <= 220 else desc[:217] + "…"
        for key in ("disciplines", "educationalContexts"):
            v = it.get(key)
            if isinstance(v, list) and v:
                slim[key] = v[:4]
        if slim:
            compact_items.append(slim)
    out = {
        "total": parsed.get("total", len(compact_items)),
        "results": compact_items,
        "_compacted": True,
    }
    return json.dumps(out, ensure_ascii=False)


async def call_mcp_tool(
    tool_name: str, arguments: dict[str, Any], *, use_cache: bool = True,
) -> str:
    """Call a WLO MCP tool via the SDK transport, with parity-preserving wiring.

    Der Vertrag für die 25 Aufrufstellen und für das Modell: **immer** eine
    Zeichenkette, auch im Fehlerfall (:func:`is_mcp_error`). Wer zusätzlich
    wissen muss, WIE es schiefging, nimmt :func:`call_mcp_tool_status`.

    ``use_cache=False`` liest den Werkzeug-Cache nicht, legt das frische
    Ergebnis aber wieder ab — für „jetzt neu holen" (Master-Skill im Studio).
    """
    text, _art = await call_mcp_tool_status(tool_name, arguments, use_cache=use_cache)
    return text


async def call_mcp_tool_status(
    tool_name: str, arguments: dict[str, Any], *, use_cache: bool = True,
) -> tuple[str, str]:
    """Wie :func:`call_mcp_tool`, sagt aber zusätzlich die **Art** des Fehlers.

    Rückgabe ``(text, art)`` mit ``art`` aus ``""`` (kein Fehler) · ``"tool"``
    (der Server hat geantwortet und abgelehnt) · ``"transport"`` (es kam keine
    Antwort) · ``"timeout"`` (keine Antwort binnen ``MCP_CALL_TIMEOUT_S``; für
    die Frage „wurde geschrieben?" dasselbe wie ``transport``) · ``"auth"`` (der
    Zugangsblock wurde abgewiesen, Paket 10 — nichts ausgeführt). Die
    Unterscheidung stammt aus ``transport.call_tool``, wo sie als Einzige noch
    vorliegt.

    **Wofür.** Ein Aufrufer mit einem Modell dahinter braucht sie nicht — das
    Modell liest den Text und ordnet ihn ein. Ein *deterministischer* Aufrufer
    schon: die Schreib-Abnahme darf nur dann „es wurde nichts geändert" sagen,
    wenn der Server geantwortet hat. Bei ausgebliebener Antwort ist derselbe
    Satz eine Behauptung, die im ungünstigen Fall eine Dublette im kuratierten
    Bestand erzeugt (``services/write_approval``).

    **Unbekannt zählt wie „keine Antwort".** Ein Fehler-Dict ohne ``kind``
    (ältere Attrappe, fremder Transport) ergibt ``"transport"`` — die
    vorsichtige Richtung, denn „abgelehnt" ist die stärkere Behauptung.

    Resolved den Tool-Namen über die Studio-Registry (mcp-servers.yaml,
    Env-Override durch ``MCP_SERVER_URL``) auf die passende Server-URL.
    Wenn kein Server den Tool deklariert, fällt es auf die Default-MCP-URL
    zurück — Backward-Compat für Tools, die im Code registriert sind aber
    (noch) nicht in der YAML.
    """
    # Paket 11 (E): ein Werkzeug eines fremden Servers geht seinen eigenen Weg —
    # nichts von dem, was unten an WLO-Namen hängt, gilt für ihn.
    if ist_fremd(tool_name):
        t0 = _time.perf_counter()
        try:
            text, art = await fremdwerkzeuge.rufen(tool_name, arguments)
        except BaseException as e:
            _abbruch_in_die_akte(tool_name, arguments, arguments, e, t0)
            raise
        text = f"{_MCP_ERROR_PREFIX}: {text}" if art else text
        _in_die_akte(tool_name, arguments, arguments, text, art, aus_cache=False, t0=t0)
        return text, art

    # Paket 18B: ein Suchfilter als Liste („Arbeitsblatt oder interaktives Material“)
    # wird ausgepackt oder in Einzelaufrufe aufgefächert — der Server kennt je Filter
    # nur einen Wert (``listen_argumente``).
    if braucht_umformung(tool_name, arguments):
        # Jeder Teilaufruf läuft wieder hier durch und trägt sich selbst in die Zugakte ein.
        return await mit_listen(tool_name, arguments, call_mcp_tool_status,
                                use_cache=use_cache)

    t0 = _time.perf_counter()
    # Eine Liste statt eines Dicts (Review 2026-10-30): auch LEERE gesendete Argumente
    # sind eine Angabe — ``gesendet or arguments`` zeigte dann die Rohargumente.
    gesendet: list[dict[str, Any]] = []
    try:
        text, art, aus_cache = await _einzelaufruf(
            tool_name, arguments, use_cache=use_cache, gesendet=gesendet)
    except BaseException as e:
        _abbruch_in_die_akte(tool_name, arguments, gesendet[0] if gesendet else arguments, e, t0)
        raise
    _in_die_akte(tool_name, arguments, gesendet[0] if gesendet else arguments, text, art,
                 aus_cache=aus_cache, t0=t0)
    return text, art


def _abbruch_in_die_akte(name: str, eingang: dict[str, Any], gesendet: dict[str, Any],
                         fehler: BaseException, t0: float) -> None:
    """Ein Aufruf, der nicht zurückkam (Review 2026-10-30): von außen abgebrochen (Frist des
    Agenten, ``wait_for`` um den Seitenkontext) oder mit einer unerwarteten Ausnahme — bis dahin
    fehlte er in der Zugakte, obwohl er lief. Nur die Art der Ausnahme, nie ihr Text."""
    art = ("abgebrochen" if isinstance(fehler, asyncio.CancelledError | TimeoutError)
           else "ausnahme")
    _in_die_akte(name, eingang, gesendet, type(fehler).__name__, art, aus_cache=False, t0=t0)


def _in_die_akte(name: str, eingang: dict[str, Any], gesendet: dict[str, Any], text: str,
                 art: str, *, aus_cache: bool, t0: float) -> None:
    """Den Aufruf protokollieren und in die Zugakte des laufenden Zugs schreiben (Paket 18C/D)
    — die Akte nur innerhalb eines Zugs.

    Hier und nicht beim Aufrufer: alle Wege (Werkzeugschleife, Agent, Vorabruf, Direktaktion)
    laufen durch diese eine Stelle, auch die gescheiterten Aufrufe."""
    dauer_ms = round((_time.perf_counter() - t0) * 1000)
    zeichen = None if art else len(text)
    # Eine Zeile je Aufruf, auch für Fehler und Cache-Treffer — ohne Inhalt (Paket 18C/D).
    ereignis(logger, "mcp_aufruf", werkzeug=name, status=art or "ok", aus_cache=aus_cache,
             dauer_ms=dauer_ms, zeichen=zeichen)
    akte = aktuelle_zugakte()
    if akte is None:
        return
    akte.werkzeug(name, argumente_eingang=eingang, argumente_gesendet=gesendet,
                  status=art or "ok", aus_cache=aus_cache, dauer_ms=dauer_ms,
                  zeichen=zeichen, fehler=text if art else None)


async def _einzelaufruf(
    tool_name: str, arguments: dict[str, Any], *, use_cache: bool,
    gesendet: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    """Ein Aufruf am WLO-Server: Prüfung, Auflösung, Cache, Transport, Auswertung.

    Rückgabe wie :func:`call_mcp_tool_status`, dazu ``aus_cache``. In ``gesendet`` stehen danach
    die Argumente, wie sie nach Prüfung und Auflösung hinausgingen (für die Zugakte)."""
    # Per-Call-Server-URL: zuerst aus der Studio-Registry, sonst Default.
    target_url = _get_server_url_for_tool(tool_name)

    # Die Argumente beim Eingang, VOR Prüfung und Auflösung — unentbehrlich für Filterfehler.
    # Paket 18C/D: Filter und Kennungen mit Wert, Freitext (Suchtext, Adresse, Titel, bei
    # Schreibvorgängen die Inhalte unveröffentlichter Materialien) nur als Länge; die Werte
    # stehen in der Zugakte des Zugs, mit ``LOG_CONTENT`` zusätzlich auf DEBUG.
    logger.info("MCP tool %s args: %s", tool_name, filterwerte(arguments))
    if get_settings().log_content:
        logger.debug("MCP tool %s args (Werte): %s", tool_name, _args_for_log(arguments))

    # Validate arguments before sending to MCP server
    arguments = validate_tool_args(tool_name, arguments)

    # Preprocessor pipeline — zentral registriert in TOOL_PREPROCESSORS.
    # Jeder Preprocessor bekommt das ``arguments``-Dict und gibt ein neues
    # Dict zurück. Aktuell registriert:
    #   * search_wlo_content / search_wlo_collections → label→URI für Filter
    #   * browse_collection_tree                      → Fach-Name → UUID
    #   * get_collection_contents                     → Sammlungs-Name → UUID
    # Neue Auto-Korrekturen kommen einfach als Eintrag in TOOL_PREPROCESSORS
    # dazu, ohne diese Funktion anzufassen.
    pp = TOOL_PREPROCESSORS.get(tool_name)
    if pp is not None:
        try:
            arguments = await pp(arguments)
        except Exception as _ppe:  # noqa: BLE001 — best-effort, Original-Args weiter
            logger.warning(
                "preprocessor for %s failed: %s — passing original args through",
                tool_name, _ppe,
            )

    # Default to JSON output for tools that support it. Cleaner parsing in
    # parse_wlo_cards / parse_wlo_topic_page_cards, label-resolved values,
    # no regex mosaic. v1 servers ignore the unknown param and return
    # Markdown — our parsers accept both, so this is safe to roll out.
    if (
        tool_name in _JSON_CAPABLE_TOOLS
        and "outputFormat" not in arguments
    ):
        arguments = {**arguments, "outputFormat": "json"}
    gesendet.append(arguments)

    # Kein ``maxChars`` mehr von uns (2026-08-21): der Server liefert ohne
    # Angabe den ganzen Text (Vorgabe 200000 seit dem MCP-Deploy 20.08., live
    # gemessen an einer 59 398-Zeichen-Seite). Begründung an der gestrichenen
    # Konstante in ``tool_args``.

    # Cache-Lookup BEVOR der Transport bemüht wird (Hits sparen den kompletten
    # SDK-Handshake+Call). Blocklist-Tools (Health-Checks) umgehen den Cache.
    cache_key = None
    if tool_name not in _TOOL_CACHE_BLOCKLIST:
        cache_key = _cache_key(tool_name, arguments, url=target_url)
        cached = _cache_get(cache_key) if use_cache else None
        if cached is not None:
            logger.info("MCP tool %s cache HIT (%d entries)", tool_name, len(_TOOL_CACHE))
            # Cached queryMetas auch wieder in den Per-Request-Akkumulator
            # zurückspielen — sonst hätten Cache-Hit-Turns keine URI-resolved
            # Filter-Daten für die Such-CTA-URL.
            _cached_metas = _TOOL_META_CACHE.get(cache_key) or []
            if _cached_metas:
                _cur = _query_metas.get([])
                for _cm in _cached_metas:
                    _cur.append(_cm)
                _query_metas.set(_cur)
                logger.debug(
                    "re-emitted %d cached queryMetas for %s",
                    len(_cached_metas), tool_name,
                )
            return cached, "", True

    # SDK-Transport (5-1b): Handshake + Call + Result-Normalisierung liegen im
    # Transport, ein Call = frische Session. Result-Dict trägt die ALT-
    # ``_json_rpc``-Form (``{"result": {"content": …}}`` / ``{"error": …}``).
    result = await transport.call_tool(tool_name, arguments, url=target_url)

    # Einmal wiederholen — aber nur, wenn KEINE Antwort kam (Review 2026-09-29).
    # Hat der Server geantwortet und abgelehnt (``kind == "tool"``: unbekanntes
    # Werkzeug, zod-Validierung, abgelaufener Schlüssel), sagt ein zweiter
    # Aufruf dasselbe noch einmal: eine zweite Sitzung und doppelte
    # ERROR-Zeilen für nichts. Bei einem bestätigten Schreibzugriff schadet er
    # sogar — der Server löscht den ``confirmToken`` beim ersten
    # Einlöseversuch, die Wiederholung meldete „unbekannt oder bereits
    # benutzt" und verdeckte den Grund. Die Ablehnung protokolliert der
    # Transport; eine Zeile hier wäre dieselbe noch einmal. Ohne ``kind`` wird
    # wiederholt: unbekannt zählt wie „keine Antwort" (Docstring).
    #
    # **Ein bestätigter Schreibaufruf wird nie wiederholt** (offener Befund 1.2,
    # 2026-09-29). „Keine Antwort" heisst nicht „nicht angekommen": der erste
    # Aufruf kann geschrieben haben, nur die Antwort ging verloren. Die
    # Wiederholung verbrauchte dann den schon eingelösten Schlüssel, bekam
    # „unbekannt oder bereits benutzt" (``kind == "tool"``), und die Abnahme
    # meldete „nichts geändert" — wer daraufhin neu anlegt, erzeugt eine
    # Dublette. So bleibt es bei ``transport``, und ``write_approval`` bittet
    # darum, in WLO nachzusehen.
    #
    # **Eine abgelaufene Frist wird ebenfalls nicht wiederholt** (Paket 4, B2):
    # der zweite Versuch hinge genauso lange — die doppelte Wartezeit, die das
    # externe Audit (F04) beschreibt. **Ein abgewiesener Zugang auch nicht**
    # (Paket 10, Kurzaudit A-3): derselbe Block würde wieder abgewiesen.
    if "error" in result and result["error"].get("kind") not in ("tool", "timeout", "auth"):
        # Nur Transportfehler: ``tool``-Fehler mit Serverantwort laufen nicht hier durch. Den
        # Grund hat ``transport`` eben ohne Fremdtexte gemeldet — hier nicht noch einmal roh
        # (Review 2026-10-30: der Text eines ``-32603`` stand so bis zu viermal im Log).
        logger.error("MCP tool %s error @ %s (%s)", tool_name, target_url,
                     result["error"].get("kind") or "transport")
        if CONFIRM_TOKEN_FIELD in arguments:
            logger.warning(
                "MCP tool %s: bestätigter Schreibaufruf wird nicht wiederholt — ob "
                "er den Server erreicht hat, ist offen", tool_name)
        else:
            logger.info("Retrying MCP tool %s with fresh session @ %s...",
                        tool_name, target_url)
            result = await transport.call_tool(tool_name, arguments, url=target_url)
            if "error" in result:
                logger.error("MCP tool %s retry failed @ %s (%s)", tool_name, target_url,
                             result["error"].get("kind") or "transport")

    if "error" in result:
        # Ohne ``kind`` gilt „keine Antwort" — siehe Docstring: „abgelehnt"
        # ist die stärkere Behauptung und braucht einen Beleg.
        _art = result["error"].get("kind")
        if _art == "auth":
            # Der Rest des Zuges läuft ohne den Block, das Widget erfährt es.
            anmeldung.markiere_abgelehnt()
        return (
            f"{_MCP_ERROR_PREFIX}: {result['error'].get('message', 'Unknown error')}",
            _art if _art in ("tool", "transport", "timeout", "auth") else "transport",
            False,
        )

    # Extract text content from result, separating _queryMeta blocks.
    result_data = result.get("result", {})
    content_parts = result_data.get("content", [])

    texts = []
    _extracted_metas_this_call: list[dict[str, Any]] = []
    for part in content_parts:
        if isinstance(part, dict) and part.get("type") == "text":
            raw_text = part.get("text", "")
            # Detect _queryMeta JSON block and accumulate it instead of
            # mixing it into the LLM-visible response text.
            if raw_text.startswith('{"_queryMeta"'):
                try:
                    meta = json.loads(raw_text).get("_queryMeta")
                    if meta:
                        metas = _query_metas.get([])
                        metas.append(meta)
                        _query_metas.set(metas)
                        _extracted_metas_this_call.append(meta)
                        logger.debug(
                            "extracted _queryMeta from %s: %s",
                            tool_name, meta.get("queryType"),
                        )
                except (json.JSONDecodeError, AttributeError):
                    texts.append(raw_text)
            else:
                texts.append(raw_text)
        elif isinstance(part, str):
            texts.append(part)

    # Vorbereiteter Schreibzugriff (E3): der Server hat die bestätigte Änderung
    # beschrieben, statt sie auszuführen. Der Text bleibt unangetastet — er sagt
    # dem Modell, dass hier nichts geschrieben wurde. Unbrauchbares wird still
    # verworfen (``read_prepared_write``): abgesetzt wird das später von einem
    # Browser mit fremden Rechten, da ist nichts besser als etwas Halbes.
    vorbereitet = read_prepared_write(result_data.get("structuredContent"))
    if vorbereitet is not None:
        offene = _prepared_writes.get([])
        offene.append(vorbereitet)
        _prepared_writes.set(offene)
        logger.info("MCP tool %s hat einen Schreibzugriff vorbereitet: %s",
                    tool_name, vorbereitet.method)
    elif result_data.get("structuredContent") is not None:
        # DEBUG, nicht WARNING (2026-08-21): der Server hängt
        # ``structuredContent`` an JEDE Antwort — im Markdown-Zweig genauso wie
        # im JSON-Zweig (sein eigener Kommentar in ``url-text.ts`` sagt es).
        # Ein Schreibzugriff ist nur der Ausnahmefall; auf WARNING lief die
        # Meldung bei jedem Leseaufruf auf und machte das Warn-Level wertlos.
        # „Still verworfen" ist ohnehin, was der Kommentar oben zusagt.
        logger.debug(
            "MCP tool %s schickte einen strukturierten Teil ohne "
            "Schreibzugriff — verworfen", tool_name)

    response = "\n".join(texts) if texts else json.dumps(result_data)

    # Slim ``get_subject_portals``: the raw API ships rich marketing
    # descriptions for every Fachportal (~50 KB total). The LLM only
    # needs nodeId + title to resolve a Fach name → UUID, and the
    # over-long descriptions actively confuse the model into emitting a
    # placeholder UUID like ``"dummmy"`` instead of extracting the right
    # one. Compact the response to nodeId / title / contentCount while
    # keeping the JSON-envelope shape callers expect.
    if tool_name == "get_subject_portals":
        try:
            response = _compact_subject_portals(response)
            logger.info("get_subject_portals compacted to %d chars", len(response))
        except Exception as _ce:  # noqa: BLE001 — Kompaktierung best-effort
            logger.warning("get_subject_portals compaction failed: %s", _ce)

    # Successful response into cache (only if we have a key, i.e. the tool
    # isn't in the blocklist).
    if cache_key is not None and darf_cachen(tool_name, response):
        _cache_set(cache_key, response)
        # Auch die extrahierten queryMetas mit-cachen, damit Cache-Hits die
        # strukturierten Filter-Daten (URI-resolved discipline /
        # educationalContext / learningResourceType) wieder re-emitten können —
        # siehe Re-Emit-Logik im Cache-Hit-Zweig oben. Nur zu einem gespeicherten Wert
        # (Paket 19, M-11: ein zu großer bleibt draußen — seine Metas sonst für immer).
        if _extracted_metas_this_call and cache_key in _TOOL_CACHE:
            _TOOL_META_CACHE[cache_key] = _extracted_metas_this_call
    return response, "", False
