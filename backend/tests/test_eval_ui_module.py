"""Paket U1-g: UI-Module in der Studio-Evaluation (Plan U1 §17).

G-1: Gold- und generativer Lauf melden die Katalog-Module wie das Widget, abschaltbar je Lauf
(``ui_module: false``); die gemeldete Liste steht in ``config`` und den Messbedingungen.
G-5: die simulierte Person und der Judge sehen die Textfassung der Blöcke.
G-6: ``modul_nutzung`` — je Muster und je Anwendungsfall, welches Modul in wie vielen Zügen.
"""

from __future__ import annotations

import asyncio

import pytest

import boerdi.services.eval.generative_run as generative_run
import boerdi.services.eval.golden_run as golden_run
import boerdi.services.eval_service as svc
from boerdi.api.eval import GoldenRunRequest, StartRequest
from boerdi.services.eval import bericht_md, engine_metrics, modul_nutzung, run_profile
from boerdi.services.eval import run_conditions as rc
from boerdi.services.eval import runner as rn
from boerdi.ui_module import katalog, schalter
from tests.test_eval_router import _FakeSession, _golden_flows, _patch_guard_and_spawn

KATALOG = sorted(katalog.katalog())


def _ohne_start(monkeypatch, mod) -> None:
    """Wächter und Start wie ``_patch_guard_and_spawn``, dazu ohne Herzschlag-Hülle: deren
    Attrappe schließt nur die äußere Koroutine, die innere (``_execute_…_run``) bliebe offen
    und meldete „never awaited“ (Review U1-g #14)."""
    _patch_guard_and_spawn(monkeypatch, mod)

    async def leer() -> None:
        return None

    def ohne_herzschlag(_factory, _tabelle, _run_id, arbeit):
        arbeit.close()
        return leer()

    monkeypatch.setattr(mod, "mit_herzschlag", ohne_herzschlag)


# ── G-1: Start-Anfragen und Lauf-Konfiguration ──────────────────────────


def test_beide_starts_melden_die_module_als_vorgabe() -> None:
    assert GoldenRunRequest().ui_module is True
    assert StartRequest().ui_module is True


@pytest.mark.parametrize(("an", "erwartet"), [(True, KATALOG), (False, [])])
def test_gold_start_haelt_die_gemeldeten_module_fest(monkeypatch, an, erwartet) -> None:
    monkeypatch.setattr(golden_run, "load_gold_flows", _golden_flows)
    _ohne_start(monkeypatch, golden_run)
    session = _FakeSession()
    asyncio.run(svc.start_golden_eval_run(session, None, GoldenRunRequest(ui_module=an)))
    assert session.added[0].config["ui_module"] == erwartet


@pytest.mark.parametrize(("an", "erwartet"), [(True, KATALOG), (False, [])])
def test_generativer_start_haelt_die_gemeldeten_module_fest(monkeypatch, an, erwartet) -> None:
    monkeypatch.setattr(generative_run, "list_personas_and_intents",
                        lambda: {"personas": [{"id": "P-AND"}], "intents": [{"id": "I01"}]})
    _ohne_start(monkeypatch, generative_run)
    session = _FakeSession()
    asyncio.run(svc.start_generative_run(session, None, StartRequest(ui_module=an)))
    assert session.added[0].config["ui_module"] == erwartet


def test_gold_start_prueft_ui_namen_gegen_den_katalog(monkeypatch) -> None:
    from fastapi import HTTPException

    def flows():
        return [{"id": "GV-X", "erwartung": "e", "turns": [
            {"message": "m", "anwendungsfall": "suchen",
             "expect": {"ui_any": ["ui_gibtsnicht"]}}]}]

    monkeypatch.setattr(golden_run, "load_gold_flows", flows)
    _ohne_start(monkeypatch, golden_run)
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(svc.start_golden_eval_run(_FakeSession(), None, GoldenRunRequest()))
    assert fehler.value.status_code == 400 and "ui_gibtsnicht" in str(fehler.value.detail)


class _Ctx:
    async def __aenter__(self):
        return "S"

    async def __aexit__(self, *exc):
        return False


