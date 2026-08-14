"""P3-3a: response system-prompt builder (``_build_system_prompt``, P1-P9) —
byte-parity port of ALT ``llm_prompt_builder.py:40-880``.

Direct unit tests against the assembled prompt: ``generate_response`` is P4/P5
(not built yet), so these pin the behaviour-critical markers of the prompt
directly. Config loaders + ``get_state_directive`` are patched on the builder
module (no ConfigStore needed); ``_render_pattern_brief`` / ``_formality_guidance``
run for real (pure). The P3 page-context block runs for real too (``get_cached`` +
``render_for_prompt`` are pure, driven off a seeded ``_page_metadata``). Only the
prompt-size telemetry (P9) is simplify-deferred, so it is not asserted here.
"""

from __future__ import annotations

import json

import pytest

from boerdi.services import response_prompt_builder as rpb
from boerdi.services import response_prompt_pattern as rpp


@pytest.fixture()
def _cfg(monkeypatch):
    monkeypatch.setattr(rpb, "load_base_persona", lambda: "BASE_PERSONA")
    monkeypatch.setattr(rpb, "load_domain_rules", lambda: "DOMAIN_RULES")
    monkeypatch.setattr(rpb, "load_persona_prompt", lambda pid: f"PERSONA_PROMPT[{pid}]")
    monkeypatch.setattr(rpb, "load_guardrails", lambda: "GUARDRAILS_BLOCK")
    monkeypatch.setattr(rpb, "get_state_directive", lambda sid: {
        "id": sid, "label": "Test-Phase", "role": "Kurator",
        "bot_directive": "Stelle eine Frage.", "next_likely": [],
    })
    return monkeypatch


def _build(**over):
    kw = {
        "classification": {"persona_id": "P-AND", "entities": {}, "signals": [],
                           "next_state": "S1"},
        "pattern_output": {"label": "M05 (Material)", "body_md": ""},
        "pattern_label": "M05 (Material-Suche)",
        "session_state": {"entities": {}},
        "environment": {},
        "rag_context": "",
        "available_rag_areas": None,
        "rag_config": None,
    }
    kw.update(over)
    return rpb._build_system_prompt(
        kw["classification"], kw["pattern_output"], kw["pattern_label"],
        kw["session_state"], kw["environment"], kw["rag_context"],
        kw["available_rag_areas"], kw["rag_config"],
    )


# ── layer order (P2/P7/P8/P9) ──────────────────────────────────────────────
def test_layer_order_base_domain_persona_pattern_context_rag_guardrails_tools_recency(_cfg):
    system, *_ = _build(
        rag_context="<<RAGCTX>>",
        pattern_output={"label": "M05 (Material)", "body_md": "BODY_RECAP"},
    )
    order = [
        "BASE_PERSONA", "DOMAIN_RULES", "PERSONA_PROMPT[P-AND]",
        "## Aktives Pattern: M05 (Material)", "## Kontext", "<<RAGCTX>>",
        "GUARDRAILS_BLOCK", "## Verfuegbare Werkzeuge", "## ⚡ LETZTE ERINNERUNG",
    ]
    idxs = [system.index(m) for m in order]
    assert idxs == sorted(idxs), f"layer order broken: {list(zip(order, idxs, strict=True))}"


# ── context block (P2 Layer 5) ─────────────────────────────────────────────
def test_context_block_renders_state_role_entities_signals(_cfg):
    system, *_ = _build(classification={
        "persona_id": "P-AND",
        "entities": {"thema": "Bruchrechnen", "_intern": "x"},
        "signals": ["frust", "eile"], "next_state": "S7",
    })
    assert "Gesprächs-Phase: S7 (Test-Phase)" in system
    assert "Rolle in dieser Phase: Kurator" in system
    assert 'Entities: {"thema": "Bruchrechnen"}' in system
    assert "_intern" not in system
    assert "Signale: frust, eile" in system
    assert "Stelle eine Frage." in system  # bot_directive as Phase-Direktive


def test_unknown_state_falls_back_to_placeholders(_cfg):
    _cfg.setattr(rpb, "get_state_directive", lambda sid: {})
    system, *_ = _build(classification={"persona_id": "P-AND", "entities": {},
                                        "signals": [], "next_state": "S9"})
    assert "Gesprächs-Phase: S9 (?)" in system
    assert "Rolle in dieser Phase: —" in system
    assert "— keine spezifische Direktive für diese Phase, folge dem Pattern." in system


