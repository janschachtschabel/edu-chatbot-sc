"""N2 (Plan 2026-11-14): Werte hinzufügen statt ersetzen, mehrere Werte je Feld.

Bis zum MCP-Stand vom 14.11. ersetzte ``wlo_update_content`` Fach, Stufe, Typ und Zielgruppe und
nahm je Feld genau eine Bezeichnung; „füge das Fach Mathematik hinzu“ ging nicht. Der neue Stand
kennt ``addDiscipline`` / ``addEducationalContext`` / ``addUserRole``, Listen an den vier Feldern
und ``lookup_wlo_vocabulary("contentType")``. Der Chatbot bietet das nur an, wenn der
bereitgestellte Server es führt.

Die Schemata stammen aus ``tools/list`` beider Stände (neu: lokal gestartet, alt: bereitgestellt,
beide gelesen am 14.11.2026).
"""
from __future__ import annotations

import json

import pytest

from boerdi.api.schemas_mcp_curation import HINZUFUEGEN, MEHRWERTIG, etiketten
from boerdi.domain import write_confirm
from boerdi.services import agent_tools, response_tool_selection
from boerdi.services.mcp import angebot, faehigkeiten, tool_args, werte_hinzufuegen
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from tests.test_mcp_client import (  # noqa: F401 — ``mcp_state`` ist eine Fixture
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)

_LISTE = {"anyOf": [{"type": "string"},
                    {"minItems": 1, "maxItems": 20, "type": "array", "items": {"type": "string"}}]}
#: ``tools/list`` des neuen Stands, auf die Felder gekürzt, an denen der Chatbot etwas abliest.
_NEU = [
    {"name": "wlo_update_content", "input_schema": {"type": "object", "properties": {
        "nodeId": {"type": "string"}, "discipline": _LISTE, "contentType": _LISTE,
        "addDiscipline": _LISTE, "addEducationalContext": _LISTE, "addUserRole": _LISTE}}},
    {"name": "lookup_wlo_vocabulary", "input_schema": {"type": "object", "properties": {
        "vocabulary": {"type": "string", "enum": [
            "educationalContext", "discipline", "userRole", "lrt", "contentType", "license",
            "targetGroup", "universitySubject", "qualityFinding", "qualityScale"]},
        "query": {"type": "string", "maxLength": 100}}}},
]
#: … und des bereitgestellten: kein ``add…``, eine Bezeichnung je Feld, ``query`` gibt es schon.
_ALT = [
    {"name": "wlo_update_content", "input_schema": {"type": "object", "properties": {
        "nodeId": {"type": "string"}, "discipline": {"type": "string"},
        "contentType": {"type": "string"}}}},
    {"name": "lookup_wlo_vocabulary", "input_schema": {"type": "object", "properties": {
        "vocabulary": {"type": "string", "enum": [
            "educationalContext", "discipline", "userRole", "lrt", "license", "targetGroup",
            "universitySubject", "qualityFinding", "qualityScale"]},
        "query": {"type": "string", "maxLength": 100}}}},
]


def _d(name: str) -> dict:
    return next(t for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)
                if t["function"]["name"] == name)


def _eig(definition: dict) -> dict:
    return definition["function"]["parameters"]["properties"]


# ── Was der Server kann ───────────────────────────────────

def test_ein_neuer_wert_an_einem_alten_parameter_ist_erkennbar():
    """``vocabulary`` gab es immer, ``contentType`` als sein Wert erst im neuen Stand."""
    assert not faehigkeiten.kennt_wert("lookup_wlo_vocabulary", "vocabulary", "contentType")
    faehigkeiten.uebernehmen(_ALT)
    assert faehigkeiten.kennt("lookup_wlo_vocabulary", "query")
    assert not faehigkeiten.kennt_wert("lookup_wlo_vocabulary", "vocabulary", "contentType")
    assert not werte_hinzufuegen.angeboten()
    faehigkeiten.uebernehmen(_NEU)
    assert faehigkeiten.kennt_wert("lookup_wlo_vocabulary", "vocabulary", "contentType")
    assert not faehigkeiten.kennt_wert("lookup_wlo_vocabulary", "query", "contentType")
    assert not faehigkeiten.kennt_wert("gibt_es_nicht", "vocabulary", "contentType")
    assert werte_hinzufuegen.angeboten()


