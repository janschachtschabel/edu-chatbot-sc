"""P11-4/GV3: A/B-Abweichungs-Report (§9-Schritt 4) — deterministische Teile.

Der Vergleich muss GENAU zwei Dinge trennen: eine echte Regression (ein Check,
der in REF bestand und in NEU fällt) und das Rauschen eines
nichtdeterministischen Modells (Textlänge, Sie/du-Zähler). Seit v2 (GV3)
gehört auch die Mechanik zum Rauschen: beobachtetes Muster und Werkzeugliste
sind je Maschine von Bauart wegen anders — der Maschinen-Vergleich ist jetzt
der Normalfall, das frühere ``--ignore-classification`` ist entfernt.
"""

import importlib.util
import json
from pathlib import Path

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("compare_golden", EVALS / "compare_golden.py")
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_OBSERVED = {
    "pattern": "M06", "tools_called": ["search_wlo_all"],
    "cards": 3, "idocs": 0, "qr": 2,
    "register": "sie", "sie": 4, "du": 0, "content_len": 100,
}
_CHECKS = {"register": True, "structure": True, "tools_any": True,
           "qr": True, "host": True}


def _turn(user="m1", *, checks=None, observed=None, bot="Antwort", error=None):
    if error:
        return {"user": user, "bot": f"(chat error: {error})", "error": error}
    return {
        "user": user, "bot": bot,
        "golden": {
            "expected": {},
            "observed": {**_OBSERVED, **(observed or {})},
            "checks": {**_CHECKS, **(checks or {})},
        },
    }


def _report(*turns, flow="GV-1", engine=""):
    """Minimal report in the shape ``run_golden.main`` writes."""
    rep = {
        "chat_url": "http://host/api/chat",
        "conversations": [{
            "kind": "golden", "flow_id": flow, "title": "Flow Eins",
            "persona_id": "*", "zielgruppe": "P-LEH", "turns": list(turns),
        }],
    }
    if engine:
        rep["engine"] = engine
    return rep


# ── Rauschen vs. Signal ──────────────────────────────────────────────────

def test_identical_reports_have_no_deviation() -> None:
    rep = _report(_turn(), _turn("m2"))
    diff = cg.compare_reports(rep, rep)
    assert diff["deviations"] == []
    assert diff["summary"]["turns_compared"] == 2
    assert cg.is_blocking(diff) is False


def test_prose_noise_is_not_a_deviation() -> None:
    """Textlänge und Sie/du-Zähler unterscheiden sich bei jedem LLM-Lauf."""
    ref = _report(_turn(observed={"content_len": 120, "sie": 4, "du": 0}))
    new = _report(_turn(observed={"content_len": 980, "sie": 11, "du": 1},
                        bot="ganz anderer Wortlaut"))
    diff = cg.compare_reports(ref, new)
    assert diff["deviations"] == []
    assert cg.is_blocking(diff) is False


def test_register_label_alone_is_not_a_deviation() -> None:
    """Das Register hat einen eigenen Check — die Beobachtung doppelt zu melden
    erzeugt nur Lärm, solange der Check gleich bleibt."""
    ref = _report(_turn(observed={"register": "sie"}))
    new = _report(_turn(observed={"register": "neutral"}))
    assert cg.compare_reports(ref, new)["deviations"] == []


def test_mechanik_wechsel_ist_keine_abweichung() -> None:
    """Der Kern von GV3: Muster-Engine meldet ``M06`` + Klassifikator-Weg,
    der Agent meldet kein Muster und andere Werkzeuge — an JEDEM Zug, von
    Bauart wegen. Solange die Checks gleich ausgehen, ist das kein Befund;
    was an den Werkzeugen zählt, behauptet der ``tools_any``-Check."""
    ref = _report(_turn(observed={"pattern": "M06",
                                  "tools_called": ["search_wlo_all (prefetch)"]}))
    new = _report(_turn(observed={"pattern": "",
                                  "tools_called": ["search_wlo_content"]}))
    diff = cg.compare_reports(ref, new)
    assert diff["deviations"] == []
    assert cg.is_blocking(diff) is False


# ── Regression / Verbesserung ────────────────────────────────────────────

def test_true_to_false_is_a_hard_regression() -> None:
    ref = _report(_turn())
    new = _report(_turn(checks={"structure": False}))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["flow"] == "GV-1" and dev["turn"] == 1
    assert dev["regressions"] == ["structure"]
    assert diff["summary"]["hard_regressions"] == 1
    assert cg.is_blocking(diff) is True


