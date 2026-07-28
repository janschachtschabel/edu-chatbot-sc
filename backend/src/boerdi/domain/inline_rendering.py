"""Inline document/card rendering (whole-module verbatim port of ALT
``chat_inline_rendering.py``): pure formatting helpers that render cards and text to
Markdown — inline card-link lists, inline documents (M09/M10/M11 boxes), lead/body
split, title truncation, card sorting. Stateless string logic, no DB/LLM/MCP → ``domain/``.

Consumed by the widget response post-processor and turn assembly (P4-5 subtree);
content_types-sister.

**NEU-Portierung:** the module has zero app imports, so it is copied byte-for-byte from
ALT (only this docstring differs) — the whole-module AST is identical.
"""

from __future__ import annotations  # noqa: I001 — verbatim ALT (2 blank lines kept)

import re as _re  # noqa: F401 — verbatim ALT (unused; shadowed by local re-imports)
from typing import Any


_INLINE_DOC_KIND_BY_PATTERN = {
    "M09": "lernpfad",
    "M10": "ki_material",
    "M11": "edit",
}


def _inline_doc_title_for_pattern(pattern_id: str, markdown: str, topic: str = "") -> str:
    """Extrahiere einen Box-Titel aus Pattern + Markdown + Topic.

    Reihenfolge (Welle E, 2026-05-23 — präferiert kontext-passende Header):
      1. Pattern-spezifische Suchpriorität:
         * M09 Lernpfad → "Lernpfad: <Topic>"-Header bevorzugt
         * M10 KI-Material → "Arbeitsblatt: <Topic>"-Header etc.
         * M11 Edit → erstes Heading
      2. ATX-Heading (# / ##) am Anfang
      3. **Bold:**-Block
      4. Pattern-Default + Topic
    """
    import re as _re  # noqa: F811 — verbatim ALT (local re-import)
    md = (markdown or "").strip()

    # 1. Pattern-spezifische Header-Suche
    if pattern_id == "M09":
        m = _re.search(r"\*\*\s*Lernpfad\s*[:\-—]?\s*([^*\n]{1,100})\*\*", md, _re.IGNORECASE)
        if m:
            return f"Lernpfad: {m.group(1).strip()}"[:120]
        # Fallback für M09: Topic im Titel
        if topic:
            return f"Lernpfad: {topic}"[:120]

    if pattern_id == "M10":
        m = _re.search(
            r"\*\*\s*(Arbeitsblatt|Quiz|Bericht|Remix|Infoblatt|Übung|Lerngeschichte|"
            r"Versuch|Präsentation|Glossar|Checkliste|Material|Steckbrief|Vergleich|"
            r"Pressemitteilung|Factsheet|Kennzahlen)\s*[:\-—]?\s*([^*\n]{1,100})\*\*",
            md, _re.IGNORECASE,
        )
        if m:
            return f"{m.group(1).strip().capitalize()}: {m.group(2).strip()}"[:120]

    # 2. ATX-Heading am Markdown-Anfang
    m = _re.match(r"^#{1,3}\s+(.+?)\s*$", md.split("\n", 1)[0] if md else "")
    if m:
        return m.group(1).strip()[:120]

    # 3. **Bold-Header:** Zeile
    m = _re.search(r"\*\*([^*\n]{4,120})\*\*", md)
    if m:
        return m.group(1).strip()[:120]

    # 4. Fallback nach Pattern + Topic
    label = {
        "M09": "Lernpfad",
        "M10": "Material",
        "M11": "Bearbeitete Version",
    }.get(pattern_id, "Inhalt")
    if topic:
        return f"{label}: {topic}"[:120]
    return label


def _format_inline_doc_intro(template: str, topic: str = "") -> str:
    """Render the intro_text template with ``{topic_suffix}`` substitution.

    Wenn ``topic`` leer ist, wird ``{topic_suffix}`` zu "". Sonst zu
    " zum Thema *Topic*". Kein KeyError-Risk wenn das Template anderen
    Placeholder enthält — fehlende Keys bleiben als ``{key}`` stehen.
    """
    suffix = f" zum Thema *{topic}*" if topic else ""
    try:
        return template.format(topic_suffix=suffix)
    except Exception:
        return template


_GENERIC_LEAD_PHRASES = (
    "hier ist dein material",
    "hier ist ihr material",
    "hier ist dein lernpfad",
    "hier ist ihr lernpfad",
    "so sieht es nach der anpassung aus",
    "sag bescheid",
    "geben sie bescheid",
    "sag mir gerne",
    "geben sie mir gerne bescheid",
    "magst du anpassungen",
    "möchten sie anpassungen",
)


