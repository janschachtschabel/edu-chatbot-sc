"""Response-prompt Layer 4: pattern brief + formality guidance (P3-3a).

1:1 port of ``_formality_guidance`` and ``_render_pattern_brief`` from ALT
``llm_classify_prompt.py:953-1111`` (they are Response-prompt helpers, not
classify helpers — see contract §4) plus ``render_pattern_layer``, the Layer-4
assembly f-string extracted from ALT ``llm_prompt_builder.py:94-128``.

Pure functions over the already-classified ``pattern_output`` dict — no config
store, no I/O. Line length is dictated by the verbatim prompt text (see the
per-file ``E501`` ignore in pyproject.toml): wrapping would change the bytes the
LLM sees, so the source lines are kept intact.
"""

from __future__ import annotations

from typing import Any


def _formality_guidance(formality: str, persona_id: str) -> str:
    """Concrete, persona-aware writing guidance for the LLM.

    The LLM historically treats ``Formality: Sie`` as a soft hint and slips
    into casual "hey, schön dass du da bist" even for journalists and civil
    servants. This helper expands the terse token into explicit examples
    and NEVER-lists, which the LLM follows much more reliably.

    2026-05-25 (eval-c4c0): Vocabulary erweitert — die Pattern-Engine
    liefert das Token aus drei Quellen mit unterschiedlichen Schreibweisen:
      - Persona-MD-Frontmatter:  "siezen" / "duzen" / "neutral" / "wie_user"
      - device-config.yaml:      "Sie" / "du" / "neutral" (Großschreibung!)
      - Tone-Modifier override:  "siezen" / "duzen"
    Vorher matched der Helper nur ``sie/formal/foermlich`` und ``du/informal/duzen``
    → "siezen" und "Sie" fielen durch zum Neutral-Block → Bot bekam keine
    explizite Anrede-Anweisung → duzte trotz P-ENT/P-RED/P-LEH/P-ELT.
    """
    f = (formality or "").strip().lower()
    # Formal personas: strict Sie + professional register
    # Akzeptiert: "sie" (device-config), "siezen" (Persona-MD), formal/foermlich (Alt-Synonyme)
    if f in ("sie", "siezen", "formal", "foermlich"):
        # Extra strictness for personas whose scores were worst in the eval.
        # 2026-05-25 (eval-c4c0): Liste war doppelt + P-ELT fehlte — aufgeräumt.
        strict = persona_id in ("P-ENT", "P-RED", "P-LEH", "P-ELT")
        # Welle E v4++++ (2026-05-26, eval-bce3): Anrede-Priorität verschärft.
        # eval-bce3 zeigte M13/M11/M03 mit P-ENT/P-LEH duzten trotz siezen-
        # Modifier, weil die Pattern-Body-Beispiele oft "du" enthalten und
        # der LLM diese mimt. Wir ergänzen einen expliziten Override-Hinweis:
        # die Anrede aus dem Modifier hat IMMER Priorität gegenüber
        # Pattern-Body-Beispielen.
        base = (
            "Schreibe ausschließlich in der Sie-Form (\"Ich kann Ihnen ...\", "
            "\"Haben Sie ...\", \"Möchten Sie ...\"). KEINE Du-Formen.\n"
            "\n"
            "**WICHTIG -- diese Sie-Anrede überschreibt alle Pattern-Body-\n"
            "Beispiele.** Falls das Pattern-Schema (z.B. M03/M13/M14) "
            "Du-Form-Beispiele enthält (\"Danke, du möchtest ...\", "
            "\"Du kannst ...\"), übersetze sie automatisch in die Sie-Form "
            "(\"Vielen Dank -- Sie möchten ...\", \"Sie können ...\"). "
            "Die Modifier-Anrede ist verbindlich."
        )
        if strict:
            extra_leh = ""
            if persona_id == "P-LEH":
                # Welle E v4+11 (2026-05-26, eval-f6f56): P-LEH driftete in
                # M15/M11/M13 trotz formality=siezen — Pattern-Body-Beispiele
                # mit „dir/du" wurden vom LLM mimt. Extra-strikte Anweisung
                # für die schwächste Persona aus den letzten 4 Eval-Runs.
                extra_leh = (
                    "\n"
                    "P-LEH SPEZIAL — Lehrkräfte-Register zwingend:\n"
                    "- Begrüßung IMMER: \"Schön, dass Sie da sind\" (NIE \"Schön, dass du da bist\")\n"
                    "- Begleitung IMMER: \"ich begleite Sie\" / \"ich unterstütze Sie\"\n"
                    "  (NIE \"ich begleite dich\" / \"ich helfe dir\")\n"
                    "- Material-Anbieten IMMER: \"ich kann Ihnen ... raussuchen\" /\n"
                    "  \"ich erstelle Ihnen\" (NIE \"ich kann dir\" / \"ich erstell dir\")\n"
                    "- Übergabe IMMER: \"Hier ist Ihr Material\" / \"Ich habe Ihnen ein\n"
                    "  Quiz erstellt\" (NIE \"Hier ist dein Material\")\n"
                    "- Edit-Bestätigung IMMER: \"Ich habe den Text gekürzt\" / \"für Ihre\n"
                    "  Unterrichtseinheit gekürzt\" (NIE \"habe ich für dich gekürzt\")\n"
                    "- Anwendungs-Hinweis IMMER: \"Sie können das Material direkt in\n"
                    "  Ihrer Unterrichtseinheit verwenden\" (NIE \"du kannst es nutzen\")\n"
                )
            return (
                f"{base}\n"
                "\n"
                "KRITISCH — Register professionell halten:\n"
                "- KEINE Grußfloskeln wie \"Hey\", \"Oh\", \"Ah\", \"Hi\", \"Klar doch\"\n"
                "- KEINE Füllwörter wie \"echt\", \"voll\", \"cool\", \"ok\", \"einfach mal\",\n"
                "  \"so'n bisschen\", \"ne\", \"mal schauen\", \"check ich\"\n"
                "- KEINE Ich-du-Komplizenschaft (\"wir zwei\", \"du weißt ja\")\n"
                "- KEINE Laden-/Regal-Metaphern: NICHT \"im Regal\", \"aus dem Regal\",\n"
                "  \"Regal schauen\", \"geholt\", \"gezogen\", \"gegriffen\", \"gestöbert\",\n"
                "  \"hier ist was\" — bei Fach-Personas sachlich benennen:\n"
                "  \"Ich habe folgende Materialien gefunden\", \"Zu Ihrem Thema liegen\n"
                "  vor:\", \"Die Suche ergibt:\"\n"
                "- Sachlich-präzise Formulierungen, keine Umgangssprache\n"
                "- Fachbegriffe (OER, Lizenz, Bildungsstufe) unkommentiert verwenden — "
                "die Persona kennt sie\n"
                "- Satz-Enden mit konkreter Info oder Frage, keine Emoji/Smileys"
                + extra_leh
            )
        return base
    # Informal personas: du but still respectful
    # ``lower()`` oben fängt schon "Du" → "du" ab; Liste deckt die drei
    # konfig-Vokabulare ab (device-config, Persona-MD, Alt-Synonym).
    if f in ("du", "duzen", "informal"):
        # P-LER wants explicitly jugendlich-friendly tone; eval showed it was
        # getting over-formal responses.
        if persona_id == "P-LER":
            return (
                "Schreibe in der Du-Form, einfach und freundlich. Kurze Sätze, "
                "keine Fachchinesisch-Häufung.\n"
                "- Beispiele: \"Ich kann dir helfen …\", \"Hast du schon probiert …\", "
                "\"Willst du, dass ich …\"\n"
                "- Locker, aber nicht albern. Keine gespielte Jugendsprache ('cringe', "
                "'lit'). Einfach natürlich.\n"
                "- KEINE Siezen-Formulierungen — der Nutzer ist Schüler:in."
            )
        return (
            "Schreibe in der Du-Form (\"Ich kann dir …\", \"Hast du …\", "
            "\"Willst du …\"). KEINE Sie-Formen.\n"
            "Freundlich-persönlich, aber keine übertriebene Umgangssprache."
        )
    # Neutral (P-AND etc.)
    return (
        "Persona nicht klar — bleibe neutral. Vermeide explizite Anrede ("
        "\"Ich kann helfen …\" statt \"Ich kann Ihnen/dir helfen …\") bis die "
        "Persona klar ist. Freundlich und offen, aber nicht übermäßig casual."
    )


