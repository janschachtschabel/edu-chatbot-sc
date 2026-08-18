"""J1 — das Ergebnis als eigener Kanal.

Gepinnt wird, was die gemessene Lücke geschlossen hat: dass das Werkzeug **kein**
``text``-Feld mehr trägt (die Nachbarschaft war die Ursache), dass es die Prosa
ausdrücklich einfordert, und dass ein unbrauchbares Argument den Lauf nicht
abbricht.
"""

from __future__ import annotations

from boerdi.domain import result_delivery as rd


def _funktion(werkzeug: dict) -> dict:
    return werkzeug["function"]


def test_traegt_nur_das_ergebnis_und_keinen_text() -> None:
    # Der Kern des Umbaus. Ein ``text``-Feld daneben stellte die Antwort für den
    # Menschen wieder in denselben Aufruf — gemessen 196 gegen 1932 Zeichen.
    f = _funktion(rd.ergebnis_werkzeug())
    assert set(f["parameters"]["properties"]) == {"result"}
    assert f["parameters"]["required"] == ["result"]


def test_beschreibung_verlangt_die_volle_antwort_danach() -> None:
    # Ohne diesen Satz wiederholte das Werkzeug die Lücke: das Modell hielte die
    # Lieferung für die Antwort. Der Gegensatz zu ``zeige_dokument`` (dort ist
    # die Prosa absichtlich ein Begleitsatz) haengt an genau dieser Stelle.
    beschreibung = _funktion(rd.ergebnis_werkzeug())["description"]
    assert "NICHT" in beschreibung
    assert "VOLLSTAENDIG" in beschreibung


def test_schema_des_gastgebers_reist_woertlich_ein() -> None:
    schema = {"type": "object", "properties": {"note": {"type": "integer"}},
              "required": ["note"]}
    f = _funktion(rd.ergebnis_werkzeug(schema))
    assert f["parameters"]["properties"]["result"] is schema


def test_ohne_schema_ein_freies_objekt() -> None:
    f = _funktion(rd.ergebnis_werkzeug())
    assert f["parameters"]["properties"]["result"]["type"] == "object"


def test_liest_das_objekt_aus_den_argumenten() -> None:
    assert rd.ergebnis_aus_argumenten({"result": {"note": 4}}) == {"note": 4}


def test_nicht_objekte_gelten_als_unbrauchbar() -> None:
    # ``ChatResponse.result`` ist ``dict | None`` — eine Liste kaeme beim
    # Gastgeber nie an. Sie abzuweisen sagt dem Modell, dass etwas nicht stimmt.
    assert rd.ergebnis_aus_argumenten({"result": [1, 2]}) is None
    assert rd.ergebnis_aus_argumenten({"result": "fertig"}) is None
    assert rd.ergebnis_aus_argumenten({}) is None
    assert rd.ergebnis_aus_argumenten("kein dict") is None
