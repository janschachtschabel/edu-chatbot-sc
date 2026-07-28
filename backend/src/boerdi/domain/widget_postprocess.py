"""Widget-modes display-effects postprocess (verbatim port of ALT
``chat_postprocess._apply_widget_modes_postprocess``): the sync response finalizer that
applies the three display toggles (canvas / cards / quick-replies disabled) plus the
unconditional external-URL->repo rewrite and guide-QR inline extraction. Sync, no I/O
beyond the ``load_widget_modes_config`` fassade -> ``domain/`` (canvas precedent: pure
sync logic here, the async ``_postprocess_response_for_widget_modes`` orchestrator lands
in ``services/`` later).

**NEU-Portierung:** the function body is byte-identical to ALT (AST-diff gate); the only
deviations are import roots (``app.`` -> ``boerdi.``, incl. the in-function
``load_widget_modes_config`` import). With NEU's compat-echo ``_widget_modes`` (all-True)
the ``not modes[...]`` disable branches are unreachable at runtime, but ``modes`` is a
parameter, so they are preserved verbatim (reachability can only be proven once the
orchestrator caller is ported -> simplification deferred to a later deliberate pass).
"""

from __future__ import annotations

import logging
import re as _re
from typing import Any

from boerdi.domain.cards.build import _apply_llm_card_selection
from boerdi.domain.content_types import _user_wants_specific_content_type
from boerdi.domain.inline_rendering import _build_inline_card_links
from boerdi.domain.url_helpers import _rewrite_external_urls_to_repo

logger = logging.getLogger(__name__)