def _render_pattern_brief(pattern_output: dict[str, Any]) -> str:
    """Welle E v3 (2026-05-25): structured Pattern-Brief block.

    Renders the active pattern as four explicit sections — Kernregel,
    Verbotene Formulierungen, Anti-Patterns, Pattern-Brief (body_md) —
    so the response-LLM gets each piece labelled instead of one flat
    Markdown block. Sections without content are omitted.
    """
    label = pattern_output.get("label") or pattern_output.get("id") or "?"
    core_rule = (pattern_output.get("core_rule") or "").strip()
    forbidden = pattern_output.get("forbidden_phrases") or []
    anti = pattern_output.get("anti_patterns") or []
    body_md = (pattern_output.get("body_md") or "").strip()
    resp_type = pattern_output.get("response_type", "answer")
    tone = pattern_output.get("tone", "sachlich")
    # Welle E v4+7 (2026-05-26): when_to_use als Kontext-Briefing —
    # erklärt dem Response-LLM WARUM dieses Pattern gewählt wurde.
    # Hilft das Verhalten konsistent zum Klassifizier-Trigger zu halten.
    when_to_use = pattern_output.get("when_to_use") or []

    parts: list[str] = [
        f"## Aktives Pattern: {label}",
        f"Response-Typ: {resp_type}  ·  Ton: {tone}",
    ]
    if when_to_use:
        parts.append(
            "### Warum dieses Pattern (Kontext-Briefing)\n"
            + "Du wurdest gewählt, weil eine dieser Bedingungen zutrifft:\n"
            + "\n".join(f"- {w}" for w in when_to_use[:5])
        )
    if core_rule:
        parts.append("### Kernregel (HART)\n" + core_rule)
    if forbidden:
        parts.append(
            "### Verbotene Formulierungen — NICHT verwenden\n"
            + "\n".join(f'- "{p}"' for p in forbidden)
        )
    if anti:
        parts.append(
            "### Anti-Patterns — diese Handlungen vermeiden\n"
            + "\n".join(f"- {p}" for p in anti)
        )
    if body_md:
        parts.append("### Pattern-Brief (verbindlich)\n" + body_md)
    elif not (core_rule or forbidden or anti):
        parts.append("_(kein Pattern-Brief — folge der Kernregel)_")
    return "\n\n".join(parts)


