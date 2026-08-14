"""Card/display payload models — ported 1:1 from ALT ``app/models/schemas.py``.

Part of the schema facade ``boerdi.api.schemas`` (import from there).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WloCard(BaseModel):
    node_id: str = ""
    title: str = ""
    description: str = ""
    disciplines: list[str] = Field(default_factory=list)
    educational_contexts: list[str] = Field(default_factory=list)
    user_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    learning_resource_types: list[str] = Field(default_factory=list)
    # Primary "open this resource" URL — external (ccm:wwwurl) for content
    # nodes, in-repo browse-URL for collections.
    url: str = ""
    # Stable in-repo URL — useful as a permalink even when `url` points to an
    # external host. Variante hängt am ``node_type``:
    #   * content     → ``/components/render/<uuid>``  (ccm:io-Permalink)
    #   * collection  → ``/components/collections?id=<uuid>``  (ccm:map-Browse)
    # Frontend kann die URL direkt nehmen ohne erneutes Pattern-Switching.
    wlo_url: str = ""
    # Direct binary download URL (no auth needed). Set on file nodes whose
    # content is hosted in edu-sharing; empty for external-link nodes,
    # collections, and anything without a binary attachment.
    download_url: str = ""
    # In-repo viewer URL for embedded PDF/video previews. Often the same as
    # `wlo_url`; differs when edu-sharing has a dedicated content endpoint.
    content_url: str = ""
    preview_url: str = ""
    # `True` = the thumbnail is a generic mediatype icon (no real preview
    # generated). Frontend can use this to suppress the thumbnail or render
    # it small instead of as a hero image.
    preview_is_icon: bool = False
    mime_type: str = ""
    file_size: int = 0
    license: str = ""
    publisher: str = ""
    node_type: str = "content"
    # Wie viele Skills die Redaktion an dieser Sammlung freigegeben hat; 0 =
    # keine Registry. Der MCP liefert ``skillRegistry`` an Sammlungstreffern
    # ungefragt mit — die Zahl kostet also keinen Zusatzabruf. Nur die Zahl,
    # keine Titel: die Kachel zeigt einen Hinweis, kein Verzeichnis (den
    # Katalog trägt der Prompt-Block, die Volltexte ``get_skill``).
    skill_count: int = 0
    topic_pages: list[dict[str, str]] = Field(default_factory=list)
    # Each entry: {url, target_group, label}
    # e.g. [{url: "https://...", target_group: "teacher", label: "Lehrkräfte"}]
    # Webseiten-Guide-Mode: same-tab-navigation target. Set by the
    # backend ONLY when (a) Environment.guide_mode is True, (b)
    # Environment.host is on the configured allow-list, and (c) at
    # least one of the URL fields above points to an allow-listed host.
    # Empty string means "no guide-target" → frontend renders the
    # regular "öffnen" / "themenseite" button instead of a "bring mich
    # hin"-button. Backwards-compatible default keeps the legacy flow
    # unchanged for clients that ignore this field.
    guide_url: str = ""
    # Card-Pipeline v2 — Single Source of Truth für den UI-Klick-Link.
    # Befüllt vom Backend via :func:`card_pipeline.build_card_link` und
    # ersetzt mittelfristig die Auswahl aus (``wlo_url`` | ``url`` |
    # ``content_url`` | ``preview_url`` | ``topic_page_url`` | ``guide_url``)
    # im Frontend.
    #
    # Modes:
    #   * Themenseiten: kuratierte ``topic_page_url`` (extern)
    #   * Sammlungen:  ``{repo}/edu-sharing/components/collections?id=…&q=…``
    #   * Einzelinhalte: ``url`` (extern) im Normal-Modus,
    #                    ``{repo}/edu-sharing/components/render/{uuid}`` im
    #                    Lotsen-Modus.
    #
    # Backward-Compat: Default leer; Bestands-Frontend ignoriert das Feld
    # und nutzt die alte URL-Logik weiter (Phase 10 zieht das Pflicht-Switch).
    link: str = ""


class QueryMetaEntry(BaseModel):
    """Metadata about a single MCP search query — forwarded from MCP server
    through backend to the frontend so the widget can display what was queried."""
    tool_name: str = ""
    query_type: str = ""
    search_term: str = ""
    criteria: list[dict[str, Any]] = Field(default_factory=list)
    pagination: dict[str, Any] = Field(default_factory=dict)
    repository_url: str = ""
    search_url: str = ""


class PaginationInfo(BaseModel):
    """Pagination metadata for card results."""
    total_count: int = 0         # Total items available (0 = unknown)
    skip_count: int = 0          # Current offset
    page_size: int = 5           # Items per page
    has_more: bool = False       # More items available?
    collection_id: str = ""      # For "load more" on collection contents
    collection_title: str = ""   # Title for display


class WebLink(BaseModel):
    """Strukturierter Web-Link aus dem Bot-Antwort-Text — typischerweise
    RAG-Quellen (FAQ-Artikel, WLO-Themenseiten, externe Referenzen) die
    der LLM während der Antwort zitiert hat. Vom Backend rausgezogen,
    damit das Frontend sie in einer eigenen Box rendern kann ohne den
    Bot-Text mit fragilen Regex zu parsen. Die zugehörigen Markdown-
    Links werden aus ``ChatResponse.content`` entfernt — Bullet-Zeilen
    komplett, Inline-Links nur die ``(url)``-Klammer (Label bleibt
    Plain-Text)."""
    title: str
    url: str


class SwimlaneBox(BaseModel):
    """Eine Schwimmlinie (Abschnitt) einer Themenseite als eigene Anzeige-Box.
    Frontend-Box-Titel = ``heading`` + „(Auszug)"; max. 3 Karten je Box."""
    heading: str = ""
    type: str = ""  # container | accordion | anchor …
    cards: list[WloCard] = Field(default_factory=list)
    has_more: bool = False  # True wenn die Themenseite mehr enthält als gezeigt


class TopicPageView(BaseModel):
    """Inhalte EINER Themenseite, nach Schwimmlinien gruppiert (Pattern M16).
    Wird ANSTELLE der normalen Sammlungs-/Inhalts-Boxen gerendert; mit
    ``topic_page_url`` als Absprung-Button auf die vollständige Themenseite."""
    variant_title: str = ""
    topic_page_url: str = ""
    swimlanes: list[SwimlaneBox] = Field(default_factory=list)
