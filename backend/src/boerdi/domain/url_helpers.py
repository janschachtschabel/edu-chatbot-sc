"""Post-answer URL helpers (whole-module verbatim port of ALT
``chat_url_helpers.py``): extract markdown/HTML links out of finished bot text
into a structured ``web_links`` box (``_extract_web_links_from_text``) and rewrite
external provider URLs to their repo render URL in guide mode
(``_rewrite_external_urls_to_repo``). Stateless, offline string/regex/urlparse
logic — no I/O, no config → ``domain/``.

Feeds ``_finalize_links_and_metas`` (web_links) and the widget response
post-processor; the rewrite keeps guide-mode single materials pointing at the
repo host rather than the external provider.

**NEU-Portierung:** the module has zero app imports, so it is copied byte-for-byte
from ALT (only this docstring differs) — the whole-module AST is identical.
"""

from __future__ import annotations

import logging
import re as _re
from typing import Any
from urllib.parse import urlparse  # noqa: F401 — shadowed by local re-import

logger = logging.getLogger(__name__)


def _extract_web_links_from_text(
    text: str,
    cards: list[Any] | None = None,
    *,
    max_links: int = 5,
    keep_bullet_labels: bool = False,
) -> tuple[str, list[dict[str, str]]]:
    """Zieht Markdown-Links ``[label](url)`` aus dem Bot-Antwort-Text raus,
    sofern sie nicht bereits zu einer Card gehören. Rückgabe:

    - **cleaned_text**: Originaltext, aber Bullet-Zeilen die nur aus
      Link bestehen sind entfernt; Inline-Links sind zu Plain-Text-
      Labels umgewandelt (``[Label](url)`` → ``Label``). Triple-Blank-
      Lines werden auf Double kollabiert.
    - **web_links**: Liste ``[{title, url}]`` der promoteten Links in
      Erscheinungsreihenfolge, dedupliziert.

    Card-URLs (``link``, ``url``, ``wlo_url``, ``topic_pages[*].url``)
    werden ausgeschlossen, damit Treffer-Kacheln nicht doppelt erscheinen
    (einmal als Card, einmal als Web-Link). Frontend liest ``web_links``
    direkt aus dem strukturierten Feld statt im Markdown zu parsen.

    ``max_links`` cappt die Liste (Default 5) — verhindert dass ein
    überschwängliches LLM 20 Links in die Box pumpt.
    """
    raw = text or ""
    # Fast-Path: nichts zu tun wenn weder Markdown- noch HTML-Link-Pattern
    # im Text auftaucht. Beide Indikatoren prüfen — sonst wären HTML-only-
    # Outputs (z.B. ``- <a href="...">X</a>``) fälschlich übersprungen.
    has_md = "[" in raw and "](" in raw
    has_html = "<a " in raw.lower() and "href" in raw.lower()
    if not has_md and not has_html:
        return raw, []

    # Card-URLs sammeln (für Filter — verhindert Duplikate mit Card-Boxen)
    card_urls: set[str] = set()
    for c in (cards or []):
        if isinstance(c, dict):
            _get = lambda k: c.get(k)  # noqa: E731, B023 — verbatim ALT
        else:
            _get = lambda k, _c=c: getattr(_c, k, None)  # noqa: E731 — verbatim ALT
        for fld in ("link", "guide_url", "wlo_url", "url", "topic_page_url"):
            v = (_get(fld) or "").strip() if _get(fld) else ""
            if v:
                card_urls.add(v)
        tps = _get("topic_pages") or []
        if isinstance(tps, list):
            for tp in tps:
                if isinstance(tp, dict):
                    tu = (tp.get("url") or "").strip()
                    if tu:
                        card_urls.add(tu)

    # Aggressive Link-Regex für ZWEI Syntax-Varianten:
    #  A) Markdown ``[label](url)`` — Standard-Bot-Output
    #  B) HTML ``<a href="url">label</a>`` — manche LLMs produzieren das,
    #     vor allem in Bullet-Listen oder bei Pattern-Outputs die HTML
    #     teilweise erlauben (gebraucht für mehr Layout-Kontrolle)
    #
    # Bullet-Variante: ganze Zeile entfernen wenn sie ausschließlich aus
    # Bullet + Link besteht. Verschiedene Bullet-Marker erlaubt: ``-`` ``*``
    # ``+`` (Markdown) sowie typografische Zeichen wie ``•`` ``◦`` ``▪`` ``·``
    # die manche LLMs trotz Markdown-Anweisung produzieren.

    # Markdown-Bullet-Line: ``- [Label](url)``  (auch mit Bold/Italic/Quote
    # um den Link, nummerierte Listen ``1. [Label](url)`` und beliebigem
    # Präfix-Text VOR dem Link wie ``- **Sammlung:** [Dreiecke](url)`` oder
    # ``- Video: [Titel](url)``. Der Präfix ist alles bis zur ersten ``[``
    # und darf ``**``/``__``/``:`` und Wörter enthalten — solange darin
    # KEIN weiterer Markdown-Link vorkommt.
    bullet_link_re = _re.compile(
        r"""^\s*
            (?:[-*+•◦▪·‣⁃▪►▶]|\d+[.)])    # Bullet ODER ``1.``/``1)`` Numbering
            \s+
            [^\[\n]{0,80}?                # optionaler Präfix vor dem Link
                                          # (Label wie ``**Sammlung:**``)
            \[([^\]\n]+)\]
            \(\s*<?(https?://.+?)>?\s*\)
            [^\[\n]{0,40}?                # optionaler Suffix nach dem Link
                                          # (Trailing-Bold/Italic-Wrapper,
                                          # Punctuation, kurze Anmerkung)
            \s*$
        """,
        _re.VERBOSE,
    )
    # HTML-Bullet-Line: ``- <a href="url">Label</a>``  (auch mit Bold)
    bullet_html_link_re = _re.compile(
        r"""^\s*[-*+•◦▪·]\s+
            (?:\*{0,2}|_{0,2})            # ggf. **/* Bold/Italic
            <a\s+[^>]*?href\s*=\s*["'](https?://[^"']+)["'][^>]*>
            ([^<]+)
            </a>
            (?:\*{0,2}|_{0,2})
            \s*$
        """,
        _re.VERBOSE | _re.IGNORECASE,
    )
    # Inline-Markdown-Link irgendwo im Text
    inline_link_re = _re.compile(
        r"""\[([^\]\n]+)\]\s*
            \(
            [^)]*?
            (https?://[^)\s>"'<]+)
            [^)]*?
            \)
        """,
        _re.VERBOSE,
    )
    # Inline-HTML-Link irgendwo im Text
    inline_html_link_re = _re.compile(
        r"""<a\s+[^>]*?href\s*=\s*["'](https?://[^"']+)["'][^>]*>
            ([^<]+)
            </a>
        """,
        _re.VERBOSE | _re.IGNORECASE,
    )

    web_links: list[dict[str, str]] = []
    seen: set[str] = set()

    def _is_material_url(url: str) -> bool:
        """True wenn ``url`` auf ein einzelnes Material zeigt (Video,
        Arbeitsblatt, externes Lehrer-Online-Modul, …) statt auf eine
        Webseite (Artikel, FAQ, Themenseite). Solche URLs gehören NICHT
        in die ``web_links``-Box „Webseiten-Inhalte" — sie sind Inhalte,
        die der LLM nur zufällig inline verlinkt hat, statt sie über die
        Card-Pipeline anzubieten.

        Heuristiken:
        - edu-sharing-Render-Pfade (``/edu-sharing/components/`` etc.)
        - Video-Plattformen (YouTube, Vimeo, Mediathekviewweb)
        - Direkt-Downloads (PDF, MP4, MP3, …)
        """
        u = (url or "").lower()
        if not u:
            return False
        # edu-sharing Material-Render-Pfade
        if (
            "/edu-sharing/components/" in u
            or "/edu-sharing/eduservlet/" in u
            or "/edu-sharing/rest/" in u
        ):
            return True
        # Video-Plattformen (YouTube, Vimeo etc. = einzelne Inhalte)
        from urllib.parse import urlparse  # noqa: F811 — verbatim ALT re-import
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        if any(host.endswith(h) for h in (
            "youtube.com", "youtu.be", "vimeo.com",
            "dailymotion.com", "twitch.tv", "tiktok.com",
        )):
            return True
        # Direkt-File-URLs (Endung)
        if u.endswith((
            ".pdf", ".mp4", ".mp3", ".wav", ".ogg", ".webm",
            ".docx", ".doc", ".pptx", ".ppt", ".odt", ".odp",
            ".zip", ".epub",
        )):
            return True
        return False

    def _record(label: str, url: str) -> bool:
        """True wenn Link aufgenommen ODER bewusst gestrippt werden soll.
        Rückgabe steuert nur die Text-Strip-Logik — ``web_links`` wird
        intern befüllt. ``True`` heißt: aus Text entfernen (Bullet) bzw.
        durch Label ersetzen (Inline). ``False`` heißt: ungültiger Input
        oder leeres Label.
        """
        label = (label or "").strip()
        url = (url or "").strip()
        if not label or not url:
            return False
        if url in seen:
            # Duplikat — aus Text strippen, aber kein 2. Eintrag in web_links
            return True
        # URL wird trotzdem aus Text entfernt, kommt aber nicht in die
        # ``Webseiten-Inhalte``-Box wenn es ein Card-Treffer ODER ein
        # einzelnes Material ist. So bleibt der Bot-Text frei von Links,
        # ohne dass die Box Materialien aufnimmt, die in die Sammlungen-
        # /Inhalte-Boxen gehören.
        skip_box = (url in card_urls) or _is_material_url(url)
        if skip_box:
            seen.add(url)
            return True
        if len(web_links) >= max_links:
            # Trotz max-Cap aus dem Text strippen — sonst stehen die
            # ersten 5 in der Box und der 6. bleibt als Underline im Text.
            seen.add(url)
            return True
        seen.add(url)
        web_links.append({"title": label, "url": url})
        return True

    # Pass 1: zeilenweise — Bullet-Link-Zeilen ganz entfernen.
    # Versucht erst Markdown-Bullet, dann HTML-Bullet — Reihenfolge
    # wichtig, damit ein gemischter Pattern wie ``- <a href=...>X</a>``
    # nicht durch die Markdown-Regex fälschlich gematcht würde.
    out_lines: list[str] = []
    for line in raw.split("\n"):
        # keep_bullet_labels (2026-06-10, Lernpfad/M09): Bullet-Zeilen mit
        # Link NICHT komplett löschen — Pass 2 ersetzt den Link durch sein
        # Label, sodass „- Material: Titel" als Erwähnung im Pfad-Text
        # stehen bleibt (der klickbare Link lebt dedupliziert in der
        # Materialien-Box darunter). Vorher zerstörte Pass 1 genau die
        # Schritt→Material-Zuordnung, die der LP-Prompt verlangt.
        if not keep_bullet_labels:
            m_md = bullet_link_re.match(line)
            if m_md and _record(m_md.group(1), m_md.group(2)):
                continue
            m_html = bullet_html_link_re.match(line)
            if m_html and _record(m_html.group(2), m_html.group(1)):
                # HTML: group(1) = url, group(2) = label (Reihenfolge anders als MD)
                continue
        out_lines.append(line)
    stripped = "\n".join(out_lines)

    # Pass 2a: Inline-Markdown-Links → "[Label](url)" durch "Label" ersetzen
    def _replace_md(match: "_re.Match[str]") -> str:  # noqa: UP037 — verbatim ALT
        label, url = match.group(1), match.group(2)
        if _record(label, url):
            return label
        return match.group(0)

    # Pass 2b: Inline-HTML-Links → "<a href="url">Label</a>" durch "Label"
    def _replace_html(match: "_re.Match[str]") -> str:  # noqa: UP037 — verbatim ALT
        # HTML-Regex hat group(1)=url, group(2)=label
        url, label = match.group(1), match.group(2)
        if _record(label, url):
            return label
        return match.group(0)

    cleaned = inline_link_re.sub(_replace_md, stripped)
    cleaned = inline_html_link_re.sub(_replace_html, cleaned)

    # Triple-Blank-Lines kollabieren (Bullet-Strip kann Lücken hinterlassen)
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, web_links


