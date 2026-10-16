"""Studio-Regeln als Regex mit Zeitgrenze (Paket 6, B1).

Zwei Stellen wenden ein im Studio gepflegtes Muster auf jede Nachricht an: die
Lotsen-Regeln (``02-domain/guide-rules``) und die Policy-Regeln
(``01-base/policy``). Die Nachricht kommt von jedem Client. Ein ungünstiges
Muster wie ``^(\\w+\\s?)*$`` lief mit ``re`` gegen eine lange Nachricht
exponentiell und hielt den Worker fest (Review Paket 4, 2026-10-04).
"""

from __future__ import annotations

import time

import pytest

#: Katastrophales Zurückspringen in ``re``: verschachtelte Quantoren ohne Treffer
#: am Ende. ``regex`` erkennt diesen Fall selbst und antwortet sofort.
_REDOS = r"^(\w+\s?)*$"
#: Ein Fall, an dem auch ``regex`` zurückspringt, bis die Zeitgrenze greift
#: (gemessen 2026-10-08: Abbruch nach 0,05 s). Der Vorausblick hebelt seine
#: Schutzmechanik aus.
_REDOS_AUCH_FUER_REGEX = r"^(?:a|(?=a)a)+$"
_LANG_A = "a" * 30 + "!"
#: Mit ``re`` gemessen 2026-10-08: 23 Zeichen 0,8 s, jedes weitere verdoppelt —
#: 26 sind rund 7 s (endlich, damit der Gegenbeweis ohne Fix nicht hängt), 40
#: wären über einen Tag.
_LANG = "a" * 26 + "!"
#: Großzügig über der Frist des Moduls, weit unter dem, was ``re`` hier braucht.
_HOECHSTENS_S = 2.0


def test_ein_ungünstiges_muster_endet_binnen_frist_ohne_treffer(caplog):
    from boerdi.domain import regel_regex

    muster = regel_regex.uebersetze(_REDOS_AUCH_FUER_REGEX)
    beginn = time.monotonic()
    with caplog.at_level("WARNING", logger="boerdi.domain.regel_regex"):
        assert regel_regex.trifft(muster, _LANG_A) is False
    assert time.monotonic() - beginn < _HOECHSTENS_S
    assert "Zeitgrenze" in caplog.text
    # Der Nachrichtentext gehört nicht ins Log.
    assert _LANG_A not in caplog.text


def test_ein_gewoehnliches_muster_trifft_wie_mit_re():
    from boerdi.domain import regel_regex

    assert regel_regex.trifft(regel_regex.uebersetze(r"\bmathe\b"), "Ich mag Mathe") is True
    assert regel_regex.trifft(regel_regex.uebersetze(r"\bmathe\b"), "Mathematik") is False
    # Ohne ignore_case bleibt Groß/Klein, wie ``re.search`` ohne Flag.
    assert regel_regex.trifft(regel_regex.uebersetze("Mathe", ignore_case=False), "mathe") is False


def test_ein_ungueltiges_muster_meldet_sich_beim_uebersetzen():
    from boerdi.domain import regel_regex

    with pytest.raises(regel_regex.RegexFehler):
        regel_regex.uebersetze("(")


def test_lotsen_regeln_haengen_nicht_an_einem_ungünstigen_muster(monkeypatch):
    from boerdi.services import config_loader
    from boerdi.services import guide_qr_injector as gq

    regeln = {"message_rules": [
        {"pattern": _REDOS, "label": "Falle", "url": "https://wirlernenonline.de/a", "priority": 9},
        {"pattern": _REDOS_AUCH_FUER_REGEX, "label": "Falle 2", "url": "https://wirlernenonline.de/b",
         "priority": 8},
        {"pattern": r"\boer\b", "label": "OER", "url": "https://wirlernenonline.de/oer",
         "priority": 1},
    ]}
    monkeypatch.setattr(config_loader, "load_guide_rules_config", lambda: regeln)
    gq.reset_compiled_cache()
    try:
        beginn = time.monotonic()
        assert gq.find_guide_match(_LANG) is None
        assert gq.find_guide_match(_LANG_A) is None
        assert time.monotonic() - beginn < _HOECHSTENS_S
        assert gq.find_guide_match("Was ist OER?") == ("OER", "https://wirlernenonline.de/oer")
    finally:
        gq.reset_compiled_cache()


