"""Pure inline-grouping helpers (P5-3-Rest, extracted from ALT llm_tool_loop.py's
pure layer): the P13 result-grouping helpers that decide what the user actually
sees in ``inline_result_grouping`` mode — card-visibility predicates
(``_is_einzelinhalt_card`` / ``_is_themenseite_card`` / ``_is_pure_sammlung_card``),
the anti-hallucination UI-box-status footer (``_ui_box_state_footer``) and the
LLM-visible tool-result redaction (``_redact_search_content_for_llm``) — plus the
response-text QR/guide-line stripper (``_strip_trailing_option_lines``).

All framework-free (stdlib + logger) → ``domain/``. Verbatim 1:1 from ALT (byte-
exact contiguous extraction incl. comments); the I/O tool-loop body that consumes
them (``_assemble_messages`` / ``_run_tool_loop``) stays in ALT and is ported with
the respond/RAG layer (P6). These predicates duplicate the not-yet-ported
``chat_cards.py`` copies (kept in sync in ALT via T-4); when chat_cards lands its
slice should reuse these instead of re-duplicating.
"""

from __future__ import annotations

import logging as _log

_logger = _log.getLogger(__name__)


def _strip_trailing_option_lines(text: str, quick_replies: list[str]) -> str:
    """Sicherheitsnetz: Entfernt Quick-Reply-/„Bring mich hin"-Optionszeilen,
    die das Modell gelegentlich ZUSÄTZLICH ans Ende des Antworttexts schreibt.

    Diese Optionen gehören ausschließlich ins strukturierte ``quick_replies``-
    Feld (das Frontend rendert sie als Pillen/Buttons UNTER der Antwort) — nicht
    als fetter Text in die Chat-Blase. Es werden nur Zeilen am ENDE entfernt,
    die (nach Abzug von Markdown-Deko) exakt einem Quick-Reply entsprechen oder
    eine „Bring mich hin"-Guide-Zeile sind. Inhaltliche Sätze bleiben unberührt.
    """
    if not text:
        return text

    def _norm(s: str) -> str:
        s = s.strip().lstrip("-–—•*_ \t").rstrip("*_ \t")
        return s.rstrip(":：").strip().lower()

    qr_norm = {_norm(q) for q in (quick_replies or []) if q and q.strip()}
    lines = text.split("\n")
    while lines:
        raw = lines[-1].strip()
        if not raw:
            lines.pop()
            continue
        n = _norm(raw)
        if n and (n in qr_norm or n.startswith("bring mich hin")):
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


# Phasen-Split Teil 2 (P13): die folgenden Helper waren Closures im Rumpf
# von ``generate_response`` und lasen ``_inline_grouping_mode`` aus dem
# umgebenden Scope — jetzt Modul-Funktionen mit explizitem Parameter
# (Call-Sites: Prefetch-Injektion + Tool-Loop).
# Tools deren Ergebnis im inline_result_grouping-Modus Einzelinhalt-
# Details enthalten könnte und damit Quellen für "Arbeitsblatt"-/
# "Video"-/"Inhalt"-Leakage in den Bot-Text sind. Nicht enthalten:
# search_wlo_collections / _topic_pages / browse_collection_tree /
# get_subject_portals — deren Treffer SIND als Boxen sichtbar, der
# User sieht also was beschrieben wird.
_EINZELINHALT_LEAK_TOOLS = {
    "search_wlo_content",      # primärer Treffer-Pool für Einzelmaterialien
    "get_collection_contents",  # Sammlung-Inhalte = i.d.R. Einzelmaterialien
    "get_node_details",        # Detail-View eines konkreten (oft Einzel-)Knotens
}

def _is_einzelinhalt_card(c: dict) -> bool:
    """True wenn die Card im Frontend als Einzelinhalt rendert (also NICHT
    in den sichtbaren Boxen erscheint, nur über die Such-CTA erreichbar
    ist). Spiegelt die Frontend-Klassifikation ``isInhalt`` aus
    ``chat.component.ts``: node_type != 'collection'."""
    nt = (c.get("node_type") or "").strip().lower()
    if nt == "collection":
        return False
    # Topic-pages werden im Frontend als Themenseiten gerendert (sichtbar).
    if c.get("topic_pages"):
        return False
    return True

def _is_themenseite_card(c: dict) -> bool:
    """Frontend-Spiegel: node_type 'topic_page' ODER collection +
    topic_pages-Variants vorhanden."""
    # hält Bedingung mit chat_cards._is_themenseite_card synchron (T-4, 2026-07-10)
    if c.get("node_type") == "topic_page":
        return True
    return (c.get("node_type") == "collection"
            and bool(c.get("topic_pages")))

