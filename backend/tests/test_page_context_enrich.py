"""Tests for the page-context enrichment node (P4-2 / R6).

The node injects the page-context IDs the widget supplies into
``session_state['entities']`` and best-effort resolves the host page's metadata via
MCP (populating the ``_page_metadata`` cache that ``context_greeting`` and — later —
``respond``'s prompt read). It runs AFTER the tour early-exit (so tour ticks skip the
MCP latency; ALT ``chat_turn_setup:90`` returns before the resolve at :92) and never
short-circuits. ``resolve_page_context`` is patched on THIS module; the injection
runs for real.
"""

from __future__ import annotations

import asyncio
import time

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.graph.nodes import page_context_enrich as m
from boerdi.graph.state import TurnContext


def _ctx(page_context: dict | None = None) -> TurnContext:
    ctx = TurnContext(req=ChatRequest(session_id="s1", message="hi"))
    ctx.env = Environment(page_context=page_context or {}).model_dump()
    ctx.session_state = {"entities": {}}
    return ctx


def _patch_resolve(monkeypatch) -> list:
    calls: list = []

    async def fake_resolve(page_context, session_state, **kw):
        calls.append((page_context, session_state))
        return None

    monkeypatch.setattr(m, "resolve_page_context", fake_resolve)
    return calls