def test_der_gold_job_reicht_die_module_an_runner_und_bedingungen(monkeypatch) -> None:
    gesehen: dict = {}

    class Runner:
        async def run_flows(self, url, flows, *, headers=None, ui_module=None):
            gesehen["runner"] = ui_module
            return [{"flow_id": flows[0]["id"], "turns": []}]

        def aggregate_golden(self, convs):
            return {"overall_pass_rate": 1.0, "turns": 0, "flows": len(convs)}

    async def bedingungen(*, judge_enabled, engine="default", flows=None, ui_module=None):
        gesehen["bedingungen"] = ui_module
        return {}

    async def egal(*a, **kw):
        return True

    monkeypatch.setattr(golden_run, "_load_golden_runner", lambda: Runner())
    monkeypatch.setattr(golden_run, "run_conditions", bedingungen)
    monkeypatch.setattr(golden_run, "_write_golden_progress", egal)
    monkeypatch.setattr(golden_run, "_finalize_run", egal)
    monkeypatch.setattr(golden_run, "fresh_tool_cache", lambda run_id: None)
    monkeypatch.setattr(golden_run, "tool_cache_stats", lambda: {})
    asyncio.run(golden_run._execute_golden_run(
        lambda: _Ctx(), "eval-u1g", [{"id": "A", "turns": []}], False,
        ui_module=["ui_entscheidung"]))
    assert gesehen == {"runner": ["ui_entscheidung"], "bedingungen": ["ui_entscheidung"]}


def test_messbedingungen_nennen_die_module_und_der_vergleich_liest_sie(monkeypatch) -> None:
    async def anzeige():
        return {"enabled": True}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)
    b = asyncio.run(rc.run_conditions(judge_enabled=False, ui_module=["ui_themenbaum"]))
    assert b["ui_module"] == ["ui_themenbaum"]
    assert asyncio.run(rc.run_conditions(judge_enabled=False))["ui_module"] is None
    vergleich = engine_metrics.conditions_of({"messbedingungen": b})
    assert vergleich["ui_module"] == ["ui_themenbaum"]


def test_messbedingungen_nennen_die_wirksamen_module(monkeypatch) -> None:
    """Review U1-g #7: gemeldet heißt nicht angeboten — im Studio abgeschaltete Module bietet der
    Server trotzdem nicht an. ``ui_module_wirksam`` hält fest, was davon wirkte, und welche
    nur der Agent nicht bekommt; der Vergleich der Bedingungen liest es mit."""
    async def anzeige():
        return {"enabled": True}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)
    monkeypatch.setattr(schalter, "_gelesen", lambda: {
        "aus": frozenset({"ui_themenbaum", "ui_inhaltsrahmen"}),
        "agent_aus": frozenset({"ui_entscheidung"})})
    gemeldet = ["ui_entscheidung", "ui_inhaltsrahmen", "ui_themenbaum", "ui_trefferliste"]
    b = asyncio.run(rc.run_conditions(judge_enabled=False, ui_module=gemeldet))
    # Der Inhaltsrahmen ist fest (kein Schalter gilt), der Themenbaum aus.
    assert b["ui_module_wirksam"] == {
        "module": ["ui_entscheidung", "ui_inhaltsrahmen", "ui_trefferliste"],
        "agent_aus": ["ui_entscheidung"]}
    vergleich = engine_metrics.conditions_of({"messbedingungen": b})
    assert vergleich["ui_module_wirksam"] == b["ui_module_wirksam"]
    assert asyncio.run(rc.run_conditions(judge_enabled=False))["ui_module_wirksam"] is None


def test_messbedingungen_nennen_flows_mit_eigenen_modulen(monkeypatch) -> None:
    """Review U1-g #7 (G-2): ein ``ui_module`` im ``environment`` eines Flows gewinnt — die
    Bedingungen sagen, welche Flows das tun."""
    async def anzeige():
        return {"enabled": True}

    monkeypatch.setattr(rc.master_skill, "anzeige", anzeige)
    flows = [{"id": "A", "turns": []},
             {"id": "B", "environment": {"ui_module": []}, "turns": []},
             {"id": "C", "environment": {"tool_mode": "read-only"}, "turns": []}]
    b = asyncio.run(rc.run_conditions(judge_enabled=False, flows=flows, ui_module=KATALOG))
    assert b["gold_flows"]["eigene_ui_module"] == ["B"]
    ohne = asyncio.run(rc.run_conditions(judge_enabled=False, flows=flows[:1]))
    assert "eigene_ui_module" not in ohne["gold_flows"]


# ── G-1/G-5: generativer Lauf ──────────────────────────────────────────


