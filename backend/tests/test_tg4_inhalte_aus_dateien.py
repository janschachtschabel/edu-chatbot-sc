"""Plan 2026-11-16, TG-4 (G-E9): das Ablauf-Werkzeug ``inhalte_aus_dateien``.

Lose Dateien ohne WLO: aus dem Teil ``struktur`` (die Auswahl mit Dateien je Ordner) wird ein Teil
``metadaten`` im Format ``wlo.metadaten@1`` — ohne LLM, ohne Netz. Titel aus dem Dateinamen (ohne
Endung, ``_``/``-`` als Leerzeichen, gekürzt), der Ordnerpfad als Beschreibung, nur Rolle
``inhalt``, je Eintrag ``i`` und kein ``node_id``. ``metadaten.als_dokument`` liest ihn, also baut
``ui_strukturentwurf`` mit ``aus_inhalten`` daraus einen Entwurf.
"""

from __future__ import annotations

import asyncio
import json

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import inhalte_aus_dateien as iad
from boerdi.services.ablauf import metadaten, simulation, typen, werkzeuge
from boerdi.services.ablauf.pruefung import pruefe, warnungen


def _datei(i: int, name: str, rolle: str = "inhalt") -> dict:
    endung = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {"i": i, "name": name, "endung": endung, "groesse": 10, "rolle": rolle}


def _auswahl() -> dict:
    """Wie ein Teil ``struktur`` nach „Senden“: Physik 7 mit Lehrplan, zwei Unterordnern."""
    return {"block_id": "blk-1", "zahlen": {"ordner": 3, "dateien": 5}, "warnungen": [],
            "struktur": {"name": "Physik 7", "dateien": 1, "alle_dateien": 5,
                         "dateiliste": [_datei(4, "Lehrplan_Physik.pdf", "struktur")],
                         "kinder": [
                             {"name": "Mechanik", "dateien": 2, "alle_dateien": 2, "kinder": [],
                              "dateiliste": [_datei(0, "01_Hebel-Gesetz.pdf"),
                                             _datei(1, "Kraft und Masse.docx")]},
                             {"name": "Optik", "dateien": 2, "alle_dateien": 2, "kinder": [],
                              "dateiliste": [_datei(2, "Linsen.v2.pptx"),
                                             {"i": 3, "endung": "tmp", "groesse": 1,
                                              "rolle": "ignorieren"}]}]}}


def _dienst(teil):
    return asyncio.run(werkzeuge.DIENSTE["inhalte_aus_dateien"]({"struktur": teil}))


# ── Titel ────────────────────────────────────────────────────────────────────────────────────────

def test_titel_ohne_endung_mit_leerzeichen():
    assert iad.titel("01_Hebel-Gesetz.pdf", "pdf") == "01 Hebel Gesetz"
    assert iad.titel("Kraft und Masse.docx", "docx") == "Kraft und Masse"
    # ohne Angabe der Endung: ein kurzer Rest hinter dem letzten Punkt
    assert iad.titel("Linsen.v2.pptx") == "Linsen.v2"
    assert iad.titel("Kapitel 1.2 Optik") == "Kapitel 1.2 Optik"
    assert iad.titel("__a__--b__.pdf", "pdf") == "a b"


def test_lange_titel_werden_an_der_wortgrenze_gekuerzt():
    name = "_".join(["Wort"] * 40) + ".pdf"
    kurz = iad.titel(name, "pdf")
    assert len(kurz) <= iad.TITEL_ZEICHEN and kurz.endswith("…")
    assert not kurz[:-1].endswith(" ") and "Wor…" not in kurz


# ── Der Teil ─────────────────────────────────────────────────────────────────────────────────────

def test_nur_inhaltsdateien_mit_titel_pfad_und_i_ohne_node_id():
    teil = _dienst(_auswahl())
    assert teil["format"] == metadaten.FORMAT and teil["fehlend"] == []
    assert teil["block_id"] == "blk-1"   # R3-2: ``i`` gilt nur für diese Auswahl
    assert teil["inhalte"] == [
        {"i": 0, "rolle": "inhalt", "titel": "01 Hebel Gesetz",
         "beschreibung": "Ordner: Physik 7 / Mechanik"},
        {"i": 1, "rolle": "inhalt", "titel": "Kraft und Masse",
         "beschreibung": "Ordner: Physik 7 / Mechanik"},
        {"i": 2, "rolle": "inhalt", "titel": "Linsen.v2",
         "beschreibung": "Ordner: Physik 7 / Optik"}]
    assert all("node_id" not in e for e in teil["inhalte"])


def test_ohne_inhaltsdatei_oder_ohne_namen_entsteht_nichts():
    nur_struktur = {"struktur": {"name": "X", "kinder": [],
                                 "dateiliste": [_datei(0, "Lehrplan.pdf", "struktur")]}}
    assert _dienst(nur_struktur) is None
    # der Teil ``structure`` (nur Ordner, vor TG-3a) trägt keine Namen
    assert _dienst({"struktur": {"name": "X", "dateien": 3, "kinder": []}}) is None
    assert _dienst(None) is None and _dienst({"format": "anders"}) is None


