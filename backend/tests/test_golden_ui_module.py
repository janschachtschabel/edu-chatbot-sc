"""Paket U1-g: UI-Module im Gold-Runner (``evals/run_golden.py``).

Plan ``docs/plans/2026-11-02-paket-u1-ui-module.md`` §17: der Lauf meldet die Katalog-Module wie
das Widget (G-1/G-2), prüft die gezeigten Blöcke (``ui_any``/``ui_none``, G-3), antwortet im
Auswahlfeld (``ui_antwort``-Züge, G-4), zeigt dem Judge die Textfassungen (G-5) und hält je Zug
die gezeigten Module fest (G-6). Ohne Netz: ``post_chat`` ist eine Attrappe mit der echten
Signatur.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from boerdi.ui_module import katalog

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("run_golden_u1g", EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def _block(modul: str, **extra) -> dict:
    art = "abfragen" if modul == "ui_entscheidung" else "anzeigen"
    return {"block_id": "abcd1234", "modul": modul, "version": 1, "art": art,
            "daten": {}, "text": "", **extra}


def _antwort(*bloecke: dict, content: str = "Gerne zeige ich Ihnen das.") -> dict:
    return {"content": content, "cards": [], "quick_replies": ["ok"],
            "ui": {"ui_bloecke": list(bloecke)}}


_FRAGE = _block(
    "ui_entscheidung", status="offen",
    daten={"frage": "Für welches Fach?", "mehrfach": False,
           "optionen": [{"id": "bio", "label": "Biologie"}, {"id": "phy", "label": "Physik"},
                        {"id": "ch", "label": "Chemie"}]},
    text="Für welches Fach?\n\n1. Biologie\n2. Physik\n3. Chemie")


# ── G-1: die Katalog-Module wie das Widget ──────────────────────────────


def test_katalog_module_sind_die_namen_des_ausgelieferten_katalogs_sortiert() -> None:
    assert rg.katalog_module() == sorted(katalog.katalog())


def test_katalog_module_ohne_datei_bricht_laut_ab(tmp_path) -> None:
    with pytest.raises(OSError):
        rg.katalog_module(tmp_path / "fehlt.json")


# ── G-3: ui_any / ui_none gegen die gezeigten Blöcke ────────────────────


def test_ui_any_besteht_mit_einem_gezeigten_block_des_moduls() -> None:
    g = rg.check_golden_turn({"ui_any": ["ui_themenbaum"]},
                             _antwort(_block("ui_themenbaum"), _block("ui_trefferliste")), {})
    assert g["checks"]["ui"] is True
    assert g["observed"]["ui_module"] == ["ui_themenbaum", "ui_trefferliste"]
    assert g["expected"]["ui_any"] == ["ui_themenbaum"]


def test_ui_any_faellt_ohne_block_durch_auch_wenn_das_werkzeug_lief() -> None:
    # Grundwahrheit ist der gezeigte Block (G-3), nicht ``tools_called``.
    g = rg.check_golden_turn({"ui_any": ["ui_themenbaum"]}, _antwort(),
                             {"tools_called": ["ui_themenbaum"]})
    assert g["checks"]["ui"] is False


def test_ui_none_faellt_durch_wenn_ein_verbotenes_modul_erscheint() -> None:
    g = rg.check_golden_turn({"ui_none": ["ui_entscheidung", "ui_themenbaum"]},
                             _antwort(_FRAGE), {})
    assert g["checks"]["ui"] is False
    assert rg.check_golden_turn({"ui_none": ["ui_entscheidung"]},
                                _antwort(_block("ui_trefferliste")), {})["checks"]["ui"] is True


def test_ui_any_und_ui_none_zusammen() -> None:
    erwartung = {"ui_any": ["ui_trefferliste"], "ui_none": ["ui_entscheidung"]}
    assert rg.check_golden_turn(erwartung, _antwort(_block("ui_trefferliste")),
                                {})["checks"]["ui"] is True
    assert rg.check_golden_turn(erwartung, _antwort(_block("ui_trefferliste"), _FRAGE),
                                {})["checks"]["ui"] is False


def test_ohne_ui_erwartung_ist_der_check_nicht_gestellt() -> None:
    assert rg.check_golden_turn({}, _antwort(_FRAGE), {})["checks"]["ui"] is None


def test_ui_ist_eine_harte_kategorie() -> None:
    assert "ui" in rg.GOLDEN_CATS and "ui" in rg.GOLDEN_HARD


def _flows(turn: dict, *weitere: dict) -> list[dict]:
    return [{"id": "GV-UI-T", "erwartung": "e",
             "turns": [{"message": "m", "anwendungsfall": "suchen", **turn},
                       *({"message": "m", "anwendungsfall": "suchen", **w} for w in weitere)]}]


def test_validate_prueft_ui_namen_gegen_den_katalog() -> None:
    with pytest.raises(ValueError, match="ui_themenbaun"):
        rg.validate_flows(_flows({"expect": {"ui_any": ["ui_themenbaun"]}}),
                          module=rg.katalog_module())
    rg.validate_flows(_flows({"expect": {"ui_none": ["ui_entscheidung"]}}),
                      module=rg.katalog_module())


def test_validate_ohne_katalog_prueft_die_namensform() -> None:
    with pytest.raises(ValueError, match="ui_any"):
        rg.validate_flows(_flows({"expect": {"ui_any": ["Themenbaum"]}}))
    with pytest.raises(ValueError, match="ui_none"):
        rg.validate_flows(_flows({"expect": {"ui_none": "ui_themenbaum"}}))


def test_load_flows_prueft_gegen_den_katalog(tmp_path) -> None:
    pfad = tmp_path / "f.yaml"
    pfad.write_text(yaml.safe_dump({"version": 2, "flows": _flows(
        {"expect": {"ui_any": ["ui_gibtsnicht"]}})}), encoding="utf-8")
    with pytest.raises(ValueError, match="ui_gibtsnicht"):
        rg.load_flows(pfad)


# ── G-4: im Auswahlfeld antworten ───────────────────────────────────────


def test_validate_ui_antwort_form() -> None:
    gut = {"ui_antwort": {"waehle": ["Biologie"], "freitext": "Klasse 7"}}
    rg.validate_flows(_flows({}, gut))
    with pytest.raises(ValueError, match="erste"):
        rg.validate_flows(_flows(gut))
    # Nur eine eigene Antwort (Auswahlfeld 2026-11-09): ``waehle`` darf leer sein, mit Text.
    rg.validate_flows(_flows({}, {"ui_antwort": {"waehle": [], "freitext": "Klasse 11"}}))
    for falsch in ({"waehle": []}, {"waehle": [], "freitext": "  "}, {"waehle": "Biologie"},
                   {"waehle": ["x"], "freitext": 3},
                   {"waehle": ["x"], "unbekannt": 1}):
        with pytest.raises(ValueError, match="ui_antwort"):
            rg.validate_flows(_flows({}, {"ui_antwort": falsch}))


def test_offene_frage_ist_der_offene_entscheidungsblock() -> None:
    assert rg.offene_frage(_antwort(_block("ui_themenbaum"), _FRAGE)) == _FRAGE
    assert rg.offene_frage(_antwort(_block("ui_themenbaum"))) is None
    assert rg.offene_frage(_antwort({**_FRAGE, "status": "beantwortet"})) is None


def test_einzelwahl_waehlt_die_erste_passende_moeglichkeit() -> None:
    antwort, text, beob = rg.baue_ui_antwort(
        {"waehle": ["physik", "Biologie"]}, _FRAGE, "getippt")
    assert antwort == {"block_id": "abcd1234", "daten": {"gewaehlt": ["phy"]}}
    assert text == "Physik"
    assert beob == {"status": "gesendet", "gewaehlt": ["Physik"]}


def test_mehrfachwahl_und_freitext_wie_das_widget() -> None:
    frage = {**_FRAGE, "daten": {**_FRAGE["daten"], "mehrfach": True, "freitext": True}}
    antwort, text, _ = rg.baue_ui_antwort(
        {"waehle": ["Chemie", "bio"], "freitext": "für Klasse 7"}, frage, "getippt")
    # Reihenfolge der Möglichkeiten im Block; ``bio`` passt als Kennung.
    assert antwort["daten"] == {"gewaehlt": ["bio", "ch"], "freitext": "für Klasse 7"}
    assert text == "Biologie, Chemie\nfür Klasse 7"


def _frage(*labels: str, mehrfach: bool = False, **daten) -> dict:
    optionen = [{"id": f"o{i}", "label": label} for i, label in enumerate(labels, start=1)]
    return {**_FRAGE, "daten": {"frage": "?", "mehrfach": mehrfach, "optionen": optionen,
                                **daten}}


def test_einzelwahl_genaue_beschriftung_vor_teilwort() -> None:
    """Review U1-g #1: „Physik“ traf zuerst „Astrophysik“ (Teilwort, früher im Block)."""
    antwort, text, _ = rg.baue_ui_antwort(
        {"waehle": ["Physik"]}, _frage("Astrophysik", "Physik"), "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o2"]} and text == "Physik"