# ── semantic page-context block (P3) ───────────────────────────────────────
def test_resolved_page_context_block_injected_after_context(_cfg):
    ss = {"entities": {"_page_metadata": {"title": "Optik", "unresolved": False}}}
    env = {"page_context": {"page_kind": "collection", "collection_id": "C1"}}
    system, *_ = _build(session_state=ss, environment=env)
    assert "## Aktuelle Seite — Sammlung (edu-sharing)" in system
    assert "Titel: Optik" in system
    assert "Sammlungs-ID (collection_id): C1" in system
    # after the generic context layer, before the always-last guardrails
    assert system.index("## Kontext") < system.index("## Aktuelle Seite —")
    assert system.index("## Aktuelle Seite —") < system.index("GUARDRAILS_BLOCK")


def test_raw_page_context_fallback_when_unresolved(_cfg):
    # no _page_metadata → get_cached None → render_for_prompt "" → raw fallback
    env = {"page_context": {"page_kind": "content", "page_text": "Sichtbarer Seitentext hier."}}
    system, *_ = _build(session_state={"entities": {}}, environment=env)
    assert "## Inhalt der aktuellen Seite (Heuristik)" in system
    assert "Sichtbarer Seitentext hier." in system


def test_no_page_context_block_when_nothing_resolvable(_cfg):
    system, *_ = _build(session_state={"entities": {}}, environment={"page_context": {}})
    assert "## Aktuelle Seite —" not in system
    assert "## Inhalt der aktuellen Seite (Heuristik)" not in system


def test_page_context_block_failure_is_swallowed(_cfg):
    def boom(_ss):
        raise RuntimeError("cache read blew up")

    _cfg.setattr(rpb.page_context, "get_cached", boom)
    ss = {"entities": {"_page_metadata": {"title": "Optik"}}}
    # a page-block failure must not break the prompt — it still assembles fully.
    system, *_ = _build(session_state=ss, environment={"page_context": {"page_kind": "collection"}})
    assert "GUARDRAILS_BLOCK" in system
    assert "## Aktuelle Seite —" not in system


# ── M11 re-render (P4) ─────────────────────────────────────────────────────
def test_m11_rerender_injects_prev_content_with_8000_cap(_cfg):
    po = {"label": "M11", "output_mode": "rerender", "body_md": ""}
    s_at, *_ = _build(pattern_output=po, pattern_label="M11 (Edit)",
                      session_state={"entities": {"_canvas_last_markdown": "X" * 8000}})
    assert "## Aktueller Inhalt zum Editieren" in s_at
    assert "X" * 8000 in s_at
    assert "(Inhalt gekürzt" not in s_at

    s_over, *_ = _build(pattern_output=po, pattern_label="M11 (Edit)",
                        session_state={"entities": {"_canvas_last_markdown": "X" * 8001}})
    assert "X" * 8000 in s_over
    assert "X" * 8001 not in s_over
    assert "(Inhalt gekürzt" in s_over


# ── display modes (P5) ─────────────────────────────────────────────────────
@pytest.mark.parametrize("mode", ["minimal", "reference", "highlight"])
def test_card_text_mode_marker(_cfg, mode):
    system, *_ = _build(pattern_output={"label": "M05", "card_text_mode": mode, "body_md": ""})
    assert f"(Modus: {mode})" in system


def test_kachel_mode_always_offers_rerank(_cfg):
    system, *_ = _build(environment={})  # cards_enabled absent → Kachel-Modus
    assert "## Optionaler Re-Rank über select_top_cards" in system


def test_inline_grouping_mode_for_search_pattern_and_no_rerank(_cfg):
    system, ci, ig, _ = _build(environment={"cards_enabled": False},
                               pattern_label="M05 (Material-Suche)")
    assert "## Inline-Result-Grouping-Mode" in system
    # interior + end-of-block pins guard against mid-block truncation of the
    # ~140-line verbatim block, not just the header.
    assert "VERBOTENE WÖRTER im Antwort-Text" in system
    assert '❌ "ergänzende Inhalte"' in system  # regression: this line was dropped in the port
    assert "URLs werden vom System automatisch über Kacheln/Boxen/CTAs gerendert." in system
    assert "## Optionaler Re-Rank über select_top_cards" not in system
    assert ci is True and ig is True


def test_inline_non_search_pattern_gets_kein_suche_block(_cfg):
    system, *_ = _build(environment={"cards_enabled": False},
                        pattern_label="M04 (Wissens-Antwort)")
    assert "## Pattern-Modus: KEIN Suche-Antworten" in system


