"""Plan 2026-11-16, TG-3a: der Teil ``struktur`` (``wlo.auswahl@1``) — der Ordnerbaum mit den
Dateien je Ordner.

- ``ui_upload`` schickt je Ordner seine Dateien (``dateiliste``: feste Nummer ``i``, Name, Endung,
  Größe, Rolle); Antworten ohne Dateien (Widget vor TG-3a) bleiben gültig.
- ``teile_aus_antwort`` schreibt ``struktur`` (voller Baum) und weiter ``structure`` (nur Ordner,
  wie vorher) — bestehende Abläufe und ``strukturentwurf_aus_ordnern`` laufen weiter.
- Die KI sieht nur eine Zusammenfassung, keine Namen; die Sicherheitsprüfung liest die Namen,
  gedeckelt; Dateinamen kommen nicht ins Log.
- ``bereitgestellt`` zählt ``dateien`` und ``inhaltsdateien``.
"""

from __future__ import annotations

import asyncio
import logging

from boerdi.api.schemas_ui import UiAntwort, UiBlock
from boerdi.services import arbeitsstand_teile
from boerdi.services.ablauf import typen, werkzeuge
from boerdi.ui_module import antwort, katalog
from boerdi.ui_module import upload_antwort as upload
from boerdi.ui_module.namen import UPLOAD


def _datei(i: int, name: str, rolle: str = "inhalt", groesse: int = 10) -> dict:
    endung = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {"i": i, "name": name, "endung": endung, "groesse": groesse, "rolle": rolle}


def _ohne_name(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "name"}


def _daten(aktion: str = "erfasst") -> dict:
    """Physik 7 mit Lehrplan (Struktur), zwei Unterordnern und einer ignorierten Datei."""
    return {
        "aktion": aktion,
        "struktur": {"name": "Physik 7", "dateien": 1, "alle_dateien": 4,
                     "dateiliste": [_datei(5, "Lehrplan.pdf", "struktur")],
                     "kinder": [
                         {"name": "Mechanik", "dateien": 2, "alle_dateien": 2, "kinder": [],
                          "dateiliste": [_datei(0, "Hebel.pdf"), _datei(1, "Kraft.docx")]},
                         {"name": "Optik", "dateien": 1, "alle_dateien": 1, "kinder": [],
                          # Review TG-3a–c, R3-4: eine ignorierte Datei ohne Namen
                          "dateiliste": [_datei(3, "Linsen.pdf"),
                                         _ohne_name(_datei(4, "alt.tmp", "ignorieren"))]}]},
        # R3-2: ``i`` ist kleiner als die Zahl aller erfassten Dateien (Nummer 2 war eine
        # Systemdatei, sie steht nicht in der Liste)
        "zahlen": {"ordner": 3, "dateien": 6, "inhalte": 3, "ignoriert": 1,
                   "strukturdokumente": 1, "bytes": 40},
        "strukturdokument": {"name": "Lehrplan.pdf", "groesse": 10, "endung": "pdf"},
        "warnungen": [],
    }


def _ohne_dateien(d: dict) -> dict:
    return {**{k: v for k, v in d.items() if k != "dateiliste"},
            "kinder": [_ohne_dateien(k) for k in d["kinder"]]}


def _pruefe(daten: dict) -> dict | None:
    block = UiBlock(block_id="b0000001", modul=UPLOAD, version=1, art="abfragen",
                    daten={"zweck": "bereitstellen"}, text="t", status="offen")
    entities: dict = {}
    antwort.merke_frage(entities, block)
    return antwort.antwort_pruefen(entities[antwort.OFFENE_FRAGE],
                                   UiAntwort(block_id="b0000001", daten=daten))


def _viele(n: int, name=lambda i: f"d{i:04d}.pdf") -> dict:
    daten = _daten()
    daten["struktur"] = {"name": "P", "dateien": n, "alle_dateien": n, "kinder": [],
                         "dateiliste": [_datei(i, name(i)) for i in range(n)]}
    daten["zahlen"] = {**daten["zahlen"], "ordner": 1, "dateien": n, "inhalte": n,
                       "ignoriert": 0, "strukturdokumente": 0}
    daten["strukturdokument"] = None
    return daten


# ── Antwortform ──────────────────────────────────────────────────────────────────────────────────

def test_die_antwort_mit_dateien_ist_gueltig_und_die_alte_ohne_auch():
    assert _pruefe(_daten()) is not None
    alt = _daten()
    alt["struktur"] = _ohne_dateien(alt["struktur"])
    assert _pruefe(alt) is not None, "Antworten vor TG-3a bleiben gültig"


