"""Paket A2a: Auslöser ``agent`` — die KI schlägt einen Ablauf vor, gestartet wird per Knopf.

Das Werkzeug ``ablauf_vorschlagen`` gibt es nur, wenn ein aktiver Ablauf den Auslöser ``agent``
trägt; seine Kennungen stehen als Aufzählung im Schema. Es startet nichts: die Schleife merkt sich
die Kennung (einmal je Zug), und die Zusammenstellung hängt die Schnellantwort
``__action__|<Titel>|ablauf_starten|{"ablauf": …}`` an — die KI schreibt nie selbst einen Knopf.
"""

from __future__ import annotations

import json

import pytest

from boerdi.services.ablauf import ausloeser, vorschlag
from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call

_SCHRITTE = [{"id": "a", "typ": "nachricht", "text": {"de": "Los."}}, {"id": "e", "typ": "ende"}]


def _roh(id_, aktiv=True, art="agent", **mehr):
    return {"id": id_, "titel": {"de": f"Titel {id_}", "en": f"Title {id_}"}, "aktiv": aktiv,
            "wann": [f"wenn {id_}"], "nicht_wann": [f"nicht {id_}"], "schritte": _SCHRITTE,
            "ausloeser": [{"art": art}], **mehr}


@pytest.fixture
def katalog(monkeypatch):
    eintraege: list = []
    monkeypatch.setattr(ausloeser, "area", lambda key: {"ablaeufe": eintraege}
                        if key == ausloeser.BEREICH else {})
    return eintraege


def test_ohne_vorschlagbaren_ablauf_kein_werkzeug(katalog):
    katalog += [_roh("aus", aktiv=False), _roh("knopf", art="knopf")]
    assert vorschlag.werkzeug("de") is None


def test_das_werkzeug_nennt_die_ablaeufe_und_zaehlt_ihre_kennungen_auf(katalog):
    katalog += [_roh("baum"), _roh("aus", aktiv=False)]
    w = vorschlag.werkzeug("de")
    assert w["function"]["name"] == vorschlag.NAME
    assert w["function"]["parameters"]["properties"]["ablauf"]["enum"] == ["baum"]
    beschreibung = w["function"]["description"]
    assert "Titel baum" in beschreibung and "wenn baum" in beschreibung
    assert "nicht baum" in beschreibung and "aus" not in w["function"]["parameters"][
        "properties"]["ablauf"]["enum"]


def test_die_schnellantwort_startet_den_ablauf_per_knopf(katalog):
    katalog.append(_roh("baum", titel={"de": "Baum | aus Ordnern"}))
    [qr] = vorschlag.schnellantworten(["baum", "fehlt"], "de")
    praefix, label, aktion, params = qr.split("|", 3)
    assert praefix == "__action__" and aktion == "ablauf_starten"
    assert "|" not in label and label.startswith("Baum")
    assert json.loads(params) == {"ablauf": "baum"}


def test_die_schnellantwort_folgt_der_sprache(katalog):
    katalog.append(_roh("baum"))
    assert "Title baum" in vorschlag.schnellantworten(["baum"], "en")[0]


def test_der_vorschlag_steht_vor_den_anderen_schnellantworten():
    neu = vorschlag.anhaengen(["a", "b", "c", "d"], ["__action__|X|ablauf_starten|{}"])
    assert neu[0].startswith("__action__") and len(neu) == 4
    assert vorschlag.anhaengen(["a"], None) == ["a"]


def test_die_schleife_merkt_sich_den_vorschlag_ohne_mcp(monkeypatch, katalog):
    katalog.append(_roh("baum"))
    werkzeug = vorschlag.werkzeug("de")
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(vorschlag.NAME, {"ablauf": "baum"}),
                     _tool_call(vorschlag.NAME, {"ablauf": "baum"}, "c2")]),
        _resp_text("Du kannst den Ablauf mit dem Knopf starten."),
    ], tools=[werkzeug])
    assert run.ablauf_vorschlaege == ["baum"] and run.tools_called == []
    assert "Knopf" in msgs[2]["content"]


def test_eine_unbekannte_kennung_wird_abgewiesen(monkeypatch, katalog):
    katalog.append(_roh("baum"))
    werkzeug = vorschlag.werkzeug("de")
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(vorschlag.NAME, {"ablauf": "boese"})]),
        _resp_text("ok"),
    ], tools=[werkzeug])
    assert run.ablauf_vorschlaege == []
    assert "boese" in msgs[2]["content"] and "Knopf" not in msgs[2]["content"]


# ── Review A2a, Befund 6/9 und Vorbefund ─────────────────────────────────────────────────────

def test_der_knopf_achtet_die_hoechstzahl_des_gastgebers():
    assert vorschlag.anhaengen(["a", "b", "c"], ["K"], hoechstens=2) == ["K", "a"]


def test_ein_leerer_titel_wird_die_kennung(katalog):
    katalog.append(_roh("baum", titel={"de": "   "}))
    [qr] = vorschlag.schnellantworten(["baum"], "de")
    assert qr.split("|")[1] == "baum"


def test_ki_schnellantworten_tragen_keine_knoepfe():
    from boerdi.services.quick_replies_llm import filtere_vorschlaege

    behalten = filtere_vorschlaege(
        ["Mehr zu Optik", '__action__|Los|curate_collection|{"x": 1}', "__auth__"],
        anzahl=4, max_zeichen=0)
    assert behalten == ["Mehr zu Optik"]


def test_nach_einer_frage_kein_vorschlag(monkeypatch, katalog):
    """Review A2a, Befund 5: unter einer offenen Frage erschiene der Knopf nie."""
    katalog.append(_roh("baum"))
    frage = {"frage": "Wie weiter?", "optionen": [{"id": "a", "label": "A"},
                                                  {"id": "b", "label": "B"}]}
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ui_entscheidung", frage),
                     _tool_call(vorschlag.NAME, {"ablauf": "baum"}, "c2")]),
        _resp_text("ok"),
    ], tools=[vorschlag.werkzeug("de"), "ui_entscheidung"])
    assert run.ui_bloecke and run.ablauf_vorschlaege == []
    assert "Knopf" not in msgs[3]["content"]
