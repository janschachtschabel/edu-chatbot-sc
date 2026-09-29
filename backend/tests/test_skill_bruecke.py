"""E-6 — die Skill-Brücke im Muster-Modus (``domain/skill_bruecke.py``).

Im Muster-Modus legt das gewählte Muster die Werkzeuge fest, und nur sechs von
zwanzig Mustern führen ``get_skill_registry`` und ``get_skill``. Sind Skills im
Spiel, soll auch ein Such- oder Themenseiten-Muster sie laden können — wenn der
Betreiber es im Studio zugelassen hat (Vorgabe: aus).

Die zugeschalteten Werkzeuge stehen bewusst NEBEN ``tools``: diese Liste liest
die Reflexions-Schleife als Pflicht (``tool_loop``, ``force_tool_use``). Ein
Angebot darf dort nicht landen, sonst verlangte ein Muster mit
``requires_all_tools`` einen Skill-Abruf, und ein Suchmuster gälte schon mit
einem bloßen Katalog-Abruf als erfüllt.
"""

from __future__ import annotations

from boerdi.domain import skill_bruecke as sb


def _muster(*tools: str) -> dict:
    return {"tools": list(tools)}


def test_zugelassen_und_im_spiel_bekommt_ein_werkzeug_muster_beide_dazu():
    po = _muster("search_wlo_content", "get_node_details")
    zusatz = sb.zuschalten(po, zugelassen=True, im_spiel=True, gesperrt=[])
    assert zusatz == ["get_skill_registry", "get_skill"]
    assert po[sb.ZUSATZ_KEY] == ["get_skill_registry", "get_skill"]


def test_die_pflichtliste_der_reflexion_bleibt_unberuehrt():
    po = _muster("search_wlo_content")
    sb.zuschalten(po, zugelassen=True, im_spiel=True, gesperrt=[])
    assert po["tools"] == ["search_wlo_content"]


def test_ohne_zulassung_aendert_sich_nichts():
    """Die Vorgabe ist aus — ohne Pflege bleibt der Muster-Modus, wie er ist."""
    po = _muster("search_wlo_content")
    assert sb.zuschalten(po, zugelassen=False, im_spiel=True, gesperrt=[]) == []
    assert sb.ZUSATZ_KEY not in po


def test_ohne_skills_im_spiel_aendert_sich_nichts():
    """Kein Zug ohne freigegebene Skills zahlt für die zwei Beschreibungen."""
    po = _muster("search_wlo_content")
    assert sb.zuschalten(po, zugelassen=True, im_spiel=False, gesperrt=[]) == []
    assert sb.ZUSATZ_KEY not in po


def test_ein_muster_ohne_werkzeuge_bleibt_ohne():
    """M01–M04, M11, M13–M15 verbieten Werkzeugaufrufe in ihren eigenen Regeln —
    dazu gehören auch die Schutzantworten bei Krise und Drohung."""
    po = _muster()
    assert sb.zuschalten(po, zugelassen=True, im_spiel=True, gesperrt=[]) == []
    assert sb.ZUSATZ_KEY not in po


def test_ein_muster_mit_eigenen_skill_werkzeugen_bekommt_nichts_doppelt():
    po = _muster("get_skill_registry", "get_skill", "search_wlo_content")
    assert sb.zuschalten(po, zugelassen=True, im_spiel=True, gesperrt=[]) == []
    assert sb.ZUSATZ_KEY not in po


def test_eine_sperre_nimmt_die_bruecke_ganz_weg():
    """Die Werkzeug-Sperre aus Safety/Policy gilt auch hier. Eins der beiden
    allein wäre ein halber Weg: der Katalog ohne Wortlaut oder umgekehrt."""
    po = _muster("search_wlo_content")
    assert sb.zuschalten(po, zugelassen=True, im_spiel=True, gesperrt=["get_skill"]) == []
    assert sb.ZUSATZ_KEY not in po


def test_verfuegbar_zaehlt_eigene_und_zugeschaltete_werkzeuge():
    assert sb.verfuegbar(_muster("get_skill_registry", "get_skill"))
    zugeschaltet = _muster("search_wlo_content")
    sb.zuschalten(zugeschaltet, zugelassen=True, im_spiel=True, gesperrt=[])
    assert sb.verfuegbar(zugeschaltet)


def test_verfuegbar_verlangt_beide():
    assert not sb.verfuegbar(_muster("search_wlo_content"))
    assert not sb.verfuegbar(_muster("get_skill"))
    assert not sb.verfuegbar({})