def test_post_chat_meldet_die_module_im_environment(monkeypatch) -> None:
    koerper: dict = {}

    class _Antwort:
        def raise_for_status(self) -> None: ...

        def json(self) -> dict:
            return {"debug": {}}

    class _Client:
        def __init__(self, **_kw) -> None: ...

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a) -> None: ...

        async def post(self, url, json, headers=None):
            koerper.clear()
            koerper.update(json)
            return _Antwort()

    monkeypatch.setattr(rn.httpx, "AsyncClient", _Client)
    asyncio.run(rn._post_chat("http://x", "hallo", "s1", ui_module=["ui_entscheidung"]))
    assert koerper["environment"] == {"ui_module": ["ui_entscheidung"]}
    asyncio.run(rn._post_chat("http://x", "hallo", "s1"))
    assert "environment" not in koerper


_FRAGE_ANTWORT = {
    "content": "Gern — eine Frage vorab.",
    "ui": {"ui_bloecke": [{"block_id": "abcd1234", "modul": "ui_entscheidung", "version": 1,
                           "art": "abfragen", "status": "offen", "daten": {},
                           "text": "Für welches Fach?\n\n1. Biologie\n2. Physik"}]},
}


def test_die_simulierte_person_sieht_die_frage_und_antwortet_getippt(monkeypatch) -> None:
    posts: list[dict] = []
    prompts: list[str] = []

    async def fake_post(chat_url, message, session_id=None, ui_module=None):
        posts.append({"message": message, "ui_module": ui_module})
        return _FRAGE_ANTWORT

    class _Resp:
        def __init__(self, text: str) -> None:
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    async def fake_llm(messages, **kw):
        prompts.append(messages[-1]["content"])
        return _Resp("Biologie bitte")

    monkeypatch.setattr(rn, "_post_chat", fake_post)
    monkeypatch.setattr(rn, "chat_completion", fake_llm)
    conv = asyncio.run(rn.simulate_conversation(
        "http://x", {"id": "P-LEH"}, {"id": "I01"}, max_turns=2, opening="Material bitte",
        ui_module=["ui_entscheidung"]))
    assert [p["ui_module"] for p in posts] == [["ui_entscheidung"], ["ui_entscheidung"]]
    assert posts[1]["message"] == "Biologie bitte"
    assert "1. Biologie" in prompts[-1]
    assert conv["turns"][0]["ui_module"] == ["ui_entscheidung"]
    assert "1. Biologie" in conv["turns"][0]["bot"]


def _sim_lauf(monkeypatch, antwort: dict) -> tuple[dict, list[str]]:
    """Zwei Züge gegen eine feste Antwort; ``prompts`` sind die Texte an die simulierte Person."""
    prompts: list[str] = []

    async def fake_post(chat_url, message, session_id=None, ui_module=None):
        return antwort

    class _Resp:
        def __init__(self, text: str) -> None:
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    async def fake_llm(messages, **kw):
        prompts.append(messages[-1]["content"])
        return _Resp("weiter")

    monkeypatch.setattr(rn, "_post_chat", fake_post)
    monkeypatch.setattr(rn, "chat_completion", fake_llm)
    conv = asyncio.run(rn.simulate_conversation(
        "http://x", {"id": "P-LEH"}, {"id": "I01"}, max_turns=2, opening="hallo",
        ui_module=["ui_entscheidung"]))
    return conv, prompts


def test_der_dialog_zeigt_judge_und_person_karten_und_dokumente(monkeypatch) -> None:
    """Review U1-g #4: die Dialog-Stufe baute den Text ohne Karten und ohne Inhaltsrahmen — die
    G-5-Ausnahme verbarg genau die. Jetzt derselbe Text wie in der Szenario-Stufe."""
    antwort = {"content": "Hier ist etwas.",
               "cards": [{"title": "Brüche üben", "url": "https://wlo.example/1"}],
               "ui": {"ui_bloecke": [
                   {"modul": "ui_trefferliste", "text": "TREFFERTEXT"},
                   {"modul": "ui_inhaltsrahmen", "text": "RAHMENTEXT",
                    "daten": {"titel": "Plan", "markdown": "# Verlaufsplan"}}]},
               "page_action": {"action": "canvas_open", "payload": {"markdown": "LEINWAND"}}}
    conv, prompts = _sim_lauf(monkeypatch, antwort)
    bot = conv["turns"][0]["bot"]
    assert bot == rn._augment_bot_text(antwort)
    assert "Brüche üben" in bot and "# Verlaufsplan" in bot and "LEINWAND" in bot
    assert "Brüche üben" in prompts[-1] and "# Verlaufsplan" in prompts[-1]