@pytest.mark.parametrize("schema", [{"enum": "lrt"}, {"enum": [1, None, "lrt"]}, "kein Schema", {}])
def test_eine_unerwartete_aufzaehlung_wirft_nicht(schema):
    assert faehigkeiten.uebernehmen([{"name": "w", "input_schema": {"properties": {"p": schema}}}])
    assert faehigkeiten.kennt("w", "p")
    assert not faehigkeiten.kennt_wert("w", "p", "contentType")


# ── Das Angebot an das Modell ───────────────────────────────

@pytest.mark.parametrize("stand", [None, _ALT])
@pytest.mark.parametrize("name", ["wlo_update_content", "wlo_update_contents",
                                  "wlo_create_content", "lookup_wlo_vocabulary"])
def test_ohne_den_neuen_stand_bleibt_die_definition_wie_sie_ist(stand, name):
    if stand:
        faehigkeiten.uebernehmen(stand)
    assert angebot.nach_faehigkeit(_d(name)) is _d(name)


def test_die_saetze_die_abgeloest_werden_stehen_in_den_vorlagen():
    """Driftet eine Vorlage, fände der Tausch den Satz nicht — und die KI läse „nur ersetzen“
    neben ``addDiscipline``."""
    assert werte_hinzufuegen.NUR_ERSETZEN in _d("wlo_update_content")["function"]["description"]
    assert werte_hinzufuegen.TYP_NICHT_NACHSCHLAGEN in _d(
        "lookup_wlo_vocabulary")["function"]["description"]
    assert " Fortsetzen wie bei" in _d("wlo_update_contents")["function"]["description"]
    for name in ("wlo_update_content", "wlo_create_content"):
        assert werte_hinzufuegen.TYP_FRAGEN in _eig(_d(name))["contentType"]["description"]


def test_die_felder_des_angebots_sind_die_der_argumentmodelle():
    assert set(werte_hinzufuegen._HINZU) == set(HINZUFUEGEN)
    assert set(MEHRWERTIG) <= set(_eig(_d("wlo_update_content")))


def test_der_inhaltstyp_darf_nachgeschlagen_werden_wenn_der_server_es_anbietet():
    """Review N2, M1: das Feld sagte weiter „nicht nachschlagen“, während das Nachschlagen den
    Weg anbot — drei Texte gegen einen."""
    faehigkeiten.uebernehmen(_NEU)
    for name in ("wlo_update_content", "wlo_create_content"):
        text = _eig(angebot.nach_faehigkeit(_d(name)))["contentType"]["description"]
        assert "vocabulary=contentType" in text and "(nicht nachschlagen)" not in text
        assert "Vorschlag aus seiner Ablehnung" in text           # zuerst bleibt die Ablehnung
    # Kennt der Server nur das Hinzufügen, nicht das Nachschlagen, bleibt der Satz.
    faehigkeiten.uebernehmen([_NEU[0], _ALT[1]])
    text = _eig(angebot.nach_faehigkeit(_d("wlo_update_content")))["contentType"]["description"]
    assert "(nicht nachschlagen)" in text


def test_die_uebrigen_werkzeuge_bleiben_im_neuen_stand_unberuehrt():
    faehigkeiten.uebernehmen(_NEU)
    geaendert = {t["function"]["name"] for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)
                 if werte_hinzufuegen.erweitert(t) is not t}
    assert geaendert == {"wlo_update_content", "wlo_update_contents", "wlo_create_content",
                         "lookup_wlo_vocabulary"}


def test_ein_rueckbau_des_servers_nimmt_das_angebot_zurueck():
    faehigkeiten.uebernehmen(_NEU)
    assert angebot.nach_faehigkeit(_d("wlo_update_content")) is not _d("wlo_update_content")
    faehigkeiten.uebernehmen(_ALT)
    for name in ("wlo_update_content", "lookup_wlo_vocabulary"):
        assert angebot.nach_faehigkeit(_d(name)) is _d(name)


