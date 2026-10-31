"""K0-1 (2026-09-26): das Messwerkzeug ``evals/engine_matrix.py`` — ohne Netz.

Die HTTP-Grenze ist ``engine_matrix._transport`` (``httpx.MockTransport``), nach
dem Vorbild von ``llm._acompletion`` im Transport der App.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx

EVALS = Path(__file__).resolve().parents[2] / "evals"


def _lade(name: str):
    spec = importlib.util.spec_from_file_location(name, EVALS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # die Geschwister importieren einander über den Namen
    spec.loader.exec_module(mod)
    return mod


# Die Kennzahlen importiert das Werkzeug seit ST-7b aus dem Backend-Paket.
_lade("engine_matrix_report")
em = _lade("engine_matrix")

FLOWS = {"flows": [{"id": "GV-LEH-1"}, {"id": "GV-RED-1"}, {"id": "GV-SAFE-1"}], "count": 3}


def _netz(monkeypatch, handler) -> None:
    monkeypatch.setattr(em, "_transport", httpx.MockTransport(handler))


def test_der_plan_ist_verschraenkt() -> None:
    """Tageszeit und Auslastung des Anbieters sollen jede Maschine gleich treffen."""
    assert em.plan(["pattern", "agent"], 2) == [
        (1, "pattern"), (1, "agent"), (2, "pattern"), (2, "agent")]


def test_flow_auswahl_mit_ausschluss_und_nur(monkeypatch) -> None:
    _netz(monkeypatch, lambda req: httpx.Response(200, json=FLOWS))
    with em.client("http://x") as c:
        assert em.flow_ids(c, [], ["GV-RED-1"]) == ["GV-LEH-1", "GV-SAFE-1"]
        assert em.flow_ids(c, ["GV-SAFE-1", "GV-RED-1"], ["GV-RED-1"]) == ["GV-SAFE-1"]


def test_der_studio_schluessel_reist_nur_als_kopfzeile(monkeypatch, capsys) -> None:
    gesehen: dict = {}

    def handler(req):
        gesehen["key"] = req.headers.get("X-Studio-Key")
        return httpx.Response(200, json=FLOWS)

    monkeypatch.setenv("STUDIO_API_KEY", "geheim-123-4567")
    _netz(monkeypatch, handler)
    with em.client("http://x") as c:
        em.flow_ids(c, [], [])
    assert gesehen["key"] == "geheim-123-4567"
    assert "geheim-123-4567" not in capsys.readouterr().out


def test_start_wartet_solange_ein_anderer_lauf_laeuft(monkeypatch) -> None:
    antworten = iter([httpx.Response(409, json={"detail": "läuft"}),
                      httpx.Response(200, json={"run_id": "eval-1"})])
    _netz(monkeypatch, lambda req: next(antworten))
    with em.client("http://x") as c:
        lauf = em.start_run(c, "agent", ["A"], judge=True, label="k0", pause=0)
    assert lauf["run_id"] == "eval-1"


def test_warten_bis_der_lauf_nicht_mehr_laeuft(monkeypatch) -> None:
    staende = iter(["running", "running", "done"])

    def handler(req):
        # Der eigene Lauf ist während der Messung der neueste — eine Zeile
        # reicht; die Liste lädt je Zeile das ganze Transkript aus der DB.
        assert req.url.params.get("limit") == "1"
        return httpx.Response(200, json={"runs": [{"id": "eval-1", "status": next(staende)}]})

    _netz(monkeypatch, handler)
    with em.client("http://x") as c:
        assert em.wait_run(c, "eval-1", poll=0) == "done"


def test_warten_uebersteht_einen_kurzen_aussetzer(monkeypatch) -> None:
    """Ein Wackler im Netz darf keine zweistündige Messreihe abbrechen."""
    antworten = iter([httpx.ConnectError("weg"), httpx.Response(502),
                      {"runs": [{"id": "eval-1", "status": "done"}]}])

    def handler(req):
        antwort = next(antworten)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort if isinstance(antwort, httpx.Response) else httpx.Response(
            200, json=antwort)

    _netz(monkeypatch, handler)
    with em.client("http://x") as c:
        assert em.wait_run(c, "eval-1", poll=0) == "done"


def test_start_faehrt_verschraenkt_und_schreibt_die_matrix(monkeypatch, tmp_path) -> None:
    gestartet: list[dict] = []

    def handler(req):
        if req.url.path == "/api/eval/gold-flows":
            return httpx.Response(200, json=FLOWS)
        if req.method == "POST":
            gestartet.append(json.loads(req.content))
            return httpx.Response(200, json={"run_id": f"eval-{len(gestartet)}"})
        return httpx.Response(200, json={"runs": [
            {"id": f"eval-{len(gestartet)}", "status": "done"}]})

    _netz(monkeypatch, handler)
    rc = em.main(["start", "--api", "http://x", "--engines", "pattern,agent",
                  "--repeat", "2", "--exclude", "GV-RED-1", "--label", "k0",
                  "--out", str(tmp_path), "--poll", "0"])

    assert rc == 0
    assert [b["engine"] for b in gestartet] == ["pattern", "agent", "pattern", "agent"]
    assert gestartet[0]["config_slug"] == "k0-pattern-r1"
    assert gestartet[0]["flow_ids"] == ["GV-LEH-1", "GV-SAFE-1"]
    matrix = json.loads(next(tmp_path.glob("matrix-*.json")).read_text(encoding="utf-8"))
    assert [(r["engine"], r["rep"], r["status"]) for r in matrix["runs"]] == [
        ("pattern", 1, "done"), ("agent", 1, "done"),
        ("pattern", 2, "done"), ("agent", 2, "done")]


def _detail(sha: str) -> dict:
    zug = {"user": "u", "bot": "Antwort", "latency_ms": 1200,
           "debug": {"token_usage": {"prompt_tokens": 1000, "cached_tokens": 0,
                                     "completion_tokens": 100, "models": {
                                         "gpt-6-luna": {"prompt": 1000, "cached": 0,
                                                        "completion": 100}}}},
           "golden": {"checks": {"qr": True},
                      "observed": {"tools_called": [], "content_len": 7}}}
    return {"status": "done", "summary": {
        "engine": "agent",
        "messbedingungen": {"chat_model": "gpt-6-luna", "master_skill": {"sha256": sha}}},
        "conversations": [{"flow_id": "GV-LEH-1", "turns": [zug]}]}


def test_auswerten_rechnet_kosten_und_warnt_bei_verschiedenen_bedingungen(
        monkeypatch, tmp_path) -> None:
    details = {"eval-1": _detail("aaa"), "eval-2": _detail("bbb")}
    tafel = {"area": "01-base/pricing", "type": "yaml", "data": {
        "currency": "USD",
        "models": {"gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50}}}}

    def handler(req):
        if req.url.path == "/api/config/data/01-base/pricing":
            return httpx.Response(200, json=tafel)
        return httpx.Response(200, json=details[req.url.path.rsplit("/", 1)[-1]])

    _netz(monkeypatch, handler)
    matrix = tmp_path / "matrix-x.json"
    matrix.write_text(json.dumps({"api": "http://x", "engines": ["agent"], "runs": [
        {"engine": "agent", "rep": 1, "run_id": "eval-1", "label": "k0-agent-r1"},
        {"engine": "agent", "rep": 2, "run_id": "eval-2", "label": "k0-agent-r2"},
    ]}), encoding="utf-8")

    assert em.main(["auswerten", "--matrix", str(matrix)]) == 0

    md = (tmp_path / "matrix-x-auswertung.md").read_text(encoding="utf-8")
    assert "Kosten je Zug (USD)" in md
    assert "0,00015" in md  # (1000·0,10 + 100·0,50) / 1 Mio.
    assert "verschiedenen Bedingungen" in md
    daten = json.loads((tmp_path / "matrix-x-auswertung.json").read_text(encoding="utf-8"))
    assert daten["engines"]["agent"]["runs"] == 2


def test_auswerten_weist_agent_laeufe_ohne_master_skill_aus(monkeypatch, tmp_path) -> None:
    """Review-Befund 2026-09-26: die Prüfsumme ist dieselbe, ob der Master-Skill
    an oder aus ist — der Vergleich muss den Schalter selbst sehen (Plan §10:
    „die Auswertung weist Läufe ohne ihn aus")."""
    an, aus = _detail("aaa"), _detail("aaa")
    an["summary"]["messbedingungen"]["master_skill"]["enabled"] = True
    aus["summary"]["messbedingungen"]["master_skill"]["enabled"] = False
    details = {"eval-1": an, "eval-2": aus}
    tafel = {"area": "01-base/pricing", "type": "yaml",
             "data": {"currency": "USD", "models": {}}}

    def handler(req):
        if req.url.path == "/api/config/data/01-base/pricing":
            return httpx.Response(200, json=tafel)
        return httpx.Response(200, json=details[req.url.path.rsplit("/", 1)[-1]])

    _netz(monkeypatch, handler)
    matrix = tmp_path / "matrix-z.json"
    matrix.write_text(json.dumps({"api": "http://x", "engines": ["agent"], "runs": [
        {"engine": "agent", "rep": 1, "run_id": "eval-1", "label": "k0-agent-r1"},
        {"engine": "agent", "rep": 2, "run_id": "eval-2", "label": "k0-agent-r2"},
    ]}), encoding="utf-8")

    assert em.main(["auswerten", "--matrix", str(matrix)]) == 0

    md = (tmp_path / "matrix-z-auswertung.md").read_text(encoding="utf-8")
    assert "Master-Skill aus in k0-agent-r2" in md
    assert "verschiedenen Bedingungen" in md
    assert "## Messbedingungen" in md


def test_auswerten_nennt_modelle_ohne_preis(monkeypatch, tmp_path) -> None:
    """Eine leere Kostenzeile ohne Grund lädt zum Raten ein — der Bericht sagt,
    welches Modell in der Preistafel fehlt."""
    leer = {"area": "01-base/pricing", "type": "yaml",
            "data": {"currency": "EUR", "models": {}}}

    def handler(req):
        if req.url.path == "/api/config/data/01-base/pricing":
            return httpx.Response(200, json=leer)
        return httpx.Response(200, json=_detail("aaa"))

    _netz(monkeypatch, handler)
    matrix = tmp_path / "matrix-y.json"
    matrix.write_text(json.dumps({"api": "http://x", "engines": ["agent"], "runs": [
        {"engine": "agent", "rep": 1, "run_id": "eval-1", "label": "k0-agent-r1"}]}),
        encoding="utf-8")

    assert em.main(["auswerten", "--matrix", str(matrix)]) == 0

    md = (tmp_path / "matrix-y-auswertung.md").read_text(encoding="utf-8")
    assert "Kein Preis gepflegt für gpt-6-luna" in md
