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

from boerdi.domain.pattern_engine import PatternDef
from boerdi.services.agent_tools import (
    AUS_DEM_KATALOG,
    SUBMIT_RESULT,
    WAEHLE_VORGEHEN,
    build_agent_tools,
)
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


# ── Der Musterkatalog als Werkzeug (H2, Hybrid-Modus) ──────────────────────


def _katalog() -> list[PatternDef]:
    return [
        PatternDef(id="M06", label="Material-Suche Cascade",
                   short_purpose="Thema ohne Filter → Kaskade"),
        PatternDef(id="M12", label="Null-Treffer-Eskalation"),
        # Gesperrt: darf weder ins ``enum`` noch in die Beschreibung geraten.
        PatternDef(id="M01", label="Krisen-Empathie"),
    ]


def test_ohne_katalog_gibt_es_kein_musterwerkzeug() -> None:
    """Der Parameter ist additiv: ``agent`` und ``/api/agent`` bleiben, wie sie
    sind. Ohne diese Zusage wäre der Hybrid keine dritte Maschine, sondern eine
    Änderung an der zweiten."""
    assert WAEHLE_VORGEHEN not in _namen(build_agent_tools())


def test_ein_leerer_katalog_bietet_kein_werkzeug_an() -> None:
    """Ein Werkzeug ohne wählbare Muster wäre ein angekündigtes Können, das der
    nächste Schritt zurücknimmt — dieselbe Regel wie bei den kuratierenden."""
    assert WAEHLE_VORGEHEN not in _namen(build_agent_tools(muster_katalog=[]))


def test_mit_katalog_steht_es_vorn_und_der_abschluss_hinten() -> None:
    """Die Reihenfolge ist die Reihenfolge der Arbeit: erst das Vorgehen wählen,
    dann arbeiten, zuletzt abschließen."""
    namen = _namen(build_agent_tools(muster_katalog=_katalog()))
    assert namen[0] == WAEHLE_VORGEHEN
    assert namen[-1] == SUBMIT_RESULT
    assert "search_wlo_all" in namen


def test_das_enum_fuehrt_genau_die_waehlbaren_kennungen() -> None:
    tools = build_agent_tools(muster_katalog=_katalog())
    props = tools[0]["function"]["parameters"]["properties"]
    assert props["muster_id"]["enum"] == ["M06", "M12"]
    assert tools[0]["function"]["parameters"]["required"] == ["muster_id"]


def test_der_katalog_steht_in_der_beschreibung() -> None:
    tools = build_agent_tools(muster_katalog=_katalog())
    text = tools[0]["function"]["description"]
    assert "### M06 — Material-Suche Cascade" in text
    assert "Thema ohne Filter" in text
    assert "Krisen-Empathie" not in text


def test_das_musterwerkzeug_ist_nicht_sperrbar() -> None:
    """Virtuell wie ``submit_result``: es geht nie an den MCP. Eine Sperre
    darauf nähme dem Lauf die Wahl seines Vorgehens, statt eine Gefahr
    abzuwenden — die Gefahr sitzt in den Werkzeugen, die das Muster dann
    freigibt, und die filtert ``blocked_tools`` weiterhin."""
    namen = _namen(build_agent_tools(muster_katalog=_katalog(),
                                     blocked_tools=[WAEHLE_VORGEHEN]))
    assert namen[0] == WAEHLE_VORGEHEN


# ── Stillgelegte Werkzeuge dürfen in keinem Text mehr vorkommen ─────────────


def _alle_texte(knoten: object) -> list[str]:
    """Jede Zeichenkette einer Werkzeugdefinition — Beschreibung wie Parameter.

    Beides geht wörtlich an das Modell; eine Parameter-Beschreibung wiegt sogar
    schwerer, weil sie genau dann gelesen wird, wenn das Werkzeug gerufen werden
    soll. Deshalb der ganze Teilbaum und nicht nur ``description``.
    """
    if isinstance(knoten, str):
        return [knoten]
    if isinstance(knoten, dict):
        return [t for wert in knoten.values() for t in _alle_texte(wert)]
    if isinstance(knoten, list):
        return [t for wert in knoten for t in _alle_texte(wert)]
    return []


def test_kein_angebotenes_werkzeug_verweist_auf_ein_stillgelegtes() -> None:
    """Ein Werkzeug, das kein Pfad reicht, darf in keinem Text als Weg stehen.

    Befund 2026-08-15: ``search_skill`` ist seit 2026-08-13 aus jedem Pfad
    genommen (:data:`AUS_DEM_KATALOG`, ``_NICHT_UEBER_PATTERN``) — die TEXTE
    zogen nicht nach. ``get_skill`` beschrieb sich als „der zweite Schritt nach
    search_skill" und seinen einzigen Pflichtparameter als „nodeId aus einem
    search_skill-Treffer". Das Modell bekommt also das Werkzeug, das die
    Anleitung öffnet, und dazu die Auskunft, seine Vorbedingung sei etwas, das
    es nicht hat. Die Agent-Schleife verdeckte das, weil ``respond_agent`` die
    Registry vorab in die Kette holt und die ``nodeId``s damit sichtbar sind;
    im Mustermodus gibt es diesen Vorabruf nicht, und der Weg endete.

    Geprüft wird der VOLLE Katalog (mit Zugangsblock, also samt kuratierender
    Werkzeuge) — beide Engines schöpfen aus ihm, die Muster-Engine über
    ``_nameable_tools``, die Agent-Schleife über ``build_agent_tools``.
    """
    assert set_turn_auth_block("wlo2.abc-def_123")
    fundstellen = {
        (werkzeug["function"]["name"], stillgelegt)
        for werkzeug in build_agent_tools()
        for text in _alle_texte(werkzeug)
        for stillgelegt in AUS_DEM_KATALOG
        if stillgelegt in text
    }
    assert not fundstellen, (
        "Diese angebotenen Werkzeuge verweisen auf ein stillgelegtes: "
        f"{sorted(fundstellen)}. Der Text muss den erreichbaren Weg nennen — "
        "sonst beschreibt er dem Modell eine Vorbedingung, die es nicht "
        "erfüllen kann."
    )


