"""Paket U6 (Plan 2026-11-17, E12): der Ablauf „Themenbaum erstellen“ ohne Frage nach dem Weg.

Der Ort ist im Upload-Feld gewählt (``aktion: bereitgestellt``, ``ort``). Nach dem Upload verzweigt
``dateien_weg`` nur nach den Teilen der Auswahl (``block_id``):

- ``metadaten`` dazu (hier im Chat gelesen, ``quelle: chatbot``) → die Fragen (``wofuer``);
- ``ablage`` dazu (in WLO abgelegt) → Rückfrage und Kestra (``metadaten_frage``);
- nur ``struktur`` (Namen) → ``aus_dateien``.

Dazu: Angaben einer früheren Auswahl zählen nicht; auf dem Dokument-Weg bleibt der Entwurf der aus
dem Dokument, auch wenn das Feld daneben Inhalte las.
"""

from __future__ import annotations

import asyncio
import pathlib
from typing import Any

import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import simulation
from boerdi.services.ablauf.pruefung import MAX_SCHRITTE, pruefe, warnungen

_SEED = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml"
_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"
#: die ``block_id`` des Upload-Felds in der Simulation (wie in den Selbsttests des Seeds)
_FELD = "simulationuiupload"


def _ablauf() -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(_SEED.read_text(encoding="utf-8")))


def _auswahl(ort: str, **mehr: Any) -> dict[str, Any]:
    daten = {"aktion": "bereitgestellt", "ort": ort,
             "struktur": {"name": "Unterlagen", "dateien": 2, "alle_dateien": 2, "kinder": [],
                          "dateiliste": [
                              {"i": 0, "name": "Linsen.pdf", "endung": "pdf", "groesse": 10,
                               "rolle": "inhalt"},
                              {"i": 1, "name": "Spiegel.pdf", "endung": "pdf", "groesse": 10,
                               "rolle": "inhalt"}]},
             "zahlen": {"ordner": 1, "dateien": 2, "inhalte": 2, "ignoriert": 0,
                        "strukturdokumente": 0, "bytes": 20},
             "strukturdokument": None, "warnungen": []}
    daten.update(mehr)
    return daten


_ABLAGE_ZAHLEN = {"layout": "flach", "gesamt": 2, "abgelegt": 2, "unklar": 0, "fehler": 0,
                  "abgebrochen": 0, "ordner_verweigert": False, "vorgang_abgelegt": False}
_ABLAGE_TEIL = {"format": "wlo.ablage@1", "block_id": _FELD, "inhalte": [
    {"index": 0, "i": 0, "titel": "Linsen.pdf", "stand": "stored", "node_id": _A,
     "rolle": "inhalt"}]}


def _bis_nach_dem_upload(antwort: dict[str, Any], *, teile: dict[str, Any] | None = None,
                         angemeldet: bool = False) -> list[str]:
    """Der Weg bis zum nächsten Halt nach dem Upload auf dem Weg „Meine Dateien“."""
    test = AblaufTest.model_validate({
        "name": "U6", "angemeldet": angemeldet, "teile": teile or {},
        "eingaben": [{"bei": "einstieg", "option": "neu"},
                     {"bei": "grundlage", "option": "dateien"},
                     {"bei": "dateien_laden", "antwort": antwort}]})
    ergebnis = asyncio.run(simulation.testen(_ablauf(), test))
    return ergebnis.weg


# ── Gestalt des Seeds ───────────────────────────────────────────────────────────────────────────

def test_die_frage_nach_dem_weg_ist_entfallen():
    ablauf = _ablauf()
    ids = {s.id for s in ablauf.schritte}
    assert not ids & {"wlo_frage", "schnell", "schnell_da", "dateien_geladen"}
    assert len(ablauf.schritte) <= MAX_SCHRITTE
    assert pruefe(ablauf) == [] and warnungen(ablauf) == []
    schritte = _SEED.read_text(encoding="utf-8").split("\ntests:")[0]
    zeilen = [z for z in schritte.splitlines() if not z.lstrip().startswith("#")]
    # kein Schritt liest mehr, was nur die Frage nach dem Weg brauchte
    for alt in ("teil.weg", "ohne_gruendlich", "wlo_erschliessen"):
        assert not any(alt in z for z in zeilen), alt


