"""Paket K2d-1 (Plan 2026-11-08): ein Verweis nimmt einen Teil des Teils —
``{"$teil": "volltext", "pfad": "outputs.markdown"}``.

- Der Pfad sind Schlüssel (und Listenstellen) mit Punkt getrennt; fehlt die Stelle, fehlt der Teil
  wie ein unbekannter (``volltext.outputs.markdown``) — das Werkzeug wird nicht gerufen.
- Nur ``$teil`` und ``pfad`` (ein Text) bilden den Verweis; alles andere bleibt, wie es ist.
- Die Grenze für Werkzeuge der KI gilt für den ausgewählten Wert, die Freigabe für den Teil.
- Die Prüfung meldet einen Pfad ohne gültige Form; der Treiber nimmt ihn an jeder Stelle, an der
  er Verweise einsetzt (nicht als ganze ``argumente``, nicht tiefer als ``TIEFE`` — beides meldet
  die Prüfung, Review K2d-1 (2)).
"""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import teil_verweise
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf.pruefung import pruefe

_VOLLTEXT = {"outputs": {"markdown": "# Optik", "seiten": [{"nr": 1, "text": "Licht"}]},
             "dateien": [], "warnungen": []}


async def _lader(name):
    return {"volltext": _VOLLTEXT, "gross": {"klein": "ok", "riesig": "x" * 70_000}}.get(name)


def _ein(args, werkzeug=None):
    return asyncio.run(teil_verweise.einsetzen(args, _lader, werkzeug))


def test_ein_pfad_waehlt_eine_stelle_im_teil_auch_in_listen():
    args, fehlt = _ein({"text": {"$teil": "volltext", "pfad": "outputs.markdown"},
                        "seite": {"$teil": "volltext", "pfad": "outputs.seiten.0.text"}})
    assert fehlt == []
    assert args == {"text": "# Optik", "seite": "Licht"}


def test_eine_fehlende_stelle_fehlt_wie_ein_unbekannter_teil():
    for pfad in ("outputs.html", "outputs.seiten.3", "outputs.markdown.x", "outputs.seiten.-1"):
        _, fehlt = _ein({"t": {"$teil": "volltext", "pfad": pfad}})
        assert fehlt == [f"volltext.{pfad}"], pfad


def test_ein_pfad_ohne_gueltige_form_fehlt():
    for pfad in ("", "a..b", "a b", ".a", "a." + ".".join(["x"] * 9)):
        _, fehlt = _ein({"t": {"$teil": "volltext", "pfad": pfad}})
        assert fehlt and fehlt[0].startswith("volltext"), pfad


def test_review_falsche_werte_fuehrende_nullen_und_zeilenumbruch():
    async def lader(name):
        werte = {"null": None, "null_zahl": 0, "leer": "", "nein": False, "liste": ["a", "b"]}
        return {"werte": werte}.get(name)

    def ein(pfad):
        return asyncio.run(teil_verweise.einsetzen({"x": {"$teil": "werte", "pfad": pfad}}, lader))

    # 0, "" und False sind Werte — null gilt als fehlend (Befund 2, bewusst)
    assert ein("null_zahl") == ({"x": 0}, [])
    assert ein("leer") == ({"x": ""}, [])
    assert ein("nein") == ({"x": False}, [])
    assert ein("null")[1] == ["werte.null"]
    # eine Listenstelle hat eine Schreibweise (Befund 3)
    assert ein("liste.1") == ({"x": "b"}, [])
    assert ein("liste.01")[1] == ["werte.liste.01"]
    assert ein("liste.0") == ({"x": "a"}, [])
    # ein Zeilenumbruch am Ende ist keine gültige Form (Befund 1), auch nicht im Namen
    assert not teil_verweise.PFAD.match("liste\n")
    assert not teil_verweise.NAME.match("draft\n")


def test_nur_teil_und_ein_text_als_pfad_bilden_den_verweis():
    args = {"a": {"$teil": "volltext", "pfad": 5},
            "b": {"$teil": "volltext", "pfad": "outputs", "mehr": 1}}
    neu, fehlt = _ein(args)
    assert neu == args and fehlt == []


def test_die_grenze_gilt_fuer_den_ausgewaehlten_wert_die_freigabe_fuer_den_teil():
    from boerdi.domain.write_confirm import is_confirmable

    schreibend = next(n for n in ("wlo_update_metadata", "wlo_create_content") if is_confirmable(n))
    args, fehlt = _ein({"t": {"$teil": "gross", "pfad": "klein"}}, schreibend)
    assert fehlt == [] and args == {"t": "ok"}
    _, fehlt = _ein({"t": {"$teil": "gross", "pfad": "riesig"}}, schreibend)
    assert fehlt == ["gross.riesig"]
    # ein lesendes Werkzeug bekommt den Teil auch nicht über einen Pfad
    _, fehlt = _ein({"t": {"$teil": "volltext", "pfad": "outputs.markdown"}}, "search_wlo_all")
    assert fehlt == ["volltext.outputs.markdown"]


def _ablauf(schritte):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"},
                                      "voraussetzungen": ["anmeldung"], "schritte": schritte})


