"""Die Werkzeugliste der Agent-Schleife (A1).

Anders als die Muster-Engine wählt hier kein Muster aus: der Agent bekommt den
GANZEN Katalog. Was bleibt, ist die eine Regel aus ``_nameable_tools`` —
kuratierende Werkzeuge nur mit hinterlegtem Zugangsblock, weil der Server sie
sonst ohnehin verweigert und ein angekündigtes Können, das der nächste Schritt
zurücknimmt, schlimmer ist als eines, das nie angeboten wurde.

``submit_result`` ist Abbruchsignal UND Struktur-Ausgabe in einem: der Agent ruft
es, wenn er fertig ist, und ein vom Aufrufer mitgegebenes Schema wird zu seinen
``parameters`` — dann erzwingt der Anbieter die Form, und wir müssen nichts über
sie wissen.
"""

from __future__ import annotations

import pytest

from boerdi.services.agent_tools import SUBMIT_RESULT, build_agent_tools
from boerdi.services.mcp.auth import set_turn_auth_block
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS


@pytest.fixture(autouse=True)
def _kein_zugangsblock():
    """Jeder Test startet ohne Anmeldung; der ContextVar überlebt sonst die Task."""
    set_turn_auth_block(None)
    yield
    set_turn_auth_block(None)


def _namen(tools: list[dict]) -> list[str]:
    return [t["function"]["name"] for t in tools]


def test_der_lesekatalog_ist_immer_dabei() -> None:
    namen = _namen(build_agent_tools())
    for gebraucht in ("search_wlo_all", "get_nodes_details", "get_skill_registry"):
        assert gebraucht in namen


def test_ohne_zugangsblock_keine_kuratierenden_werkzeuge() -> None:
    namen = _namen(build_agent_tools())
    assert "wlo_create_content" not in namen
    assert "wlo_add_to_collection" not in namen


def test_mit_zugangsblock_sind_sie_dabei() -> None:
    assert set_turn_auth_block("wlo2.abc-def_123")
    namen = _namen(build_agent_tools())
    assert "wlo_create_content" in namen
    assert "wlo_add_to_collection" in namen


def test_die_liste_ist_eine_kopie_des_katalogs() -> None:
    """E2-Regression: ein früherer Zweig aliaste ``TOOL_DEFINITIONS`` und ließ
    den Katalog bei JEDEM Zug um einen Eintrag wachsen (22 → 27 über fünf
    Aufrufe). Diese Zusicherung ist billiger als der Fund war."""
    vorher = len(TOOL_DEFINITIONS)
    build_agent_tools()
    build_agent_tools()
    assert len(TOOL_DEFINITIONS) == vorher


def test_submit_result_schliesst_die_liste_ab() -> None:
    tools = build_agent_tools()
    assert _namen(tools)[-1] == SUBMIT_RESULT, (
        "zuletzt, damit es in der Werkzeugliste nicht zwischen Suchwerkzeugen "
        "untergeht"
    )


def test_ohne_schema_ist_das_ergebnis_frei_und_freiwillig() -> None:
    ergebnis = build_agent_tools()[-1]["function"]["parameters"]
    assert ergebnis["properties"]["result"]["type"] == "object"
    assert ergebnis["required"] == ["text"]


def test_ein_mitgegebenes_schema_wird_zur_form_und_zur_pflicht() -> None:
    """Wer ein Schema mitgibt, will die Struktur — eine Antwort ohne sie wäre für
    ihn wertlos, also darf sie nicht optional sein."""
    schema = {
        "type": "object",
        "properties": {"sachrichtigkeit": {"type": "integer", "minimum": 0, "maximum": 5}},
        "required": ["sachrichtigkeit"],
    }
    ergebnis = build_agent_tools(result_schema=schema)[-1]["function"]["parameters"]
    assert ergebnis["properties"]["result"] == schema
    assert set(ergebnis["required"]) == {"text", "result"}


def test_kuratierende_werkzeuge_lassen_sich_ausdruecklich_abwaehlen() -> None:
    """Ein Gastgeber darf einen rein lesenden Lauf verlangen, auch wenn die
    Person angemeldet ist — Qualitätsprüfung ändert nichts."""
    assert set_turn_auth_block("wlo2.abc-def_123")
    namen = _namen(build_agent_tools(allow_curation=False))
    assert "wlo_create_content" not in namen
    assert "search_wlo_all" in namen


# ── Die Werkzeug-Sperre des Chat-Zuges (A4c-2b) ─────────────────────────────


def test_gesperrte_werkzeuge_fallen_aus_dem_katalog() -> None:
    """Safety/Policy sperren im Chat einzelne Werkzeuge. Im Bestandsweg streicht
    ``route`` sie aus ``pattern_output['tools']``; der Agent-Modus reicht sie
    hierher, weil er den Katalog selbst bekommt."""
    namen = _namen(build_agent_tools(blocked_tools=["search_wlo_content"]))
    assert "search_wlo_content" not in namen
    assert "search_wlo_all" in namen


def test_die_sperre_erreicht_auch_die_kuratierenden_werkzeuge() -> None:
    assert set_turn_auth_block("wlo2.abc-def_123")
    namen = _namen(build_agent_tools(blocked_tools=["wlo_delete_content"]))
    assert "wlo_delete_content" not in namen
    assert "wlo_create_content" in namen


def test_das_abschluss_werkzeug_ist_nicht_sperrbar() -> None:
    """Es ist virtuell — es geht nie an den MCP. Eine Sperre darauf nähme dem
    Lauf seine Ziellinie, statt eine Gefahr abzuwenden."""
    namen = _namen(build_agent_tools(blocked_tools=[SUBMIT_RESULT]))
    assert namen[-1] == SUBMIT_RESULT


def test_ohne_abschluss_werkzeug_endet_die_liste_beim_katalog() -> None:
    """Der Chat-Zug lässt es weg: dort liest niemand das strukturierte
    ``result``, und ein zusätzlicher Modellzug dafür kostet messbar Zeit."""
    namen = _namen(build_agent_tools(include_submit=False))
    assert SUBMIT_RESULT not in namen
    assert "search_wlo_all" in namen
