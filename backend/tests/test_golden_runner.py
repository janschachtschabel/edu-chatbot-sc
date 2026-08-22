"""GV1: golden runner v2 (evals/run_golden.py) — deterministic parts.

v2 (2026-08-22) misst Ergebnisse statt Klassifikator-Interna: die harten
Kategorien sind register/structure/tools_any/qr (host bleibt weich).
persona/intent sind KEINE Golden-Checks mehr — deren Messung ist Auftrag der
generativen Strecke (Plan docs/plans/2026-08-22-golden-v2-anwendungsfaelle.md,
Entscheid §2). v1-Dateien weist der Runner laut ab (kein stiller
Doppelbetrieb), die Engine wird per ``--engine`` gewählt und steht im Bericht.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("run_golden", EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def test_strip_id() -> None:
    assert rg.strip_id("M03 (Schritt-für-Schritt)") == "M03"
    assert rg.strip_id("P-LEH") == "P-LEH"
    assert rg.strip_id("") == ""


def test_detect_register() -> None:
    assert rg.detect_register("Gerne zeige ich Ihnen passende Materialien.")[0] == "sie"
    assert rg.detect_register("Schau dir das an, du findest dein Material hier.")[0] == "du"
    assert rg.detect_register("Hier sind Materialien.")[0] == "neutral"


# ── Chat-Timeout (Review-Befund 3, 2026-08-22) ───────────────────────────


def test_chat_timeout_default_deckt_schleifen_zuege(monkeypatch) -> None:
    """120 s statt der alten 60: Agent-/Hybrid-Züge machen mehrere LLM-Runden,
    und beim Anbieter sind 30-41 s Wartezeit je Runde gemessen — ein 60er
    Deckel verbuchte legitime Züge als Chat-Fehler, asymmetrisch zulasten
    der Schleifen-Maschinen."""
    monkeypatch.delenv("EVAL_CHAT_TIMEOUT", raising=False)
    assert rg.chat_timeout() == 120.0


def test_chat_timeout_liest_die_umgebung(monkeypatch) -> None:
    monkeypatch.setenv("EVAL_CHAT_TIMEOUT", "45")
    assert rg.chat_timeout() == 45.0


def test_chat_timeout_weist_unsinn_laut_ab(monkeypatch) -> None:
    """Wie ``chat_headers``: ein Tippfehler darf nicht still auf den Default
    fallen — sonst misst der Lauf mit einem anderen Deckel, als der Aufrufer
    glaubt."""
    monkeypatch.setenv("EVAL_CHAT_TIMEOUT", "12o")
    with pytest.raises(ValueError):
        rg.chat_timeout()


# ── check_golden_turn v2: Ergebnis-Checks, engine-fair ───────────────────

_BOT_OK = {
    "content": "Gerne zeige ich Ihnen Material.",
    # 2026-08-19: der Host muss zur Vorgabe von ``repo_host()`` passen —
    # der Test prueft die HOST-Pruefung, nicht einen bestimmten Host.
    "cards": [{"wlo_url": "https://repository.staging.openeduhub.net/x"}],
    "inline_documents": [],
    "quick_replies": ["Mehr zeigen"],
}


def test_check_golden_turn_v2_all_pass(monkeypatch) -> None:
    monkeypatch.delenv("REPO_BASE_URL", raising=False)
    expect = {
        "register": "sie", "structure": "cards",
        "tools_any": ["search_wlo_all", "search_wlo_content"],
        "must_offer": "Treffer mit Anschlussangebot.",
    }
    debug = {
        "pattern": "M06 (Suche)",
        "tools_called": ["search_wlo_all (prefetch)", "zeige_dokument"],
    }
    got = rg.check_golden_turn(expect, _BOT_OK, debug)
    assert got["checks"] == {
        "register": True, "structure": True, "tools_any": True,
        "qr": True, "host": True,
    }
    assert got["expected"]["must_offer"] == "Treffer mit Anschlussangebot."
    # Annotationen ("(prefetch)") fallen weg — Vergleich wie metrics.py
    assert got["observed"]["tools_called"] == ["search_wlo_all", "zeige_dokument"]


def test_check_golden_turn_v2_has_no_classifier_checks() -> None:
    """persona/intent im expect werden ignoriert, nicht geprüft — v2 misst
    Ergebnisse. Ein liegengebliebenes v1-Feld darf keinen Check erzeugen."""
    got = rg.check_golden_turn(
        {"persona": "P-LEH", "intent": "I03", "register": "sie"}, _BOT_OK, {})
    assert set(got["checks"]) == {"register", "structure", "tools_any", "qr", "host"}
    assert "persona" not in got["expected"] and "intent" not in got["expected"]


def test_register_neutral_is_none_not_pass() -> None:
    """v2-Ehrlichkeit: Ansage-Zeile + 1-Satz-Lead ohne Anrede ist NICHT
    „richtig gesiezt" — die Heuristik hat schlicht nichts gemessen."""
    neutral_bot = {"content": "Hier ist Material.", "cards": [],
                   "inline_documents": [], "quick_replies": ["ok"]}
    for exp_reg in ("sie", "du"):
        got = rg.check_golden_turn({"register": exp_reg}, neutral_bot, {})
        assert got["checks"]["register"] is None