def _strip_generic_lead_lines(lead: str) -> str:
    """Entfernt Generic-Floskel-Zeilen aus dem Lead-Block.

    Welle E v4++++ (2026-05-26, eval-e901): Der LLM produziert oft
    PARALLEL einen Generic-Eröffner (\"Hier ist dein Material — sag
    Bescheid\") UND einen substanziellen Lead (\"Ich habe dir ein
    Quiz zum Thema X erstellt\"). Wir lassen nur den substanziellen
    Lead in der Bubble — die Generic-Floskeln sind in den Pattern-MDs
    explizit als forbidden_phrases markiert.

    Die Filterung läuft zeilenweise (jede Zeile, deren lowercase-Form
    eine der ``_GENERIC_LEAD_PHRASES`` enthält UND nicht zusätzlich
    substanzielle Inhalts-Marker (`**`, `*Thema*`, Material-Typ) trägt,
    fliegt raus). Übrig bleibt der inhaltsspezifische Lead.
    """
    if not lead:
        return ""
    out_lines: list[str] = []
    for raw in lead.split("\n"):
        line = raw.strip()
        if not line:
            out_lines.append(raw)
            continue
        low = line.lower()
        is_generic = any(p in low for p in _GENERIC_LEAD_PHRASES)
        if is_generic:
            # Nur droppen, wenn die Zeile keine Material-Typ-Substanz
            # enthält (Substanz-Marker: `**Quiz**`, `**Arbeitsblatt**`,
            # `*Thema*`, "erstellt", "gekürzt", "umformuliert" usw).
            substantive_markers = ("**", "*", "erstellt", "gekürzt",
                                   "umformuliert", "angepasst", "ergänzt",
                                   "vereinfacht")
            if not any(m in line for m in substantive_markers):
                continue  # generic-only → drop
        out_lines.append(raw)
    cleaned = "\n".join(out_lines).strip()
    return cleaned


def _split_lead_and_body(markdown: str) -> tuple[str, str]:
    """Trennt den 1-2-Sätze-Lead vor dem ersten H1/H2 vom restlichen
    Markdown-Body.

    Welle E v4++++ (2026-05-26, eval-e901): Der LLM rendert in M09/M10/M11
    typischerweise einen Bot-Bubble-Lead (\"Ich habe Ihnen ein Quiz zum
    Thema *X* erstellt.\") VOR dem ersten Heading. Dieser Lead landet als
    ``ChatResponse.content`` in der Bubble; der Body (ab erstem Heading)
    geht ins InlineDocument. Generic-Floskel-Zeilen werden zusätzlich
    rausgefiltert (\"Hier ist dein Material — sag Bescheid\"), damit nur
    der substanzielle Lead in der Bubble landet. Wenn kein Lead da ist,
    kommt eine leere Bubble raus — die Box reicht für die Anzeige.

    Returns:
        (lead, body). Lead ist getrimmt + Generic-Floskel-bereinigt,
        Body ist der Rest inkl. Heading. Wenn das Markdown gar kein
        Heading enthält, ist Lead leer und Body == Markdown.
    """
    import re as _re  # noqa: F811 — verbatim ALT (local re-import)
    md = (markdown or "").strip()
    if not md:
        return "", ""

    # Suche nach erstem ATX-Heading (^# / ^## / ^### ...) — wir matchen
    # am Zeilen-Anfang.
    m = _re.search(r"(?m)^#{1,3}\s+\S", md)
    if not m:
        # Kein Heading → kein Body-Split, alles ist Lead-Material (kann
        # auch leer bleiben). Wir geben das ganze MD als Body zurück
        # damit die Box gefüllt ist und die Bubble leer.
        return "", md

    lead = md[:m.start()].strip()
    body = md[m.start():].strip()

    # Generic-Floskeln rauswerfen.
    lead = _strip_generic_lead_lines(lead)

    # Sicherheits-Cap: bei extrem langem Lead (>800 Zeichen) nur ersten
    # Absatz behalten. Normalerweise nicht nötig, da der Cleaner schon
    # das Wesentliche extrahiert.
    if len(lead) > 800:
        first_para = lead.split("\n\n", 1)[0]
        lead = first_para.strip()
    return lead, body


