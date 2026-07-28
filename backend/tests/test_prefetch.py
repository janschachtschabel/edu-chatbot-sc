"""services.prefetch — Spekulativer MCP-Prefetch (Port ALT ``chat_prefetch``).

Port des ``_launch_speculative_prefetch``-Charakterisierungsnetzes aus ALT
``test_chat_prefetch.py`` auf ``run_speculative_prefetch``. Pinnt das IST-Verhalten
mit Boundary-Mocks: ``call_mcp_tool`` + ``_topic_pages_with_warmup`` sind
Top-Imports in ``services/prefetch.py`` (bare names im Body) → am Modul patchen
(Fixture ``spec_mcp``). ``_retrieve_task_exception`` läuft ECHT als done_callback
mit (räumt die Fake-Tasks beim Drain ab).

Das ``_fallback_inline_search``-Netz (ALT ``test_chat_prefetch``) gehört zur
Inline-Safety-Net-Slice und wird dort mitportiert.

NICHT gepinnt (bewusst, statt rigged): der ``req.message[:120]``-Query-Fallback
(unerreichbar, solange das Signal-Gate greift) und die done_callback-Registrierung
(nur indirekt: der echte Callback läuft beim Abräumen fehlerfrei mit).
"""

from __future__ import annotations

import asyncio

import pytest

import boerdi.services.prefetch as prefetch
from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.services.prefetch import run_speculative_prefetch

# Start-Bedingung (ALLE müssen gelten): risk != "high", Intent in {I03, I04},
# Anchor-Entity (thema/topic/query/schlagwort ODER fach), Pattern-Hint != M16,
# NICHT (I04 + thema). Greift sie nicht → Default-Tupel, kein MCP-Start.
_SPEC_DEFAULTS = (None, None, None, "", [], False, [])


@pytest.fixture
def spec_mcp(monkeypatch):
    """Boundary-Fakes für ``run_speculative_prefetch``.

    ``call_mcp_tool`` und ``_topic_pages_with_warmup`` sind Top-Imports in
    ``services/prefetch.py`` (bare names im Body) → Patch auf ``prefetch``.
    ``calls`` protokolliert ``("call", tool, args)`` bzw. ``("warmup", query,
    args)`` in Task-Scheduling-Reihenfolge (= Start-Reihenfolge, da die Fakes
    keine Awaits vor dem Protokollieren haben).
    """
    calls: list[tuple] = []

    async def _call(tool, args):
        calls.append(("call", tool, dict(args)))
        return "RAW"

    async def _warmup(query, args):
        calls.append(("warmup", query, dict(args)))
        return "RAW"

    monkeypatch.setattr(prefetch, "call_mcp_tool", _call)
    monkeypatch.setattr(prefetch, "_topic_pages_with_warmup", _warmup)
    return calls


async def _drive_spec(req, classification, safety):
    """Funktion treiben und die gestarteten Fake-Tasks abräumen (sonst warnt
    asyncio.run beim Loop-Close über pending Tasks)."""
    out = await run_speculative_prefetch(req, classification, safety)
    pending = ([out[0]] if out[0] is not None else []) + [t for _, t in out[4]]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return out


def _launch(message="Material zu Brüchen", intent="I03", entities=None,
            pattern_hint=None, tool_hint=None, risk="low"):
    req = ChatRequest(session_id="s", message=message)
    classification = ClassificationResult(
        intent_id=intent, entities=entities or {},
        pattern_id_hint=pattern_hint, tool_id_hint=tool_hint,
    )
    return asyncio.run(_drive_spec(req, classification,
                                   SafetyDecision(risk_level=risk)))


# ── Start-Bedingung: Skip-Zweige (Default-Tupel, kein MCP-Call) ──────────

def test_spec_skips_on_high_risk(spec_mcp):
    assert _launch(intent="I03", entities={"thema": "Brüche"},
                   risk="high") == _SPEC_DEFAULTS
    assert spec_mcp == []


