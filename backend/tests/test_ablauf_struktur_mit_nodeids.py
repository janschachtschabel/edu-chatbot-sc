"""Paket AS-Dd (Plan 2026-11-09 §5e): die Dienste ``struktur_mit_nodeids`` und ``baum_aus_entwurf``.

Nach dem Anlegen eines Sammlungsbaums (``wlo_create_collection_tree``, Antwort
``nodes: [{path, nodeId?, status, code?}]``, Pfad = Titel mit „/“) trägt der Entwurf
(``wlo.sammlungsstruktur@1``) je Punkt die Kennung seiner Sammlung im vorhandenen Feld ``wlo_id``
— Folgeschritte (Einsortieren, Metadaten) treffen so die richtigen Knoten. Zugeordnet wird über den
Titelpfad, ohne Rücksicht auf Groß- und Kleinschreibung und Leerraum (wie ``onExisting: merge``).
``baum_aus_entwurf`` liefert den Baum zum Anlegen — mit denselben Titeln.
"""

from __future__ import annotations

import asyncio

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import typen, werkzeuge
from boerdi.services.ablauf.pruefung import pruefe

_ID = "{:08x}-0000-4000-8000-000000000000"
_ENTWURF = {"titel": "Physik", "quelle": "ki", "knoten": [
    {"id": "mech", "titel": "Mechanik", "kinder": [
        {"id": "kin", "titel": "Kinematik"}, {"id": "dyn", "titel": "Dynamik"}]},
    {"id": "opt", "titel": "Optik"},
]}
_ANGELEGT = {"complete": True, "nodes": [
    {"path": "Mechanik", "nodeId": _ID.format(1), "status": "created"},
    {"path": "mechanik/ KINEMATIK ", "nodeId": _ID.format(2), "status": "existing"},
    {"path": "Mechanik/Dynamik", "nodeId": None, "status": "failed", "code": "x"},
    {"path": "Optik", "nodeId": _ID.format(4), "status": "created"},
]}


def _rufen(args):
    return asyncio.run(werkzeuge.DIENSTE["struktur_mit_nodeids"](args))


def test_jeder_angelegte_punkt_traegt_seine_kennung():
    neu = _rufen({"entwurf": _ENTWURF, "angelegt": _ANGELEGT})
    mech = neu["knoten"][0]
    assert mech["wlo_id"] == _ID.format(1)
    assert mech["kinder"][0]["wlo_id"] == _ID.format(2)
    # ohne Kennung im Ergebnis: keine Kennung
    assert "wlo_id" not in mech["kinder"][1]
    assert neu["knoten"][1]["wlo_id"] == _ID.format(4)
    # der Entwurf selbst bleibt unverändert (Kopie)
    assert "wlo_id" not in _ENTWURF["knoten"][0]


def test_auch_eine_reine_liste_der_knoten():
    neu = _rufen({"entwurf": _ENTWURF, "angelegt": _ANGELEGT["nodes"]})
    assert neu["knoten"][1]["wlo_id"] == _ID.format(4)


def test_ohne_entwurf_oder_ergebnis_entsteht_nichts():
    assert _rufen({"entwurf": None, "angelegt": _ANGELEGT}) is None
    assert _rufen({"entwurf": _ENTWURF, "angelegt": "kein Ergebnis"}) is None


def test_eine_kennung_ohne_gueltige_form_wird_nicht_uebernommen():
    """``wlo_id`` hat im Vertrag des Moduls die Form einer UUID (auch kein Zeilenende dahinter)."""
    neu = _rufen({"entwurf": _ENTWURF, "angelegt": {"nodes": [
        {"path": "Mechanik", "nodeId": _ID.format(1), "status": "created"},
        {"path": "Optik", "nodeId": "keine-uuid", "status": "created"},
        {"path": "Mechanik/Kinematik", "nodeId": _ID.format(2) + "\n", "status": "created"}]}})
    assert "wlo_id" not in neu["knoten"][1]
    assert "wlo_id" not in neu["knoten"][0]["kinder"][0]


def _ablauf(*schritte):
    return AblaufArea.model_validate({"id": "s", "titel": {"de": "S"}, "schritte": [
        *schritte, {"id": "e", "typ": "ende"}]})


