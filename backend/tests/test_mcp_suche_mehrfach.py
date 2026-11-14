"""N4 (Plan 2026-11-14): mehrere Inhaltssuchen in einem Aufruf (``search_wlo_content_many``).

Der MCP-Server kennt das Werkzeug ab dem Stand vom 14.11.; der bereitgestellte nicht. Der Chatbot
bietet es nur an, wenn die Werkzeugliste des Servers es führt, und nimmt es bewusst nicht in den
Katalog auf: den reicht der Muster-Weg als Ganzes weiter.

Die Antwortform stammt vom neuen Stand, lokal gestartet gegen das Staging-Repository (14.11.2026):
Markdown als Text, die Treffer dazu im strukturierten Teil. Der Client stellt den strukturierten
Teil als Umschlag vor den Text — daraus entstehen die Karten, das Modell bekommt nur den Text.
"""
from __future__ import annotations

import asyncio
import json
import pathlib

import pytest
import yaml

from boerdi.domain import mcp_unvollstaendig
from boerdi.domain.host_capabilities import KURATIEREND, LESEND, erlaubt
from boerdi.domain.tool_result_redaction import (
    _redact_search_content_for_llm,
    redigiere_strukturell,
)
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.domain.url_helpers import _extract_web_links_from_text
from boerdi.services import (
    agent_tool_overview,
    agent_tools,
    response_tool_selection,
    turn_persist,
)
from boerdi.services.card_collect import CARD_YIELDING_TOOLS, collect_cards
from boerdi.services.mcp import (
    angebot,
    faehigkeiten,
    suche_mehrfach,
    tool_args,
    tool_cache,
    tool_descriptions,
)
from boerdi.services.mcp.parsers import parse_search_many_cards
from boerdi.services.mcp.parsers.json_scan import load_leading
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.safety import regex_gate
from tests.test_agent_loop import _lauf, _OutcomeFake, _resp_text, _resp_tools, _tool_call
from tests.test_mcp_client import (  # noqa: F401 — ``mcp_state`` ist eine Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)

NAME = "search_wlo_content_many"
_SEEDS = pathlib.Path(__file__).parents[1] / "seeds"
_LEIFI = "https://www.leifiphysik.de/optik/lichtreflexion/versuche/reflexion-von-licht-simulation"

#: Die Antwort des Servers in Markdown (gekürzt, wörtlich): je Anfrage ein Block unter ihrer id.
_ANTWORT = (
    "## s1 — „Reflexion von Licht“ (2)\n"
    "1. **Reflexion von Licht (Simulation)**\n"
    "   Interaktives Medium · Übungsmaterial · Arbeitsblatt · Sekundarstufe I · Copyright, freier "
    "Zugang\n"
    f"   {_LEIFI}\n"
    "   nodeId: 9a6f8eb1-a5fa-49c6-88f1-aa38d3633200\n"
    "   Die Reflexion von Licht wird mit diesem Java-Applet anschaulich demonstriert.\n"
    "Es gibt weitere Treffer — search_wlo_content liefert mehr und blättert.")
_NICHT_BEANTWORTET = (
    "## a — „Optik“ (1)\n1. **Mondphasen - Experiment**\n   nodeId: "
    "85db22e2-64fd-4a57-848c-6bd9bc8cf394\n\n"
    "## Nicht beantwortet — KEIN Befund „keine Treffer“\n"
    "b: nicht beantwortet (unresolved_filter: discipline „Quatschfach\")")


def _treffer(kennung: str, titel: str, adresse: str) -> dict:
    """Ein Treffer in Kurzform, wie ``structuredContent.results[id].results[]`` ihn trägt."""
    return {"nodeId": kennung, "title": titel, "url": adresse, "description": "Kurz.",
            "learningResourceTypes": ["Video"], "educationalContexts": ["Sekundarstufe I"],
            "license": "CC BY", "previewUrl": f"https://repo.example/preview?nodeId={kennung}"}


_REFLEXION = _treffer("9a6f8eb1-a5fa-49c6-88f1-aa38d3633200", "Reflexion von Licht (Simulation)",
                      _LEIFI)
_LINSEN = _treffer("85db22e2-64fd-4a57-848c-6bd9bc8cf394", "Linsen – Video",
                   "https://www.youtube.com/watch?v=abc")
#: Der strukturierte Teil: zwei Anfragen, ein Material steht bei beiden.
_STRUKTUR = {"results": {"s1": {"count": 1, "results": [_REFLEXION], "more": True},
                         "s2": {"count": 2, "results": [_LINSEN, _REFLEXION]}},
             "missing": []}


def _server_kennt() -> None:
    assert faehigkeiten.uebernehmen([
        {"name": NAME, "input_schema": {"properties": {"queries": {}, "maxResults": {}}}},
        {"name": "search_wlo_content", "input_schema": {"properties": {"query": {}}}}])


def _namen(tools: list[dict]) -> set[str]:
    return {t["function"]["name"] for t in tools}


def _agent(**kw) -> set[str]:
    return _namen(agent_tools._mcp_werkzeuge(**{"allow_curation": False, "blocked_tools": None,
                                                "tool_mode": None, **kw}))


# ── Das Angebot ────────────────────────────────────────

def test_das_werkzeug_steht_nicht_im_katalog():
    """Der Muster-Weg reicht ``TOOL_DEFINITIONS`` als Ganzes weiter — ein Server ohne das Werkzeug
    wiese dort jeden Aufruf ab."""
    assert NAME not in _namen(TOOL_DEFINITIONS)
    assert suche_mehrfach.DEFINITION["function"]["name"] == NAME


def test_angeboten_wird_es_nur_wenn_der_server_es_fuehrt(monkeypatch):
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: False)
    assert angebot.zusaetzliche() == []
    assert NAME not in _agent() and NAME not in _namen(response_tool_selection._nameable_tools())
    _server_kennt()
    assert angebot.zusaetzliche() == [suche_mehrfach.DEFINITION]
    assert NAME in _agent() and NAME in _namen(response_tool_selection._nameable_tools())
    # Ein Rückbau des Servers nimmt es wieder weg.
    faehigkeiten.uebernehmen([{"name": "search_wlo_content",
                               "input_schema": {"properties": {"query": {}}}}])
    assert NAME not in _agent()