def test_spec_skips_on_non_search_intent(spec_mcp):
    assert _launch(intent="I01", entities={"thema": "Brüche"}) == _SPEC_DEFAULTS
    assert spec_mcp == []


def test_spec_skips_without_search_anchor(spec_mcp):
    # medientyp allein ist KEIN Anchor (kein thema/topic/query/schlagwort/fach)
    # → kein Prefetch, M03 (Geführte Klärung) übernimmt.
    assert _launch(intent="I03", entities={"medientyp": "Video"}) == _SPEC_DEFAULTS
    assert spec_mcp == []


def test_spec_skips_on_m16_hint(spec_mcp):
    # M16 macht seine EIGENE gezielte Auflösung → Spekulativ-Suche wäre
    # verworfene MCP-Arbeit.
    assert _launch(intent="I03", entities={"thema": "Brüche"},
                   pattern_hint="M16") == _SPEC_DEFAULTS
    assert spec_mcp == []


def test_spec_skips_i04_with_thema(spec_mcp):
    # B2: I04+thema landet im LP-Fast-Path (eigene MCP-Calls) → skip.
    # I04 mit NUR fach (weicher Anchor) startet dagegen (s. search_all-Test).
    assert _launch(intent="I04", entities={"thema": "Brüche"}) == _SPEC_DEFAULTS
    assert spec_mcp == []


# ── Primary-Tool-Wahl + Extras ───────────────────────────────────────────

def test_spec_i03_topic_first_warmup_primary_with_staircase_extras(spec_mcp):
    # I03 → _topic_first → Primary search_wlo_topic_pages via Warmup-Wrapper;
    # Extras = Staircase [collections, content], je maxResults=5, dedupliziert
    # (der Intent-Zweig hängt content ein zweites Mal an → genau 1× gestartet).
    out = _launch(intent="I03", entities={"thema": "Brüche"})
    spec_task, name, args, query, extras, is_all, all_extras = out
    assert isinstance(spec_task, asyncio.Task)
    assert name == "search_wlo_topic_pages"
    assert args == {"query": "Brüche", "maxResults": 10}
    assert query == "Brüche"
    assert [n for n, _t in extras] == ["search_wlo_collections", "search_wlo_content"]
    assert all(isinstance(t, asyncio.Task) for _n, t in extras)
    assert is_all is False
    assert all_extras == []
    assert spec_mcp == [
        ("warmup", "Brüche", {"query": "Brüche", "maxResults": 10}),
        ("call", "search_wlo_collections", {"query": "Brüche", "maxResults": 5}),
        ("call", "search_wlo_content", {"query": "Brüche", "maxResults": 5}),
    ]


def test_spec_i04_generic_search_becomes_search_wlo_all(spec_mcp):
    # I04 ohne thema, mit fach (weicher Anchor): Heuristik wählt collections,
    # O1 kombiniert zu EINEM search_wlo_all — keine Extras (deckt alle Töpfe ab).
    # maxContent=8: Collections-Primary wird bei I03/I04 auf 5 gekappt,
    # search_wlo_all hebt via max(_primary_max, 8) wieder auf 8 an.
    out = _launch(message="Ich brauche Material für den Unterricht",
                  intent="I04",
                  entities={"fach": "Mathematik", "stufe": "Sekundarstufe I"})
    spec_task, name, args, query, extras, is_all, all_extras = out
    assert isinstance(spec_task, asyncio.Task)
    assert name == "search_wlo_all"
    assert is_all is True
    assert query == "Mathematik"
    assert args == {
        "query": "Mathematik", "maxContent": 8, "maxCollections": 5,
        "includeFacets": True, "discipline": "Mathematik",
        "educationalContext": "Sekundarstufe I",
    }
    assert extras == []
    assert all_extras == []
    assert spec_mcp == [("call", "search_wlo_all", args)]


