"""Module mit Datenquelle (Paket U1-e, Plan §3.2 / §15): große Daten holt das Backend selbst.

Das Manifest nennt unter ``datenquelle`` ein MCP-Werkzeug, die ``argumente``, die die KI angeben
darf, und feste ``vorgaben``. Die KI sieht nur diese Argumente — mit der Beschreibung aus dem
Werkzeug-Katalog (``services/mcp/tool_defs``), damit es keine zweite Fassung gibt. Beim Aufruf
ruft das Backend das Werkzeug, formt das Ergebnis zu Block-Daten und gibt der KI nur eine
Quittung: Die Daten laufen nicht durchs Modell.

**Text statt ``structuredContent``** (Plan §15, E-2): Mit ``outputFormat: json``, das der Client
für diese Werkzeuge ohnehin setzt (``tool_args._JSON_CAPABLE_TOOLS``), ist der Text wörtlich das
``structuredContent`` des Servers (``wlo-mcp-server-sc/src/tools/browse.ts:272-276``). Der
Werkzeug-Cache speichert nur Text — ein Seitenkanal hätte bei einem Cache-Treffer nichts.

Der Ruf geht über ``call_mcp_tool_status``: Prüfung, Auflösung von Fach-Namen, Cache, Zugang und
Zugakte gelten wie für jeden Aufruf. Ob das Werkzeug im Lauf überhaupt verfügbar ist (Sperren,
Studio-Schalter), entscheidet das Angebot (``werkzeuge.modul_werkzeuge``), nicht dieses Modul.

Das Ergebnis trägt neben Block und Text ein ``ToolOutcome`` (Review U1-e, Befund 6): Die Schleifen
führen den Aufruf in ``tools_called``/``outcomes`` wie jeden anderen Werkzeugaufruf.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any, Final, NamedTuple

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.ui_module import katalog, themenbaum
from boerdi.ui_module.katalog import Manifest

logger = logging.getLogger(__name__)

_WERT_ZEICHEN: Final = 200

#: Werkzeug → (Ergebnis, Überschrift) → Block-Daten oder ``None``; dazu Textfassung und Quittung.
_Umformer = tuple[Callable[[Any, str], dict[str, Any] | None],
                  Callable[[dict[str, Any]], str], Callable[[dict[str, Any]], str]]

_UMFORMER: Final[dict[str, _Umformer]] = {
    "browse_collection_tree": (themenbaum.daten_aus, themenbaum.textfassung, themenbaum.quittung),
}

_FEHLER_ARGUMENTE: Final = ("Fehler: {name} braucht eines der Argumente {argumente} als "
                            "kurzen Text. Berichtige den Aufruf oder antworte in Prosa.")
_FEHLER_LADEN: Final = ("Fehler: {name} ließ sich nicht laden. Prüfe das Argument (subject ist "
                        "der Name eines Fachportals, nodeId die Kennung einer Sammlung) oder "
                        "antworte ohne den Baum.")
#: Review U1-e, Befund 5: keine Antwort des Servers — ein anderes Argument hülfe nicht.
_FEHLER_UNERREICHBAR: Final = ("Fehler: {name} ist gerade nicht erreichbar. Rufe es nicht noch "
                               "einmal auf; antworte ohne den Baum.")
#: Arten aus ``call_mcp_tool_status``, bei denen der Server nicht geantwortet hat.
_UNERREICHBAR: Final = frozenset({"transport", "timeout", "auth", "busy"})

#: Review U1-e, Befund 1: die Werkzeug-Nachricht für eine Antwort derselben Runde, wenn ein Modul
#: mit Datenquelle keinen Block geliefert hat — sonst stünde „hier ist der Baum“ ohne Baum da.
ANTWORT_VERWORFEN: Final = ("Nicht übernommen: Ein UI-Modul dieser Runde ließ sich nicht laden "
                            "(siehe sein Ergebnis). Antworte noch einmal, ohne auf seine Anzeige "
                            "zu verweisen.")
#: Zweites Review TW-6, Befund 1: die Antwort derselben Runde nach einer Umlenkung — sonst stünde
#: „hier kannst du hochladen“ ohne Feld und ohne Ablauf da.
ANTWORT_UMGELENKT: Final = ("Nicht übernommen: Das Modul dieser Runde lief nicht (siehe sein "
                            "Ergebnis). Rufe zuerst den genannten Ablauf auf, dann antworte.")


class Ergebnis(NamedTuple):
    """Ein Aufruf mit Datenquelle: Block (oder ``None``), Text für die KI, Ergebnis fürs
    Protokoll."""

    block: UiBlock | None
    text: str
    outcome: ToolOutcome


def werkzeug(manifest: Manifest) -> str | None:
    """Das Werkzeug der Datenquelle — oder ``None`` für ein Modul ohne."""
    quelle = manifest.get("datenquelle")
    return quelle.get("werkzeug") if isinstance(quelle, dict) else None


def parameter(manifest: Manifest) -> dict[str, Any] | None:
    """Die Parameter für die KI: nur die ``argumente``, beschrieben wie im Werkzeug-Katalog.
    ``None``, wenn das Werkzeug dort fehlt oder keine Umformung kennt — dann kein Angebot."""
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS

    name = werkzeug(manifest)
    if name not in _UMFORMER:
        return None
    definition = next((t["function"] for t in TOOL_DEFINITIONS
                       if t["function"]["name"] == name), None)
    if definition is None:
        return None
    eigenschaften = definition["parameters"].get("properties", {})
    argumente = manifest["datenquelle"]["argumente"]
    return {"type": "object",
            "properties": {a: eigenschaften[a] for a in argumente if a in eigenschaften}}


async def _rufen(name: str, args: dict[str, Any]) -> tuple[str, str]:
    """Die Naht zum MCP-Client (in Tests ersetzt)."""
    from boerdi.services.mcp.client import call_mcp_tool_status

    return await call_mcp_tool_status(name, args)


def _gesendete_argumente(manifest: Manifest, args: Any) -> dict[str, Any] | None:
    """Die genannten Argumente (kurze Texte) samt Vorgaben; ``None`` ohne brauchbares Argument.

    Nennt die KI mehrere, gilt das letzte der Liste — beim Themenbaum ``nodeId`` vor ``subject``,
    wie der Server selbst (``browse.ts:212``); ein Fehler-Zug für eine doppelte Angabe lohnt nicht.
    """
    if not isinstance(args, dict):
        return None
    quelle = manifest["datenquelle"]
    genannt = {a: args[a] for a in quelle["argumente"] if args.get(a) not in (None, "")}
    if not genannt or not all(isinstance(w, str) and len(w) <= _WERT_ZEICHEN
                              for w in genannt.values()):
        return None
    gilt = next(a for a in reversed(quelle["argumente"]) if a in genannt)
    return {gilt: genannt[gilt], **(quelle.get("vorgaben") or {})}


def _fehlschlag(name: str, text: str, art: str, latenz_ms: int = 0) -> Ergebnis:
    # Nur die Art, nie Text des Servers: ``outcomes`` landen im Debug-Block.
    status = "timeout" if art == "timeout" else "error"
    return Ergebnis(None, text, ToolOutcome(tool=name, status=status, error=art,
                                            latency_ms=latenz_ms))


class Geladen(NamedTuple):
    """Das rohe Ergebnis des Werkzeugs (Paket U2): ``payload`` (JSON) oder ``None`` mit ``art``
    (``modul``, ``argumente``, eine Art aus ``call_mcp_tool_status``, ``form``)."""

    payload: Any
    art: str
    gesendet: dict[str, Any] | None
    latenz_ms: int


async def laden(name: str, args: Any) -> Geladen:
    """Das Werkzeug der Datenquelle mit den Argumenten der KI und den Vorgaben rufen und den
    JSON-Text lesen — ohne Umformung. Gemeinsam mit :func:`aufruf` und der Brücke „Als Entwurf
    bearbeiten“ (``services/strukturentwurf_aktion``), die mehr Felder braucht als der Baum."""
    manifest = katalog.katalog().get(name)
    werkzeug_name = werkzeug(manifest) if manifest else None
    if manifest is None or werkzeug_name not in _UMFORMER:
        return Geladen(None, "modul", None, 0)
    gesendet = _gesendete_argumente(manifest, args)
    if gesendet is None:
        return Geladen(None, "argumente", None, 0)
    t0 = time.monotonic()
    text, art = await _rufen(werkzeug_name, gesendet)
    if art == "tool":
        # Eine Datenquelle liest nur — ein zweiter Versuch ist gefahrlos. Ein kurzer Ausfall
        # von edu-sharing hinter dem MCP-Server kommt als ``tool``-Fehler an, und den wiederholt
        # der MCP-Client nicht (dort heißt ``tool`` „der Server hat abgelehnt“). Frist, Anmeldung
        # und Verbindung bleiben bei einem Versuch: das Warten verdoppelte sich, ein abgewiesener
        # Zugang bliebe abgewiesen, und Verbindungsfehler wiederholt der Client schon.
        logger.info("Datenquelle %s für %s: Werkzeugfehler, zweiter Versuch", werkzeug_name, name)
        text, art = await _rufen(werkzeug_name, gesendet)
    latenz_ms = int((time.monotonic() - t0) * 1000)
    if art:
        return Geladen(None, art, gesendet, latenz_ms)
    try:
        return Geladen(json.loads(text), "", gesendet, latenz_ms)
    except (json.JSONDecodeError, TypeError):
        return Geladen(None, "form", gesendet, latenz_ms)


async def aufruf(name: str, args: Any, *, titel: str | None = None) -> Ergebnis:
    """Ein Modul-Aufruf mit Datenquelle → ``(Block, Quittung, Ergebnis)`` oder
    ``(None, Fehlertext, Ergebnis)``.

    ``titel`` ist die Überschrift des Blocks; ohne Angabe das genannte Fach (``subject``) — eine
    Kennung allein sagt der Person nichts. Die Direktaktion ``show_collection_tree`` gibt den
    Titel des Knotens mit, den die Person geöffnet hat.

    Der Fehlertext enthält keinen Text des Servers: er ginge sonst ungerahmt an die KI.
    """
    geladen = await laden(name, args)
    if geladen.art == "modul":
        return _fehlschlag(name, f"Fehler: {name} ist kein UI-Modul mit Datenquelle.", "modul")
    manifest = katalog.katalog()[name]
    if geladen.art == "argumente":
        return _fehlschlag(name, _FEHLER_ARGUMENTE.format(
            name=name, argumente=" oder ".join(manifest["datenquelle"]["argumente"])),
            "argumente")
    werkzeug_name = werkzeug(manifest) or ""
    latenz_ms = geladen.latenz_ms
    if geladen.art in _UNERREICHBAR:
        logger.info("Datenquelle %s für %s: nicht erreichbar (%s)", werkzeug_name, name,
                    geladen.art)
        return _fehlschlag(name, _FEHLER_UNERREICHBAR.format(name=name), geladen.art, latenz_ms)
    formen, text_aus, quittung_aus = _UMFORMER[werkzeug_name]
    gesendet = geladen.gesendet or {}
    ueberschrift = titel if titel is not None else str(gesendet.get("subject") or "")
    daten = formen(geladen.payload, ueberschrift) if geladen.payload is not None else None
    if daten is None or katalog.daten_fehler(manifest, daten):
        grund = geladen.art or ("abweichung" if daten is not None else "form")
        logger.info("Datenquelle %s für %s: kein brauchbares Ergebnis (%s)", werkzeug_name, name,
                    grund)
        return _fehlschlag(name, _FEHLER_LADEN.format(name=name), grund, latenz_ms)
    block = neuer_block(name, manifest["version"], manifest["art"], daten, text_aus(daten))
    # Die Zahl der Einträge oben (Themenbaum: ``knoten``) — leer ist ein Block, aber kein Treffer.
    anzahl = len(daten.get("knoten") or [])
    return Ergebnis(block, quittung_aus(daten),
                    ToolOutcome(tool=name, status="success" if anzahl else "empty",
                                item_count=anzahl, latency_ms=latenz_ms))