def test_sperren_und_modus_gelten_auch_fuer_das_neue_werkzeug():
    _server_kennt()
    assert NAME not in _agent(blocked_tools=[NAME])
    # Lesend: in beiden Modi eines Gastgebers erlaubt, wie jede Suche.
    assert erlaubt(NAME, LESEND) and erlaubt(NAME, KURATIEREND)
    assert NAME in _agent(tool_mode=LESEND) and NAME in _agent(tool_mode=KURATIEREND)
    # Persönliche Daten oder eine Krise sperren jede Volltext- und Materialsuche, auch diese.
    assert NAME in regex_gate.SPERRE_PERSOENLICH and NAME in regex_gate.SPERRE_KRISE


def test_im_studio_abgeschaltet_bekommt_es_kein_weg(monkeypatch):
    """Review N4 (m1): der Schalter je MCP-Server (``werkzeuge_aus``) wirkt auf Agent und Muster."""
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: False)
    _server_kennt()
    aus = frozenset({NAME})
    monkeypatch.setattr(agent_tools, "verborgene_werkzeuge", lambda: aus)
    monkeypatch.setattr(response_tool_selection, "verborgene_werkzeuge", lambda: aus)
    assert NAME not in _agent()
    assert NAME not in _namen(response_tool_selection._nameable_tools())


