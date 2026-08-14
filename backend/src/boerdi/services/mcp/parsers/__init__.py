"""MCP-Response-Parser: JSON/Text-Envelopes -> Boerdi-Card-Dicts.

1:1-Port aus ALT ``app/services/mcp_parsers.py`` — zustandslose reine Funktionen,
kein geteilter Client-/Cache-Zustand, nur ``config_loader`` für Repo-URLs
(``get_repo_base_url``/``rewrite_repo_host`` sind settings-getrieben → kein PG).
Der Leaf-Knoten des ``services/mcp``-Pakets für die Karten-Erzeugung; die Tool-
Loop (5-3) und der Reranker (5-5) konsumieren diese Parser direkt.

Diese Fassade ist die **einzige** Import-Adresse (wie bei ``config_loader``):
``from boerdi.services.mcp.parsers import parse_wlo_cards``. Sie hält den
Modulpfad stabil, den Bestands-Tests auch als Patch-Ziel benutzen
(``monkeypatch.setattr("boerdi.services.mcp.parsers.parse_wlo_cards", …)``).

W11 (2026-08-01): vorher ein Modul mit 622 Zeilen — dem Doppelten der Regel — mit
drei Gründen, sich zu ändern. Rein mechanisch zerlegt, kein Verhalten angefasst:

* :mod:`~boerdi.services.mcp.parsers.cards` — FormattedNode-Envelope → Karten
  (plus ``parse_total_count``, das dasselbe Such-Envelope liest)
* :mod:`~boerdi.services.mcp.parsers.topic_pages` — Varianten und Schwimmlinien
* :mod:`~boerdi.services.mcp.parsers.text_blocks` — Volltext und Wikipedia
* :mod:`~boerdi.services.mcp.parsers.json_scan` — der Klammer-Scanner
* :mod:`~boerdi.services.mcp.parsers.skill_registry` — die Freigabeliste, die
  ein Ergebnis nebenbei mitbringt (P1, 2026-08-13). Nachzügler zu W11 und der
  einzige Parser, der nicht für die Oberfläche liest, sondern für den Prompt.

Eine Grenze, die der Schnitt zieht: modulinterne Aufrufe (z.B. ``topic_pages``
→ ``_cards_from_json_envelope``) lösen jetzt im **definierenden** Modul auf. Ein
Test, der einen dieser Helfer ersetzen will, muss ihn dort ersetzen, nicht an der
Fassade. Für die öffentlichen Parser ändert sich nichts — keiner ruft einen
anderen intern auf (gemessen 2026-08-01).
"""

from boerdi.services.mcp.parsers.cards import (
    parse_search_all_cards,
    parse_total_count,
    parse_wlo_cards,
)
from boerdi.services.mcp.parsers.json_scan import _first_json_object
from boerdi.services.mcp.parsers.skill_registry import (
    parse_skill_registries,
    skill_registry_note,
)
from boerdi.services.mcp.parsers.text_blocks import (
    parse_content_text,
    parse_wikipedia_summary,
)
from boerdi.services.mcp.parsers.topic_pages import (
    _topic_page_display_title,
    parse_topic_page_swimlanes,
    parse_wlo_topic_page_cards,
)

__all__ = [
    "_first_json_object",
    "_topic_page_display_title",
    "parse_content_text",
    "parse_search_all_cards",
    "parse_skill_registries",
    "parse_topic_page_swimlanes",
    "parse_total_count",
    "parse_wikipedia_summary",
    "parse_wlo_cards",
    "parse_wlo_topic_page_cards",
    "skill_registry_note",
]