def test_register_matching_passes_opposite_fails() -> None:
    sie_bot = {"content": "Gerne zeige ich Ihnen Material.", "cards": [],
               "inline_documents": [], "quick_replies": ["ok"]}
    assert rg.check_golden_turn({"register": "sie"}, sie_bot, {})["checks"]["register"] is True
    assert rg.check_golden_turn({"register": "du"}, sie_bot, {})["checks"]["register"] is False


def test_tools_any_fails_when_none_called() -> None:
    debug = {"tools_called": ["wissen_suchen", 42, None]}  # Nicht-Strings ignoriert
    got = rg.check_golden_turn(
        {"tools_any": ["search_wlo_all"]},
        {"content": "x", "cards": [], "inline_documents": [], "quick_replies": ["ok"]},
        debug,
    )
    assert got["checks"]["tools_any"] is False
    assert got["observed"]["tools_called"] == ["wissen_suchen"]


def test_check_golden_turn_not_asserted_is_none() -> None:
    got = rg.check_golden_turn(
        {},
        {"content": "Hi", "cards": [], "inline_documents": [], "quick_replies": []},
        {},
    )
    checks = got["checks"]
    assert checks["register"] is None
    assert checks["structure"] is None
    assert checks["tools_any"] is None
    assert checks["host"] is None  # no card urls => not asserted
    assert checks["qr"] is False  # qr is always asserted


def test_check_golden_turn_failures() -> None:
    got = rg.check_golden_turn(
        {"register": "sie", "structure": "idoc", "tools_any": ["zeige_dokument"]},
        {
            "content": "Schau du dir dein Material an!",
            "cards": [{"url": "https://fremdhost.example/x"}],
            "inline_documents": [],
            "quick_replies": [],
        },
        {"tools_called": ["search_wlo_all"]},
    )
    assert got["checks"] == {
        "register": False, "structure": False, "tools_any": False,
        "qr": False, "host": False,
    }


def test_aggregate_golden_v2_rates_and_zielgruppe() -> None:
    conversations = [{
        "flow_id": "GV-T", "title": "t", "persona_id": "*", "zielgruppe": "P-LEH",
        "turns": [
            {"golden": {"checks": {"register": True, "structure": True,
                                   "tools_any": True, "qr": True, "host": True},
                        "expected": {}, "observed": {}}, "user": "a", "latency_ms": 10},
            {"golden": {"checks": {"register": None, "structure": False,
                                   "tools_any": None, "qr": True, "host": None},
                        "expected": {}, "observed": {}}, "user": "b", "latency_ms": 20},
        ],
    }]
    m = rg.aggregate_golden(conversations)
    assert m["categories"] == ["register", "structure", "tools_any", "qr", "host"]
    assert m["flows"] == 1 and m["turns"] == 2
    # hart: register 1/1, structure 1/2, tools_any 1/1, qr 2/2 => 5/6
    assert m["hard_total"] == 6 and m["hard_passed"] == 5
    assert m["overall_pass_rate"] == round(5 / 6, 3)
    assert m["rates"]["host"] == 1.0  # host is soft: reported, not in hard rate
    # Begleitfix GV1: bis v1 überschrieb die Kategorie-Zelle "persona" die
    # Persona-ID im per_flow-Eintrag (im Studio als Bug dokumentiert,
    # gold-scorecard.ts) — v2 führt die Zielgruppe kollisionsfrei.
    assert m["per_flow"]["GV-T"]["zielgruppe"] == "P-LEH"
    assert m["per_flow"]["GV-T"]["register"] == {"ok": 1, "total": 1}


