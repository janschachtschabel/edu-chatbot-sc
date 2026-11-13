"""MCP-Stand nach der Audit-Nacharbeit (Plan ``docs/plans/2026-11-13-mcp-nach-audit.md``).

Der MCP-Server meldet seit dem Audit neue Ablehnungen und gibt nach einem Folgefehler beim
Anlegen die id des Datensatzes zurück. Der Chatbot lief damit weiter, sagte der Person aber nur
„abgelehnt“ ohne Grund bzw. „ob es angekommen ist, kann ich nicht sagen“.

- C2: neue Codes mit eigenem Satz, ``recordExists`` mit Kennung, Codes der Stapel-Ablage.
- C4: eine abgelehnte ``get_skill``-Antwort ist keine Anleitung — in beiden Schleifen.

C3 (die Trace-ID als ``X-Request-Id``) ist nach dem Review entfallen: der MCP liest
``x-client-trace-id`` und B3 inzwischen selbst, eine gemeinsame ``X-Request-Id`` nähme ihm die
Kennung je Anfrage.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.write_confirm import remember_pending
from boerdi.i18n.bot_text import bot_text
from boerdi.services import master_skill
from boerdi.services import write_approval as wa_mod
from boerdi.services.ablage import mcp_ablage
from boerdi.services.mcp import client
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.write_approval import abgelehnt_text, redeem_write_approval
from tests.test_ablage_mcp import mcp  # noqa: F401 — Fixture
from tests.test_agent_loop import _lauf, _OutcomeFake, _resp_text, _resp_tools, _tool_call
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)
from tests.test_write_approval import _SESSION, _Spy

_SCHLUESSEL = "Schluessel-0123456789abcd"


# ── C2: neue Ablehnungen mit eigenem Satz ──────────────────────────────────────────────────────

@pytest.mark.parametrize(("code", "schluessel"), [
    ("already_decided", "write.grund.alreadyDecided"),
    ("already_submitted", "write.grund.alreadySubmitted"),
    ("is_a_folder", "write.grund.isAFolder"),
    ("is_a_collection", "write.grund.isACollection"),
    ("not_a_record", "write.grund.notARecord"),
])
@pytest.mark.parametrize("lang", ["de", "en"])
def test_neue_ablehnungen_nennen_ihren_grund_mit_eigenem_satz(code, schluessel, lang):
    """Vorher: „WLO hat die Änderung abgelehnt“ ohne ein Wort, warum. Der Text des Servers taugt
    nicht: er ist an die KI gerichtet und nennt Werkzeuge und Status-Kennungen (Review C2)."""
    antwort = McpAntwort(f"MCP error [{code}]: ist wlo_update_content das Werkzeug", "tool", code,
                         {"code": code, "message": "ist wlo_update_content das Werkzeug "
                                                   "(Status 200_tocheck)"})
    text = abgelehnt_text(lang, antwort)
    assert text.startswith(bot_text(lang, "write.executeRejected"))
    assert bot_text(lang, schluessel) in text
    assert "wlo_" not in text and "200_tocheck" not in text


@pytest.mark.parametrize("code", ["upstream_error", "suggestion_not_marked", "ganz_neu"])
def test_andere_codes_zeigen_weiter_keinen_servertext(code):
    """``upstream_error`` trägt Text des Repositoriums; ``suggestion_not_marked`` kommt nur nach
    der Einlösung (neu vorgelegt oder „bitte nachsehen“) und braucht hier keinen Satz."""
    antwort = McpAntwort(f"MCP error [{code}]: Interna", "tool", code,
                         {"code": code, "message": "Interna"})
    assert abgelehnt_text("de", antwort) == bot_text("de", "write.executeRejected")


@pytest.fixture
def _rand(monkeypatch):
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    monkeypatch.setattr(wa_mod, "save_message", _Spy())
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)
    monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "person-a")


def _req(lang: str = "de") -> ChatRequest:
    return ChatRequest(session_id="bb-1", message="Ja, so ausführen",
                       environment=Environment(locale=lang))


def _zustand() -> dict:
    return {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        "wlo_create_content", {"title": "T"}, _SCHLUESSEL, now=time.time(), caller="person-a")}}


def _mcp(antwort: McpAntwort):
    async def rufe(_tool, _args, **_k):
        return antwort

    return rufe


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", ["de", "en"])
async def test_angelegt_aber_unvollstaendig_nennt_den_datensatz(_rand, monkeypatch, lang):
    """Der Datensatz existiert, ein Schritt danach bekam keine Antwort (``recordExists``). Vorher:
    „ob sie angekommen ist, kann ich nicht sagen … sonst steht sie zweimal da“ — und die id las
    niemand. Jetzt: angelegt, mit Kennung, nachtragen statt neu anlegen."""
    fehler = McpAntwort(
        "MCP error [unverified]: angelegt — die Datei fehlt. NICHT erneut anlegen.", "timeout",
        "unverified", {"code": "unverified", "message": "angelegt — die Datei fehlt.",
                       "outcomeOpen": True, "recordExists": True, "nodeId": "ab12-cd34",
                       "requiresNewPreview": False})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _mcp(fehler))
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(lang), zustand)
    assert antwort.content == bot_text(lang, "write.recordExists", kennung="ab12-cd34")
    assert "ab12-cd34" in antwort.content
    # wie jeder offene Ausgang: nichts neu vorgelegt, die Abnahme ist verbraucht
    assert "_pending_write" not in zustand["entities"] and not antwort.quick_replies
    assert antwort.debug.entities["reason"] == "mcp_error"


def test_die_kennung_neben_dem_fehler_kommt_beim_aufrufer_an(mcp_state, monkeypatch):  # noqa: F811
    """Review C2 (schwer): in zwei von drei Fällen (``markWritten`` des Servers: Felder verworfen,
    Rücklesen gescheitert) steht die Kennung NEBEN ``error`` im strukturierten Teil. Der Client
    reichte nur ``error`` weiter — der Satz hätte keine Kennung gehabt."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {
        "kind": "tool", "message": "Felder nicht gespeichert",
        "structured": {"error": {"code": "not_stored", "message": "Felder nicht gespeichert",
                                 "outcomeOpen": True, "recordExists": True},
                       "nodeId": "ef56-ab78", "title": "Optik"}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort(
        "wlo_create_content", {"title": "Optik"}, use_cache=False))
    assert antwort.art == "timeout"                     # offener Ausgang, nie „nichts geändert“
    assert antwort.fehler["recordExists"] is True and antwort.fehler["nodeId"] == "ef56-ab78"


