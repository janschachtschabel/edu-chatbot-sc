"""Canvas-Create-Fast-Path body (P4-5, port of ALT
``chat_pipeline_phases._try_canvas_create_fast_path`` Z. 243-681) — the I05 → M10
block that turns "Erstelle ein Arbeitsblatt zur Photosynthese" into generated
canvas material without going through ``generate_response``. Sister of
``run_lp_fast_path``.

The body is a **verbatim** port of the ALT function: topic priority (classifier
→ sticky session → fach-fallback → marker-pattern → messy regex fallback with
garbage + phantom filters), the robust "named artefact → auto" fallback, the
``generate_canvas_content`` call with the Loesungen-block validator/stub, both
degradation branches, and the sticky ``session_state`` mutations. It mutates
``session_state`` in place (ALT parity: ``_canvas_material_type``/``_canvas_topic``/
``_canvas_last_markdown``/``thema``).

Home is ``services/`` (awaits the async ``generate_canvas_content``). Documented
deviations (the AST-diff gate proves the body is otherwise byte-identical):
- every helper is imported under its ALT name from the canonical NEU homes
  (``domain/canvas/{intent,types}``, ``domain/completion_messages``,
  ``services/canvas_service``) instead of ALT's ``chat_pipeline_phases`` re-imports;
- keyword-only signature + a ``CanvasFastPathResult`` NamedTuple return (field
  order = the ALT bare 7-tuple) — mirrors ``run_lp_fast_path``;
- the ALT ``_lp_routed`` parameter is renamed ``lp_routed`` (public kw name; one
  body reference in the routing guard).

**simplify (bewusste Ausnahme):** die Funktion ist deutlich laenger als der
~50-Zeilen-Schwellwert — ein 1:1-Verbatim-Port eines kohaesiven, getesteten ALT-
Blocks. Als AST-diffbare Einheit gehalten (0 Divergenz) statt in un-diffbare
Sub-Funktionen mit Zustands-Threading zu splitten; ein verhaltens-erhaltender
Split kommt nach der Graph-Verdrahtung (Integrationsdeckung vorhanden).

Verdrahtung in den Route-Node (neben ``run_lp_fast_path``) folgt als eigener Slice.
"""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from boerdi.domain.canvas.intent import (
    extract_material_type_from_message,
    named_artifact_label,
    resolve_material_type,
)
from boerdi.domain.canvas.types import get_material_types, get_type_aliases
from boerdi.domain.completion_messages import _canvas_completion_message
from boerdi.services.canvas_service import (
    generate_canvas_content,
    material_type_quick_replies_for_persona,
)

logger = logging.getLogger(__name__)


class CanvasFastPathResult(NamedTuple):
    """Outputs of the canvas-create fast-path (ALT bare 7-tuple, same order).

    ``routed`` mirrors ALT ``_canvas_routed``. When it is False the caller keeps
    the standard path's values; ``tools_called``/``new_state`` are the passed-in
    inputs echoed unchanged (ALT: the outer ``if`` block was not entered).
    """

    routed: bool
    payload_out: dict | None
    forced_quick_replies: list[str]
    response_text: str
    tools_called: list[str]
    wlo_cards_raw: list[dict]
    new_state: str