def test_einzelwahl_ganzes_wort_vor_teilwort() -> None:
    antwort, _, _ = rg.baue_ui_antwort(
        {"waehle": ["Physik"]}, _frage("Astrophysik", "Physik der Wärme"), "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o2"]}


def test_einzelwahl_beste_stufe_vor_reihenfolge_der_wendungen() -> None:
    """Die erste Wendung zählt nur unter gleich guten Treffern: ein Teilwort der ersten Wendung
    verliert gegen die genaue Beschriftung der zweiten."""
    antwort, _, _ = rg.baue_ui_antwort(
        {"waehle": ["Physik", "Naturwissenschaft"]},
        _frage("Astrophysik", "Naturwissenschaft"), "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o2"]}
    # Gleich gute Treffer: die Reihenfolge der Wendungen entscheidet (Vorrang des Autors).
    antwort, _, _ = rg.baue_ui_antwort(
        {"waehle": ["Physik", "Biologie"]}, _frage("Biologie", "Physik"), "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o2"]}


def test_teilwort_bleibt_der_letzte_rueckfall() -> None:
    antwort, text, _ = rg.baue_ui_antwort(
        {"waehle": ["Physik"]}, _frage("Biologie", "Astrophysik"), "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o2"]} and text == "Astrophysik"


def test_mehrfachwahl_nimmt_je_wendung_nur_die_besten_treffer() -> None:
    """Review U1-g #1: „Experiment“ nahm auch „Experimentierkasten bauen“ mit dazu."""
    frage = _frage("Einstieg", "Experiment", "Experimentierkasten bauen", "Quiz am Ende",
                   "Quizlet-Karten", mehrfach=True)
    antwort, text, _ = rg.baue_ui_antwort(
        {"waehle": ["Experiment", "Quiz", "Einstieg"]}, frage, "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o1", "o2", "o4"]}
    assert text == "Einstieg, Experiment, Quiz am Ende"


