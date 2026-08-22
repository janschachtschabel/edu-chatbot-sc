"""A5: was den Golden-Lauf zum A/B-Instrument macht (``evals/run_golden.py``).

Zwei Dinge fehlten, um EINE Suite gegen BEIDE Maschinen zu fahren und das
Ergebnis lesen zu können:

* **Kopfzeilen je Lauf.** Der Umschalter ``X-Boerdi-Engine`` ist eine Kopfzeile
  (A4a) — ohne sie liefe die Suite immer gegen die Vorgabe. Wichtiger als das
  Durchreichen ist hier das **Scheitern**: unlesbare Kopfzeilen müssen den Lauf
  abbrechen. Ein stiller Rückfall wäre der teuerste Ausfall dieser Reihe — man
  hielte einen Muster-Lauf für einen Agent-Lauf und vergliche ihn mit sich
  selbst.
* **Latenz je Zug.** Der Sinn des Umschalters ist die Frage „ist er schneller".
  Die Gesamtdauer beantwortet sie nicht: sie mischt 24-Sekunden-Suchen mit
  Sofortantworten. Nützt auch ohne Agent-Modus.

Ergänzt ``test_golden_runner.py`` (die deterministischen Teile) — hier steht,
was A5 hinzugefügt hat.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("run_golden", EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def _flow(*expects: dict) -> dict:
    return {
        "id": "F1", "title": "Flow Eins", "zielgruppe": "P-LEH",
        "turns": [{"message": f"m{i}", "expect": e} for i, e in enumerate(expects, 1)],
    }


def _v2_flows_datei(tmp_path: Path) -> Path:
    """Eine minimale v2-Datei — seit GV1 weist ``main`` v1-Sets ab, die
    Kopfzeilen-Tests brauchen also ein gültiges v2-Ziel."""
    import yaml

    p = tmp_path / "flows.yaml"
    p.write_text(yaml.safe_dump({"version": 2, "flows": [_flow({})]},
                                allow_unicode=True), encoding="utf-8")
    return p


def _antwort() -> dict:
    return {"content": "Antwort", "cards": [], "quick_replies": ["a"], "debug": {}}


# ── Kopfzeilen ──────────────────────────────────────────────────────────────


def test_kopfzeilen_erreichen_jeden_zug(monkeypatch) -> None:
    gesehen: list = []

    async def fake_post(url, message, session_id, headers=None):
        gesehen.append(headers)
        return _antwort()

    monkeypatch.setattr(rg, "post_chat", fake_post)
    asyncio.run(rg.run_flows("http://x/api/chat", [_flow({}, {})],
                             headers={"X-Boerdi-Engine": "agent"}))
    assert gesehen == [{"X-Boerdi-Engine": "agent"}] * 2


def test_gegenrichtung_ohne_kopfzeilen_bleibt_der_lauf_wie_bisher(monkeypatch) -> None:
    """Der Bestandsaufruf des Backends (``run_flows(url, flows)``) reicht keine
    Kopfzeilen herein und darf sich nicht ändern."""
    gesehen: list = []

    async def fake_post(url, message, session_id, headers=None):
        gesehen.append(headers)
        return _antwort()

    monkeypatch.setattr(rg, "post_chat", fake_post)
    asyncio.run(rg.run_flows("http://x/api/chat", [_flow({})]))
    assert gesehen == [None]


def test_leere_angabe_ergibt_keine_kopfzeilen() -> None:
    assert rg.chat_headers("") == {}
    assert rg.chat_headers("   ") == {}
    assert rg.chat_headers(None) == {}


def test_kopfzeilen_werden_aus_json_gelesen() -> None:
    assert rg.chat_headers('{"X-Boerdi-Engine": "agent"}') == {
        "X-Boerdi-Engine": "agent"}


def test_unlesbare_kopfzeilen_scheitern_laut(monkeypatch) -> None:
    """Der teuerste Ausfall dieser Reihe wäre ein stiller: ohne die Kopfzeile
    liefe die Suite gegen die Muster-Engine, und der A/B-Vergleich vergliche sie
    mit sich selbst — ohne dass irgendwo etwas rot wird."""
    for kaputt in ('{"a": ', "[1, 2]", '"nur ein string"', '{"a": 5}'):
        try:
            rg.chat_headers(kaputt)
        except ValueError:
            continue
        raise AssertionError(f"{kaputt!r} haette scheitern muessen")


def test_main_bricht_bei_unlesbaren_kopfzeilen_ab(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EVAL_CHAT_HEADERS", "{kaputt")

    async def darf_nicht_laufen(*a, **k):     # pragma: no cover
        raise AssertionError("run_flows trotz unlesbarer Kopfzeilen gestartet")

    monkeypatch.setattr(rg, "run_flows", darf_nicht_laufen)
    assert rg.main(["--flows", str(_v2_flows_datei(tmp_path)),
                    "--out", str(tmp_path / "r")]) == 2


def test_der_report_nennt_die_kopfzeilen_namen_ohne_werte(
        monkeypatch, tmp_path) -> None:
    """Eine Kopfzeile kann ein Geheimnis tragen (``WLO-Access-Block`` enthält die
    Zugangs-Kennung). Der Report soll trotzdem sagen, WOMIT gemessen wurde —
    also die Namen, nie die Werte."""
    monkeypatch.setenv(
        "EVAL_CHAT_HEADERS",
        '{"X-Boerdi-Engine": "agent", "WLO-Access-Block": "geheim-jti-123"}')

    async def fake_flows(url, flows, *, headers=None):
        return [{"kind": "golden", "flow_id": "F1", "title": "", "persona_id": "*",
                 "zielgruppe": "", "intent_id": "", "session_id": "s", "turns": []}]

    monkeypatch.setattr(rg, "run_flows", fake_flows)
    rg.main(["--flows", str(_v2_flows_datei(tmp_path)),
             "--out", str(tmp_path)])
    roh = next(tmp_path.glob("golden-*.json")).read_text(encoding="utf-8")
    assert "geheim-jti-123" not in roh
    assert json.loads(roh)["chat_headers"] == ["WLO-Access-Block", "X-Boerdi-Engine"]


# ── Latenz je Zug ───────────────────────────────────────────────────────────


def test_jeder_zug_traegt_seine_latenz(monkeypatch) -> None:
    async def fake_post(url, message, session_id, headers=None):
        return _antwort()

    monkeypatch.setattr(rg, "post_chat", fake_post)
    convs = asyncio.run(rg.run_flows("http://x/api/chat", [_flow({}, {})]))
    for turn in convs[0]["turns"]:
        assert isinstance(turn["latency_ms"], int)
        assert turn["latency_ms"] >= 0


def test_auch_ein_fehl_zug_traegt_seine_latenz(monkeypatch) -> None:
    """Eine Zeitüberschreitung ist der teuerste Zug des Laufs — ausgerechnet den
    nicht zu messen wäre die falsche Auslassung."""
    async def broken_post(url, message, session_id, headers=None):
        raise RuntimeError("down")

    monkeypatch.setattr(rg, "post_chat", broken_post)
    convs = asyncio.run(rg.run_flows("http://x/api/chat", [_flow({})]))
    turn = convs[0]["turns"][0]
    assert turn["error"] == "down"
    assert isinstance(turn["latency_ms"], int)


def _conv(*latenzen: int) -> dict:
    return {
        "flow_id": "F1", "title": "T", "persona_id": "P-LEH",
        "turns": [{"user": f"m{i}", "latency_ms": ms,
                   "golden": {"expected": {}, "observed": {}, "checks": {"qr": True}}}
                  for i, ms in enumerate(latenzen, 1)],
    }


def test_die_scorecard_traegt_die_latenz_verteilung() -> None:
    """Der Median beantwortet „ist er schneller", das Maximum „wo steht er"."""
    metrics = rg.aggregate_golden([_conv(100, 200, 300, 400, 23_300)])
    lat = metrics["latency"]
    assert lat["turns"] == 5
    assert lat["p50_ms"] == 300
    assert lat["max_ms"] == 23_300
    assert lat["total_ms"] == 24_300
    assert metrics["per_turn"][0]["latency_ms"] == 100


def test_eine_scorecard_ohne_latenz_bleibt_gueltig() -> None:
    """Ein Zug ohne Messung (Bestands-Report, anderer Erzeuger) darf die
    Auswertung nicht kippen — er zählt nur nicht mit."""
    conv = _conv(100, 200)
    del conv["turns"][0]["latency_ms"]
    lat = rg.aggregate_golden([conv])["latency"]
    assert lat["turns"] == 1 and lat["p50_ms"] == 200


def test_ohne_jede_messung_bleibt_die_latenz_leer() -> None:
    conv = _conv(100)
    del conv["turns"][0]["latency_ms"]
    lat = rg.aggregate_golden([conv])["latency"]
    assert lat["turns"] == 0
    assert lat["p50_ms"] is None and lat["max_ms"] is None


def test_die_konsole_zeigt_die_latenz() -> None:
    text = rg.render_console(rg.aggregate_golden([_conv(100, 23_300)]))
    assert "Latenz" in text
    assert "23.3" in text