def _is_pure_sammlung_card(c: dict) -> bool:
    """Frontend-Spiegel: collection ohne topic_pages."""
    return (c.get("node_type") == "collection"
            and not c.get("topic_pages"))

def _ui_box_state_footer(cards: list[dict], _inline_grouping_mode: bool) -> str:
    """Strukturierte Beschreibung dessen, was der User NACH diesem Tool-
    Call in den Result-Group-Boxen tatsächlich sieht. Wird im
    inline_grouping_mode an JEDE Tool-Result-Message angehängt, damit
    die LLM bei der Text-Generation **nur über tatsächlich Sichtbares**
    spricht (Anti-Hallucination, vgl. User-Feedback 2026-05-21:
    Bot kündigte „zwei Sammlungen" an, UI zeigte keine).

    Nicht für Card-Aufzählung — nur Counts pro Box-Typ. Reihenfolge
    entspricht der Render-Reihenfolge im Chat (Themenseiten >
    Sammlungen > Webseiten-Inhalte > Such-CTA)."""
    if not _inline_grouping_mode:
        return ""
    n_topic = sum(1 for c in cards if _is_themenseite_card(c))
    n_coll = sum(1 for c in cards if _is_pure_sammlung_card(c))
    n_content = sum(1 for c in cards if _is_einzelinhalt_card(c))
    return (
        "\n\n[UI-BOX-STATUS nach diesem Tool-Call — gilt fuer deinen "
        "Antwort-Text]: "
        f"{n_topic} Themenseite(n) sichtbar, "
        f"{n_coll} Sammlung(en) sichtbar, "
        f"{n_content} Einzelinhalt(e) NICHT sichtbar (nur via Such-CTA "
        "zur externen Suche erreichbar). "
        "WAHRHEITSPFLICHT: Sprich im Text nur ueber die sichtbaren "
        "Boxen UND verweise auf die Such-CTA, wenn der User nach "
        "Einzelinhalten / Material-Typen gefragt hat. NIEMALS "
        "Sammlungen/Themenseiten erfinden, die der UI-Status nicht "
        "zeigt — das ist eine Halluzination."
    )

def _redact_search_content_for_llm(
    name: str, raw_text: str, parsed_cards: list[dict],
    _inline_grouping_mode: bool,
) -> str:
    """Im inline_result_grouping-Modus die Einzelinhalte aus dem
    LLM-sichtbaren Tool-Result-Text rausziehen — die Cards selbst
    bleiben in ``all_cards`` / Prefetch-Akkumulatoren erhalten, sodass
    Such-CTA-Count und Lernpfad-Generator (separater Flow) weiter
    Zugriff haben.

    Greift wenn:
      - inline_result_grouping-Modus aktiv UND
      - Tool gehört zu den Einzelinhalt-Quellen UND
      - die geparsten Cards enthalten mindestens 1 Einzelinhalt.

    Tools mit ausschließlich Sammlungen/Themenseiten (search_wlo_collections,
    search_wlo_topic_pages, browse_collection_tree, get_subject_portals)
    werden NICHT redacted — der User SIEHT diese Treffer.
    """
    if not (_inline_grouping_mode and parsed_cards):
        return raw_text[:4000]
    if name not in _EINZELINHALT_LEAK_TOOLS:
        return raw_text[:4000]
    einzel = [c for c in parsed_cards if _is_einzelinhalt_card(c)]
    if not einzel:
        # Tool steht zwar auf der Leak-Liste, aber konkret nur Sammlungen
        # zurückgekommen → keine Redaction nötig (z.B. get_collection_contents
        # einer Meta-Sammlung).
        return raw_text[:4000]
    n = len(einzel)
    types: dict[str, int] = {}
    for c in einzel:
        lrt = (c.get("lrt_label")
               or c.get("learning_resource_type")
               or "Inhalt")
        types[lrt] = types.get(lrt, 0) + 1
    type_summary = ", ".join(
        f"{k}x {t}" for t, k in sorted(
            types.items(), key=lambda x: -x[1],
        )[:5]
    ) or "verschiedene Typen"
    _logger.info(
        "inline_grouping: redacted %s (n=%d einzelinhalte, types=%s)",
        name, n, type_summary,
    )
    return (
        f"OK - {name} lieferte {n} Einzelinhalte "
        f"({type_summary}). Diese sind im Backend gespeichert "
        "und werden NICHT als sichtbare Items angezeigt - der "
        "User erreicht sie nur ueber die Such-CTA. WICHTIG: "
        "Du darfst diese Einzelinhalte NICHT im Antwort-Text "
        "erwaehnen, zaehlen oder typisieren (kein 'ein Video', "
        "'ein Arbeitsblatt', 'zwei Materialien', 'eine Aufgabe'). "
        "Sprich im Text NUR ueber Themenseiten und Sammlungen."
    )
