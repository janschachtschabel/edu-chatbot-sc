"""SW-5 (Plan 2026-11-14, Werkzeuge für Sammlungsstrukturen): was der MCP-Stand vom 15.11.2026
zu unseren Wünschen S11 und S13 gebaut hat.

- S11: der dritte Wert ``order: "position"`` (gesetzte Position, sonst Titel) an
  ``browse_collection_tree``, ``get_collection_overview`` und — neu mit ``order`` —
  ``list_collection_tree``; dazu das Merkmal ``childrenPositioned``. Das Themenbaum-Modul liest
  damit; wo keine Position unterscheidet, sortiert es selbst nach Titel.
- S13: ``unreadParents`` / ``refusedParents`` im Kopf der Baumliste — der Strukturabgleich
  begrenzt „nicht gefunden“ wieder auf den betroffenen Zweig.

Die Drahtformen stammen vom lokal gestarteten Server (gegen Staging, anonym, nur lesend) und aus
der Notiz des Entwicklers (``docs/plans/2026-11-15-antwort-sammlungsstrukturen-3.md`` im
MCP-Repo). Einen Ausfall konnten wir nicht herbeiführen; ``unreadParents`` ist nach der Notiz
und dem Quelltext geschrieben.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.mcp import angebot, baum_lesen, faehigkeiten, tool_args
from boerdi.ui_module import datenquelle, katalog, themenbaum
from tests.test_strukturabgleich_sw4 import (
    _LISTE,
    _NEU,
    OPTIK,
    _lauf,
    _liste,
    _Server,
    _ungewiss,
)
from tests.test_ui_themenbaum import THEMENBAUM, _Rufer

BAUM = "browse_collection_tree"
UEBERSICHT = "get_collection_overview"
LISTE = baum_lesen.WERKZEUG
_WERTE_NEU = ["title", "stored", "position"]


def _server(*, position: bool = True, liste_mit_order: bool = True) -> None:
    """Die Werkzeugliste des Servers: ``order`` mit seiner Aufzählung, wie ``tools/list`` sie
    nennt."""
    werte = _WERTE_NEU if position else ["title", "stored"]
    order = {"order": {"type": "string", "enum": werte}}
    assert faehigkeiten.uebernehmen([
        {"name": BAUM, "input_schema": {"properties": {"nodeId": {}, **order}}},
        {"name": UEBERSICHT, "input_schema": {"properties": {"nodeId": {}, **order}}},
        {"name": LISTE, "input_schema": {"properties": {
            "nodeId": {}, "depth": {}, "maxItems": {}, "skipCount": {},
            "includeContentCounts": {}, **(order if liste_mit_order else {})}}}])


def _definition(name: str) -> dict:
    roh = baum_lesen.DEFINITION if name == LISTE else {
        "type": "function", "function": {"name": name, "parameters": {
            "type": "object", "properties": {"nodeId": {"type": "string"}}}}}
    return baum_lesen.erweitert(roh)["function"]["parameters"]["properties"]


# ── S11: der dritte Wert, angeboten nur wo der Server ihn führt ──────────────────────────────

def test_position_steht_in_der_aufzaehlung_wenn_der_server_sie_fuehrt():
    _server()
    for name in (BAUM, UEBERSICHT):
        order = _definition(name)["order"]
        assert order["enum"] == _WERTE_NEU and "'position'" in order["description"]
    # Die Baumliste nimmt ``order`` jetzt auch; ihre Vorgabe ist die Reihenfolge des Repositorys.
    liste = _definition(LISTE)["order"]
    assert liste["enum"] == ["stored", "title", "position"]
    assert "'stored' (Vorgabe)" in liste["description"]
    assert baum_lesen.DEFINITION["function"]["parameters"]["properties"].get("order") is None


def test_ein_stand_ohne_position_bietet_sie_nicht_an():
    _server(position=False, liste_mit_order=False)
    assert _definition(BAUM)["order"]["enum"] == ["title", "stored"]
    assert "position" not in _definition(BAUM)["order"]["description"]
    assert "order" not in _definition(LISTE)
    assert not any(baum_lesen.position_bekannt(n) for n in (BAUM, UEBERSICHT, LISTE))


@pytest.mark.parametrize("werkzeug", [BAUM, UEBERSICHT, LISTE])
def test_position_reist_mit_und_wird_ohne_den_wert_am_server_abgelehnt(werkzeug):
    aus = tool_args.validate_tool_args(werkzeug, {"nodeId": OPTIK, "order": "position"})
    assert aus["order"] == "position"
    # Geprüft, nicht durchgereicht: Bei einem Prüffehler kämen die rohen Argumente zurück, ohne
    # die Vorgaben des Modells (Review SW-5, Befund 4).
    ohne = tool_args.validate_tool_args(werkzeug, {"nodeId": OPTIK})
    assert "order" not in ohne and {k: v for k, v in aus.items() if k != "order"} == ohne
    assert len(ohne) > 1
    roh = tool_args.validate_tool_args(werkzeug, {"nodeId": OPTIK, "order": "rueckwaerts"})
    assert roh == {"nodeId": OPTIK, "order": "rueckwaerts"}
    # Ein Server ohne den Wert verwürfe ihn still (oder wiese den Aufruf mit einer Schemameldung
    # ab) — die KI hielte die Liste für „gesetzte Position, sonst Titel“.
    _server(position=False, liste_mit_order=False)
    satz = angebot.lokale_ablehnung(werkzeug, {"nodeId": OPTIK, "order": "position"})
    assert satz and "order" in satz and "Nichts wurde gelesen" in satz
    _server()
    assert angebot.lokale_ablehnung(werkzeug, {"nodeId": OPTIK, "order": "position"}) is None
    assert angebot.lokale_ablehnung(werkzeug, {"nodeId": OPTIK, "order": "title"}) is None


def test_order_an_einer_baumliste_ohne_den_parameter_wird_abgelehnt():
    """Review SW-5, Befund 5: Der Stand vom 14.11. führt die Baumliste ohne ``order``. Er
    verwürfe 'title' still und lieferte in der Reihenfolge des Repositorys."""
    _server(position=False, liste_mit_order=False)
    for wert in ("title", "position"):
        satz = angebot.lokale_ablehnung(LISTE, {"nodeId": OPTIK, "order": wert})
        assert satz and "Nichts wurde gelesen" in satz, wert
    # die Vorgabe und „nicht angegeben“ gehen durch
    for args in ({"nodeId": OPTIK}, {"nodeId": OPTIK, "order": "stored"},
                 {"nodeId": OPTIK, "order": ""}):
        assert angebot.lokale_ablehnung(LISTE, args) is None, args


# ── S11: das Themenbaum-Modul ────────────────────────────────────────────────────────────────

def test_der_themenbaum_liest_mit_position_nur_wo_der_server_sie_fuehrt(monkeypatch):
    manifest = katalog.katalog()[THEMENBAUM]
    assert "order" not in datenquelle._gesendete_argumente(manifest, {"nodeId": "aaaa-1111"})
    _server(position=False)
    assert "order" not in datenquelle._gesendete_argumente(manifest, {"nodeId": "aaaa-1111"})
    _server()
    assert datenquelle._gesendete_argumente(manifest, {"nodeId": "aaaa-1111"}) == {
        "nodeId": "aaaa-1111", "depth": 2, "maxResults": 31, "order": "position"}
    r = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, _text, outcome = asyncio.run(datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"}))
    assert outcome.status == "success" and block is not None
    assert r.calls[0][1]["order"] == "position"


def _baum(*titel: str, kinder: dict[str, tuple] | None = None, **oben) -> dict:
    ergebnisse = []
    for i, t in enumerate(titel):
        knoten: dict = {"nodeId": f"n{i}", "title": t}
        if kinder and t in kinder:
            namen, merkmal = kinder[t]
            knoten["children"] = [{"nodeId": f"n{i}-{j}", "title": k}
                                  for j, k in enumerate(namen)]
            if merkmal is not None:
                knoten["childrenPositioned"] = merkmal
        ergebnisse.append(knoten)
    return {"parent": OPTIK, "results": ergebnisse, **oben}


def _titel(knoten: list[dict]) -> list[str]:
    return [k["titel"] for k in knoten]


def test_wo_keine_position_unterscheidet_sortiert_das_modul_nach_titel():
    """Gemessen an „Optik“ (15.11.2026): Mit ``position`` und ``childrenPositioned: false`` stehen
    erst die Sammlungen mit (gleicher) Position nach Titel, dann die ohne — zwei Alphabete
    hintereinander. Das Merkmal heißt dann „selbst sortieren“."""
    vom_server = ("Farben", "Geometrische Optik", "Menschliches Auge", "Wellenoptik",
                  "Kompendium_Fachinhalte", "Kompendium_Lehrpläne")
    daten = themenbaum.daten_aus(_baum(*vom_server, childrenPositioned=False))
    assert _titel(daten["knoten"]) == ["Farben", "Geometrische Optik", "Kompendium_Fachinhalte",
                                       "Kompendium_Lehrpläne", "Menschliches Auge", "Wellenoptik"]
    # wie im Wörterbuch: ä wie a, ohne Groß/Klein
    daten = themenbaum.daten_aus(_baum("Zoo", "Ökologie", "akustik", "Ägypten", "Äther",
                                       "Ørsted", "Łódź", childrenPositioned=False))
    assert _titel(daten["knoten"]) == ["Ägypten", "akustik", "Äther", "Łódź", "Ökologie",
                                       "Ørsted", "Zoo"]


def test_der_entwurf_aus_dem_baum_steht_in_derselben_reihenfolge():
    """Review SW-5, Befund 2: „Als Entwurf bearbeiten“ liest denselben Rohbaum. Ohne die eigene
    Sortierung stünden im Entwurf die zwei Alphabete, die der Baum gerade nicht zeigt."""
    from boerdi.ui_module import strukturentwurf_bestand

    vom_server = ("Farben", "Wellenoptik", "Kompendium_Fachinhalte")
    roh = _baum(*vom_server, childrenPositioned=False, kinder={
        "Farben": (("Spektrum", "Additiv"), False), "Wellenoptik": (("Beugung", "Abbe"), True)})
    entwurf = strukturentwurf_bestand.aus_bestand(roh, "Optik")
    baum = themenbaum.daten_aus(roh)
    assert _titel(entwurf["knoten"]) == _titel(baum["knoten"]) == [
        "Farben", "Kompendium_Fachinhalte", "Wellenoptik"]
    assert _titel(entwurf["knoten"][0]["kinder"]) == ["Additiv", "Spektrum"]
    assert _titel(entwurf["knoten"][2]["kinder"]) == ["Beugung", "Abbe"]      # gesetzt
    # Der Eingang bleibt, wie er war (der Rohbaum liegt im Cache des Clients).
    assert [k["title"] for k in roh["results"]] == list(vom_server)


def test_eine_vorgabe_des_manifests_geht_vor(monkeypatch):
    _server()
    manifest = {**katalog.katalog()[THEMENBAUM]}
    manifest["datenquelle"] = {**manifest["datenquelle"], "vorgaben": {"depth": 2,
                                                                      "order": "stored"}}
    assert datenquelle._gesendete_argumente(manifest, {"nodeId": "aaaa-1111"})["order"] == "stored"


@pytest.mark.parametrize("merkmal", [True, None])
def test_eine_gesetzte_oder_ungenannte_reihenfolge_bleibt_die_des_servers(merkmal):
    """``true``: die Abfolge eines Lehrplans. Fehlt das Merkmal (älterer Server, gekürzte Liste),
    weiß das Modul nichts — und ändert nichts."""
    lehrplan = ("Zellen", "Organe", "Atmung", "Blutkreislauf")
    oben = {} if merkmal is None else {"childrenPositioned": merkmal}
    assert _titel(themenbaum.daten_aus(_baum(*lehrplan, **oben))["knoten"]) == list(lehrplan)
    # ``1`` oder ein Text ist kein ``false``
    for kein_bool in (0, "false"):
        daten = themenbaum.daten_aus(_baum(*lehrplan, childrenPositioned=kein_bool))
        assert _titel(daten["knoten"]) == list(lehrplan)


def test_das_merkmal_gilt_je_ebene():
    baum = _baum("Zellen", "Atmung", childrenPositioned=True, kinder={
        "Zellen": (("Zellkern", "Aufbau", "Mitose"), False),       # keine Position: nach Titel
        "Atmung": (("Lunge", "Bronchien", "Alveolen"), True)})     # gesetzt: wie geliefert
    knoten = themenbaum.daten_aus(baum)["knoten"]
    assert _titel(knoten) == ["Zellen", "Atmung"]
    assert _titel(knoten[0]["kinder"]) == ["Aufbau", "Mitose", "Zellkern"]
    assert _titel(knoten[1]["kinder"]) == ["Lunge", "Bronchien", "Alveolen"]


def test_sortiert_wird_vor_dem_deckel():
    """Mehr Themen, als der Baum zeigt: Der Deckel schneidet die sortierte Liste, nicht die
    gelieferte."""
    viele = [f"Thema {i:02d}" for i in range(themenbaum.HOECHSTENS_OBEN, -1, -1)]   # 30 … 00
    daten = themenbaum.daten_aus(_baum(*viele, childrenPositioned=False))
    assert _titel(daten["knoten"])[:2] == ["Thema 00", "Thema 01"]
    assert len(daten["knoten"]) == themenbaum.HOECHSTENS_OBEN and daten["wurzel_mehr"] is True


# ── S13: der Ort eines Ausfalls im Strukturabgleich ──────────────────────────────────────────

def _kennt_die_liste() -> None:
    _server()


def _ausfall(**kopf) -> dict:
    return {**_LISTE, **kopf}


@pytest.mark.parametrize(("marke", "feld"), [("incomplete", "unreadParents"),
                                             ("restricted", "refusedParents")])
def test_ein_ausfall_macht_nur_unter_der_genannten_sammlung_ungewiss(monkeypatch, marke, feld):
    """Die Unterliste von „Linsen“ (``g-l``) wurde nicht gelesen: ``k1-1-2`` liegt darunter,
    ``k2-1-1`` hat keinen zugeordneten Elternpunkt und könnte dort stehen. Alles andere bleibt
    verbindlich „neu“ — vorher war nach jedem Ausfall jeder neue Punkt „nicht gefunden“."""
    _kennt_die_liste()
    erg = _lauf(monkeypatch, _Server(_liste(_ausfall(**{marke: True, feld: ["g-l"]}))))
    daten = erg.block.daten
    assert _ungewiss(daten["zeilen"]) == {"k1-1-2", "k2-1-1"}
    assert daten["unvollstaendig"] is True and daten["gekuerzt"] is True
    assert "nicht vollständig gelesen: 2 der neuen Punkte" in erg.text
    assert not katalog.daten_fehler(katalog.katalog()["ui_strukturabgleich"], daten)


def test_beide_listen_und_mehrere_seiten_zaehlen_zusammen(monkeypatch):
    _kennt_die_liste()
    seite1 = {**_LISTE, "items": _LISTE["items"][:3], "more": {"nextSkipCount": 250},
              "incomplete": True, "unreadParents": ["w"]}
    seite2 = {**_LISTE, "skipCount": 250, "items": _LISTE["items"][3:],
              "restricted": True, "refusedParents": ["g-l-s"]}
    erg = _lauf(monkeypatch, _Server(_liste(seite1), _liste(seite2)))
    # unter „Wellenoptik“ (Ebene 1) und unter „Sammellinsen“ (Ebene 3) fehlt etwas:
    # ``k1-1-1-2`` liegt unter Sammellinsen; die Punkte ohne Elternsammlung ab Ebene 2 können
    # unter Wellenoptik stehen. ``k1-1-2`` (unter „Linsen“, ganz gelesen) und ``k2`` bleiben neu.
    assert _ungewiss(erg.block.daten["zeilen"]) == {"k1-1-1-2", "k2-1", "k2-1-1"}


def test_ein_ausfall_erst_auf_einer_folgeseite_laesst_sich_nicht_eingrenzen(monkeypatch):
    """Review SW-5, Befund 1: Jede Seite ist ein eigener Lauf des Servers. Fällt eine Unterliste
    erst im zweiten aus, fehlt ihr Zweig dort, und alle späteren Positionen rücken vor — zwischen
    den Seiten fehlen Einträge, die nicht unter der genannten Sammlung liegen. Ein vorhandener
    Punkt hieße sonst verbindlich „neu“."""
    _kennt_die_liste()
    seite1 = {**_LISTE, "items": _LISTE["items"][:3], "more": {"nextSkipCount": 250}}
    seite2 = {**_LISTE, "skipCount": 250, "items": _LISTE["items"][3:],
              "incomplete": True, "unreadParents": ["g"]}       # die Kinder von „g“: auf Seite 1
    erg = _lauf(monkeypatch, _Server(_liste(seite1), _liste(seite2)))
    assert _ungewiss(erg.block.daten["zeilen"]) == set(_NEU)
    # Eine Ablehnung ist in jedem Lauf gleich — sie bleibt eingegrenzt, auch auf Seite 2.
    seite2 = {**_LISTE, "skipCount": 250, "items": _LISTE["items"][3:],
              "restricted": True, "refusedParents": ["g-l"]}
    erg = _lauf(monkeypatch, _Server(_liste(seite1), _liste(seite2)))
    assert _ungewiss(erg.block.daten["zeilen"]) == {"k1-1-2", "k2-1-1"}


@pytest.mark.parametrize("kopf", [
    {"incomplete": True},                                            # Stand ohne die Listen
    {"incomplete": True, "unreadParents": []},                       # sagt es nicht
    {"incomplete": True, "unreadParents": ["g-l"], "unreadParentsTotal": 73},   # mehr als 50
    {"incomplete": True, "unreadParents": "g-l"},                    # fremde Form
    {"incomplete": True, "unreadParents": ["g-l", 7]},
    {"incomplete": True, "unreadParents": [OPTIK]},                  # die Start-Sammlung selbst
    {"incomplete": True, "unreadParents": ["nicht-gelesen"]},        # ein fremder Zweig
    {"restricted": True, "refusedParents": ["g-l"], "incomplete": True},   # eine Liste fehlt
])
def test_sagt_die_antwort_nicht_wo_ist_jeder_neue_punkt_ungewiss(monkeypatch, kopf):
    """Die schlimme Richtung wäre ein verbindliches „neu“ über einem nicht gelesenen Zweig."""
    _kennt_die_liste()
    erg = _lauf(monkeypatch, _Server(_liste(_ausfall(**kopf))))
    assert _ungewiss(erg.block.daten["zeilen"]) == set(_NEU), kopf
    assert erg.block.daten["unvollstaendig"] is True


def test_die_listen_ohne_ihre_marke_zaehlen_nicht(monkeypatch):
    """Sie stehen laut Server genau dann, wenn ``incomplete`` bzw. ``restricted`` steht."""
    _kennt_die_liste()
    erg = _lauf(monkeypatch, _Server(_liste(_ausfall(unreadParents=["g-l"]))))
    assert _ungewiss(erg.block.daten["zeilen"]) == set()
    assert "unvollstaendig" not in erg.block.daten


def test_die_baumliste_wird_weiter_in_der_reihenfolge_des_repositorys_gelesen(monkeypatch):
    """Für den Abgleich zählt die Reihenfolge nicht — der Dienst sendet kein ``order``."""
    _kennt_die_liste()
    server = _Server(_liste(_LISTE))
    _lauf(monkeypatch, server)
    assert "order" not in server.aufrufe[0][1]
