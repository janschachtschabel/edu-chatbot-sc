"""P5/R5: direct-action handlers (services/direct_actions.py).

DI-rewrite of ALT ``app/routers/chat_direct_actions.py`` — the three actions the
widget triggers with a chip (``req.action`` ∈ {browse_collection,
generate_learning_path, curate_collection}) that short-circuit the turn and
build a full :class:`ChatResponse` directly, without ``generate_response``.

ALT convention (kept): the external boundaries — MCP (``call_mcp_tool`` +
parsers), the LLM generators, the QR generator and persistence — are patched
**on this module**; the pure card/guide/inline helpers run for real. So these
are fast unit tests, not pg-gated (the persistence itself is pinned in R3a/R3b).
"""

from __future__ import annotations

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.obs.usage import add_usage, new_accumulator
from boerdi.services import direct_actions


def _req(action: str, **params) -> ChatRequest:
    return ChatRequest(session_id="bb-1", message="los", action=action, action_params=params)


def _state() -> dict:
    return {"persona_id": "P-AND", "entities": {}}


def _raw_cards(n: int) -> list[dict]:
    """n minimal WLO card dicts, each with a unique node_id (so _build_cards
    keeps all n — it dedups by node_id)."""
    return [
        {
            "node_id": f"n{i}",
            "title": f"Titel {i}",
            "url": f"https://wlo.example/{i}",
            "description": f"Beschreibung {i}",
            "node_type": "content",
        }
        for i in range(n)
    ]


