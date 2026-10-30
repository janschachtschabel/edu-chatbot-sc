"""Paket 18C/D (2.5): Helfer für Logzeilen ohne Inhalt.

Das Log sagt, dass etwas geschah und wie lange; was, steht im gespeicherten Zug (Zugakte), und
die Trace-ID verbindet beides. Freitext erscheint deshalb nur als Länge, eine Sitzung nur als
Kurzkennung — die Sitzungs-ID selbst wirkt wie ein Schlüssel zum Verlauf. Filterwerte (Fach,
Stufe, Typ, Lizenz, Kennungen) bleiben: sie tragen keine Personendaten, und Filterfehler sind
der häufigste Fehlertyp.
"""

from __future__ import annotations

import hashlib
import json
import logging

import pytest

from boerdi.obs import log_inhalt
from boerdi.obs.log_format import JsonFormatter


@pytest.mark.parametrize("text,erwartet", [
    ("Hallo", "‹5 Zeichen›"), ("", "‹0 Zeichen›"), (None, "‹0 Zeichen›"),
])
def test_inhalt_nur_als_laenge(text, erwartet):
    assert log_inhalt.inhalt(text) == erwartet


def test_kennung_ist_ein_kurzer_fester_hash():
    sid = "bb-0123456789abcdef0123456789abcdef"
    assert log_inhalt.kennung(sid) == hashlib.sha256(sid.encode()).hexdigest()[:8]
    assert log_inhalt.kennung(sid) == log_inhalt.kennung(sid)
    assert sid not in log_inhalt.kennung(sid)
    assert log_inhalt.kennung("") == log_inhalt.kennung(None) == "-"


def test_filterwerte_behalten_filter_und_kennungen_freitext_nur_als_laenge():
    args = {
        "query": "Klimawandel", "url": "https://de.wikipedia.org/wiki/Optik",
        "discipline": "Physik", "educationalContext": "Sekundarstufe I",
        "learningResourceType": ["Video", "Arbeitsblatt"], "maxResults": 5,
        "includeTextContent": True, "nodeId": "a1b2-c3", "outputFormat": "json",
        "excludeNodeIds": [f"id-{i}" for i in range(200)], "confirmToken": "geheim",
        "metadata": {"title": "Entwurf"}, "unbekannt": "frei",
    }
    assert log_inhalt.filterwerte(args) == {
        "query": "‹11 Zeichen›", "url": "‹35 Zeichen›",
        "discipline": "Physik", "educationalContext": "Sekundarstufe I",
        "learningResourceType": ["Video", "Arbeitsblatt"], "maxResults": 5,
        "includeTextContent": True, "nodeId": "a1b2-c3", "outputFormat": "json",
        "excludeNodeIds": "‹200 Einträge›", "confirmToken": "‹geschwärzt›",
        "metadata": "‹1 Einträge›", "unbekannt": "‹4 Zeichen›",
    }


def test_filterwerte_ohne_dict_leer():
    assert log_inhalt.filterwerte("frei") == {}


def test_ein_ereignis_ist_eine_zeile_mit_feldern(caplog):
    lg = logging.getLogger("boerdi.test.ereignis")
    with caplog.at_level(logging.INFO, logger="boerdi.test.ereignis"):
        log_inhalt.ereignis(lg, "mcp_aufruf", werkzeug="search_wlo_content", status="ok",
                            dauer_ms=812)
    (rec,) = caplog.records
    assert rec.getMessage() == "mcp_aufruf werkzeug=search_wlo_content status=ok dauer_ms=812"
    assert rec.levelno == logging.INFO
    zeile = json.loads(JsonFormatter().format(rec))
    assert zeile["event"] == "mcp_aufruf"
    assert zeile["fields"] == {"werkzeug": "search_wlo_content", "status": "ok", "dauer_ms": 812}


def test_ein_ereignis_auf_debug(caplog):
    lg = logging.getLogger("boerdi.test.ereignis")
    with caplog.at_level(logging.DEBUG, logger="boerdi.test.ereignis"):
        log_inhalt.ereignis(lg, "zugriff", stufe=logging.DEBUG, route="/widget/{pfad}")
    assert caplog.records[0].levelno == logging.DEBUG


def test_gewoehnliche_zeilen_im_json_ohne_felder():
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "frei %s", ("z",), None)
    zeile = json.loads(JsonFormatter().format(rec))
    assert "event" not in zeile and "fields" not in zeile


def test_fehlerorte_ohne_eingabewert():
    from pydantic import BaseModel, ValidationError

    class M(BaseModel):
        anzahl: int

    with pytest.raises(ValidationError) as fehler:
        M.model_validate({"anzahl": "Meine Frage KANARIE7Q"})
    text = log_inhalt.fehlerorte(fehler.value)
    assert text == "anzahl (int_parsing)"


def test_formatierer_schwaerzen_eingabewerte_aus_pruefungen():
    """Review Phase 2: ein Prüffehler, der bis zu einem allgemeinen Fänger läuft, zeigte im
    Text ``input_value=…`` — die Formatierer schwärzen ihn."""
    import sys

    from pydantic import BaseModel, ValidationError

    from boerdi.obs.log_format import text_formatter

    class M(BaseModel):
        anzahl: int

    # Als Variable: im Traceback stünde sonst die Quelltextzeile samt Wort — im Betrieb zeigt
    # ein Traceback Code, keine Eingaben.
    eingabe = "Meine Frage KANARIE7Q"
    try:
        M.model_validate({"anzahl": eingabe})
    except ValidationError:
        info = sys.exc_info()
    satz = logging.LogRecord("x", logging.ERROR, __file__, 1, "fehler: %s", (info[1],), info)
    satz.trace_id = "-"  # setzt im Betrieb ``TraceIdFilter``
    for formatierer in (JsonFormatter(), text_formatter()):
        zeile = formatierer.format(satz)
        assert "KANARIE7Q" not in zeile and "int_parsing" in zeile