def test_legacy_inline_link_mode_when_grouping_disabled(_cfg):
    system, ci, ig, _ = _build(
        environment={"cards_enabled": False, "inline_result_grouping": False},
        pattern_label="M05 (Material-Suche)")
    assert "## Inline-Link-Mode" in system
    assert "LIEFERN, NICHT VERSPRECHEN." in system  # interior pin
    assert "liefert, übergib sie NICHT als Text — das System verlinkt die Kachel." in system
    assert ci is True and ig is False


# ── signal modulation + degradation (P6/P8) ────────────────────────────────
def test_signal_rules_appended(_cfg):
    system, *_ = _build(pattern_output={
        "label": "M05", "body_md": "",
        "skip_intro": True, "one_option": True, "add_sources": True,
    })
    assert "## Regel: Keine Einleitung. Direkt zur Sache." in system
    assert "## Regel: Nur 1 Option anbieten. Nicht überfordern." in system
    assert "## Regel: Quellen und Herkunft explizit nennen." in system


def test_degradation_block_and_tool_lock(_cfg):
    system, _ci, _ig, dnt = _build(pattern_output={
        "label": "M05", "body_md": "",
        "degradation": True, "missing_slots": ["thema"],
        "blocked_patterns": [{"id": "M05", "label": "Material", "missing": ["thema"]}],
    })
    assert "## Degradation aktiv: Fehlende Slots: ['thema']." in system
    assert "Blockierte Patterns: M05 (Material, braucht: thema)." in system
    assert "PFLICHT-RUECKFRAGE" in system
    assert "## Verfuegbare Werkzeuge" not in system
    assert dnt is True


def test_explicit_empty_tools_yields_m15_no_tools_rules(_cfg):
    system, *_ = _build(pattern_output={"label": "M15", "body_md": "", "tools": []})
    assert "Antworte NUR mit flieszendem Text." in system
    assert "## Verfuegbare Werkzeuge" not in system


# ── session context blocks (P8) ────────────────────────────────────────────
def test_session_collections_and_contents_blocks(_cfg):
    ss = {"entities": {
        "_last_collections": json.dumps([{"title": "Sammlung Brueche", "node_id": "col1"}]),
        "_last_contents": json.dumps([{"title": "Video Brueche",
                                       "learning_resource_types": ["Video"],
                                       "description": "D" * 150}]),
    }}
    system, *_ = _build(session_state=ss)
    assert "## Verfuegbare Sammlungen aus vorherigen Ergebnissen" in system
    assert '- "Sammlung Brueche" (nodeId: col1)' in system
    assert "## Zuvor gezeigte Materialien" in system
    assert '1. "Video Brueche" (Video) — ' in system
    assert "D" * 100 in system
    assert "D" * 101 not in system
    # tools block present + intact end-of-block (guards the ~110-line verbatim block)
    assert "## Tool-Routing-Regeln" in system
    assert "learningResourceType" in system
    assert "11-13=Sek II)." in system


def test_tools_block_lists_knowledge_areas_when_available(_cfg):
    system, *_ = _build(
        available_rag_areas=["WirLernenOnline"],
        rag_config={"WirLernenOnline": {"description": "WLO-Plattformwissen"}},
    )
    assert 'query_knowledge(area="WirLernenOnline"): WLO-Plattformwissen' in system


def test_tools_block_falls_back_when_no_knowledge_areas(_cfg):
    system, *_ = _build(available_rag_areas=None, rag_config=None)
    assert "(Keine Wissensbereiche verfuegbar)" in system


# ── returned flags ─────────────────────────────────────────────────────────
def test_flags_default_non_inline(_cfg):
    _system, ci, ig, dnt = _build()
    assert (ci, ig, dnt) == (False, False, False)


# ── pattern helpers (direct, pure) ─────────────────────────────────────────
def test_render_pattern_brief_full_sections():
    out = rpp._render_pattern_brief({
        "label": "M05", "core_rule": "CORE", "forbidden_phrases": ["FP"],
        "anti_patterns": ["AP"], "body_md": "BODY", "response_type": "answer",
        "tone": "sachlich", "when_to_use": ["W1"],
    })
    assert "## Aktives Pattern: M05" in out
    assert "Response-Typ: answer  ·  Ton: sachlich" in out
    assert "### Warum dieses Pattern (Kontext-Briefing)" in out
    assert "### Kernregel (HART)\nCORE" in out
    assert "### Verbotene Formulierungen — NICHT verwenden" in out
    assert '- "FP"' in out
    assert "### Anti-Patterns — diese Handlungen vermeiden" in out
    assert "### Pattern-Brief (verbindlich)\nBODY" in out


def test_render_pattern_brief_empty_placeholder():
    out = rpp._render_pattern_brief({"label": "M15"})
    assert "_(kein Pattern-Brief — folge der Kernregel)_" in out


