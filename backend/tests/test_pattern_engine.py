"""Coverage + Verhaltens-Pins für pattern_engine — Port von ALT
``tests/test_pattern_engine.py``. Modul zog nach ``boerdi.domain.pattern_engine``.

Hint-primary Pattern-Selektion + Phase-3-Modulation. Config-Seams gemockt:
``_load_config_tables`` + ``get_tone_modifier_for_persona`` für ``phase3_modulate``,
``get_patterns`` + ``phase3_modulate`` für ``select_pattern`` (isoliert die
Selektions-Logik von der Modulation). Die Loader werden am ``config_loader``-
Facade gemockt, weil die Modulation/Ladepfade sie lazy von dort importieren.
"""

from __future__ import annotations

import pytest

from boerdi.domain import pattern_engine as pe
from boerdi.services import config_loader


# ── _apply_length_bias (rein) ──────────────────────────────────────
@pytest.mark.parametrize("default,bias,exp", [
    ("mittel", 0.0, "mittel"),
    ("mittel", 0.2, "lang"),      # +Shift
    ("mittel", -0.2, "kurz"),     # -Shift
    ("lang", 0.2, "lang"),        # Clamp bei 2
    ("kurz", -0.2, "kurz"),       # Clamp bei 0
    ("unbekannt", 0.0, "mittel"),  # Default-Rank 1
])
def test_apply_length_bias(default, bias, exp):
    assert pe._apply_length_bias(default, bias) == exp


# ── _pattern_from_dict ─────────────────────────────────────────────
def test_pattern_from_dict_label_fallback():
    p = pe._pattern_from_dict({"id": "M99"})
    assert p.id == "M99"
    assert p.label == "M99"          # label fällt auf id zurück


def test_pattern_from_dict_drops_legacy_fields():
    p = pe._pattern_from_dict(
        {"id": "M01", "label": "X", "gate_personas": ["P-AND"], "page_bonus": 5}
    )
    assert (p.id, p.label) == ("M01", "X")  # Legacy-Felder ignoriert, kein Crash


# ── phase3_modulate (Config-Tabellen + Tone-Modifier gemockt) ──────
def _mock_tables(monkeypatch, modulations, reduce_items, device_max, formality):
    monkeypatch.setattr(pe, "_load_config_tables",
                        lambda: (modulations, reduce_items, device_max, formality))


def _mock_tone(monkeypatch, **tone):
    monkeypatch.setattr(config_loader, "get_tone_modifier_for_persona", lambda pid: tone)


def test_phase3_modulate_modifier_override_wins_and_appends_helpers(monkeypatch):
    _mock_tables(monkeypatch, {}, [], {"desktop": 6, "mobile": 3}, {"P-AND": "neutral"})
    _mock_tone(monkeypatch, tone="warm", length_bias=0.0, formality="du",
               card_text_mode="highlight", override=True)
    p = pe.PatternDef(id="M09", label="Suche", tools=["search_wlo_collections"],
                      default_tone="sachlich")
    out = pe.phase3_modulate(p, signals=[], device="desktop", entities={}, persona_id="P-LEH")
    assert out["tone"] == "warm"            # override → Modifier siegt
    assert out["formality"] == "du"
    assert out["card_text_mode"] == "highlight"
    assert out["max_items"] == 6
    # Such-Tool aktiv → Helper-Tools automatisch ergänzt
    assert "lookup_wlo_vocabulary" in out["tools"]
    assert "get_node_details" in out["tools"]


def test_phase3_modulate_signal_and_degradation(monkeypatch):
    _mock_tables(monkeypatch, {"knapp": {"detail_level": "kompakt"}}, ["knapp"],
                 {"desktop": 6}, {})
    _mock_tone(monkeypatch, tone="neutral", length_bias=0.0, formality="wie_user",
               card_text_mode="minimal", override=False)
    p = pe.PatternDef(id="M09", label="X", precondition_slots=["thema"],
                      default_tone="sachlich")
    out = pe.phase3_modulate(p, signals=["knapp"], device="desktop", entities={},
                             persona_id="P-AND")
    assert out["detail_level"] == "kompakt"        # Signal-Modulation angewandt
    assert out["max_items"] == 3                   # 'knapp' in reduce_items → geklemmt
    assert out["degradation"] is True              # precondition 'thema' fehlt
    assert out["missing_slots"] == ["thema"]
    assert out["formality"] == "neutral"           # wie_user + kein Map-Eintrag → neutral


