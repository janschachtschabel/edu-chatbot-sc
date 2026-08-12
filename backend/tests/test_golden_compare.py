"""P11-4: A/B-Abweichungs-Report (§9-Schritt 4) — deterministische Teile.

Der Vergleich muss GENAU zwei Dinge trennen: eine echte Regression (ein Check,
der in ALT bestand und in NEU fällt) und das Rauschen eines nichtdeterministischen
Modells (Textlänge, Sie/du-Zähler). Wer das Rauschen mitreportet, bekommt bei
jedem Turn eine Abweichung und sieht die eine echte nicht mehr.
"""

import importlib.util
import json
from pathlib import Path

EVALS = Path(__file__).resolve().parents[2] / "evals"

_spec = importlib.util.spec_from_file_location("compare_golden", EVALS / "compare_golden.py")
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_OBSERVED = {
    "persona": "P-LEH", "intent": "I03", "pattern": "M06",
    "cards": 3, "idocs": 0, "qr": 2,
    "register": "sie", "sie": 4, "du": 0, "content_len": 100,
}
_CHECKS = {"persona": True, "intent": True, "register": True,
           "structure": True, "qr": True, "host": True}


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


def _report(*turns, flow="GS-1"):
    """Minimal report in the shape ``run_golden.main`` writes."""
    return {
        "chat_url": "http://host/api/chat",
        "conversations": [{
            "kind": "golden", "flow_id": flow, "title": "Flow Eins",
            "persona_id": "P-LEH", "turns": list(turns),
        }],
    }


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


# ── Regression / Verbesserung ────────────────────────────────────────────

def test_true_to_false_is_a_hard_regression() -> None:
    ref = _report(_turn())
    new = _report(_turn(checks={"persona": False}))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["flow"] == "GS-1" and dev["turn"] == 1
    assert dev["regressions"] == ["persona"]
    assert diff["summary"]["hard_regressions"] == 1
    assert cg.is_blocking(diff) is True


def test_false_to_true_is_an_improvement_not_a_regression() -> None:
    ref = _report(_turn(checks={"intent": False}))
    new = _report(_turn())
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["improvements"] == ["intent"] and dev["regressions"] == []
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


# ── Klassifikation und Struktur ──────────────────────────────────────────

def test_classification_change_is_reported_without_check_change() -> None:
    """Beide Läufe bestehen, treffen aber ein anderes Pattern — genau das ist
    die Abweichung, die ein reiner Pass/Fail-Vergleich verschluckt."""
    ref = _report(_turn())
    new = _report(_turn(observed={"pattern": "M15"}))
    diff = cg.compare_reports(ref, new)
    (dev,) = diff["deviations"]
    assert dev["changed"] == {"pattern": {"ref": "M06", "new": "M15"}}
    assert dev["regressions"] == []
    assert diff["summary"]["classification_changes"] == 1
    assert cg.is_blocking(diff) is False


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
    assert diff["turns"]["only_ref"] == [["GS-1", 2]]
    assert cg.is_blocking(diff) is True


def test_extra_turn_in_new_blocks() -> None:
    """Andersherum genauso: dann sind die Flow-Dateien auseinandergelaufen und
    der ganze Vergleich ist wertlos (README: nur synchron ändern)."""
    diff = cg.compare_reports(_report(_turn()), _report(_turn(), _turn("m2")))
    assert diff["turns"]["only_new"] == [["GS-1", 2]]
    assert cg.is_blocking(diff) is True


def test_flow_missing_in_new_is_named() -> None:
    ref = {"conversations": [*_report(_turn())["conversations"],
                             *_report(_turn(), flow="GS-2")["conversations"]]}
    diff = cg.compare_reports(ref, _report(_turn()))
    assert diff["flows"]["only_ref"] == ["GS-2"]
    assert cg.is_blocking(diff) is True


# ── Redaktions-Stichprobe + CLI ──────────────────────────────────────────

def test_deviating_turn_carries_both_texts_for_review() -> None:
    """§9-4 verlangt Stichproben-Redaktion: ohne die beiden Wortlaute müsste
    die Redaktion zwei Riesen-JSONs von Hand nebeneinanderlegen."""
    ref = _report(_turn(bot="ALT-Wortlaut"))
    new = _report(_turn(bot="NEU-Wortlaut", checks={"persona": False}))
    (dev,) = cg.compare_reports(ref, new)["deviations"]
    assert dev["texts"] == {"ref": "ALT-Wortlaut", "new": "NEU-Wortlaut"}