def test_eine_kennung_im_fehler_selbst_bleibt_die_des_servers(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"kind": "tool", "message": "x", "structured": {
        "error": {"code": "unverified", "outcomeOpen": True, "recordExists": True,
                  "nodeId": "aus-dem-fehler"}, "nodeId": "daneben-1234"}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort(
        "wlo_create_content", {"title": "T"}, use_cache=False))
    assert antwort.fehler["nodeId"] == "aus-dem-fehler"


def test_ohne_record_exists_wird_keine_kennung_uebernommen(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"kind": "tool", "message": "x", "structured": {
        "error": {"code": "refused", "message": "x"}, "nodeId": "daneben-1234"}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort(
        "wlo_create_content", {"title": "T"}, use_cache=False))
    assert "nodeId" not in antwort.fehler


@pytest.mark.asyncio
async def test_angelegt_ganz_ohne_kennung_sagt_es_trotzdem(_rand, monkeypatch):
    fehler = McpAntwort("MCP error [not_stored]: Felder fehlen", "timeout", "not_stored",
                        {"code": "not_stored", "outcomeOpen": True, "recordExists": True})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _mcp(fehler))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.recordExistsOhneKennung")


@pytest.mark.asyncio
async def test_eine_kennung_mit_fremden_zeichen_kommt_nicht_in_den_text(_rand, monkeypatch):
    fehler = McpAntwort("MCP error [unverified]: x", "timeout", "unverified", {
        "code": "unverified", "outcomeOpen": True, "recordExists": True,
        "nodeId": "ab12](https://boese.example) [klick"})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _mcp(fehler))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.recordExistsOhneKennung")


@pytest.mark.asyncio
async def test_ein_offener_ausgang_ohne_datensatz_bleibt_bitte_nachsehen(_rand, monkeypatch):
    fehler = McpAntwort("MCP error [unverified]: unklar", "timeout", "unverified",
                        {"code": "unverified", "outcomeOpen": True})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _mcp(fehler))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.executeUnconfirmed")


# ── C2: Stapel-Ablage ──────────────────────────────────────────────────────────────────────────

_EINTRAG = [{"titel": "a", "sha256": "a" * 64, "groesse": 1, "art": "pdf"}]


def _vorbereiten_code(mcp, antwort) -> str:  # noqa: F811
    mcp["antworten"]["wlo_prepare_file_batch"] = antwort
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.vorbereiten("X", _EINTRAG))
    return fehler.value.code


def test_zu_viele_stapel_ist_voll_und_nicht_abgewiesen(mcp):  # noqa: F811
    """``too_many_batches`` kommt als ``status: failed`` ohne ``batchToken``. Vorher: 422
    „abgewiesen“ (nicht wiederholbar), obwohl es in ein paar Minuten wieder geht."""
    assert _vorbereiten_code(mcp, {"error": {
        "message": "zu viele", "kind": "tool",
        "structured": {"status": "failed", "reason": "too_many_batches"}}}) == "voll"


def test_ein_anderer_grund_beim_vorbereiten_bleibt_abgewiesen(mcp):  # noqa: F811
    assert _vorbereiten_code(mcp, {"error": {
        "message": "x", "kind": "tool",
        "structured": {"status": "failed", "reason": "seltsam"}}}) == "abgewiesen"