def test_der_treiber_setzt_einen_pfad_in_argumenten_und_in_ganzen_daten_ein():
    from tests.test_ablauf_treiber import _STRUKTUR, STRUKTURENTWURF, _umgebung

    ablauf = _ablauf([
        {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "paket", "pfad": "innen"}}, "schreibt": "draft"},
        {"id": "zeigen", "typ": "modul", "modul": STRUKTURENTWURF,
         "daten": {"$teil": "huelle", "pfad": "entwurf"}},
        {"id": "e", "typ": "ende"}])
    aus = asyncio.run(treiber.starten(ablauf, _umgebung(teile={"paket": {"innen": _STRUKTUR}})))
    [(name, _typ, wert, _zf)] = aus.neue_teile
    assert name == "draft" and wert["quelle"] == "ordner"
    # der zweite Schritt liest `huelle.entwurf` — die gibt es nicht: der Lauf endet mit Fehler
    assert aus.lauf["status"] == "fehler"

    ablauf = _ablauf([
        {"id": "zeigen", "typ": "modul", "modul": STRUKTURENTWURF,
         "daten": {"$teil": "huelle", "pfad": "entwurf"}},
        {"id": "e", "typ": "ende"}])
    aus = asyncio.run(treiber.starten(ablauf, _umgebung(teile={"huelle": {"entwurf": wert}})))
    [block] = aus.bloecke
    assert block.modul == STRUKTURENTWURF and block.daten["knoten"] == wert["knoten"]


def test_ganze_daten_brauchen_an_der_stelle_ein_objekt():
    from tests.test_ablauf_treiber import STRUKTURENTWURF, _umgebung

    ablauf = _ablauf([
        {"id": "zeigen", "typ": "modul", "modul": STRUKTURENTWURF,
         "daten": {"$teil": "huelle", "pfad": "titel"}},
        {"id": "e", "typ": "ende"}])
    # die Stelle gibt es, aber sie ist ein Text — und eine fehlende Stelle in einem vorhandenen Teil
    for pfad_teil in ({"titel": "nur Text"}, {"anderes": {}}):
        aus = asyncio.run(treiber.starten(ablauf, _umgebung(teile={"huelle": pfad_teil})))
        assert aus.lauf["status"] == "fehler" and aus.bloecke == []


def test_die_pruefung_meldet_einen_pfad_ohne_gueltige_form():
    def befunde(pfad):
        return pruefe(_ablauf([
            {"id": "w", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
             "argumente": {"struktur": {"$teil": "structure", "pfad": pfad}}},
            {"id": "e", "typ": "ende"}]))

    assert not [b for b in befunde("outputs.markdown") if "Pfad" in b]
    assert [b for b in befunde("outputs.markdown\n") if "Pfad" in b]
    [befund] = [b for b in befunde("a..b") if "Pfad" in b]
    assert "w" in befund and "a..b" in befund
    # der Name des Teils wird weiter geprüft
    namen = pruefe(_ablauf([
        {"id": "w", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "Gross", "pfad": "a"}}},
        {"id": "e", "typ": "ende"}]))
    assert any("'Gross'" in b for b in namen)

# ── Review K2d-1 (2) ──────────────────────────────────────────────────────────────────────────

def _werkzeug_schritt(argumente):
    return _ablauf([{"id": "w", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
                     "argumente": argumente}, {"id": "e", "typ": "ende"}])


def test_review2_ganze_argumente_als_verweis_meldet_die_pruefung():
    # der Treiber setzt die oberste Ebene von argumente nie ein …
    args, fehlt = _ein({"$teil": "volltext", "pfad": "outputs"})
    assert args == {"$teil": "volltext", "pfad": "outputs"} and fehlt == []
    # … darum meldet es die Prüfung
    assert any("ganzer Verweis" in b for b in pruefe(_werkzeug_schritt(
        {"$teil": "structure", "pfad": "innen"})))
    assert not any("ganzer Verweis" in b for b in pruefe(_werkzeug_schritt(
        {"struktur": {"$teil": "structure", "pfad": "innen"}})))


def test_review2_ein_zu_tiefer_verweis_meldet_die_pruefung():
    def geschachtelt(n):
        wert = {"$teil": "structure"}
        for _ in range(n):
            wert = {"x": wert}
        return wert

    # Tiefe TIEFE: setzt der Treiber ein; eine Ebene tiefer nicht
    flach, tief = geschachtelt(teil_verweise.TIEFE), geschachtelt(teil_verweise.TIEFE + 1)
    # (``structure`` hat der Lader nicht: versucht wird nur, was der Treiber erreicht)
    assert _ein(flach)[1] == ["structure"] and _ein(tief) == (tief, [])
    assert not any("tiefer als" in b for b in pruefe(_werkzeug_schritt(flach)))
    [befund] = [b for b in pruefe(_werkzeug_schritt(tief)) if "tiefer als" in b]
    assert "'structure'" in befund


def test_review2_befunde_bleiben_kurz_und_pfad_in_daten_wird_geprueft():
    from tests.test_ablauf_treiber import STRUKTURENTWURF

    [befund] = [b for b in pruefe(_werkzeug_schritt(
        {"struktur": {"$teil": "structure", "pfad": "x" * 100_000}})) if "Pfad" in b]
    assert len(befund) < 400
    for pfad in ("", "a..b"):
        daten = pruefe(_ablauf([{"id": "m", "typ": "modul", "modul": STRUKTURENTWURF,
                                 "daten": {"knoten": {"$teil": "draft", "pfad": pfad}}},
                                {"id": "e", "typ": "ende"}]))
        assert any("Pfad" in b for b in daten), pfad
