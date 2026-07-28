"""Inline-document model — ported 1:1 from ALT ``app/models/schemas.py``.

Part of the schema facade ``boerdi.api.schemas`` (import from there).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InlineDocument(BaseModel):
    """Gerahmtes Inline-Dokument im Chat-Verlauf — typischerweise
    Lernpfade (M09), KI-generierte Materialien (M10) oder iterativ
    überarbeitete Vorgänger-Versionen (M11).

    Welle E (2026-05-23) — ersetzt das frühere Canvas-Pane-Konzept:
    Statt ein separates Pane aufzumachen, rendert das Frontend den
    Markdown direkt im Chat-Verlauf als optisch konsistente Box (gleicher
    Rahmen wie die Webseiten-Inhalte-Box, aber kleinere Schrift —
    ``display_rules.inline_documents.font_size_percent``).
    """
    # ``kind`` steuert das Styling (Icon, Rahmen-Akzent) auf Frontend-
    # Seite: "lernpfad" | "ki_material" | "bericht" | "remix" | "edit".
    kind: str = "ki_material"
    # Überschrift der Box. Bei Lernpfaden z.B. "Lernpfad — Photosynthese
    # (Sek I)". Frontend zeigt sie als Box-Header über dem Markdown.
    title: str = ""
    # Markdown-Body. Wird vom Frontend via DOMPurify gerendert (gleicher
    # Renderer wie für Bot-Bubbles, kein Extra-Code nötig).
    content: str = ""
    # Optionale Metadaten — z.B. material_type, source_node_id (bei
    # Remix), discipline, educational_context.
    meta: dict[str, Any] = Field(default_factory=dict)
