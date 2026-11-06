"""Paket A1: der lokale Treiber — rechnet ohne Modell bis zum nächsten wartenden Schritt oder Ende.

Er liest Teile über den Lader des Vorgangs, schreibt Werkzeug-Ergebnisse als neue Teile, hält bei
einem abfragenden Modul an (``offener_block``) und setzt mit der Antwort fort. Nachricht, Modul,
Werkzeug, Verzweigung und Ende sind die Schrittarten; ein Fehler geht zu ``bei_fehler`` oder endet.
"""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import treiber
from boerdi.ui_module.namen import STRUKTURENTWURF

_FRAGE = {"frage": "Wie weiter?", "optionen": [{"id": "ordner", "label": "Aus Ordnern"},
                                                {"id": "neu", "label": "Neu entwerfen"}]}
_STRUKTUR = {"struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2, "kinder": [
    {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
    {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]}, "zahlen": {}}


def _ablauf(schritte, **mehr):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"},
                                      "schritte": schritte, **mehr})


def _umgebung(teile=None, werkzeug=None):
    teile = teile or {}

    async def lader(name):
        return teile.get(name)

    async def rufe(name, args):
        return (werkzeug or {}).get(name)

    return treiber.Umgebung(teile=lader, sprache="de", mcp=rufe)


def _starte(ablauf, **u):
    return asyncio.run(treiber.starten(ablauf, _umgebung(**u)))


def test_nachricht_und_ende_ohne_halt():
    aus = _starte(_ablauf([{"id": "a", "typ": "nachricht", "text": {"de": "Hallo"}},
                           {"id": "e", "typ": "ende", "text": {"de": "Fertig"}}]))
    assert aus.texte == ["Hallo", "Fertig"] and aus.lauf["status"] == "fertig"
    assert aus.bloecke == [] and aus.lauf["offener_block"] is None


def test_ein_abfragendes_modul_haelt_an_und_die_antwort_setzt_fort():
    ablauf = _ablauf([
        {"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE,
         "text": {"de": "Eine Frage:"}},
        {"id": "gabel", "typ": "verzweigung",
         "weiter": [{"wenn_gewaehlt": "ordner", "dann": "ja"}, {"sonst": "nein"}]},
        {"id": "ja", "typ": "ende", "text": {"de": "Aus Ordnern."}},
        {"id": "nein", "typ": "ende", "text": {"de": "Neu."}}])
    aus = _starte(ablauf)
    [block] = aus.bloecke
    assert aus.texte == ["Eine Frage:"] and block.modul == "ui_entscheidung"
    assert aus.lauf == {**aus.lauf, "status": "wartet_person", "schritt": "frage",
                        "offener_block": block.block_id}
    weiter = asyncio.run(treiber.weiter(ablauf, aus.lauf, {"gewaehlt": ["ordner"]}, _umgebung()))
    assert weiter.texte == ["Aus Ordnern."] and weiter.lauf["status"] == "fertig"