def _apply_widget_modes_postprocess(
    modes: dict[str, bool],
    quick_replies: list[str],
    cards: list[Any],
    page_action: dict[str, Any] | None,
    response_text: str,
    guide_mode_on: bool,
    user_message: str = "",
    selected_card_ids: list[str] | None = None,
) -> tuple[list[str], list[Any], dict[str, Any] | None, str]:
    """Wendet die 3 Display-Toggle-Effekte auf die fertige Response an.

    Reihenfolge wichtig:
    1. ``canvas_enabled=false`` zuerst — wenn Canvas aus, müssen wir den
       Canvas-Markdown aus der ``page_action`` zurück in ``response_text``
       holen, BEVOR wir entscheiden, ob Cards inline gerendert werden.
    2. ``cards_enabled=false`` danach — wenn Cards aus, hängen wir die
       (jetzt finalen) Cards als Markdown-Liste an ``response_text`` an
       und leeren die Card-Liste.
    3. ``quick_replies_enabled=false`` zuletzt — Quick-Replies komplett
       wegfallen lassen.
    """
    from boerdi.services.config_loader import load_widget_modes_config as _lwm

    # ── Welle C Sprint 6 Hotfix: Lotsen-URL-Konsistenz ───────────────
    # Bevor der Inline-Card-Append oder andere Text-Mutationen laufen,
    # rewrite externe URLs (``card.url`` = z.B. youtube.com) im LLM-
    # generierten Bot-Text auf die jeweilige Repo-Render-URL (``card.link``
    # / ``card.wlo_url``). Greift nur wenn Lotsen-Modus aktiv ist —
    # im Normal-Modus bleiben externe Links unverändert (der User
    # springt absichtlich raus).
    response_text = _rewrite_external_urls_to_repo(
        response_text, cards or [], guide_mode_on,
    )

    # Vor jeder Transformation festhalten, ob die Antwort eine "echte"
    # Information anbietet (Cards oder Canvas-Material). Lotsen-Inline-
    # Links zu RAG-Quellen (FAQ, WLO-Webseite, Fachportale…) sind nur
    # dann sinnvoll, wenn die Antwort sonst rein textuell wäre. Sobald
    # Cards oder ein Canvas-Dokument im Spiel sind, lenken zusätzliche
    # Off-Topic-Links nur ab und sehen wie Werbung aus — der User möchte
    # dann die Hauptinformation lesen.
    _has_substantive_content = bool(cards) or (
        isinstance(page_action, dict)
        and page_action.get("action") in {
            "canvas_open", "canvas_update", "canvas_show_cards",
        }
        and (
            page_action.get("action") != "canvas_show_cards"
            or ((page_action.get("payload") or {}).get("cards"))
        )
    )

    # ── 1) canvas_enabled=false ──────────────────────────────────────
    if not modes["canvas_enabled"] and page_action and isinstance(page_action, dict):
        action = page_action.get("action") or ""
        payload = page_action.get("payload") or {}
        if action in {"canvas_open", "canvas_update"}:
            md = (payload.get("markdown") or "").strip() if isinstance(payload, dict) else ""
            if md:
                # Sentinel-HTML-Kommentar als Marker für das Frontend.
                # Das Frontend nutzt ihn um:
                #   1. den Marker beim Render zu strippen (DOMPurify-safe),
                #   2. einen Print-/PDF-Button für genau diese Nachricht
                #      anzuzeigen (analog zum Lernpfad-Print-Button),
                #   3. eine treffende Print-Überschrift zu setzen.
                # Format: <!-- boerdi:printable-canvas|<type>|<title> -->
                # <type> ist material_type aus dem Canvas-Payload
                # (z.B. "lernpfad", "arbeitsblatt", "quiz"); <title> ist
                # der vom Backend gesetzte Dokument-Titel.
                _ct_type = ""
                _ct_title = ""
                if isinstance(payload, dict):
                    _ct_type = str(payload.get("material_type") or "material").strip().lower()
                    _ct_title = str(payload.get("title") or "Material").strip()
                # Pipe in title escapen, damit das Parsing im Frontend
                # nicht durcheinanderkommt.
                _ct_title_safe = _ct_title.replace("|", "/").replace("-->", "--&gt;")
                sentinel = f"<!-- boerdi:printable-canvas|{_ct_type}|{_ct_title_safe} -->"
                # Markdown ins Chat-Text einbauen, Canvas-Action droppen.
                response_text = (
                    response_text + "\n\n" + sentinel + "\n\n" + md
                ).strip()
            page_action = None
        elif action == "canvas_show_cards":
            # Cards aus dem Canvas-Payload zurück ins Top-Level cards-Feld
            # heben, damit (falls cards_enabled=true) die normale Card-
            # Anzeige im Chat greift. Bei cards_enabled=false werden sie
            # weiter unten zu Inline-Links transformiert.
            inner = (payload.get("cards") or []) if isinstance(payload, dict) else []
            if isinstance(inner, list) and inner:
                cards = list(inner) + list(cards or [])
            page_action = None

    # Lotsen-QRs (``__guide__|Label|URL``) werden als Inline-Markdown-Links
    # ans Antwort-Ende gehängt — aber nur, wenn die Antwort sonst rein
    # textuell wäre. Pillen-Buttons für Absprung-Links sehen UX-mäßig
    # schlecht aus; die Chatfortführungs-Pillen sollen für *Konversation*
    # da sein, nicht für Navigation. Card-Buttons (``card.guide_url``)
    # sind ein separater Mechanismus und bleiben unverändert.
    def _extract_guide_inline(qrs: list[str]) -> tuple[list[str], list[str]]:
        kept: list[str] = []
        inline: list[str] = []
        for qr in qrs:
            if isinstance(qr, str) and qr.startswith("__guide__|"):
                rest = qr[len("__guide__|"):]
                if "|" in rest:
                    label, url = rest.split("|", 1)
                    label = label.strip() or "Bring mich hin"
                    url = url.strip()
                    if url:
                        inline.append(f"- [{label}]({url})")
                        continue
            kept.append(qr)
        return kept, inline

    # Inline-Modus (Host-Setting cards-enabled="false") signalisiert „minimaler
    # UI-Fußabdruck — nur Kachel-Treffer als Inline-Links". RAG-Fallback-
    # Hinweise (FAQ, Themenseiten via guide_qr_injector) wären in diesem
    # Modus Lärm: der User hat die schlanke Variante gewählt, will keine
    # spekulativen Off-Topic-Hinweise. Daher Lotsen-QRs hier IMMER strippen,
    # statt sie als Inline-Markdown anzuhängen.
    #
    # AUSNAHME (Welle C.5 Refactor 2026-05-21): Wenn ``inline-result-grouping``
    # an ist (Default), gibt es im Frontend separate Box-Anzeigen für Cards
    # (Themenseiten / Sammlungen) und Webseiten-Inhalte. Dann ist
    # ``cards-enabled=false`` keine Inline-Link-Anweisung mehr, sondern nur
    # noch „keine Card-Tile-Anzeige" — die Cards bleiben aber im Array
    # erhalten und werden vom Frontend in den Boxen gerendert. Inline-Card-
    # Markdown wird in dem Fall NICHT erzeugt.
    _grouping_on_pp = modes.get("inline_result_grouping", True)
    _cards_inline_mode = (not modes["cards_enabled"]) and (not _grouping_on_pp)

    if _cards_inline_mode or _has_substantive_content:
        # Cards / Canvas-Material decken die Information ab — Lotsen-
        # Inline-Links zu RAG-Quellen wären off-topic. Lotsen-QRs aus
        # den Quick-Replies droppen, damit sie auch nicht als Pille
        # auftauchen. Inline-Mode: ebenfalls strippen (kein FAQ-Append).
        quick_replies = [
            qr for qr in quick_replies
            if not (isinstance(qr, str) and qr.startswith("__guide__|"))
        ]
        _guide_inline_lines: list[str] = []
    else:
        quick_replies, _guide_inline_lines = _extract_guide_inline(quick_replies)

    # ── 2) cards_enabled=false ───────────────────────────────────────
    # ABER: nur in den Inline-Markdown-Konversions-Pfad, wenn auch
    # ``inline-result-grouping=false`` ist. Bei aktivem Grouping bleiben
    # Cards in der Liste erhalten — das Frontend rendert sie dann in den
    # Result-Group-Boxen (Themenseiten/Sammlungen/Webseiten), nicht als
    # Tile und nicht als Inline-Markdown. Siehe ``_cards_inline_mode`` oben.
    if (not modes["cards_enabled"]) and not _grouping_on_pp:
        wm = _lwm()
        limit = int(wm.get("cards_inline_link_limit", 3))
        title_max = int(wm.get("cards_inline_link_title_max", 70))
        # Wenn die Antwort schon KI-generiertes Canvas-Material enthält
        # (Lernpfad, Arbeitsblatt, Quiz, Bericht …), die separate Inline-
        # Card-Liste NICHT zusätzlich anhängen — die wäre redundant zum
        # Material selbst (das im Lernpfad-Fall sogar die Cards bereits
        # inline referenziert). Erkannt entweder am ``boerdi:printable-
        # canvas``-Sentinel (Material-Erzeugung) oder am intrinsischen
        # Lernpfad-Marker ``**Lernpfad:``.
        _has_inline_canvas_material = (
            "boerdi:printable-canvas" in (response_text or "")
            or _re.search(r"\*\*Lernpfad:", response_text or "")
        )
        if _has_inline_canvas_material:
            logger.info(
                "inline-mode: Antwort enthält Canvas-Material — "
                "keine zusätzliche Inline-Card-Liste angehängt"
            )
            cards = []
            # page_action kann gleich raus — Inline-Material läuft komplett
            # über response_text.
            if page_action and isinstance(page_action, dict):
                _pl = page_action.get("payload") or {}
                if isinstance(_pl, dict) and "cards" in _pl:
                    _pl["cards"] = []
                    page_action["payload"] = _pl
            # (Der frühere Lotsen-Inline-Append hier war unerreichbar —
            # dieser Zweig läuft nur bei _cards_inline_mode, und dann ist
            # _guide_inline_lines immer [] — entfernt 2026-07-09.)
            # ── 3) quick_replies_enabled=false ───────────────────────────────
            if not modes["quick_replies_enabled"]:
                quick_replies = []
            return quick_replies, cards, page_action, response_text
        # PRIO 1: vom LLM via select_top_cards-Tool getroffene Auswahl
        # (siehe llm_service.py). Wenn das LLM Tool gerufen hat, ist diese
        # Liste die Quelle der Wahrheit — kein Re-Sortieren auf algorith-
        # mischer Basis. Damit folgt die Anzeige der semantischen Auswahl
        # des Modells (Klassenstufe, Material-Mix, Typ-Priorität).
        if selected_card_ids:
            cards_for_display = _apply_llm_card_selection(cards or [], selected_card_ids)
            # LLM hat schon sortiert + auf 5 begrenzt → kein algorithmischer
            # Sort mehr.
            prefer_content = False
        else:
            cards_for_display = list(cards or [])
            # Fallback: User fragt explizit nach Inhaltstyp (Video/Arbeitsblatt/…)?
            # Dann Einzelinhalte zuerst, sonst Themenseite → Sammlung → Einzel
            # (gleiche Reihenfolge wie das Canvas-Grid).
            prefer_content = _user_wants_specific_content_type(user_message)
        inline_md = _build_inline_card_links(
            cards_for_display, guide_mode_on, limit, title_max,
            prefer_content=prefer_content,
        )
        # Diagnostic log: wenn cards da sind aber inline_md leer bleibt,
        # ist meistens ein URL-Issue schuld (alle URLs leer oder nicht
        # allow-listed). Wir wollen das sehen, weil sonst der User nur
        # Text sieht und nicht weiß warum die Links fehlen.
        if cards_for_display and not inline_md:
            try:
                _diag = []
                for _c in cards_for_display[:3]:
                    _g = (lambda n: _c.get(n) if isinstance(_c, dict)  # noqa: E731, B023 — ALT
                          else getattr(_c, n, None))  # noqa: B023 — verbatim ALT
                    _diag.append({
                        "node_id": _g("node_id"),
                        "guide_url": bool(_g("guide_url")),
                        "wlo_url": bool(_g("wlo_url")),
                        "url": bool(_g("url")),
                        "title": bool(_g("title")),
                    })
                logger.warning(
                    "inline-mode: %d cards aber 0 Links — guide_mode=%s, "
                    "limit=%d, sample=%s",
                    len(cards_for_display), guide_mode_on, limit, _diag,
                )
            except Exception:
                logger.debug("inline-mode link diagnostics failed", exc_info=True)
        if inline_md:
            # Mit Leerzeile vom Bot-Text trennen, damit Markdown-Renderer
            # die Liste sauber abgrenzt.
            response_text = (response_text.rstrip() + "\n\n" + inline_md).strip()
        # Cards-Liste BEHALTEN, auch im Inline-Mode — das Frontend zeigt
        # sie nicht als Kacheln (gated durch ``cardsEnabledBool=false``),
        # aber JS-Listener / Embed-Hosts (Event-Inspector, externe Systeme
        # mit ``emit-guide-suggestion="true"``) brauchen sie, um den Top-1-
        # Treffer als ``badboerdi:guide-suggestion``-Event zu konsumieren.
        # Vorher: ``cards = []`` — Inspector im Inline-Modus blieb stumm.
        cards = cards_for_display
        # Falls die page_action noch Cards hält (z.B. show_results auf
        # /suche), ebenfalls leeren — wir wollen konsistent "keine
        # Kacheln, nur Inline-Links". Das page_action-Cards-Feld ist
        # für die Canvas-Komponente; im Inline-Mode ist Canvas eh
        # ausgeschaltet, also ist Leeren hier sinnvoll.
        if page_action and isinstance(page_action, dict):
            payload = page_action.get("payload") or {}
            if isinstance(payload, dict) and "cards" in payload:
                payload["cards"] = []
                page_action["payload"] = payload

    # ── 2b) Lotsen-Inline-Links anhängen (nach Cards-Inline, damit sie
    #         als eigene Liste darunter auftauchen) ──────────────────────
    if _guide_inline_lines:
        response_text = (
            response_text.rstrip() + "\n\n" + "\n".join(_guide_inline_lines)
        ).strip()

    # ── 3) quick_replies_enabled=false ───────────────────────────────
    if not modes["quick_replies_enabled"]:
        quick_replies = []

    return quick_replies, cards, page_action, response_text