def test_policy_regeln_haengen_nicht_an_einem_ungünstigen_muster(monkeypatch):
    from boerdi.domain import policy

    monkeypatch.setattr(policy, "load_policy_config", lambda: {"rules": [
        {"id": "falle", "match": {"message_regex": _REDOS}, "effect": {"block_tools": ["x"]}},
        {"id": "treffer", "match": {"message_regex": "hausaufgabe"},
         "effect": {"block_tools": ["y"]}},
    ]})
    beginn = time.monotonic()
    langsam = policy.assess_policy(_LANG, "P-LER", "I01")
    assert time.monotonic() - beginn < _HOECHSTENS_S
    assert langsam.matched_rules == []
    # Mit Satzzeichen am Ende: ``_REDOS`` passt nur auf reine Wortfolgen.
    assert policy.assess_policy("Meine Hausaufgabe?", "P-LER", "I01").matched_rules == [
        "treffer"]


def test_eine_ungueltige_policy_regex_wird_beim_speichern_abgewiesen():
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe

    doc = {"rules": [
        {"id": "gut", "match": {"message_regex": "hausaufgabe"}, "effect": {}},
        {"id": "kaputt", "match": {"message_regex": "("}, "effect": {}},
    ]}
    with pytest.raises(HTTPException) as err:
        _assert_area_document_safe("01-base/policy", doc, "de")
    assert err.value.status_code == 400
    assert "kaputt" in err.value.detail


def test_speichern_prueft_mit_demselben_motor_wie_die_laufzeit():
    # ``\p{L}`` kennt ``regex``, ``re`` nicht. Vorher wies das Speichern ab, was
    # die Laufzeit (seit B1 ``regex``) problemlos anwendet — und umgekehrt hätte
    # ein Muster, das nur ``re`` versteht, gespeichert und dann nie gegriffen.
    from boerdi.api.config_guards import _assert_area_document_safe

    _assert_area_document_safe("02-domain/guide-rules", {"message_rules": [
        {"pattern": r"\p{L}+schule", "label": "Schule", "url": "https://x"},
    ]}, "de")
    _assert_area_document_safe("01-base/policy", {"rules": [
        {"id": "u", "match": {"message_regex": r"\p{L}+schule"}, "effect": {}},
    ]}, "de")


def test_eine_policy_regel_ohne_text_als_ausdruck_wird_abgewiesen():
    # Review Paket 6: ``str(2024)`` passierte die Prüfung, zur Laufzeit warf
    # ``regex.compile(2024)`` einen TypeError — jeder passende Zug brach ab.
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe

    for wert in (2024, ["hausaufgabe"]):
        with pytest.raises(HTTPException) as err:
            _assert_area_document_safe("01-base/policy", {"rules": [
                {"id": "zahl", "match": {"message_regex": wert}, "effect": {}}]}, "de")
        assert err.value.status_code == 400
        assert "zahl" in err.value.detail


def test_eine_gespeicherte_policy_regel_ohne_text_bricht_keinen_zug_ab(monkeypatch):
    # Was schon in der Datenbank steht (etwa aus einer alten Sicherung), trifft nie.
    from boerdi.domain import policy

    monkeypatch.setattr(policy, "load_policy_config", lambda: {"rules": [
        {"id": "zahl", "match": {"message_regex": 2024}, "effect": {"block_tools": ["x"]}},
        {"id": "treffer", "match": {"message_regex": "hausaufgabe"},
         "effect": {"block_tools": ["y"]}},
    ]})
    entscheid = policy.assess_policy("Meine Hausaufgabe 2024?", "P-LER", "I01")
    assert entscheid.matched_rules == ["treffer"]


def test_policy_regeln_halten_die_zeitgrenze_auch_wenn_regex_zurueckspringt(monkeypatch, caplog):
    # Review Paket 6: ``_REDOS`` löst ``regex`` selbst sofort auf; erst dieser
    # Ausdruck zeigt, dass ``assess_policy`` mit Zeitgrenze sucht.
    from boerdi.domain import policy

    monkeypatch.setattr(policy, "load_policy_config", lambda: {"rules": [
        {"id": "falle", "match": {"message_regex": _REDOS_AUCH_FUER_REGEX},
         "effect": {"block_tools": ["x"]}},
    ]})
    beginn = time.monotonic()
    with caplog.at_level("WARNING", logger="boerdi.domain.regel_regex"):
        entscheid = policy.assess_policy(_LANG_A, "P-LER", "I01")
    assert time.monotonic() - beginn < _HOECHSTENS_S
    assert entscheid.matched_rules == []
    assert "Zeitgrenze" in caplog.text

