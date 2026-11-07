"""Paket M1 (Plan 2026-11-07): der Chatbot liest den neuen MCP-Antwortvertrag.

- Fehler tragen ``structuredContent.error = {code, message, …}``; der Client reicht Code und
  Zusatzfelder an deterministische Aufrufer weiter (:func:`client.call_mcp_tool_antwort`).
- ``login_required`` / ``login_rejected`` gelten wie ein abgewiesener Zugang.
- Stapel-Ablage: die Gründe heißen ``batch_unknown/expired/mismatch``.
- ``search_wlo_within_collection`` kennt ``excludeNodeIds`` (keine Umrechnung mehr).
- Eine Lizenz, die wir nicht abbilden, geht unverändert an den Server — der antwortet ehrlich
  mit 0 Treffern und Vorschlägen; ``unresolvedFilters`` auch aus ``structuredContent``.
"""

from __future__ import annotations

import asyncio

from boerdi.domain.facets import unresolved_filter_note
from boerdi.services.ablage import mcp_ablage
from boerdi.services.mcp import arg_resolvers as ar
from boerdi.services.mcp import client
from boerdi.services.mcp.tool_args import validate_tool_args
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _result,
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)


def _fehler(code: str, text: str = "abgelehnt", **mehr):
    return {"error": {"message": text, "kind": "tool",
                      "structured": {"error": {"code": code, "message": text, **mehr}}}}


# ── 1. Fehlercode und Zusatzfelder ─────────────────────────────────────────────────────────

def test_der_code_und_die_zusatzfelder_kommen_beim_aufrufer_an(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_fehler("timeout", "zu langsam", outcomeOpen=False)])
    antwort = asyncio.run(client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"}))
    assert antwort.code == "timeout" and antwort.art == "tool"
    assert antwort.fehler == {"code": "timeout", "message": "zu langsam", "outcomeOpen": False}
    assert client.is_mcp_error(antwort.text) and "zu langsam" in antwort.text


def test_ein_erfolg_traegt_keinen_code_aber_den_strukturierten_teil(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {"content": [_text_part("ok")],
                                              "structuredContent": {"total": 1}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"}))
    assert antwort.code is None and antwort.fehler is None and antwort.art == ""
    assert antwort.strukturiert == {"total": 1} and antwort.text == "ok"


def test_status_bleibt_wie_bisher(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"message": "nein", "kind": "tool"}}])
    text, art = asyncio.run(client.call_mcp_tool_status("unknown_probe_tool", {"q": "x"}))
    assert (text, art) == ("MCP error: nein", "tool")      # ohne Code wie bisher


# ── 2. Anmeldung ──────────────────────────────────────────────────────────────────────────

def test_login_required_und_rejected_gelten_wie_ein_abgewiesener_zugang(mcp_state, monkeypatch):  # noqa: F811
    from boerdi.services.mcp import anmeldung, auth

    for code in ("login_required", "login_rejected"):
        _wire_tool_url(monkeypatch)
        calls = _wire_transport(monkeypatch, [_fehler(code, "Bitte anmelden"), _result([])])

        async def zug():
            auth.set_turn_auth_block("wlo2.block")
            antwort = await client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"})
            return antwort, auth.has_auth_token(), anmeldung.abgelehnt_in_diesem_zug()

        try:
            antwort, mit_block, abgelehnt = asyncio.run(zug())
        finally:
            anmeldung._cache.clear()
        assert antwort.art == "auth" and antwort.code == code, code
        assert len(calls) == 1 and not mit_block and abgelehnt, code


# ── 3. Stapel-Ablage ──────────────────────────────────────────────────────────────────────

def test_die_neuen_stapel_gruende_verlangen_ein_neues_vorbereiten():
    for alt, neu in (("unknown", "batch_unknown"), ("expired", "batch_expired"),
                     ("mismatch", "batch_mismatch")):
        assert mcp_ablage.grund({"status": "failed", "reason": neu}) == "neu_vorbereiten", neu
        # Rückfall: ein älterer Server meldet die alten Namen.
        assert mcp_ablage.grund({"status": "failed", "reason": alt}) == "neu_vorbereiten", alt


# ── 4. excludeNodeIds in der Sammlung ─────────────────────────────────────────────────────

def test_in_der_sammlung_geht_exclude_node_ids_durch():
    out = validate_tool_args("search_wlo_within_collection",
                             {"nodeId": "n", "excludeNodeIds": ["a", "b"]})
    assert out.get("excludeNodeIds") == ["a", "b"] and out.get("skipCount", 0) == 0


# ── 5. Lizenz und unresolvedFilters ───────────────────────────────────────────────────────

def test_eine_unbekannte_lizenz_geht_unveraendert_an_den_server(monkeypatch):
    from tests.test_lizenz_abgleich import _vokabular

    _vokabular(monkeypatch, [])
    out = asyncio.run(ar._resolve_filter_uris({"license": "frei", "q": 1}))
    assert out["license"] == "frei"


def test_unresolved_filters_aus_dem_strukturierten_teil(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part("{}")],
        "structuredContent": {"total": 0, "results": [], "unresolvedFilters": [
            {"field": "license", "value": "CC BY NC", "suggestions": ["CC BY-NC"]}]}}}])

    async def szenario():
        await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        return client.get_query_metas()

    metas = asyncio.run(szenario())
    assert metas and metas[0]["unresolvedFilters"][0]["value"] == "CC BY NC"


