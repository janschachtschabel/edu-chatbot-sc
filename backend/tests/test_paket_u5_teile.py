"""Paket U3/U5 (Plan 2026-11-17, E11): Antwort ``bereitgestellt`` → Teile im Vorgang, je Ort.

- ``chat``: ``structure``/``struktur`` (immer), ``strukturdokument`` (``quelle: chatbot``) und
  ``metadaten`` (``wlo.metadaten@1``, ``quelle: chatbot``) — der Server rechnet ``metadaten`` beim
  Speichern aus den gespeicherten Kurzangaben neu, nie aus Angaben des Browsers;
- ``wlo``: nur die Auswahl (``ablage`` schreibt der Ablage-Endpunkt);
- ``namen``: nur die Auswahl.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.services import arbeitsstand_teile as at
from boerdi.services.ablauf import metadaten
from boerdi.services.dokumente import metadaten_lokal as ml
from tests.test_paket_u4_orte import _A, _B, ABLAGE, CHAT_DATEIEN, bereitgestellt


def _geprueft(daten: dict) -> dict:
    return {"modul": "ui_upload", "block_id": "b0000001", "daten": daten}


def _namen(teile) -> list[str]:
    return [t[0] for t in teile]


def test_ort_chat_ergibt_struktur_strukturdokument_und_metadaten():
    teile = at.teile_aus_antwort(_geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN)))
    assert _namen(teile) == ["structure", "struktur", "strukturdokument", "metadaten"]
    sd = dict((t[0], t[2]) for t in teile)["strukturdokument"]
    assert sd["dokumente"] == [{"quelle": "chatbot", "ref": f"dokument:{_B}",
                                "name": "Lehrplan.pdf"}]
    wert = dict((t[0], t[2]) for t in teile)["metadaten"]
    assert wert["format"] == metadaten.FORMAT and wert["quelle"] == "chatbot"
    assert wert["block_id"] == "b0000001"
    # nur Inhalte; der gelesene mit Verweis, der nicht lesbare mit Titel aus dem Namen
    assert [(e["i"], e["lesbar"], e.get("upload_id")) for e in wert["inhalte"]] == [
        (0, True, _A), (1, False, None)]
    assert wert["inhalte"][1]["titel"] == "Folien"


@pytest.mark.parametrize("daten", [
    bereitgestellt("wlo", dateien=[{"i": 0, "rolle": "inhalt"}], ablage=ABLAGE),
    bereitgestellt("namen"),
])
def test_ort_wlo_und_namen_ergeben_nur_die_auswahl(daten):
    assert _namen(at.teile_aus_antwort(_geprueft(daten))) == ["structure", "struktur"]


def _zeile(kennung, angaben=None, rolle="inhalt"):
    befund = {"rolle": rolle}
    if angaben is not None:
        befund["angaben"] = angaben
    return SimpleNamespace(id=kennung, name="x", befund=befund)


def test_der_server_rechnet_die_angaben_aus_der_datenbank_neu():
    roh = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        _geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN))))["metadaten"]
    roh["inhalte"][0]["titel"] = "Vom Browser erfunden"
    roh["inhalte"][0]["beschreibung"] = "unterschoben"
    angaben = {"titel": "Linsen im Alltag", "beschreibung": "Sammellinsen",
               "schlagworte": ["Optik"], "fach": "Physik", "stufe": "Sekundarstufe I"}
    neu, kurz = ml.neu_berechnet(roh, [_zeile(_A, angaben)])
    e = neu["inhalte"][0]
    assert (e["titel"], e["beschreibung"], e["schlagworte"]) == (
        "Linsen im Alltag", "Sammellinsen", ["Optik"])
    assert e["faecher"] == ["Physik"] and e["stufen"] == ["Sekundarstufe I"]
    assert e["lesbar"] is True and e["upload_id"] == _A
    assert "2" in kurz and "1 gelesen" in kurz


def test_unbekannte_oder_fremde_kennung_gilt_als_nicht_gelesen():
    roh = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        _geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN))))["metadaten"]
    # die Kennung gehört einem Strukturdokument — kein Inhalt
    neu, _ = ml.neu_berechnet(roh, [_zeile(_A, rolle="struktur")])
    e = neu["inhalte"][0]
    assert e["lesbar"] is False and "upload_id" not in e and e["titel"] == "Linsen"


def test_gelesen_ohne_angaben_titel_aus_dem_namen():
    roh = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        _geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN))))["metadaten"]
    neu, _ = ml.neu_berechnet(roh, [_zeile(_A)])
    assert neu["inhalte"][0]["titel"] == "Linsen" and neu["inhalte"][0]["lesbar"] is True


def test_das_format_liest_als_dokument_fuer_aus_inhalten():
    roh = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        _geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN))))["metadaten"]
    neu, _ = ml.neu_berechnet(roh, [_zeile(_A, {"titel": "Linsen im Alltag",
                                                 "beschreibung": "Sammellinsen",
                                                 "schlagworte": ["Optik"]})])
    dok = metadaten.als_dokument(neu)
    assert dok is not None
    assert [a.titel for a in dok.abschnitte] == ["Linsen im Alltag", "Folien"]
    assert "Sammellinsen" in dok.markdown and "Schlagworte: Optik" in dok.markdown


def test_ein_grosser_teil_bleibt_unter_der_grenze():
    viele = [{"i": n, "name": f"Datei mit einem recht langen Namen Nummer {n}.pptx",
              "endung": "pptx", "groesse": 1, "rolle": "inhalt"} for n in range(500)]
    struktur = {"name": "A" * 100, "dateien": 500, "alle_dateien": 500, "kinder": [],
                "dateiliste": viele}
    wert = ml.aus_antwort({"struktur": struktur, "dateien": []}, "b0000001")
    assert ml._groesse(wert) <= metadaten.MAX_TEIL
    assert len(wert["inhalte"]) + int(wert.get("ausgelassen") or 0) == 500


def test_arbeitsstand_speichert_metadaten_nur_neu_berechnet(monkeypatch):
    """``_speichern`` ersetzt den Teil des Browsers durch den des Servers (Kurzangaben aus der
    Datenbank, nur Inhalte dieser Sitzung)."""
    from boerdi.services import arbeitsstand

    gesetzt: dict = {}
    vorgang = SimpleNamespace(id="v1", status="offen")

    async def lesen(s, vid, aufrufer):
        return vorgang

    async def teil_setzen(s, v, name, *, typ, wert, zusammenfassung, tage):
        gesetzt[name] = wert
        return v

    async def teil_wert(s, v, name):
        return None

    async def zeilen(s, session_id, merk, rolle="struktur"):
        assert rolle is None
        return [_zeile(_A, {"titel": "Aus der DB", "beschreibung": "", "schlagworte": []}),
                _zeile(_B, rolle="struktur")]

    monkeypatch.setattr(arbeitsstand.vorgaenge, "lesen", lesen)
    monkeypatch.setattr(arbeitsstand.vorgaenge, "teil_setzen", teil_setzen)
    monkeypatch.setattr(arbeitsstand.vorgaenge, "teil_wert", teil_wert)
    monkeypatch.setattr(arbeitsstand, "_lesbare_zeilen", zeilen)
    monkeypatch.setattr(arbeitsstand, "verweis", lambda e, a: {"id": "v1"})
    monkeypatch.setattr(arbeitsstand, "tage", lambda: 8)
    teile = [t for t in at.teile_aus_antwort(
        _geprueft(bereitgestellt("chat", dateien=CHAT_DATEIEN))) if t[0] == "metadaten"]
    asyncio.run(arbeitsstand._speichern(None, "s1", {}, teile))
    assert gesetzt["metadaten"]["inhalte"][0]["titel"] == "Aus der DB"