def test_main_writes_report_and_returns_exit_code(tmp_path) -> None:
    ref_p, new_p = tmp_path / "alt.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn(checks={"intent": False}))),
                     encoding="utf-8")
    out = tmp_path / "out"

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p), "--out", str(out)])

    assert code == 1  # harte Regression
    (written,) = list(out.glob("ab-*.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["summary"]["hard_regressions"] == 1
    assert payload["ref"]["path"] == str(ref_p)


def test_main_returns_zero_when_only_improvements(tmp_path) -> None:
    ref_p, new_p = tmp_path / "alt.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn(checks={"intent": False}))),
                     encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")

    assert cg.main(["--ref", str(ref_p), "--new", str(new_p),
                    "--out", str(tmp_path / "out")]) == 0


# ── A5: Muster-Engine gegen Agent-Modus vergleichen ──────────────────────
#
# Der Agent-Modus klassifiziert nicht (A4b) und wählt kein Muster (A4c-1): er
# liefert die Ersatz-Klassifikation und das Muster ``AGENT``. Persona, Intent
# und Muster weichen deshalb an FAST JEDEM Zug ab — nicht als Befund, sondern
# von Bauart wegen. Ungefiltert überdeckt dieses Rauschen genau das, worum es
# geht: ob die ANTWORT besser oder schlechter wird.


def _pattern_turn(**kw):
    """Der Referenz-Zug: die Muster-Engine hat klassifiziert und ein Muster
    gewählt."""
    return _turn(observed={"persona": "P-LEH", "intent": "I06", "pattern": "M06"}, **kw)


def _agent_turn(**kw):
    """Derselbe Zug im Agent-Modus: Ersatz-Klassifikation (``I03``, ``P-AND``)
    und das synthetische Muster ``AGENT`` — alle drei von Bauart wegen anders."""
    return _turn(observed={"persona": "P-AND", "intent": "I03", "pattern": "AGENT"},
                 checks={"persona": False, "intent": False}, **kw)


def test_ohne_flagge_ist_der_maschinenwechsel_lauter_rauschen() -> None:
    """Die Gegenrichtung zuerst: ohne die Flagge bleibt der Vergleich streng —
    ein Klassifikations-Wechsel IST eine Abweichung, wenn man ALT gegen NEU
    misst (der ursprüngliche Zweck des Reports, P11-4)."""
    diff = cg.compare_reports(_report(_pattern_turn()), _report(_agent_turn()))
    assert diff["summary"]["hard_regressions"] == 2      # persona + intent
    assert diff["summary"]["classification_changes"] == 3
    assert cg.is_blocking(diff) is True


def test_mit_flagge_bleibt_nur_die_antwort_uebrig() -> None:
    diff = cg.compare_reports(_report(_pattern_turn()), _report(_agent_turn()),
                              ignore_classification=True)
    assert diff["summary"]["hard_regressions"] == 0
    assert diff["summary"]["classification_changes"] == 0
    assert diff["deviations"] == []
    assert cg.is_blocking(diff) is False


def test_die_flagge_verdeckt_keine_echte_regression() -> None:
    """Was sie NICHT ausblenden darf: Register, Struktur, Quick-Replies, Host —
    das ist die Antwort, und die ist der Gegenstand des Vergleichs."""
    neu = _agent_turn()
    neu["golden"]["checks"]["structure"] = False
    neu["golden"]["observed"]["cards"] = 0
    diff = cg.compare_reports(_report(_pattern_turn()), _report(neu),
                              ignore_classification=True)
    assert diff["summary"]["hard_regressions"] == 1
    assert diff["deviations"][0]["regressions"] == ["structure"]
    assert diff["deviations"][0]["changed"] == {"cards": {"ref": 3, "new": 0}}
    assert cg.is_blocking(diff) is True


def test_der_report_sagt_dass_gefiltert_wurde(tmp_path) -> None:
    """Ein Report, dem man nicht ansieht, dass er filtert, behauptet mehr
    Deckungsgleichheit, als er geprüft hat."""
    ref_p, new_p = tmp_path / "alt.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_pattern_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_agent_turn())), encoding="utf-8")
    out = tmp_path / "out"

    code = cg.main(["--ref", str(ref_p), "--new", str(new_p), "--out", str(out),
                    "--ignore-classification"])

    assert code == 0
    (written,) = list(out.glob("ab-*.json"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["ignore_classification"] is True
    assert "Klassifikation" in cg.render_console(payload)


def test_ohne_flagge_steht_es_auch_im_report(tmp_path) -> None:
    ref_p, new_p = tmp_path / "alt.json", tmp_path / "neu.json"
    ref_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    new_p.write_text(json.dumps(_report(_turn())), encoding="utf-8")
    cg.main(["--ref", str(ref_p), "--new", str(new_p), "--out", str(tmp_path / "out")])
    (written,) = list((tmp_path / "out").glob("ab-*.json"))
    assert json.loads(written.read_text(encoding="utf-8"))[
        "ignore_classification"] is False