def test_injects_present_page_context_ids_into_entities(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1", "collection_id": "C1", "subject_slug": "mathe"})
    out = asyncio.run(m.page_context_enrich(ctx))
    ents = out.session_state["entities"]
    assert ents["node_id"] == "N1"
    assert ents["collection_id"] == "C1"
    assert ents["subject_slug"] == "mathe"


def test_skips_absent_and_falsy_keys(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1", "collection_id": ""})
    out = asyncio.run(m.page_context_enrich(ctx))
    # empty collection_id skipped; absent keys skipped
    assert out.session_state["entities"] == {"node_id": "N1"}


def test_calls_resolve_with_page_ctx_and_session_state(monkeypatch):
    calls = _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1"})
    asyncio.run(m.page_context_enrich(ctx))
    assert len(calls) == 1
    page_ctx, session_state = calls[0]
    assert page_ctx == {"node_id": "N1"}
    assert session_state is ctx.session_state  # resolve caches on the live session_state


def test_resolve_failure_is_swallowed_and_ids_still_injected(monkeypatch):
    async def boom(page_context, session_state, **kw):
        raise RuntimeError("mcp down")

    monkeypatch.setattr(m, "resolve_page_context", boom)
    ctx = _ctx({"node_id": "N1"})
    out = asyncio.run(m.page_context_enrich(ctx))  # must not raise
    assert out.session_state["entities"]["node_id"] == "N1"


def test_never_sets_early_response(monkeypatch):
    _patch_resolve(monkeypatch)
    ctx = _ctx({"node_id": "N1"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.early_response is None


# ── Host-Einordnung (Seitenkontext-Erweiterung, Aufgabe 3) ──────────
# Der Erkenner im Widget kennt nur Pfad und Query; alles, was er nicht
# einordnen kann, landet auf ``other``. Erst der Hostname trennt dort die
# eigene Startseite von einer fremden Seite — und diese Trennung entscheidet
# später, ob der Bot die Erschliessung anbietet. Sie passiert hier, weil die
# Liste der eigenen Hosts eine Betriebs-Tatsache ist, die die Redaktion pflegt.

_OWN = {"own_hosts": ["wirlernenonline.de", "repository.staging.openeduhub.net"]}


def _patch_cfg(monkeypatch, cfg: dict | None = None) -> None:
    monkeypatch.setattr(m, "load_context_actions", lambda: cfg if cfg is not None else _OWN)


def test_eigener_host_macht_aus_other_home(monkeypatch):
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "other", "page_host": "wirlernenonline.de"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "home"


def test_fremder_host_macht_aus_other_external(monkeypatch):
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "other", "page_host": "example.org"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "external"


def test_fehlende_seitenart_wird_wie_other_behandelt(monkeypatch):
    # Ältere Widget-Bundles schicken gar kein page_kind — sie dürfen die
    # Einordnung trotzdem bekommen, sonst wirkt das Feature erst nach Deploy.
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_host": "example.org"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "external"


def test_erkannte_sammlung_bleibt_sammlung_trotz_eigenem_host(monkeypatch):
    # DIE Regression: die echte Staging-Adresse der Sammlung "Geometrische Optik"
    # liegt auf einem EIGENEN Host und trägt page_kind='collection'. Würde die
    # Host-Einordnung das überschreiben, wären Metadaten und Kontext-Chips weg.
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({
        "page_kind": "collection",
        "collection_id": "f35c17d1-a29e-4b26-9d22-802682fad43d",
        "page_host": "repository.staging.openeduhub.net",
    })
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "collection"


def test_ohne_host_bleibt_die_seitenart_unveraendert(monkeypatch):
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "other"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "other"


def test_der_resolver_sieht_die_eingeordnete_seitenart(monkeypatch):
    # resolve_page_context liest page_kind (Volltext nur bei 'content'), und die
    # Meldung liest es danach — beide müssen denselben Wert sehen.
    calls = _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "other", "page_host": "example.org"})
    asyncio.run(m.page_context_enrich(ctx))
    assert calls[0][0]["page_kind"] == "external"


def test_kaputte_config_bricht_den_zug_nicht(monkeypatch):
    _patch_resolve(monkeypatch)

    def boom():
        raise RuntimeError("config store down")

    monkeypatch.setattr(m, "load_context_actions", boom)
    ctx = _ctx({"page_kind": "other", "page_host": "example.org", "node_id": "N1"})
    out = asyncio.run(m.page_context_enrich(ctx))  # must not raise
    assert out.env["page_context"]["page_kind"] == "other"  # unverändert, nicht geraten
    assert out.session_state["entities"]["node_id"] == "N1"


# ── Bestandsfakten für BEIDE Engines (Nutzer-Vorgabe 2026-08-14) ───────────
#
# Dieser Knoten läuft VOR der Begrüßung und VOR ``respond`` (Graph-Reihenfolge
# ``setup → tour → page_context_enrich → context_greeting → … → respond``).
# Genau ein Abruf je Zug versorgt damit alle drei Verbraucher: Begrüßung,
# Muster-Engine und Agent-Schleife. Zwei Abrufe wären zwei Wartezeiten.


def _mit_cache(monkeypatch, meta: dict) -> list:
    """Resolver, der einen Metadaten-Cache hinterlässt — wie der echte."""
    calls: list = []

    async def fake_resolve(page_context, session_state, **kw):
        calls.append((page_context, session_state))
        session_state.setdefault("entities", {})["_page_metadata"] = meta
        return meta

    monkeypatch.setattr(m, "resolve_page_context", fake_resolve)
    return calls


def _fakten_spion(monkeypatch, fakten: dict | Exception) -> list:
    gerufen: list = []

    async def fake_collect(collection_id):
        gerufen.append(collection_id)
        if isinstance(fakten, Exception):
            raise fakten
        return fakten

    monkeypatch.setattr(m, "collect_context_facts", fake_collect)
    return gerufen


def test_bestandsfakten_landen_am_seiten_cache(monkeypatch):
    meta = {"title": "Geometrische Optik"}
    _mit_cache(monkeypatch, meta)
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {"materials": 35, "skills": 28})
    ctx = _ctx({"page_kind": "collection", "collection_id": "C1"})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert gerufen == ["C1"]
    assert out.session_state["entities"]["_page_metadata"]["context_facts"] == {
        "materials": 35, "skills": 28}


def test_eine_inhaltsseite_fragt_nicht_nach_bestand(monkeypatch):
    # Ein Einzelinhalt enthält keine Materialien und führt keine Freigabeliste
    # — ein Abruf dafür wäre ein Rundlauf ins Leere, und er kostet Zeit.
    _mit_cache(monkeypatch, {"title": "Ein Video"})
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {"materials": 1})
    ctx = _ctx({"page_kind": "content", "node_id": "N1"})
    asyncio.run(m.page_context_enrich(ctx))
    assert gerufen == []


def test_bereits_vorhandene_fakten_werden_nicht_neu_geholt(monkeypatch):
    # Der Cache überlebt den Zug (jsonb-Entities). Ein zweiter Abruf je Zug
    # wäre reine Wartezeit für dieselbe Antwort.
    meta = {"title": "T", "context_facts": {"materials": 35}}
    _mit_cache(monkeypatch, meta)
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {"materials": 99})
    ctx = _ctx({"page_kind": "collection", "collection_id": "C1"})
    asyncio.run(m.page_context_enrich(ctx))
    assert gerufen == []
    assert meta["context_facts"] == {"materials": 35}


