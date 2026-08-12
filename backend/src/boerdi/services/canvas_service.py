"""Canvas-Content-Service: KI-generierte Bildungsmaterialien (P4-5, port of
ALT ``app/services/canvas_service.py``).

Phase 1 MVP: Erstellt strukturierte Markdown-Dokumente passend zum Material-Typ
und erlaubt chat-gesteuertes Editieren bestehender Canvas-Inhalte.

NEU-deviation (documented): the LLM call goes through ``llm.chat_completion``
(routing/semaphore/usage) instead of ALT's ``client``/``MODEL``/
``build_chat_kwargs`` singletons (LiteLLM has no persistent client). The
prompt-building is verbatim ALT. Precedent: llm_learning_path.py (5-6a).

The ALT re-export facade (which re-exported the canvas_intent/canvas_types/
canvas_postprocess symbols so legacy code could import them via canvas_service)
is dropped: in NEU those live at canonical homes under ``domain/canvas/`` and
consumers import from there directly. This module imports only what its own
functions need.
"""
from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.canvas.postprocess import (
    _extract_h1_title,
    _strip_empty_sections,
    _strip_latex,
)
from boerdi.domain.canvas.types import (
    get_analytical_personas,
    get_create_triggers,
    get_lrt_mapping,
    get_material_types,
    get_short_alias_whitelist,
    get_type_aliases,
    material_type_label,
)
from boerdi.i18n import DEFAULT, Locale, bot_text, language_name, template_hint
from boerdi.services import llm
from boerdi.services.wikipedia_service import fetch_wikipedia_summary

logger = logging.getLogger(__name__)


def material_type_quick_replies(lang: Locale = DEFAULT) -> list[str]:
    """Return all material-type quick-reply labels (with emoji prefix).

    Ohne Produktiv-Aufrufer (Stand C1-g2e) — der Chat baut die Chips über die
    persona-abhängige Schwester. ``lang`` steht trotzdem hier, damit die beiden
    nicht auseinanderlaufen, wenn jemand diese Fassung verdrahtet.
    """
    return [
        f"{v['emoji']} {material_type_label(v, lang)}"
        for v in get_material_types().values()
    ]


def material_type_quick_replies_for_persona(
    persona_id: str | None, lang: Locale = DEFAULT
) -> list[str]:
    """Persona-abhängige Reihenfolge der Material-Typ-Chips.

    - Bei Verwaltung/Politik/Presse/Berater/Redaktion zuerst die analytischen
      Typen (Bericht, Factsheet, …), dann 'Automatisch', dann die didaktischen.
    - Bei Lehrkraft / Schueler / Eltern / unbekannt: gewohnte Reihenfolge
      (Automatisch zuerst, dann die didaktischen Typen, analytische am Ende).
    """
    types = get_material_types()
    analytical = get_analytical_personas()

    def _label(key: str) -> str:
        v = types[key]
        return f"{v['emoji']} {material_type_label(v, lang)}"

    analytical_keys = [
        k for k, v in types.items() if v.get("category") == "analytisch"
    ]
    didactical_keys = [
        k for k, v in types.items()
        if v.get("category") != "analytisch" and k != "auto"
    ]

    if persona_id in analytical:
        order = analytical_keys + ["auto"] + didactical_keys
    else:
        order = ["auto"] + didactical_keys + analytical_keys
    return [_label(k) for k in order]


def get_material_type_category(key: str | None) -> str:
    """Return 'analytisch' or 'didaktisch' for a given material-type key."""
    types = get_material_types()
    if not key or key not in types:
        return "didaktisch"
    return types[key].get("category", "didaktisch")


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------