async def run_canvas_create_fast_path(
    *,
    req: Any,
    classification: Any,
    session_state: dict,
    pattern_output: dict,
    memory_context: str,
    lp_routed: bool,
    tools_called: list[str],
    new_state: str,
) -> CanvasFastPathResult:
    """Run the canvas-create fast-path; see the module docstring for the port.

    Returns a :class:`CanvasFastPathResult`; not routed (``lp_routed`` or the
    winning intent is not I05) ⇒ ``routed=False`` with the input
    ``tools_called``/``new_state`` echoed and the helper defaults elsewhere.
    """
    response_text = ""
    wlo_cards_raw: list[dict] = []
    # ── Canvas-Create via natural text (I05 + M10) ────────
    # User tippt z.B. "Erstelle ein Arbeitsblatt zur Photosynthese"
    # → Classifier setzt I05, Pattern-Engine waehlt M10
    # → wir generieren Canvas-Inhalt direkt, ohne generate_response.
    _canvas_routed = False
    _canvas_payload_out: dict | None = None
    _canvas_forced_quick_replies: list[str] = []
    # Trigger canvas flow whenever I05 is the winning intent — even if
    # the pattern engine eliminated M10 (e.g. precondition_slots missing).
    # In that case we want to show the material-type degradation, not fall
    # through to a generic M03 Clarification response.
    if (not lp_routed
            and classification.intent_id == "I05"):
        # Topic priority (fixes "stale topic" bug, same logic as material_typ):
        # 1. classifier extraction from THIS turn
        # 2. sticky session value (prior turn) — only when classifier is silent
        # 3. Welle E v4+5: Fach-Fallback — wenn weder topic noch session
        #    topic gesetzt sind, aber ein `fach` (Mathe/Deutsch/Bio/...) als
        #    Entity vorliegt, verwende das Fach als Topic. Greift bei „Quiz
        #    für meine Klausur in Mathe" → topic=Mathe (M10 kann arbeiten
        #    statt in M03-Klärung-Loop zu fallen).
        _c_topic = (
            ((classification.entities or {}).get("thema") or "").strip()
            or (session_state.get("entities", {}).get("thema") or "").strip()
            or ((classification.entities or {}).get("fach") or "").strip()
            or (session_state.get("entities", {}).get("fach") or "").strip()
        )
        # Type priority (fixes "stale type" bug):
        # 1. direct extraction from THIS turn's message (covers chip-clicks
        #    like "Rollenspielkarten" after a prior Infoblatt creation)
        # 2. classifier entity for this turn
        # 3. fallback to sticky session value from prior turn
        _mt_key = (
            extract_material_type_from_message(req.message)
            or resolve_material_type(
                (classification.entities or {}).get("material_typ", "")
            )
            or resolve_material_type(
                session_state.get("entities", {}).get("material_typ", "")
            )
        )

        # Topic-Fallback: wenn der Classifier kein 'thema' extrahiert hat,
        # aber Material-Typ bekannt ist, nutze die User-Message selbst als
        # Topic (nach Bereinigung: Create-Verben + Material-Typ-Wort raus).
        # Deckt analytische Anfragen ab, wo 'thema' oft komplex ist
        # ('OER-Lage in Deutschland', 'Vergleich WLO vs Schulbücher', etc.).
        if not _c_topic and _mt_key:
            import re as _re_topic

            # ── First-class extraction: explicit topic markers ──────
            # Most natural German create requests follow patterns like:
            #   "… zum Thema X …", "… über X …", "… zu X für Y …"
            # Extract just the noun phrase after the marker — that gives
            # us a much cleaner topic than stripping the full sentence.
            _msg_low = (req.message or "")
            _marker_match = _re_topic.search(
                r"\b(?:zum\s+thema|zu\s+dem\s+thema|über\s+das\s+thema|"
                r"über|zur|zum|zu)\s+"
                r"(?P<topic>[A-ZÄÖÜa-zäöüß][\wäöüÄÖÜß\s\-]{2,80}?)"
                r"(?=[,.?!]|\s+(?:für|zur|zum|in\s+der|im|auf|mit|"
                r"das\s+wäre|und\s+|bitte|gern|gerne|schritt)|\s*$)",
                _msg_low,
                flags=_re_topic.IGNORECASE,
            )
            if _marker_match:
                _candidate = _marker_match.group("topic").strip()
                # Clean trailing fillers + capitalise nicely
                _candidate = _re_topic.sub(r"\s+", " ", _candidate).strip(" .,:;-")
                if 3 <= len(_candidate) <= 80:
                    _c_topic = _candidate
                    # Skip the rest of the messy fallback
                    logger.info("Topic extracted via marker pattern: %r", _c_topic)

        if not _c_topic and _mt_key:
            import re as _re_topic
            _fallback = (req.message or "").strip()
            # strip role-prefixes like "Ich bin Lehrerin und möchte...", "Als
            # Redakteurin brauche ich..." — these are identity statements, not
            # topics. Must happen BEFORE verb-stripping so the subsequent strip
            # can find the verb.
            _fallback = _re_topic.sub(
                r"^\s*(ich\s+bin\s+\w+(?:in)?|"
                r"als\s+\w+(?:kraft|ist[in]*|e?r?|in)?)\b"
                r"[,\s]+(und\s+)?",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )
            # strip leading create verbs (including polite Sie-Form)
            _fallback = _re_topic.sub(
                r"^\s*(erstelle?|generiere?|mach(?:\s+mir)?|bau\s+mir|schreib\s+mir|"
                r"entwirf|produziere|ich\s+brauche|brauche|ich\s+benötige|benötige|"
                r"ich\s+möchte|möchte|ich\s+hab(?:e)?|hab(?:e)?|ich\s+suche|suche|"
                r"hätte\s+ger?n|gib\s+mir|kannst\s+du|könntest\s+du|könnten\s+sie|"
                r"können\s+sie|würden\s+sie|würdest\s+du|hätten\s+sie|haben\s+sie|"
                r"fasse\s+zusammen|wandle)"
                r"\s+(mir\s+)?(bitte\s+)?(ein|eine|einen|die|der|das|den)?\s*",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )
            # strip the detected material-type word
            _aliases = get_type_aliases()
            for _alias in sorted((k for k in _aliases.keys()), key=len, reverse=True):
                if len(_alias) >= 4 and _aliases[_alias] == _mt_key:
                    _fallback = _re_topic.sub(
                        rf"\b{_re_topic.escape(_alias)}\b", "", _fallback,
                        flags=_re_topic.IGNORECASE,
                    )
            # strip leading role prefixes ("als Verwaltungskraft", "als Journalist")
            _fallback = _re_topic.sub(
                r"^\s*als\s+\w+(?:kraft|ist[in]*|e?r?|in)\b[\s,]*",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )
            # strip "zu", "über", "zum", "zur" + collapse whitespace
            _fallback = _re_topic.sub(r"^\s*(zu|über|zum|zur|ueber)\s+", "", _fallback, flags=_re_topic.IGNORECASE)

            # NEW: cut off subordinate clauses like "…, das mein Sohn nutzt"
            # / "…, mit dem die Schüler üben" / "…, dass meine Klasse versteht".
            # The relative clause is just background context, not part of the
            # topic. Without this, the topic became "Mathe in der 3. Klasse,
            # das mein Sohn für seine Hausaufgaben nutze…". Must run BEFORE
            # the trailing-verb stripper so the verb (which is now exposed at
            # end-of-string) can be removed in the next step.
            _fallback = _re_topic.sub(
                r"\s*,\s*(das|dass|der|die|den|dem|mit\s+dem|mit\s+der|"
                r"mit\s+denen|für\s+das|für\s+den|für\s+die|wo|womit|"
                r"woraus|in\s+dem|in\s+der|in\s+denen|um\s+zu|sodass|"
                r"so\s+dass|damit|weil|denn)\b.*$",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )

            # NEW: cut off "für meine|seine|deine|ihre …" purpose clauses
            # ("für meine nächste Sitzung", "für seine Hausaufgaben"). These
            # describe USE not topic; they confuse the LLM downstream.
            _fallback = _re_topic.sub(
                r"\s+für\s+(meine|seine|deine|ihre|unsere|eure|"
                r"meinen|seinen|deinen|ihren|unseren|euren)\s+\w+.*$",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )

            # NEW: strip TRAILING create-verbs ("…erstellen", "…generieren",
            # "…bauen") — they're often at the end of the user sentence,
            # e.g. "Kannst du mir ein Arbeitsblatt für Mathe erstellen?"
            # → after subordinate-cut: "Arbeitsblatt für Mathe erstellen"
            # → after trailing-verb-cut: "Arbeitsblatt für Mathe".
            _fallback = _re_topic.sub(
                r"\s+(erstellen|machen|bauen|generieren|schreiben|entwerfen|"
                r"produzieren|verfassen|zusammenstellen|herunterladen|"
                r"runterladen|zur\s+Verfügung\s+stellen|bereitstellen)"
                r"(\s+kannst|\s+könntest|\s+würdest|\s+wirst|\s+könnten\s+Sie|"
                r"\s+würden\s+Sie|\s+möchtest|\s+möchten\s+Sie)?\??\s*$",
                "", _fallback, flags=_re_topic.IGNORECASE,
            )

            _fallback = _re_topic.sub(r"\s+", " ", _fallback).strip(" .,:;-?")
            # Cap at 80 chars to avoid weirdly long topics
            _c_topic = _fallback[:80]

            # ── Plausibilitätscheck gegen garbage-Topics ──────────────
            # Der regex-Fallback oben kann Müll liefern, wenn die Nachricht
            # kein echter Create-Befehl mit Thema war, sondern z.B. eine Frage
            # zum Download, Feedback oder vage Äußerung. Beispiele aus dem Eval:
            #   "Kannst du mir das Arbeitsblatt runterladen?" → "das runterladen?"
            #   "Ich brauche Ideen für ein neues Arbeitsblatt" → "Ideen für ein neues"
            #   "Gibt's ne Übersicht zu Statistiken?" → "ne zu Statistiken"
            # In allen diesen Fällen: lieber Topic LEER lassen, damit das
            # System sauber degradiert und nach dem konkreten Thema fragt.
            if _c_topic:
                _tl = _c_topic.lower().strip(" .,:;?!")
                _bad = False
                # Zu kurz (weniger als ein echtes Wort)
                if len(_tl) < 3:
                    _bad = True
                # Beginnt mit Pronomen/Artikel/Possessiv (meist Satzreste ohne Sachsubstantiv)
                elif _re_topic.match(
                    r"^(das|dieses|diese|dieser|der|die|den|dem|des|ein|eine|einen|einem|einer|eines|"
                    r"ihm|ihr|ihre|ihres|ihrem|ihren|ihn|ihnen|"
                    r"mein|meine|meines|meinem|meinen|deiner?|deines|deinem|deinen|"
                    r"unser|unsere|unseres|unserem|unseren|euer|eure|"
                    r"mir|mich|dir|dich|uns|euch|es|sie|er)\b",
                    _tl,
                ):
                    _bad = True
                # Beginnt mit Frage-/Meta-Wort (das ist KEINE Create-Intention)
                elif _re_topic.match(
                    r"^(wie|was|wo|wann|warum|wer|wieso|wieviel|wie viel|"
                    r"kannst|kann|könnte|könntest|hast|habt|gibt|gibts|"
                    r"ideen|vorschläge|tipps|möglichkeiten|eine frage|frage|"
                    r"ne frage|irgendwas|irgendwie|neues|neu|alles|etwas|"
                    r"paar|einige|wenige|viele|ein paar|"
                    r"bitte|mal|gerne|gern|also|so|mal eben|kurz mal|"
                    r"hey|hi|hallo|servus|oh|na|hm|äh|eh)\b",
                    _tl,
                ):
                    _bad = True
                # Enthält Konversations-Filler ("das wäre super", "echt cool")
                # → der Fallback hat zu viel Satz erfasst, lieber leer lassen
                elif _re_topic.search(
                    r"\b(das\s+wäre|wäre\s+(echt|super|toll|cool|nett)|"
                    r"echt\s+(super|toll|cool)|"
                    r"das\s+wäre\s+echt\s+super|"
                    r"vielen\s+dank|danke|"
                    r"hilf(e|t)?\s+mir|kannst\s+du\s+mir)\b",
                    _tl,
                ):
                    _bad = True
                # Zu wenig substantielle Inhalt (reine Satz-Fragmente wie
                # "e der aktuellen", "zu Ihrem letzten", "paar Fragen zu")
                elif len(_tl) < 12 or (
                    # Erste 1-2 Zeichen sind kleinbuchstabiger Rest-Fragment,
                    # typisch nach Material-Typ-Strip: "e der aktuellen..."
                    _tl[:2].strip() in ("e", "er", "es", "en", "em", "n", "s")
                    and _tl[2:3] == " "
                ):
                    _bad = True
                # Endet auf Fragezeichen (Frage, keine Create-Directive)
                elif _c_topic.rstrip().endswith("?"):
                    _bad = True
                # Enthält Verben, die KEINE Erstellung bedeuten — User will
                # existierende Dinge aufrufen/manipulieren, kein neues Material
                elif _re_topic.search(
                    r"\b(runterladen|herunterladen|bewerten|bewertung|prüfen|"
                    r"ansehen|anschauen|kopieren|teilen|löschen|exportieren|"
                    r"ausdrucken|drucken|speichern|öffnen|schließen|abbrechen|"
                    r"bereitstellen|bereitstellung|schicken|senden|zusenden|"
                    r"weiterleiten|feedback|meinung|bewerte|review)\b",
                    _tl,
                ):
                    _bad = True
                # Enthält Meta-/Referenz-Tokens ("der letzten", "meiner klasse",
                # "meinem sohn") — deutet auf Abfrage-Intent, nicht Erstellung
                elif _re_topic.search(
                    r"\b(der letzt|die letzt|das letzt|meiner?\s+(klasse|tochter|"
                    r"sohn|kinder|schüler))\b",
                    _tl,
                ):
                    _bad = True
                if _bad:
                    logger.info(
                        "canvas-create topic fallback rejected as garbage: %r (msg: %r)",
                        _c_topic, (req.message or "")[:100],
                    )
                    _c_topic = ""
                else:
                    logger.info("canvas-create topic fallback: %r", _c_topic)

        # Welle E v4+5 (2026-05-26, eval-185e): Phantom-Topic-Filter.
        # Wenn der Classifier "einem Thema" / "ein Thema" / "irgendwas"
        # als Topic-String extrahiert hat, ist das KEIN konkretes Thema
        # — der User hat im Text z.B. „Quiz zu einem Thema" geschrieben.
        # Wir behandeln das wie leeren Topic und routen auf M03-Slot-
        # Klärung, statt das LLM mit Phantom-Topic Material generieren
        # zu lassen.
        if _c_topic:
            _topic_low = _c_topic.lower().strip()
            _phantom_patterns = (
                "einem thema", "ein thema", "irgendeinem thema",
                "irgendwas", "irgendetwas", "etwas", "irgendein thema",
                "einem beliebigen thema", "beliebigem thema",
            )
            _is_phantom = (
                _topic_low in _phantom_patterns
                or any(_topic_low.startswith(p + " ") for p in _phantom_patterns)
                or any(_topic_low.endswith(" " + p) for p in _phantom_patterns)
                or _topic_low.endswith(" erstellen")
                or _topic_low.endswith(" generieren")
                or _topic_low.endswith(" machen")
            )
            if _is_phantom:
                logger.info(
                    "canvas-create phantom topic detected, force slot-clarification: %r",
                    _c_topic,
                )
                _c_topic = ""

        # ── Robust-Fallback (eval-1eda, GS-4.3): Topic vorhanden, aber der
        # genannte Artefakt-Typ ist (noch) kein bekannter Alias (z.B.
        # "Argumentationshilfe"). Statt in M03 ("Welcher Typ?") zu fallen,
        # generieren wir mit 'auto' und reichen den genannten Begriff durch —
        # das LLM wählt das beste ECHTE Format aus dem Material-Vokabular.
        # Greift NUR bei klar benanntem Artefakt; "mach mir was/ein Material"
        # liefert named_artifact_label() == "" → bleibt M03 (nichts verschlechtert).
        _requested_label = ""
        if _c_topic and not _mt_key:
            _named = named_artifact_label(
                req.message,
                (classification.entities or {}).get("material_typ", ""),
            )
            if _named:
                _mt_key = "auto"
                _requested_label = _named
                logger.info(
                    "M10 robust-fallback: ungelistetes Artefakt %r -> auto (topic=%r)",
                    _named, _c_topic[:60],
                )

        if _c_topic and _mt_key:
            _mts_flow = get_material_types()
            _label = _requested_label or _mts_flow[_mt_key]["label"]
            _emoji = _mts_flow[_mt_key]["emoji"]
            try:
                # Welle E v4++ (2026-05-26): formality aus pattern_output
                # explizit durchreichen — sonst duzt der Material-Generator
                # bei P-ENT/P-RED-Anfragen trotz siezen-Modifier.
                _formality_for_material = pattern_output.get("formality", "") or ""
                _title, _md = await generate_canvas_content(
                    topic=_c_topic,
                    material_type_key=_mt_key,
                    session_state=session_state,
                    memory_context=memory_context,
                    formality=_formality_for_material,
                    requested_label=_requested_label,
                )
                # Welle E v4+5 (2026-05-26, eval-185e): Lösungen-Pflicht
                # bei aufgabenbasiertem Material. Bei Arbeitsblatt/Quiz/
                # Übung MUSS ein `## Lösungen`-Block existieren — sonst
                # ist das Material für Lehrkräfte/Eltern wertlos. Wenn
                # das LLM den Block vergessen hat, hängen wir einen Stub
                # an + loggen für Pattern-Monitoring.
                _needs_loesungen = _mt_key in (
                    "arbeitsblatt", "quiz", "uebung", "übung", "test"
                )
                if _needs_loesungen and _md:
                    import re as _re_loes
                    # Welle E v4+11 (2026-05-26, eval-f6f56-Befund): Validator
                    # akzeptiert jetzt mehrere Lösungs-Formate:
                    #   1. ## Lösungen / Loesungen / Musterlösung (Heading)
                    #   2. **Lösungen:** als Bold-Header
                    #   3. „Lösung 1:" / „Lösung zu Aufgabe 1:" als nummerierte Zeilen
                    #   4. ## Antworten / ## Auflösung
                    _has_loes = bool(_re_loes.search(
                        r"(?im)^#{1,3}\s*(lösungen|loesungen|musterlösung|musterloesung|"
                        r"lösungsteil|antworten|auflösung|aufloesung)\b",
                        _md,
                    )) or bool(_re_loes.search(
                        r"(?im)^\*\*(lösungen?|loesungen?|antworten):?\*\*",
                        _md,
                    )) or bool(_re_loes.search(
                        # "Lösung X:" oder "Lösung zu Aufgabe X:" als nummerierte
                        # Block-Zeile am Zeilenanfang. .{0,30} fängt Varianten wie
                        # "Lösung zu Aufgabe 1", "Lösung Teil A", "Lösung Nr. 3" ab.
                        r"(?im)^\s*(lösung|loesung)(\s+.{0,30})?\s*[:.]",
                        _md,
                    ))
                    if not _has_loes:
                        logger.warning(
                            "M10 material_type=%s ohne ## Lösungen-Block — "
                            "Stub angehängt (topic=%r). LLM-Pattern-Body-Compliance fail.",
                            _mt_key, _c_topic[:80],
                        )
                        _md = (_md or "").rstrip() + (
                            "\n\n## Lösungen\n\n"
                            "_Lösungen werden ergänzt — du kannst mir "
                            "antworten mit \"Lösungen ergänzen\", "
                            "dann fülle ich den Block aus._\n"
                        )
                # Welle E (2026-05-23) — Material-Markdown ans response_text
                # konkatenieren statt nur ins canvas_open payload. Sonst greift
                # das InlineDocument-Routing am Hauptpfad-Ende nicht (es prüft
                # response_text-Länge >= 200 chars), und das Material würde
                # weder als Inline-Box noch als Canvas-Pane (entfernt) im UI
                # erscheinen → leere Bot-Antwort, wie der User berichtet hat.
                _canvas_completion_intro = _canvas_completion_message(
                    _label, _c_topic, _md, canvas_enabled=False,
                    formality=_formality_for_material,
                )
                response_text = (
                    (_canvas_completion_intro or "").rstrip()
                    + "\n\n" + (_md or "").lstrip()
                ).strip()
                tools_called = ["canvas_service.generate_canvas_content"]
                wlo_cards_raw = []
                _canvas_routed = True
                # PageAction nicht mehr setzen — Material lebt jetzt in
                # response_text und wird vom InlineDocument-Routing am
                # Hauptpfad-Ende in die ``inline_documents``-Box verpackt.
                _canvas_payload_out = None
                new_state = "S3"
                session_state["entities"]["_canvas_material_type"] = _mt_key
                session_state["entities"]["_canvas_topic"] = _c_topic
                # Store fresh markdown so subsequent edit-verb turns
                # ("mach es einfacher") operate on THIS canvas, not on an
                # older one that may still be in session memory.
                session_state["entities"]["_canvas_last_markdown"] = _md
                # Also refresh thema so next turn's classifier sees the
                # current topic, not a stale prior one.
                session_state["entities"]["thema"] = _c_topic
            except Exception as _e:
                # Same hardening as in _handle_canvas_create — graceful chat
                # bubble instead of bubbling a 500. The frontend would otherwise
                # show its generic "konnte ich leider nicht erstellen" message.
                logger.error("M10 canvas generation failed: %s", _e)
                response_text = (
                    f"Ich konnte das **{_label}** zum Thema *{_c_topic}* gerade "
                    f"nicht erstellen ({type(_e).__name__}). Versuch es nochmal — "
                    "meistens klappt es beim zweiten Anlauf."
                )
                tools_called = ["canvas_service.generate_canvas_content", "error"]
                wlo_cards_raw = []
                _canvas_routed = True
                _canvas_payload_out = None
                new_state = session_state.get("state_id") or "S3"
        elif _c_topic and not _mt_key:
            response_text = (
                f"Welches Material soll ich dir zum Thema **{_c_topic}** erstellen? "
                "Waehle einen Typ aus den Vorschlaegen oder schreib \"Automatisch\", "
                "damit ich den passenden Typ selbst waehle."
            )
            tools_called = []
            wlo_cards_raw = []
            _canvas_routed = True
            _canvas_forced_quick_replies = material_type_quick_replies_for_persona(
                session_state.get("persona_id") or ""
            )
        elif not _c_topic:
            response_text = (
                "Gerne erstelle ich dir ein Material. Zu welchem **Thema**? "
                "Beispiel: \"Erstelle ein Arbeitsblatt zur Photosynthese für Klasse 6\"."
            )
            tools_called = []
            wlo_cards_raw = []
            _canvas_routed = True
    return CanvasFastPathResult(
        routed=_canvas_routed,
        payload_out=_canvas_payload_out,
        forced_quick_replies=_canvas_forced_quick_replies,
        response_text=response_text,
        tools_called=tools_called,
        wlo_cards_raw=wlo_cards_raw,
        new_state=new_state,
    )