def _build_inline_document(
    pattern_id: str,
    markdown: str,
    display_rules: dict[str, Any],
    topic: str = "",
    extra_meta: dict[str, Any] | None = None,
    formality: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Wenn das Pattern für Box-Rendering konfiguriert ist, packe das
    Markdown in ein InlineDocument und gib einen Bubble-Lead-Text zurück.
    Sonst leere Liste + Markdown unverändert weiterreichen.

    Welle E v4++++ (2026-05-26, eval-e901): Der Bubble-Lead kommt jetzt
    aus dem LLM-Output (Text vor erstem H1/H2), NICHT mehr aus
    hartcodierten Generic-Strings. Wenn das Pattern-MD einen
    ``intro_text``-Template definiert (display-rules.yaml), gewinnt das
    Template — sonst der LLM-Lead, sonst leer.

    ``formality`` bleibt als Parameter erhalten für Studio-Template-
    Rendering, wird aber nicht mehr für hartcodierte Fallbacks genutzt.

    Returns:
        (inline_documents, lead_text_for_bubble). Liste mit 0 oder 1
        Document. Lead kann leer sein wenn der LLM keinen Lead produziert
        hat — dann sieht der User nur die Box.
    """
    md = (markdown or "").strip()
    if not md:
        return [], markdown or ""

    ind = (display_rules or {}).get("inline_documents") or {}
    if not ind.get("enabled", True):
        return [], markdown

    per_pat = ind.get("per_pattern") or {}
    if not per_pat.get(pattern_id, False):
        return [], markdown

    # Lead/Body-Split: Lead landet in der Bubble, Body in der Box.
    _lead, _body = _split_lead_and_body(md)
    box_content = _body or md

    kind = _INLINE_DOC_KIND_BY_PATTERN.get(pattern_id, "ki_material")
    title = _inline_doc_title_for_pattern(pattern_id, box_content, topic)
    meta = {"pattern": pattern_id}
    if extra_meta:
        meta.update(extra_meta)

    inline_doc = {
        "kind": kind,
        "title": title,
        "content": box_content,
        "meta": meta,
    }

    # Begleittext-Priorität:
    # 1. Studio-Template (display-rules.yaml inline_documents.intro_text.MXX)
    # 2. LLM-generierter Lead (Text vor erstem Heading im MD)
    # 3. Leer — die Box reicht aus
    template = (ind.get("intro_text") or {}).get(pattern_id, "")
    if template:
        intro = _format_inline_doc_intro(template, topic).strip()
    else:
        intro = _lead

    return [inline_doc], intro


def _truncate_title(title: str, max_chars: int) -> str:
    """Word-boundary-aware truncation with ellipsis.

    Cuts at the last whitespace before ``max_chars`` (kein Mitten-im-Wort-
    Cut), appends "…" if anything was removed. Returns the original title
    if it fits.
    """
    t = (title or "").strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    space = cut.rfind(" ")
    if space >= max_chars // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-") + "…"


def _inline_card_url(card: Any, guide_mode: bool) -> str:
    """Pick the right URL to expose in an inline link.

    Lotsen-Modus an → ``guide_url`` (Repo/WLO-Seite, falls Backend es
    annotiert hat); sonst → ``wlo_url`` (Direktlink auf Inhalt).
    Fallback: ``url`` (kann external sein) → ``content_url``.
    """
    def _g(name: str) -> str:
        v = getattr(card, name, None) if not isinstance(card, dict) else card.get(name)
        return (v or "").strip() if isinstance(v, str) else ""
    if guide_mode:
        url = _g("guide_url")
        if url:
            return url
    return _g("wlo_url") or _g("url") or _g("content_url")


def _sort_cards_for_inline(cards: list[Any], prefer_content: bool) -> list[Any]:
    """Sortiere Cards für Inline-Link-Anzeige in Gruppen.

    Default: Themenseite → Sammlungen → Einzelinhalte (wie im Canvas).
    Bei ``prefer_content=True`` (User fragt nach konkretem Format):
    Einzelinhalte → Themenseiten → Sammlungen.

    Innerhalb jeder Gruppe bleibt die ursprüngliche Reihenfolge (Relevanz
    aus MCP) erhalten.
    """
    def _g(c: Any, name: str) -> Any:
        return c.get(name) if isinstance(c, dict) else getattr(c, name, None)

    def is_topic_page(c: Any) -> bool:
        nt = _g(c, "node_type")
        if nt == "topic_page":
            return True
        return nt == "collection" and bool(_g(c, "topic_pages"))

    def is_collection_only(c: Any) -> bool:
        nt = _g(c, "node_type")
        return nt == "collection" and not _g(c, "topic_pages")

    def is_content(c: Any) -> bool:
        nt = _g(c, "node_type")
        return nt not in ("collection", "topic_page")

    topic = [c for c in cards if is_topic_page(c)]
    coll = [c for c in cards if is_collection_only(c)]
    content = [c for c in cards if is_content(c)]

    if prefer_content:
        return content + topic + coll
    return topic + coll + content


def _icon_name_for_card(card: Any) -> str:
    """Pick a Material-Symbol-Name passend zum Inhaltstyp einer Card.

    Wird beim Inline-Link-Rendering (``_build_inline_card_links``) als
    Sentinel ``@@ICON:NAME@@`` voran gestellt — das Frontend ersetzt das
    in ``renderMarkdown`` mit dem passenden Inline-SVG aus ``shared/icons.ts``.
    Damit sieht der User auf einen Blick, ob ein Inline-Treffer eine
    Themenseite, eine Sammlung oder ein einzelnes Material ist.
    """
    def _g(name: str) -> Any:
        return card.get(name) if isinstance(card, dict) else getattr(card, name, None)
    node_type = _g("node_type") or ""
    topic_pages = _g("topic_pages") or []
    if node_type == "topic_page":
        return "topic"              # Themenseite (Stern-Icon)
    if node_type == "collection":
        if topic_pages:
            return "topic"          # Themenseite (Stern-Icon)
        return "auto_stories"        # Sammlung (Buch-Stapel)
    # Einzel-Inhalt — Typ aus learning_resource_types ableiten
    types = _g("learning_resource_types") or []
    types_l = [str(t).lower() for t in types if t]
    has = lambda needle: any(needle in t for t in types_l)  # noqa: E731 — verbatim ALT
    if has("video"):
        return "play_circle"
    if has("arbeitsblatt"):
        return "article"
    if has("interaktiv"):
        return "videogame_asset"
    if has("audio"):
        return "headphones"
    if has("quiz") or has("test"):
        return "quiz"
    if has("präsent") or has("praesent"):
        return "image"
    if has("übung") or has("uebung"):
        return "edit_note"
    if has("kurs"):
        return "school"
    if has("webseite") or has("website"):
        return "language"
    return "menu_book"


def _build_inline_card_links(
    cards: list[Any],
    guide_mode: bool,
    limit: int,
    title_max: int,
    prefer_content: bool = False,
) -> str:
    """Render up to ``limit`` cards as a Markdown bullet-list of links.

    Returns "" if no usable cards remain. Each entry is::

        - [@@ICON:NAME@@ Kurztitel](URL)

    Das Frontend ersetzt das ``@@ICON:NAME@@``-Sentinel mit dem passenden
    Material-Symbol-Inline-SVG (hellgrau gestylt), damit Nutzer
    Themenseiten, Sammlungen und Einzelmaterialien optisch unterscheiden
    können — ohne Kachel-Layout.

    Reihenfolge: standardmäßig Themenseite → Sammlung → Einzelinhalt
    (analog zum Canvas-Kachel-Grid). Bei ``prefer_content=True`` (User
    fragt nach konkretem Format wie „Video", „Arbeitsblatt") kehrt sich
    das um — Einzelinhalte stehen oben, damit der Treffer-Typ den die
    User-Frage anvisiert hat, zuerst sichtbar ist.

    URL fallback chain: card.link (Card-Pipeline v2, Single Source of
    Truth) → guide_url (only when guide_mode on) → wlo_url → url →
    content_url. If even that is empty, the entry is skipped (no naked-
    text dangling). If a card has no title, the URL stands in as the
    visible label.
    """
    if not cards:
        return ""
    ordered = _sort_cards_for_inline(cards, prefer_content)
    lines: list[str] = []
    seen_urls: set[str] = set()
    for c in ordered:
        if len(lines) >= limit:
            break
        # Phase 4a: card.link bevorzugen (build_card_link Single Source of
        # Truth — collections?id= für Sammlungen, render/ für Inhalte im
        # Lotsen-Modus, externe URL im Normal-Modus). Wenn nicht gesetzt,
        # fällt der alte _inline_card_url-Pfad ein.
        url = (c.get("link") if isinstance(c, dict)
               else getattr(c, "link", "")) or ""
        if not url:
            url = _inline_card_url(c, guide_mode)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = ""
        try:
            title = (c.get("title") if isinstance(c, dict)
                     else getattr(c, "title", "")) or ""
        except Exception:
            title = ""
        title = _truncate_title(title, title_max) or url
        icon = _icon_name_for_card(c)
        # Icon-Sentinel INSIDE der Markdown-Link-Klammern, damit das Span
        # nach dem Parsen INNERHALB des ``<a>``-Tags landet und Teil der
        # Klick-Fläche wird. KEIN Leerzeichen zwischen Sentinel und Titel
        # — der Abstand kommt vom ``margin-right`` am ``.bb-inline-icon``-
        # Span (CSS). Sonst würde der Link-Underline durch das Space-
        # Zeichen vor dem Titel ziehen — optisch hässlich.
        lines.append(f"- [@@ICON:{icon}@@{title}]({url})")
    return "\n".join(lines)
