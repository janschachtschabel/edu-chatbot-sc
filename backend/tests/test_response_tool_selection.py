"""Direkte Unit-Charakterisierung von ``_select_active_tools`` (P3-3b).

Die einzige ALT-Abdeckung war ein *Integrations*-Test
(``test_active_tools_selection.py``), der die Funktion durch ``generate_response``
fährt — ein Harness, das in NEU noch nicht gebaut ist (blockiert auf Tool-Loop /
P4-P6). Der Portierungs-Vertrag (``docs/plans/p3-response-prompt-contract.md``
§1/§5) schreibt daher **direkte** Unit-Tests gegen die §6-Marker vor. Die drei
ALT-Integrations-Verträge (search_wlo_all sichtbar / medientyp strippt all+pots /
content bleibt) sind hier als direkte Fälle gespiegelt. ``TOOL_DEFINITIONS`` läuft
ECHT (Import aus dem 5-2-Port); kein Netz, keine DB.
"""

from __future__ import annotations

import pytest

from boerdi.services import response_tool_selection as rts
from boerdi.services.mcp import tool_defs as td

_ALL_TOOL_NAMES = [t["function"]["name"] for t in td.TOOL_DEFINITIONS]
# ALT M06-Kaskade: kombinierte Breitsuche + Einzel-Tools (test_active_tools_selection.py).
_SEARCH_TOOLS_WITH_ALL = [
    "search_wlo_all",
    "search_wlo_topic_pages",
    "search_wlo_collections",
    "search_wlo_content",
    "lookup_wlo_vocabulary",
]
_RAG_CFG = {"recht": {"description": "Rechtsfragen"}}


@pytest.fixture(autouse=True)
def _clean_env_and_tools(monkeypatch):
    # ENV-Gates werden zur Call-Zeit gelesen → für Determinismus leeren.
    monkeypatch.delenv("CHAT_DISABLE_SELECT_TOP_CARDS", raising=False)
    monkeypatch.delenv("CHAT_INLINE_QUICK_REPLIES", raising=False)
    # Safety-Net gegen den verbatim portierten ALT-Quirk (mcp-Zweig aliast
    # TOOL_DEFINITIONS): Inhalt nach jedem Test wiederherstellen, damit kein
    # ``.append`` in andere Tests / andere Importeure leakt.
    snapshot = list(td.TOOL_DEFINITIONS)
    yield
    td.TOOL_DEFINITIONS[:] = snapshot


def _select(pattern_output, *, entities=None, areas=None, rag_config=None,
            inline=False, degradation=False):
    return rts._select_active_tools(
        {"entities": entities or {}},
        pattern_output,
        areas,
        rag_config,
        inline,
        degradation,
    )


def _names(pattern_output, **kw):
    active, *_ = _select(pattern_output, **kw)
    return [t["function"]["name"] for t in active]


def test_ein_stillgelegtes_werkzeug_kommt_auch_aus_einem_muster_nicht_durch(monkeypatch):
    """P3 (Nutzer-Entscheid 2026-08-13) gilt fuer BEIDE Wege.

    Die Agent-Schleife filtert ``AUS_DEM_KATALOG`` im Code; der Muster-Weg
    verliess sich allein darauf, dass kein Seed das Werkzeug mehr nennt. Muster
    liegen aber in der Datenbank: bis zum Seed-Import traegt sie die alten, und
    im Studio laesst sich der Name jederzeit wieder eintragen. Der Wächter im
    Seed-Baum liest den Seed, nicht die Datenbank — er saehe das nicht.

    Hier steht das Werkzeug also ausdruecklich im Muster, und trotzdem darf es
    dem Modell nicht angeboten werden.
    """
    _disable_cards(monkeypatch)
    from boerdi.services.agent_tools import AUS_DEM_KATALOG
    stillgelegt = sorted(AUS_DEM_KATALOG)
    namen = _names({"tools": [*stillgelegt, "search_wlo_collections"]})
    assert "search_wlo_collections" in namen, "das Muster verliert seine anderen Werkzeuge"
    assert not (set(namen) & AUS_DEM_KATALOG), f"{stillgelegt} wurde trotzdem angeboten"