def test_die_frage_wird_fuer_die_person_nicht_abgeschnitten(monkeypatch) -> None:
    """Review U1-g #4: ``bot_text[:1500]`` schnitt die Frage hinter einer langen Blase ab."""
    antwort = {**_FRAGE_ANTWORT, "content": "x" * 3000}
    _, prompts = _sim_lauf(monkeypatch, antwort)
    assert "2. Physik" in prompts[-1]
    assert "x" * 1501 not in prompts[-1]


def test_augment_bot_text_zeigt_die_textfassung_ausser_rahmen_und_trefferliste() -> None:
    text = rn._augment_bot_text({"content": "x", "ui": {"ui_bloecke": [
        {"modul": "ui_themenbaum", "text": "Physik\n- Optik"},
        {"modul": "ui_trefferliste", "text": "TREFFERTEXT"},
        {"modul": "ui_inhaltsrahmen", "text": "RAHMENTEXT", "daten": {"markdown": "# Plan"}},
    ]}})
    assert "Optik" in text and "[UI-Modul ui_themenbaum" in text
    assert "TREFFERTEXT" not in text and "RAHMENTEXT" not in text


def test_execute_run_reicht_die_module_an_beide_stufen(monkeypatch) -> None:
    gesehen: list = []

    async def fake_generate(personas, intents, count, progress_cb=None, **kw):
        return [{"persona_id": "P-AND", "intent_id": "I01", "opening": "hi"}]

    async def fake_post(chat_url, message, session_id=None, ui_module=None):
        gesehen.append(("szenario", ui_module))
        return {"content": "ok", "ui": {"ui_bloecke": [{"modul": "ui_trefferliste"}]}}

    async def fake_simulate(chat_url, persona, intent, max_turns=3, **kw):
        gesehen.append(("dialog", kw.get("ui_module")))
        return {"session_id": "s", "turns": [], "ended_early": False}

    async def fake_judge(*a, **kw):
        return {"total": 1.0}

    async def progress(convs, activity):
        return None

    monkeypatch.setattr(rn, "generate_scenarios", fake_generate)
    monkeypatch.setattr(rn, "_post_chat", fake_post)
    monkeypatch.setattr(rn, "simulate_conversation", fake_simulate)
    monkeypatch.setattr(rn, "judge_turn", fake_judge)
    convs: list[dict] = []
    asyncio.run(rn.execute_run(
        chat_url="http://x", run_id="r", conversations=convs, mode="both",
        personas=[{"id": "P-AND"}], intents=[{"id": "I01"}], scenarios_per_combo=1,
        turns_per_conv=1, target_turns=2, progress=progress, ui_module=["ui_trefferliste"]))
    assert gesehen == [("szenario", ["ui_trefferliste"]), ("dialog", ["ui_trefferliste"])]
    assert convs[0]["turns"][0]["ui_module"] == ["ui_trefferliste"]


# ── G-6: Modul-Nutzung ─────────────────────────────────────────────────


def _zug(muster: str, module: list[str] | None, fall: str = "", **extra) -> dict:
    zug = {"debug": {"pattern": muster}, **extra}
    if module is not None:
        zug["ui_module"] = module
    if fall:
        zug["anwendungsfall"] = fall
    return zug


def test_modul_nutzung_je_muster_und_anwendungsfall() -> None:
    convs = [{"turns": [
        _zug("AGENT (Werkzeug-Agent)", ["ui_themenbaum", "ui_trefferliste"], "orientieren"),
        _zug("AGENT (Werkzeug-Agent)", ["ui_entscheidung"], "suchen"),
        _zug("M04 (Fakten-Bulletin)", [], "suchen"),
        _zug("M04 (Fakten-Bulletin)", ["ui_trefferliste"], "", error="down"),  # Fehlzug
        _zug("M04 (Fakten-Bulletin)", None, "suchen"),  # alter Zug ohne Erfassung
    ]}]
    n = modul_nutzung.modul_nutzung(convs)
    assert n["zuege"] == 4 and n["erfasst"] == 3
    assert n["module"] == ["ui_entscheidung", "ui_themenbaum", "ui_trefferliste"]
    assert n["je_muster"] == {
        "AGENT": {"zuege": 2, "module": {"ui_themenbaum": 1, "ui_trefferliste": 1,
                                         "ui_entscheidung": 1}},
        "M04": {"zuege": 1, "module": {}},
    }
    assert n["je_anwendungsfall"] == {
        "orientieren": {"zuege": 1, "module": {"ui_themenbaum": 1, "ui_trefferliste": 1}},
        "suchen": {"zuege": 2, "module": {"ui_entscheidung": 1}},
    }