def test_der_teil_ist_ein_dokument_fuer_den_strukturentwurf():
    dok = metadaten.als_dokument(_dienst(_auswahl()))
    assert dok is not None and dok.format == metadaten.DOKUMENT_FORMAT
    assert [a.titel for a in dok.abschnitte] == ["01 Hebel Gesetz", "Kraft und Masse", "Linsen.v2"]
    assert "Ordner: Physik 7 / Mechanik" in dok.markdown


def test_500_lange_namen_passen_unter_die_grenze():
    lang = "Ein_sehr_langer_Dateiname_mit_vielen_Woertern_zur_Unterrichtsreihe_" * 2
    kinder = [{"name": f"Ordner {n} mit einem langen Namen fuer die Pruefung", "kinder": [],
               "dateiliste": [_datei(n * 50 + k, f"{lang}{k}.pdf") for k in range(50)]}
              for n in range(10)]
    teil = _dienst({"struktur": {"name": "Wurzel", "kinder": kinder}})
    groesse = len(json.dumps(teil, ensure_ascii=False).encode("utf-8"))
    assert groesse <= metadaten.MAX_TEIL
    assert len(teil["inhalte"]) + teil.get("ausgelassen", 0) == 500
    assert metadaten.als_dokument(teil) is not None


def test_der_dienst_nimmt_aus_inhalten_den_teil_aus_dateinamen(monkeypatch):
    """Der Weg bis zum Generator: ``ui_strukturentwurf`` mit ``aus_inhalten`` liest den Teil."""
    from boerdi.services import strukturentwurf_dienst
    from boerdi.ui_module import dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    gesehen: dict = {}

    async def erzeugen(auftrag, *, llm, frist_ende, vorlage=None, dokument=None, moderieren=None):
        gesehen["dokument"] = dokument
        return strukturentwurf_dienst.Erzeugt(daten=None, grund="test")

    async def moderieren(text):
        gesehen["moderiert"] = text
        return {"flagged": False}

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", erzeugen)
    monkeypatch.setattr(dienst, "_moderation", lambda: moderieren)
    teil = _dienst(_auswahl())

    async def teile(name):
        return teil if name == "metadaten" else None

    asyncio.run(dienst._strukturentwurf(katalog()["ui_strukturentwurf"],
                                        {"thema": "Physik", "aus_inhalten": True},
                                        Umgebung(teile=teile)))
    assert [a.titel for a in gesehen["dokument"].abschnitte][:2] == ["01 Hebel Gesetz",
                                                                      "Kraft und Masse"]
    # die Namen gehen vor Ebene 1 durch die Moderation (wie Metadaten aus WLO)
    assert "01 Hebel Gesetz" in gesehen["moderiert"]


# ── Eingetragen wie die anderen Werkzeuge ────────────────────────────────────────────────────────

def test_ein_reiner_dienst_mit_typ_und_eingabe():
    assert "inhalte_aus_dateien" in werkzeuge.REINE_DIENSTE
    assert typen.dienst_typ("inhalte_aus_dateien") == typen.METADATEN
    assert typen.DIENST_EINGABE["inhalte_aus_dateien"] == {"struktur": typen.AUSWAHL}


def test_das_studio_bekommt_es_im_katalog():
    from boerdi.api import config_choices

    werte = {c["value"] for c in config_choices._SOURCES["ablauf_werkzeuge"]()}
    assert "inhalte_aus_dateien" in werte


def _ablauf(schreibt: str = "metadaten") -> AblaufArea:
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"}, "schritte": [
        {"id": "namen", "typ": "werkzeug", "werkzeug": "inhalte_aus_dateien",
         "argumente": {"struktur": {"$teil": "struktur"}}, "schreibt": schreibt,
         "bei_fehler": "ohne"},
        {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}},
        {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Dateinamen."}}],
        "tests": [{"name": "Aus den Namen", "teile": {"struktur": _auswahl()},
                   "erwartet": {"weg": ["namen", "ende"], "status": "fertig",
                                "teile": [schreibt]}},
                  {"name": "Ohne Namen", "teile": {"struktur": {"struktur": {"name": "X"}}},
                   "erwartet": {"weg": ["namen", "ohne"]}}]})


def test_die_pruefung_kennt_das_werkzeug_ohne_anmeldung():
    ablauf = _ablauf()
    assert pruefe(ablauf) == []          # kein MCP: keine Voraussetzung Anmeldung
    assert not any("metadaten" in w for w in warnungen(ablauf))


def test_ein_anderer_teilname_ist_ein_hinweis():
    """Wie ``metadaten_lesen``: ``ui_strukturentwurf`` (aus_inhalten) liest fest ``metadaten``."""
    assert any("metadaten" in w for w in warnungen(_ablauf("namen")))


def test_die_simulation_rechnet_den_dienst_selbst():
    ergebnisse = asyncio.run(simulation.alle(_ablauf()))
    assert all(e.ok for e in ergebnisse), [(e.name, e.abweichungen) for e in ergebnisse]