def test_freitext_wird_wie_im_widget_gekuerzt() -> None:
    """Review U1-g #3: das Widget kürzt auf ``maxLength`` des Manifests (1000 Zeichen); der
    Runner tut dasselbe und vermerkt es, statt eine Antwort zu schicken, die der Server
    verwirft."""
    frage = _frage("Physik", "Chemie", mehrfach=True, freitext=True)
    lang = "  " + "x" * 1200 + "  "
    antwort, text, beob = rg.baue_ui_antwort({"waehle": ["Physik"], "freitext": lang},
                                             frage, "getippt")
    assert antwort["daten"]["freitext"] == "x" * rg.FREITEXT_MAX
    assert text == "Physik\n" + "x" * rg.FREITEXT_MAX
    assert beob == {"status": "gesendet", "gewaehlt": ["Physik"], "freitext_gekuerzt": 1200}
    _, _, kurz = rg.baue_ui_antwort({"waehle": ["Physik"], "freitext": "x"}, frage, "g")
    assert "freitext_gekuerzt" not in kurz


# Auswahlfeld 2026-11-09: bei Einzelwahl ist „Eigene Antwort“ ein Punkt der Gruppe — das Widget
# schickt die Wahl ODER den Text. Der Runner macht es ebenso.
def test_einzelwahl_mit_passender_moeglichkeit_verwirft_den_text() -> None:
    frage = _frage("Physik", "Chemie", freitext=True)
    antwort, text, beob = rg.baue_ui_antwort({"waehle": ["Physik"], "freitext": "auch Optik"},
                                             frage, "getippt")
    assert antwort["daten"] == {"gewaehlt": ["o1"]} and text == "Physik"
    assert beob == {"status": "gesendet", "gewaehlt": ["Physik"], "freitext_verworfen": True}