def test_modul_nutzung_eines_alten_laufs_ist_nicht_erfasst() -> None:
    n = modul_nutzung.modul_nutzung([{"turns": [_zug("M04", None)]}])
    assert n["erfasst"] == 0 and n["je_muster"] == {} and n["module"] == []


def test_ersatzblasen_zaehlen_nicht_mit() -> None:
    """Review U1-g #11: eine Fehler- oder „ausgelastet“-Blase hat nichts gezeigt — sie stünde
    sonst als „Zug ohne Modul“ im Nenner."""
    convs = [{"turns": [
        _zug("AGENT", ["ui_entscheidung"], "suchen"),
        _zug("AGENT", [], "suchen", golden={"fallback": "Da ist intern etwas schiefgelaufen"}),
    ]}]
    n = modul_nutzung.modul_nutzung(convs)
    assert n["zuege"] == 1 and n["erfasst"] == 1
    assert n["je_muster"]["AGENT"]["zuege"] == 1
    assert n["je_anwendungsfall"]["suchen"]["zuege"] == 1


def test_bericht_unterscheidet_noch_keine_zuege_vom_alten_lauf() -> None:
    """Review U1-g #10: ein Lauf ohne beantworteten Zug ist nicht „von vor U1-g“."""
    def text(nutzung):
        return bericht_md.render({"id": "eval-1", "summary": {}, "auswertung": {"gesamt": {}},
                                  "modul_nutzung": nutzung})

    leer = text(modul_nutzung.modul_nutzung([{"turns": []}]))
    assert "Noch keine beantworteten Züge." in leer and "vor U1-g" not in leer
    alt = text(modul_nutzung.modul_nutzung([{"turns": [_zug("M04", None)]}]))
    assert "Nicht erfasst (Lauf von vor U1-g)." in alt


def test_das_lauf_detail_traegt_die_modul_nutzung(monkeypatch) -> None:
    async def get_run(session, run_id):
        return {"id": run_id, "mode": "generative",
                "conversations": [{"turns": [_zug("AGENT", ["ui_entscheidung"])]}]}

    monkeypatch.setattr(run_profile, "get_run", get_run)
    monkeypatch.setattr(run_profile, "load_pricing", lambda: None)
    detail = asyncio.run(run_profile.get_run_with_profile(None, "eval-1"))
    assert detail["modul_nutzung"]["je_muster"]["AGENT"]["module"] == {"ui_entscheidung": 1}


def test_der_bericht_nennt_module_und_modul_nutzung() -> None:
    detail = {
        "id": "eval-1", "summary": {"messbedingungen": {"ui_module": ["ui_themenbaum"]}},
        "auswertung": {"gesamt": {}},
        "modul_nutzung": modul_nutzung.modul_nutzung(
            [{"turns": [_zug("AGENT", ["ui_themenbaum"], "orientieren")]}]),
    }
    text = bericht_md.render(detail)
    assert "**UI-Module:** ui\\_themenbaum" in text
    assert "## Modul-Nutzung" in text and "| AGENT | 1 | 1 |" in text
    ohne = bericht_md.render({**detail, "summary": {"messbedingungen": {"ui_module": []}}})
    assert "**UI-Module:** keine" in ohne


# ── Zwillinge (Review U1-g #13) ────────────────────────────────────────


def test_textfassungs_regeln_von_runner_und_gold_runner_sind_gleich() -> None:
    """``runner`` und ``evals/run_golden.py`` tragen dieselbe Regel als Zwilling (der Gold-Runner
    bleibt ohne ``boerdi.*``) — wie ``ANWENDUNGSFAELLE``/``FALLBACK_TEXTS`` hier festgehalten."""
    from tests.test_golden_ui_module import rg

    assert rn._SCHON_GEZEIGT == rg._SCHON_GEZEIGT
    assert rn._TEXTFASSUNG_MAX == rg._TEXTFASSUNG_MAX