def test_spec_llm_tool_hint_topic_pages_wins_and_keeps_warmup(spec_mcp):
    # LLM-Hint search_wlo_topic_pages überstimmt die Heuristik (die für
    # I04+fach collections→search_all gewählt hätte) und blockt search_all.
    out = _launch(intent="I04", entities={"fach": "Chemie"},
                  tool_hint="search_wlo_topic_pages")
    _task, name, args, _query, extras, is_all, _ = out
    assert name == "search_wlo_topic_pages"
    assert is_all is False
    assert args == {"query": "Chemie", "maxResults": 10, "discipline": "Chemie"}
    # NOTE: pinnt IST-Verhalten — ohne _topic_first (kein I03/M06/"themenseite")
    # gibt es KEINE Collections-Extra zum Topic-Primary; das vom Intent-Zweig
    # angehängte topic_pages-Extra fällt dem Primary-Dedup zum Opfer → nur
    # search_wlo_content bleibt als Extra.
    assert [n for n, _t in extras] == ["search_wlo_content"]
    assert spec_mcp == [
        ("warmup", "Chemie", args),
        ("call", "search_wlo_content",
         {"query": "Chemie", "maxResults": 5, "discipline": "Chemie"}),
    ]


def test_spec_llm_tool_hint_content_collapses_into_search_all(spec_mcp):
    # NOTE: pinnt IST-Verhalten — der O1-Umbau überschreibt den expliziten
    # LLM-Hint search_wlo_content (ohne Medientyp/"themenseite") mit dem
    # kombinierten search_wlo_all; vom Hint überlebt nur _primary_max=10
    # (Content-Primary ungekappt) → maxContent=10 statt 8.
    out = _launch(intent="I03", entities={"thema": "Brüche"},
                  tool_hint="search_wlo_content")
    _task, name, args, _query, extras, is_all, _ = out
    assert name == "search_wlo_all"
    assert is_all is True
    assert args == {"query": "Brüche", "maxContent": 10, "maxCollections": 5,
                    "includeFacets": True}
    assert extras == []
    assert spec_mcp == [("call", "search_wlo_all", args)]


def test_spec_medientyp_forces_single_filtered_content_call(spec_mcp):
    # Medientyp-Fokus überschreibt _topic_first (I03) UND den LLM-Hint:
    # genau EIN gefiltertes search_wlo_content, kein search_all, keine Extras.
    out = _launch(intent="I03",
                  entities={"thema": "Photosynthese", "medientyp": "Video",
                            "fach": "Biologie", "stufe": "Sek I"},
                  tool_hint="search_wlo_collections")
    _task, name, args, _query, extras, is_all, _ = out
    assert name == "search_wlo_content"
    assert is_all is False
    assert args == {"query": "Photosynthese", "maxResults": 10,
                    "learningResourceType": "Video",
                    "discipline": "Biologie", "educationalContext": "Sek I"}
    assert extras == []
    assert spec_mcp == [("call", "search_wlo_content", args)]


def test_spec_wants_topic_with_collections_hint_stays_direct_and_capped(spec_mcp):
    # "themenseite" im Text blockiert search_all; Collections-Primary wird
    # wegen _wants_topic auf maxResults=5 gekappt und läuft OHNE Warmup direkt.
    out = _launch(message="Zeig mir eine Themenseite dazu", intent="I04",
                  entities={"fach": "Chemie", "stufe": "Sek II"},
                  tool_hint="search_wlo_collections")
    _task, name, args, _query, extras, is_all, _ = out
    assert name == "search_wlo_collections"
    assert is_all is False
    assert args == {"query": "Chemie", "maxResults": 5,
                    "discipline": "Chemie", "educationalContext": "Sek II"}
    # NOTE: pinnt IST-Verhalten — trotz "Themenseite" im Text wird KEIN
    # topic_pages-Extra gefeuert: _wants_topic setzt _topic_first, dessen
    # Staircase-Zweig [collections, content] annimmt, der Primary sei schon
    # topic_pages; der Hint-Primary collections wird weggededupt → nur content.
    assert [n for n, _t in extras] == ["search_wlo_content"]
    assert spec_mcp == [
        ("call", "search_wlo_collections", args),
        ("call", "search_wlo_content",
         {"query": "Chemie", "maxResults": 5, "discipline": "Chemie",
          "educationalContext": "Sek II"}),
    ]