def test_die_beschreibung_sagt_was_nicht_beantwortet_heisst():
    text = suche_mehrfach.DEFINITION["function"]["description"]
    assert "KEIN Befund 'keine Treffer'" in text
    # Titel und Link nennt die KI selbst — das stimmt auch ohne Chat (``/api/agent`` kennt keine
    # Karten). Im Chat kommen Karten dazu, begrenzt; die Beschreibung verspricht nicht mehr.
    assert "Nenne je Teil den Titel und den Link" in text and "NICHT als Karten" not in text
    assert "zusaetzlich als Karten (reihum je Anfrage, begrenzt)" in text
    eig = suche_mehrfach.DEFINITION["function"]["parameters"]["properties"]
    assert eig["queries"]["items"]["required"] == ["id", "query"]
    assert "OER" in eig["license"]["description"]
    assert set(eig["queries"]["items"]["properties"]["filters"]["properties"]) == {
        "educationalContext", "discipline", "userRole", "learningResourceType", "publisher",
        "license"}


def test_die_registry_des_servers_nennt_das_werkzeug():
    """``_get_server_url_for_tool`` sucht den Namen in der Registry; der Wächter über
    ``TOOL_DEFINITIONS`` sieht dieses Werkzeug nicht, weil es dort nicht steht."""
    roh = yaml.safe_load((_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8"))
    [wlo] = [s for s in roh["servers"] if s["id"] == "wlo-mcp"]
    assert NAME in wlo["tools"]


def test_die_gepflegten_sperrlisten_nennen_das_werkzeug():
    """Review N4 (m3): neben den festen Sperren (``regex_gate``) die zwei im Studio gepflegten."""
    basis = _SEEDS / "01-base"
    policy = yaml.safe_load((basis / "policy.yaml").read_text(encoding="utf-8"))
    [regel] = [r for r in policy["rules"] if r.get("id") == "pol-no-personal-data-search"]
    assert NAME in regel["effect"]["block_tools"]
    schutz = yaml.safe_load((basis / "safety-config.yaml").read_text(encoding="utf-8"))
    assert NAME in schutz["crisis_blocked_tools"]


# ── Studio: Schalter und Zeile ───────────────────────────────

def test_das_studio_zeigt_das_werkzeug_und_warum_es_fehlt(monkeypatch):
    """Review N4 (m1): eine Zeile auf der Seite „Werkzeuge“ — solange der Server es nicht führt,
    mit diesem Grund — und ein Schalter am MCP-Server."""
    monkeypatch.setattr(agent_tool_overview, "schreiben_erlaubt", lambda: False)
    monkeypatch.setattr(agent_tool_overview, "load_policy_config", lambda: {"rules": [
        {"id": "pol-no-personal-data-search", "effect": {"block_tools": [NAME]}}]})

    def _zeile() -> dict:
        return next(t for t in agent_tool_overview.werkzeugliste()["tools"] if t["name"] == NAME)

    ohne = _zeile()
    assert ohne["kind"] == "read" and ohne["offered"] is False
    assert {"code": "server_lacks"} in ohne["locks"]
    assert {"code": "safety_fixed", "signals": ["pii"]} in ohne["locks"]
    assert {"code": "policy", "rules": ["pol-no-personal-data-search"]} in ohne["locks"]
    _server_kennt()
    mit = _zeile()
    assert mit["offered"] is True and {"code": "server_lacks"} not in mit["locks"]
    assert NAME in tool_descriptions._KATALOG


def test_die_seite_mcp_server_warnt_nicht_dass_jeder_aufruf_scheitert(monkeypatch):
    """Review 2 (Befund 3): „fehlt am Server — eingeschaltet scheitert jeder Aufruf“ gilt für
    Katalog-Werkzeuge. Dieses wird ohne den Server gar nicht angeboten; die Seite „Werkzeuge“
    nennt den Grund. Den Schalter trägt es trotzdem."""
    primaer = {"id": "wlo-mcp", "enabled": True, "url": "https://mcp.example",
               "tools": [NAME, "search_skill", "get_url_text"]}

    async def _live(_url):
        return {"get_url_text": "holt Text"}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [primaer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _live)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_fehlen_am_server"] == ["search_skill"]
    assert NAME in server["werkzeuge_im_katalog"]


# ── Was an den Server geht ─────────────────────────────────

def test_die_anfragen_gehen_in_den_schranken_des_servers_hinaus():
    aus = tool_args.validate_tool_args(NAME, {
        "queries": [
            {"id": "s1", "query": "  Reflexion von Licht ", "fremd": 1,
             "filters": {"discipline": "Physik", "license": " ", "userRole": None,
                         "educationalLevel": "Sekundarstufe I"}},
            {"id": 2, "query": "x" * 300},
            {"id": "s" * 60, "query": "Linsen", "filters": {}},
            {"id": "s4", "query": "Brechung", "filters": {"learningResourceType": ["Video"]}},
        ],
        "discipline": "Physik", "educationalContext": "", "license": ["CC BY"], "maxResults": 9,
        # ``null`` und eine leere Liste heißen „nicht angegeben“, die alten Namen werden übersetzt.
        "userRole": None, "publisher": [], "resourceType": "Video",
        "distinct": True, "outputFormat": "json", "erfunden": True})
    assert aus == {
        "queries": [
            {"id": "s1", "query": "Reflexion von Licht",
             "filters": {"discipline": "Physik", "educationalContext": "Sekundarstufe I"}},
            {"id": "2", "query": "x" * 200},
            {"id": "s" * 40, "query": "Linsen"},
            # Eine Liste mit genau einem Wert ist dieser Wert.
            {"id": "s4", "query": "Brechung", "filters": {"learningResourceType": "Video"}}],
        "discipline": "Physik", "license": "CC BY", "learningResourceType": "Video",
        "maxResults": 5, "distinct": True}


@pytest.mark.parametrize("kaputt", [
    {"query": "ohne id"}, {"id": "a"}, {"id": "a", "query": "  "}, {"id": True, "query": "x"},
    "keine Anfrage", 7,
])
def test_was_keine_anfrage_sein_kann_faellt_nicht_still_weg(kaputt):
    """Fiele sie weg, bliebe ein Schritt ohne Suche und sähe aus wie „keine Treffer“. Der Server
    lehnt den Aufruf ab und sagt es."""
    aus = tool_args.validate_tool_args(NAME, {"queries": [{"id": "s1", "query": "Optik"}, kaputt]})
    assert aus["queries"] == [{"id": "s1", "query": "Optik"}, kaputt]


@pytest.mark.parametrize("filter_", [
    {"learningResourceType": ["Video", "Arbeitsblatt"]},   # mehrere Werte
    {"license": ["CC BY", "CC0"], "discipline": "Physik"},
    {"publisher": 7},
    "Physik",                                              # kein Objekt
    ["Video"],
])
def test_ein_filter_der_keiner_sein_kann_faellt_nicht_still_weg(filter_):
    """Review N4 (M3): Fiele er weg, liefe die Suche ungefiltert und sähe gefiltert aus — die KI
    gäbe Treffer jeder Lizenz als „CC BY“ aus. Er bleibt stehen, der Server lehnt den Aufruf ab."""
    aus = tool_args.validate_tool_args(NAME, {
        "queries": [{"id": "s1", "query": "Optik", "filters": filter_}]})
    assert aus["queries"] == [{"id": "s1", "query": "Optik", "filters": filter_}]


def test_ein_unbekannter_filtername_wird_abgelehnt_statt_still_verworfen(monkeypatch, mcp_state):  # noqa: F811
    """Review 2 (Befund 4): Den Namen ließe der Server still weg — die Suche liefe ungefiltert und
    sähe gefiltert aus. Sagen kann es nur der Client."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [])
    args = {"queries": [{"id": "s1", "query": "Optik"},
                        {"id": "s2", "query": "Linsen",
                         "filters": {"fach": "Physik", "discipline": "Physik"}}]}
    antwort = asyncio.run(client.call_mcp_tool_antwort(NAME, args))
    assert calls == [] and antwort.art == "tool" and antwort.code == "invalid_input"
    assert "Unbekannter Filter 'fach' in Anfrage 's2'" in antwort.text
    assert "learningResourceType" in antwort.text and "Nichts wurde gesucht" in antwort.text


def test_mehrere_werte_im_gemeinsamen_filter_gehen_roh_zum_server():
    """Das Modell lässt je Filter einen Text zu; mit einer Liste scheitert die Prüfung, die
    Argumente gehen roh hinaus, und der Server lehnt sie ab (kein Fächern, kein Weglassen)."""
    roh = {"queries": [{"id": "s1", "query": "Optik"}], "license": ["CC BY", "CC0"]}
    assert tool_args.validate_tool_args(NAME, dict(roh)) == roh


def test_mehr_als_acht_anfragen_lehnt_der_client_mit_einem_satz_ab(monkeypatch, mcp_state):  # noqa: F811
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [])
    neun = {"queries": [{"id": f"q{i}", "query": f"Thema {i}"} for i in range(9)]}
    antwort = asyncio.run(client.call_mcp_tool_antwort(NAME, neun))
    assert calls == []                                       # nichts ging hinaus
    assert antwort.art == "tool" and antwort.code == "invalid_input"
    assert "Hoechstens 8 Anfragen" in antwort.text and "genannt wurden 9" in antwort.text
    assert suche_mehrfach.nicht_moeglich(NAME, {"queries": neun["queries"][:8]}) is None
    assert suche_mehrfach.nicht_moeglich("search_wlo_content", neun) is None


@pytest.mark.parametrize("anfragen", [[], "Optik", None, {"id": "a", "query": "Optik"}])
def test_keine_liste_oder_keine_anfrage_lehnt_der_client_ebenso_ab(anfragen):
    """Review N4 (NIT 1): dieselbe Begründung wie bei „mehr als acht“ — der Server antwortete mit
    einer Schemameldung."""
    satz = angebot.lokale_ablehnung(NAME, {"queries": anfragen})
    assert satz and "1 bis 8 Anfragen" in satz and "Nichts wurde gesucht" in satz


# ── Was zurückkommt ────────────────────────────────────

def test_die_antwort_reist_als_umschlag_und_text_und_steht_im_cache(monkeypatch, mcp_state):  # noqa: F811
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [
        {"result": {"content": [_text_part(_ANTWORT)], "structuredContent": _STRUKTUR}}])
    args = {"queries": [{"id": "s1", "query": "Reflexion von Licht"},
                        {"id": "s2", "query": "Linsen"}], "maxResults": 2}
    erste = asyncio.run(client.call_mcp_tool(NAME, dict(args)))
    # Vorn der strukturierte Teil, dahinter der Text des Servers, unverändert.
    assert load_leading(erste) == _STRUKTUR
    assert mcp_unvollstaendig.ohne_umschlag(erste) == _ANTWORT
    # Markdown angefordert: den Text für das Modell schreibt der Server, nicht der Chatbot.
    assert "outputFormat" not in calls[0]["arguments"]
    assert asyncio.run(client.call_mcp_tool(NAME, dict(args))) == erste
    assert len(calls) == 1
    assert tool_cache._ttl_for_tool(NAME) == tool_cache._ttl_for_tool("search_wlo_content")


def test_ohne_strukturierten_teil_bleibt_der_text_wie_er_ist():
    assert suche_mehrfach.mit_umschlag(None, _ANTWORT) == _ANTWORT
    assert suche_mehrfach.mit_umschlag({"missing": []}, _ANTWORT) == _ANTWORT
    # ``outputFormat: json`` kam mit rohen Argumenten durch: der Text ist schon der Umschlag.
    schon = json.dumps(_STRUKTUR)
    assert suche_mehrfach.mit_umschlag(_STRUKTUR, schon) == schon
    assert mcp_unvollstaendig.ohne_umschlag(schon) == schon
    assert mcp_unvollstaendig.ohne_umschlag(_ANTWORT) == _ANTWORT


def test_die_treffer_werden_karten():
    """Review N4 (M1): ohne Karten sähe die Person die Treffer nicht — die Endverarbeitung nimmt
    Links aus dem Antworttext."""
    antwort = suche_mehrfach.mit_umschlag(_STRUKTUR, _ANTWORT)
    assert NAME in CARD_YIELDING_TOOLS
    alle: list[dict] = []
    karten = collect_cards(alle, NAME, antwort)
    # Reihum je Anfrage, jedes Material einmal.
    assert [k["node_id"] for k in karten] == [_REFLEXION["nodeId"], _LINSEN["nodeId"]]
    assert [k["node_id"] for k in alle] == [k["node_id"] for k in karten]
    erste = karten[0]
    assert erste["title"] == "Reflexion von Licht (Simulation)" and erste["url"] == _LEIFI
    assert erste["node_type"] == "content" and erste["license"] == "CC BY"
    assert erste["preview_url"] and erste["learning_resource_types"] == ["Video"]
    # Ein JSON weiter hinten im Text ist kein Umschlag; ein Fehlertext ergibt keine Karten.
    assert parse_search_many_cards(_ANTWORT + "\n" + json.dumps(_STRUKTUR)) == []
    assert parse_search_many_cards("MCP error [invalid_input]: …") == []
    assert parse_search_many_cards(json.dumps({"results": [_REFLEXION]})) == []


def test_jeder_teil_bekommt_eine_karte_solange_der_deckel_reicht():
    """Review 2 (Befund 1): Die Materialien-Box ist gedeckelt. In der Reihenfolge der Anfragen
    blieben mit dem Standard-Deckel (3) nur Karten zur ersten Anfrage. Reihum, und mit dem Deckel
    des Lernpfads (Vorgabe 5), trägt jeder von fünf Teilen eine Karte."""
    struktur = {"results": {f"s{i}": {"count": 3, "results": [
        _treffer(f"{i}{j}", f"T{i}{j}", f"https://example.org/{i}/{j}") for j in range(3)]}
        for i in range(5)}, "missing": []}
    karten = collect_cards([], NAME, suche_mehrfach.mit_umschlag(struktur, "## s0"))
    assert len(karten) == 15
    schluessel, vorgabe = turn_persist._materialien_deckel("AGENT", mehrfachsuche=True)
    assert (schluessel, vorgabe) == ("materialien_max_lernpfad", 5)
    assert [k["title"] for k in karten[:vorgabe]] == ["T00", "T10", "T20", "T30", "T40"]
    # Ohne die Mehrfachsuche bleibt es beim Standard, der Lernpfad behält seinen Deckel.
    assert turn_persist._materialien_deckel("AGENT", mehrfachsuche=False) == ("materialien_max", 3)
    assert turn_persist._materialien_deckel("M09", mehrfachsuche=False)[0] == schluessel
    # Eine Anfrage ohne Treffer oder mit weniger Treffern hält die anderen nicht auf.
    struktur["results"]["s1"]["results"] = []
    struktur["results"]["s2"]["results"] = struktur["results"]["s2"]["results"][:1]
    reihum = collect_cards([], NAME, suche_mehrfach.mit_umschlag(struktur, "## s0"))
    assert [k["title"] for k in reihum[:6]] == ["T00", "T20", "T30", "T40", "T01", "T31"]


def test_die_titel_im_antworttext_bleiben_die_links_gehen():
    """Der Fall aus dem ersten Review: Die KI antwortet mit ``- [Titel](Adresse)`` je Thema.
    Nach einer Mehrfachsuche bleiben die Zeilen mit ihren Titeln stehen (``turn_links``:
    ``keep_bullet_labels``, wie beim Lernpfad); die Links nimmt die Endverarbeitung heraus. Keine
    der Adressen landet als „Webseite“ in der falschen Box — sie gehören zu Karten. Was über den
    Deckel der Box hinausgeht, hat im Chat danach einen Titel, aber keinen Link."""
    karten = collect_cards([], NAME, suche_mehrfach.mit_umschlag(_STRUKTUR, _ANTWORT))
    text = ("Zu den Themen:\n\n"
            f"- [Reflexion von Licht (Simulation)]({_LEIFI})\n"
            f"- [Linsen – Video]({_LINSEN['url']})\n")
    sauber, webseiten = _extract_web_links_from_text(text, cards=karten, keep_bullet_labels=True)
    assert "](" not in sauber and webseiten == []
    assert "- Reflexion von Licht (Simulation)" in sauber and "- Linsen – Video" in sauber
    assert {_LEIFI, _LINSEN["url"]} <= {k["url"] for k in karten}


def test_das_modell_bekommt_den_ganzen_text_ohne_umschlag():
    """Review N4 (M2): im Muster-Weg schnitt der blinde Deckel bei 4 000 Zeichen ab — „Nicht
    beantwortet“ steht am Ende und fiel zuerst. Beide Wege bekommen den Text des Servers ganz."""
    block = "".join(f"## s{i} — „Thema {i}“ (5)\n" + "1. **Titel**\n   Zeile\n" * 60
                    for i in range(6))
    text = block + "\n## Nicht beantwortet — KEIN Befund „keine Treffer“\ns7: nicht beantwortet"
    assert len(text) > 8000
    struktur = {"results": {"s0": {"count": 1, "results": [_REFLEXION]}},
                "missing": [{"part": "s7", "code": "timeout"}]}
    antwort = suche_mehrfach.mit_umschlag(struktur, text)
    karten = collect_cards([], NAME, antwort)
    for gruppiert in (True, False):
        sicht = _redact_search_content_for_llm(NAME, antwort, karten, gruppiert)
        assert sicht == text.strip()
    assert redigiere_strukturell(NAME, antwort) == text.strip()
    # Der Umschlag (Vorschaubilder, Rohfelder) reist nicht ins Modell.
    assert "previewUrl" not in redigiere_strukturell(NAME, antwort)


def test_in_der_agent_schleife_erntet_die_naht_den_umschlag_das_modell_liest_den_text(monkeypatch):
    """Review 2 (Befund 7): der ganze Weg einer Runde. Die Ernte bekommt die Antwort mit dem
    Umschlag (daraus die Karten), in der Nachrichtenkette steht nur der Text des Servers."""
    antwort = suche_mehrfach.mit_umschlag(_STRUKTUR, _ANTWORT)
    alle: list[dict] = []
    _fake, _run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(NAME, {"queries": [{"id": "s1", "query": "Reflexion"},
                                                   {"id": "s2", "query": "Linsen"}]})]),
        _resp_text("fertig"),
    ], outcome=_OutcomeFake({NAME: antwort}),
        on_tool_result=lambda name, text: collect_cards(alle, name, text))
    assert [k["node_id"] for k in alle] == [_REFLEXION["nodeId"], _LINSEN["nodeId"]]
    [werkzeug_nachricht] = [m for m in msgs if m.get("role") == "tool"]
    assert werkzeug_nachricht["content"] == _ANTWORT
    assert "previewUrl" not in werkzeug_nachricht["content"]


def test_ein_ausreisser_wird_gedeckelt_und_behaelt_das_ende():
    """Review 2 (Befund 9): Titel und Adressen deckelt der Server nicht. Der weite Deckel greift
    nur dann — und lässt „Nicht beantwortet“ am Ende stehen."""
    text = ("## s1 — „Optik“ (1)\n1. **" + "T" * 60_000 + "**\n\n"
            "## Nicht beantwortet — KEIN Befund „keine Treffer“\ns2: nicht beantwortet (timeout)")
    antwort = suche_mehrfach.mit_umschlag({"results": {"s1": {"count": 1, "results": []}},
                                           "missing": [{"part": "s2", "code": "timeout"}]}, text)
    for sicht in (redigiere_strukturell(NAME, antwort),
                  _redact_search_content_for_llm(NAME, antwort, [], False)):
        assert len(sicht) < 33_000 and "[… gekürzt …]" in sicht
        assert sicht.startswith("## s1") and sicht.endswith("s2: nicht beantwortet (timeout)")


def test_die_antwort_traegt_keinen_fremdinhalt_rahmen():
    """Wie die Einzelsuche: Der Server hält jede Zeile einzeilig, die Antwort ist strukturiert.
    ``tests/test_untrusted_text.py`` sieht dieses Werkzeug nicht — es steht nicht im Katalog."""
    assert frame_untrusted(NAME, _ANTWORT) == frame_untrusted("search_wlo_content", _ANTWORT)


def test_eine_teilantwort_bleibt_nicht_im_cache(monkeypatch, mcp_state):  # noqa: F811
    """Was der Server nicht beantworten konnte (``missing``), ist kein Befund — beim nächsten
    Aufruf wird neu gefragt. Der Satz darüber reist im Text zur KI."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    teil = {"result": {"content": [_text_part(_NICHT_BEANTWORTET)], "structuredContent": {
        "results": {"a": {"count": 1, "results": []}},
        "missing": [{"part": "b", "code": "unresolved_filter"}]}}}
    calls = _wire_transport(monkeypatch, [teil, teil])
    args = {"queries": [{"id": "a", "query": "Optik"},
                        {"id": "b", "query": "Optik", "filters": {"discipline": "Quatschfach"}}]}
    for _ in range(2):
        text = asyncio.run(client.call_mcp_tool(NAME, dict(args)))
        assert "KEIN Befund „keine Treffer“" in redigiere_strukturell(NAME, text)
    assert len(calls) == 2