def _disable_cards(monkeypatch):
    # Isoliert die Basis-Auswahl (kein select_top_cards-Append) und umgeht damit
    # zugleich den mcp-Alias-Quirk.
    monkeypatch.setenv("CHAT_DISABLE_SELECT_TOP_CARDS", "1")


# ═══ P10 — Basis-Tool-Wahl ═════════════════════════════════════════════════
def test_pattern_tools_whitelist_in_tool_defs_order(monkeypatch):
    _disable_cards(monkeypatch)
    # Reihenfolge folgt TOOL_DEFINITIONS (Comprehension-Filter), NICHT der
    # Reihenfolge in pattern.tools.
    names = _names({"tools": ["lookup_wlo_vocabulary", "search_wlo_content"]})
    assert names == ["search_wlo_content", "lookup_wlo_vocabulary"]


def test_explicit_empty_tools_yields_no_base_tools(monkeypatch):
    _disable_cards(monkeypatch)
    # tools==[] explizit → KEINE Tools (z.B. M15-Orientierungs-Guide).
    assert _names({"tools": []}) == []


def test_mcp_source_offers_all_tool_defs(monkeypatch):
    _disable_cards(monkeypatch)
    assert _names({"sources": ["mcp"]}) == _ALL_TOOL_NAMES


def test_mcp_source_waechst_den_katalog_nicht():
    """Der ``has_mcp_source``-Zweig darf ``TOOL_DEFINITIONS`` nicht anfassen.

    Gemessen 2026-08-10 beim Bau von E2: er wies die Modul-Globale per REFERENZ
    zu, und das spätere ``active_tools.append(...)`` schrieb dann in sie hinein.
    Über fünf Aufrufe wuchs der Katalog 22 → 27, das Modell bekam
    ``select_top_cards`` fünfmal angeboten. Im Testlauf fiel es als
    Reihenfolge-Abhängigkeit auf (zwei fremde Tests kippten), im Betrieb wäre es
    still gewachsen: jeder Zug eines ``sources: [mcp]``-Musters ein Eintrag
    mehr. Der ``simplify:``-Vermerk im Modulkopf hatte den Fall beschrieben —
    hier ist die Messung dazu.

    Bewusst OHNE ``_disable_cards``: gerade der eingeschaltete Zustand löst den
    ``append`` aus. Das autouse-Sicherheitsnetz oben stellt den Katalog erst
    NACH dem Test wieder her — während des Laufs misst diese Prüfung also den
    echten Zustand. Genau deshalb blieb der Defekt lange unsichtbar: das Netz
    hielt ihn in dieser Datei, und keine andere fasste den Zweig an.
    """
    vorher = len(td.TOOL_DEFINITIONS)
    for _ in range(3):
        rts._select_active_tools(
            classification={}, pattern_output={"sources": ["mcp"]},
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=True, _degradation_no_tools=False,
        )
    assert len(td.TOOL_DEFINITIONS) == vorher


def test_fallback_search_and_topic_pages(monkeypatch):
    _disable_cards(monkeypatch)
    # Kein tools, kein mcp → Fallback {collections, topic_pages}.
    assert _names({}) == ["search_wlo_collections", "search_wlo_topic_pages"]


# ═══ P10b — medientyp-Strip ════════════════════════════════════════════════
def test_medientyp_strips_all_collections_topics_keeps_content(monkeypatch):
    _disable_cards(monkeypatch)
    names = _names(
        {"tools": list(_SEARCH_TOOLS_WITH_ALL), "sources": ["mcp"]},
        entities={"medientyp": "Video"},
    )
    assert "search_wlo_all" not in names
    assert "search_wlo_collections" not in names
    assert "search_wlo_topic_pages" not in names
    assert "search_wlo_content" in names


def test_no_medientyp_keeps_search_wlo_all(monkeypatch):
    _disable_cards(monkeypatch)
    names = _names(
        {"tools": list(_SEARCH_TOOLS_WITH_ALL), "sources": ["mcp"]},
        entities={},
    )
    assert "search_wlo_all" in names
    assert "search_wlo_content" in names