def test_einzelwahl_ohne_passende_moeglichkeit_ist_eine_eigene_antwort() -> None:
    frage = _frage("Physik", "Chemie", freitext=True)
    for spec in ({"waehle": [], "freitext": "  Klasse 11 "},
                 {"waehle": ["Biologie"], "freitext": "Klasse 11"}):
        antwort, text, beob = rg.baue_ui_antwort(spec, frage, "getippt")
        assert antwort["daten"] == {"gewaehlt": [], "freitext": "Klasse 11"} and text == "Klasse 11"
        assert beob == {"status": "gesendet", "gewaehlt": [], "eigene_antwort": True}
    # ohne Freitext-Feld bleibt es getippt
    assert rg.baue_ui_antwort({"waehle": [], "freitext": "Klasse 11"}, _frage("Physik", "Chemie"),
                              "getippt")[0] is None


def test_freitext_max_ist_die_grenze_des_manifests() -> None:
    schema = katalog.katalog()["ui_entscheidung"]["antwort"]
    assert rg.FREITEXT_MAX == schema["properties"]["freitext"]["maxLength"]


def test_freitext_nur_wenn_die_frage_ihn_anbietet() -> None:
    antwort, text, _ = rg.baue_ui_antwort({"waehle": ["Physik"], "freitext": "x"},
                                          _FRAGE, "getippt")
    assert "freitext" not in antwort["daten"] and text == "Physik"


def test_ohne_frage_oder_passende_moeglichkeit_geht_die_nachricht_getippt() -> None:
    assert rg.baue_ui_antwort({"waehle": ["Physik"]}, None, "getippt") == (
        None, "getippt", {"status": "keine_frage", "gewaehlt": []})
    assert rg.baue_ui_antwort({"waehle": ["Kunst"]}, _FRAGE, "getippt") == (
        None, "getippt", {"status": "keine_passende_option", "gewaehlt": []})


def _ui_flow(environment: dict | None = None) -> dict:
    flow = {"id": "GV-UI-T", "title": "t", "zielgruppe": "P-LEH", "erwartung": "e", "turns": [
        {"message": "Ich brauche Material für meine 7. Klasse.", "anwendungsfall": "suchen",
         "expect": {"ui_any": ["ui_entscheidung"]}},
        {"message": "Biologie", "anwendungsfall": "suchen",
         "ui_antwort": {"waehle": ["Biologie"]},
         "expect": {"ui_any": ["ui_trefferliste"]}},
    ]}
    if environment is not None:
        flow["environment"] = environment
    return flow


def _fake_post(gesehen: list[dict], antworten: list[dict]):
    async def fake(url, message, session_id, headers=None, environment=None, ui_antwort=None):
        gesehen.append({"message": message, "environment": environment,
                        "ui_antwort": ui_antwort})
        return antworten[len(gesehen) - 1]
    return fake


def test_run_flows_antwortet_im_auswahlfeld_des_vorigen_zugs(monkeypatch) -> None:
    gesehen: list[dict] = []
    monkeypatch.setattr(rg, "post_chat", _fake_post(
        gesehen, [_antwort(_FRAGE), _antwort(_block("ui_trefferliste"))]))
    convs = asyncio.run(rg.run_flows("http://x/api/chat", [_ui_flow()],
                                     ui_module=["ui_entscheidung", "ui_trefferliste"]))
    erster, zweiter = gesehen
    assert erster["ui_antwort"] is None
    assert erster["environment"] == {"ui_module": ["ui_entscheidung", "ui_trefferliste"]}
    assert zweiter["ui_antwort"] == {"block_id": "abcd1234", "daten": {"gewaehlt": ["bio"]}}
    assert zweiter["message"] == "Biologie"
    t1, t2 = convs[0]["turns"]
    assert t1["ui_module"] == ["ui_entscheidung"] and t1["golden"]["checks"]["ui"] is True
    assert t2["user"] == "Biologie" and t2["golden"]["checks"]["ui"] is True
    assert t2["golden"]["observed"]["ui_antwort"] == {"status": "gesendet",
                                                      "gewaehlt": ["Biologie"]}
    # Der Judge sieht die Frage samt Möglichkeiten (G-5).
    assert "1. Biologie" in t1["bot"] and "ui_entscheidung" in t1["bot"]