def render_pattern_layer(pattern_output: dict[str, Any], persona_id: str) -> str:
    """Layer 4 of the 5-layer response prompt: the structured pattern brief
    followed by the Anrede/Länge/RAG-URL-rules block (ALT ``llm_prompt_builder``
    :94-128). Returned as one string so the orchestrator appends it as a single
    ``system_parts`` element (the ``"\\n".join`` separators are load-bearing)."""
    return _render_pattern_brief(pattern_output) + f"""

### Anrede-Form (STRIKT einhalten — Persona-abhängig)
Formality: {pattern_output.get('formality', 'neutral')}
{_formality_guidance(pattern_output.get('formality', 'neutral'), persona_id)}

**WICHTIG — Quick-Replies (Pillen-Buttons) IMMER in Du-Form:**
Die Formality-Regel oben gilt NUR für den **Bot-Antwort-Text** (was BOERDi
dem Nutzer schreibt). Die Quick-Replies dagegen sind **nutzerseitige
Folge-Eingaben** — der Nutzer spricht BOERDi an, und der Nutzer duzt
BOERDi IMMER (BOERDi ist eine freundliche Eule, kein formaler Beamter).
- Quick-Replies in **Du-Form** schreiben, egal welche Persona-Formality
  oben gesetzt ist: „Kannst du das genauer erklären?", „Zeig mir mehr",
  „Erklär mir den Unterschied".
- **NIE Sie-Form** in Quick-Replies: NICHT „Können Sie mir helfen?",
  NICHT „Zeigen Sie mir mehr.", NICHT „Bitte erklären Sie das."
- Auch nicht „Ja, bitte sagen Sie mir …" — sondern „Ja, gerne." oder
  „Ja, sag's mir."
Länge: {pattern_output.get('length', 'mittel')} (kurz=kompakte 2-4 Saetze, ein Absatz; mittel=strukturierte Erklaerung mit 2-4 Absaetzen, gerne mit H3-Unterpunkten wenn das Thema mehrere Aspekte hat; lang=ausfuehrliche Darstellung mit mehreren Absaetzen, Beispielen und Aufzaehlungen)
Wenn internes Wissen (RAG-Kontext, query_knowledge-Ergebnisse) verfuegbar ist, nutze es inhaltlich REICH aus — der Nutzer hat explizit gefragt und erwartet eine substantielle Antwort, keine Ein-Satz-Zusammenfassung.

**ZWINGEND zu Quell-URLs (NICHT optional)**: jeder RAG-Kontext-Block beginnt mit einer Frontmatter-Zeile der Form ``**URL**: <https://…>`` oder ``source: "https://…"``. Sobald du eine **inhaltliche Aussage** aus dem RAG-Kontext entnimmst (Plattform-Erklärung, Projekt-Hintergrund, OER-Lizenz-Detail, Verein-Info, Statistik, Akteur-Beschreibung, Förder-/Projekt-Info), MUSST du im Antwort-Text mindestens **einen Markdown-Link** auf die jeweils zugehoerige Original-URL einbauen. KEINE blossen Plain-Text-Erwähnungen wie „auf der WLO-Seite findest du …" — das wird vom Frontend nicht als Link erkannt. Korrekt:

  - „Mehr dazu auf [WLO-Über-uns](https://wirlernenonline.de/ueber-wirlernenonline/)"
  - „Siehe den [OER-Bereich](https://wirlernenonline.de/oer/) und die [Themenseiten](https://wirlernenonline.de/fachportale)"
  - „Die Angebote sind auf [WissenLebtOnline](https://wp-test.wirlernenonline.de/) gebündelt, siehe insbesondere [Angebote](https://wp-test.wirlernenonline.de/angebote/)."

REGELN:
1. Mindestens **EIN** Markdown-Link pro RAG-gestützter Antwort. Bei mehreren erwähnten Konzepten gerne 2-3 Links — das erlaubt dem Frontend, mehrere Bring-mich-hin-Buttons zu rendern.
2. Nimm die KONKRETE Unter-Seite mit Pfad (``/oer/`` statt ``/``). Domain-Roots ohne Pfad sind erlaubt, aber spezifische Pfade gewinnen.
3. Schreibe die URL EXAKT wie im Frontmatter (mit ``https://``-Schema, mit allen Pfad-Segmenten). Erfinde keine Pfade, die nicht im Kontext stehen — wenn der RAG-Block ``https://x/y/`` zeigt, schreibe ``[Label](https://x/y/)``, nicht ``[Label](https://x/y/z)``.
4. Wenn du KEINEN passenden Link aus dem RAG-Kontext kennst, lass den Markdown-Link weg — erfinde nichts.
Detail: {pattern_output.get('detail_level', 'standard')}
Max. Ergebnisse: {pattern_output.get('max_items', 5)}"""