def test_die_upload_schritte_nennen_den_neuen_knopf():
    ablauf = _ablauf()
    for sid in ("dokument_laden", "ordner_laden", "dateien_laden"):
        s = next(x for x in ablauf.schritte if x.id == sid)
        assert "„Hochladen“" in s.text["de"] and "“Upload”" in s.text["en"], sid
        for alt in ("Senden", "Lesen lassen", "übertr"):
            assert alt not in s.text["de"], (sid, alt)
        for alt in ("“Send”", "Read document", "transfer"):
            assert alt not in s.text["en"], (sid, alt)


# ── Verzweigung je Ort ──────────────────────────────────────────────────────────────────────────

def test_hier_im_chat_gelesen_fuehrt_direkt_zu_den_fragen():
    weg = _bis_nach_dem_upload(_auswahl("chat", dateien=[
        {"i": 0, "rolle": "inhalt", "upload_id": _A}]))
    assert weg[-3:] == ["dateien_laden", "dateien_weg", "wofuer"]


def test_in_wlo_abgelegt_fuehrt_zur_rueckfrage_vor_kestra():
    weg = _bis_nach_dem_upload(
        _auswahl("wlo", dateien=[{"i": 0, "rolle": "inhalt"}, {"i": 1, "rolle": "inhalt"}],
                 ablage=_ABLAGE_ZAHLEN),
        teile={"ablage": _ABLAGE_TEIL}, angemeldet=True)
    assert weg[-3:] == ["dateien_laden", "dateien_weg", "metadaten_frage"]


def test_nur_namen_fuehrt_zu_den_dateinamen():
    weg = _bis_nach_dem_upload(_auswahl("namen"))
    assert weg[-4:] == ["dateien_laden", "dateien_weg", "aus_dateien", "wofuer"]


def test_angaben_einer_frueheren_auswahl_zaehlen_nicht():
    """Lagen hier im Chat gelesene Angaben einer anderen Auswahl im Vorgang, nimmt der Ablauf bei
    „Nur Namen senden“ die Namen der neuen Auswahl — nicht die alten Angaben."""
    alt = {"format": "wlo.metadaten@1", "quelle": "chatbot", "block_id": "einfrueheresfeld01",
           "titel": "Inhalte aus 1 Dateien (1 gelesen)", "fehlend": [],
           "inhalte": [{"i": 0, "rolle": "inhalt", "titel": "Alt", "lesbar": True,
                        "upload_id": _B}]}
    weg = _bis_nach_dem_upload(_auswahl("namen"), teile={"metadaten": alt})
    assert weg[-4:] == ["dateien_laden", "dateien_weg", "aus_dateien", "wofuer"]


def test_dokument_weg_bleibt_beim_dokument_auch_mit_gelesenen_inhalten():
    """Hier im Chat liest das Feld neben dem Lehrplan auch Inhalte (``metadaten``) — der Entwurf
    kommt trotzdem aus dem Dokument, nicht aus den Inhalten."""
    [fall] = [t for t in _ablauf().tests if t.name == "Dokument hier im Chat lesen, mit Inhalt"]
    ergebnis = asyncio.run(simulation.testen(_ablauf(), fall))
    assert ergebnis.ok, ergebnis.abweichungen
    assert "entwurf_dokument" in ergebnis.weg
    assert not {"soll_ist", "soll_wenig", "entwurf_inhalte"} & set(ergebnis.weg)


def test_ordner_mit_unterordnern_bleibt_hier_im_chat_der_ordner_weg():
    [fall] = [t for t in _ablauf().tests if t.name == "Ordner hier im Chat, verfeinern"]
    ergebnis = asyncio.run(simulation.testen(_ablauf(), fall))
    assert ergebnis.ok, ergebnis.abweichungen
    assert ergebnis.weg[ergebnis.weg.index("ordner_geladen") + 1] == "aus_ordnern"


# ── Review U (19.11.), MAJOR 1: lokale ``metadaten`` gehören zu einer Auswahl ─────────────────────