def test_aendern_bietet_hinzufuegen_und_listen_an():
    faehigkeiten.uebernehmen(_NEU)
    vorlage = _d("wlo_update_content")
    vorher = json.dumps(vorlage, sort_keys=True)
    neu = angebot.nach_faehigkeit(vorlage)["function"]
    eig = neu["parameters"]["properties"]
    for feld in ("addDiscipline", "addEducationalContext", "addUserRole"):
        assert eig[feld]["type"] == "array" and "FUEGT hinzu" in eig[feld]["description"]
    assert "Nicht zusammen mit discipline" in eig["addDiscipline"]["description"]
    for feld in ("discipline", "educationalContext", "userRole", "contentType"):
        assert eig[feld]["type"] == "array" and "ERSETZT" in eig[feld]["description"]
        assert "Bezeichnung" in eig[feld]["description"]         # der bisherige Text bleibt davor
    assert "addContentType" not in eig                             # der Typ lässt sich nur ersetzen
    text = neu["description"]
    assert "nimm addDiscipline, addEducationalContext oder addUserRole" in text
    assert "nur ersetzen kann" not in text and "dafuer nicht aufrufen" not in text
    assert "wlo_suggest_metadata" in text                          # der Weg für einen weiteren Typ
    assert "Nie dasselbe Feld zugleich ersetzen und ergaenzen" in text
    assert "Die Vorschau nennt den Datensatz" in text              # der Rest bleibt
    assert json.dumps(vorlage, sort_keys=True) == vorher            # die Vorlage bleibt unberührt


def test_der_stapel_bietet_es_je_eintrag_an():
    faehigkeiten.uebernehmen(_NEU)
    neu = angebot.nach_faehigkeit(_d("wlo_update_contents"))["function"]
    eintrag = neu["parameters"]["properties"]["items"]["items"]["properties"]
    assert {"addDiscipline", "addEducationalContext", "addUserRole"} <= set(eintrag)
    assert "als Vorschlag hinterlegt" in eintrag["addUserRole"]["description"]
    assert eintrag["discipline"]["type"] == "array" and "ERSETZT" in eintrag["discipline"][
        "description"]
    # Review N2 (N5): die Zielgruppe wird im Stapel nicht geschrieben — auch nicht „ersetzt“.
    assert "als Vorschlag hinterlegt" in eintrag["userRole"]["description"]
    assert "ERSETZT" not in eintrag["userRole"]["description"]
    assert "Je Eintrag fuegen addDiscipline und addEducationalContext hinzu" in neu["description"]
    assert "content" not in eintrag                                 # wie bisher: ohne Inhalt


def test_anlegen_bekommt_listen_aber_kein_hinzufuegen():
    """Ein neuer Datensatz hat nichts, wozu etwas hinzukäme; der Server kennt die Felder dort
    nicht."""
    faehigkeiten.uebernehmen(_NEU)
    eig = _eig(angebot.nach_faehigkeit(_d("wlo_create_content")))
    assert eig["discipline"]["type"] == "array"
    assert "ERSETZT" not in eig["discipline"]["description"]      # dort gibt es nichts Bisheriges
    assert not [k for k in eig if k in ("addDiscipline", "addEducationalContext", "addUserRole")]
    assert "addToCollectionId" in eig


def test_nachschlagen_nennt_die_inhaltstypen_des_schreibens():
    faehigkeiten.uebernehmen(_NEU)
    neu = angebot.nach_faehigkeit(_d("lookup_wlo_vocabulary"))["function"]
    eig = neu["parameters"]["properties"]
    assert "contentType" in eig["vocabulary"]["enum"] and "lrt" in eig["vocabulary"]["enum"]
    assert "nicht dieselbe Liste wie lrt" in eig["vocabulary"]["description"]
    assert "query" in eig
    assert "NICHT unter lrt nachschlagen" in neu["description"]
    assert "vocabulary=contentType mit query" in neu["description"]
    assert "zuerst ihre Vorschlaege nehmen" in neu["description"]   # erst danach nachschlagen
    assert "SUCHE NICHT" in neu["description"]


def test_agent_und_muster_bekommen_dasselbe_angebot(monkeypatch):
    faehigkeiten.uebernehmen(_NEU)
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: True)
    agent = {t["function"]["name"]: t for t in agent_tools._mcp_werkzeuge(
        allow_curation=True, blocked_tools=None, tool_mode=None)}
    muster = {t["function"]["name"]: t for t in response_tool_selection._nameable_tools()}
    for katalog in (agent, muster):
        assert "addDiscipline" in _eig(katalog["wlo_update_content"])
        assert "contentType" in _eig(katalog["lookup_wlo_vocabulary"])["vocabulary"]["enum"]
    # N3 bleibt an den direkten Werkzeugen dem Agenten vorbehalten.
    assert "collection" not in _eig(muster["browse_collection_tree"])


def test_ohne_schreibrecht_kommt_kein_schreibwerkzeug_dazu(monkeypatch):
    faehigkeiten.uebernehmen(_NEU)
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: False)
    agent = {t["function"]["name"] for t in agent_tools._mcp_werkzeuge(
        allow_curation=True, blocked_tools=None, tool_mode=None)}
    muster = {t["function"]["name"] for t in response_tool_selection._nameable_tools()}
    for namen in (agent, muster):
        assert "wlo_update_content" not in namen and "lookup_wlo_vocabulary" in namen