# ── run_flows record shape (was Judge + Backend-Aggregatoren lesen) ──────
# The flat debug subset mirrors ALT ``eval_golden._flatten_debug``; the full
# ``debug`` blob (trace, context, entities) must NOT travel, or every golden
# report and every persisted transcript carries kilobytes nobody reads.
_FULL_DEBUG = {
    "pattern": "M04 (Fakten-Bulletin)", "persona": "P-LEH (Lehrkraft)",
    "intent": "I01 (Suche)", "safety": None, "tools_called": ["search_wlo"],
    "pattern_id_hint": "M04", "pattern_reasoning": "weil", "llm_engine_match": True,
    "token_usage": {"total_tokens": 7}, "phase3_modulations": {"length": "kurz"},
    "trace": ["big"], "context": {"blob": "x" * 500}, "entities": {"thema": "wasser"},
}


def _flow(*expects: dict) -> dict:
    return {
        "id": "F1", "title": "Flow Eins", "zielgruppe": "P-LEH",
        "turns": [{"message": f"m{i}", "expect": e} for i, e in enumerate(expects, 1)],
    }


def test_run_flows_records_what_judge_and_metrics_read(monkeypatch) -> None:
    monkeypatch.delenv("REPO_BASE_URL", raising=False)

    # ``headers`` seit A5 — die Attrappe folgt der ECHTEN Signatur, nicht dem
    # eigenen Aufruf (Lehre aus A4b: ein ``async``-Double für ein synchrones
    # ``load_engine`` war zwei Scheiben lang grün und in Produktion kaputt).
    async def fake_post(url, message, session_id, headers=None):
        return {"content": "Gerne zeige ich Ihnen die Antwort.",
                "cards": [{"title": "K",
                           "url": "https://repository.staging.openeduhub.net/x"}],
                "quick_replies": ["a"], "debug": dict(_FULL_DEBUG)}

    monkeypatch.setattr(rg, "post_chat", fake_post)
    convs = asyncio.run(rg.run_flows(
        "http://x/api/chat",
        [_flow({"register": "sie", "tools_any": ["search_wlo"], "must_offer": "x"}, {})],
    ))

    conv = convs[0]
    # persona_id "*" = KEIN Klassifikator-Soll: sonst würde
    # ``_aggregate_classification_metrics`` die Zielgruppe als Soll-Persona
    # werten und Golden-Läufe im Agent-Modus die Trends verschmutzen.
    assert conv["persona_id"] == "*"
    assert conv["zielgruppe"] == "P-LEH"
    assert conv["intent_id"] == ""
    t1, t2 = conv["turns"]
    assert t1["debug"]["pattern"] == "M04 (Fakten-Bulletin)"
    assert set(t1["debug"]) == {
        "pattern", "persona", "intent", "safety", "tools_called", "pattern_id_hint",
        "pattern_reasoning", "llm_engine_match", "token_usage", "phase3_modulations",
    }
    assert t1["golden"]["checks"] == {
        "register": True, "structure": None, "tools_any": True,
        "qr": True, "host": True,
    }
    # v1-Relikte weg: v2 hat keine Klassifikator-Erwartungen je Turn
    assert "expected_persona" not in t1 and "expected_intent" not in t1
    assert t1["cards_count"] == 1
    assert t1["response_length"] == len("Gerne zeige ich Ihnen die Antwort.")
    assert isinstance(t1["latency_ms"], int)
    assert t2["golden"]["checks"]["tools_any"] is None  # expect {} → nichts geprüft


