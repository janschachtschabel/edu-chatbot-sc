"""Das Skill-Verzeichnis einer Sammlung und die Skill-Suche — für das Studio.

Sammlungs-Skills lagen bis hier ohne jede Anzeige im Repositorium (Plan §2.2):
welche Anleitungen eine Sammlung freigibt, sah nur der Agent, und erst, wenn er
``get_skill_registry`` rief. Das Verzeichnis (ST-8c) ruft dasselbe Werkzeug im
JSON-Format — dieselbe Antwort, derselbe Werkzeug-Cache — und formt sie für
eine Liste um. Die Suche per Suchbegriff (Paket F3) fragt ``search_skill``,
sofern der MCP-Server es anbietet; jeder Eintrag trägt einen Link zum
Bearbeiten im md-editor (``domain/repo_links``).

**Fremd beschriebener Text.** Titel, Beschreibungen und Stichworte schreibt die
Redaktion im Repositorium. Sie werden geprüft statt vertraut: ein Eintrag ohne
Knoten fällt heraus, jeder Text wird eine Zeile. Das Studio zeigt sie als reinen
Text.

**Ein Fehler ist ein Fehler.** Antwortet der MCP nicht oder unlesbar, gibt es
``VerzeichnisFehler`` statt eines leeren Verzeichnisses — „diese Sammlung gibt
keine Skills frei" wäre sonst eine Behauptung ohne Beleg.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from boerdi.domain.repo_links import editor_url, render_url
from boerdi.obs.log_inhalt import inhalt
from boerdi.services.config_loader import get_repo_base_url
from boerdi.services.mcp.client import call_mcp_tool, call_mcp_tool_status, is_mcp_error

logger = logging.getLogger(__name__)

#: So meldet der MCP-Server ein Werkzeug, das er nicht registriert hat —
#: ``search_skill`` fehlt mit ``WLO_DISABLE_SKILL_SEARCH`` oder
#: ``WLO_SKILL_TOOL_MODE=one-tool``. Gemessen 2026-09-29 am eingestellten Server:
#: „MCP error -32602: Tool search_skill not found".
_SUCHE_FEHLT = re.compile(r"\bTool search_skill not found\b", re.IGNORECASE)

#: So viele Treffer erbittet die Suche — das Maximum des Servers (``maxResults``,
#: zod ``max(25)`` in ``tools/skills.ts``). Er nennt keine Gesamtzahl; kommen so
#: viele zurück, kann die Liste gekappt sein.
SUCHE_MAX = 25


class VerzeichnisFehler(RuntimeError):
    """Der MCP hat nicht oder unlesbar geantwortet.

    ``grund`` ist ``mcp`` (der Server meldete einen Fehler, ``detail`` trägt seinen
    Text) oder ``unlesbar`` (keine JSON-Antwort). Ein Code statt eines Satzes:
    der Router übersetzt ihn in die Sprache der Anfrage.
    """

    def __init__(self, grund: str, detail: str = "") -> None:
        super().__init__(detail or grund)
        self.grund = grund
        self.detail = detail


def _zeile(wert: object) -> str:
    return " ".join(wert.split()) if isinstance(wert, str) else ""


def _link(node_id: str) -> str:
    return render_url(node_id, get_repo_base_url())


def _liste(roh: object) -> list[Any]:
    return roh if isinstance(roh, list) else []


def _eintrag(roh: object) -> dict[str, Any] | None:
    if not isinstance(roh, dict) or not (node_id := _zeile(roh.get("nodeId"))):
        return None
    stichworte = [w for w in map(_zeile, _liste(roh.get("keywords"))) if w]
    return {
        "node_id": node_id,
        "title": _zeile(roh.get("title")),
        "description": _zeile(roh.get("description")),
        "keywords": stichworte,
        "context": _zeile(roh.get("context")),
        "url": _link(node_id),
        # Bearbeitet wird das Original: ein Treffer aus einer Fachsammlung ist ein
        # Verweis und nicht beschreibbar (``nodeIdLine`` im MCP-Server). Die
        # Registry nennt nur ``nodeId`` — dort ist es der Skill selbst.
        "edit_url": editor_url(_zeile(roh.get("originalId")) or node_id, get_repo_base_url()),
    }


def _als_objekt(roh: str) -> dict[str, Any]:
    """Die JSON-Antwort des MCP als Objekt — sonst ``VerzeichnisFehler("unlesbar")``."""
    try:
        daten = json.loads(roh)
    except ValueError as exc:
        raise VerzeichnisFehler("unlesbar") from exc
    if not isinstance(daten, dict):
        raise VerzeichnisFehler("unlesbar")
    return daten


async def skill_verzeichnis(collection_id: str) -> dict[str, Any]:
    """Registry-Dokument, freigegebene Skills und nicht aufgelöste Einträge."""
    roh = await call_mcp_tool(
        "get_skill_registry", {"collectionId": collection_id, "outputFormat": "json"})
    if is_mcp_error(roh):
        logger.warning("Skill-Verzeichnis %s: %s", collection_id, roh[:200])
        raise VerzeichnisFehler("mcp", roh)
    daten = _als_objekt(roh)

    registry = daten.get("registry") if isinstance(daten.get("registry"), dict) else None
    dokument = _zeile((registry or {}).get("registryNodeId"))
    # Nicht aufgelöst heißt beim MCP-Server zweierlei: ein Knoten, den es nicht
    # (mehr) gibt, und ein Block ganz ohne Link (``nodeId: ""``) — der typische
    # Fehler im Dokument. Beide bleiben; nur ein Eintrag ohne Titel UND Knoten
    # hat nichts zu zeigen (Review-Befund 2026-09-27).
    offen = [
        {"node_id": _zeile(u.get("nodeId")), "title": _zeile(u.get("title"))}
        for u in _liste((registry or {}).get("unresolved"))
        if isinstance(u, dict) and (_zeile(u.get("nodeId")) or _zeile(u.get("title")))
    ]
    return {
        "collection_id": collection_id,
        "registry": {
            "node_id": dokument, "title": _zeile(registry.get("registryTitle")),
            "url": _link(dokument),
        } if registry and dokument else None,
        "entries": [e for e in map(_eintrag, _liste((registry or {}).get("entries"))) if e],
        "unresolved": offen,
        "reason": daten.get("reason") if isinstance(daten.get("reason"), str) else None,
        # Die Suche nach dem Dokument oder seine Liste wurde gekappt — das
        # Verzeichnis ist dann womöglich unvollständig, und das soll dastehen.
        "truncated": bool(daten.get("scanTruncated") or (registry or {}).get("truncated")),
    }


async def skill_suche(suchbegriff: str) -> dict[str, Any]:
    """Skills per Suchbegriff im Skill-Bestand des MCP-Servers — über
    ``search_skill`` (Paket F3).

    Welcher Bestand das ist, entscheidet der Server: die konfigurierte
    Skills-Sammlung samt Skillsets, ohne sie das ganze Repositorium. Deshalb geht
    kein ``includeSubcollections`` mit — es höbe seine Vorgabe auf.

    ``available: False``, wenn der MCP-Server das Werkzeug nicht anbietet: ein
    Zustand des Servers, kein Fehler — das Studio verweist dann auf die Suche
    per Sammlungs-ID. Die Meldung kommt je nach SDK als Werkzeug- oder als
    JSON-RPC-Fehler an, also für beide Arten. Jeder andere Fehler bleibt ein
    ``VerzeichnisFehler``. ``truncated``: so viele Treffer wie erbeten.
    """
    roh, art = await call_mcp_tool_status(
        "search_skill", {"query": suchbegriff, "outputFormat": "json", "maxResults": SUCHE_MAX})
    if (art or is_mcp_error(roh)) and _SUCHE_FEHLT.search(roh):
        return {"query": suchbegriff, "available": False, "entries": [], "truncated": False}
    if art or is_mcp_error(roh):
        logger.warning("Skill-Suche %s: %s", inhalt(suchbegriff), inhalt(roh))
        raise VerzeichnisFehler("mcp", roh)
    treffer = _liste(_als_objekt(roh).get("skills"))
    return {"query": suchbegriff, "available": True,
            "entries": [e for e in map(_eintrag, treffer) if e],
            "truncated": len(treffer) >= SUCHE_MAX}