def test_formality_sie_strict_persona_gets_professional_register():
    out = rpp._formality_guidance("Sie", "P-ENT")
    assert "Sie-Form" in out
    assert "Register professionell halten" in out


def test_formality_p_leh_special_block():
    out = rpp._formality_guidance("siezen", "P-LEH")
    assert "P-LEH SPEZIAL" in out


def test_formality_du_schueler():
    out = rpp._formality_guidance("du", "P-LER")
    assert "Du-Form" in out
    assert "Schüler:in" in out


def test_formality_neutral_default():
    out = rpp._formality_guidance("neutral", "P-AND")
    assert "bleibe neutral" in out


# ── Sprache der Antwort (C1-f1) ────────────────────────────────────────────
# Der Prompt trug diese Zeile schon immer, hart auf Deutsch — und zwar in
# ALLEN DREI sich ausschliessenden P8-Bloecken. C1-f1 macht sie sprachabhaengig
# statt eine zweite, widersprechende Direktive anzuhaengen.
DE_ZEILE = "Antworte auf Deutsch. Formatiere mit Markdown."

_P8_ZWEIGE = {
    "werkzeuge": {"label": "M05 (Material)", "body_md": ""},
    "m15_ohne_werkzeuge": {"label": "M15", "body_md": "", "tools": []},
    "degradation": {"label": "M05 (Material)", "body_md": "", "degradation": True,
                    "missing_slots": ["fach"], "blocked_patterns": []},
}


@pytest.mark.parametrize("zweig", sorted(_P8_ZWEIGE))
def test_deutsch_bleibt_wortgleich_in_jedem_p8_zweig(_cfg, zweig):
    """Der Regelfall aendert sich nicht — auch nicht die Position der Zeile.

    Deshalb wird sie an Ort und Stelle sprachabhaengig, statt als eigener
    Block hinten anzuhaengen: das haette den deutschen Satz jedes Zuges hinter
    den Aktualitaets-Anker verschoben, ohne dass irgendwer das gewollt haette.
    """
    ohne, *_ = _build(pattern_output=_P8_ZWEIGE[zweig], environment={})
    deutsch, *_ = _build(pattern_output=_P8_ZWEIGE[zweig], environment={"locale": "de-DE"})
    assert DE_ZEILE in ohne
    assert deutsch == ohne


@pytest.mark.parametrize("zweig", sorted(_P8_ZWEIGE))
def test_englisches_locale_tauscht_die_zeile_in_jedem_p8_zweig(_cfg, zweig):
    system, *_ = _build(pattern_output=_P8_ZWEIGE[zweig], environment={"locale": "en-GB"})
    assert DE_ZEILE not in system
    assert "Antworte auf Englisch" in system


def test_unbekanntes_locale_faellt_auf_deutsch_zurueck(_cfg):
    # Kein Ratespiel bei `fr-FR`: nicht unterstuetzt -> Standard, wie
    # `resolve_locale` es auch fuer den Accept-Language-Header tut (C1-e1).
    system, *_ = _build(environment={"locale": "fr-FR"})
    assert DE_ZEILE in system


# ── Bestand + Skillkatalog in der Muster-Engine (Nutzer-Vorgabe 2026-08-14) ─
#
# „inhaltsanzahl und Skillregistry muss man in beiden modi aktiv rein geben —
# pattern und agent loop". Dies ist die Muster-Seite; die Agent-Seite hängt am
# selben Renderer und hat ihren Wächter in ``test_respond_agent``.


def _sammlung_mit_bestand() -> dict:
    return {"entities": {"_page_metadata": {
        "title": "Geometrische Optik",
        "context_facts": {
            "materials": 35, "sub_collections": 4, "skills": 28,
            "skill_titles": ["Stunde planen"],
        },
    }}}


def test_bestand_und_skillkatalog_stehen_im_muster_prompt(_cfg):
    system, *_ = _build(
        session_state=_sammlung_mit_bestand(),
        environment={"page_context": {"page_kind": "collection", "collection_id": "C1"}},
    )
    assert "35 Materialien" in system
    assert "28" in system
    assert "Stunde planen" in system
    assert "search_skill" in system
    assert "get_skill" in system


def test_ohne_bestand_bleibt_der_muster_prompt_wie_bisher(_cfg):
    # Gegenprobe: kein leerer Abschnitt auf einer Seite ohne Bestandsangaben.
    system, *_ = _build(
        session_state={"entities": {"_page_metadata": {"title": "Irgendwas"}}},
        environment={"page_context": {"page_kind": "collection"}},
    )
    assert "Bestand dieser Sammlung" not in system