def test_run_flows_ohne_frage_schickt_die_nachricht_getippt(monkeypatch) -> None:
    gesehen: list[dict] = []
    monkeypatch.setattr(rg, "post_chat", _fake_post(
        gesehen, [_antwort(), _antwort(_block("ui_trefferliste"))]))
    convs = asyncio.run(rg.run_flows("http://x/api/chat", [_ui_flow()]))
    assert gesehen[1]["ui_antwort"] is None and gesehen[1]["message"] == "Biologie"
    assert convs[0]["turns"][1]["golden"]["observed"]["ui_antwort"]["status"] == "keine_frage"
    # Ohne ``ui_module`` und ohne Flow-Umgebung bleibt der Körper wie vor U1-g.
    assert gesehen[0]["environment"] is None


def test_ui_module_des_flows_gewinnt_ueber_die_laufvorgabe(monkeypatch) -> None:
    gesehen: list[dict] = []
    monkeypatch.setattr(rg, "post_chat", _fake_post(gesehen, [_antwort(), _antwort()]))
    asyncio.run(rg.run_flows(
        "http://x/api/chat", [_ui_flow({"ui_module": [], "tool_mode": "read-only"})],
        ui_module=["ui_entscheidung"]))
    assert gesehen[0]["environment"] == {"ui_module": [], "tool_mode": "read-only"}


def test_post_chat_schickt_ui_antwort_mit(monkeypatch) -> None:
    koerper: dict = {}

    class _Antwort:
        def raise_for_status(self) -> None: ...
        def json(self) -> dict:
            return {}

    class _Client:
        def __init__(self, **_kw) -> None: ...
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_a) -> None: ...
        async def post(self, url, json, headers=None):
            koerper.update(json)
            return _Antwort()

    monkeypatch.setattr(rg.httpx, "AsyncClient", _Client)
    asyncio.run(rg.post_chat("http://x", "Biologie", "s1",
                             ui_antwort={"block_id": "abcd1234", "daten": {"gewaehlt": ["b"]}}))
    assert koerper["ui_antwort"] == {"block_id": "abcd1234", "daten": {"gewaehlt": ["b"]}}


# ── G-5: Textfassungen für den Judge ────────────────────────────────────


def test_augment_zeigt_textfassungen_ausser_inhaltsrahmen_und_trefferliste() -> None:
    text = rg.augment_bot_text(_antwort(
        _block("ui_themenbaum", text="Physik\n- Optik\n- Mechanik"),
        _block("ui_trefferliste", text="TREFFERTEXT"),
        _block("ui_inhaltsrahmen", text="RAHMENTEXT", daten={"markdown": "# Plan"})))
    assert "Optik" in text and "[UI-Modul ui_themenbaum" in text
    assert "TREFFERTEXT" not in text and "RAHMENTEXT" not in text and "# Plan" in text


# ── CLI: --ohne-ui-module und der Bericht ───────────────────────────────


def _write(tmp_path) -> Path:
    pfad = tmp_path / "f.yaml"
    pfad.write_text(yaml.safe_dump({"version": 2, "flows": [_ui_flow()]}, allow_unicode=True),
                    encoding="utf-8")
    return pfad


def _fake_run_flows(seen: dict):
    async def fake(chat_url, flows, *, headers=None, ui_module=None):
        seen["ui_module"] = ui_module
        return []
    return fake


def test_cli_meldet_die_katalog_module_und_nennt_sie_im_bericht(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.delenv("EVAL_CHAT_HEADERS", raising=False)
    rg.main(["--flows", str(_write(tmp_path)), "--out", str(tmp_path / "r")])
    assert seen["ui_module"] == rg.katalog_module()
    bericht = json.loads(next((tmp_path / "r").glob("golden-*.json")).read_text("utf-8"))
    assert bericht["ui_module"] == rg.katalog_module()


def test_cli_ohne_ui_module(tmp_path, monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(rg, "run_flows", _fake_run_flows(seen))
    monkeypatch.delenv("EVAL_CHAT_HEADERS", raising=False)
    rg.main(["--flows", str(_write(tmp_path)), "--ohne-ui-module", "--out", str(tmp_path / "r")])
    assert seen["ui_module"] == []
    bericht = json.loads(next((tmp_path / "r").glob("golden-*.json")).read_text("utf-8"))
    assert bericht["ui_module"] == []
