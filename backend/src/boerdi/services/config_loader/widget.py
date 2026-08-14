"""Widget-facing loaders — port of ALT config_loader/widget.py
(defaults, clamps and normalizations 1:1; docstring details live there).
"""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def load_device_config() -> dict[str, Any]:
    return area("01-base/device-config")


def load_header_nav_config() -> dict[str, Any]:
    """{'buttons': [...]} — only valid, enabled buttons with a URL; dedup by id."""
    cfg = area("01-base/header-nav").get("header_nav") or {}
    raw = cfg.get("buttons") or []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in raw:
        if not isinstance(it, dict):
            continue
        if not bool(it.get("enabled", True)):
            continue
        url = str(it.get("url") or "").strip()
        if not url:
            continue
        bid = str(it.get("id") or "").strip() or f"btn{len(out)}"
        if bid in seen:
            continue
        seen.add(bid)
        out.append({
            "id": bid,
            "label": str(it.get("label") or "").strip() or bid,
            # C1-g1a: leer heißt „nicht gepflegt" — KEIN Rückfall auf ``bid``
            # wie oben, sonst stünde die Button-ID als englische Beschriftung
            # da statt der deutschen.
            "label_en": str(it.get("label_en") or "").strip(),
            "icon": str(it.get("icon") or "explore").strip(),
            "url": url,
            "new_tab": bool(it.get("new_tab", False)),
        })
    return {"buttons": out}