def test_ein_ausgelastetes_repositorium_ist_voll(mcp):  # noqa: F811
    """``WLO_UPSTREAM_CONCURRENCY`` des MCP: ``upstream_busy`` war in der Ablage unbekannt."""
    assert _vorbereiten_code(mcp, {"error": {
        "message": "x", "kind": "tool",
        "structured": {"error": {"code": "upstream_busy", "retryAfter": 5}}}}) == "voll"


def test_ausgelastet_mit_offenem_ausgang_ist_nicht_voll(mcp):  # noqa: F811
    """Review C2: beim Ablegen einer Datei KANN geschrieben sein — „voll, gleich noch einmal“
    legte sie womöglich doppelt ab. Wie jede Antwort mit offenem Ausgang: ``zu_langsam``."""
    mcp["antworten"]["wlo_store_batch_file"] = {"error": {
        "message": "x", "kind": "tool",
        "structured": {"error": {"code": "upstream_busy", "outcomeOpen": True}}}}
    with pytest.raises(mcp_ablage.AblageFehler) as fehler:
        asyncio.run(mcp_ablage.datei_ablegen("tok-1234567890", 0, "r-1"))
    assert fehler.value.code == "zu_langsam"


# ── C4: eine abgelehnte Anleitung ist keine Anleitung ──────────────────────────────────────────

_KOPF = "# Skill: Riesig\n\n---\n\n"
_ZU_GROSS = ("_Die Datei ist zu groß für eine Anleitung und wurde NICHT geladen — eine Anleitung "
             "wird nie gekürzt, also ganz oder gar nicht (https://wlo.example/x)._")


@pytest.mark.parametrize("schluss", [
    _ZU_GROSS,
    "_Dieser Datensatz ist keine Textdatei — get_skill lädt nur Anleitungen im Textformat. Für "
    "den Inhalt anderer Dateien: get_wlo_content_text (https://wlo.example/x)._",
    "_Für diesen Skill ist kein Anleitungstext abrufbar (https://wlo.example/x)._",
])
def test_eine_abgelehnte_datei_ist_keine_anleitung(schluss):
    """Seit dem Audit lehnt ``get_skill`` Dateien über 2 MiB und Binärdateien ab — als Erfolgstext
    mit eigener Schlusszeile. Ein so abgelehnter Master-Skill wäre als Anleitung übernommen."""
    assert master_skill.keine_anleitung(_KOPF + schluss)


def test_eine_echte_anleitung_bleibt_eine():
    """Die Zeile zählt nur am Schluss — eine Anleitung darf sie zitieren."""
    text = _KOPF + _ZU_GROSS + "\n\nSo eine Zeile heißt: teile die Datei.\n\n- Schritt 1"
    assert not master_skill.keine_anleitung(text)
    assert master_skill.keine_anleitung("Skill abc ist nicht abrufbar (404).")


def test_der_muster_weg_merkt_eine_abgelehnte_datei_nicht_als_anleitung(monkeypatch):
    """Die Werkzeug-Schleife des Muster-Wegs (``services/tool_loop``): eine abgelehnte Datei wäre
    sonst die „laufende Anleitung“ der nächsten Züge."""
    from tests.test_tool_loop import _OutcomeFake as _MusterOutcome
    from tests.test_tool_loop import _skill_zug

    _fake, _result, state = _skill_zug(
        monkeypatch, _MusterOutcome({"get_skill": _KOPF + _ZU_GROSS}))
    assert "_skill_lauf" not in state["session_state"]["entities"]
    _fake, _result, state = _skill_zug(
        monkeypatch, _MusterOutcome({"get_skill": "# Skill: Stunde planen\n\n---\n\nArbeite so."}))
    assert state["session_state"]["entities"]["_skill_lauf"]["node_id"] == "n-1"


def test_der_agent_merkt_eine_abgelehnte_datei_nicht_als_anleitung(monkeypatch):
    """Review C4 (schwer): der Agent ist die Vorgabe-Engine — die Prüfung saß nur in der
    Werkzeug-Schleife des Muster-Wegs."""
    _, lauf, _msgs = _lauf(
        monkeypatch,
        [_resp_tools([_tool_call("get_skill", {"nodeId": "gross"})]), _resp_text("Fertig.")],
        outcome=_OutcomeFake({"get_skill": _KOPF + _ZU_GROSS}),
    )
    assert lauf.anleitungen == []
    _, lauf, _msgs = _lauf(
        monkeypatch,
        [_resp_tools([_tool_call("get_skill", {"nodeId": "gut"})]), _resp_text("Fertig.")],
        outcome=_OutcomeFake({"get_skill": "# Skill: Stunde planen\n\n---\n\nArbeite so."}),
    )
    assert [a["node_id"] for a in lauf.anleitungen] == ["gut"]