def test_run_flows_error_turn_is_recorded(monkeypatch) -> None:
    async def broken_post(url, message, session_id, headers=None):
        raise RuntimeError("down")

    monkeypatch.setattr(rg, "post_chat", broken_post)
    convs = asyncio.run(rg.run_flows(
        "http://x/api/chat", [_flow({"register": "sie"})]))

    turn = convs[0]["turns"][0]
    assert turn["error"] == "down" and turn["bot"] == "(chat error: down)"
    assert isinstance(turn["latency_ms"], int)
    assert "golden" not in turn  # no check result for a turn that never happened


# ── Format-Pin: v2 laden, v1 laut abweisen ───────────────────────────────

def _write_flows(tmp_path, version=2) -> Path:
    data = {"version": version, "flows": [{
        "id": "GV-T-1", "zielgruppe": "P-LEH", "title": "t",
        "turns": [{"message": "hallo",
                   "expect": {"register": "sie", "must_offer": "x"}}],
    }]}
    p = tmp_path / "flows.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_load_flows_accepts_v2(tmp_path) -> None:
    flows = rg.load_flows(_write_flows(tmp_path))
    assert flows[0]["id"] == "GV-T-1"


def test_load_flows_rejects_v1(tmp_path) -> None:
    with pytest.raises(ValueError, match="version: 2"):
        rg.load_flows(_write_flows(tmp_path, version=1))


def test_main_exits_2_on_v1_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("EVAL_CHAT_HEADERS", raising=False)
    rc = rg.main(["--flows", str(_write_flows(tmp_path, version=1)),
                  "--out", str(tmp_path / "r")])
    assert rc == 2


# ── Engine-Wahl: --engine setzt die Kopfzeile, der Bericht trägt sie ─────

def _fake_run_flows(seen: dict):
    async def fake(chat_url, flows, *, headers=None):
        seen["headers"] = dict(headers or {})
        golden = rg.check_golden_turn(
            {"register": "sie"},
            {"content": "Gerne zeige ich Ihnen Material.", "cards": [],
             "inline_documents": [], "quick_replies": ["ok"]},
            {},
        )
        return [{"kind": "golden", "flow_id": "GV-T-1", "title": "t",
                 "persona_id": "*", "zielgruppe": "P-LEH", "intent_id": "",
                 "session_id": "s",
                 "turns": [{"user": "hallo", "bot": "…", "debug": {},
                            "golden": golden, "latency_ms": 7}]}]
    return fake