_VERBINDEN = {"id": "verbinden", "typ": "werkzeug", "werkzeug": "struktur_mit_nodeids",
              "argumente": {"entwurf": {"$teil": "draft"}, "angelegt": {"$teil": "angelegt"}},
              "schreibt": "draft_mit_ids", "bei_fehler": "e"}


def test_typen_und_pruefung_kennen_den_dienst():
    assert typen.DIENST_AUSGABE["struktur_mit_nodeids"] == typen.STRUKTUR
    assert typen.DIENST_EINGABE["struktur_mit_nodeids"]["entwurf"] == typen.STRUKTUR
    befunde = pruefe(_ablauf(_VERBINDEN))
    # ``angelegt`` schreibt hier niemand — der Dienst selbst ist bekannt
    assert not any("unbekannt" in b and "struktur_mit_nodeids" in b for b in befunde), befunde


def test_der_typ_nach_der_freigabe_passt_zum_erwarteten():
    """Review AS-Dd, Befunde 8/9: der Treiber speichert das Ergebnis eines schreibenden Werkzeugs
    unter ``typen.dienst_typ`` — genau den Typ, den ``angelegt`` erwartet."""
    assert typen.DIENST_EINGABE["struktur_mit_nodeids"]["angelegt"] == typen.dienst_typ(
        "wlo_create_collection_tree")
    baum = {"id": "baum", "typ": "werkzeug", "werkzeug": "baum_aus_entwurf",
            "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "baum", "bei_fehler": "e"}
    anlegen = {"id": "anlegen", "typ": "werkzeug", "werkzeug": "wlo_create_collection_tree",
               "argumente": {"parentCollectionId": _ID.format(5), "tree": {"$teil": "baum"}},
               "freigabe": {"de": "Anlegen?"}, "schreibt": "angelegt", "bei_fehler": "e"}
    gut = pruefe(_ablauf(baum, anlegen, _VERBINDEN))
    assert not any("angelegt" in b for b in gut), gut
    falsch = {"id": "anlegen", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
              "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "angelegt",
              "bei_fehler": "e"}
    assert any("angelegt" in b for b in pruefe(_ablauf(falsch, _VERBINDEN)))


def test_keine_neue_wurzel_und_kein_rueckgriff():
    """Review AS-Dd, Befund 1: ein oberer Punkt mit dem Titel des Entwurfs gibt seine Kennung weder
    der Wurzel noch einem gescheiterten Punkt."""
    entwurf = {"titel": "Optik", "knoten": [
        {"id": "o", "titel": "Optik", "kinder": [{"id": "ol", "titel": "Linsen"}]},
        {"id": "l", "titel": "Linsen"}]}
    neu = _rufen({"entwurf": entwurf, "angelegt": {"nodes": [
        {"path": "Optik", "nodeId": _ID.format(1), "status": "created"},
        {"path": "Optik/Linsen", "nodeId": _ID.format(2), "status": "created"},
        {"path": "Linsen", "status": "failed", "code": "x"}]}})
    assert "wurzel_wlo_id" not in neu
    assert neu["knoten"][0]["kinder"][0]["wlo_id"] == _ID.format(2)
    assert "wlo_id" not in neu["knoten"][1]


def test_alte_kennungen_fallen_weg():
    """Review AS-Dd, Befund 2: ein Entwurf aus dem Bestand trägt Kennungen der Quellsammlung —
    nach dem Anlegen gilt nur, was ``angelegt`` nennt."""
    entwurf = {"titel": "P", "quelle": "wlo", "wurzel_wlo_id": _ID.format(8), "knoten": [
        {"id": "a", "titel": "A", "wlo_id": _ID.format(7)},
        {"id": "b", "titel": "B", "wlo_id": _ID.format(6)}]}
    neu = _rufen({"entwurf": entwurf, "angelegt": {"nodes": [
        {"path": "A", "status": "failed"},
        {"path": "B", "nodeId": _ID.format(3), "status": "existing"}]}})
    assert "wlo_id" not in neu["knoten"][0] and "wurzel_wlo_id" not in neu
    assert neu["knoten"][1]["wlo_id"] == _ID.format(3)
    assert entwurf["knoten"][0]["wlo_id"] == _ID.format(7)   # Eingabe unverändert


def test_ohne_einen_treffer_kein_wert():
    """Review AS-Dd, Befund 3: das Ergebnis eines anderen Baums verbindet nichts (bei_fehler)."""
    anderer = {"nodes": [{"path": "Chemie", "nodeId": _ID.format(1), "status": "created"}]}
    assert _rufen({"entwurf": _ENTWURF, "angelegt": anderer}) is None
    assert _rufen({"entwurf": _ENTWURF, "angelegt": {"unveraendert": True}}) is None
    assert _rufen({"entwurf": _ENTWURF, "angelegt": {"complete": True}}) is None


def test_mehrdeutige_pfade_bekommen_keine_kennung():
    """Review AS-Dd, Befund 4: der Server hält „a/B“ (ein Titel) und „A“→„B“ getrennt, der
    Vergleich ohne Groß/Klein nicht — dann lieber keine Kennung als eine falsche."""
    entwurf = {"titel": "P", "knoten": [
        {"id": "x", "titel": "a/B"},
        {"id": "a", "titel": "A", "kinder": [{"id": "b", "titel": "B"}]},
        {"id": "c", "titel": "Ein/Aus"}]}
    neu = _rufen({"entwurf": entwurf, "angelegt": {"nodes": [
        {"path": "a/B", "nodeId": _ID.format(1), "status": "created"},
        {"path": "A", "nodeId": _ID.format(2), "status": "created"},
        {"path": "A/B", "nodeId": _ID.format(3), "status": "created"},
        {"path": "Ein/Aus", "nodeId": _ID.format(4), "status": "created"}]}})
    assert "wlo_id" not in neu["knoten"][0]
    assert "wlo_id" not in neu["knoten"][1]["kinder"][0]
    assert neu["knoten"][1]["wlo_id"] == _ID.format(2)
    # ein Titel mit „/“, der eindeutig ist, wird zugeordnet
    assert neu["knoten"][2]["wlo_id"] == _ID.format(4)
    # auf Seiten des Entwurfs genauso: nur „A/B“ angelegt, zwei Punkte hätten diesen Pfad
    neu = _rufen({"entwurf": entwurf, "angelegt": {"nodes": [
        {"path": "A/B", "nodeId": _ID.format(3), "status": "created"},
        {"path": "Ein/Aus", "nodeId": _ID.format(4), "status": "created"}]}})
    assert "wlo_id" not in neu["knoten"][0] and "wlo_id" not in neu["knoten"][1]["kinder"][0]


def test_kaputte_punkte_brechen_nichts():
    entwurf = {"titel": "P", "knoten": ["kein punkt", {"id": "a"}, {"id": "b", "titel": "B",
                                                               "kinder": "keine liste"}]}
    neu = _rufen({"entwurf": entwurf, "angelegt": [{"path": "B", "nodeId": _ID.format(2)}, 7]})
    assert neu["knoten"][2]["wlo_id"] == _ID.format(2)


# ── Review AS-Dd, Befund 5: der Baum für ``wlo_create_collection_tree`` aus dem Entwurf ──────

def _baum(args):
    return asyncio.run(werkzeuge.DIENSTE["baum_aus_entwurf"](args))


def test_baum_aus_entwurf_mit_denselben_titeln():
    entwurf = {**_ENTWURF, "knoten": [
        {**_ENTWURF["knoten"][0], "beschreibung": "Bewegung", "wlo_id": _ID.format(1),
         "keywords": ["x"]}, _ENTWURF["knoten"][1]]}
    # SW-2: die Schlagworte reisen mit (``wlo_id`` nicht); ein Server, der sie im Baum nicht
    # kennt, bekommt sie nicht (``tests/test_mcp_baum_metadaten.py``).
    assert _baum({"entwurf": entwurf}) == [
        {"title": "Mechanik", "description": "Bewegung", "keywords": ["x"], "children": [
            {"title": "Kinematik"}, {"title": "Dynamik"}]},
        {"title": "Optik"}]
    assert typen.DIENST_EINGABE["baum_aus_entwurf"]["entwurf"] == typen.STRUKTUR


def test_baum_aus_entwurf_ohne_punkte_kein_wert():
    assert _baum({"entwurf": {"titel": "P", "knoten": []}}) is None
    assert _baum({"entwurf": "kein entwurf"}) is None
    assert _baum({"entwurf": {"titel": "P", "knoten": ["x", {"id": "a"}]}}) is None