# ── Was an den Server geht ─────────────────────────────────

def test_hinzufuegen_kommt_durch_die_pruefung_der_argumente():
    aus = tool_args.validate_tool_args("wlo_update_content", {
        "nodeId": "n1", "addDiscipline": ["Mathematik", "Informatik"], "addUserRole": "Lehrer"})
    assert aus == {"nodeId": "n1", "commit": False, "addDiscipline": ["Mathematik", "Informatik"],
                   "addUserRole": "Lehrer"}


@pytest.mark.parametrize("wert, gesendet", [
    ("Physik", "Physik"),
    (["Physik"], "Physik"),                    # eine einzelne nimmt auch ein Server ohne Listen
    (["Physik", " ", "", "Chemie "], ["Physik", "Chemie"]),
    (" Physik ", "Physik"),
    # Mehr als 20 lehnt der Server ab und sagt es — der Client schneidet nicht still ab.
    ([f"F{i}" for i in range(30)], [f"F{i}" for i in range(30)]),
])
def test_eine_oder_mehrere_bezeichnungen(wert, gesendet):
    for feld in ("discipline", "educationalContext", "userRole", "contentType", "addDiscipline"):
        aus = tool_args.validate_tool_args("wlo_update_content", {"nodeId": "n1", feld: wert})
        assert aus[feld] == gesendet, feld


@pytest.mark.parametrize("wert", [7, [["Physik"]], {"a": 1}])
def test_was_keine_bezeichnung_ist_bleibt_wie_es_ist(wert):
    assert etiketten(wert) == wert


@pytest.mark.parametrize("leer", ["", "   ", [], ["", " "], None])
def test_ein_leeres_feld_reist_nicht_mit(leer):
    aus = tool_args.validate_tool_args("wlo_update_content", {
        "nodeId": "n1", "title": "T", "discipline": leer, "addDiscipline": leer})
    assert aus == {"nodeId": "n1", "title": "T", "commit": False}


def test_beides_zugleich_entscheidet_der_server():
    """Der Server lehnt ``discipline`` neben ``addDiscipline`` ab und sagt es; der Client wählt
    nicht aus, sonst schriebe er etwas anderes, als die KI verlangt hat."""
    aus = tool_args.validate_tool_args("wlo_update_content", {
        "nodeId": "n1", "discipline": "Physik", "addDiscipline": "Mathematik"})
    assert aus["discipline"] == "Physik" and aus["addDiscipline"] == "Mathematik"


def test_anlegen_nimmt_listen_und_kein_hinzufuegen():
    aus = tool_args.validate_tool_args("wlo_create_content", {
        "title": "T", "discipline": ["Physik", "Chemie"], "addDiscipline": "Mathematik"})
    assert aus == {"title": "T", "discipline": ["Physik", "Chemie"]}


def test_der_stapel_laesst_hinzufuegen_je_eintrag_durch():
    aus = tool_args.validate_tool_args("wlo_update_contents", {"items": [
        {"nodeId": "n1", "addDiscipline": ["Mathematik"], "discipline": "", "fremd": 1},
        {"nodeId": "n2", "educationalContext": ["Sekundarstufe I", "Sekundarstufe II"]}]})
    # Review N2 (M3): wie im Einzelaufruf — eine einzelne Bezeichnung geht als Text.
    assert aus["items"] == [
        {"nodeId": "n1", "addDiscipline": "Mathematik"},
        {"nodeId": "n2", "educationalContext": ["Sekundarstufe I", "Sekundarstufe II"]}]
    aus = tool_args.validate_tool_args("wlo_update_contents", {"items": [
        {"nodeId": "n1", "discipline": [" Physik "], "addUserRole": ["", " "],
         "keywords": ["a", ""]}]})
    assert aus["items"] == [{"nodeId": "n1", "discipline": "Physik", "keywords": ["a"]}]


def test_etwas_anderes_als_text_in_der_liste_bleibt_dem_server_ueberlassen():
    """Fail-open wie bei jedem Feld: der Client repariert nur, was er versteht."""
    roh = {"nodeId": "n1", "discipline": ["Physik", 7]}
    assert tool_args.validate_tool_args("wlo_update_content", dict(roh)) == roh