def _rewrite_external_urls_to_repo(
    text: str, cards: list[Any], guide_mode: bool,
) -> str:
    """Welle C Sprint 6 Hotfix — Lotsen-URL-Konsistenz im Bot-Text.

    Bug-Report (Inline-Widget + Lotsen): „einzelinhalte dürfen im
    lotsenmodus nicht auf die wwwurl verlinkt sein". Trotz korrekt
    annotierter ``card.link`` baute der LLM im Antwort-Text Markdown-
    Links auf ``card.url`` (externer Anbieter, z.B. ``youtube.com/...``).
    Sammlungen waren OK, weil sie keine externe URL haben — Einzel-
    inhalte aber schon.

    Fix: nach Antwort-Generierung scanne alle Markdown-Links und
    ersetze externe URLs durch die jeweilige Repo-Render-URL der
    zugehörigen Card. ``card.url`` (extern) → ``card.link`` /
    ``card.wlo_url`` (Repo). No-op wenn Lotsen aus oder keine Card-
    URL-Map verfügbar.
    """
    if not guide_mode or not text or not cards:
        return text or ""
    url_map: dict[str, str] = {}
    for c in cards:
        if isinstance(c, dict):
            ext = (c.get("url") or "").strip()
            repo = (c.get("link") or c.get("wlo_url")
                    or c.get("guide_url") or "").strip()
        else:
            ext = (getattr(c, "url", "") or "").strip()
            repo = (getattr(c, "link", "")
                    or getattr(c, "wlo_url", "")
                    or getattr(c, "guide_url", "")
                    or "").strip()
        if ext and repo and ext != repo:
            url_map[ext] = repo
    if not url_map:
        return text
    rewritten = text
    n_replaced = 0
    for ext, repo in url_map.items():
        if ext in rewritten:
            rewritten = rewritten.replace(ext, repo)
            n_replaced += 1
        else:
            # LLM often adds/removes "www." — try the opposite variant.
            if "://www." in ext:
                alt = ext.replace("://www.", "://", 1)
            elif "://" in ext:
                alt = ext.replace("://", "://www.", 1)
            else:
                continue
            if alt in rewritten:
                rewritten = rewritten.replace(alt, repo)
                n_replaced += 1
    if n_replaced:
        logger.info(
            "lotsen-mode URL-rewrite: %d external→repo replacements in response_text",
            n_replaced,
        )
    return rewritten