def test_ein_werkzeug_schreibt_einen_teil_den_der_naechste_schritt_liest():
    ablauf = _ablauf([
        {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft"},
        {"id": "zeigen", "typ": "modul", "modul": STRUKTURENTWURF, "daten": {"$teil": "draft"}},
        {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf, teile={"structure": _STRUKTUR})
    [(name, typ, wert, _zf)] = aus.neue_teile
    assert name == "draft" and wert["quelle"] == "ordner"
    [block] = aus.bloecke
    assert block.modul == STRUKTURENTWURF and block.daten["knoten"][0]["titel"] == "Mechanik"
    assert aus.lauf["schritt"] == "zeigen"


def test_ein_fehlender_teil_geht_zu_bei_fehler():
    ablauf = _ablauf([
        {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft",
         "bei_fehler": "schade"},
        {"id": "ok", "typ": "ende", "text": {"de": "Gut."}},
        {"id": "schade", "typ": "ende", "text": {"de": "Ohne Ordner geht es nicht."}}])
    aus = _starte(ablauf)
    assert aus.texte == ["Ohne Ordner geht es nicht."] and aus.lauf["status"] == "fertig"


def test_ohne_bei_fehler_endet_der_lauf_mit_fehler():
    ablauf = _ablauf([
        {"id": "suche", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "x"}, "schreibt": "treffer"},
        {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf)            # das MCP-Werkzeug liefert nichts
    assert aus.lauf["status"] == "fehler" and aus.fehler == "suche"


def test_ein_lesendes_mcp_werkzeug_wird_ein_teil():
    ablauf = _ablauf([
        {"id": "suche", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "Optik"}, "schreibt": "treffer"},
        {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf, werkzeug={"search_wlo_all": "3 Treffer"})
    assert aus.neue_teile[0][:3] == ("treffer", "text", "3 Treffer")


def test_eine_veraltete_antwort_setzt_nicht_fort():
    ablauf = _ablauf([{"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
                      {"id": "e", "typ": "ende", "text": {"de": "x"}}])
    aus = _starte(ablauf)
    fertig = {**aus.lauf, "status": "fertig"}
    weiter = asyncio.run(treiber.weiter(ablauf, fertig, {"gewaehlt": ["neu"]}, _umgebung()))
    assert weiter is None


def test_die_fassung_haengt_an_der_definition():
    a = _ablauf([{"id": "e", "typ": "ende"}])
    b = _ablauf([{"id": "e", "typ": "ende", "text": {"de": "anders"}}])
    assert treiber.fassung(a) != treiber.fassung(b) and treiber.fassung(a) == treiber.fassung(a)


# ── Review A1: Fassung, Schrittgrenze, Sperren, Schalter, Teile an lesende Werkzeuge ───────────

def test_titel_und_schalter_aendern_die_fassung_nicht():
    """Befund 5: nur geänderte Schritte halten einen wartenden Lauf an."""
    schritte = [{"id": "e", "typ": "ende"}]
    a = _ablauf(schritte)
    b = _ablauf(schritte, titel={"de": "Neuer Titel"}, aktiv=True)
    assert treiber.fassung(a) == treiber.fassung(b)


def test_nach_geaenderten_schritten_setzt_ein_wartender_lauf_nicht_fort():
    alt = _ablauf([{"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
                   {"id": "e", "typ": "ende", "text": {"de": "x"}}])
    lauf = _starte(alt).lauf
    neu = _ablauf([{"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
                   {"id": "e", "typ": "ende", "text": {"de": "anders"}}])
    assert treiber.kann_weiter(alt, lauf) and not treiber.kann_weiter(neu, lauf)
    assert asyncio.run(treiber.weiter(neu, lauf, {}, _umgebung())) is None


def test_die_schrittgrenze_endet_mit_fehler():
    kette = [{"id": f"s{i}", "typ": "nachricht", "text": {"de": str(i)}}
             for i in range(treiber.RECHENSCHRITTE + 1)] + [{"id": "e", "typ": "ende"}]
    aus = _starte(_ablauf(kette))
    assert aus.lauf["status"] == "fehler" and len(aus.texte) == treiber.RECHENSCHRITTE


def test_ein_gesperrtes_werkzeug_liefert_nichts():
    """Befund 2: die Werkzeugsperre der Sicherheitsprüfung gilt auch für Schritte."""
    ablauf = _ablauf([
        {"id": "suche", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": "Optik"}, "schreibt": "treffer", "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}])
    umgebung = treiber.Umgebung(teile=_umgebung().teile, mcp=_umgebung(
        werkzeug={"search_wlo_all": "3 Treffer"}).mcp, gesperrt=frozenset({"search_wlo_all"}))
    aus = asyncio.run(treiber.starten(ablauf, umgebung))
    assert aus.neue_teile == [] and aus.lauf["status"] == "fertig"


def test_ein_lesendes_werkzeug_bekommt_keine_teile():
    """Befund 9: ``teil_verweise.darf`` gilt im Treiber für lesende WLO-Werkzeuge."""
    ablauf = _ablauf([
        {"id": "suche", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": {"$teil": "document"}}, "schreibt": "treffer"},
        {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf, teile={"document": "geheim"}, werkzeug={"search_wlo_all": "Treffer"})
    assert aus.lauf["status"] == "fehler" and aus.neue_teile == []


def test_ein_ausgeschaltetes_modul_baut_keinen_block(monkeypatch):
    from boerdi.ui_module import schalter

    monkeypatch.setattr(schalter, "aktiv", lambda name: name != "ui_entscheidung")
    ablauf = _ablauf([{"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
                      {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf)
    assert aus.bloecke == [] and aus.lauf["status"] == "fehler"


def test_ein_modul_mit_modell_dienst_wird_nicht_ueber_den_dienst_gebaut():
    """Befund 4: passt ``daten`` nicht, ruft der Treiber nicht den LLM-Dienst des Moduls."""
    ablauf = _ablauf([{"id": "zeigen", "typ": "modul", "modul": STRUKTURENTWURF,
                       "daten": {"quelle": "dokument"}}, {"id": "e", "typ": "ende"}])
    aus = _starte(ablauf)
    assert aus.bloecke == [] and aus.fehler == "zeigen"


def test_eine_wahl_ist_nur_eine_liste_von_texten():
    ablauf = _ablauf([
        {"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": _FRAGE},
        {"id": "gabel", "typ": "verzweigung",
         "weiter": [{"wenn_gewaehlt": "o", "dann": "ja"}, {"sonst": "nein"}]},
        {"id": "ja", "typ": "ende", "text": {"de": "ja"}},
        {"id": "nein", "typ": "ende", "text": {"de": "nein"}}])
    lauf = _starte(ablauf).lauf
    weiter = asyncio.run(treiber.weiter(ablauf, lauf, {"gewaehlt": "ordner"}, _umgebung()))
    assert weiter.texte == ["nein"] and weiter.lauf["gewaehlt"] == []
