"""Tests for the proactive context-greeting node (P4-2d, R6).

Port of ALT ``test_context_greeting.py``. Two layers:

* ``maybe_context_greeting`` (the ported dispatcher): ``None`` ONLY when
  ``page_event != 'context_open'``; on ``context_open`` ALWAYS a ChatResponse —
  a greeting when every gate passes, else ``content == ""``. The two DB writes
  are patched on THIS module; ``page_context`` + ``load_context_actions`` run for
  real (unseeded config store → the ALT-identical defaults).
* ``context_greeting`` (the node adapter): sets ``ctx.early_response`` on a hit,
  leaves it None on a normal turn, and swallows dispatcher errors (a greeting bug
  must never break the turn).

NEU seam deviations over ALT: the DB writes take ``session`` first, so the fakes
and the assertion indices shift by one.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.api.schemas import ChatRequest
from boerdi.graph.nodes import context_greeting as g
from boerdi.graph.state import TurnContext

_SESSION = object()  # sentinel — the patched DB writes ignore it


def _req(session_id: str = "s1", message: str = "") -> ChatRequest:
    return ChatRequest(session_id=session_id, message=message)


def _env(page_event: str | None = "context_open", page_context: dict | None = None) -> dict:
    return {"page_event": page_event, "page_context": page_context or {}}


def _state(meta: dict, greeted: list | None = None) -> dict:
    ents: dict = {"_page_metadata": meta}
    if greeted is not None:
        ents["_greeted_pages"] = greeted
    return {"entities": ents}


def _resolved(title: str = "Optik", **extra) -> dict:
    return {"title": title, "unresolved": False, **extra}


def _collection_ctx() -> dict:
    return {"page_kind": "collection", "collection_id": "C1"}


def _sig_collection(title: str = "Optik") -> str:
    """Der Entdopplungs-Schlüssel, den der Knoten für `_collection_ctx` vermerkt."""
    return g._greeting_signature("collection", _collection_ctx(), {"title": title})


def _patch_io(monkeypatch) -> dict:
    calls: dict = {"update": [], "save": []}

    async def fake_update(session, session_id, **kw):
        calls["update"].append((session, session_id, kw))

    async def fake_save(session, session_id, role, content, **kw):
        calls["save"].append((session, session_id, role, content, kw))

    monkeypatch.setattr(g, "update_session", fake_update)
    monkeypatch.setattr(g, "save_message", fake_save)
    return calls


# ── Dispatcher: maybe_context_greeting ──────────────────────────────────────

def test_no_page_event_returns_none(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), {"page_event": None, "page_context": _collection_ctx()},
        _state(_resolved()), ["prev"]))
    assert resp is None


def test_empty_history_returns_empty_and_persists_nothing(monkeypatch):
    calls = _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), _state(_resolved()), []))
    assert resp is not None and resp.content == ""
    assert calls["save"] == [] and calls["update"] == []


def test_collection_greeting_full(monkeypatch):
    calls = _patch_io(monkeypatch)
    state = _state(_resolved(title="Optik"))
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), state, ["prev"]))
    assert "Optik" in resp.content
    assert resp.debug.pattern == "CTX:collection"
    joined = "\n".join(resp.quick_replies)
    # Beschriftung seit P7 „Sammlungsinhalte zeigen" (Nutzer-Vorgabe
    # 2026-08-13); die Aktion dahinter ist unverändert ``browse_collection``.
    assert "__action__|Sammlungsinhalte zeigen|browse_collection|" in joined
    assert "__action__|Sammlung kuratieren|curate_collection|" in joined
    assert '"collection_id": "C1"' in joined
    assert "__guide__|Inhalt melden|" in joined
    # dedup recorded + persisted exactly once each
    assert _sig_collection() in state["entities"]["_greeted_pages"]
    assert len(calls["update"]) == 1
    assert len(calls["save"]) == 1 and calls["save"][0][2] == "assistant"


def test_dedup_second_call_returns_empty(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    ctx = _collection_ctx()
    r1 = asyncio.run(
        g.maybe_context_greeting(_SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    assert r1.content
    r2 = asyncio.run(
        g.maybe_context_greeting(_SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    assert r2.content == ""


def test_suche_ohne_suchbegriff_bleibt_stumm(monkeypatch):
    # Bis zur Seitenkontext-Erweiterung schwieg `search` immer. Jetzt meldet es
    # sich — aber nur, wenn es einen Suchbegriff zu nennen gibt. Eine leere
    # Suchseite hat keinen Gegenstand, über den zu reden wäre.
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "search"}),
        _state(_resolved()), ["prev"]))
    assert resp.content == ""


def test_topic_page_kind_greets(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "topic", "collection_id": "T1"}),
        _state(_resolved(title="Klimawandel")), ["prev"]))
    assert "Klimawandel" in resp.content
    assert resp.debug.pattern == "CTX:topic"


def test_unresolved_meta_returns_empty(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state({"title": "T", "unresolved": True}), ["prev"]))
    assert resp.content == ""


def test_content_report_pill_uses_node_id(monkeypatch):
    _patch_io(monkeypatch)
    ctx = {"page_kind": "content", "node_id": "N9"}
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=ctx), _state(_resolved(title="Material")), ["prev"]))
    joined = "\n".join(resp.quick_replies)
    assert "node=N9" in joined  # report_url {node_id} substituted


def test_melden_prefilled_and_erkunden_action_pill_parseable(monkeypatch):
    """T14-Golden: the Melden pill carries the pre-filled ID in the URL, and the
    Erkunden action pill decodes to browse_collection + valid params-JSON (the
    contract the frontend parser consumes)."""
    import json as _json
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state(_resolved(title="Optik")), ["prev"]))

    report = next(q for q in resp.quick_replies if q.startswith("__guide__|Inhalt melden|"))
    assert "node=C1" in report and "type=quelle" in report

    erkunden = next(
        q for q in resp.quick_replies
        if q.startswith("__action__|Sammlungsinhalte zeigen|")
    )
    _, label, action, params_json = erkunden.split("|", 3)
    assert action == "browse_collection"
    params = _json.loads(params_json)
    assert params["collection_id"] == "C1"
    assert params["title"] == "Optik"


def test_greeted_pages_fifo_cap_20(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved(), greeted=[f"sig{i}" for i in range(20)])
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()), state, ["prev"]))
    assert resp.content
    greeted = state["entities"]["_greeted_pages"]
    assert len(greeted) == 20            # capped
    assert "sig0" not in greeted         # oldest evicted
    assert _sig_collection() in greeted


# ── Node adapter: context_greeting(ctx, session) ────────────────────────────

def _node_ctx(env: dict, session_state: dict, history: list) -> TurnContext:
    ctx = TurnContext(req=_req())
    ctx.env = env
    ctx.session_state = session_state
    ctx.history = history
    return ctx


def test_node_sets_early_response_on_greeting(monkeypatch):
    _patch_io(monkeypatch)
    ctx = _node_ctx(
        _env(page_context=_collection_ctx()), _state(_resolved(title="Optik")), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is not None
    assert "Optik" in out.early_response.content
    assert out.early_response.debug.pattern == "CTX:collection"


def test_node_no_page_event_leaves_early_response_none(monkeypatch):
    _patch_io(monkeypatch)
    ctx = _node_ctx(
        {"page_event": None, "page_context": _collection_ctx()},
        _state(_resolved()), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is None


def test_node_swallows_dispatcher_exception(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("greeting exploded")

    monkeypatch.setattr(g, "maybe_context_greeting", boom)
    ctx = _node_ctx(_env(page_context=_collection_ctx()), _state(_resolved()), ["prev"])
    out = asyncio.run(g.context_greeting(ctx, _SESSION))
    assert out.early_response is None  # a greeting bug must not break the turn


# ── C1-g2b: Begrüßung und Chips je Sprache ──────────────────────────────────
# Die Wahl fällt im Zug (`environment.locale`), nicht beim Laden — wie bei den
# Lotsen-Beschriftungen (C1-g2a). Zwei Fälle zählen: gepflegt → englisch, und
# nicht gepflegt → deutsch statt leer.

def _cfg_zweisprachig() -> dict:
    return {
        "enabled": True,
        "report_url": "https://wirlernenonline.de/melden?node={node_id}",
        "greetings": {"collection": "Du bist in der Sammlung „{title}“."},
        "greetings_en": {"collection": "You are in the “{title}” collection."},
        "pills": {"collection": [
            {"label": "Sammlung erkunden", "label_en": "Explore collection",
             "kind": "action", "action": "browse_collection"},
            {"label": "Passende Inhalte suchen", "label_en": "Find matching content",
             "kind": "text"},
            {"label": "Inhalt melden", "label_en": "Report content", "kind": "report"},
        ]},
        "curate_prompt": "",
    }


def test_greeting_and_pills_english_when_maintained(monkeypatch):
    _patch_io(monkeypatch)
    monkeypatch.setattr(g, "load_context_actions", _cfg_zweisprachig)
    env = _env(page_context=_collection_ctx())
    env["locale"] = "en"
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), env, _state(_resolved(title="Optics")), ["prev"]))
    assert resp.content == "You are in the “Optics” collection."
    joined = "\n".join(resp.quick_replies)
    assert "__action__|Explore collection|browse_collection|" in joined
    # Ein `text`-Chip wird beim Klick ALS NACHRICHT gesendet — bliebe er
    # deutsch, schickte ein englischer Nutzer deutschen Text an die
    # Klassifikation.
    assert "Find matching content" in resp.quick_replies
    assert "__guide__|Report content|" in joined


def test_german_locale_keeps_german_labels(monkeypatch):
    _patch_io(monkeypatch)
    monkeypatch.setattr(g, "load_context_actions", _cfg_zweisprachig)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state(_resolved(title="Optik")), ["prev"]))
    assert resp.content == "Du bist in der Sammlung „Optik“."
    assert "Passende Inhalte suchen" in resp.quick_replies


# ── Seitenkontext-Erweiterung: Suche, eigene Startseite, fremde Seite ───────
# Die drei neuen Arten sind KEINE WLO-Objekte — es gibt keinen Knoten, dessen
# Metadaten man auflösen könnte. Der Gegenstand der Meldung ist deshalb ein
# anderer: bei `search` der Suchbegriff aus der URL, bei `home`/`external` der
# Hostname. Genau daran hing die alte Sperre 3 („aufgelöste Metadaten"), und
# genau die musste verallgemeinert werden.

def test_suche_meldet_sich_mit_dem_suchbegriff(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "search", "search_query": "Photosynthese"}),
        _state(_resolved()), ["prev"]))
    assert "Photosynthese" in resp.content
    assert resp.debug.pattern == "CTX:search"
    assert resp.quick_replies


def test_eigene_startseite_nennt_den_host(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "home", "page_host": "wirlernenonline.de"}),
        _state(_resolved()), ["prev"]))
    assert "wirlernenonline.de" in resp.content
    assert resp.debug.pattern == "CTX:home"


def test_fremde_seite_nennt_den_host(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "external", "page_host": "beispiel.org"}),
        _state(_resolved()), ["prev"]))
    assert "beispiel.org" in resp.content
    assert resp.debug.pattern == "CTX:external"


def test_neue_arten_brauchen_keine_aufgeloesten_metadaten(monkeypatch):
    # Für eine fremde Seite gibt es nichts aufzulösen: `resolve_page_context`
    # liefert dort nichts oder eine `unresolved`-Hülle. Hinge die Meldung
    # weiter an Sperre 3, käme sie nie an.
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "external", "page_host": "beispiel.org"}),
        {"entities": {}}, ["prev"]))
    assert "beispiel.org" in resp.content


def test_fremde_seite_ohne_host_bleibt_stumm(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "external"}),
        _state(_resolved()), ["prev"]))
    assert resp.content == ""


def test_abschalter_schweigt_auch_bei_den_neuen_arten(monkeypatch):
    _patch_io(monkeypatch)
    monkeypatch.setattr(g, "load_context_actions", lambda: {"enabled": False})
    for ctx in (
        {"page_kind": "search", "search_query": "Optik"},
        {"page_kind": "home", "page_host": "wirlernenonline.de"},
        {"page_kind": "external", "page_host": "beispiel.org"},
    ):
        resp = asyncio.run(g.maybe_context_greeting(
            _SESSION, _req(), _env(page_context=ctx), _state(_resolved()), ["prev"]))
        assert resp.content == "", ctx["page_kind"]


# ── Aufgabe 5: auch beim ERSTEN Laden melden ────────────────────────────────
# Bisher war eine leere History die Abbruchbedingung — sie unterschied „der
# Nutzer redet schon" von „frische Sitzung". Beim Erstaufruf ist die leere
# History aber der Normalzustand, kein Zeichen für einen verirrten Ping. Das
# Widget sagt deshalb mit einem EIGENEN Ereignis, welcher Fall vorliegt;
# die History-Sperre gilt nur noch für den Fortsetzungs-Fall.

def test_erstaufruf_meldet_sich_trotz_leerer_history(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env("context_open_initial", _collection_ctx()),
        _state(_resolved(title="Optik")), []))
    assert "Optik" in resp.content
    assert resp.debug.pattern == "CTX:collection"


def test_fortsetzen_mit_leerer_history_bleibt_stumm(monkeypatch):
    # Unverändertes Bestandsverhalten: ohne das eigene Erstaufruf-Signal ist
    # eine leere History weiterhin der Abbruch.
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env("context_open", _collection_ctx()),
        _state(_resolved()), []))
    assert resp.content == ""


def test_erstaufruf_hebt_nur_die_history_sperre_auf(monkeypatch):
    """Die übrigen Sperren gelten weiter — sonst würde der Erstaufruf zur
    Hintertür, durch die eine ungeeignete Seite doch grüßt."""
    _patch_io(monkeypatch)

    # nicht begrüßbare Seitenart
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env("context_open_initial", {"page_kind": "subject"}),
        _state(_resolved()), []))
    assert resp.content == ""

    # kein Gegenstand (Metadaten nicht aufgelöst)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env("context_open_initial", _collection_ctx()),
        _state({"title": "T", "unresolved": True}), []))
    assert resp.content == ""


def test_erstaufruf_wird_ebenso_entdoppelt(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    env = _env("context_open_initial", _collection_ctx())
    r1 = asyncio.run(g.maybe_context_greeting(_SESSION, _req(), env, state, []))
    assert r1.content
    r2 = asyncio.run(g.maybe_context_greeting(_SESSION, _req(), env, state, []))
    assert r2.content == ""


def test_unbekanntes_ereignis_laeuft_weiter_den_normalfluss(monkeypatch):
    _patch_io(monkeypatch)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env("context_reopen", _collection_ctx()),
        _state(_resolved()), ["prev"]))
    assert resp is None


# ── Entdopplung der neuen Arten ─────────────────────────────────────────────
# `_current_context_signature` liest ausschliesslich Knoten-IDs und Slugs. Für
# Suche/Startseite/fremde Seite sind die allesamt leer — alle drei Arten
# bekämen denselben Entdopplungs-Schlüssel und blockierten sich gegenseitig
# nach der ersten Meldung. Der Gegenstand der Meldung muss deshalb mit hinein.

def test_zwei_verschiedene_suchen_melden_sich_beide(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    r1 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "search", "search_query": "Optik"}),
        state, ["prev"]))
    r2 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "search", "search_query": "Photosynthese"}),
        state, ["prev"]))
    assert "Optik" in r1.content
    assert "Photosynthese" in r2.content


def test_dieselbe_suche_meldet_sich_nur_einmal(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    ctx = {"page_kind": "search", "search_query": "Optik"}
    r1 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    r2 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=ctx), state, ["prev"]))
    assert r1.content and r2.content == ""


def test_verschiedene_fremde_seiten_melden_sich_beide(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    r1 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "external", "page_host": "a.de"}),
        state, ["prev"]))
    r2 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "external", "page_host": "b.de"}),
        state, ["prev"]))
    assert "a.de" in r1.content
    assert "b.de" in r2.content


def test_suche_und_fremde_seite_blockieren_einander_nicht(monkeypatch):
    _patch_io(monkeypatch)
    state = _state(_resolved())
    r1 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "search", "search_query": "Optik"}),
        state, ["prev"]))
    r2 = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context={"page_kind": "external", "page_host": "a.de"}),
        state, ["prev"]))
    assert r1.content and r2.content


# ── Aufgabe 6: Dublettenprüfung vor dem Erschliessungs-Angebot ──────────────
# M20 verlangt sie vor JEDER Neuanlage; ein zweiter Datensatz zur selben
# Adresse ist die häufigste vermeidbare Verschmutzung des Bestands. Sie läuft
# hier, damit das Angebot gar nicht erst erscheint, wenn es die Seite schon
# gibt — statt sich darauf zu verlassen, dass das Modell M20 befolgt.
#
# ZWEI Zweige, nicht drei: der Negativ-Text behauptet nichts über Dubletten
# („Ich kann mir die Seite ansehen und sie vorschlagen"), also ist „nichts
# gefunden" dieselbe ehrliche Aussage wie „konnte nicht fragen". Ein eigener
# Fehlertext wäre eine Unterscheidung ohne Unterschied.

def _external_ctx(url: str = "https://beispiel.org/artikel") -> dict:
    return {"page_kind": "external", "page_host": "beispiel.org", "page_url": url}


def _patch_lookup(monkeypatch, result=None, boom: bool = False) -> list:
    seen: list = []

    async def fake(url: str, title: str):
        seen.append((url, title))
        if boom:
            raise RuntimeError("mcp down")
        return result

    monkeypatch.setattr(g, "find_existing_by_url", fake)
    return seen


def test_bekannte_seite_wird_als_bekannt_gemeldet(monkeypatch):
    _patch_io(monkeypatch)
    _patch_lookup(monkeypatch, {"node_id": "N7", "title": "Der Artikel", "matched_on": "url"})
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_external_ctx()), _state(_resolved()), ["prev"]))
    assert "Der Artikel" in resp.content
    assert resp.debug.pattern == "CTX:external:bekannt"


def test_bekannte_seite_bietet_das_aufnehmen_nicht_mehr_an(monkeypatch):
    _patch_io(monkeypatch)
    _patch_lookup(monkeypatch, {"node_id": "N7", "title": "Der Artikel", "matched_on": "url"})
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_external_ctx()), _state(_resolved()), ["prev"]))
    joined = "\n".join(resp.quick_replies)
    assert "Nimm diese Seite in WLO auf" not in joined
    assert "N7" in joined  # stattdessen der Weg zum vorhandenen Eintrag


def test_unbekannte_seite_bietet_das_aufnehmen_an(monkeypatch):
    _patch_io(monkeypatch)
    _patch_lookup(monkeypatch, None)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_external_ctx()), _state(_resolved()), ["prev"]))
    assert "beispiel.org" in resp.content
    assert "Nimm diese Seite in WLO auf" in "\n".join(resp.quick_replies)


def test_gescheiterte_pruefung_behauptet_keine_dublette(monkeypatch):
    _patch_io(monkeypatch)
    _patch_lookup(monkeypatch, boom=True)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_external_ctx()), _state(_resolved()), ["prev"]))
    assert "beispiel.org" in resp.content     # ehrlicher Normaltext, kein Fehlertext
    assert "Nimm diese Seite in WLO auf" in "\n".join(resp.quick_replies)


def test_ohne_adresse_wird_gar_nicht_geprueft(monkeypatch):
    # Solange das Widget die Adresse nicht mitschickt, unterbleibt der Aufruf —
    # eine Prüfung auf den blossen Hostnamen fände die falsche Seite.
    _patch_io(monkeypatch)
    seen = _patch_lookup(monkeypatch, None)
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "external", "page_host": "beispiel.org"}),
        _state(_resolved()), ["prev"]))
    assert seen == []
    assert "beispiel.org" in resp.content


def test_andere_seitenarten_loesen_keine_pruefung_aus(monkeypatch):
    _patch_io(monkeypatch)
    seen = _patch_lookup(monkeypatch, None)
    asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), _env(page_context=_collection_ctx()),
        _state(_resolved(title="Optik")), ["prev"]))
    asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(),
        _env(page_context={"page_kind": "home", "page_host": "wirlernenonline.de"}),
        _state(_resolved()), ["prev"]))
    assert seen == []


def test_die_beiden_backend_listen_nennen_dieselben_arten():
    """Die begrüßbaren Arten stehen an ZWEI Stellen im Backend: der Knoten
    entscheidet, ob er redet, der Loader entscheidet, ob es überhaupt einen Text
    dazu gibt. Fällt eine Änderung an einer Stelle aus, passiert still gar
    nichts — der Loader würfe den Seed-Text weg, bevor der Knoten ihn sieht."""
    from boerdi.services.config_loader.widget import _CONTEXT_ACTIONS_PAGE_KINDS

    assert set(g._GREETABLE_KINDS) == set(_CONTEXT_ACTIONS_PAGE_KINDS)


def test_das_widget_gate_erreicht_jede_begruessbare_art():
    """Die dritte Stelle, und die einzige in einer anderen Sprache: schickt das
    Widget für eine Seitenart gar keinen Ping, kommt das Backend nie zu Wort —
    egal wie gepflegt der Text ist. Das Widget führt seine Abdeckung deshalb als
    benannte Liste; hier wird sie gegengelesen (Muster aus
    `test_widget_router.py`: Datei lesen statt hoffen).

    Warum eine eigene Liste und nicht das Gate selbst: `home`/`external` setzt
    der Erkenner nie — sie kommen dort als `other` an. Das Gate kann sie also
    gar nicht namentlich abfragen; welche Backend-Arten es *erreicht*, ist eine
    Aussage über seine Absicht und steht deshalb daneben.
    """
    import re
    from pathlib import Path

    gate = (
        Path(__file__).resolve().parents[2]
        / "frontend/projects/ui/src/shell/lifecycle.ts"
    )
    if not gate.exists():  # Backend-Image ohne Frontend-Quellen
        pytest.skip(f"Widget-Quelle nicht da: {gate}")
    block = re.search(
        r"PING_COVERS_BACKEND_KINDS\s*=\s*\[(.*?)\]", gate.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert block, "PING_COVERS_BACKEND_KINDS im Widget nicht gefunden"
    abgedeckt = set(re.findall(r"'([a-z_]+)'", block.group(1)))
    assert abgedeckt, "Liste im Widget ist leer — dann pingt nichts"
    assert set(g._GREETABLE_KINDS) == abgedeckt


def test_english_locale_without_translation_falls_back_to_german(monkeypatch):
    # Ohne gepflegte Fassung greifen die deutschen Loader-Vorgaben. Ein leerer
    # Gruß wäre hier fatal: die Begrüßung ist die Abbruchbedingung des Knotens
    # (`if not greeting.strip()` → leere Antwort), der Chip-Satz fiele mit weg.
    _patch_io(monkeypatch)
    env = _env(page_context=_collection_ctx())
    env["locale"] = "en"
    resp = asyncio.run(g.maybe_context_greeting(
        _SESSION, _req(), env, _state(_resolved(title="Optik")), ["prev"]))
    assert "Optik" in resp.content
    assert resp.quick_replies