_FREMD = {"format": "wlo.metadaten@1", "quelle": "chatbot", "block_id": "einfrueheresfeld01",
          "titel": "Inhalte aus 1 Dateien (1 gelesen)", "fehlend": [],
          "inhalte": [{"i": 0, "rolle": "inhalt", "titel": "Alt", "lesbar": True, "upload_id": _B}]}


def test_neu_und_anderes_waehlen_verwerfen_auch_die_angaben():
    """Lokale ``metadaten`` gehen mit in einen neuen Vorgang (``zug._bereitstellung``) — wer neu
    anfängt oder anderes wählt, verwirft sie mit der Auswahl."""
    schritte = {s.id: s for s in _ablauf().schritte}
    for schritt, option in (("einstieg", "neu"), ("einstieg_mit", "andere")):
        [o] = [o for o in schritte[schritt].optionen if o.id == option]
        assert "metadaten" in (o.verwirft or []), (schritt, option)


def test_selbsttests_der_drei_wege_tragen_angaben_im_vorgang():
    """Die Selbsttests der drei nachgestellten Wege (a: Dokument und Inhalt bereit, „Ja,
    verwenden“; b: fremde Angaben, Thema getippt; c: „Anderes wählen“) beginnen mit lokalen
    ``metadaten`` im Vorgang und enden beim Entwurf aus Dokument bzw. Thema."""
    namen = {"Dokument schon gelesen, verwenden": "entwurf_dokument",
             "Thema getippt bis zum Entwurf": "entwurf_thema",
             "Lerninhalte sind ein Thema": "entwurf_thema"}
    faelle = [t for t in _ablauf().tests if t.name in namen]
    assert len(faelle) == 3
    for fall in faelle:
        assert fall.teile["metadaten"]["quelle"] == "chatbot"
        ergebnis = asyncio.run(simulation.testen(_ablauf(), fall))
        assert ergebnis.ok, (fall.name, ergebnis.weg, ergebnis.abweichungen)
        assert namen[fall.name] in ergebnis.weg
        assert not {"soll_ist", "soll_wenig"} & set(ergebnis.weg)


def test_angaben_da_nimmt_nur_angaben_zur_auswahl():
    """Ohne Angaben aus WLO weiter: lagen hier im Chat gelesene Angaben einer anderen Auswahl im
    Vorgang, gelten die Dateinamen der neuen Auswahl."""
    test = AblaufTest.model_validate({
        "name": "U6", "angemeldet": True,
        "teile": {"ablage": _ABLAGE_TEIL, "metadaten": _FREMD},
        "werkzeuge": {"lesen": None},
        "eingaben": [{"bei": "einstieg", "option": "neu"},
                     {"bei": "grundlage", "option": "dateien"},
                     {"bei": "dateien_laden", "antwort": _auswahl(
                         "wlo", dateien=[{"i": 0, "rolle": "inhalt"}], ablage=_ABLAGE_ZAHLEN)},
                     {"bei": "metadaten_frage", "option": "nein"},
                     {"bei": "ohne_metadaten", "option": "ohne"}]})
    weg = asyncio.run(simulation.testen(_ablauf(), test)).weg
    assert weg[weg.index("angaben_da") + 1] == "aus_dateien"


def test_zum_entwurf_bindet_die_angaben_an_die_auswahl():
    """Liegen ``metadaten`` einer anderen Auswahl vor und ist weder Thema noch Dokument gewählt,
    fragt der Ablauf nicht nach Soll/Ist (das ginge um fremde Dateien)."""
    datei = {"i": 0, "name": "L.pdf", "endung": "pdf", "groesse": 10, "rolle": "inhalt"}
    struktur = {"block_id": "b0000009", "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1},
                "warnungen": [],
                "struktur": {"name": "U", "dateien": 1, "kinder": [], "dateiliste": [datei]}}
    test = AblaufTest.model_validate({
        "name": "U6", "angemeldet": False, "ab": "zum_entwurf",
        "teile": {"metadaten": {**_FREMD, "inhalte": _FREMD["inhalte"] * 5}, "struktur": struktur}})
    weg = asyncio.run(simulation.testen(_ablauf(), test)).weg
    assert weg[:2] == ["zum_entwurf", "entwurf_thema"]