def test_false_to_true_is_an_improvement_not_a_regression() -> None:
    ref = _report(_turn(checks={"tools_any": False}))
    new = _report(_turn())
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["improvements"] == ["tools_any"] and dev["regressions"] == []
    assert diff["summary"]["hard_regressions"] == 0
    assert cg.is_blocking(diff) is False


def test_not_asserted_to_false_is_not_a_regression() -> None:
    """None heißt „für diesen Turn nicht geprüft" — daraus kann keine
    Regression werden, sonst zählt `host` bei jedem kartenlosen Turn."""
    ref = _report(_turn(checks={"host": None}))
    new = _report(_turn(checks={"host": False}))
    diff = cg.compare_reports(ref, new)
    assert diff["summary"]["hard_regressions"] == 0
    assert diff["summary"]["soft_regressions"] == 0


def test_neutral_register_none_to_false_is_not_a_regression() -> None:
    """v2-Ehrlichkeit trägt bis hierher: ein Turn, dessen Register in REF
    nicht messbar war (None), kann in NEU nur NEU ausfallen — nicht
    schlechter geworden sein."""
    ref = _report(_turn(checks={"register": None}))
    new = _report(_turn(checks={"register": False}))
    assert cg.compare_reports(ref, new)["summary"]["hard_regressions"] == 0


def test_host_regression_is_soft_and_does_not_block() -> None:
    """`host` ist im Runner ausdrücklich weich — hier genauso."""
    ref = _report(_turn())
    new = _report(_turn(checks={"host": False}))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["regressions"] == ["host"]
    assert diff["summary"]["soft_regressions"] == 1
    assert diff["summary"]["hard_regressions"] == 0
    assert cg.is_blocking(diff) is False


# ── Struktur ─────────────────────────────────────────────────────────────

def test_structure_change_is_reported() -> None:
    ref = _report(_turn(observed={"cards": 6}))
    new = _report(_turn(observed={"cards": 0}))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["changed"] == {"cards": {"ref": 6, "new": 0}}
    assert diff["summary"]["structure_changes"] == 1


# ── Fehl-Turns und Strukturbrüche ────────────────────────────────────────

def test_error_turn_in_new_blocks() -> None:
    ref = _report(_turn())
    new = _report(_turn(error="connection refused"))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["error"] == {"ref": None, "new": "connection refused"}
    assert diff["summary"]["errors_new"] == 1
    assert cg.is_blocking(diff) is True


def test_error_turn_only_in_ref_does_not_block() -> None:
    ref = _report(_turn(error="down"))
    new = _report(_turn())
    diff = cg.compare_reports(ref, new)
    assert diff["summary"]["errors_ref"] == 1
    assert diff["summary"]["errors_new"] == 0
    assert cg.is_blocking(diff) is False


def test_turn_missing_in_new_blocks() -> None:
    """Ein unvollständiger NEU-Lauf darf nicht als „keine Regression" gelesen
    werden — sonst belohnt der Report den Abbruch."""
    diff = cg.compare_reports(_report(_turn(), _turn("m2")), _report(_turn()))
    assert diff["turns"]["only_ref"] == [["GV-1", 2]]
    assert cg.is_blocking(diff) is True


def test_extra_turn_in_new_blocks() -> None:
    """Andersherum genauso: dann sind die Flow-Dateien auseinandergelaufen und
    der ganze Vergleich ist wertlos (README: nur synchron ändern)."""
    diff = cg.compare_reports(_report(_turn()), _report(_turn(), _turn("m2")))
    assert diff["turns"]["only_new"] == [["GV-1", 2]]
    assert cg.is_blocking(diff) is True


def test_flow_missing_in_new_is_named() -> None:
    ref = {"conversations": [*_report(_turn())["conversations"],
                             *_report(_turn(), flow="GV-2")["conversations"]]}
    diff = cg.compare_reports(ref, _report(_turn()))
    assert diff["flows"]["only_ref"] == ["GV-2"]
    assert cg.is_blocking(diff) is True


# ── Redaktions-Stichprobe + CLI ──────────────────────────────────────────