def test_das_manifest_erlaubt_den_teil_struktur():
    schreibt = katalog.katalog()[UPLOAD]["vorgang"]["schreibt"]
    # TG-3d: dazu ``strukturdokument`` (die Verweise auf alle gelesenen Strukturdokumente)
    # Paket U5 (Plan 2026-11-17): dazu ``metadaten`` (quelle chatbot, „Hier im Chat“)
    assert schreibt == ["structure", "struktur", "document", "strukturdokument", "metadaten"]


def test_namen_gekuerzt_ist_eine_bekannte_warnung():
    daten = _daten()
    daten["warnungen"] = ["namen_gekuerzt"]
    assert _pruefe(daten) is not None


def test_hoechstens_fuenfhundert_dateien_und_jede_nummer_einmal():
    assert _pruefe(_viele(500)) is not None
    # über alle Ordner zusammen — das Schema deckelt nur je Ordner
    zu_viele = _viele(500)
    zu_viele["struktur"]["kinder"] = [{"name": "X", "dateien": 1, "alle_dateien": 1, "kinder": [],
                                       "dateiliste": [_datei(500, "x.pdf")]}]
    assert upload.grund(zu_viele) == "zu viele Dateien"
    assert _pruefe(zu_viele) is None
    doppelt = _daten()
    doppelt["struktur"]["kinder"][1]["dateiliste"][0]["i"] = 0
    assert upload.grund(doppelt) == "Nummer einer Datei doppelt"
    assert _pruefe(doppelt) is None
    # zwei Strukturdokumente in den Listen, gezählt ist eins
    zwei = _daten()
    zwei["struktur"]["kinder"][0]["dateiliste"][0]["rolle"] = "struktur"
    assert upload.grund(zwei) == "Strukturdokument in der Liste ohne Zahl"


def test_dateinamen_mit_zeilenumbruch_oder_zu_lang_weist_das_schema_ab():
    for name in ("a\nb.pdf", "x" * 121):
        daten = _daten()
        daten["struktur"]["dateiliste"][0]["name"] = name
        assert _pruefe(daten) is None, name


def test_dateinamen_kommen_nicht_ins_log(caplog):
    doppelt = _daten()
    doppelt["struktur"]["kinder"][1]["dateiliste"][0]["i"] = 0
    doppelt["struktur"]["kinder"][0]["dateiliste"][0]["name"] = "Zeugnis_Mustermann.pdf"
    with caplog.at_level(logging.DEBUG):
        assert _pruefe(doppelt) is None
        geprueft = _pruefe(_daten())
        arbeitsstand_teile.teile_aus_antwort(geprueft)
        antwort.antwort_block(geprueft)
    assert "Mustermann" not in caplog.text and "Hebel" not in caplog.text


# ── Teile: ``struktur`` und die Sicht ``structure`` ─────────────────────────────────────────────

def test_struktur_traegt_den_vollen_baum_structure_bleibt_nur_mit_ordnern():
    geprueft = _pruefe(_daten())
    teile = {t[0]: t for t in arbeitsstand_teile.teile_aus_antwort(geprueft)}
    assert set(teile) == {"structure", "struktur"}
    _n, typ, wert, kurz = teile["struktur"]
    assert typ == "wlo.auswahl@1" == typen.AUSWAHL == arbeitsstand_teile.AUSWAHL
    assert wert["struktur"]["kinder"][0]["dateiliste"][1] == _datei(1, "Kraft.docx")
    assert wert["zahlen"]["inhalte"] == 3 and wert["warnungen"] == []
    assert kurz == "4 Dateien in 3 Ordnern, davon 1 Strukturdokument"
    _n, typ, wert, kurz = teile["structure"]
    assert typ == "wlo.ordnerbaum@1" and kurz == "3 Ordner, 3 Inhalte"
    assert "dateiliste" not in str(wert)
    assert wert["struktur"] == _ohne_dateien(_daten()["struktur"])


def test_eine_alte_antwort_ergibt_nur_structure():
    alt = _daten()
    alt["struktur"] = _ohne_dateien(alt["struktur"])
    assert [t[0] for t in arbeitsstand_teile.teile_aus_antwort(_pruefe(alt))] == ["structure"]


def test_ein_gelesenes_dokument_kommt_dazu():
    daten = _daten("dokument")
    daten["dokument"] = {"upload_id": "11111111-1111-4111-8111-111111111111",
                         "name": "Lehrplan.pdf", "format": "pdf", "vorschau": [],
                         "befund": {"seiten": 3, "woerter": 100, "abschnitte": 4,
                                    "gliederung_art": "ueberschriften", "warnungen": []}}
    namen = [t[0] for t in arbeitsstand_teile.teile_aus_antwort(_pruefe(daten))]
    assert namen == ["structure", "struktur", "document", "strukturdokument"]