def _report(tmp_path) -> dict:
    path = next((tmp_path / "r").glob("golden-*.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def test_engine_flag_sets_header_and_report(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.delenv("EVAL_CHAT_HEADERS", raising=False)
    rc = rg.main(["--flows", str(_write_flows(tmp_path)), "--engine", "agent",
                  "--out", str(tmp_path / "r"), "--label", "t"])
    assert rc == 0
    assert seen["headers"]["X-Boerdi-Engine"] == "agent"
    report = _report(tmp_path)
    assert report["engine"] == "agent"
    assert "X-Boerdi-Engine" in report["chat_headers"]  # Name ja, Wert separat


def test_engine_from_env_header_case_insensitive(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.setenv("EVAL_CHAT_HEADERS", '{"x-boerdi-engine": "hybrid"}')
    rc = rg.main(["--flows", str(_write_flows(tmp_path)), "--out", str(tmp_path / "r")])
    assert rc == 0
    assert _report(tmp_path)["engine"] == "hybrid"


def test_engine_flag_overrides_env_header(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.setenv("EVAL_CHAT_HEADERS", '{"x-boerdi-engine": "pattern"}')
    rc = rg.main(["--flows", str(_write_flows(tmp_path)), "--engine", "agent",
                  "--out", str(tmp_path / "r")])
    assert rc == 0
    engine_keys = [k for k in seen["headers"] if k.lower() == "x-boerdi-engine"]
    assert engine_keys == ["X-Boerdi-Engine"]  # genau einmal, Flag gewinnt
    assert seen["headers"]["X-Boerdi-Engine"] == "agent"
    assert _report(tmp_path)["engine"] == "agent"


def test_engine_defaults_to_server_default(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.delenv("EVAL_CHAT_HEADERS", raising=False)
    rc = rg.main(["--flows", str(_write_flows(tmp_path)), "--out", str(tmp_path / "r")])
    assert rc == 0
    assert _report(tmp_path)["engine"] == "default"


# ── GV2: Format-Pin des ausgelieferten v2-Datensatzes ────────────────────

SEED_FLOWS = Path(__file__).resolve().parents[1] / "seeds" / "eval" / "gold-flows.yaml"

_ZIELGRUPPEN = {"P-LEH", "P-LER", "P-ELT", "P-ENT", "P-RED", "P-AND"}
_EXPECT_FELDER = {"register", "structure", "tools_any", "must_offer"}


def test_seed_gold_flows_sind_v2_und_wohlgeformt() -> None:
    """Der Wächter des Datensatzes: eine Quelle (Seed), version 2, jedes
    ``expect`` trägt ein ``must_offer`` (der Judge-Auftrag, GV4), und es
    stehen nur Felder darin, die der Runner auch prüft — ein Tippfehler wie
    ``tools_all`` wäre sonst ein Check, der still nie stattfindet."""
    flows = rg.load_flows(SEED_FLOWS)
    ids = [str(f.get("id")) for f in flows]
    assert len(ids) == 12 and len(set(ids)) == 12
    assert {str(f.get("zielgruppe")) for f in flows} >= _ZIELGRUPPEN
    for flow in flows:
        assert set(flow) <= {"id", "zielgruppe", "title", "turns"}, flow.get("id")
        assert flow.get("turns"), f"{flow.get('id')} ohne Turns"
        for i, turn in enumerate(flow["turns"], start=1):
            wo = f"{flow.get('id')} T{i}"
            assert str(turn.get("message") or "").strip(), f"{wo} ohne message"
            assert set(turn) <= {"message", "expect"}, wo
            exp = turn.get("expect") or {}
            fremd = set(exp) - _EXPECT_FELDER
            assert not fremd, f"{wo}: unbekannte Felder {fremd}"
            assert str(exp.get("must_offer") or "").strip(), f"{wo} ohne must_offer"
            if "register" in exp:
                assert exp["register"] in ("sie", "du"), wo
            if "structure" in exp:
                assert exp["structure"] in ("idoc", "cards"), wo
            if "tools_any" in exp:
                assert isinstance(exp["tools_any"], list) and exp["tools_any"], wo
                assert all(isinstance(t, str) and t.strip() for t in exp["tools_any"]), wo


def test_die_evals_kopie_ist_geloescht() -> None:
    """Regel „Seed ist die Import-Quelle": bis GV2 lag eine byte-gleiche
    Kopie in ``evals/`` und musste von Hand synchron gehalten werden."""
    assert not (EVALS / "gold-flows.yaml").exists()


def test_der_cli_default_zeigt_auf_die_seed_datei() -> None:
    assert Path(rg.DEFAULT_FLOWS) == SEED_FLOWS


def test_die_vorgabe_des_runners_folgt_der_des_backends(monkeypatch) -> None:
    """``repo_host`` verspricht im Docstring „same default as the backend" —
    bis 2026-08-19 hielt das nichts fest. Laufen die beiden auseinander,
    schlaegt ``host_ok`` bei JEDER Karte fehl, und der ganze Lauf meldet einen
    Fehler, den es nicht gibt (bzw. verschweigt einen, den es gibt).
    """
    from urllib.parse import urlparse

    from boerdi.settings import Settings

    monkeypatch.delenv("REPO_BASE_URL", raising=False)
    vorgabe = Settings.model_fields["repo_base_url"].default
    assert rg.repo_host() == urlparse(vorgabe).netloc