def test_deviating_turn_carries_both_texts_for_review() -> None:
    """§9-4 verlangt Stichproben-Redaktion: ohne die beiden Wortlaute müsste
    die Redaktion zwei Riesen-JSONs von Hand nebeneinanderlegen."""
    ref = _report(_turn(bot="REF-Wortlaut"))
    new = _report(_turn(bot="NEU-Wortlaut", checks={"structure": False}))
    (dev,) = cg.compare_reports(ref, new)["deviations"]
    assert dev["texts"] == {"ref": "REF-Wortlaut", "new": "NEU-Wortlaut"}


def test_main_writes_report_and_returns_exit_code(tmp_path) -> None:
    ref_p, new_p = tmp_path / "ref.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn(checks={"tools_any": False}))),
                     encoding="utf-8")
    out = tmp_path / "out"

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p), "--out", str(out)])

    assert code == 1  # harte Regression
    (written,) = list(out.glob("ab-*.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["summary"]["hard_regressions"] == 1
    assert payload["ref"]["path"] == str(ref_p)


def test_main_returns_zero_when_only_improvements(tmp_path) -> None:
    ref_p, new_p = tmp_path / "ref.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn(checks={"tools_any": False}))),
                     encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")

    assert cg.main(["--ref", str(ref_p), "--new", str(new_p),
                    "--out", str(tmp_path / "out")]) == 0


# ── GV3: der Maschinen-Vergleich ist der Normalfall ──────────────────────

def test_der_report_nennt_beide_engines(tmp_path) -> None:
    """Ungleiche Engines sind der gewollte A/B-Fall, kein Fehler — aber ein
    Vergleich, der nicht sagt, WELCHE Maschinen er vergleicht, ist nicht
    lesbar."""
    ref_p, new_p = tmp_path / "ref.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn(), engine="pattern")),
                     encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn(), engine="agent")),
                     encoding="utf-8")
    out = tmp_path / "out"

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p), "--out", str(out)])

    assert code == 0  # gleicher Befund, andere Maschine: kein Blocker
    (written,) = list(out.glob("ab-*.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["engine_ref"] == "pattern"
    assert payload["engine_new"] == "agent"
    console = cg.render_console(payload)
    assert "pattern" in console and "agent" in console


def test_alte_reports_ohne_engine_bleiben_vergleichbar(tmp_path) -> None:
    ref_p, new_p = tmp_path / "ref.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    code = cg.main(["--ref", str(ref_p), "--new", str(new_p),
                    "--out", str(tmp_path / "out")])
    assert code == 0
    (written,) = list((tmp_path / "out").glob("ab-*.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["engine_ref"] == "" and payload["engine_new"] == ""


def test_echte_regression_bleibt_im_maschinen_vergleich_sichtbar() -> None:
    """Was der Rauschfilter NICHT verdecken darf: Register, Struktur,
    Quick-Replies, Werkzeug-Soll — das ist die Antwort, und die ist der
    Gegenstand des Vergleichs."""
    neu = _turn(observed={"pattern": "", "cards": 0},
                checks={"structure": False})
    diff = cg.compare_reports(_report(_turn()), _report(neu))
    assert diff["summary"]["hard_regressions"] == 1
    assert diff["deviations"][0]["regressions"] == ["structure"]
    assert diff["deviations"][0]["changed"] == {"cards": {"ref": 3, "new": 0}}
    assert cg.is_blocking(diff) is True


def test_leere_reports_blockieren_statt_gruen(tmp_path) -> None:
    """Review-Befund 5 (2026-08-22): zwei falsche Dateien (keine Golden-
    Reports) verglichen sich zu "0 Turns, keine Abweichung" mit Exit 0 -
    ein Bedienfehler erzeugte ein gruenes Abnahme-Signal. 0 verglichene
    Turns sind ein Strukturbruch, kein sauberer Vergleich."""
    ref_p, new_p = tmp_path / "a.json", tmp_path / "b.json"
    ref_p.write_text("{}", encoding="utf-8")
    new_p.write_text("{}", encoding="utf-8")

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p),
                    "--out", str(tmp_path / "out")])

    assert code == 1


def test_echter_vergleich_bleibt_exit_0(tmp_path) -> None:
    """Gegenprobe zum 0-Turn-Guard: ein regulaerer, deckungsgleicher
    Vergleich bleibt gruen."""
    ref_p, new_p = tmp_path / "ref.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p),
                    "--out", str(tmp_path / "out")])

    assert code == 0