# ── Kurzfassung nach der Musterwahl (H8-2) ──────────────────────────────────
# ``waehle_vorgehen`` bleibt in JEDER eingeschraenkten Liste (virtuell, sonst
# kaeme der Lauf aus dem Muster nicht heraus) und schleppt damit seinen Katalog
# durch alle Runden: gemessen 25 251 von 31 742 Zeichen des Werkzeugsatzes nach
# der Wahl. Ab der zweiten Runde genuegt die Kurzfassung.


def _beschreibung(tools: list[dict], name: str) -> str:
    for t in tools:
        if t["function"]["name"] == name:
            return t["function"]["description"]
    raise AssertionError(f"{name} steht nicht in der Liste")


def test_die_vorgabe_bleibt_der_volle_katalog() -> None:
    """Die erste Runde muss waehlen koennen — dafuer braucht sie die
    Einsatzregeln. Nur der Weg NACH der Wahl schaltet um."""
    text = _beschreibung(build_agent_tools(muster_katalog=_katalog()), WAEHLE_VORGEHEN)
    assert "Einsetzen wenn" in text or "Thema ohne Filter" in text
    assert "### M06" in text


def test_die_kurzfassung_ist_deutlich_kleiner() -> None:
    voll = _beschreibung(build_agent_tools(muster_katalog=_katalog()), WAEHLE_VORGEHEN)
    kurz = _beschreibung(
        build_agent_tools(muster_katalog=_katalog(), katalog_kurz=True), WAEHLE_VORGEHEN)
    assert len(kurz) < len(voll)
    assert "### M06" not in kurz


def test_die_kurzfassung_nimmt_dem_lauf_keine_wahl() -> None:
    """Sparen darf die Beschreibung, nicht die Auswahl: das ``enum`` ist in
    beiden Fassungen dasselbe, sonst waere ein Muster nach der ersten Wahl
    unerreichbar."""
    for kurz in (False, True):
        tools = build_agent_tools(muster_katalog=_katalog(), katalog_kurz=kurz)
        props = tools[0]["function"]["parameters"]["properties"]
        assert props["muster_id"]["enum"] == ["M06", "M12"]


def test_die_kurzfassung_nennt_die_muster_weiter_mit_namen() -> None:
    kurz = _beschreibung(
        build_agent_tools(muster_katalog=_katalog(), katalog_kurz=True), WAEHLE_VORGEHEN)
    assert "M06" in kurz and "Material-Suche Cascade" in kurz
    assert "M12" in kurz and "Null-Treffer-Eskalation" in kurz
    assert "Krisen-Empathie" not in kurz


def test_die_kurzfassung_spricht_vom_WECHSELN() -> None:
    """Der Kopfsatz der Vollfassung fordert eine Wahl. Bliebe er stehen, forderte
    er sie ein zweites Mal — und ein Lauf, der schon waehlte, waehlte erneut."""
    kurz = _beschreibung(
        build_agent_tools(muster_katalog=_katalog(), katalog_kurz=True), WAEHLE_VORGEHEN)
    assert "wechsel" in kurz.lower()


# ── O-A: Werkzeug-Erlaubnis je Einbettung ────────────────────────────


def test_ohne_modus_bleibt_der_katalog_vollstaendig() -> None:
    assert set_turn_auth_block("wlo2.abc-def_123")
    assert _namen(build_agent_tools()) == _namen(build_agent_tools(tool_mode=None))
    assert _namen(build_agent_tools()) == _namen(build_agent_tools(tool_mode="full"))


def test_read_only_nimmt_die_schreibenden_werkzeuge_heraus() -> None:
    assert set_turn_auth_block("wlo2.abc-def_123")
    namen = _namen(build_agent_tools(tool_mode="read-only"))
    assert "wlo_add_to_collection" not in namen
    assert "wlo_create_content" not in namen
    assert "search_wlo_all" in namen
    assert "get_wikipedia_summary" in namen


def test_curate_laesst_schreiben_zu_und_den_blick_nach_draussen_nicht() -> None:
    assert set_turn_auth_block("wlo2.abc-def_123")
    namen = _namen(build_agent_tools(tool_mode="curate"))
    assert "wlo_add_to_collection" in namen
    assert "get_wikipedia_summary" not in namen
    assert "get_url_text" not in namen


def test_der_modus_erreicht_die_virtuellen_werkzeuge_nicht() -> None:
    """Sonst naehme eine Anzeige-Entscheidung dem Lauf seine Ziellinie."""
    muster = [PatternDef(id="M06", label="Suche", body_md="x")]
    namen = _namen(build_agent_tools(
        tool_mode="read-only", muster_katalog=muster,
        include_dokument=True, include_submit=True))
    assert WAEHLE_VORGEHEN in namen
    assert SUBMIT_RESULT in namen
    assert "zeige_dokument" in namen
