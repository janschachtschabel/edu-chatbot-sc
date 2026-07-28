"""Widget embed-mode compat echo (port of ALT ``chat_widget_modes._widget_modes``):
returns the four legacy layout flags as always-``True`` so downstream postprocess/
routing code that still reads them keeps working (Welle E reduced the real embed
modes to nothing). Stateless, ignores its request → ``domain/``.

Consumed by the widget response post-processor (P4-5 subtree).

**NEU-Portierung:** ``_widget_modes`` is copied byte-for-byte from ALT (the
``req`` annotation is a PEP-563 string, so the function AST is identical); the only
change is the TYPE_CHECKING schema import path. ALT's sibling ``_display_rules`` is
deliberately NOT reproduced — NEU already bypasses that thin wrapper
(``domain/quick_reply_policy`` reads ``load_display_rules_config`` directly).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # nur für Typprüfer/IDE — die Annotationen sind Strings (PEP 563)
    from boerdi.api.schemas import ChatRequest


def _widget_modes(req: "ChatRequest") -> dict[str, bool]:  # noqa: UP037 — verbatim ALT
    """Welle E (2026-05-23) — Widget-Embed-Modi auf das Minimum reduziert.

    Layout-Steuerung (Cards/Canvas/Grouping/Quick-Replies) liegt zentral
    im Studio (display-rules.yaml). 2026-06-10: auch das letzte Embed-
    Flag ``ai_content_enabled`` wurde entfernt — KI-generierte Inhalte
    sind immer zugelassen (ein gesendetes Attribut wird ignoriert).

    Backward-Compat-Echo: cards/canvas/quick_replies/inline_result_grouping
    werden im Rückgabe-Dict immer als ``True`` mitgeliefert, damit alter
    Postprocess-/Routing-Code, der diese Keys noch liest, weiter
    funktioniert ohne explizit aufgeräumt werden zu müssen.
    """
    return {
        # Compat-Echo (Welle E entfernt). Alle deprecaten Modi sind immer
        # an aus Sicht des Backends. Nachgelagerter Code, der noch diese
        # Keys liest, verhält sich damit wie das neue Default-Layout.
        "cards_enabled": True,
        "canvas_enabled": True,
        "inline_result_grouping": True,
        "quick_replies_enabled": True,
    }
