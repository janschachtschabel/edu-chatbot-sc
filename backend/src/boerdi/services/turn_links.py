"""Turn phases P27-P28 (verbatim port of ALT ``chat_turn_links._finalize_links_and_metas``).

Sibling of ``services/turn_assembly`` (P20-P24): the ALT ``chat_turn_*`` turn-phase
orchestrators land in ``services/turn_*``. This one runs the post-answer rewriters
(off-topic card filter, type-focus card-strip + honest Such-CTA text-replace, and the
anti-hallucination watchdog — the last two only for M05/M06 and not when the pattern
degraded), extracts ``web_links`` from the answer text, and assembles the MCP query
metas (``get_query_metas`` -> ``QueryMetaEntry`` list, a synthetic fallback meta for the
search-CTA, and the type-focus search-URL override via the MCP vocab lookup).

**NEU-Portierung:** the fn is AST byte-identical to ALT modulo the in-function import
paths — ``QueryMetaEntry`` from ``boerdi.api.schemas`` and the three vocab helpers
(``_label_to_uri_cache``/``_ensure_label_cache``/``_fuzzy_lookup``) from
``boerdi.services.mcp.arg_resolvers`` (ALT bundled them under ``app.services.mcp_client``;
NEU split the MCP client, so ``get_query_metas`` stays in ``mcp.client`` while the vocab
helpers live in ``mcp.arg_resolvers``). Boundaries (``get_query_metas``/``get_repo_base_url``/
``_extract_web_links_from_text``/``_resolve_wanted_content_types``) are module-level so tests
patch them here; the vocab helpers stay lazy in-function so tests patch them at the source.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.api.schemas import ChatRequest
from boerdi.domain.content_types import _resolve_wanted_content_types
from boerdi.domain.url_helpers import _extract_web_links_from_text
from boerdi.services.config_loader import get_repo_base_url
from boerdi.services.mcp.client import get_query_metas

logger = logging.getLogger(__name__)


async def _finalize_links_and_metas(
    req: ChatRequest,
    session_state: dict,
    classification_dict: dict,
    winner: Any,
    pattern_output: dict,
    tracer: Any,
    tools_called: list,
    _effective_pattern_id: str,
    cards: list,
    response_text: str,
) -> tuple:
    """Phasen P27–P28 von ``_chat_impl``: Grouping-/Legacy-Inline-Flags,
    Off-Topic-Card-Filter, Type-Focus-Card-Strip + Text-Replace und
    Anti-Halluzination-Watchdog (beide nur bei winner M05/M06 und nicht
    bei Degradation), _extract_web_links_from_text (+ Type-Focus-
    web_links-Clear), Query-Metas (get_query_metas → QueryMetaEntry-
    Liste, synthetische Fallback-Meta für die Search-CTA, Type-Focus-
    Search-URL-Override mit Vocab-Lookup) und tracer.record(query_meta).

    Parameter-Reihenfolge: req, session_state, classification_dict,
    winner, pattern_output, tracer, tools_called, _effective_pattern_id,
    cards, response_text.

    Die ``"winner" in dir()``-/``"pattern_output" in dir()``-Wächter im
    Body bleiben wahr (beide Namen sind hier Parameter, wie sie an der
    Ursprungsstelle stets gebunden waren). Mutiert nichts in-place, was
    draußen weiterlebt; ``cards``/``response_text`` werden rebound →
    Rückgabe.

    Returns (7-Tupel): (cards, response_text, _final_text, _web_links,
    _raw_metas, _query_meta_entries, _type_focus_label).
    ``_grouping_on_impl``/``_winner_id`` u.a. bleiben intern (kein
    Leser danach bzw. Phase 6 rebindet ``_winner_id`` vor jedem Load —
    AST-geprüft).
    """
    # Save bot message (cleaned text + web_links werden weiter unten beim
    # Response-Build genauso wieder verwendet — siehe ``_final_text`` /
    # ``_web_links``). Hier zuerst rechnen, einmal save, einmal return.
    #
    # Die Extraktion strippt Inline-Markdown-Links aus dem Text und stellt
    # sie strukturiert in ``web_links`` bereit. Sie läuft seit Welle C.5
    # (Default-Flip 2026-05-21) per Default — wird nur im LEGACY-Inline-
    # Mode übersprungen:
    #   - ``inline-result-grouping=false`` (explizit) → altes Layout, Inline-
    #     Links bleiben als Lotsen-Bullets im Text.
    #   - ``cards-enabled=false`` + ``inline-result-grouping=false`` → Legacy:
    #     Cards werden vom Postprocess als Markdown-Bullets im Text angehängt,
    #     die müssen sichtbar bleiben — also Re-Extraktion AUS.
    #   - ``cards-enabled=false`` + ``inline-result-grouping=true/None`` →
    #     Welle-C.5-Refactor: keine Inline-Card-Bullets im Text, Frontend
    #     rendert Cards in Boxen. Re-Extraktion AN (für LLM-flowing-text-
    #     Links → Webseiten-Inhalte-Box).
    _ig_flag_impl = getattr(req.environment, "inline_result_grouping", None)
    _ce_flag_impl = getattr(req.environment, "cards_enabled", None)
    _legacy_inline_impl = (_ce_flag_impl is False) and (_ig_flag_impl is False)
    _grouping_on_impl = (_ig_flag_impl is not False) and (not _legacy_inline_impl)

    # ── Off-Topic-Card-Filter (Welle C.5+, 2026-05-22) ─────────────────
    # Im inline_grouping_mode landen Cards 1:1 in Themenseiten-/Sammlungs-
    # Boxen. Wenn der MCP-Pool fachfremde Treffer enthält (beobachtet:
    # "Chemie" / "Chemie und Umwelt 123" bei query=Klimawandel), bekommt
    # der User irreführende Boxen. Wir matchen Titel-Tokens gegen den
    # User-Suchbegriff + Klassifikator-Entities (thema/fach) und droppen
    # Cards ohne Token-Overlap aus ``cards`` (in-place).
    # Cards ohne thema/fach/Nachricht-Signal werden NICHT gefiltert
    # (zu wenig Kontext für Relevanz-Urteil).
    if _grouping_on_impl and cards:
        try:
            import re as _re_tf
            _classif_entities = classification_dict.get("entities", {}) or {}
            _topic_signal = " ".join([
                str(_classif_entities.get("thema") or ""),
                str(_classif_entities.get("topic") or ""),
                str(_classif_entities.get("fach") or ""),
                str(req.message or ""),
            ]).lower()
            # Tokens >= 4 Zeichen → grobe Stopword-Filterung ohne Liste
            # ("der", "die", "das", "ich", "zum", … fallen weg). Begriffe
            # werden geteilt an Whitespace + Bindestrich (Klima-wandel →
            # Klima, wandel).
            _topic_tokens = {
                t.strip("„""'\".,;:!?()[]{}/")
                for t in _re_tf.split(r"[\s\-/]+", _topic_signal)
                if len(t) >= 4
            }
            _topic_tokens.discard("")
            if _topic_tokens:
                # Per-Card-Match: irgendein Token im Titel/Beschreibung/
                # Keywords? Auch Substring (klimawandel matcht "klima").
                def _card_matches(_c) -> bool:
                    # Welle E v4+12 (2026-05-27): Themenseiten-Cards
                    # IMMER durchlassen. Sie kommen aus
                    # ``search_wlo_topic_pages`` (server-seitig nach
                    # Topic kuratiert) — der Title ist oft semantisch
                    # passend („Nachhaltigkeit" für „Klimawandel"-
                    # Suche), aber Token-Overlap im Titel gibt's nicht.
                    # Ohne diesen Bypass würde der Off-Topic-Filter die
                    # echten Themenseiten-Treffer wegwerfen und nur die
                    # Title-matched Sammlungen-Cards übrig lassen.
                    _tp = getattr(_c, "topic_pages", None)
                    if _tp and isinstance(_tp, list) and len(_tp) > 0:
                        return True
                    _t = (str(getattr(_c, "title", "") or "") + " "
                          + str(getattr(_c, "description", "") or "") + " "
                          + " ".join(getattr(_c, "keywords", None) or [])
                          ).lower()
                    if not _t.strip():
                        # Card ohne Text → defensiv durchlassen
                        return True
                    for tok in _topic_tokens:
                        # Token oder kürzeres Präfix (>= 4 Zeichen) im
                        # Card-Text? Substring statt regex \b um auch
                        # zusammengesetzte deutsche Wörter abzudecken
                        # (Klimawandel ≈ Klimaschutz, Klimaforschung).
                        if tok in _t:
                            return True
                        # Präfix-Match: tok="klimawandel" → "klima" in _t?
                        if len(tok) >= 7 and tok[:5] in _t:
                            return True
                    return False
                _before_cards = list(cards)
                cards = [c for c in cards if _card_matches(c)]
                if len(cards) < len(_before_cards):
                    _kept_ids = {getattr(c, "node_id", None) for c in cards}
                    _dropped_titles = [
                        str(getattr(c, "title", "?"))[:40]
                        for c in _before_cards
                        if getattr(c, "node_id", None) not in _kept_ids
                    ]
                    logger.info(
                        "off-topic-filter: %d → %d cards (signal-tokens=%s, dropped=%s)",
                        len(_before_cards), len(cards),
                        sorted(_topic_tokens)[:6],
                        _dropped_titles[:5],
                    )
        except Exception as _otf_err:
            logger.warning("off-topic filter crashed: %s", _otf_err)

    # ── Type-Focus Card-Strip + Text-Replace (Welle C.5+, 2026-05-22) ──
    # User-Anforderung: Wenn der User explizit nach Material-Typ fragt
    # ("nur videos bitte", "hast du Arbeitsblätter?", "Übungen zu X"),
    # ist die korrekte UI für inline_grouping_mode KOMPLETT minimal:
    # nur Such-CTA mit dem Typ-gefilterten Suchlink, Bot-Text als
    # 1-Satz-Verweis darauf.
    #
    # WICHTIG (Bug-Fix Eval-b2cd 2026-05-23): Dieser Rewriter darf nur bei
    # echten **Material-Such-Patterns** (M05 gefiltert / M06 Cascade) greifen.
    # Sonst überschreibt er andere Patterns mit „Für Videos zum Thema schau in
    # die Suche unten".
    # Bug-Fix 2026-06-01: M07 (Fachportal-Übersicht) + M08 (Sammlung-Drilldown)
    # RAUS — das sind Navigations-Pattern mit eigenem Card-Output. Bei „welche
    # Fachportale gibt es" hat der Rewriter sonst die Portal-Liste durch eine
    # „Für Arbeitsblätter zu Photosynthese …"-Meldung (stales Session-Thema)
    # ersetzt → völlig sinnfreie Antwort.
    _winner_id = getattr(winner, "id", "") if "winner" in dir() else ""
    _is_search_pattern_active = _winner_id in {"M05", "M06"}
    # Degradation (Pflicht-Slot fehlt): Die Antwort IST die Rueckfrage —
    # es wurde nicht gesucht, es gibt keine "gefilterten Treffer unten".
    # Beide Rewriter (Type-Focus + Anti-Hallu) muessen aussetzen, sonst
    # ersetzen sie die Rueckfrage durch eine faktisch falsche Such-CTA.
    _po_for_rewriters = pattern_output if "pattern_output" in dir() else {}
    _rewriters_degraded = bool(
        _po_for_rewriters.get("degradation")
        and _po_for_rewriters.get("missing_slots")
    )
    _type_focus_label = ""
    if _grouping_on_impl and _is_search_pattern_active and not _rewriters_degraded:
        try:
            _classif_e = classification_dict.get("entities", {}) or {}
            _session_e = session_state.get("entities", {}) or {}
            _wanted = _resolve_wanted_content_types(
                req.message or "",
                session_entities=_session_e,
                classification_entities=_classif_e,
            )
            if _wanted:
                # Display-Label aus dem ersten canonical Type
                # ("video" → "Videos", "arbeitsblatt" → "Arbeitsblätter").
                _label_map = {
                    "video": "Videos",
                    "arbeitsblatt": "Arbeitsblätter",
                    "übung": "Übungen",
                    "uebung": "Übungen",
                    "quiz": "Quizze",
                    "audio": "Audios",
                    "präsentation": "Präsentationen",
                    "praesentation": "Präsentationen",
                    "test": "Tests",
                    "podcast": "Podcasts",
                    "bild": "Bilder",
                    "lied": "Lieder",
                    "aufgabe": "Aufgaben",
                    "simulation": "Simulationen",
                }
                _first_wanted = sorted(_wanted)[0]
                _type_focus_label = _label_map.get(_first_wanted, _first_wanted.capitalize())

                # A) Cards: Sammlungen/Themenseiten KOMPLETT raus —
                #    der User will sie nicht sehen, sie verwirren ihn nur.
                #    Einzelinhalte bleiben (für Such-CTA-Count + Lernpfad).
                _before_n = len(cards) if cards else 0
                cards = [
                    c for c in (cards or [])
                    if getattr(c, "node_type", None) != "collection"
                    and not getattr(c, "topic_pages", None)
                ]
                if len(cards) < _before_n:
                    logger.info(
                        "type-focus card-strip: %d → %d (gefiltert: Sammlungen/Themenseiten "
                        "raus, Typ-Fokus=%s)",
                        _before_n, len(cards), sorted(_wanted),
                    )

                # B) Bot-Text: KOMPLETT durch Such-CTA-Verweis ersetzen.
                #    Egal was die LLM ausspuckt — bei Type-Focus ist die
                #    ehrliche Antwort immer "Für [Typ] schau in die Suche
                #    unten". Sonst rutschen Variationen wie "Hier sind
                #    passende Videos…" durch, die so tun als wären die
                #    Videos sichtbar (sind sie nicht — sie sind hinter
                #    der Such-CTA). Verlust eines höflichen "Klar — …"-
                #    Intros nehmen wir bewusst in Kauf; die Antwort wird
                #    dadurch maximal eindeutig.
                if response_text:
                    _topic_for_text = (
                        (_classif_e.get("thema")
                         or _classif_e.get("topic")
                         or _session_e.get("thema")
                         or "").strip()
                    )
                    _topic_suffix = (
                        f" zu „{_topic_for_text}"" "
                        if _topic_for_text else " zum Thema "
                    )
                    _new_response = (
                        f"Für {_type_focus_label}{_topic_suffix}schau "
                        "in die Suche unten — dort findest du die "
                        "gefilterten Treffer."
                    )
                    if _new_response.strip() != response_text.strip():
                        logger.warning(
                            "type-focus text-replace (label=%s): "
                            "original=%r | replaced=%r",
                            _type_focus_label,
                            response_text[:200],
                            _new_response[:200],
                        )
                        response_text = _new_response
        except Exception as _tf_err:
            logger.warning("type-focus rewriter crashed: %s", _tf_err)

    # ── Anti-Hallucination-Wächter (Welle C.5+, 2026-05-21) ────────────
    # Nur im inline_grouping_mode. Der LLM bekommt zwar UI-BOX-STATUS-
    # Footer + verschärfte Prompt-Regeln, halluziniert aber gelegentlich
    # Sammlungen/Themenseiten, die gar nicht im UI sichtbar sind
    # ("Hier sind zwei Sammlungen…" obwohl die Boxen leer sind).
    # Verifikation gegen die *tatsächlich* in ``cards`` vorhandenen
    # Knoten + leichtes Auto-Rewrite, falls die Behauptung falsch ist.
    # Strippt nicht heuristisch ganze Sätze (zu fragil), sondern
    # ersetzt nur die Behauptungswörter durch eine ehrliche Variante,
    # die auf die Such-CTA verweist.
    #
    # Zusätzlich seit 2026-05-22: Material-Typ-Anfrage-Erkennung. Wenn der
    # User explizit nach Video/Arbeitsblatt/Übung/… fragt, ist der korrekte
    # Antwort-Modus IMMER ein Such-CTA-Verweis ("Für [Typ] schau in die
    # Suche unten") — egal ob Sammlungen/Themenseiten zufällig auch im
    # Pool sind. Sonst Bait-and-Switch ("User wollte Videos, Bot zeigte
    # Sammlung"). Diese Mode-Erkennung wirkt VOR den Box-Hallucination-
    # Patches: ist sie aktiv und der Text erwähnt Sammlung/Themenseite,
    # rewriten wir den führenden Satz auf einen Type-Verweis.
    # Anti-Hallu-Block läuft NUR bei Such-Patterns. Sonst überschreibt er
    # die ehrlich erzeugten Outputs anderer Patterns (M13 Submit-Link,
    # M14 Feedback-Echo, M15 Orientierung etc.) mit „Für [Typ] zum Thema
    # schau in die Suche unten" — würde Bug-Fix-Ziel zerschießen.
    if (_grouping_on_impl and response_text and cards is not None
            and _is_search_pattern_active and not _rewriters_degraded):
        try:
            _n_themen = sum(
                1 for c in cards
                if (getattr(c, "node_type", None) == "collection"
                    and bool(getattr(c, "topic_pages", None)))
            )
            _n_samml = sum(
                1 for c in cards
                if (getattr(c, "node_type", None) == "collection"
                    and not getattr(c, "topic_pages", None))
            )

            # Offer-Mode-Skip: Wenn in diesem Turn KEIN Such-Tool gelaufen
            # ist (z.B. M15-Orientierungs-Antwort: „Ich kann nach
            # passenden Themenseiten/Sammlungen suchen — nenn mir dein
            # Thema"), ist die Erwähnung dieser Worte KEINE Halluzination
            # über aktuelle Treffer, sondern ein **Angebot für Folge-Turns**.
            # Watchdog-Patches treffen dann unschuldige Sätze — beobachtet
            # 2026-05-22: „passenden Themenseiten oder Sammlungen" →
            # „passende Treffer in der Suche oder passende Treffer in der
            # Suche". Wir skippen die Sammlung/Themenseite-Patches in
            # diesem Fall komplett.
            _offered_only_no_search = not any(
                t in (tools_called or [])
                for t in ("search_wlo_content",
                          "search_wlo_collections",
                          "search_wlo_topic_pages",
                          "browse_collection_tree",
                          "get_subject_portals",
                          "get_collection_contents")
            )
            import re as _re_wd
            _new_text = response_text
            _changed_reasons = []

            # ── Material-Typ-Detection aus User-Message + Entities ──
            # Signale (in Prioritätsreihenfolge):
            #   1. classification.entities.medientyp gesetzt (klassifikator-
            #      erkannt — höchste Sicherheit, z.B. "Video", "Arbeitsblatt")
            #   2. Regex auf req.message: explizite Material-Typ-Wörter
            #      kombiniert mit "zeig mir / ich brauche / hast du / gibt es"
            _classif_e = classification_dict.get("entities", {}) or {}
            _medientyp_classif = (_classif_e.get("medientyp") or "").strip()
            _type_words_re = _re_wd.compile(
                # Singular + Plural + Umlaut/AE-Varianten.
                # ``arbeitsbl[äa]tt(?:er|aer)?`` deckt
                # arbeitsblatt / arbeitsblätter / arbeitsblaetter.
                r"\b(videos?|"
                r"arbeitsbl(?:a|ä|ae)tt(?:er|aer)?|"
                r"(?:ü|ue)bung(?:en)?|"
                r"quiz(?:ze)?|audios?|"
                r"pr(?:ä|ae)sentation(?:en)?|"
                r"interaktive[srn]?\s+(?:(?:ü|ue)bung|aufgabe)|"
                r"aufgaben?|tests?|lieder|podcasts?|"
                r"bilder|grafiken?|simulation(?:en)?|"
                r"erkl(?:ä|ae)rvideos?)\b",
                _re_wd.IGNORECASE,
            )
            _user_msg_match = _type_words_re.search(req.message or "")
            _is_type_focus = bool(_medientyp_classif) or bool(_user_msg_match)
            _type_label = (
                _medientyp_classif
                or (_user_msg_match.group(0).capitalize() if _user_msg_match
                    else "Materialien")
            )

            # Schärfung A: Material-Typ-Anfrage → führender Satz wird auf
            # Such-CTA-Verweis getauscht, wenn Bot stattdessen Sammlung/
            # Themenseite anpreist. Wir machen das auch dann, wenn
            # _n_samml > 0 oder _n_themen > 0 — der User wollte ja
            # explizit den Material-Typ, nicht die Sammlungs-Übersicht.
            if _is_type_focus and _re_wd.search(
                r"\b(?:Sammlung(?:en)?|Themenseite(?:n)?)\b",
                _new_text, _re_wd.IGNORECASE,
            ):
                # Ersten Satz, der Sammlung/Themenseite enthält, ersetzen
                # durch einen Type-Verweis. Folgesätze bleiben — der Bot
                # darf weiter freundlich anbieten zu verfeinern.
                _first_sentence_with_claim = _re_wd.compile(
                    r"(?is)^[^.!?]*?\b(?:Sammlung(?:en)?|Themenseite(?:n)?)"
                    r"\b[^.!?]*?[.!?]\s*",
                )
                _replacement = (
                    f"Für {_type_label} zum Thema klick auf die Suche "
                    "unten — dort findest du die gefilterten Treffer. "
                )
                _patched = _first_sentence_with_claim.sub(
                    _replacement, _new_text, count=1,
                )
                if _patched != _new_text:
                    _new_text = _patched
                    _changed_reasons.append(
                        f"type-focus={_type_label!r} aber Text claimt Sammlung/Themenseite"
                    )

            # Capitalization-Helper: wenn das Match am Satzanfang steht
            # (Vorgänger ist Satzende-Punktuation + Whitespace ODER String-
            # Start), Replacement mit Großbuchstaben starten. Sonst klein —
            # passt mitten im Satz nahtlos. Vermeidet das beobachtete
            # "...nicht gefunden. passende Treffer..."-Problem (lowercase
            # nach Punkt), User-Feedback 2026-05-22.
            def _ctx_aware_sub(_pattern: "_re_wd.Pattern", _text: str,  # noqa: UP037
                                _base_repl: str, _count: int = 3) -> str:
                def _replace(m):
                    pos = m.start()
                    # Backtrack: letzter nicht-Whitespace vor dem Match
                    before = _text[:pos]
                    j = len(before) - 1
                    while j >= 0 and before[j].isspace():
                        j -= 1
                    is_sentence_start = (j < 0) or before[j] in ".!?\""
                    if is_sentence_start:
                        return _base_repl[:1].upper() + _base_repl[1:]
                    return _base_repl
                return _pattern.sub(_replace, _text, count=_count)

            # Determiner-/Adjektiv-Präfix mit allen DE-Deklinationen.
            # Greift „zwei passende Sammlungen", „die passenden Sammlungen",
            # „eine passende Sammlung", „diesen passenden Sammlungen" usw.
            # Vorher (Bug 2026-05-22): „passende" matched, „passenden"
            # nicht → Ergebnis „passenden passende Treffer in der Suche".
            # Jetzt: alle Adjektiv-Endungen + Artikel-Deklinationen.
            _det_adj = (
                r"(?:\b(?:"
                r"zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|"
                r"ein(?:e[srnm]?)?|"
                r"d(?:er|ie|as|em|en|es)|"
                r"diese[srnm]?|"
                r"meine[srnm]?|deine[srnm]?|seine[srnm]?|"
                r"unsere[srnm]?|eure[srnm]?|ihre[srnm]?|"
                r"passende[srnm]?|"
                r"einige|mehrere|alle[srnm]?|viele|wenige|"
                r"weitere|andere[srnm]?|"
                r"ähnliche[srnm]?|verwandte[srnm]?"
                r")\s+)?"
            )

            # Bot behauptet Sammlung(en), aber keine sichtbar — patchen.
            # Skip wenn kein Such-Tool gelaufen ist (Offer-Mode).
            if (not _offered_only_no_search and _n_samml == 0
                and _re_wd.search(
                    r"\bSammlung(?:en)?\b", _new_text, _re_wd.IGNORECASE,
                )):
                _phrase_re = _re_wd.compile(
                    _det_adj + r"\bSammlung(?:en)?\b",
                    _re_wd.IGNORECASE,
                )
                _new_text = _ctx_aware_sub(
                    _phrase_re, _new_text,
                    "passende Treffer in der Suche", _count=3,
                )
                _changed_reasons.append(f"sammlungen=0 aber Text claimt")  # noqa: F541

            # Bot behauptet Themenseite(n), aber keine sichtbar — patchen.
            # Skip wenn kein Such-Tool gelaufen ist (Offer-Mode).
            if (not _offered_only_no_search and _n_themen == 0
                and _re_wd.search(
                    r"\bThemenseite(?:n)?\b", _new_text, _re_wd.IGNORECASE,
                )):
                _phrase_re = _re_wd.compile(
                    _det_adj + r"\bThemenseite(?:n)?\b",
                    _re_wd.IGNORECASE,
                )
                _new_text = _ctx_aware_sub(
                    _phrase_re, _new_text,
                    "passende Treffer in der Suche", _count=3,
                )
                _changed_reasons.append(f"themenseiten=0 aber Text claimt")  # noqa: F541

            # "ich hab(e) dir … rausgezogen/zusammengestellt/herausgesucht"
            # — auch wenn die Box leer ist, hat der Bot diese Liefer-
            # Behauptungen im Repertoire. Wenn weder Themenseiten noch
            # Sammlungen sichtbar sind, ist das eine pure Halluzination.
            # Dann ersetzen wir den Liefer-Satz durch einen Suchverweis.
            if (not _offered_only_no_search
                and _n_samml == 0 and _n_themen == 0):
                _new_text = _re_wd.sub(
                    r"(?im)^.*?(?:rausgezogen|rausgesucht|zusammengestellt|"
                    r"herausgesucht|gefunden|kuratiert).*?[.!?]\s*",
                    "Schau in die verlinkte Suche unten — dort findest du "
                    "passende Treffer zum Thema. ",
                    _new_text,
                    count=1,
                )
                if _new_text != response_text:
                    _changed_reasons.append("liefer-claim ohne sichtbare Boxen")

            if _changed_reasons and _new_text != response_text:
                logger.warning(
                    "anti-halluzination patch: %s | original=%r | patched=%r",
                    "; ".join(_changed_reasons),
                    response_text[:200],
                    _new_text[:200],
                )
                response_text = _new_text
        except Exception as _wd_err:
            # Wächter darf NIE den ganzen Turn fallen lassen — defensiv
            # nur warnen und Original-Text durchlassen.
            logger.warning(
                "anti-halluzination watchdog crashed: %s", _wd_err,
            )

    if _grouping_on_impl:
        _final_text, _web_links = _extract_web_links_from_text(
            response_text, cards=cards,
            # Lernpfad: Material-Erwähnungen als Text behalten (s. Helper).
            keep_bullet_labels=(_effective_pattern_id == "M09"),
        )
    else:
        _final_text, _web_links = response_text, []

    # Type-Focus defensiv: Webseiten-Inhalte-Box weg, wenn der User
    # Einzelinhalte wollte. Im Type-Focus-Mode ist der ehrliche Antwort-
    # Modus "Klick auf die Suche unten" — eine Webseiten-Inhalte-Box mit
    # RAG-Quellen lenkt davon ab und wirkt wie ein Treffer ("schau hier
    # ist was"). Auch wenn der Type-Focus-Text-Replace bereits gegriffen
    # hat und _web_links jetzt schon leer wäre — bei einem hypothetischen
    # Replace-Skip (z.B. wenn response_text leer war) hätte _web_links
    # noch Inhalt. Diese Zeile macht das Verhalten deterministisch.
    if _grouping_on_impl and _type_focus_label and _web_links:
        logger.info(
            "type-focus: cleared %d web_links (type-focus answer should be "
            "Such-CTA-only)", len(_web_links),
        )
        _web_links = []

    # Collect all MCP query metadata accumulated during this turn — wir
    # bauen die Liste hier (vor save_message), damit sie GEMEINSAM mit dem
    # Bot-Text in ``debug_json`` persistiert wird. Beim Session-Restore
    # ``GET /messages`` → ``msg.debug._query_metas`` kommt der Search-CTA
    # ("Alle Treffer in der Suche…") dann auch nach Reopen/Page-Nav wieder.
    from boerdi.api.schemas import QueryMetaEntry
    _raw_metas = get_query_metas()
    _query_meta_entries = []
    for _rm in _raw_metas:
        try:
            _query_meta_entries.append(QueryMetaEntry(
                tool_name=_rm.get("toolName", ""),
                query_type=_rm.get("queryType", ""),
                search_term=_rm.get("searchTerm", ""),
                criteria=_rm.get("criteria", []),
                pagination=_rm.get("pagination", {}),
                repository_url=_rm.get("repositoryUrl", ""),
                search_url=_rm.get("searchUrl", ""),
            ))
        except Exception:
            pass
    # ── Synthetic fallback meta für die Search-CTA (Welle C.5+, 2026-05-21) ──
    # Wenn das MCP für die Sammlungs-/Themenseiten-Tools keinen ``searchUrl``/
    # ``searchTerm`` mitliefert (passiert in Praxis bei manchen Tool-Variants),
    # bleibt die "Treffer zur Suche"-CTA im Frontend leer — obwohl Cards
    # gefunden wurden. Dann hat der Bot **defensiv** eine Suche durchgeführt,
    # die Frontend-Box sollte dem User auch den Sprung in die volle Suche
    # ermöglichen. Wir synthetisieren in diesem Fall einen Meta-Eintrag aus
    # den Klassifikations-Entities (thema / fach / Nachricht) + REPO_BASE_URL,
    # sodass der Frontend-Fallback (groupedSearchUrl) ohne Sonderlogik greift.
    _has_usable_search_signal = any(
        (m.search_url or m.search_term) for m in _query_meta_entries
    )
    if cards and not _has_usable_search_signal:
        _classif_entities = classification_dict.get("entities", {}) or {}
        _fallback_term = ""
        for _k in ("thema", "topic"):
            _v = (_classif_entities.get(_k) or "").strip()
            if _v:
                _fallback_term = _v
                break
        if not _fallback_term:
            _fach = (_classif_entities.get("fach") or "").strip()
            if _fach:
                _fallback_term = _fach
        if not _fallback_term:
            _msg = (req.message or "").strip()
            if _msg and len(_msg) <= 120:
                _fallback_term = _msg
        if _fallback_term:
            try:
                from boerdi.api.schemas import QueryMetaEntry as _QME
                _repo = (get_repo_base_url() or "").rstrip("/")
                _synthetic = _QME(
                    tool_name="synthetic_fallback",
                    query_type="fallback",
                    search_term=_fallback_term,
                    criteria=[],
                    pagination={},
                    repository_url=_repo,
                    search_url="",
                )
                _query_meta_entries.append(_synthetic)
                logger.info(
                    "synthesized fallback queryMeta for search-CTA: term=%r repo=%r",
                    _fallback_term, _repo,
                )
            except Exception as _qm_err:
                logger.warning("fallback queryMeta synthesis failed: %s", _qm_err)

    # ── Type-Focus Search-URL-Override (Welle C.5+, 2026-05-22) ────────
    # WLO/edu-sharing-Such-URL nutzt ``q=<keyword>&filters=<json>``.
    # Wir bauen die URL strukturiert und packen ALLE bekannten Filter
    # mit URI rein (URI-Lookup via mcp_client._label_to_uri_cache):
    #   q=<thema>
    #   filters={
    #     "ccm:oeh_lrt_aggregated": ["<lrt-uri>"]      # Material-Typ
    #     "ccm:taxonid":            ["<discipline-uri>"]  # Fach
    #     "ccm:educationalcontext": ["<eduCtx-uri>"]   # Bildungsstufe
    #   }
    #   sort={"active":"cm:modified","direction":"desc"} (Konvention)
    # Jeder Filter ist optional — fehlt das Entity oder findet das
    # Vocab-Lookup keine URI, fällt nur dieser eine Filter weg, der
    # Rest bleibt. Bei komplett leerem Filter-Dict landet der User in
    # der reinen Volltext-Suche und kann dort manuell filtern.
    if _type_focus_label:
        try:
            from boerdi.api.schemas import QueryMetaEntry as _QME_tf  # noqa: I001
            from urllib.parse import urlencode as _urlencode_tf
            import json as _json_tf

            # Vocab-Lookup-Helper (Best-Effort, returnt "" bei Miss).
            # Probiert Singular/Plural-Varianten + Umlaut-Transformationen,
            # weil das MCP-Vocab oft Singular-Canonicals speichert
            # (z.B. "Arbeitsblatt") und der User-Begriff Plural ist
            # (z.B. "Arbeitsblätter").
            async def _vocab_uri_for(vocab: str, label: str) -> str:
                if not label or not label.strip():
                    return ""
                try:
                    from boerdi.services.mcp.arg_resolvers import (  # noqa: I001
                        _label_to_uri_cache as _vc,
                        _ensure_label_cache as _ev,
                        _fuzzy_lookup as _fv,
                    )
                    await _ev(vocab)
                    _vmap = _vc.get(vocab) or {}

                    def _de_umlaut_a_o_u(s: str) -> str:
                        return (s.replace("ä", "a").replace("ö", "o")
                                 .replace("ü", "u").replace("ß", "ss"))

                    def _de_umlaut_ae(s: str) -> str:
                        return (s.replace("ä", "ae").replace("ö", "oe")
                                 .replace("ü", "ue").replace("ß", "ss"))

                    # Generiere Variantenliste: Original, plural-stripped,
                    # umlaut-transformiert. Reihenfolge so, dass die
                    # genauesten Matches zuerst stehen.
                    _base = label.strip().lower()
                    _stems: list[str] = []
                    for v in (_base, _de_umlaut_a_o_u(_base), _de_umlaut_ae(_base)):
                        if v and v not in _stems:
                            _stems.append(v)
                    # Plural-Suffixe abschneiden: er, en, e, n, s
                    _suffixes = ("er", "en", "e", "n", "s")
                    _candidates: list[str] = []
                    for stem in _stems:
                        if stem not in _candidates:
                            _candidates.append(stem)
                        for suf in _suffixes:
                            if stem.endswith(suf) and len(stem) > len(suf) + 2:
                                _c = stem[:-len(suf)]
                                if _c not in _candidates:
                                    _candidates.append(_c)
                    # Direkt-Hit?
                    for _k in _candidates:
                        if _k in _vmap:
                            return _vmap[_k]
                    # Fuzzy auf Original + Umlaut-Varianten
                    for _try in (label, _de_umlaut_a_o_u(_base),
                                  _de_umlaut_ae(_base)):
                        _m = _fv(_vmap, _try)
                        if _m:
                            return _m[1]
                except Exception as _e:
                    logger.debug(
                        "vocab-uri-lookup %s=%r nicht verfügbar: %s",
                        vocab, label, _e,
                    )
                return ""

            _classif_e_tf = classification_dict.get("entities", {}) or {}
            _sess_e_tf = session_state.get("entities", {}) or {}
            _tf_topic = (
                (_classif_e_tf.get("thema")
                 or _classif_e_tf.get("topic")
                 or _sess_e_tf.get("thema")
                 or "").strip()
            )
            if _tf_topic:
                # ── URIs aus MCP-queryMeta extrahieren (Primärquelle) ──
                # MCP's _queryMeta-Blöcke enthalten die URI-resolved
                # Filter-Daten in ``criteria`` (Liste von Dicts wie
                # ``{property: "ccm:taxonid", values: [<uri>], label: ...}``).
                # Wir bevorzugen diese URIs gegenüber dem eigenen
                # Vocab-Lookup, weil sie genau die sind, mit denen die
                # MCP-Tool-Calls tatsächlich gefiltert haben — kein
                # Risiko von Free-Text-Mismatch.
                _props_to_uri: dict[str, str] = {}
                for _meta in _query_meta_entries:
                    for _c in (_meta.criteria or []):
                        _prop = (_c.get("property") if isinstance(_c, dict)
                                 else "") or ""
                        _vals = (_c.get("values") if isinstance(_c, dict)
                                 else []) or []
                        # nur URIs übernehmen (Heuristik: beginnt mit
                        # ``http://`` oder ``https://``)
                        for _v in _vals:
                            if isinstance(_v, str) and _v.startswith(("http://", "https://")):
                                # Erstes URI je Property gewinnt (Reihenfolge =
                                # Tool-Call-Reihenfolge ≈ Relevanz).
                                _props_to_uri.setdefault(_prop, _v)
                                break

                # Property-Namen-Normalisierung: MCP nutzt manchmal Synonyme
                # ("ccm:educationalcontext" vs. "ccm:educationalContext",
                # "ccm:taxonid" als unique key). Wir mappen auf die
                # kanonischen WLO-Search-URL-Filter-Keys.
                def _pick_props(*keys: str) -> str:
                    for _k in keys:
                        _u = _props_to_uri.get(_k, "")
                        if _u:
                            return _u
                    return ""

                # 1) LRT — bevorzugt aus MCP criteria, sonst Vocab-Lookup
                _lrt_uri = _pick_props(
                    "ccm:oeh_lrt_aggregated",
                    "learningResourceType",
                )
                if not _lrt_uri:
                    _lrt_uri = await _vocab_uri_for("lrt", _type_focus_label)
                # 2) Discipline — bevorzugt aus MCP criteria, sonst entity-Lookup
                _disc_uri = _pick_props("ccm:taxonid", "discipline")
                if not _disc_uri:
                    _fach_label = (
                        (_classif_e_tf.get("fach")
                         or _sess_e_tf.get("fach")
                         or "").strip()
                    )
                    if _fach_label:
                        _disc_uri = await _vocab_uri_for("discipline", _fach_label)
                # 3) EducationalContext — analog
                _eductx_uri = _pick_props(
                    "ccm:educationalcontext",
                    "ccm:educationalContext",
                    "educationalContext",
                )
                if not _eductx_uri:
                    _stufe_label = (
                        (_classif_e_tf.get("stufe")
                         or _classif_e_tf.get("bildungsstufe")
                         or _sess_e_tf.get("stufe")
                         or "").strip()
                    )
                    if _stufe_label:
                        _eductx_uri = await _vocab_uri_for("educationalContext", _stufe_label)

                _repo = (get_repo_base_url() or "").rstrip("/")
                _tf_search_url = ""
                if _repo:
                    _qs: dict[str, str] = {"q": _tf_topic}
                    _filters_dict: dict[str, list[str]] = {}
                    if _lrt_uri:
                        _filters_dict["ccm:oeh_lrt_aggregated"] = [_lrt_uri]
                    if _disc_uri:
                        _filters_dict["ccm:taxonid"] = [_disc_uri]
                    if _eductx_uri:
                        _filters_dict["ccm:educationalcontext"] = [_eductx_uri]
                    if _filters_dict:
                        _qs["filters"] = _json_tf.dumps(
                            _filters_dict,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        # Sort-Konvention: neueste zuerst — passt zum Type-
                        # Focus-Anwendungsfall (User will frische Treffer).
                        _qs["sort"] = _json_tf.dumps(
                            {"active": "cm:modified", "direction": "desc"},
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                    logger.info(
                        "type-focus url-filters: lrt=%s discipline=%s eduCtx=%s",
                        bool(_lrt_uri), bool(_disc_uri), bool(_eductx_uri),
                    )
                    _tf_search_url = (
                        f"{_repo}/edu-sharing/components/search"
                        f"?{_urlencode_tf(_qs)}"
                    )
                    logger.info(
                        "type-focus search-url built (lrt_uri=%s): %s",
                        bool(_lrt_uri), _tf_search_url[:200],
                    )
                if _tf_search_url:
                    _tf_meta = _QME_tf(
                        tool_name="search_wlo_content",
                        query_type="type-focus-synth",
                        search_term=_tf_topic,
                        criteria=[{
                            "property": "learningResourceType",
                            "values": [_lrt_uri] if _lrt_uri else [_type_focus_label.lower()],
                            "label": _type_focus_label,
                        }],
                        pagination={},
                        repository_url=_repo,
                        search_url=_tf_search_url,
                    )
                    # An den ANFANG der Liste — Frontend nimmt den ersten
                    # search_wlo_content-Match.
                    _query_meta_entries.insert(0, _tf_meta)
        except Exception as _tfm_err:
            logger.warning("type-focus search-url override failed: %s", _tfm_err)

    if _query_meta_entries:
        tracer.record("query_meta", "MCP search queries", {
            "queries": [m.model_dump() for m in _query_meta_entries],
        })
    return (cards, response_text, _final_text, _web_links, _raw_metas,
            _query_meta_entries, _type_focus_label)