# ── select_pattern (get_patterns + phase3_modulate gemockt) ────────
def _mock_selection(monkeypatch, patterns):
    monkeypatch.setattr(pe, "get_patterns", lambda: patterns)
    monkeypatch.setattr(pe, "phase3_modulate", lambda p, *a, **k: {"id": p.id})


def _call(**kw):
    return pe.select_pattern("P-AND", "S1", "I01", [], "", "desktop", {}, **kw)


def test_select_enforced_wins(monkeypatch):
    _mock_selection(monkeypatch, [pe.PatternDef(id="M01", label="Crisis"),
                                  pe.PatternDef(id="M15", label="Orient")])
    w, out, scores, elim = _call(enforced_pattern_id="M01")
    assert w.id == "M01"
    assert scores == {"M01": 1.0}
    assert elim == []


def test_select_hint_wins(monkeypatch):
    _mock_selection(monkeypatch, [pe.PatternDef(id="M09", label="Suche"),
                                  pe.PatternDef(id="M15", label="Orient")])
    w, _out, scores, _e = _call(pattern_id_hint="M09")
    assert w.id == "M09"
    assert scores == {"M09": 1.0}


def test_select_unknown_hint_uses_fallback_id(monkeypatch):
    # M07 (patterns[0]) ist KEINE Fallback-ID; M15 schon → Fallback wählt M15.
    _mock_selection(monkeypatch, [pe.PatternDef(id="M07", label="X"),
                                  pe.PatternDef(id="M15", label="Orient")])
    w, _o, _s, _e = _call(pattern_id_hint="M-UNKNOWN")
    assert w.id == "M15"


def test_select_enforced_unknown_falls_through_to_hint(monkeypatch):
    _mock_selection(monkeypatch, [pe.PatternDef(id="M09", label="S")])
    w, _o, _s, _e = _call(enforced_pattern_id="M-GONE", pattern_id_hint="M09")
    assert w.id == "M09"


def test_select_default_fallback_first_pattern_when_no_fallback_id(monkeypatch):
    _mock_selection(monkeypatch, [pe.PatternDef(id="M07", label="X")])  # kein M15/M03
    w, _o, _s, _e = _call()
    assert w.id == "M07"          # patterns[0] als letzte Instanz


def test_select_no_patterns_raises(monkeypatch):
    monkeypatch.setattr(pe, "get_patterns", lambda: [])
    with pytest.raises(RuntimeError):
        _call()


# ── Config-Loading-Pfade (config_loader-Seam gemockt) ──────────────
def test_load_patterns_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(config_loader, "load_pattern_definitions", lambda: [])
    assert pe.load_patterns() == []


def test_load_patterns_maps_dicts_to_defs(monkeypatch):
    monkeypatch.setattr(config_loader, "load_pattern_definitions",
                        lambda: [{"id": "M09", "label": "Suche"}, {"id": "M15"}])
    pats = pe.get_patterns()  # delegiert an load_patterns
    assert [p.id for p in pats] == ["M09", "M15"]
    assert pats[1].label == "M15"  # label-Fallback


def test_load_config_tables_uses_defaults(monkeypatch):
    monkeypatch.setattr(config_loader, "load_signal_modulations", lambda: ({"x": {}}, ["y"]))
    monkeypatch.setattr(config_loader, "load_device_config", lambda: {})
    mods, reduce, device_max, formality = pe._load_config_tables()
    assert (mods, reduce) == ({"x": {}}, ["y"])
    assert device_max == {"desktop": 6, "tablet": 4, "mobile": 3}  # Default bei leerer Config
    assert formality == {"P-AND": "neutral"}                        # Default