def test_medientyp_sammlung_behaelt_die_sammlungssuche(monkeypatch):
    """Nutzer-Befund 2026-08-16: „Suche mir Sammlungen zum Thema Optik" ergab
    ``medientyp='Sammlung'``, worauf genau die Werkzeuge verschwanden, die
    Sammlungen finden. Ohne Sammlungskarte gibt es keine Skill-Notiz und damit
    keinen Vorrang der freigegebenen Anleitungen.

    Die Begruendung des Strips traegt nur fuer INHALTS-Typen; meint der
    Medientyp die Sammlung selbst, ist die Sammlungssuche der richtige Weg."""
    _disable_cards(monkeypatch)
    names = _names(
        {"tools": list(_SEARCH_TOOLS_WITH_ALL), "sources": ["mcp"]},
        entities={"medientyp": "Sammlung"},
    )
    assert "search_wlo_all" in names
    assert "search_wlo_collections" in names
    assert "search_wlo_topic_pages" in names


def test_medientyp_themenseite_behaelt_die_sammlungssuche(monkeypatch):
    _disable_cards(monkeypatch)
    names = _names(
        {"tools": list(_SEARCH_TOOLS_WITH_ALL), "sources": ["mcp"]},
        entities={"medientyp": "Themenseite"},
    )
    assert "search_wlo_topic_pages" in names


def test_medientyp_adds_content_when_pattern_omitted_it(monkeypatch):
    _disable_cards(monkeypatch)
    # Pattern listet nur Sammlungen/Themenseiten; medientyp strippt beide →
    # search_wlo_content wird garantiert nachgezogen.
    names = _names(
        {"tools": ["search_wlo_collections", "search_wlo_topic_pages"]},
        entities={"medientyp": "Arbeitsblatt"},
    )
    assert names == ["search_wlo_content"]


# ═══ P11a/b — RAG-Sources-Gate + query_knowledge ═══════════════════════════
def test_query_knowledge_prepended_when_areas_and_rag_allowed(monkeypatch):
    _disable_cards(monkeypatch)
    names = _names({"sources": ["mcp", "rag"]}, areas=["recht"], rag_config=_RAG_CFG)
    assert names[0] == "query_knowledge"


def test_query_knowledge_enum_equals_areas(monkeypatch):
    _disable_cards(monkeypatch)
    active, *_ = _select(
        {"sources": ["mcp", "rag"]},
        areas=["recht", "ethik"],
        rag_config={"recht": {"description": "R"}, "ethik": {"description": "E"}},
    )
    qk = next(t for t in active if t["function"]["name"] == "query_knowledge")
    enum = qk["function"]["parameters"]["properties"]["area"]["enum"]
    assert enum == ["recht", "ethik"]


def test_rag_gate_blocks_query_knowledge_when_sources_without_rag(monkeypatch):
    _disable_cards(monkeypatch)
    active, _decl, allowed, _qr = _select(
        {"sources": ["mcp"]}, areas=["recht"], rag_config=_RAG_CFG,
    )
    names = [t["function"]["name"] for t in active]
    assert "query_knowledge" not in names
    assert allowed is False


def test_rag_allowed_when_no_sources_declared(monkeypatch):
    _disable_cards(monkeypatch)
    active, decl, allowed, _qr = _select({}, areas=["recht"], rag_config=_RAG_CFG)
    names = [t["function"]["name"] for t in active]
    assert names[0] == "query_knowledge"
    assert decl is None
    assert allowed is True


# ═══ P11c — select_top_cards (ENV-Gate + Inline/Re-Rank-Beschreibung) ═══════
def test_select_top_cards_appended_by_default():
    names = _names({"tools": ["search_wlo_content"]})
    assert names == ["search_wlo_content", "select_top_cards"]


def test_select_top_cards_disabled_via_env(monkeypatch):
    monkeypatch.setenv("CHAT_DISABLE_SELECT_TOP_CARDS", "1")
    assert "select_top_cards" not in _names({"tools": ["search_wlo_content"]})


def test_select_top_cards_disable_set_is_exact_yes_does_not_disable(monkeypatch):
    # DISABLE-Set ist exakt ("1","true","True") — "yes" deaktiviert NICHT.
    monkeypatch.setenv("CHAT_DISABLE_SELECT_TOP_CARDS", "yes")
    assert "select_top_cards" in _names({"tools": ["search_wlo_content"]})


