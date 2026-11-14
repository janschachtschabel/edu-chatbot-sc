"""SW-3 (Plan 2026-11-14, Werkzeuge für Sammlungsstrukturen): sieben Kuratier-Werkzeuge zum Pflegen
von Sammlungen — Stapel-Einreichen, Stapel-Herausnehmen, leere Sammlungen löschen, Umhängen,
Reihenfolge setzen, Vorschläge lesen und entscheiden — und das Umsortieren an
``wlo_add_to_collections``.

Der MCP-Server kennt sie ab dem Stand „Sammlungsstrukturen“ (14.11.2026); der bereitgestellte
nicht. Sie stehen im Katalog (Bestätigung, Pläne, Argumentmodelle greifen von selbst), angeboten
werden sie nur, wenn die Werkzeugliste des Servers sie führt.

Die Schemata stammen aus ``tools/list`` dieses Stands (lokal gestartet, 14.11.2026).
"""
from __future__ import annotations

import asyncio
import pathlib
import time

import pytest
import yaml

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain import host_capabilities as hc
from boerdi.domain.write_confirm import (
    CONFIRMABLE_TOOLS,
    CURATION_TOOLS,
    NUR_LESEND,
    PLAN_TOOLS,
    is_confirmable,
    is_plan,
    remember_pending,
)
from boerdi.i18n.bot_text import bot_text
from boerdi.obs.log_inhalt import filterwerte
from boerdi.services import agent_tool_overview, agent_tools, response_tool_selection
from boerdi.services import write_approval as wa_mod
from boerdi.services.ablauf import freigabe_ergebnis
from boerdi.services.ablauf import werkzeuge as ablauf_werkzeuge
from boerdi.services.mcp import (
    angebot,
    faehigkeiten,
    sammlungspflege,
    tool_args,
    tool_cache,
    tool_descriptions,
)
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.mcp.tool_defs_curation import CURATION_ARG_MODELS, CURATION_TOOL_DEFINITIONS
from boerdi.services.write_approval import abgelehnt_text, redeem_write_approval
from tests.test_mcp_client import (  # noqa: F401 — ``mcp_state`` ist eine Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)
from tests.test_write_approval import _SESSION, _Spy

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds"
_NEU = sammlungspflege.WERKZEUGE
_PLAENE = {"wlo_submit_contents", "wlo_remove_from_collections", "wlo_delete_collections"}
_STAPEL = "wlo_add_to_collections"


def _server(*namen: str) -> None:
    """Der bereitgestellte Server führt genau diese der neuen Werkzeuge."""
    assert faehigkeiten.uebernehmen([
        {"name": "search_wlo_content", "input_schema": {"properties": {"query": {}}}},
        *({"name": n, "input_schema": {"properties": {sammlungspflege._MARKEN[n]: {}}}}
          for n in namen)])


def _agent(monkeypatch) -> dict[str, dict]:
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    return {t["function"]["name"]: t for t in agent_tools._mcp_werkzeuge(
        allow_curation=True, blocked_tools=None, tool_mode=None)}


def _muster(monkeypatch) -> dict[str, dict]:
    monkeypatch.setattr(response_tool_selection, "schreiben_erlaubt", lambda: True)
    return {t["function"]["name"]: t for t in response_tool_selection._nameable_tools()}


# ── Der Katalog ────────────────────────────────────────

def test_die_sieben_stehen_im_katalog_mit_modell_und_bestaetigung():
    katalog = {t["function"]["name"] for t in CURATION_TOOL_DEFINITIONS}
    assert len(_NEU) == 7 and _NEU <= katalog and _NEU <= CURATION_TOOLS
    assert _NEU <= set(CURATION_ARG_MODELS)
    # Eines liest nur; die übrigen sechs führen einen Bestätigungsschlüssel.
    assert _NEU & NUR_LESEND == {"wlo_list_collection_proposals"}
    assert _NEU - NUR_LESEND <= CONFIRMABLE_TOOLS
    assert not is_confirmable("wlo_list_collection_proposals")
    # Drei laufen als Plan (eine Bestätigung, „Plan fortsetzen“), die übrigen einfach zweistufig.
    assert _NEU & PLAN_TOOLS == _PLAENE
    assert all(is_plan(n) for n in _PLAENE) and not is_plan("wlo_move_collection")
    # Ein Schreibvorgang kommt nie aus dem Cache — auch nicht die Liste der Vorschläge.
    assert all(tool_cache.cache_gesperrt(n, {}) for n in _NEU)


def test_im_lesemodus_bleibt_nur_die_liste_der_vorschlaege():
    assert hc.erlaubt("wlo_list_collection_proposals", hc.LESEND)
    for name in _NEU - {"wlo_list_collection_proposals"}:
        assert not hc.erlaubt(name, hc.LESEND), name
        assert hc.erlaubt(name, hc.KURATIEREND), name


def test_loeschen_geht_nicht_aus_einem_ablauf():
    """Entscheid SE-3: wie jedes Löschen. Die anderen bestätigbaren sind in einem Schritt mit
    Freigabe erlaubt."""
    assert not ablauf_werkzeuge.freigebbar("wlo_delete_collections")
    for name in ("wlo_submit_contents", "wlo_remove_from_collections", "wlo_move_collection",
                 "wlo_order_collection", "wlo_decide_collection_proposal"):
        assert ablauf_werkzeuge.freigebbar(name), name
    assert not ablauf_werkzeuge.freigebbar("wlo_list_collection_proposals")


def test_plaene_verlangen_keinen_zweiten_aufruf_und_einfache_schon():
    """Die Beschreibung muss zur Einlösung passen: Einen Plan löst der Chat selbst ein."""
    je = {t["function"]["name"]: t["function"]["description"] for t in CURATION_TOOL_DEFINITIONS}
    for name in _PLAENE:
        assert "NICHT erneut auf" in je[name] and "Plan fortsetzen" in je[name], name
    for name in ("wlo_move_collection", "wlo_order_collection", "wlo_decide_collection_proposal"):
        assert "erneut auf" in je[name] and "NICHT erneut auf" not in je[name], name
    assert "Vorschau-Schritt" in je["wlo_list_collection_proposals"]


def test_registry_und_m18_nennen_die_werkzeuge():
    roh = yaml.safe_load((_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8"))
    [wlo] = [s for s in roh["servers"] if s["id"] == "wlo-mcp"]
    assert _NEU <= set(wlo["tools"])
    m18 = (_SEEDS / "03-patterns" / "m18-kuration.md").read_text(encoding="utf-8")
    kopf = yaml.safe_load(m18.split("---")[1])
    assert _NEU <= set(kopf["tools"])


# ── Das Angebot ────────────────────────────────────────

def test_angeboten_wird_nur_was_der_server_fuehrt(monkeypatch):
    """Im Katalog stehen sie immer; ein Aufruf an einen Server ohne sie endete im Fehler."""
    assert not _NEU & set(_agent(monkeypatch)) and not _NEU & set(_muster(monkeypatch))
    # Die übrigen Kuratier-Werkzeuge sind davon unberührt.
    assert CURATION_TOOLS - _NEU <= set(_agent(monkeypatch))

    _server("wlo_submit_contents", "wlo_order_collection")          # ein Teil
    assert _NEU & set(_agent(monkeypatch)) == {"wlo_submit_contents", "wlo_order_collection"}
    assert _NEU & set(_muster(monkeypatch)) == {"wlo_submit_contents", "wlo_order_collection"}

    _server(*_NEU)
    assert _NEU <= set(_agent(monkeypatch)) and _NEU <= set(_muster(monkeypatch))
    # Ohne Anmeldung keins, wie jedes Kuratier-Werkzeug.
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    ohne = {t["function"]["name"] for t in agent_tools._mcp_werkzeuge(
        allow_curation=True, blocked_tools=None, tool_mode=None)}
    assert not _NEU & ohne
    # Ein Rückbau des Servers nimmt sie wieder weg.
    _server()
    assert not _NEU & set(_agent(monkeypatch))


def test_das_studio_nennt_den_grund_und_warnt_nicht(monkeypatch):
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    monkeypatch.setattr(agent_tool_overview, "schreiben_erlaubt", lambda: True)

    def _zeilen() -> dict[str, dict]:
        return {t["name"]: t for t in agent_tool_overview.werkzeugliste()["tools"]}

    ohne = _zeilen()
    for name in _NEU:
        assert ohne[name]["kind"] == "curation" and ohne[name]["offered"] is False
        assert {"code": "server_lacks"} in ohne[name]["locks"], name
    assert {"code": "server_lacks"} not in ohne["wlo_create_content"]["locks"]
    _server(*_NEU)
    mit = _zeilen()
    for name in _NEU:
        assert mit[name]["offered"] is True, name
        assert {"code": "server_lacks"} not in mit[name]["locks"]

    # Seite „MCP-Server“: Schalter ja, die Warnung „fehlt am Server“ nein.
    primaer = {"id": "wlo-mcp", "enabled": True, "url": "https://mcp.example",
               "tools": [*sorted(_NEU), "search_skill", "get_url_text"]}

    async def _live(_url):
        return {"get_url_text": "holt Text"}

    monkeypatch.setattr(tool_descriptions.config_loader, "load_mcp_servers", lambda: [primaer])
    monkeypatch.setattr(tool_descriptions, "_fetch_tool_descriptions", _live)
    (server,) = asyncio.run(tool_descriptions.load_mcp_servers_with_descriptions())
    assert server["werkzeuge_fehlen_am_server"] == ["search_skill"]
    assert _NEU <= set(server["werkzeuge_im_katalog"])


# ── Was an den Server geht ─────────────────────────────────

def test_die_argumente_in_der_form_des_servers():
    pruefe = tool_args.validate_tool_args
    # Einreichen: bloße Kennungen sind gemeint, wie sie dastehen; fremde Felder fallen weg.
    assert pruefe("wlo_submit_contents", {
        "items": ["m-1", {"nodeId": "m-2", "titel": "x"}], "comment": "bitte prüfen",
        "continuationToken": "plan-1", "erfunden": 1}) == {
        "items": [{"nodeId": "m-1"}, {"nodeId": "m-2"}], "comment": "bitte prüfen",
        "continuationToken": "plan-1"}
    assert pruefe("wlo_remove_from_collections", {"pairs": [
        {"nodeId": "m-1", "collectionId": "c-1", "removeFrom": "c-9", "x": 1}]}) == {
        "pairs": [{"nodeId": "m-1", "collectionId": "c-1"}]}
    assert pruefe("wlo_delete_collections", {"nodeIds": ["c-1", "c-2"], "recycle": True}) == {
        "nodeIds": ["c-1", "c-2"]}
    assert pruefe("wlo_move_collection", {"nodeId": "c-1", "newParentId": "c-2", "x": 1}) == {
        "nodeId": "c-1", "newParentId": "c-2"}
    assert pruefe("wlo_order_collection", {"collectionId": "c-1", "order": ["a", "b"]}) == {
        "collectionId": "c-1", "order": ["a", "b"]}
    assert pruefe("wlo_list_collection_proposals", {"collectionId": "c-1"}) == {
        "collectionId": "c-1"}
    assert pruefe("wlo_list_collection_proposals", {"collectionId": "c-1", "status": "DECLINED"})[
        "status"] == "DECLINED"
    assert pruefe("wlo_decide_collection_proposal", {
        "collectionId": "c-1", "nodeId": "m-1", "decision": "decline"})["decision"] == "decline"
    # Der Bestätigungsschlüssel reist durch, auch wenn er in keinem Modell steht.
    assert pruefe("wlo_move_collection", {"nodeId": "c-1", "newParentId": "c-2",
                                          "confirmToken": "t-1"})["confirmToken"] == "t-1"


@pytest.mark.parametrize("werkzeug, kaputt", [
    ("wlo_decide_collection_proposal", {"collectionId": "c", "nodeId": "m", "decision": "ja"}),
    ("wlo_order_collection", {"collectionId": "c", "order": "a,b"}),
    ("wlo_delete_collections", {"nodeIds": "c-1"}),
])
def test_was_nicht_passt_geht_roh_zum_server_statt_still_umgedeutet(werkzeug, kaputt):
    assert tool_args.validate_tool_args(werkzeug, dict(kaputt)) == kaputt


# ── Umsortieren und Vorschlagen an den Einsortier-Werkzeugen ──────────────────

def _definition(name: str) -> dict:
    return next(t for t in CURATION_TOOL_DEFINITIONS if t["function"]["name"] == name)


def test_umsortieren_und_vorschlagen_kennt_nur_der_neue_stand():
    stapel, einzeln = _definition(_STAPEL), _definition("wlo_add_to_collection")
    _server()
    assert angebot.nach_faehigkeit(stapel) is stapel
    assert angebot.nach_faehigkeit(einzeln) is einzeln

    _server("wlo_remove_from_collections")          # der Stand, der beides kennt
    neu = angebot.nach_faehigkeit(stapel)["function"]
    paar = neu["parameters"]["properties"]["pairs"]["items"]
    assert "removeFrom" in paar["properties"] and paar["required"] == ["nodeId", "collectionId"]
    assert "VORGESCHLAGEN" in neu["description"] and "NICHT aufgenommen" in neu["description"]
    assert "removeFrom" in neu["description"] and "moved" in neu["description"]
    einzel = angebot.nach_faehigkeit(einzeln)["function"]
    assert "VORGESCHLAGEN" in einzel["description"] and "removeFrom" not in einzel["description"]
    # Der Katalog selbst bleibt, wie er ist; ein Muster bekommt dieselbe Erweiterung.
    assert "removeFrom" not in stapel["function"]["parameters"]["properties"]["pairs"]["items"][
        "properties"]
    assert angebot.fuer_muster(stapel)["function"] == neu


def test_removefrom_bleibt_im_modell_und_ein_leeres_faellt_weg():
    aus = tool_args.validate_tool_args(_STAPEL, {"pairs": [
        {"nodeId": "m-1", "collectionId": "c-2", "removeFrom": "c-1", "x": "y"},
        {"nodeId": "m-2", "collectionId": "c-2", "removeFrom": ""}]})
    assert aus["pairs"] == [{"nodeId": "m-1", "collectionId": "c-2", "removeFrom": "c-1"},
                            {"nodeId": "m-2", "collectionId": "c-2"}]


def test_umsortieren_an_einem_aelteren_server_wird_abgelehnt(monkeypatch, mcp_state):  # noqa: F811
    """Er nähme auf und ließe das Material still in der Quelle liegen — die KI meldete
    „umsortiert“. Der Client sagt es, statt zu senden."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [{"result": {"content": [_text_part("Vorschau")]}}] * 2)
    paare = {"pairs": [{"nodeId": "m-1", "collectionId": "c-2", "removeFrom": "c-1"}]}

    _server()
    antwort = asyncio.run(client.call_mcp_tool_antwort(_STAPEL, dict(paare)))
    assert calls == [] and antwort.code == "invalid_input"
    assert "removeFrom" in antwort.text and "Nichts wurde geaendert" in antwort.text
    # Ohne ``removeFrom`` geht derselbe Aufruf an jeden Stand.
    ohne = {"pairs": [{"nodeId": "m-1", "collectionId": "c-2"}]}
    assert asyncio.run(client.call_mcp_tool(_STAPEL, dict(ohne))) == "Vorschau"

    _server("wlo_remove_from_collections")
    assert asyncio.run(client.call_mcp_tool(_STAPEL, dict(paare))) == "Vorschau"
    assert calls[1]["arguments"] == paare


# ── Review SW-3 ──────────────────────────────────────────────────────────────

def test_umsortieren_an_der_falschen_stelle_wird_abgelehnt_statt_still_verworfen(
        monkeypatch, mcp_state):  # noqa: F811
    """Befund 5: ``removeFrom`` am einzelnen Werkzeug oder auf oberster Ebene fiel still weg —
    hinaus ging nur die Aufnahme, die KI meldete „umsortiert“. Der Client lehnt ab, an jedem
    Stand des Servers; zum Server geht das Feld nie."""
    from boerdi.services.mcp import client

    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [{"result": {"content": [_text_part("Vorschau")]}}])
    _server(*_NEU)
    for werkzeug, args in (
            ("wlo_add_to_collection",
             {"collectionId": "c-2", "nodeId": "m-1", "removeFrom": "c-1"}),
            (_STAPEL, {"removeFrom": "c-1", "pairs": [{"nodeId": "m-1", "collectionId": "c-2"}]})):
        antwort = asyncio.run(client.call_mcp_tool_antwort(werkzeug, dict(args)))
        assert antwort.code == "invalid_input" and "an jedes Paar" in antwort.text, werkzeug
    assert calls == []
    # Auch mit einem Schlüssel geht ein falsch gesetztes ``removeFrom`` nie hinaus.
    assert angebot.lokale_ablehnung("wlo_add_to_collection", {
        "collectionId": "c-2", "nodeId": "m-1", "removeFrom": "c-1", "confirmToken": "t"})
    # Das Herausnehmen kennt das Feld gar nicht (eigenes Modell).
    assert tool_args.validate_tool_args("wlo_remove_from_collection", {
        "collectionId": "c-1", "nodeId": "m-1", "removeFrom": "c-9"}) == {
        "collectionId": "c-1", "nodeId": "m-1"}


@pytest.mark.parametrize("schluessel", ["confirmToken", "continuationToken"])
def test_ein_bestaetigter_plan_wird_nie_lokal_abgelehnt(schluessel):
    """Befund 2: Nach einem Neustart oder drei gescheiterten Abfragen ist der Stand des Servers
    unbekannt. Ein Klick auf „Plan fortsetzen“ in diesem Fenster wurde lokal abgelehnt, der Plan
    verworfen — obwohl der Server ihn selbst ausgestellt hat und er dort schon lief."""
    faehigkeiten.vergessen()
    paare = [{"nodeId": "m-1", "collectionId": "c-2", "removeFrom": "c-1"}]
    assert angebot.lokale_ablehnung(_STAPEL, {"pairs": paare, schluessel: "s-1"}) is None
    # Eine NEUE Vorschau bleibt bei unbekanntem Stand abgelehnt: unbekannt heißt nein.
    assert angebot.lokale_ablehnung(_STAPEL, {"pairs": paare})


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", ["de", "en"])
async def test_angenommen_aber_nicht_markiert_sagt_was_geschehen_ist(monkeypatch, lang):
    """Befund 1 (schwer): Der Server meldet ``proposal_not_marked`` mit ``recordExists`` — die
    Person las „Der Datensatz ist angelegt …, lege ihn nicht noch einmal an“. Angelegt wurde
    nichts: Das Material liegt jetzt in der Sammlung, die Markierung des Vorschlags ist offen."""
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    monkeypatch.setattr(wa_mod, "save_message", _Spy())
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)
    monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "person-a")
    fehler = McpAntwort(
        "MCP error [proposal_not_marked]: aufgenommen, Markierung offen.", "tool",
        "proposal_not_marked",
        {"code": "proposal_not_marked", "message": "aufgenommen, Markierung offen.",
         "outcomeOpen": True, "recordExists": True, "nodeId": "m-3333-4444",
         "mark": "unverified"})

    async def _rufe(_tool, _args, **_k):
        return fehler

    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _rufe)
    zustand = {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        "wlo_decide_collection_proposal",
        {"collectionId": "c-1", "nodeId": "m-3333-4444", "decision": "accept"},
        "Schluessel-0123456789abcd", now=time.time(), caller="person-a")}}
    req = ChatRequest(session_id="bb-1", message="Ja, so ausführen",
                      environment=Environment(locale=lang))
    antwort = await redeem_write_approval(_SESSION, req, zustand)
    assert antwort.content == bot_text(lang, "write.proposalNotMarked")
    assert antwort.content != bot_text(lang, "write.recordExists", kennung="m-3333-4444")
    assert "_pending_write" not in zustand["entities"] and not antwort.quick_replies
    assert antwort.debug.entities["reason"] == "mcp_error"


@pytest.mark.parametrize(("code", "schluessel"), [
    ("is_original", "write.grund.isOriginal"),
    ("source_is_original", "write.grund.isOriginal"),
    ("already_proposed", "write.grund.alreadyProposed"),
    ("no_pending_proposal", "write.grund.noPendingProposal"),
    ("no_change", "write.grund.noChange"),
])
@pytest.mark.parametrize("lang", ["de", "en"])
def test_die_neuen_ablehnungen_nennen_ihren_grund(code, schluessel, lang):
    """Befund 3: ``is_original`` kommt beim einzelnen Herausnehmen erst NACH dem Ja — ohne Satz
    las die Person nur „WLO hat die Änderung abgelehnt“. Eigene Sätze, in beiden Sprachen, ohne
    den Text des Servers (er nennt Werkzeuge)."""
    antwort = McpAntwort(f"MCP error [{code}]: nimm wlo_delete_content", "tool", code,
                         {"code": code, "message": "nimm wlo_delete_content"})
    text = abgelehnt_text(lang, antwort)
    assert text.startswith(bot_text(lang, "write.executeRejected"))
    assert bot_text(lang, schluessel) in text and "wlo_" not in text


def test_im_ablauf_ist_nicht_eingereicht_kein_erfolg():
    """Befund 4: Mit lauter ``not_stored`` lief der Lauf weiter, als sei eingereicht."""
    def _alle(status: str, feld: str = "items") -> bool:
        return freigabe_ergebnis.alle_gescheitert({feld: [{"nodeId": "m", "status": status}] * 2})

    assert _alle("failed") and _alle("not_stored")
    assert freigabe_ergebnis.alle_gescheitert(
        {"items": [{"status": "failed"}, {"status": "not_stored"}]})
    # Vorgeschlagen ist bewusst kein Scheitern: Die Vorschau hat es gesagt.
    assert not _alle("proposed", "pairs") and not _alle("submitted") and not _alle("already")
    assert not freigabe_ergebnis.alle_gescheitert(
        {"items": [{"status": "not_stored"}, {"status": "submitted"}]})


def test_die_reihenfolge_steht_nicht_mit_wert_im_log():
    """Befund 9: Nennt die KI in ``order`` Titel statt Kennungen, stünden sie im Log."""
    log = filterwerte({"collectionId": "c-1", "newParentId": "c-2",
                       "order": ["Optik – Klasse 7b (Entwurf Müller)", "Mechanik"]})
    assert log["collectionId"] == "c-1" and log["newParentId"] == "c-2"
    assert "Müller" not in str(log) and "Mechanik" not in str(log)


def test_leer_heisst_was_die_anmeldung_sehen_kann():
    """Befund 6: die Einschränkung des Servers gehört in die Beschreibung."""
    text = _definition("wlo_delete_collections")["function"]["description"]
    assert "NUR leere" in text and "DEINE Anmeldung sehen kann" in text
