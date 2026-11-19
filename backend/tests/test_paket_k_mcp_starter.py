"""Paket K1/K8 (Plan 2026-11-17): Kestra-Flows über die MCP-Werkzeuge (``mcp_starter``).

Die Antworten unten sind die Drahtform des MCP (``wlo-mcp-server-sc``, Commit ``da33918``,
``src/tools/bapi-flows.ts``): ``structuredContent`` je Ausgang, Ablehnungen als ``isError`` mit
``status``/``reason`` und ``error.code`` (+ ``outcomeOpen``), so wie ``transport.call_tool`` sie
weiterreicht (``{"error": {"kind": "tool", "structured": …}}``). Keine Netzaufrufe.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from boerdi.services.auftraege import client, mcp_starter

FLOW = "edusharing.chatbot/node-metadata-write"
JOB = "8f2c1d7e-job-4711"
TOKEN = "ct_vorschau_schluessel_0123456789"


def _ok(structured: dict, text: str = "ok") -> dict:
    return {"result": {"content": [{"type": "text", "text": text}],
                       "structuredContent": structured}}


def _abgelehnt(reason: str, *, outcome_open: bool | None = None, status: str = "failed",
               **mehr) -> dict:
    """``failed()`` des MCP: ``isError`` mit ``status``, ``reason`` und ``error``."""
    fehler = {"code": reason, "message": f"Text zu {reason} (jobId: {JOB})"}
    if outcome_open is not None:
        fehler["outcomeOpen"] = outcome_open
    return {"error": {"kind": "tool", "message": fehler["message"],
                      "structured": {"status": status, "reason": reason, **mehr,
                                     "error": fehler}}}


VORSCHAU = _ok({"status": "preview", "confirm": {
    "token": TOKEN, "expiresAt": "2026-11-18T10:10:00.000Z",
    "preview": {"action": "change", "target": {"nodeId": FLOW, "kind": "flow", "title": FLOW},
                "statement": "Startet den Auftrag für 2 Materialien.",
                "items": ["n-1 „A“", "n-2 „B“"], "fields": []}}},
    text=f"Bitte prüfen … Dazu denselben Aufruf mit confirmToken: {TOKEN} wiederholen.")
GESTARTET = _ok({"status": "started", "jobId": JOB, "flow": FLOW},
                text=f"Der Auftrag „{FLOW}“ läuft (jobId: {JOB}).")


@pytest.fixture
def mcp(monkeypatch):
    gerufen: list = []
    antworten: dict[str, list] = {}

    async def call_tool(name, args, **_k):
        gerufen.append((name, args))
        liste = antworten.get(name) or [{"error": {"message": "x", "kind": "transport"}}]
        return liste.pop(0) if len(liste) > 1 else liste[0]

    monkeypatch.setattr(mcp_starter.transport, "call_tool", call_tool)
    monkeypatch.setattr(mcp_starter, "has_personal_auth", lambda: True)
    monkeypatch.setattr(mcp_starter, "_zug_block", lambda: "wlo2.block-der-person")
    monkeypatch.setattr(mcp_starter, "_neu_geholt", None)      # Takt des Nachholens je Test neu
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({FLOW}))
    return {"gerufen": gerufen, "antworten": antworten}


def _start(eingaben=None):
    return asyncio.run(mcp_starter.starten(FLOW, eingaben or {"node_ids": ["n-1", "n-2"],
                                                               "language": "de"}))


# ── K1: Start in zwei Schritten ──────────────────────────────────────────────────────────────

def test_start_holt_die_vorschau_und_bestaetigt_mit_dem_schluessel(mcp):
    mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, GESTARTET]
    kennung = _start()
    assert kennung == mcp_starter.PRAEFIX + JOB and mcp_starter.ist_mcp(kennung)
    [(n1, a1), (n2, a2)] = mcp["gerufen"]
    eingaben = {"node_ids": ["n-1", "n-2"], "language": "de"}
    assert (n1, a1) == ("wlo_start_flow", {"flow": FLOW, "inputs": eingaben})
    assert (n2, a2) == ("wlo_start_flow", {"flow": FLOW, "inputs": eingaben,
                                           "confirmToken": TOKEN})


def test_eine_wiederholte_antwort_gilt_als_gestartet(mcp):
    mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, _ok(
        {"status": "started", "jobId": JOB, "flow": FLOW, "replayed": True})]
    assert _start() == mcp_starter.PRAEFIX + JOB


@pytest.mark.parametrize(("antwort", "grund"), [
    (_abgelehnt("not_allowed"), "nicht_erlaubt"),
    (_abgelehnt("bad_inputs", problems=[{"nodeId": "n-1", "problem": "is_reference"}]),
     "eingaben"),
    (_abgelehnt("login_required"), "abgewiesen"),
    (_abgelehnt("upstream_error"), "fehler"),
    ({"error": {"message": "x", "kind": "transport"}}, "fehler"),
    ({"error": {"message": "x", "kind": "busy"}}, "voll"),
    (_ok({"confirm": None, "unchanged": True}), "fehler"),
])
def test_eine_abgelehnte_vorschau_startet_nichts(mcp, antwort, grund):
    mcp["antworten"]["wlo_start_flow"] = [antwort]
    with pytest.raises(client.AuftragFehler) as fehler:
        _start()
    assert fehler.value.grund == grund
    assert all("confirmToken" not in a for _n, a in mcp["gerufen"])


@pytest.mark.parametrize(("antwort", "grund", "code"), [
    (_abgelehnt("bad_inputs", outcome_open=False, requiresNewPreview=True), "eingaben", None),
    (_abgelehnt("edu_user_required", outcome_open=False), "abgewiesen", "EDU_USER_REQUIRED"),
    (_abgelehnt("rejected", outcome_open=False), "abgewiesen", None),
    (_abgelehnt("upstream_error", outcome_open=False), "fehler", None),
    (_abgelehnt("confirm_expired", outcome_open=False), "fehler", None),
])
def test_outcome_open_false_heisst_nichts_gestartet(mcp, antwort, grund, code):
    mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, antwort]
    with pytest.raises(client.AuftragFehler) as fehler:
        _start()
    assert (fehler.value.grund, fehler.value.code) == (grund, code)


@pytest.mark.parametrize("antwort", [
    _abgelehnt("upstream_error", outcome_open=True),
    _abgelehnt("rate_limited", outcome_open=True, retryAfter=30),
    _abgelehnt("confirm_unknown", outcome_open=True),
    {"error": {"message": "x", "kind": "timeout"}},
    {"error": {"message": "x", "kind": "transport"}},
    _ok({"inProgress": True}),
    _ok({"status": "started", "flow": FLOW}),                      # 202 ohne brauchbare jobId
    _ok({"status": "started", "jobId": "../x", "flow": FLOW}),
])
def test_outcome_open_true_oder_keine_antwort_startet_nie_neu(mcp, antwort):
    """``error.outcomeOpen: true`` (oder keine Antwort nach der Bestätigung): ein Job kann laufen —
    kein zweiter Start, der Aufrufer sieht nach."""
    mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, antwort]
    with pytest.raises(client.AuftragFehler) as fehler:
        _start()
    assert fehler.value.grund == "offen"
    assert len(mcp["gerufen"]) == 2


def test_nur_freigegebene_flows_und_nur_mit_anmeldung(mcp, monkeypatch):
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.starten("andere/flow", {}))
    assert fehler.value.grund == "nicht_erlaubt"
    monkeypatch.setattr(mcp_starter, "has_personal_auth", lambda: False)
    with pytest.raises(client.AuftragFehler) as fehler:
        _start()
    assert fehler.value.grund == "abgewiesen" and mcp["gerufen"] == []


def test_verfuegbar_nur_mit_allen_drei_werkzeugen(monkeypatch):
    from boerdi.services.mcp import faehigkeiten

    faehigkeiten.vergessen()
    try:
        faehigkeiten.uebernehmen([{"name": "wlo_start_flow"}, {"name": "wlo_flow_status"}])
        assert mcp_starter.verfuegbar() is False
        faehigkeiten.uebernehmen([{"name": n} for n in mcp_starter.WERKZEUGE])
        assert mcp_starter.verfuegbar() is True
    finally:
        faehigkeiten.vergessen()


# ── K1: Stand ────────────────────────────────────────────────────────────────────────────────

def _stand(antwort, mcp, kennung=mcp_starter.PRAEFIX + JOB):
    mcp["antworten"]["wlo_flow_status"] = [antwort]
    return asyncio.run(mcp_starter.stand(kennung))


def test_stand_laeuft_mit_fortschritt(mcp):
    stand = _stand(_ok({"status": "running", "rawStatus": "RUNNING", "progress": {
        "started": 4, "running": 1, "succeeded": 2, "warning": 0, "failed": 1}}), mcp)
    assert stand.status == "laeuft"
    # Durchtest Paket K (19.11.): gescheiterte zählen nicht als fertig
    assert stand.fortschritt == {"fertig": 2, "gesamt": 4, "fehlgeschlagen": 1}
    assert mcp["gerufen"] == [("wlo_flow_status", {"jobId": JOB})]


def test_stand_fertig_mit_bericht_und_dateien(mcp):
    bericht = {"report": [{"nodeId": "n-1", "status": "success",
                           "written": {"changedKeys": ["cclom:title"], "ignoredKeys": []},
                           "httpCode": 200, "characters": 812}]}
    stand = _stand(_ok({"status": "succeeded", "rawStatus": "SUCCEEDED", "warnings": True,
                        "outputs": bericht, "files": [{"outputId": "o1", "name": "a.md",
                                                       "size": 3, "available": True}]}), mcp)
    assert stand.status == "fertig" and stand.outputs == bericht and stand.warnungen is True
    assert stand.dateien == [{"name": "a.md", "groesse": 3, "kennung": "o1", "verfuegbar": True}]


def test_ausgaben_tragen_keine_job_kennung(mcp):
    """K8: was der Flow ausgibt, wird Teil des Vorgangs — eine Kennung des Jobs darin geht weg."""
    stand = _stand(_ok({"status": "succeeded", "outputs": {
        "jobId": JOB, "report": [{"nodeId": "n-1", "executionId": "e-1", "status": "ok"}]}}), mcp)
    assert stand.outputs == {"report": [{"nodeId": "n-1", "status": "ok"}]}


@pytest.mark.parametrize(("roh", "status", "code"), [
    ({"status": "failed", "rawStatus": "FAILED", "errorCode": "TIMEOUT"}, "fehler", "TIMEOUT"),
    ({"status": "cancelled", "rawStatus": "KILLED"}, "fehler", None),
    ({"status": "succeeded", "truncated": True}, "fehler", None),
])
def test_stand_beendet_ohne_ergebnis(mcp, roh, status, code):
    stand = _stand(_ok(roh), mcp)
    assert (stand.status, stand.fehlercode) == (status, code)


@pytest.mark.parametrize(("antwort", "grund"), [
    (_ok({"status": "unknown", "rawStatus": "WEIRD"}), "fehler"),        # erneut abfragbar
    (_abgelehnt("unknown_job"), "job_unbekannt"),
    (_abgelehnt("upstream_error"), "fehler"),
    (_abgelehnt("rate_limited", retryAfter=20), "voll"),
    (_abgelehnt("edu_user_required"), "abgewiesen"),
    ({"error": {"message": "x", "kind": "auth"}}, "abgewiesen"),
    ({"error": {"message": "x", "kind": "timeout"}}, "fehler"),
])
def test_stand_fehler(mcp, antwort, grund):
    with pytest.raises(client.AuftragFehler) as fehler:
        _stand(antwort, mcp)
    assert fehler.value.grund == grund


def test_ein_offener_start_ist_nicht_abfragbar(mcp):
    """Ausgang beim Start offen: es gibt keine jobId — „Stand nachsehen“ heißt die Datensätze lesen,
    der MCP wird nicht gefragt."""
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.stand(mcp_starter.offene_kennung()))
    assert fehler.value.grund == "job_unbekannt" and mcp["gerufen"] == []


# ── K1/K4: Abbruch ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("antwort", "ausgang"), [
    (_ok({"status": "cancelled"}), "abgebrochen"),
    (_ok({"status": "already_finished"}), "schon_fertig"),
])
def test_abbrechen(mcp, antwort, ausgang):
    mcp["antworten"]["wlo_cancel_flow"] = [antwort]
    assert asyncio.run(mcp_starter.abbrechen(mcp_starter.PRAEFIX + JOB)) == ausgang
    assert mcp["gerufen"] == [("wlo_cancel_flow", {"jobId": JOB})]


@pytest.mark.parametrize(("antwort", "grund"), [
    (_ok({"status": "unknown_job"}), "job_unbekannt"),
    (_abgelehnt("upstream_error", outcome_open=True), "offen"),
    ({"error": {"message": "x", "kind": "timeout"}}, "offen"),
    ({"error": {"message": "x", "kind": "transport"}}, "offen"),
    (_abgelehnt("rejected"), "abgewiesen"),
])
def test_abbrechen_fehler(mcp, antwort, grund):
    mcp["antworten"]["wlo_cancel_flow"] = [antwort]
    with pytest.raises(client.AuftragFehler) as fehler:
        asyncio.run(mcp_starter.abbrechen(mcp_starter.PRAEFIX + JOB))
    assert fehler.value.grund == grund


# ── K8: die jobId nie ins Log ────────────────────────────────────────────────────────────────

def test_die_job_id_steht_in_keinem_log(mcp, caplog):
    mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, GESTARTET]
    mcp["antworten"]["wlo_flow_status"] = [
        _ok({"status": "running"}), _ok({"status": "unknown", "rawStatus": "X"}),
        _abgelehnt("unknown_job"), _abgelehnt("upstream_error")]
    mcp["antworten"]["wlo_cancel_flow"] = [_abgelehnt("upstream_error", outcome_open=True)]
    with caplog.at_level(logging.DEBUG):
        kennung = _start()
        for _ in range(4):
            try:
                asyncio.run(mcp_starter.stand(kennung))
            except client.AuftragFehler:
                pass
        with pytest.raises(client.AuftragFehler):
            asyncio.run(mcp_starter.abbrechen(kennung))
        mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, _abgelehnt("upstream_error",
                                                                   outcome_open=True)]
        with pytest.raises(client.AuftragFehler):
            _start()
    assert caplog.records, "die Wege oben loggen etwas"
    assert JOB not in caplog.text and TOKEN not in caplog.text