def _clamped_int(raw: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def load_widget_modes_config() -> dict[str, Any]:
    cfg = area("01-base/widget-modes").get("widget_modes") or {}
    return {
        "cards_inline_link_limit": _clamped_int(cfg.get("cards_inline_link_limit"), 5, 1, 6),
        "cards_inline_link_title_max": _clamped_int(
            cfg.get("cards_inline_link_title_max"), 70, 30, 200),
    }


def load_website_tour_config() -> dict[str, Any]:
    cfg = area("01-base/website-tour").get("website_tour")
    if not isinstance(cfg, dict):
        return {"enabled": False, "groups": [], "steps": {}}
    cfg = dict(cfg)
    cfg["enabled"] = bool(cfg.get("enabled", True))
    return cfg


_WELCOME_DEFAULT_GREETING = (
    "Hey, schön dass du da bist! Ich bin Boerdi, die schlaue Eule von "
    "WissenLebtOnline.\nIch kann dir zeigen, wie du deine Wissens- oder "
    "Lerninhalte ins KI-Zeitalter bringst? Oder ich kann dir helfen "
    "vorhandene Inhalte in unserer Datenbasis zu finden."
)
_WELCOME_DEFAULT_REPLIES = [
    "Wie bringe ich meine Inhalte ins KI-Zeitalter?",
    "Ich suche Inhalte zu einem Thema.",
    "Führe mich systematisch durch die Webseite.",
    "Was ist WissenLebtOnline?",
]


def load_welcome_config() -> dict[str, Any]:
    cfg = area("01-base/welcome-config").get("welcome") or {}
    greeting = cfg.get("greeting")
    if not isinstance(greeting, str) or not greeting.strip():
        greeting = _WELCOME_DEFAULT_GREETING
    raw_replies = cfg.get("quick_replies")
    if isinstance(raw_replies, list):
        replies = [str(r).strip() for r in raw_replies if str(r).strip()]
    else:
        replies = []
    if not replies:
        replies = list(_WELCOME_DEFAULT_REPLIES)
    tour_reply = cfg.get("tour_reply")
    tour_reply = tour_reply.strip() if isinstance(tour_reply, str) else ""
    # C1-g1a: die englischen Felder bekommen NICHT die deutschen Rückfälle
    # oben. Leer heißt „nicht gepflegt"; wer den deutschen Wert einsetzte,
    # nähme dem Widget die Unterscheidung zwischen „bewusst gleich" und
    # „fehlt" — und damit jeden späteren Rückfall auf den eingebauten
    # englischen Katalog.
    greeting_en = cfg.get("greeting_en")
    greeting_en = greeting_en.strip() if isinstance(greeting_en, str) else ""
    raw_replies_en = cfg.get("quick_replies_en")
    replies_en = (
        [str(r).strip() for r in raw_replies_en if str(r).strip()]
        if isinstance(raw_replies_en, list) else []
    )
    tour_reply_en = cfg.get("tour_reply_en")
    tour_reply_en = tour_reply_en.strip() if isinstance(tour_reply_en, str) else ""
    return {
        "greeting": greeting.strip(),
        "quick_replies": replies,
        "tour_reply": tour_reply,
        "greeting_en": greeting_en,
        "quick_replies_en": replies_en,
        "tour_reply_en": tour_reply_en,
    }


_CONTEXT_ACTIONS_DEFAULT_REPORT_URL = (
    "https://wirlernenonline.de/mitmachen/inhalt-vorschlagen/"
    "?type=quelle&node={node_id}#esform"
)
_CONTEXT_ACTIONS_DEFAULT_GREETINGS: dict[str, str] = {
    "collection": ("Du bist gerade in der Sammlung „{title}“. "
                   "Ich kenne ihren Inhalt — womit kann ich helfen?"),
    "content": ("Du schaust dir gerade „{title}“ an. "
                "Ich kann Fragen dazu beantworten — oder direkt:"),
    "topic": ("Du bist auf der Themenseite „{title}“. "
              "Ich kenne ihre Struktur — womit kann ich helfen?"),
    # Seitenkontext-Erweiterung: drei Arten, die KEIN WLO-Objekt sind. Ihr
    # Platzhalter ist deshalb ein anderer — `{query}` bzw. `{host}` statt
    # `{title}`: es gibt keinen Knoten, dessen Titel sich auflösen liesse.
    "search": ("Du siehst gerade die Treffer zu „{query}“. "
               "Ich kann die Suche verfeinern oder etwas dazu erklären."),
    "home": "Du befindest Dich auf {host}. Womit fangen wir an?",
    "external": ("Du bist auf {host} — das gehört nicht zu WLO. Ich kann mir "
                 "die Seite ansehen und sie für den Bestand vorschlagen."),
}
# Nutzer-Vorgabe 2026-08-13 (P7), wortgleich mit
# ``seeds/01-base/context-actions.yaml`` — ``test_context_action_pills`` hält die
# beiden Listen zusammen. Sie stehen zweimal, weil der Loader ohne
# Datenbankeintrag eine Vorgabe braucht und die Redaktion eine Datei; bis P7
# waren sie gedriftet (hier fehlte JEDES ``label_en``, und bei ``kind: text``
# heisst das: einem englischen Nutzer deutschen Text in den Mund gelegt).
#
# Zwei Beschriftungen sind nachgemessen und nicht frei wählbar: „Stunde planen"
# (nicht „Unterrichtsstunde…" — das Wort steht in ``lp_intent._lp_keywords``,
# und der Schnellweg liefe vor der Musterwahl) und „Webseiten-Tour starten"
# (enthält „tour starten" aus ``website-tour``, wo ein harter Phrasenvergleich
# entscheidet). Die ausführliche Begründung steht im Kopf der Seed-Datei.
_CONTEXT_ACTIONS_DEFAULT_PILLS: dict[str, list[dict[str, str]]] = {
    "collection": [
        {"label": "Sammlungsinhalte zeigen", "label_en": "Show collection contents",
         "kind": "action", "action": "browse_collection"},
        {"label": "Stunde planen", "label_en": "Plan a lesson", "kind": "text"},
        {"label": "Sammlung kuratieren", "label_en": "Curate collection",
         "kind": "action", "action": "curate_collection"},
        {"label": "Zu Lehrplänen beraten", "label_en": "Advise on the curriculum",
         "kind": "text"},
        {"label": "Inhalt melden", "label_en": "Report content", "kind": "report"},
    ],
    "content": [
        {"label": "Mehr Details zeigen", "label_en": "Show more details", "kind": "text"},
        {"label": "Volltext abrufen und bearbeiten", "label_en": "Open the full text",
         "kind": "action", "action": "show_content_text"},
        {"label": "Inhalte remixen", "label_en": "Remix this content", "kind": "text"},
        {"label": "Ähnliche Inhalte suchen", "label_en": "Find similar content",
         "kind": "text"},
        {"label": "Inhalt melden", "label_en": "Report content", "kind": "report"},
    ],
    "topic": [
        {"label": "Themenseiteninhalte zeigen", "label_en": "Show topic page contents",
         "kind": "action", "action": "browse_collection"},
        {"label": "Stunde planen", "label_en": "Plan a lesson", "kind": "text"},
        {"label": "Sammlung kuratieren", "label_en": "Curate collection",
         "kind": "action", "action": "curate_collection"},
        {"label": "Zu Lehrplänen beraten", "label_en": "Advise on the curriculum",
         "kind": "text"},
        {"label": "Inhalt melden", "label_en": "Report content", "kind": "report"},
    ],
    "search": [
        {"label": "Videos zum Thema", "label_en": "Videos on this topic", "kind": "text"},
        {"label": "Arbeitsblätter zum Thema", "label_en": "Worksheets on this topic",
         "kind": "text"},
    ],
    "home": [
        {"label": "Informiere mich über WLO", "label_en": "Tell me about WLO",
         "kind": "text"},
        {"label": "Webseiten-Tour starten", "label_en": "Start the web tour",
         "kind": "text"},
        {"label": "Inhalte finden", "label_en": "Find content", "kind": "text"},
        {"label": "Kontakt und mitmachen", "label_en": "Contact and get involved",
         "kind": "text"},
    ],
    # WÖRTLICH aus M20s `trigger_phrases`. Bei `kind: text` IST die
    # Beschriftung die Nachricht, die der Klick sendet — sie muss also das
    # Muster auslösen, nicht bloss gut klingen. Eine frei erfundene Formulierung
    # wäre eine Schaltfläche, die nichts tut. `action`-Chips scheiden hier aus:
    # es gibt keine Direkt-Aktion fürs Erschliessen (nur browse_collection,
    # curate_collection, generate_learning_path, show_content_text) — der Weg
    # führt über M20.
    "external": [
        {"label": "Nimm diese Seite in WLO auf", "label_en": "Add this page to WLO",
         "kind": "text"},
        {"label": "Was steht auf der Seite, und passt das zu uns",
         "label_en": "What is on this page, and does it fit us", "kind": "text"},
    ],
}
# Zweite Lesart von `external`: die Dublettenprüfung hat die Seite im Bestand
# gefunden. {title} ist der Titel des GEFUNDENEN Eintrags, nicht der der Seite.
_CONTEXT_ACTIONS_DEFAULT_DUPLICATE_GREETING = (
    "Diese Seite gibt es in WLO schon: „{title}“."
)
_CONTEXT_ACTIONS_DEFAULT_DUPLICATE_PILL = "Den vorhandenen Eintrag ansehen"
_CONTEXT_ACTIONS_DEFAULT_CURATE_PROMPT = (
    "Das Kompendium beschreibt, was die Sammlung inhaltlich abdecken SOLL. Die "
    "Inhaltsliste zeigt, was IST. Nenne konkret: (1) gut abgedeckte Kernthemen, "
    "(2) Lücken (im Kompendium beschrieben, aber ohne passenden Inhalt), "
    "(3) je Lücke einen konkreten Suchvorschlag."
)
# Welche Seitenarten überhaupt einen Text haben können. Diese Liste ist eine
# STILLE SPERRE: was hier fehlt, wirft der Loader aus der Config, bevor der
# Knoten es je sieht — ein gepflegter Seed-Text käme wirkungslos an. Sie muss
# deshalb mit ``context_greeting._GREETABLE_KINDS`` übereinstimmen; ein Test
# prüft das gegeneinander.
_CONTEXT_ACTIONS_PAGE_KINDS = (
    "collection", "content", "topic", "search", "home", "external",
)
_CONTEXT_ACTIONS_PILL_KINDS = ("action", "text", "report")


def _normalize_context_pills(
    raw: Any, default: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Drop labelless / unknown-kind / actionless-action pills; fall back to
    the per-kind defaults when nothing valid remains (ALT semantics).

    Both paths return the same shape. The German defaults carry an empty
    ``label_en``: they are the safety net for an empty config, not a place to
    maintain text (same call as ``_RULES`` in the guide injector, C1-g2a).
    """
    if not isinstance(raw, list):
        return [{**p, "label_en": ""} for p in default]
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        if not label or kind not in _CONTEXT_ACTIONS_PILL_KINDS:
            continue
        # C1-g2b: `label_en` roh durchreichen, kein Rückfall auf `label` —
        # sonst ließe sich „bewusst gleich" nicht mehr von „nicht gepflegt"
        # unterscheiden.
        pill: dict[str, str] = {
            "label": label, "label_en": str(item.get("label_en") or "").strip(),
            "kind": kind,
        }
        if kind == "action":
            action = str(item.get("action") or "").strip()
            if not action:
                continue
            pill["action"] = action
        out.append(pill)
    return out if out else [{**p, "label_en": ""} for p in default]


def load_context_actions() -> dict[str, Any]:
    cfg = area("01-base/context-actions").get("context_actions") or {}

    report_url = cfg.get("report_url")
    if not isinstance(report_url, str) or not report_url.strip():
        report_url = _CONTEXT_ACTIONS_DEFAULT_REPORT_URL

    raw_greet = cfg.get("greetings") or {}
    greetings: dict[str, str] = {}
    for kind in _CONTEXT_ACTIONS_PAGE_KINDS:
        val = raw_greet.get(kind) if isinstance(raw_greet, dict) else None
        if isinstance(val, str) and val.strip():
            greetings[kind] = val.strip()
        else:
            greetings[kind] = _CONTEXT_ACTIONS_DEFAULT_GREETINGS[kind]

    # C1-g2b: die englische Fassung bekommt KEINE Vorgabe eingesetzt. Ein
    # leerer Wert heißt „nicht gepflegt" und lässt den Knoten die deutsche
    # nehmen; die deutsche Vorgabe hier einzusetzen, verwischte den Unterschied.
    raw_greet_en = cfg.get("greetings_en") or {}
    greetings_en: dict[str, str] = {}
    for kind in _CONTEXT_ACTIONS_PAGE_KINDS:
        val = raw_greet_en.get(kind) if isinstance(raw_greet_en, dict) else None
        greetings_en[kind] = val.strip() if isinstance(val, str) else ""

    raw_pills = cfg.get("pills") or {}
    pills: dict[str, list[dict[str, str]]] = {}
    for kind in _CONTEXT_ACTIONS_PAGE_KINDS:
        raw = raw_pills.get(kind) if isinstance(raw_pills, dict) else None
        pills[kind] = _normalize_context_pills(raw, _CONTEXT_ACTIONS_DEFAULT_PILLS[kind])

    curate_prompt = cfg.get("curate_prompt")
    if not isinstance(curate_prompt, str) or not curate_prompt.strip():
        curate_prompt = _CONTEXT_ACTIONS_DEFAULT_CURATE_PROMPT

    # Die Dubletten-Fassung ist KEINE eigene Seitenart, sondern die zweite
    # Lesart von `external` — sie gehört deshalb nicht in die Seitenart-Karten
    # (sonst könnte ein Widget sie als `page_kind` senden und würde begrüßt).
    def _text(key: str, default: str) -> str:
        val = cfg.get(key)
        return val.strip() if isinstance(val, str) and val.strip() else default

    return {
        "enabled": bool(cfg.get("enabled", True)),
        "report_url": report_url.strip(),
        "greetings": greetings,
        "greetings_en": greetings_en,
        "pills": pills,
        "curate_prompt": curate_prompt.strip(),
        "duplicate_greeting": _text(
            "duplicate_greeting", _CONTEXT_ACTIONS_DEFAULT_DUPLICATE_GREETING,
        ),
        # Wie bei `greetings_en`: keine deutsche Vorgabe einsetzen, leer heißt
        # „nicht gepflegt" und lässt den Knoten die deutsche Fassung nehmen.
        "duplicate_greeting_en": _text("duplicate_greeting_en", ""),
        "duplicate_pill_label": _text(
            "duplicate_pill_label", _CONTEXT_ACTIONS_DEFAULT_DUPLICATE_PILL,
        ),
        "duplicate_pill_label_en": _text("duplicate_pill_label_en", ""),
    }


def load_display_rules_config() -> dict[str, Any]:
    cfg = area("01-base/display-rules").get("display_rules") or {}

    ind = cfg.get("inline_documents") or {}
    font_pct = _clamped_int(ind.get("font_size_percent"), 85, 70, 100)
    per_pattern: dict[str, bool] = {}
    for k, v in (ind.get("per_pattern") or {}).items():
        per_pattern[str(k).strip().upper()] = bool(v)
    for pid in ("M09", "M10", "M11"):
        per_pattern.setdefault(pid, True)
    intro_text: dict[str, str] = {}
    for k, v in (ind.get("intro_text") or {}).items():
        s = str(v or "").strip()
        if s:
            intro_text[str(k).strip().upper()] = s
    inline_documents = {
        "enabled": bool(ind.get("enabled", True)),
        "font_size_percent": font_pct,
        "per_pattern": per_pattern,
        "intro_text": intro_text,
    }

    grp = cfg.get("groups") or {}
    scb_raw = cfg.get("single_content_box") or {}
    legacy_max = scb_raw.get("max_count")

    def _grp_int(key: str, default: int, lo: int, hi: int) -> int:
        raw = grp.get(key)
        if raw is None and key == "materialien_max" and legacy_max is not None:
            raw = legacy_max  # backward-compat
        return _clamped_int(raw, default, lo, hi)

    groups = {
        "themenseiten_max": _grp_int("themenseiten_max", 3, 1, 20),
        "sammlungen_max": _grp_int("sammlungen_max", 3, 1, 20),
        "materialien_max": _grp_int("materialien_max", 3, 1, 8),
        "materialien_max_lernpfad": _grp_int("materialien_max_lernpfad", 5, 1, 8),
        "webseiten_max": _grp_int("webseiten_max", 3, 1, 30),
    }

    scb_layout = str(scb_raw.get("layout") or "card").strip().lower()
    if scb_layout not in ("card", "list"):
        scb_layout = "card"
    single_content_box = {
        "enabled": bool(scb_raw.get("enabled", True)),
        "max_count": groups["materialien_max"],  # echo-stability for old frontends
        "layout": scb_layout,
    }

    icl = cfg.get("inline_card_links") or {}
    inline_card_links = {
        "limit": _clamped_int(icl.get("limit"), 3, 1, 6),
        "title_max_chars": _clamped_int(icl.get("title_max_chars"), 70, 30, 200),
    }

    qr = cfg.get("quick_replies") or {}
    quick_replies = {
        "max_count": _clamped_int(qr.get("max_count"), 4, 0, 6),
        "inline_fallback_enabled": bool(qr.get("inline_fallback_enabled", True)),
    }

    pak = cfg.get("prompt_anzeige_konsistenz") or {}
    excl: list[str] = []
    for e in pak.get("exclude_patterns") or []:
        s = str(e or "").strip().upper()
        if s and s not in excl:
            excl.append(s)
    prompt_anzeige_konsistenz = {
        "enabled": bool(pak.get("enabled", True)),
        "exclude_patterns": excl,
    }

    return {
        "inline_documents": inline_documents,
        "single_content_box": single_content_box,
        "groups": groups,
        "inline_card_links": inline_card_links,
        "quick_replies": quick_replies,
        "prompt_anzeige_konsistenz": prompt_anzeige_konsistenz,
    }


def load_guide_rules_config() -> dict[str, Any]:
    data = area("02-domain/guide-rules")

    msg_rules: list[dict[str, Any]] = []
    for item in data.get("message_rules") or []:
        if not isinstance(item, dict):
            continue
        pat = str(item.get("pattern") or "").strip()
        lbl = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if not (pat and lbl and url):
            continue
        try:
            prio = int(item.get("priority") or 50)
        except (TypeError, ValueError):
            prio = 50
        # C1-g2a: `label_en` geht ROH durch — kein Rückfall auf `label`. Setzte
        # der Loader ihn ein, könnte niemand mehr „bewusst gleich" von „nicht
        # gepflegt" unterscheiden (dieselbe Regel wie bei der Begrüßung).
        msg_rules.append({
            "pattern": pat, "label": lbl,
            "label_en": str(item.get("label_en") or "").strip(),
            "url": url, "priority": prio,
        })

    rag_rules: dict[str, dict[str, str]] = {}
    raw_rag = data.get("rag_area_rules") or {}
    if isinstance(raw_rag, dict):
        for rag_area, cfg in raw_rag.items():
            if not isinstance(cfg, dict):
                continue
            lbl = str(cfg.get("label") or "").strip()
            url = str(cfg.get("url") or "").strip()
            bp = str(cfg.get("brand_pattern") or "").strip()
            if not (lbl and url and bp):
                continue
            rag_rules[str(rag_area).strip()] = {
                "label": lbl, "url": url, "brand_pattern": bp,
            }

    return {"message_rules": msg_rules, "rag_area_rules": rag_rules}


_PLACEHOLDER_TOPICS_DEFAULT: tuple[str, ...] = (
    "thema", "themen", "ein thema", "einem thema", "irgendwas",
    "etwas", "was", "irgendetwas", "irgendein thema", "sonstiges",
    "material", "materialien", "ein material", "ein paar materialien",
    "sachen", "dinge", "stuff", "topic", "etwas thema",
    "inhalt", "inhalte", "content",
)


def load_placeholder_topics_config() -> dict[str, Any]:
    data = area("01-base/placeholder-topics")
    raw_list = data.get("placeholder_topics")
    topics: set[str] = set()
    if isinstance(raw_list, list) and raw_list:
        for item in raw_list:
            s = str(item or "").strip().lower()
            if s:
                topics.add(s)
    if not topics:
        topics = set(_PLACEHOLDER_TOPICS_DEFAULT)
    min_length = _clamped_int(data.get("min_topic_length"), 3, 0, 10)
    return {"topics": topics, "min_length": min_length}