def test_ein_ausfall_der_fakten_kostet_den_zug_nicht(monkeypatch):
    meta = {"title": "T"}
    _mit_cache(monkeypatch, meta)
    _patch_cfg(monkeypatch)
    _fakten_spion(monkeypatch, RuntimeError("MCP weg"))
    ctx = _ctx({"page_kind": "collection", "collection_id": "C1"})
    out = asyncio.run(m.page_context_enrich(ctx))  # darf nicht werfen
    assert "context_facts" not in meta
    assert out.early_response is None


def test_ein_ergebnisloser_abruf_wird_nicht_bei_jedem_zug_wiederholt(monkeypatch):
    """Review-Befund 2026-08-14: ohne Vermerk lief der Abruf JEDEN Zug erneut.

    Der Fall ist real — eine Sammlung, deren Statistik 404 liefert und die keine
    Freigabeliste führt, ergibt zweimal nichts. Ohne Gedächtnis kostet das
    dauerhaft zwei MCP-Rundläufe je Zug, im Hängefall bis zum vollen Deckel.
    Dasselbe Modul löst das nebenan längst so: ``_UNRESOLVED_TTL_SECONDS``.
    """
    meta = {"title": "T"}
    _mit_cache(monkeypatch, meta)
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {})
    ctx = _ctx({"page_kind": "collection", "collection_id": "C1"})
    asyncio.run(m.page_context_enrich(ctx))
    asyncio.run(m.page_context_enrich(ctx))      # zweiter Zug, gleiche Sitzung
    assert gerufen == ["C1"], "der leere Abruf wurde wiederholt"


def test_nach_der_ruhezeit_wird_es_erneut_versucht(monkeypatch):
    """Der Vermerk ist eine Pause, keine Aufgabe: ein vorübergehend stummer MCP
    darf die Sammlung nicht für die ganze Sitzung ohne Bestand lassen."""
    meta = {"title": "T", "context_facts": {"_leer_seit": time.time() - 10_000}}
    _mit_cache(monkeypatch, meta)
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {"materials": 35})
    ctx = _ctx({"page_kind": "collection", "collection_id": "C1"})
    asyncio.run(m.page_context_enrich(ctx))
    assert gerufen == ["C1"]
    assert meta["context_facts"] == {"materials": 35}


# ── EK2: Erschließungs-Situation (editorial-desk) ───────────────────────────
# Die URL benennt die SITUATION (Prüftisch mit konkretem Knoten) und darf die
# positive ``content``-Einstufung des Erkenners übersteuern — anders als der
# Hostname, der nur Unentschiedenes klärt. Serverseitig, damit jeder
# Einbett-Weg (Repo-Rahmen, Plugin, eigenes Widget) den Fix ohne Host-Änderung
# bekommt.

_DESK_URL = (
    "https://repository.staging.openeduhub.net/edu-sharing/components/"
    "editorial-desk?mode=audit&viewType=Single&mdsEdit=true&useAi=true"
    "&nodeId=0d4c07cf-1919-436b-8c07-cf1919f36bde"
)


def test_pruefktisch_url_macht_aus_content_editorial(monkeypatch):
    """EK2 (2026-08-20, Live-Befund Staging): die editorial-desk-URL fiel in den
    generischen ``?node``-Zweig (content) — und content begrüßt nur mit
    aufgelöstem Titel, den es anonym auf dem Prüftisch nie gibt (403)."""
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({
        "page_kind": "content",
        "node_id": "0d4c07cf-1919-436b-8c07-cf1919f36bde",
        "page_host": "repository.staging.openeduhub.net",
        "page_url": _DESK_URL,
    })
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "editorial"


def test_pruefktisch_uebersicht_ohne_knoten_bleibt_unangetastet(monkeypatch):
    # Ohne node_id ist es die Prüftisch-ÜBERSICHT, kein Einzelinhalt in
    # Erschließung — dort greift weiter die Host-Einordnung (eigene Seite).
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({
        "page_kind": "other",
        "page_host": "repository.staging.openeduhub.net",
        "page_url": ("https://repository.staging.openeduhub.net/edu-sharing/"
                     "components/editorial-desk?mode=audit"),
    })
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "home"


def test_renderseite_ausserhalb_des_pruefktischs_bleibt_content(monkeypatch):
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({
        "page_kind": "content",
        "node_id": "n-1",
        "page_host": "repository.staging.openeduhub.net",
        "page_url": ("https://repository.staging.openeduhub.net/edu-sharing/"
                     "components/render/n-1"),
    })
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "content"