def test_nachschlagen_mit_eingrenzung_kommt_durch():
    aus = tool_args.validate_tool_args("lookup_wlo_vocabulary",
                                       {"vocabulary": "contentType", "query": "Video"})
    assert aus == {"vocabulary": "contentType", "query": "Video"}
    assert tool_args.validate_tool_args("lookup_wlo_vocabulary", {"field": "lrt"}) == {
        "vocabulary": "lrt"}


@pytest.mark.parametrize("query, gesendet", [
    (None, {"vocabulary": "lrt"}), (7, {"vocabulary": "lrt"}), ("  ", {"vocabulary": "lrt"}),
    ("x" * 300, {"vocabulary": "lrt", "query": "x" * 100}),
])
def test_ein_unbrauchbares_query_kippt_das_nachschlagen_nicht(query, gesendet):
    """Review N2, M2: ``query`` ist jetzt angeboten. ``null`` schickte sonst die Rohargumente
    hinaus, und zod lehnte den ganzen Aufruf ab — vorher fiel das Feld einfach weg."""
    assert tool_args.validate_tool_args("lookup_wlo_vocabulary",
                                       {"field": "lrt", "query": query}) == gesendet


# ── Der Bestätigungsweg ────────────────────────────────────

def test_vorschau_und_ausfuehrung_tragen_dieselben_argumente():
    """Gemerkt werden die Argumente des Modells; ausgeführt wird im Folgezug genau das — durch
    dieselbe Prüfung. Listen und ``add…`` überstehen den Weg über JSON unverändert."""
    roh = {"nodeId": "n1", "addDiscipline": ["Mathematik"], "discipline": [],
           "educationalContext": ["Sekundarstufe I", " ", "Hochschule"]}
    vorschau = tool_args.validate_tool_args("wlo_update_content", dict(roh))
    gemerkt = json.loads(json.dumps(write_confirm.remember_pending(
        "wlo_update_content", roh, "tok-1", now=1000.0)))
    eingeloest = write_confirm.confirmed_args(gemerkt, "wlo_update_content", now=1010.0)
    ausfuehrung = tool_args.validate_tool_args("wlo_update_content", eingeloest)
    schluessel = write_confirm.CONFIRM_TOKEN_FIELD
    assert ausfuehrung.pop(schluessel) == "tok-1"
    assert ausfuehrung == vorschau == {
        "nodeId": "n1", "commit": False, "addDiscipline": "Mathematik",
        "educationalContext": ["Sekundarstufe I", "Hochschule"]}


# ── Ein Server, der es nachweislich nicht kann ────────────────────────

def test_hinzufuegen_an_einem_alten_server_wird_gesagt_statt_verschluckt():
    """Review N2, M4: ein Server ohne ``add…`` verwirft das Feld still — mit ``title`` daneben
    schriebe er nur den Titel, und das Fach fehlte wortlos."""
    args = {"nodeId": "n1", "title": "T", "addDiscipline": "Mathematik"}
    assert werte_hinzufuegen.nicht_moeglich("wlo_update_content", args) is None   # Stand unbekannt
    faehigkeiten.uebernehmen(_ALT)
    grund = werte_hinzufuegen.nicht_moeglich("wlo_update_content", args)
    assert grund and "addDiscipline" in grund and "wlo_suggest_metadata" in grund
    assert "Mathematik" not in grund                               # kein Inhalt im Fehlertext
    assert werte_hinzufuegen.nicht_moeglich("wlo_update_content", {"nodeId": "n1", "title": "T"}
                                            ) is None
    grund = werte_hinzufuegen.nicht_moeglich("wlo_update_contents", {"items": [
        {"nodeId": "n1", "title": "T"}, {"nodeId": "n2", "addUserRole": "Lehrer"}, "kaputt"]})
    assert grund and "addUserRole" in grund
    assert werte_hinzufuegen.nicht_moeglich("wlo_create_content", args) is None
    faehigkeiten.uebernehmen(_NEU)
    assert werte_hinzufuegen.nicht_moeglich("wlo_update_content", args) is None


def test_der_client_schickt_einen_solchen_aufruf_nicht_hinaus(monkeypatch, mcp_state):  # noqa: F811
    import asyncio

    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [])
    faehigkeiten.uebernehmen(_ALT)
    antwort = asyncio.run(client.call_mcp_tool_antwort(
        "wlo_update_content", {"nodeId": "n1", "title": "T", "addDiscipline": "Mathematik"}))
    assert calls == []
    assert antwort.art == "tool" and antwort.code == "invalid_input"
    assert antwort.text.startswith("MCP error [invalid_input]: Dieser Server kann Werte nicht")