def test_eine_unvollstaendige_teilsuche_gilt_nur_fuer_sekunden():
    """Review N4 (m2): ``results[id].incomplete`` — eine Suchvariante antwortete nicht. Der Rat
    des Servers („ein erneuter Aufruf kann sie vervollständigen“) liefe sonst fünf Minuten gegen
    den Cache."""
    ganz = {"results": {"a": {"count": 1, "results": [_REFLEXION]}}, "missing": []}
    halb = {"results": {"a": {"count": 1, "results": [_REFLEXION]},
                        "b": {"count": 0, "results": [], "incomplete": True}}, "missing": []}
    assert NAME in mcp_unvollstaendig.WERKZEUGE
    assert not mcp_unvollstaendig.ist_unvollstaendig(NAME, ganz, "## a")
    assert mcp_unvollstaendig.ist_unvollstaendig(NAME, halb, "## a")
    # Aus dem Cache kommt nur der Text: dort trägt der Umschlag das Kennzeichen.
    assert mcp_unvollstaendig.ist_unvollstaendig(
        NAME, None, suche_mehrfach.mit_umschlag(halb, "## a\n## b"))
    assert not mcp_unvollstaendig.ist_unvollstaendig(
        NAME, None, suche_mehrfach.mit_umschlag(ganz, "## a"))


def test_die_antwort_wird_nicht_als_json_angefordert():
    """Den Text für das Modell schreibt der Server (seine Hinweise je Anfrage, „Nicht
    beantwortet“); der Client setzt für dieses Werkzeug kein ``outputFormat: json``."""
    assert NAME not in tool_args._JSON_CAPABLE_TOOLS