class _SaveSpy:
    """Records save_message calls (persistence boundary)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, session, session_id, role, content, cards=None, debug=None):
        self.calls.append(
            {"session_id": session_id, "role": role, "content": content,
             "cards": cards, "debug": debug}
        )


def _patch_browse_boundaries(monkeypatch, *, cards, total, qr=None):
    async def fake_mcp(name, args):
        fake_mcp.calls.append((name, args))
        return "MCP-TEXT"

    fake_mcp.calls = []
    save = _SaveSpy()

    async def fake_qr(**kwargs):
        return list(qr if qr is not None else ["qr-A"])

    monkeypatch.setattr(direct_actions, "call_mcp_tool", fake_mcp)
    monkeypatch.setattr(direct_actions, "parse_wlo_cards", lambda text: list(cards))
    monkeypatch.setattr(direct_actions, "parse_total_count", lambda text: total)
    monkeypatch.setattr(direct_actions, "generate_quick_replies", fake_qr)
    monkeypatch.setattr(direct_actions, "save_message", save)
    return fake_mcp, save


# ── browse_collection ───────────────────────────────────────────

async def test_browse_collection_paginates_and_builds_page_action(monkeypatch) -> None:
    # PAGE_SIZE+1 raw cards ⇒ has_more, display trimmed to PAGE_SIZE.
    fake_mcp, save = _patch_browse_boundaries(monkeypatch, cards=_raw_cards(6), total=42)

    resp = await direct_actions._handle_browse_collection(
        object(), _req("browse_collection", collection_id="col-1", title="Bio"), _state()
    )

    # 6 fetched, 5 shown (PAGE_SIZE), one over the edge signals has_more.
    assert len(resp.cards) == 5
    assert resp.content == "**Bio** — Ergebnisse 1–5 von 42:"
    assert resp.pagination is not None
    assert resp.pagination.total_count == 42
    assert resp.pagination.has_more is True
    assert resp.pagination.skip_count == 0
    assert resp.pagination.page_size == 5
    assert resp.pagination.collection_id == "col-1"
    assert resp.pagination.collection_title == "Bio"
    # canvas routing: contents go into the canvas card pane, not duplicated inline.
    assert resp.page_action is not None
    assert resp.page_action["action"] == "canvas_show_cards"
    assert resp.page_action["payload"]["source"] == "collection"
    assert resp.page_action["payload"]["collection_id"] == "col-1"
    assert resp.page_action["payload"]["append"] is False  # skip_count == 0
    assert len(resp.page_action["payload"]["cards"]) == 5
    assert "qr-A" in resp.quick_replies
    # fetched PAGE_SIZE+1 to detect has_more
    assert fake_mcp.calls[0][0] == "get_collection_contents"
    assert fake_mcp.calls[0][1] == {"nodeId": "col-1", "maxItems": 6, "skipCount": 0}
    # assistant turn persisted
    assert len(save.calls) == 1
    assert save.calls[0]["role"] == "assistant"
    assert save.calls[0]["session_id"] == "bb-1"
    assert resp.debug.pattern == "ACTION: browse_collection"


async def test_browse_collection_append_flag_and_skip_window(monkeypatch) -> None:
    # A second page (skip_count=5): window label shifts, append=True so the
    # frontend appends instead of replacing.
    _patch_browse_boundaries(monkeypatch, cards=_raw_cards(3), total=42)

    resp = await direct_actions._handle_browse_collection(
        object(),
        _req("browse_collection", collection_id="col-1", title="Bio", skip_count=5),
        _state(),
    )

    assert len(resp.cards) == 3  # only 3 left, no has_more
    assert resp.pagination.has_more is False
    assert resp.pagination.skip_count == 5
    assert resp.content == "**Bio** — Ergebnisse 6–8 von 42:"
    assert resp.page_action["payload"]["append"] is True


async def test_browse_collection_empty_is_honest(monkeypatch) -> None:
    _patch_browse_boundaries(monkeypatch, cards=[], total=0)

    resp = await direct_actions._handle_browse_collection(
        object(), _req("browse_collection", collection_id="col-1", title="Bio"), _state()
    )

    assert resp.cards == []
    assert 'In der Sammlung "Bio" habe ich leider keine Inhalte gefunden.' in resp.content


async def test_browse_bucht_seinen_qr_aufruf(monkeypatch) -> None:
    """Beim Bau von K1b/K1c gefunden, in KEINER Liste enthalten: auch das
    reine Blättern ruft den QR-Generator — ein echter LLM-Aufruf. Die Messung
    zählte nur Module mit eigenem Generator und übersah den geteilten."""
    _patch_browse_boundaries(monkeypatch, cards=_raw_cards(2), total=2)
    qr_kwargs: dict = {}

    async def fake_qr(**kwargs):
        qr_kwargs.update(kwargs)
        return ["qr-A"]

    monkeypatch.setattr(direct_actions, "generate_quick_replies", fake_qr)
    acc = new_accumulator()
    add_usage(acc, {"prompt": 7, "completion": 3, "model": "m"}, phase="probe")

    resp = await direct_actions._handle_browse_collection(
        object(), _req("browse_collection", collection_id="col-1", title="Bio"), _state(),
        usage_acc=acc,
    )

    assert qr_kwargs["usage_acc"] is acc
    assert resp.debug.token_usage["per_phase"]["probe"]["prompt"] == 7


async def test_browse_collection_missing_id_short_circuits(monkeypatch) -> None:
    fake_mcp, save = _patch_browse_boundaries(monkeypatch, cards=_raw_cards(3), total=3)

    resp = await direct_actions._handle_browse_collection(
        object(), _req("browse_collection", title="Bio"), _state()
    )

    assert resp.content == "Keine Sammlungs-ID angegeben."
    assert fake_mcp.calls == []  # never touched MCP
    assert save.calls == []


# ── curate_collection ───────────────────────────────────────────

class _CurationSpy:
    def __init__(self, out: str) -> None:
        self.out = out
        self.kwargs: dict | None = None

    async def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.out


def _patch_curate_boundaries(monkeypatch, *, cards, curate_out="KURATIONSTEXT", prompt="PROMPT"):
    async def fake_mcp(name, args):
        fake_mcp.calls.append((name, args))
        return "MCP-TEXT"

    fake_mcp.calls = []
    spy = _CurationSpy(curate_out)
    monkeypatch.setattr(direct_actions, "call_mcp_tool", fake_mcp)
    monkeypatch.setattr(direct_actions, "parse_wlo_cards", lambda text: list(cards))
    monkeypatch.setattr(direct_actions, "generate_curation_text", spy)
    monkeypatch.setattr(direct_actions, "load_context_actions", lambda: {"curate_prompt": prompt})
    return fake_mcp, spy


def test_curate_search_pill() -> None:
    assert (
        direct_actions._curate_search_pill("Bruchrechnen", "de")
        == "Fehlende Inhalte zu Bruchrechnen suchen"
    )
    assert direct_actions._curate_search_pill("  ", "de") == "Fehlende Inhalte suchen"
    assert (
        direct_actions._curate_search_pill("Bruchrechnen", "en")
        == "Search for content missing from Bruchrechnen"
    )


async def test_curate_no_compendium_is_honest_not_hallucinated(monkeypatch) -> None:
    # No editorial SOLL text ⇒ no reliable gap baseline ⇒ honest hint, no LLM call.
    _fake_mcp, spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(3))

    resp = await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", collection_id="col-1", title="Bio"), _state()
    )

    assert "keinen kompendialen Text" in resp.content
    assert resp.quick_replies == ["Fehlende Inhalte zu Bio suchen"]
    assert resp.debug.pattern == "ACTION: curate_collection"
    assert spy.kwargs is None  # the LLM was NOT asked to invent gaps


async def test_curate_with_compendium_runs_gap_analysis(monkeypatch) -> None:
    _fake_mcp, spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    state = _state()
    state["entities"]["_page_metadata"] = {"compendium_text": "SOLL: Zellatmung, Photosynthese"}

    resp = await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", collection_id="col-1", title="Bio"), state
    )

    assert resp.content == "KURATIONSTEXT"
    assert resp.quick_replies == ["Fehlende Inhalte zu Bio suchen"]
    # LLM got the SOLL (compendium), the IST (contents), and the Studio prompt.
    assert spy.kwargs["compendium"] == "SOLL: Zellatmung, Photosynthese"
    assert spy.kwargs["instruction"] == "PROMPT"
    assert "Titel 0" in spy.kwargs["contents_text"]
    assert resp.debug.tools_called == ["get_collection_contents", "llm_curation"]


async def test_kuration_bucht_auf_den_zug_merkposten(monkeypatch) -> None:
    """K1c: wie beim Lernpfad — der Merkposten geht an den Generator UND ins
    Debug, weil ``turn_persist`` auf dem Direkt-Aktions-Weg nicht läuft."""
    _fake_mcp, spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    state = _state()
    state["entities"]["_page_metadata"] = {"compendium_text": "SOLL: Zellatmung"}
    acc = new_accumulator()
    add_usage(acc, {"prompt": 7, "completion": 3, "model": "m"}, phase="probe")

    resp = await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", collection_id="col-1", title="Bio"), state,
        usage_acc=acc,
    )

    assert spy.kwargs["usage_acc"] is acc
    assert resp.debug.token_usage["per_phase"]["probe"]["prompt"] == 7


async def test_curate_missing_id_short_circuits(monkeypatch) -> None:
    fake_mcp, _spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))

    resp = await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", title="Bio"), _state()
    )

    assert resp.content == "Keine Sammlungs-ID angegeben."
    assert fake_mcp.calls == []


# ── generate_learning_path ──────────────────────────────────────

class _UpdateSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, session, session_id, **kwargs):
        self.calls.append({"session_id": session_id, **kwargs})


def _patch_lp_boundaries(monkeypatch, *, cards, lp_text=None, inline_ret=None,
                         qr_policy=("exact", 3)):
    async def fake_mcp(name, args):
        fake_mcp.calls.append((name, args))
        return "MCP-TEXT"

    fake_mcp.calls = []
    save = _SaveSpy()
    upd = _UpdateSpy()
    _lp_text = lp_text if lp_text is not None else ("Lernpfad Eiszeit. " + "wort " * 120)

    async def fake_lp(**kwargs):
        fake_lp.kwargs = kwargs
        return _lp_text

    fake_lp.kwargs = None

    async def fake_qr(**kwargs):
        return ["qr-A"]

    monkeypatch.setattr(direct_actions, "call_mcp_tool", fake_mcp)
    monkeypatch.setattr(direct_actions, "parse_wlo_cards", lambda text: [dict(c) for c in cards])
    monkeypatch.setattr(direct_actions, "generate_learning_path_text", fake_lp)
    monkeypatch.setattr(direct_actions, "generate_quick_replies", fake_qr)
    monkeypatch.setattr(direct_actions, "save_message", save)
    monkeypatch.setattr(direct_actions, "update_session", upd)
    monkeypatch.setattr(direct_actions, "_qr_policy", lambda pid: qr_policy)
    if inline_ret is not None:
        monkeypatch.setattr(direct_actions, "_build_inline_document", lambda *a, **k: inline_ret)
    return fake_mcp, save, upd, fake_lp


async def test_lp_direktaktion_bucht_beide_llm_aufrufe(monkeypatch) -> None:
    """K1b: Die Direkt-Aktion ist der ZWEITE Weg zum Lernpfad-Generator — die
    Messung im Plan kannte nur den Fast-Path. Beide LLM-Aufrufe des Handlers
    (Lernpfad + Quick-Replies) buchen auf den Zug-Merkposten.

    Und er MUSS hier ins Debug der Antwort: der preflight-Knoten beendet den
    Zug vorzeitig, ``turn_persist`` — die einzige Stelle, die sonst
    ``token_usage`` setzt — läuft auf diesem Weg nie.
    """
    _mcp, _save, _upd, fake_lp = _patch_lp_boundaries(monkeypatch, cards=_raw_cards(3))
    qr_kwargs: dict = {}

    async def fake_qr(**kwargs):
        qr_kwargs.update(kwargs)
        return ["qr-A"]

    monkeypatch.setattr(direct_actions, "generate_quick_replies", fake_qr)
    acc = new_accumulator()
    # Vorgebucht, damit sich „derselbe Merkposten" von „ein frischer" trennen
    # laesst — ein leerer waere von ``new_accumulator()`` nicht zu unterscheiden.
    add_usage(acc, {"prompt": 7, "completion": 3, "model": "m"}, phase="probe")

    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req("generate_learning_path", collection_id="col-1", title="Eiszeit"),
        _state(),
        usage_acc=acc,
    )

    assert fake_lp.kwargs["usage_acc"] is acc
    assert qr_kwargs["usage_acc"] is acc
    assert resp.debug.token_usage["per_phase"]["probe"]["prompt"] == 7


async def test_lp_happy_path_persists_canvas_state_and_marks_diversity(monkeypatch) -> None:
    inline_doc = {"kind": "ki_material", "title": "Lernpfad", "content": "BODY",
                  "meta": {"pattern": "M09"}}
    _fake_mcp, save, upd, fake_lp = _patch_lp_boundaries(
        monkeypatch, cards=_raw_cards(3), inline_ret=([inline_doc], "INTRO"),
    )
    state = _state()

    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req("generate_learning_path", collection_id="col-1", title="Eiszeit"),
        state,
    )

    # inline-document branch: bubble lead + boxed body
    assert resp.content == "INTRO"
    assert len(resp.inline_documents) == 1
    assert isinstance(resp.display_rules, dict)
    assert "qr-A" in resp.quick_replies
    assert resp.debug.pattern == "ACTION: generate_learning_path"
    assert resp.debug.intent == "I04"
    assert resp.debug.state == "S3"
    # assistant turn persisted
    assert len(save.calls) == 1 and save.calls[0]["role"] == "assistant"
    # canvas follow-up state persisted — entities as a native dict (jsonb), NOT json.dumps
    assert len(upd.calls) == 1
    assert upd.calls[0]["state_id"] == "S3"
    ent = upd.calls[0]["entities"]
    assert isinstance(ent, dict)  # jsonb dict, not a json-encoded string
    assert ent["_canvas_material_type"] == "lernpfad"
    assert ent["_canvas_topic"] == "Eiszeit"
    # session_state mutated for the M11 follow-up iteration
    assert state["state_id"] == "S3"
    # ``last_pattern`` stand hier bis 2026-08-15 und wurde von niemandem
    # gelesen — dazu auf der obersten Ebene, die ``update_session`` oben gar
    # nicht mitschreibt. Der Wächter zeigt jetzt umgekehrt: kein toter Merker.
    assert "last_pattern" not in state
    # diversity: the fetched node ids are marked used (before text-filtering)
    assert "n0" in state["entities"]["_lp_used_node_ids"]
    assert fake_lp.kwargs["collection_title"] == "Eiszeit"


async def test_lp_empty_collection_is_honest(monkeypatch) -> None:
    _fake_mcp, save, _upd, fake_lp = _patch_lp_boundaries(monkeypatch, cards=[])

    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req("generate_learning_path", collection_id="col-1", title="Eiszeit"),
        _state(),
    )

    assert "Leider keine Inhalte" in resp.content
    assert fake_lp.kwargs is None  # the LLM is not asked to build a path from nothing
    assert save.calls == []  # honest early-return, nothing persisted


async def test_lp_missing_id_short_circuits(monkeypatch) -> None:
    fake_mcp, _save, _upd, _fake_lp = _patch_lp_boundaries(monkeypatch, cards=_raw_cards(3))

    resp = await direct_actions._handle_generate_learning_path(
        object(), _req("generate_learning_path", title="Eiszeit"), _state()
    )

    assert resp.content == "Keine Sammlungs-ID angegeben."
    assert fake_mcp.calls == []


async def test_lp_generation_error_degrades_to_chat_bubble(monkeypatch) -> None:
    _fake_mcp, save, upd, _fake_lp = _patch_lp_boundaries(monkeypatch, cards=_raw_cards(3))

    async def boom(**kwargs):
        raise RuntimeError("B-API down")

    monkeypatch.setattr(direct_actions, "generate_learning_path_text", boom)

    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req("generate_learning_path", collection_id="col-1", title="Eiszeit"),
        _state(),
    )

    assert resp.content.startswith("Fehler beim Erstellen des Lernpfads")
    assert "error" in resp.debug.tools_called
    assert resp.inline_documents == []  # error branch returns before inline-doc build
    # even on failure the (error) turn is still persisted + canvas state advanced
    assert len(save.calls) == 1
    assert len(upd.calls) == 1


async def test_lp_trims_cards_to_materialien_max(monkeypatch) -> None:
    # 4 cards all referenced in the LP text; the Studio cap (=1) trims the
    # rendered Materialien box, matching the main-path group trim.
    cards = _raw_cards(4)
    lp_text = (
        "Lernpfad Test.\n"
        + "\n".join(f"- [T{i}](https://wlo.example/{i})" for i in range(4))
        + "\n" + ("pad " * 80)
    )
    _fake_mcp, _save, _upd, _fake_lp = _patch_lp_boundaries(
        monkeypatch, cards=cards, lp_text=lp_text,
    )
    monkeypatch.setattr(
        direct_actions, "load_display_rules_config",
        lambda: {"groups": {"materialien_max_lernpfad": 1}},
    )
    monkeypatch.setattr(direct_actions, "_build_inline_document", lambda *a, **k: ([], ""))

    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req("generate_learning_path", collection_id="col-1", title="Test"),
        _state(),
    )

    assert len(resp.cards) == 1


# ── _direct_action_safety_text (pure; R2 preflight screens with it) ──

def test_direct_action_safety_text_concatenates_and_caps() -> None:
    req = ChatRequest(
        session_id="bb-1",
        message="m" * 600,
        action="curate_collection",
        action_params={"title": "t" * 600, "collection_id": "c1", "n": 5},
    )
    text = direct_actions._direct_action_safety_text(req)

    assert text.startswith("m" * 500)  # message capped at 500
    assert "title: " + ("t" * 500) in text  # string params folded, capped
    assert "n: " not in text  # non-string action_params skipped
    assert len(text) <= 2000


# ── Sprache der Direkt-Aktionen (C1-f2a) ───────────────────────────────
# Die Verdrahtungs-Probe: `environment.locale` aus der Anfrage muss beim
# Erzeuger als `lang` ankommen. Ohne sie waere der Parameter Maschinerie
# ohne Verbraucher — genau der Fehler, den C1-f1 vermieden hat.


def _req_locale(action: str, locale: str, **params) -> ChatRequest:
    return ChatRequest(
        session_id="bb-1", message="los", action=action, action_params=params,
        environment=Environment(locale=locale),
    )


async def test_curate_reicht_die_widget_sprache_an_den_erzeuger_durch(monkeypatch) -> None:
    _fake_mcp, spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    state = _state()
    state["entities"]["_page_metadata"] = {"compendium_text": "SOLL: Zellatmung"}

    await direct_actions._handle_curate_collection(
        object(), _req_locale("curate_collection", "en-GB", collection_id="col-1", title="Bio"),
        state,
    )
    assert spy.kwargs["lang"] == "en"


async def test_curate_ohne_locale_bleibt_deutsch(monkeypatch) -> None:
    _fake_mcp, spy = _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    state = _state()
    state["entities"]["_page_metadata"] = {"compendium_text": "SOLL: Zellatmung"}

    await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", collection_id="col-1", title="Bio"), state,
    )
    assert spy.kwargs["lang"] == "de"  # Vorgabe des Vertrags ist "de-DE"


async def test_browse_leere_sammlung_folgt_der_sprache(monkeypatch) -> None:
    _patch_browse_boundaries(monkeypatch, cards=[], total=0)
    resp = await direct_actions._handle_browse_collection(
        object(), _req_locale("browse_collection", "en-GB", collection_id="c1", title="Bio"),
        _state(),
    )
    assert resp.content == 'I found no content in the collection "Bio".'


async def test_curate_ohne_kompendium_folgt_der_sprache(monkeypatch) -> None:
    _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    resp = await direct_actions._handle_curate_collection(
        object(), _req_locale("curate_collection", "en-GB", collection_id="c1", title="Bio"),
        _state(),
    )
    assert "no editorial summary on file" in resp.content
    assert resp.quick_replies == ["Search for content missing from Bio"]


async def test_curate_ohne_id_bleibt_auf_deutsch_ohne_locale(monkeypatch) -> None:
    _patch_curate_boundaries(monkeypatch, cards=_raw_cards(2))
    resp = await direct_actions._handle_curate_collection(
        object(), _req("curate_collection", title="Bio"), _state(),
    )
    assert resp.content == "Keine Sammlungs-ID angegeben."


async def test_lp_reicht_die_sprache_an_die_inline_box_durch(monkeypatch) -> None:
    """C1-f2b5: ``environment.locale`` muss bis zum Box-Titel durchkommen.

    Ohne diese Probe waere der neue ``lang``-Parameter von
    ``_build_inline_document`` wieder Maschinerie ohne Verbraucher — der
    Rueckfall-Titel stuende weiter auf Deutsch ueber einer englischen Box.
    """
    seen: dict = {}

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return ([{"kind": "lernpfad", "title": "T", "content": "B",
                  "meta": {"pattern": "M09"}}], "INTRO")

    _patch_lp_boundaries(monkeypatch, cards=_raw_cards(3))
    monkeypatch.setattr(direct_actions, "_build_inline_document", spy)

    await direct_actions._handle_generate_learning_path(
        object(),
        _req_locale("generate_learning_path", "en-GB", collection_id="col-1", title="Ice age"),
        _state(),
    )
    assert seen.get("lang") == "en"


async def test_lp_fehlschlag_bleibt_auch_auf_englisch_eine_schlichte_blase(monkeypatch) -> None:
    """Der Fehlschlag wird am Kontrollfluss erkannt, nicht am Wortlaut.

    Vor C1-f2b entschied ein ``startswith`` auf den deutschen Fehlersatz, ob
    statt eines Canvas-Dokuments eine schlichte Blase zurueckkommt. Mit einer
    zweiten Sprache haette der Vergleich still nicht mehr gegriffen — und der
    Nutzer haette einen Fehlertext als Lernpfad-Dokument praesentiert bekommen.
    """
    _fake_mcp, save, _upd, _fake_lp = _patch_lp_boundaries(monkeypatch, cards=_raw_cards(3))

    async def boom(**kwargs):
        raise RuntimeError("B-API down")

    monkeypatch.setattr(direct_actions, "generate_learning_path_text", boom)

    state = _state()
    resp = await direct_actions._handle_generate_learning_path(
        object(),
        _req_locale("generate_learning_path", "en-GB", collection_id="col-1", title="Ice age"),
        state,
    )

    assert resp.content.startswith('Failed to build the learning path for "Ice age"')
    assert "error" in resp.debug.tools_called
    # Der Fehl-Zweig kehrt frueh zurueck. Seit 2026-08-15 markiert auch der
    # Erfolgszweig nichts mehr (der Merker war wirkungslos, Begründung im
    # Handler) — die Zusicherung „ein Fehlertext wird nicht zum Bearbeiten-
    # Gegenstand" gilt damit erst recht, und der Wächter hält sie fest.
    assert "last_pattern" not in state
