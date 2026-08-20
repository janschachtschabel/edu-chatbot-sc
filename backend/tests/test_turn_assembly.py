"""Behaviour pins for ``services/turn_assembly._assemble_cards_and_qrs`` (port of
ALT ``chat_turn_assembly.py``, phases P20–P24).

The assembly has NO dedicated ALT unit test (it was exercised only end-to-end via
``test_chat_endpoint``), so these pins nail the observable contract of each phase:
card enrichment (preview_url synthesis + topic-page default description), build +
pagination, session refs, the QR cascade (forced > inline > none > speculative
consistency-gate > exact call, with orphan-cancel), guide-QR attach + marker-strip,
the collection-relevance fallback QR, and the page_action priority ladder.

Only the external boundaries are patched on THIS module (ALT convention — the
function imports them as top-level names): ``generate_quick_replies`` (LLM I/O),
``_attach_guide_qr`` (services), ``get_repo_base_url`` (config), ``_qr_default_count``
(config), ``_build_cards`` (built + tested separately). The relevance helpers
(``_is_themenseite_card`` / ``_collection_matches_topic``) and the marker-stripper
run for real against real ``WloCard`` objects.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.api.schemas import ChatRequest, WloCard
from boerdi.services import turn_assembly as ta

_PREVIEW = "https://repo.example/edu-sharing/preview?nodeId={nid}&storeProtocol=workspace&storeId=SpacesStore"


def _wlo(c: dict) -> WloCard:
    return WloCard(**{k: v for k, v in c.items() if k in WloCard.model_fields})


@pytest.fixture(autouse=True)
def _boundaries(monkeypatch):
    """Deterministic external boundaries; individual tests override as needed."""
    monkeypatch.setattr(ta, "get_repo_base_url", lambda: "https://repo.example")
    monkeypatch.setattr(ta, "_qr_default_count", lambda: 4)
    # Guide-attach: identity by default (isolate the rest of the cascade).
    monkeypatch.setattr(ta, "_attach_guide_qr",
                        lambda req, qrs, ss, response_text=None: qrs)
    # _build_cards: faithful-ish — map each (possibly enriched) raw dict to a WloCard.
    monkeypatch.setattr(ta, "_build_cards", lambda raw, persona: [_wlo(c) for c in raw])

    async def _gen(**k):
        return ["genQR1", "genQR2"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)


async def _call(**over):
    kw = dict(
        req=ChatRequest(session_id="s1", message="frage"),
        env={},
        session_state={"entities": {}},
        usage_acc={},
        classification=type("C", (), {"persona_id": ""})(),
        classification_dict={},
        winner=type("W", (), {"id": "M06"})(),
        pattern_output={"format_follow_up": "quick_replies", "max_items": 5},
        _canvas_payload_out=None,
        _canvas_forced_quick_replies=None,
        _qr_mode="auto",
        _qr_max=None,
        _qr_spec_task=None,
        _effective_pattern_id="M06",
        response_text="Antwort.",
        wlo_cards_raw=[],
        _host_qr_max=None,
    )
    kw.update(over)
    return await ta._assemble_cards_and_qrs(**kw)


# ── Card enrichment (phase P20) ────────────────────────────────────
async def test_synthesizes_preview_url_from_node_id():
    raw = [{"node_id": "abc", "node_type": "content"}]
    await _call(wlo_cards_raw=raw)
    assert raw[0]["preview_url"] == _PREVIEW.format(nid="abc")


async def test_does_not_overwrite_existing_preview_url():
    raw = [{"node_id": "abc", "preview_url": "keep"}]
    await _call(wlo_cards_raw=raw)
    assert raw[0]["preview_url"] == "keep"


async def test_default_description_for_bare_topic_page_card():
    raw = [{"node_id": "c", "topic_pages": [{"url": "u"}], "title": "Mathe"}]
    await _call(wlo_cards_raw=raw)
    assert "Themenseite" in raw[0]["description"]
    assert "Mathe" in raw[0]["description"]


# ── Pagination (phase P21) ─────────────────────────────────────────
async def test_pagination_none_at_or_below_page_size():
    raw = [{"node_id": f"n{i}", "node_type": "content"} for i in range(5)]
    _cards, _qr, _pa, pagination, _rt = await _call(wlo_cards_raw=raw)
    assert pagination is None


async def test_pagination_set_above_page_size():
    raw = [{"node_id": f"n{i}", "node_type": "content"} for i in range(6)]
    _cards, _qr, _pa, pagination, _rt = await _call(
        wlo_cards_raw=raw,
        session_state={"entities": {"thema": "x"}},  # keep cards (has topic)
    )
    assert pagination is not None
    assert pagination.total_count == 6
    assert pagination.page_size == 5
    assert pagination.has_more is False


# ── Session refs (phase P21b) ──────────────────────────────────────
async def test_session_refs_split_collections_and_contents():
    raw = [
        {"node_id": "coll1", "node_type": "collection", "title": "Sammlung"},
        {"node_id": "cont1", "node_type": "content", "title": "Material"},
    ]
    ss = {"entities": {"thema": "x"}}
    await _call(wlo_cards_raw=raw, session_state=ss)
    assert "coll1" in ss["entities"]["_last_collections"]
    assert "cont1" in ss["entities"]["_last_contents"]


# ── QR cascade (phase P22) ─────────────────────────────────────────
async def test_qr_forced_wins(monkeypatch):
    seen = {"gen": False}

    async def _gen(**k):
        seen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(_canvas_forced_quick_replies=["A", "B"])
    assert qr == ["A", "B"]
    assert seen["gen"] is False


async def test_qr_inline_wins_and_pops_session_key():
    ss = {"entities": {}, "_inline_quick_replies": ["I1"]}
    _c, qr, _pa, _pg, _rt = await _call(session_state=ss)
    assert qr == ["I1"]
    assert "_inline_quick_replies" not in ss


async def test_qr_mode_none_yields_empty(monkeypatch):
    seen = {"gen": False}

    async def _gen(**k):
        seen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(_qr_mode="none")
    assert qr == []
    assert seen["gen"] is False


async def test_qr_speculative_accepted_when_gate_ok(monkeypatch):
    seen = {"gen": False}

    async def _gen(**k):
        seen["gen"] = True
        return ["exact"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)

    async def _ret():
        return ["S1", "S2"]

    task = asyncio.create_task(_ret())
    _c, qr, _pa, _pg, _rt = await _call(
        _qr_spec_task=task, response_text="Hier ist die Antwort.",
    )
    assert qr == ["S1", "S2"]
    assert seen["gen"] is False


async def test_qr_speculative_rejected_on_question_triggers_exact_call():
    async def _hang():
        await asyncio.Event().wait()

    task = asyncio.create_task(_hang())
    _c, qr, _pa, _pg, _rt = await _call(
        _qr_spec_task=task, response_text="Welche Klasse?", _effective_pattern_id="M06",
    )
    assert qr == ["genQR1", "genQR2"]  # exact call used
    await asyncio.sleep(0)
    assert task.cancelled()  # orphan speculative task cancelled


async def test_qr_speculative_question_kept_for_m03(monkeypatch):
    async def _ret():
        return ["M03a", "M03b"]

    task = asyncio.create_task(_ret())
    _c, qr, _pa, _pg, _rt = await _call(
        _qr_spec_task=task, response_text="Welche Klassenstufe?",
        _effective_pattern_id="M03",
    )
    assert qr == ["M03a", "M03b"]


async def test_qr_max_zero_skips_generator(monkeypatch):
    seen = {"gen": False}

    async def _gen(**k):
        seen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(_qr_max=0)
    assert qr == []
    assert seen["gen"] is False


async def test_orphan_spec_task_cancelled_on_forced_path():
    async def _hang():
        await asyncio.Event().wait()

    task = asyncio.create_task(_hang())
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["F"], _qr_spec_task=task,
    )
    assert qr == ["F"]
    await asyncio.sleep(0)
    assert task.cancelled()


# ── Guide deco (phase P23) ─────────────────────────────────────────
async def test_guide_qr_attach_applied(monkeypatch):
    monkeypatch.setattr(
        ta, "_attach_guide_qr",
        lambda req, qrs, ss, response_text=None: ["__guide__|G|https://x", *qrs],
    )
    _c, qr, _pa, _pg, _rt = await _call()
    assert qr[0] == "__guide__|G|https://x"


async def test_guide_marker_stripped_from_response_text():
    _c, _qr, _pa, _pg, rt = await _call(
        response_text="Text hier. guide|Label|https://x.de/thema danach.",
    )
    assert "guide|" not in rt
    assert "https://" not in rt
    assert "Text hier" in rt


async def test_collection_relevance_fallback_qr(monkeypatch):
    async def _gen(**k):
        return ["g1", "g2", "g3", "g4"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    raw = [
        {"node_id": "c1", "node_type": "collection", "title": "Ganz anderes Thema"},
        {"node_id": "c2", "node_type": "collection", "title": "Noch was"},
    ]
    _c, qr, _pa, _pg, _rt = await _call(
        wlo_cards_raw=raw, session_state={"entities": {"thema": "Photosynthese"}},
    )
    assert qr[0] == "Zeig mir stattdessen Einzelmaterialien zu Photosynthese"
    assert len(qr) <= 4


# ── page_action ladder (phase P24) ─────────────────────────────────
async def test_page_action_canvas_payload_dominates():
    payload = {"action": "canvas_open", "payload": {"x": 1}}
    _c, _qr, page_action, _pg, _rt = await _call(_canvas_payload_out=payload)
    assert page_action is payload


async def test_cards_suppressed_without_topic_or_discovery():
    raw = [{"node_id": "n1", "node_type": "content", "title": "Startseite Mathe"}]
    cards, _qr, page_action, _pg, _rt = await _call(
        wlo_cards_raw=raw, session_state={"entities": {}},  # no thema/fach
        winner=type("W", (), {"id": "M06"})(),
    )
    assert cards == []
    assert page_action is None


async def test_page_action_show_results_on_host_page():
    raw = [{"node_id": "n1", "node_type": "content", "title": "Mat"}]
    _c, _qr, page_action, _pg, _rt = await _call(
        wlo_cards_raw=raw,
        session_state={"entities": {"thema": "Mathe"}},
        env={"page": "/suche", "page_context": {}},
    )
    assert page_action["action"] == "show_results"


async def test_page_action_canvas_show_cards_in_widget():
    raw = [{"node_id": "n1", "node_type": "content", "title": "Mat"}]
    _c, _qr, page_action, _pg, _rt = await _call(
        wlo_cards_raw=raw,
        session_state={"entities": {"thema": "Mathe"}},
        env={"page": "/suche", "page_context": {"widget": True}},
    )
    assert page_action["action"] == "canvas_show_cards"
    assert page_action["payload"]["append"] is False


# ── Anmelde-Rückfrage (C5-c2) ──────────────────────────────────────
# Die Bedingung läuft hier ECHT (``curation_blocked_by_mode``); nur der
# Zugangsblock wird gesetzt bzw. weggenommen. Ein Test, der stattdessen die
# Bedingung selbst attrappiert, bewiese nur, dass eine Attrappe zurückgibt,
# was man ihr eingebaut hat.


async def test_kurationsmuster_ohne_block_bietet_die_anmeldung_an(monkeypatch):
    from boerdi.services import response_tool_selection as rts
    monkeypatch.setattr(rts, "has_auth_token", lambda: False)

    _c, qrs, _pa, _pg, _rt = await _call(
        pattern_output={"format_follow_up": "quick_replies", "max_items": 5,
                        "tools": ["wlo_add_to_collection"]},
    )
    assert qrs[0] == "__auth__"
    assert qrs[1] == "Such einfach, ohne Anmeldung"


async def test_mit_block_bleibt_die_rueckfrage_weg(monkeypatch):
    """Wer kuratieren kann, soll nicht gefragt werden, ob er sich anmelden will."""
    from boerdi.services import response_tool_selection as rts
    monkeypatch.setattr(rts, "has_auth_token", lambda: True)

    _c, qrs, _pa, _pg, _rt = await _call(
        pattern_output={"format_follow_up": "quick_replies", "max_items": 5,
                        "tools": ["wlo_add_to_collection"]},
    )
    assert "__auth__" not in qrs


async def test_reines_suchmuster_bleibt_unberuehrt(monkeypatch):
    from boerdi.services import response_tool_selection as rts
    monkeypatch.setattr(rts, "has_auth_token", lambda: False)

    _c, qrs, _pa, _pg, _rt = await _call(
        pattern_output={"format_follow_up": "quick_replies", "max_items": 5,
                        "tools": ["search_wlo_content"]},
    )
    assert qrs == ["genQR1", "genQR2"]


async def test_die_sprache_des_zuges_gilt(monkeypatch):
    from boerdi.services import response_tool_selection as rts
    monkeypatch.setattr(rts, "has_auth_token", lambda: False)

    _c, qrs, _pa, _pg, _rt = await _call(
        req=ChatRequest(session_id="s1", message="frage",
                        environment={"locale": "en"}),
        pattern_output={"format_follow_up": "quick_replies", "max_items": 5,
                        "tools": ["wlo_add_to_collection"]},
    )
    assert qrs[1] == "Just search, no sign-in"


# ── Der Themen-Filter und die Schleifen-Maschinen (H6, live gemessen) ──────

_INHALTS_KARTE = {"node_id": "n1", "node_type": "content", "title": "Optik-Buch"}


async def test_ohne_thema_werden_karten_im_bestandsweg_unterdrueckt():
    """Der Bestandsfilter, unverändert: ohne Slot ist die Suche themenlos
    gelaufen, und die Treffer sind erfahrungsgemäß Müll."""
    ergebnis = await _call(wlo_cards_raw=[dict(_INHALTS_KARTE)],
                           winner=type("W", (), {"id": "M06"})(),
                           session_state={"entities": {}})
    assert ergebnis[0] == []


async def test_ein_thema_im_slot_laesst_die_karten_stehen():
    ergebnis = await _call(wlo_cards_raw=[dict(_INHALTS_KARTE)],
                           winner=type("W", (), {"id": "M06"})(),
                           session_state={"entities": {"thema": "Optik"}})
    assert len(ergebnis[0]) == 1


async def test_die_schleifen_maschinen_behalten_ihre_karten():
    """Live gemessen 2026-08-17: der Hybrid erntete acht Karten, und dieser
    Filter löschte alle acht — die Slots sind dort leer, weil das MODELL den
    Suchbegriff als Werkzeug-Argument übergibt statt eines Klassifikators.

    ``agent`` steht mit im Test, obwohl er bis heute durchkam: das lag allein
    daran, dass sein Modell meist ``search_wlo_all`` wählt, dessen
    Themenseiten-Karten die Ausnahme darüber treffen. Geliehen, nicht zugesichert.
    """
    for maschine in ("HYBRID", "AGENT"):
        ergebnis = await _call(wlo_cards_raw=[dict(_INHALTS_KARTE)],
                               winner=type("W", (), {"id": maschine})(),
                               session_state={"entities": {}})
        assert len(ergebnis[0]) == 1, f"{maschine} verliert seine Karten"


# ── O-B2: Mix-Modus (Host-Chips + KI-Auffuellung) ──────────────────
async def test_qr_mix_fuellt_mit_generator_bis_zur_gesamtzahl(monkeypatch):
    gesehen = {}

    async def _gen(**k):
        gesehen.update(k)
        return ["KI1", "KI2", "KI3"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["A", "B"], _host_qr_max=4)
    assert qr == ["A", "B", "KI1", "KI2"]
    assert gesehen["count"] == 2   # nur der Rest wird generiert


async def test_qr_mix_ohne_zahl_bleibt_hartes_ueberschreiben(monkeypatch):
    """Der O-B-Vertrag: keine Gesamtzahl -> forced ersetzt alles."""
    aufgerufen = {"gen": False}

    async def _gen(**k):
        aufgerufen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(_canvas_forced_quick_replies=["A"])
    assert qr == ["A"]
    assert aufgerufen["gen"] is False


async def test_qr_mix_kappt_forced_auf_die_gesamtzahl_ohne_generator(monkeypatch):
    aufgerufen = {"gen": False}

    async def _gen(**k):
        aufgerufen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["A", "B", "C"], _host_qr_max=2)
    assert qr == ["A", "B"]
    assert aufgerufen["gen"] is False


async def test_qr_mix_dedupe_gegen_die_host_chips(monkeypatch):
    """Erzeugt das Modell einen Host-Chip doppelt (Gross/klein egal),
    faellt er weg — dann kommen eben weniger Chips an."""

    async def _gen(**k):
        # "a" doppelt einen Host-Chip, das zweite "KI1" sich selbst — beides
        # faellt weg (Inline-QRs kommen ungeprueft aus der Antwort).
        return ["a", "KI1", "KI1"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["A"], _host_qr_max=4)
    assert qr == ["A", "KI1"]


async def test_qr_mix_nutzt_inline_qrs_ohne_generator_call(monkeypatch):
    """Agent-/Hybrid-Zuege liefern Inline-QRs aus der Antwort mit — die
    Fuellung ist dann gratis (kein zweiter LLM-Call)."""
    aufgerufen = {"gen": False}

    async def _gen(**k):
        aufgerufen["gen"] = True
        return ["x"]

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    ss = {"entities": {}, "_inline_quick_replies": ["I1", "I2"]}
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["A"], _host_qr_max=3, session_state=ss)
    assert qr == ["A", "I1", "I2"]
    assert aufgerufen["gen"] is False
    assert "_inline_quick_replies" not in ss


async def test_qr_mix_generatorfehler_laesst_die_host_chips_stehen(monkeypatch):
    async def _gen(**k):
        raise RuntimeError("B-API weg")

    monkeypatch.setattr(ta, "generate_quick_replies", _gen)
    _c, qr, _pa, _pg, _rt = await _call(
        _canvas_forced_quick_replies=["A", "B"], _host_qr_max=4)
    assert qr == ["A", "B"]
