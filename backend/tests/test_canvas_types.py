"""Characterization tests for domain/canvas/types.py (P4-5 canvas leaf).

ALT origin: ``app/services/canvas_types.py`` — the ``_DEFAULT_*`` fallback data
+ the 8 config-driven getters. Each getter reads the ``config_loader.load_canvas_*``
read-facade (studio-editable, mtime/NOTIFY-cached) and falls back to the in-code
``_DEFAULT_*`` block on empty result or load failure. In ALT these were only
integration-tested via ``canvas_service`` re-export (test_canvas_service_pure.py:
material-types-nonempty + getter-type-contracts) → these pin the merge/default/
override semantics directly. Logic fidelity is proven by the AST-diff gate.

``config_loader`` is faked at the module (as the ALT docstring prescribes:
"Tests patchen canvas_types.config_loader") so the getters are hermetic and
PG-independent.
"""

from types import SimpleNamespace

from boerdi.domain.canvas import types as ct


def _patch_cl(monkeypatch, **loaders):
    """Fake types.config_loader; each named loader returns its value or, if
    callable, is used as-is (to raise). Unnamed loaders return empty containers."""
    def _make(val):
        if callable(val):
            return val
        return lambda: val

    ns = SimpleNamespace(
        load_canvas_material_types=_make(loaders.get("material_types", [])),
        load_canvas_type_aliases=_make(loaders.get(
            "type_aliases", {"aliases": {}, "short_whitelist": [], "lrt_to_type": {}})),
        load_canvas_create_triggers=_make(loaders.get(
            "create_triggers", {"create_triggers": [], "search_verbs": []})),
        load_canvas_edit_triggers=_make(loaders.get(
            "edit_triggers", {"edit_triggers": [], "explicit_create_overrides": []})),
        load_canvas_persona_priorities=_make(loaders.get(
            "persona_priorities", {"analytical_personas": []})),
    )
    monkeypatch.setattr(ct, "config_loader", ns)


def _boom():
    raise RuntimeError("config store down")


class TestGetMaterialTypes:
    def test_empty_loader_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch, material_types=[])
        assert ct.get_material_types() == ct._DEFAULT_MATERIAL_TYPES

    def test_loader_exception_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch, material_types=_boom)
        assert ct.get_material_types() == ct._DEFAULT_MATERIAL_TYPES

    def test_defaults_are_deepcopied(self, monkeypatch):
        _patch_cl(monkeypatch, material_types=[])
        got = ct.get_material_types()
        got["auto"]["label"] = "MUTATED"
        assert ct._DEFAULT_MATERIAL_TYPES["auto"]["label"] != "MUTATED"

    def test_config_items_mapped(self, monkeypatch):
        _patch_cl(monkeypatch, material_types=[
            {"id": "foo", "label": "Foo", "emoji": "🎯",
             "structure": "S", "category": "didaktisch"},
        ])
        out = ct.get_material_types()
        # `label_en` gehoert seit C1-g2e zum Eintrag: der Getter ist gecacht,
        # die Sprache gehoert zum Zug — also reist sie mit statt aufgeloest zu
        # werden. Erwartung erweitert statt auf Teilmenge abgeschwaecht.
        assert out == {"foo": {"label": "Foo", "label_en": "", "emoji": "🎯",
                               "structure": "S", "category": "didaktisch"}}

    def test_english_label_travels_with_the_entry(self, monkeypatch):
        """C1-g2e: ohne `label_en` im Eintrag koennte niemand es waehlen."""
        _patch_cl(monkeypatch, material_types=[
            {"id": "foo", "label": "Foo", "label_en": "Bar", "emoji": "🎯"},
        ])
        assert ct.get_material_types()["foo"]["label_en"] == "Bar"

    def test_material_type_label_picks_per_key(self):
        entry = {"label": "Arbeitsblatt", "label_en": "Worksheet"}
        assert ct.material_type_label(entry, "de") == "Arbeitsblatt"
        assert ct.material_type_label(entry, "en") == "Worksheet"

    def test_material_type_label_falls_back_to_german(self):
        """Leer heisst „nicht gepflegt", nie „leerer Text"."""
        assert ct.material_type_label({"label": "Glossar"}, "en") == "Glossar"
        assert ct.material_type_label(
            {"label": "Glossar", "label_en": "  "}, "en") == "Glossar"

    def test_item_defaults_and_skips(self, monkeypatch):
        _patch_cl(monkeypatch, material_types=[
            "not-a-dict",                       # skipped (not dict)
            {"label": "no id"},                 # skipped (no id)
            {"id": "bar"},                      # label/emoji defaulted, no category
        ])
        out = ct.get_material_types()
        assert set(out) == {"bar"}
        assert out["bar"] == {"label": "bar", "label_en": "",
                              "emoji": "📄", "structure": ""}