def test_editorial_desk_nur_im_pfad_nicht_in_der_query(monkeypatch):
    # Ein ?next=…editorial-desk… in der Query (Login-Redirect) ist KEIN
    # Prüftisch — nur der Pfad zählt.
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({
        "page_kind": "content",
        "node_id": "n-1",
        "page_host": "repository.staging.openeduhub.net",
        "page_url": ("https://repository.staging.openeduhub.net/edu-sharing/"
                     "components/render/n-1?next=%2Fcomponents%2Feditorial-desk"),
    })
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "content"


def test_feindliche_nicht_string_werte_brechen_den_zug_nicht(monkeypatch):
    """Review-Befund EK (2026-08-20): ``environment.page_context`` ist
    ``dict[str, Any]`` — ein Client kann ``node_id``/``page_url`` als Zahl
    senden. ``(123 or "").strip()`` bzw. ``urlsplit(123)`` würfen und der
    Knoten bräche den Zug — gegen den Vertrag des Moduls (Ausfälle kosten
    nie den Zug, siehe Resolver- und Config-Tests oben)."""
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "content", "node_id": 123, "page_url": 456})
    out = asyncio.run(m.page_context_enrich(ctx))  # darf nicht werfen
    assert out.env["page_context"]["page_kind"] == "content"


# ── EK4: Textfelder normalisieren (Review-Befund A) ─────────────────────────
# ``page_context`` ist im Vertrag ``dict[str, Any]`` — Freiform, damit Gastgeber
# eigene Felder mitgeben können. Genau das macht ``(wert or "").strip()`` zur
# Falle: jeder TRUTHY Nicht-String wirft. Falsy Werte (``0``, ``""``, ``None``)
# waren nie betroffen, und das ist der Grund, warum es niemandem auffiel — ein
# numerisches TypeScript-Enum (``enum PageKind { Content, Collection }``) läuft
# auf Inhaltsseiten (0) sauber und bricht auf Sammlungsseiten (1).


def test_zahl_als_seitenart_bricht_den_zug_nicht(monkeypatch):
    """Der TypeScript-Enum-Fall. Die Zahl wird zur Zeichenkette, nicht zu einer
    geratenen Seitenart: ``"1"`` ist keine bekannte Art, der Bot bietet also
    keine Kontext-Knöpfe an — aber der Zug lebt, statt mit AttributeError in
    die Fehler-Blase zu laufen (und zwar bei JEDEM Zug dieser Einbettung)."""
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": 1, "page_host": "example.org"})
    out = asyncio.run(m.page_context_enrich(ctx))  # darf nicht werfen
    assert out.env["page_context"]["page_kind"] == "1"


def test_zahl_als_host_bricht_die_einordnung_nicht(monkeypatch):
    # Nach der Normalisierung läuft die Host-Einordnung ganz normal durch.
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "other", "page_host": 12345})
    out = asyncio.run(m.page_context_enrich(ctx))
    assert out.env["page_context"]["page_kind"] == "external"


def test_zahl_als_sammlungs_id_erreicht_den_bestandsabruf(monkeypatch):
    """Ein Gastgeber-CMS mit numerischen IDs. Hier ist ``str()`` nicht nur
    rettend, sondern sachlich richtig: aus ``4711`` wird die brauchbare
    Kennung ``"4711"``, und der Bestandsabruf läuft damit weiter."""
    _mit_cache(monkeypatch, {"title": "Eine Sammlung"})
    _patch_cfg(monkeypatch)
    gerufen = _fakten_spion(monkeypatch, {"materials": 3})
    ctx = _ctx({"page_kind": "collection", "collection_id": 4711})
    asyncio.run(m.page_context_enrich(ctx))
    assert gerufen == ["4711"]


def test_leere_und_fehlende_werte_bleiben_unangetastet(monkeypatch):
    """``None`` darf NICHT zu ``"None"`` werden — sonst stünde der Titel
    „None" im Prompt. Falsy heisst „nicht gesetzt" und bleibt es."""
    _patch_resolve(monkeypatch)
    _patch_cfg(monkeypatch)
    ctx = _ctx({"page_kind": "content", "document_title": None, "node_id": ""})
    out = asyncio.run(m.page_context_enrich(ctx))
    pc = out.env["page_context"]
    assert pc["document_title"] is None
    assert pc["node_id"] == ""