def test_die_kurzbeschreibung_in_einzahl_und_ohne_ordner():
    lose = _viele(1)
    lose["struktur"]["name"] = ""
    lose["zahlen"]["ordner"] = 0
    assert upload.dateien_satz(lose) == "1 Datei ohne Ordner"
    assert upload.dateien_satz(_viele(2)) == "2 Dateien in 1 Ordner"


def test_struktur_ist_bereitstellung_und_ein_bekannter_modul_teil():
    assert arbeitsstand_teile.BEREITSTELLUNG == ("structure", "struktur", "document",
                                                 "strukturdokument")
    assert typen.MODUL_TEILE["struktur"] == typen.AUSWAHL
    assert typen.modul_teile(katalog.katalog(), UPLOAD)["struktur"] == "wlo.auswahl@1"


# ── Was die KI und die Sicherheitsprüfung sehen ──────────────────────────────────────────────────

def test_die_ki_sieht_eine_zusammenfassung_keine_dateinamen():
    block = antwort.antwort_block(_pruefe(_daten()))
    assert "Dateien: 4 Dateien in 3 Ordnern, davon 1 Strukturdokument." in block
    for name in ("Hebel", "Kraft", "Linsen", "alt.tmp"):
        assert name not in block
    # ohne Dateien je Ordner (altes Widget) keine solche Zeile
    alt = _daten()
    alt["struktur"] = _ohne_dateien(alt["struktur"])
    assert "Dateien:" not in antwort.antwort_block(_pruefe(alt))


def test_die_sicherheitspruefung_liest_die_dateinamen_vor_der_nachricht():
    text = antwort.sicherheits_text("Hallo", _pruefe(_daten()))
    for name in ("Hebel.pdf", "Kraft.docx", "Linsen.pdf"):
        assert name in text
    assert "alt.tmp" not in text                        # R3-4: ausgeschlossen, ohne Namen
    assert text.endswith("\nHallo")


def test_die_dateinamen_sind_gedeckelt_und_halten_die_nachricht_im_geprueften_teil():
    """500 Namen zu 120 Zeichen wären 60 000 Zeichen — die Moderation prüft ganz nur rund
    30 000 (8 Abschnitte zu 4000, ``safety/moderation``); dahinter läge die Nachricht."""
    lang = _viele(500, name=lambda i: f"{i:04d}" + "n" * 112 + ".pdf")
    vorsatz = upload.sicherheit(lang)
    namen = upload._dateinamen(lang["struktur"])
    assert len(namen) <= upload.DATEINAMEN_ZEICHEN + len("\n…(gekürzt)")
    assert namen.endswith("…(gekürzt)") and namen.startswith("0000")
    assert len(vorsatz) < 15_000


# ── Dienst ``bereitgestellt`` ────────────────────────────────────────────────────────────────────

def _bereit(teile: dict) -> dict:
    async def lader(name):
        return teile.get(name)

    return asyncio.run(werkzeuge.DIENSTE["bereitgestellt"](
        {}, werkzeuge.DienstKontext(teile=lader)))


def test_bereitgestellt_zaehlt_dateien_und_inhaltsdateien():
    [struktur] = [t[2] for t in arbeitsstand_teile.teile_aus_antwort(_pruefe(_daten()))
                  if t[0] == "struktur"]
    bereit = _bereit({"struktur": struktur})
    # nicht ignoriert: 3 Inhalte + 1 Strukturdokument
    assert (bereit["dateien"], bereit["inhaltsdateien"]) == (4, 3)
    assert werkzeuge.ZUSAMMENFASSUNG["bereitgestellt"](bereit) == "4 Dateien"


def test_bereitgestellt_ohne_struktur_null_dateien():
    """Nur ``structure`` (vor TG-3a): ohne Namen trägt der Weg über die Dateien nicht."""
    alt = {"struktur": {"name": "P", "dateien": 3, "alle_dateien": 3, "kinder": []},
           "zahlen": {"inhalte": 3}}
    bereit = _bereit({"structure": alt})
    assert (bereit["dateien"], bereit["inhaltsdateien"]) == (0, 0)


# ── Übertragung: das MCP bekommt keine Nummer (TG-3b) ────────────────────────────────────────────

def test_die_nummer_geht_nicht_an_das_mcp(monkeypatch):
    from boerdi.services.ablage import mcp_ablage

    gesendet: list = []

    async def werkzeug(name, args):
        gesendet.append(args)
        return {"batchToken": "t" * 20, "entries": [{"index": 0}]}

    monkeypatch.setattr(mcp_ablage, "_werkzeug", werkzeug)
    asyncio.run(mcp_ablage.vorbereiten("P", [{"titel": "a", "sha256": "a" * 64, "groesse": 1,
                                             "art": "pdf", "rolle": "inhalt", "i": 7}]))
    assert gesendet[0]["entries"] == [{"title": "a", "sha256": "a" * 64, "size": 1,
                                       "ext": "pdf", "role": "content"}]