async def generate_canvas_content(
    topic: str,
    material_type_key: str,
    session_state: dict[str, Any] | None = None,
    memory_context: str = "",
    formality: str = "",
    requested_label: str = "",
    lang: Locale = DEFAULT,
    usage_acc: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Generate structured markdown content for a given topic and material type.

    ``usage_acc`` is optional — threaded through, the call is accounted under
    phase ``"canvas"`` (K1c). With ``max_tokens=2500`` this is the largest
    single call in the system; unbooked it understates every cost figure.

    ``formality`` (Welle E v4++ 2026-05-26): Persona-Anrede explizit
    durchreichen. Akzeptiert "siezen" / "duzen" / "sie" / "du" / "wie_user" /
    "neutral" — wenn gesetzt, baut der Helper eine harte Anrede-Direktive
    in den System-Prompt ein, damit P-ENT / P-RED / P-LEH-Anfragen nicht
    fälschlich geduzt zurückkommen.

    Returns (title, markdown_body).
    The title is derived from the first H1 in the response (fallback: topic).
    """
    _types = get_material_types()
    material_type_key = material_type_key if material_type_key in _types else "auto"
    mat = _types[material_type_key]

    entities = (session_state or {}).get("entities", {}) or {}
    learner_info = []
    if entities.get("fach"):
        learner_info.append(f"Fach: {entities['fach']}")
    if entities.get("stufe"):
        learner_info.append(f"Bildungsstufe: {entities['stufe']}")
    learner_ctx = " | ".join(learner_info) if learner_info else "allgemeine Lernende"

    category = mat.get("category", "didaktisch")
    if category == "analytisch":
        # Politik / Verwaltung / Beratung / Presse — Fokus auf Faktentreue,
        # Zitierfähigkeit und Platzhalter statt Halluzinationen.
        system = (
            "Du bist BOERDi, ein analytischer Assistent für WirLernenOnline.de.\n"
            "Du erstellst sachlich-zitierfähige Dokumente für Entscheidungsträger:innen "
            "(Politik, Verwaltung, Presse, Beratung).\n"
            f"Hintergrundkontext: {learner_ctx}.\n"
            "\n"
            "TONALITÄT: sachlich, faktenorientiert, siezend. Keine Werbesprache, keine "
            "didaktischen Formulierungen ('Lernende ...' u.ä. vermeiden, hier geht es um "
            "Entscheidungsvorlagen / Reporting).\n"
            "\n"
            "FAKTENTREUE — WICHTIG:\n"
            "- Nutze vorliegenden Kontext (Wikipedia, RAG) strikt für Zahlen und Aussagen.\n"
            "- Wenn eine Zahl oder Aussage NICHT durch den Kontext belegt ist, schreibe "
            "  [Zahl einsetzen] oder [Quelle ergänzen] — NIEMALS plausibel klingende "
            "  Zahlen erfinden. Ein Bericht mit Platzhaltern ist besser als einer mit "
            "  falschen Zahlen.\n"
            "- Benutze Markdown-Tabellen (| Kopf | … |) für Kennzahlen.\n"
            "- Kennzeichne jede zitierte Quelle am Ende im Abschnitt '## Quellen' oder "
            "  direkt inline als [Quelle](URL).\n"
            "\n"
            # C1-f2a: das Sprachwort stand hier schon — sprachabhaengig an Ort
            # und Stelle, damit der deutsche Prompt bytegleich bleibt.
            "FORMAT: Antworte AUSSCHLIESSLICH mit Markdown. Keine einleitenden Sätze "
            f"an den Nutzer, keine Codefences um das ganze Dokument. {language_name(lang)}."
        )
    else:
        # Didaktisch — Lehrkräfte / Schüler:innen / Eltern
        system = (
            "Du bist BOERDi, ein pädagogischer Assistent für WirLernenOnline.de.\n"
            f"Du erstellst didaktisch durchdachte Bildungsmaterialien. Zielgruppe: {learner_ctx}.\n"
            "Antworte AUSSCHLIESSLICH mit sauberem Markdown ohne einleitende oder abschließende Meta-Sätze.\n"
            f"Keine Codefences um das gesamte Dokument. {language_name(lang)}.\n"
            "\n"
            "FORMATIERUNGS-REGELN — WICHTIG:\n"
            "- KEINE LaTeX-Syntax verwenden. Kein \\frac{}{}, kein \\sqrt{}, keine $...$-Delimiter.\n"
            "  Der Canvas hat keinen Math-Renderer.\n"
            "- Brüche als 'Zähler/Nenner' schreiben, z.B. 3/4, 15/20. Bei Bedarf auch\n"
            "  'drei Viertel' ausgeschrieben.\n"
            "- Bruch-Vergleiche mit Platzhaltern: '3/4 __ 5/8' (zwei Unterstriche), nicht '\\_\\_'.\n"
            "- Wurzeln als 'Wurzel(9) = 3' oder 'sqrt(9)', Potenzen als '3^2' oder '3 hoch 2'.\n"
            "- Mathematische Symbole: x, y, z, pi, +, -, * (für Multiplikation), : (für Division).\n"
            "- Unicode-Sonderzeichen wie °, ², ³, ½, ¼ sind erlaubt, wenn sie besser lesbar sind."
        )

    # Welle E v4++ (2026-05-26): Persona-Anrede explizit durchreichen.
    # eval-bd3a zeigte: P-ENT × I05/I03 mit ``formality=siezen`` bekam
    # geduzte Material-Texte zurück, weil der System-Prompt oben keine
    # Anrede-Vorgabe machte. Wir hängen jetzt eine harte Direktive an.
    _formality_low = (formality or "").strip().lower()
    if _formality_low in ("sie", "siezen", "formal", "foermlich"):
        system += (
            "\n\nANREDE — KRITISCH:\n"
            "Wenn die Aufgaben Aufforderungen an die lesende Person enthalten "
            '("Erkläre ...", "Berechne ...", "Beantworte ...") UND eine Anrede '
            "nötig ist, **musst du siezen** ('Erklären Sie ...', 'Berechnen Sie ...', "
            "'Bitte beantworten Sie ...'). KEINE Du-Form. Auch in einleitenden Sätzen "
            "des Dokuments ('In diesem Arbeitsblatt lernen Sie ...', nicht 'lernst du ...'). "
            "Sachliche Aufgaben ohne direkte Anrede sind erlaubt."
        )
    elif _formality_low in ("du", "duzen", "informal"):
        system += (
            "\n\nANREDE: Du-Form verwenden ('Erkläre ...', 'In diesem Arbeitsblatt "
            "lernst du ...'). Die Persona ist Schüler:in oder Kind."
        )

    # C1-f2a: zuletzt, damit der Hinweis auch die Anrede-Direktive noch
    # ueberdeckt. Fuer Deutsch ist er leer — der Prompt bleibt bytegleich.
    system += template_hint(lang)

    mem_block = ""
    if memory_context and memory_context.strip():
        mem_block = f"\n\nBisher bekannter Kontext aus der Sitzung:\n{memory_context.strip()}\n"

    # Seitenkontext (Sammlung/Themenseite): Titel + kompendialer Text als
    # optionaler Grounding-Block, damit „Erstelle einen Inhalt zu dieser
    # Sammlung" das Kompendium als Soll-Beschreibung nutzt. Bewusst weich
    # gerahmt („nur nutzen, wenn zum Thema passend"), damit ein Kompendium,
    # das nicht zum konkreten topic passt, das Material nicht verfälscht.
    page_block = ""
    _page_meta = entities.get("_page_metadata")
    if isinstance(_page_meta, dict):
        _pm_title = (_page_meta.get("title") or "").strip()
        _pm_comp = (_page_meta.get("compendium_text") or "").strip()
        if _pm_title or _pm_comp:
            _pm_lines = [
                "\n\nKontext der aktuellen Seite (nur nutzen, wenn zum Thema passend):"
            ]
            if _pm_title:
                _pm_lines.append(f"Sammlung/Seite: {_pm_title}")
            if _pm_comp:
                _pm_lines.append(f"Kompendialer Text (Auszug): {_pm_comp[:1500]}")
            page_block = "\n".join(_pm_lines) + "\n"

    # Wikipedia-DE für fachlich belastbare Grundlagen. Fehlschlag ist
    # tolerierbar (LLM-Wissen übernimmt). Der fetch_wikipedia_summary-Helper
    # filtert bereits auf Relevanz (irrelevante Treffer werden None).
    wiki_block = ""
    wiki_used: dict[str, str] | None = None
    try:
        wiki = await fetch_wikipedia_summary(topic)
        if wiki and wiki.get("extract"):
            wiki_used = {"title": wiki["title"], "url": wiki.get("url", "")}
            # Doppel-Sicherung gegen Wikipedia-False-Positives:
            # Layer 1 (Helper-Side) macht den Relevanz-Check bereits — aber
            # heuristische Title-Prefix-Matches können trotzdem mal danebenliegen
            # (z.B. "Dreiecke" Topic Mathematik → "Dreiecker" Bergname).
            # Layer 2 (LLM-Side, hier) erlaubt dem Modell, den Treffer ZU LESEN
            # und SEMANTISCH ZU PRÜFEN, ob der Artikel wirklich zum Thema passt.
            # Bei Mismatch MUSS das LLM den Wiki-Inhalt verwerfen UND die
            # Quellenangabe weglassen — niemals falsches Wissen einbauen.
            wiki_block = (
                f"\n\nMögliche Faktenbasis aus der deutschen Wikipedia "
                f"(Artikel: \"{wiki['title']}\", {wiki.get('url','')} ):\n"
                f"{wiki['extract']}\n\n"
                f"WICHTIG — RELEVANZ-PRÜFUNG (zuerst durchführen):\n"
                f"  Vergleiche den Artikel-Titel \"{wiki['title']}\" mit dem Thema "
                f"\"{topic}\". Beziehen sie sich auf DASSELBE Konzept?\n"
                f"  - JA, passt eindeutig zum Thema → verarbeite den Extract in "
                f"eigenen Sätzen (NICHT wörtlich zitieren) UND hänge am Materialende "
                f"GENAU EINE Quellenangabe-Zeile an:\n"
                f"    *Quelle: Wikipedia-Artikel „{wiki['title']}\" ({wiki.get('url','')}). "
                f"Inhalte unter CC BY-SA 4.0 verarbeitet.*\n"
                f"  - NEIN, der Artikel handelt von etwas anderem (z.B. Bergname, "
                f"Person, Ort, gleichlautende Marke, Begriff aus anderem Fach) → "
                f"IGNORIERE den Extract komplett, baue NICHTS davon ein und "
                f"setze KEINE Quellenangabe. Nutze stattdessen ausschließlich "
                f"dein eigenes Fach-Wissen zum Thema \"{topic}\".\n"
                f"  - UNSICHER (Begriff hat mehrere Bedeutungen, Extract nur "
                f"oberflächlich verwandt) → behandle wie NEIN: nichts einbauen, "
                f"keine Quelle. Lieber kein Wiki-Bezug als ein falscher.\n"
                f"Diese Regel hat Vorrang vor allen anderen Anweisungen zur "
                f"Quellenangabe."
            )
    except Exception as e:
        logger.info("wikipedia enrichment skipped: %s", e)

    # Typ-Block: bei 'auto' + vom Nutzer genanntem (un-aliastem) Begriff den
    # Begriff durchreichen, damit das LLM das am besten passende ECHTE Format
    # aus dem Vokabular wählt und das Material entsprechend benennt.
    _req_label = (requested_label or "").strip()
    if material_type_key == "auto" and _req_label:
        _type_block = (
            f"Der Nutzer hat ausdrücklich um **{_req_label}** gebeten. "
            f"„{_req_label}\" ist kein fest definiertes Format — wähle das am "
            f"besten dazu passende Format aus der folgenden Liste und gestalte "
            f"das Material so, dass es einer „{_req_label}\" entspricht "
            f"(H1 z.B. '# {_req_label}: {topic}').\n\n"
            f"Vorgaben:\n{mat['structure']}"
        )
    else:
        _type_block = (
            f"Typ: **{mat['emoji']} {mat['label']}**\n\n"
            f"Vorgaben:\n{mat['structure']}"
        )
    prompt = (
        f"Erstelle folgendes Material zum Thema **{topic}**:\n\n"
        f"{_type_block}"
        f"{mem_block}"
        f"{page_block}"
        f"{wiki_block}\n\n"
        "Liefere ausschließlich den Markdown-Inhalt des Materials, keine Einleitungssaetze "
        "an den Benutzer. Der erste nicht-leere Ausgabe-Block MUSS eine H1-Überschrift sein.\n\n"
        "QUALITÄTS-GATES — wichtig, sonst wirkt das Material kaputt:\n"
        "1. JEDE H2-Überschrift MUSS mindestens 2 Sätze oder 3 Bullet-Points an Inhalt haben.\n"
        "   Eine reine Überschrift wie '## Differenzierung:' ohne Folgeinhalt ist VERBOTEN —\n"
        "   entweder mit Inhalt füllen oder ganz weglassen.\n"
        "2. Kein leerer Listen-Punkt ('- ') und keine 'Tipp:' / 'Hinweis:' / 'Differenzierung:'-\n"
        "   Zeilen ohne anschließenden Erklärungstext.\n"
        "3. Der letzte Ausgabe-Block muss inhaltlich vollständig sein — niemals mit einem\n"
        "   Kolon-Wort enden. Bei Token-Limit lieber einen Abschnitt weniger, dafür komplett.\n"
        "4. Wenn 'Lösungen' im Material steht, muss zu jeder Aufgabe eine Antwort folgen —\n"
        "   nicht nur 'Lösungen:' alleinstehend."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await llm.chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=2500,
            usage_acc=usage_acc,
            phase="canvas",
        )
        md = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("generate_canvas_content failed: %s", e)
        md = (
            f"# {material_type_label(mat, lang)}: {topic}\n\n"
            f"*{bot_text(lang, 'material.createFailed')}: {e}*"
        )

    md = _strip_latex(md)
    md = _strip_empty_sections(md)

    # Safety-Net: ensure the Wikipedia citation is present when a WP article
    # was fed into the prompt. The LLM sometimes drops it despite the rule.
    if wiki_used and wiki_used.get("title"):
        if "wikipedia" not in md.lower():
            src_line = (
                f"*Quelle: Wikipedia-Artikel „{wiki_used['title']}\" "
                f"({wiki_used.get('url','')}). "
                "Inhalte unter CC BY-SA 4.0 verarbeitet.*"
            )
            md = md.rstrip() + "\n\n---\n" + src_line + "\n"

    title = _extract_h1_title(md) or (
        f"{(_req_label or material_type_label(mat, lang))}: {topic}"
    )
    return title, md


# Module-level attribute shim for backward compatibility: legacy imports
# like `from canvas_service import MATERIAL_TYPES` still work and return
# a fresh dict that reflects the current YAML state at access time.
def __getattr__(name: str):  # pragma: no cover — small bridging layer
    if name == "MATERIAL_TYPES":
        return get_material_types()
    if name == "_TYPE_ALIASES":
        return get_type_aliases()
    if name == "_SHORT_ALIAS_WHITELIST":
        return get_short_alias_whitelist()
    if name == "_CREATE_TRIGGERS":
        return get_create_triggers()
    if name == "_ANALYTICAL_PERSONAS":
        return get_analytical_personas()
    if name == "_LRT_TO_MATERIAL_TYPE":
        return get_lrt_mapping()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
