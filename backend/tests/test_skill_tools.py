"""D1+D2: Skill-Werkzeuge im Katalog und in den Mustern.

Der Server führt seit dem Deployment vom 2026-08-10 `search_skill` und
`get_skill` — redaktionell gepflegte Anleitungen (Inhaltsart `ai_skill`, bis
zum 2026-08-12 `ai_prompt`) mit angehängter `SKILL.md`. Die Registry kannte
beide Namen schon (Paket A); es
fehlten der Katalog (was das Modell sehen kann) und die Muster (was es je Zug
wirklich sieht).

Gemessen 2026-08-10 gegen den echten Server: der Bestand enthält **noch keinen**
Skill (`{"query":null,"skills":[],"unresolved":[]}`). Die Redaktion legt sie
gerade an — deshalb ist die Verdrahtung fertig gebaut, damit sie greift, sobald
Inhalte da sind. Bis dahin antwortet das Werkzeug wahrheitsgemäß „Keine Skills
gefunden."
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS, validate_tool_args
from boerdi.services.response_tool_selection import _select_active_tools

_SKILL_TOOLS = ("search_skill", "get_skill")
_PATTERN_DIR = pathlib.Path(__file__).resolve().parents[1] / "seeds" / "03-patterns"


def _katalog() -> dict[str, dict]:
    return {t["function"]["name"]: t["function"] for t in TOOL_DEFINITIONS}


def _muster(datei: str) -> dict:
    text = (_PATTERN_DIR / datei).read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1]) or {}


# ── D1: Katalog ──────────────────────────────────────────────────────────


class TestKatalog:
    @pytest.mark.parametrize("name", _SKILL_TOOLS)
    def test_werkzeug_steht_im_katalog(self, name):
        assert name in _katalog()

    def test_search_skill_nennt_get_skill_als_folgeschritt(self):
        # Zwei-Schritt-Werkzeug: ohne diesen Hinweis ruft das Modell die
        # Auflistung und antwortet aus Titel + Beschreibung, ohne die
        # Anleitung je zu laden.
        assert "get_skill" in _katalog()["search_skill"]["description"]

    def test_get_skill_verlangt_eine_node_id(self):
        assert _katalog()["get_skill"]["parameters"]["required"] == ["nodeId"]

    def test_search_skill_verlangt_nichts(self):
        # Ohne Argumente listet der Server den ganzen Katalog auf — das ist
        # die Antwort auf „welche Anleitungen gibt es?".
        assert not _katalog()["search_skill"]["parameters"].get("required")


# ── D1: Argument-Prüfung ─────────────────────────────────────────────────
# ``validate_tool_args`` reicht Argumente UNGEPRÜFT durch, solange kein Modell
# registriert ist. Für ein Werkzeug mit Server-Grenzen (maxResults 1..25) hieße
# das: eine vom Modell erfundene 500 ginge roh an den Server.


class TestArgumentPruefung:
    def test_maxresults_wird_auf_die_servergrenze_geklemmt(self):
        assert validate_tool_args("search_skill", {"maxResults": 500})["maxResults"] == 25

    def test_leere_zeichenketten_fallen_weg(self):
        geprueft = validate_tool_args("search_skill", {"query": "Stunde planen", "discipline": ""})
        assert geprueft["query"] == "Stunde planen"
        assert "discipline" not in geprueft

    def test_get_skill_behaelt_die_node_id(self):
        geprueft = validate_tool_args("get_skill", {"nodeId": "abc-123"})
        assert geprueft["nodeId"] == "abc-123"


# ── D2: Muster-Zuordnung ─────────────────────────────────────────────────


class TestMusterZuordnung:
    @pytest.mark.parametrize("datei", [
        "m09-lernpfad-erstellung.md",
        "m10-ki-inhalt-generierung.md",
    ])
    def test_muster_bietet_beide_skill_werkzeuge(self, datei):
        tools = _muster(datei).get("tools") or []
        assert set(_SKILL_TOOLS) <= set(tools), f"{datei}: {tools}"

    # ENTFERNT (R1, 2026-08-11): ``test_m10_behaelt_seine_bisherigen_werkzeuge``
    # verlangte hier ``search_wlo_collections`` + ``search_wlo_topic_pages`` für
    # M10, mit der Begründung, das Muster habe sie zuvor über den Rückfall-Zweig
    # von ``_select_active_tools`` bekommen.
    #
    # Diese Begründung ist widerlegt. Der Rückfall-Zweig ist über
    # ``phase3_modulate`` unerreichbar — ``PatternDef.tools`` hat
    # ``default_factory=list``, der Schlüssel steht also IMMER im Dict und der
    # erste Zweig fängt alles ab (``test_rueckfall_zweig_ist_unerreichbar``).
    # Nachgemessen an M10 im Vorzustand (``sources: [llm]``, kein ``tools:``):
    # NULL Werkzeuge, nicht zwei. Der Test schützte also keine Regression,
    # sondern verlangte eine Neuvergabe — gegen M10s eigene
    # ``forbidden_phrases`` („Such-Tool-Calls").
    #
    # Die richtige Zusicherung lebt jetzt als ``TestKiErzeugungSuchtNicht`` in
    # ``test_pattern_tool_naht.py``, wo die Aussagen über den Betriebspfad
    # stehen. Hier bewusst kein zweiter, gleichlautender Test.

    def test_skill_werkzeuge_erreichen_das_modell_wirklich(self):
        # Der Katalog allein wirkt nicht: Muster mit ``tools`` schneiden die
        # Liste auf ihre eigenen Namen zu (vgl. den M17-Befund in
        # test_config_seed_tree.py).
        aktiv, *_ = _select_active_tools(
            classification={}, pattern_output=_muster("m09-lernpfad-erstellung.md"),
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=False, _degradation_no_tools=False,
        )
        assert set(_SKILL_TOOLS) <= {t["function"]["name"] for t in aktiv}

    def test_typ_fokus_laesst_die_skill_werkzeuge_stehen(self):
        # Bei einem Medientyp-Filter strippt ``_select_active_tools`` die
        # Sammlungs-/Themenseiten-Suche. Eine Anleitung ist kein Suchtreffer
        # und darf davon nicht mitgerissen werden.
        aktiv, *_ = _select_active_tools(
            classification={"entities": {"medientyp": "Arbeitsblatt"}},
            pattern_output=_muster("m09-lernpfad-erstellung.md"),
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=False, _degradation_no_tools=False,
        )
        assert set(_SKILL_TOOLS) <= {t["function"]["name"] for t in aktiv}