def test_der_hinweis_zur_lizenz_sagt_die_wahrheit_und_nennt_vorschlaege():
    """Eine unbekannte Lizenz leert die Antwort — „allgemeiner gesucht“ wäre falsch."""
    note = unresolved_filter_note([{"unresolvedFilters": [
        {"field": "license", "value": "CC BY NC", "suggestions": ["CC BY-NC", "CC BY"]}]}])
    assert "allgemeiner" not in note and "CC BY-NC" in note and "CC BY NC" in note
    andere = unresolved_filter_note([{"unresolvedFilters": [
        {"field": "discipline", "value": "Zauberei"}]}])
    assert "allgemeiner" in andere


# ── Review M1 ─────────────────────────────────────────────────────────────────────────────

def test_der_strukturierte_meta_kommt_aus_einer_eigenen_aufgabe(mcp_state, monkeypatch):  # noqa: F811
    """Review M1, Befund 1: Knoten und Vorabruf laufen in kopierten Kontexten — nur ein Anhängen
    an die gebundene Liste erreicht ``persist``."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part("{}")],
        "structuredContent": {"total": 0, "results": [], "unresolvedFilters": [
            {"field": "license", "value": "CC BY NC"}]}}}])

    async def szenario():
        client.reset_query_metas()
        await asyncio.create_task(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
        return client.get_query_metas()

    assert asyncio.run(szenario())


def test_kein_doppelter_meta_eintrag_neben_dem_textblock(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part("{}"),
                    _text_part('{"_queryMeta": {"toolName": "t", "unresolvedFilters": []}}')],
        "structuredContent": {"unresolvedFilters": [{"field": "license", "value": "X"}]}}}])

    async def szenario():
        await client.call_mcp_tool("unknown_probe_tool", {"q": "x"})
        return client.get_query_metas()

    assert len(asyncio.run(szenario())) == 1


def test_login_required_ohne_persoenlichen_block_wirft_nichts_weg(mcp_state, monkeypatch):  # noqa: F811
    """Review M1, Befund 3: anonymer Block oder Block der Anlage — kein „Anmeldung gilt nicht
    mehr“ für jemanden, der nie angemeldet war, kein Alarm über den Block der Anlage."""
    from boerdi.services.mcp import anmeldung, auth

    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_fehler("login_required", "Bitte anmelden")])

    async def zug():
        auth.set_turn_auth_block("wlo-anon.x")
        antwort = await client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"})
        return antwort, auth.hat_zug_block(), anmeldung.abgelehnt_in_diesem_zug()

    try:
        antwort, mit_block, abgelehnt = asyncio.run(zug())
    finally:
        anmeldung._cache.clear()
    assert antwort.art == "tool" and antwort.code == "login_required"
    assert mit_block and not abgelehnt


def test_ein_offener_ausgang_ist_kein_abgelehnt(mcp_state, monkeypatch):  # noqa: F811
    """Review M1, Befund 4: ``timeout`` mit offenem Ausgang, ``not_visible`` und ``unverified``
    heißen „kann geschrieben sein“ — nie „abgelehnt, nichts geändert“."""
    for antwort_server, art in (
            (_fehler("timeout", "zu langsam", outcomeOpen=True), "timeout"),
            (_fehler("timeout", "zu langsam"), "timeout"),
            (_fehler("not_visible", "nicht sichtbar"), "timeout"),
            (_fehler("unverified", "nicht prüfbar"), "timeout"),
            (_fehler("timeout", "zu langsam", outcomeOpen=False), "tool")):
        _wire_tool_url(monkeypatch)
        _wire_transport(monkeypatch, [antwort_server])
        antwort = asyncio.run(client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"}))
        assert antwort.art == art, antwort_server


def test_das_modell_sieht_den_code(mcp_state, monkeypatch):  # noqa: F811
    """Plan M1.1: der Code steht im Text, den das Modell liest (der Präfix bleibt)."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_fehler("not_found", "Nicht gefunden.")])
    text = asyncio.run(client.call_mcp_tool("unknown_probe_tool", {"q": "x"}))
    assert text == "MCP error [not_found]: Nicht gefunden." and client.is_mcp_error(text)


def test_ein_sammelwert_geht_als_oer_an_den_server(monkeypatch):
    """Review M1, Befund 6: der Server kennt nur seine eigenen Schreibweisen der Sammelwerte."""
    from boerdi.services.mcp.lizenz_abgleich import lizenz_filter

    for wert in ("OER Lizenz", "Freie-Lizenzen", "oer  lizenzen", "OER"):
        assert lizenz_filter({"CC BY": "CC_BY"}, wert) == "OER", wert


def test_eine_unaufgeloeste_lizenz_haengt_nicht_an_der_sitzung():
    """Review M1, Befund 7: sonst leerte die gemerkte Lizenz jede Folgesuche."""
    from boerdi.domain.facets import lizenz_unaufgeloest

    assert lizenz_unaufgeloest([{"unresolvedFilters": [{"field": "license", "value": "x"}]}])
    assert not lizenz_unaufgeloest([{"unresolvedFilters": [{"field": "discipline", "value": "x"}]}])
    assert not lizenz_unaufgeloest(None)
