"""Envelopes, die keine Karten liefern, sondern einen Textblock.

Teil der Fassade ``boerdi.services.mcp.parsers``. Zwei Werkzeuge, ein Muster:
Envelope lesen, in Boerdi-Feldnamen umbenennen — und wenn kein Envelope kommt,
einen **benannten** Leerfall zurückgeben statt aus Markdown zu raten. Geraten
würde hier direkt in Unterrichtsmaterial hineinwirken (falscher Volltext,
falsch zugeordnete Wikipedia-Quelle), deshalb ist der Leerfall die Regel.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_content_text(mcp_text: str) -> dict[str, Any]:
    """Parst ``get_wlo_content_text`` (outputFormat=json) in den Volltext-Block.

    Envelope des Servers (``src/apps/outputSchemas.ts`` ``contentTextSchema``)::

        {"nodeId": "…", "title": "…", "text": "…",
         "source": "repository" | "external-extraction" | "none",
         "sourceUrl": str | null, "charCount": 4200, "truncated": false,
         "reason": "access_denied" | "no_text_no_url" | "extraction_failed"
                   | "node_not_found"}          # nur wenn kein Text da ist

    Rückgabe (Boerdi-Namen)::

        {"node_id", "title", "text", "source", "source_url",
         "char_count", "truncated", "reason"}

    ``reason`` ist der Grund, den der Server für einen leeren Volltext nennt —
    ohne ihn kann der Bot nicht unterscheiden, ob das Material aus Rechtegründen
    verschlossen ist (``access_denied``; daran ändert auch ein zweiter Versuch
    nichts) oder ob die Extraktion scheiterte. Kommt kein Envelope an (v1-Server
    oder ``outputFormat=markdown``), ist das Ergebnis leer mit
    ``reason="no_envelope"``: lieber ein benannter Leerfall als ein halb
    geratener Text, der als Arbeitsblatt-Inhalt weiterverwendet würde.
    """
    out: dict[str, Any] = {
        "node_id": "", "title": "", "text": "", "source": "",
        "source_url": "", "char_count": 0, "truncated": False, "reason": "",
    }
    if not mcp_text:
        return out
    try:
        obj = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        obj = None
    if not isinstance(obj, dict) or "text" not in obj:
        logger.warning(
            "parse_content_text: kein JSON-Envelope (%r)", mcp_text[:80],
        )
        out["reason"] = "no_envelope"
        return out
    out["node_id"] = obj.get("nodeId") or ""
    out["title"] = obj.get("title") or ""
    out["text"] = obj.get("text") or ""
    out["source"] = obj.get("source") or ""
    out["source_url"] = obj.get("sourceUrl") or ""
    out["char_count"] = obj.get("charCount") or 0
    out["truncated"] = bool(obj.get("truncated"))
    out["reason"] = obj.get("reason") or ""
    return out


def parse_wikipedia_summary(mcp_text: str) -> dict[str, Any]:
    """Parst ``get_wikipedia_summary`` (outputFormat=json) in einen Kurzinfo-Block.

    Envelope des Servers (live geprüft 2026-08-01)::

        {"query": "…", "found": true,
         "summary": {"title": "…", "extract": "…", "url": "…", "lang": "de"}}
        {"query": "…", "found": false, "summary": null}

    Rückgabe (Boerdi-Namen)::

        {"title", "extract", "url"}      # alle leer, wenn nichts gefunden wurde

    Ohne ``outputFormat="json"`` antwortet das Werkzeug in Markdown. Titel und
    URL daraus zurückzuraten wäre eine Fehlerquelle in *Unterrichtsmaterial* —
    ein falsch zugeordneter Wikipedia-Artikel bekommt am Ende eine
    CC-BY-SA-Quellenangabe. Deshalb ist der Nicht-Envelope-Fall ein sauberer
    Leerfall statt eines Rateversuchs.
    """
    out: dict[str, Any] = {"title": "", "extract": "", "url": ""}
    if not mcp_text:
        return out
    try:
        obj = json.loads(mcp_text)
    except (ValueError, json.JSONDecodeError):
        obj = None
    if not isinstance(obj, dict) or "found" not in obj:
        logger.warning(
            "parse_wikipedia_summary: kein JSON-Envelope (%r)", mcp_text[:80],
        )
        return out
    summary = obj.get("summary")
    if not isinstance(summary, dict):
        return out
    out["title"] = summary.get("title") or ""
    out["extract"] = summary.get("extract") or ""
    out["url"] = summary.get("url") or ""
    return out