def test_spec_m06_pattern_hint_triggers_topic_first(spec_mcp):
    # Pattern-Hint M06 (ohne Tool-Hint) → _topic_first → Warmup-Primary
    # topic_pages + Staircase-Extras, auch bei I04.
    out = _launch(intent="I04", entities={"fach": "Physik"}, pattern_hint="M06")
    _task, name, _args, _query, extras, is_all, _ = out
    assert name == "search_wlo_topic_pages"
    assert is_all is False
    assert [n for n, _t in extras] == ["search_wlo_collections", "search_wlo_content"]
    assert spec_mcp[0] == ("warmup", "Physik",
                           {"query": "Physik", "maxResults": 10,
                            "discipline": "Physik"})


# ── Query-Bildung ────────────────────────────────────────────────────────

def test_spec_query_priority_and_truncation(spec_mcp):
    # NOTE: pinnt IST-Verhalten — _spec_query_from_classification prüft fach
    # VOR topic/query/schlagwort (anders als das Signal-Gate, das fach nur als
    # weichsten Fallback nimmt) → fach gewinnt gegen topic.
    out = _launch(intent="I03", entities={"topic": "Optik", "fach": "Physik"})
    assert out[3] == "Physik"
    out = _launch(intent="I03", entities={"thema": "x" * 200})
    assert out[3] == "x" * 120     # Anchor wird auf 120 Zeichen gekappt


# ── Degradation ──────────────────────────────────────────────────────────

def test_spec_spawn_exception_degrades_to_no_task(spec_mcp, monkeypatch):
    # Boundary wirft synchron beim Spawn (z.B. kaputter Tool-Aufbau) →
    # except-Zweig: kein Task, KEINE Exception nach außen.
    def _boom(tool, args):
        raise RuntimeError("spawn boom")
    monkeypatch.setattr(prefetch, "call_mcp_tool", _boom)
    out = _launch(intent="I04", entities={"fach": "Mathe"})
    spec_task, name, args, query, extras, is_all, all_extras = out
    assert spec_task is None
    assert extras == []
    # NOTE: pinnt IST-Verhalten — nur spec_task wird zurückgesetzt; die übrigen
    # Spec-Variablen behalten ihren bereits gesetzten Zwischenstand
    # (Tool-Name/Args/Flag zeigen weiter auf search_wlo_all).
    assert name == "search_wlo_all"
    assert is_all is True
    assert query == "Mathe"
    assert args == {"query": "Mathe", "maxContent": 8, "maxCollections": 5,
                    "includeFacets": True, "discipline": "Mathe"}
    assert all_extras == []


# ── Toter Knopf ──────────────────────────────────────────────────────────

def test_spec_sammlung_keyword_has_no_observable_effect(spec_mcp):
    # NOTE: _wants_samml-Zweig entfernt 2026-07-09 (war seit O1 effektiv tot:
    # das Collections-Extra lieferte der Staircase-Zweig ohnehin bzw. das
    # Dedup/der search_all-Clear entfernte es wieder). Dieser Test bleibt als
    # Regressions-Wächter: "Sammlungen" im Text hat weiterhin KEINEN Effekt
    # auf das Spekulativ-Prefetch-Ergebnis.
    def _comparable(out):
        return (out[1], out[2], out[3], [n for n, _t in out[4]], out[5])
    a = _launch(message="Zeig mir Sammlungen zu Brüchen",
                intent="I03", entities={"thema": "Brüche"})
    b = _launch(message="Material zu Brüchen",
                intent="I03", entities={"thema": "Brüche"})
    assert _comparable(a) == _comparable(b)