def test_select_top_cards_inline_description_when_cards_inline_mode():
    active, *_ = _select({"tools": ["search_wlo_content"]}, inline=True)
    sel = next(t for t in active if t["function"]["name"] == "select_top_cards")
    assert sel["function"]["description"].startswith("FINAL-SELECTION für Inline-Modus")


def test_select_top_cards_rerank_description_when_not_inline():
    active, *_ = _select({"tools": ["search_wlo_content"]}, inline=False)
    sel = next(t for t in active if t["function"]["name"] == "select_top_cards")
    assert sel["function"]["description"].startswith("RE-RANK-HINT für Kachel-Modus")


def _select_tool(**kw):
    active, *_ = _select({"tools": ["search_wlo_content"]}, **kw)
    return next(t for t in active if t["function"]["name"] == "select_top_cards")


def test_die_auswahl_ist_dem_modell_nicht_mehr_bei_fuenf_verboten():
    """Befund 2026-08-14 (Review zu #193).

    Der Backend-Deckel folgt seit #193 den Studio-Gruppen (Vorgabe 3+3+3), die
    Werkzeug-Definition deckelte das Modell aber weiter bei fuenf — als
    ``maxItems`` IM SCHEMA. Wo der Anbieter das Schema durchsetzt, waren mehr
    als fuenf IDs technisch unmoeglich; der neue Deckel war damit unerreichbar
    und die Optik-Sammlung konnte weiter aus der Auswahl fallen.

    Die Obergrenze hier ist die Konstante, nicht das Budget: das Budget lebt in
    der Konfiguration und wird allein im Backend angewandt. Zwei Zahlen fuer
    dieselbe Sache waeren die naechste Gelegenheit zum Auseinanderlaufen.
    """
    from boerdi.domain.inline_grouping import MAX_SELECTABLE_CARDS
    sel = _select_tool()
    schema = sel["function"]["parameters"]["properties"]["card_ids"]
    assert schema["maxItems"] == MAX_SELECTABLE_CARDS
    assert schema["minItems"] == 1


def test_die_beschreibung_nennt_kein_ziel_von_fuenf():
    # Der Deckel im Code allein reicht nicht: was das Modell liest, ist die
    # Beschreibung. Stand dort weiter „ZIEL: bis zu 5 IDs", waehlte es fuenf.
    for sel in (_select_tool(inline=True), _select_tool(inline=False)):
        beschreibung = sel["function"]["description"]
        assert "bis zu 5 IDs" not in beschreibung
        assert "1-5 IDs" not in beschreibung


# ═══ P11d — Degradation-Wipe ═══════════════════════════════════════════════
def test_degradation_wipes_all_tools():
    # _degradation_no_tools=True + nichtleere Liste → komplette Leerung, auch
    # das eben angehängte select_top_cards.
    assert _names({"tools": ["search_wlo_content"]}, degradation=True) == []


def test_degradation_then_respond_to_user_when_inline_qr(monkeypatch):
    # respond_to_user wird NACH der Degradation-Leerung angehängt.
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "1")
    assert _names({"tools": ["search_wlo_content"]}, degradation=True) == ["respond_to_user"]


# ═══ P11e — respond_to_user (ENV-Gate) ═════════════════════════════════════
def test_respond_to_user_absent_by_default():
    assert "respond_to_user" not in _names({"tools": ["search_wlo_content"]})


def test_respond_to_user_appended_last_when_inline_qr_env(monkeypatch):
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "1")
    names = _names({"tools": ["search_wlo_content"]})
    assert names[-1] == "respond_to_user"


def test_inline_qr_set_accepts_yes(monkeypatch):
    # INLINE_QR-Set ist ("1","true","yes") — asymmetrisch zum DISABLE-Set.
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "yes")
    assert "respond_to_user" in _names({"tools": ["search_wlo_content"]})


# ═══ Rückgabe-Tupel ════════════════════════════════════════════════════════
def test_return_tuple_shape_and_flags(monkeypatch):
    _disable_cards(monkeypatch)
    active, decl, allowed, qr = _select(
        {"sources": ["mcp", "rag"]}, areas=["recht"], rag_config=_RAG_CFG,
    )
    assert isinstance(active, list)
    assert decl == ["mcp", "rag"]
    assert allowed is True
    assert qr is False  # CHAT_INLINE_QUICK_REPLIES nicht gesetzt
