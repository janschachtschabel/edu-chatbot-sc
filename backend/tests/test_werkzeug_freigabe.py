"""Werkzeuge je MCP-Server ein- und ausschalten (Paket 7, S5 — Nutzer-Entscheid 2026-10-09).

Bis Paket 7 nahm eine feste Konstante (``AUS_DEM_KATALOG``) ``search_skill`` aus
jedem Pfad; abschalten ließ sich sonst nichts. Jetzt trägt jeder Server der
Registry ``werkzeuge_aus``: ohne Eintrag gilt die Vorgabe (``search_skill``
verborgen — Skills kommen über die Freigabeliste der Sammlung), eine gepflegte
Liste ersetzt sie.
"""

from __future__ import annotations

from boerdi.domain.werkzeug_freigabe import ohne_vorgabe, verborgen, wirksam_aus

_VORGABE = frozenset({"search_skill"})


def _primaer(**felder) -> dict:
    return {"id": "wlo-mcp", "tools": ["search_skill", "get_url_text", "search_wlo_all"],
            **felder}


def test_ohne_registry_gilt_die_vorgabe():
    assert verborgen([], primaer_id="wlo-mcp", vorgabe=_VORGABE) == _VORGABE


def test_ohne_eintrag_gilt_die_vorgabe():
    assert verborgen([_primaer()], primaer_id="wlo-mcp", vorgabe=_VORGABE) == _VORGABE


def test_eine_gepflegte_liste_ersetzt_die_vorgabe():
    # Leer = alles an, auch search_skill (im Studio eingeschaltet).
    assert verborgen([_primaer(werkzeuge_aus=[])], primaer_id="wlo-mcp",
                     vorgabe=_VORGABE) == frozenset()
    assert verborgen([_primaer(werkzeuge_aus=["get_url_text"])], primaer_id="wlo-mcp",
                     vorgabe=_VORGABE) == frozenset({"get_url_text"})


def test_ein_weiterer_server_verbirgt_nur_seine_werkzeuge():
    weiterer = {"id": "x", "tools": ["suche_x", "search_skill"]}
    assert verborgen([_primaer(werkzeuge_aus=[]), weiterer], primaer_id="wlo-mcp",
                     vorgabe=_VORGABE) == frozenset({"search_skill"})
    weiterer_aus = {"id": "x", "tools": ["suche_x"], "werkzeuge_aus": ["suche_x"]}
    assert verborgen([_primaer(werkzeuge_aus=[]), weiterer_aus], primaer_id="wlo-mcp",
                     vorgabe=_VORGABE) == frozenset({"suche_x"})


def test_ein_kaputter_eintrag_faellt_auf_die_vorgabe():
    # Die Registry schreibt das Studio über einen eigenen Endpunkt — ein Wert
    # anderer Form darf nicht still alles freischalten.
    assert verborgen([_primaer(werkzeuge_aus="search_skill")], primaer_id="wlo-mcp",
                     vorgabe=_VORGABE) == _VORGABE


def test_die_wirksame_liste_fuer_das_studio():
    assert wirksam_aus(_primaer(), primaer=True, vorgabe=_VORGABE) == ["search_skill"]
    assert wirksam_aus(_primaer(werkzeuge_aus=["b", "a"]), primaer=True,
                       vorgabe=_VORGABE) == ["a", "b"]
    assert wirksam_aus({"id": "x", "tools": ["suche_x"]}, primaer=False,
                       vorgabe=_VORGABE) == []


def test_die_vorgabe_wird_beim_speichern_nicht_festgeschrieben():
    """Review Paket 7, A-10: das Studio zeigt die Vorgabe als Liste an. Gespeichert
    hieße sie gepflegt — „fehlt = Vorgabe“ gälte nicht mehr, und eine spätere
    Änderung der Vorgabe erreichte die Anlage nie."""
    assert "werkzeuge_aus" not in ohne_vorgabe(
        _primaer(werkzeuge_aus=["search_skill"]), primaer=True, vorgabe=_VORGABE)
    # Alles eingeschaltet ist eine Entscheidung, keine Vorgabe.
    assert ohne_vorgabe(_primaer(werkzeuge_aus=[]), primaer=True,
                        vorgabe=_VORGABE)["werkzeuge_aus"] == []
    assert ohne_vorgabe(_primaer(werkzeuge_aus=["get_url_text"]), primaer=True,
                        vorgabe=_VORGABE)["werkzeuge_aus"] == ["get_url_text"]
    weiterer = {"id": "x", "tools": ["suche_x"], "werkzeuge_aus": []}
    assert "werkzeuge_aus" not in ohne_vorgabe(weiterer, primaer=False, vorgabe=_VORGABE)
    assert ohne_vorgabe(_primaer(), primaer=True, vorgabe=_VORGABE) == _primaer()



def test_der_schalter_eines_fremden_werkzeugs_verbirgt_kein_gleichnamiges_wlo_werkzeug():
    """Paket 11 (E): fremde Werkzeuge haben einen eigenen Namensraum; ihr Schalter gilt dort."""
    fremd = {"id": "andere", "tools": ["get_skill"], "werkzeuge_aus": ["get_skill"],
             "tool_schemas": [{"name": "get_skill", "read_only": True}]}
    assert "get_skill" not in verborgen([fremd], primaer_id="wlo-mcp", vorgabe=frozenset())


def test_ein_uebernommenes_search_skill_ist_nicht_von_haus_aus_aus():
    """Review Paket 11, #5: Studio und Laufzeit zeigen dieselbe Vorgabe — für übernommene Werkzeuge
    eines weiteren Servers keine."""
    fremd = {"id": "andere", "tools": ["search_skill"],
             "tool_schemas": [{"name": "search_skill", "read_only": True}]}
    assert wirksam_aus(fremd, primaer=False, vorgabe=frozenset({"search_skill"})) == []