class TestGetTypeAliases:
    def test_empty_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_type_aliases() == dict(ct._DEFAULT_TYPE_ALIASES)

    def test_exception_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch, type_aliases=_boom)
        assert ct.get_type_aliases() == dict(ct._DEFAULT_TYPE_ALIASES)

    def test_yaml_merged_over_defaults_lowercased(self, monkeypatch):
        _patch_cl(monkeypatch, type_aliases={
            "aliases": {"MyAlias": "quiz", 5: "bad", "k": 9},  # non-str k/v dropped
            "short_whitelist": [], "lrt_to_type": {},
        })
        out = ct.get_type_aliases()
        assert out["myalias"] == "quiz"          # lowercased
        assert "quiz" in ct._DEFAULT_TYPE_ALIASES  # defaults retained
        assert 5 not in out and "k" not in out     # non-str filtered


class TestShortAliasWhitelist:
    def test_empty_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_short_alias_whitelist() == set(ct._DEFAULT_SHORT_ALIAS_WHITELIST)

    def test_from_loader_lowercased_set(self, monkeypatch):
        _patch_cl(monkeypatch, type_aliases={
            "aliases": {}, "short_whitelist": [" AB ", "cd", ""], "lrt_to_type": {}})
        assert ct.get_short_alias_whitelist() == {"ab", "cd"}


class TestLrtMapping:
    def test_empty_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_lrt_mapping() == dict(ct._DEFAULT_LRT_TO_MATERIAL_TYPE)

    def test_merge_over_defaults(self, monkeypatch):
        _patch_cl(monkeypatch, type_aliases={
            "aliases": {}, "short_whitelist": [], "lrt_to_type": {"NewLRT": "quiz"}})
        out = ct.get_lrt_mapping()
        assert out["newlrt"] == "quiz"
        assert len(out) == len(ct._DEFAULT_LRT_TO_MATERIAL_TYPE) + 1


class TestTriggerGetters:
    def test_create_triggers_default_and_override(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_create_triggers() == tuple(ct._DEFAULT_CREATE_TRIGGERS)
        _patch_cl(monkeypatch, create_triggers={
            "create_triggers": ["baue", "", "erzeuge"], "search_verbs": []})
        assert ct.get_create_triggers() == ("baue", "erzeuge")

    def test_edit_triggers_default_and_override(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_edit_triggers() == ct._DEFAULT_EDIT_TRIGGERS
        _patch_cl(monkeypatch, edit_triggers={
            "edit_triggers": ["ändere"], "explicit_create_overrides": []})
        assert ct.get_edit_triggers() == ("ändere",)

    def test_explicit_create_overrides_default_and_override(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_explicit_create_overrides() == ct._DEFAULT_EXPLICIT_CREATE_OVERRIDES
        _patch_cl(monkeypatch, edit_triggers={
            "edit_triggers": [], "explicit_create_overrides": ["neues quiz"]})
        assert ct.get_explicit_create_overrides() == ("neues quiz",)


class TestAnalyticalPersonas:
    def test_empty_returns_defaults(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert ct.get_analytical_personas() == ct._DEFAULT_ANALYTICAL_PERSONAS

    def test_from_loader_frozenset_stripped(self, monkeypatch):
        _patch_cl(monkeypatch, persona_priorities={"analytical_personas": [" P-RED ", "P-ENT"]})
        out = ct.get_analytical_personas()
        assert isinstance(out, frozenset)
        assert out == frozenset({"P-RED", "P-ENT"})


class TestTypeContracts:
    """Ported from ALT test_canvas_service_pure.py (getter type contracts)."""

    def test_material_types_is_nonempty_dict(self, monkeypatch):
        _patch_cl(monkeypatch)
        mts = ct.get_material_types()
        assert isinstance(mts, dict) and mts

    def test_config_getter_types(self, monkeypatch):
        _patch_cl(monkeypatch)
        assert isinstance(ct.get_create_triggers(), tuple)
        assert isinstance(ct.get_edit_triggers(), tuple)
        assert isinstance(ct.get_type_aliases(), dict)
        assert isinstance(ct.get_analytical_personas(), frozenset)
        assert isinstance(ct.get_short_alias_whitelist(), set)
