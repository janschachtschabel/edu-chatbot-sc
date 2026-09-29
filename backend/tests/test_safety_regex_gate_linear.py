"""Regex-Gate — lineare Laufzeit bei denselben Treffern (Befund 2026-09-27).

Drei Muster liefen quadratisch: die beiden PII-Zeilen (``KOPF.*SCHWANZ``) und
die Injection-Zeile ``<\\|.*?\\|>``. Auf einer langen Zeile voller Köpfe las
jeder weitere Kopf den Rest der Zeile neu — gemessen 20.000 Zeichen ≈ 1 s,
hochgerechnet 200.000 ≈ 100 s, synchron in der Event-Loop. Die Chat-Nachricht hat keinen
Deckel und ``/api/chat`` ist anonym: eine Anfrage hielt den ganzen Worker an.

Festgehalten wird zweierlei: die schlimmsten Eingaben bleiben linear, und die
Treffer sind dieselben wie vorher — am Ende sehr langer Nachrichten, an den
Kanten (Zeilenumbruch, Wortgrenze, Reihenfolge) und im Zufallsvergleich gegen
die alten Ausdrücke.
"""

from __future__ import annotations

import asyncio
import random
import re
import time

import pytest

from boerdi.services.safety import regex_gate as rg
from boerdi.services.safety import service as ss

# Die Ausdrücke VOR dem Umbau — die Referenz für „dieselben Treffer".
_PII_VORHER = [
    r"\b(passwort|password|kreditkart|sozialvers|geburtsdatum)\b.*\b(meine?|ist|lautet)\b",
    r"\b(password|credit\s*card|social\s*security|date\s+of\s+birth)\b.*\b(my|is|are)\b",
]
_SONDERZEICHEN_VORHER = r"<\|.*?\|>"

# Nur die Injection-Stufe: kein Moderations-, kein Rechts-LLM.
_NUR_REGEX = {
    "security_level": "regex",
    "presets": {"regex": {"moderation": "never", "legal_classifier": "never",
                          "prompt_injection": True}},
    "escalation": {},
}

_HARMLOS = "wie erkläre ich bruchrechnung in klasse sechs "


def _lang(einheit: str, zeichen: int) -> str:
    return (einheit * (zeichen // len(einheit) + 1))[:zeichen]


def _am_ende(satz: str, fueller: str = _HARMLOS) -> str:
    """``satz`` ganz am Ende einer Nachricht von genau 100.000 Zeichen."""
    return _lang(fueller, 100_000 - len(satz) - 1) + " " + satz


def _sekunden(aufruf) -> float:
    t0 = time.perf_counter()
    aufruf()
    return time.perf_counter() - t0


def _pii(text: str) -> bool:
    return "pii_in_message" in rg.regex_gate(text, []).reasons


def _pii_vorher(text: str) -> bool:
    return any(re.search(p, text.lower()) for p in _PII_VORHER)


def _injection(text: str) -> bool:
    """Dieselbe Schleife wie die Injection-Stufe in ``service.assess_safety``."""
    return any(re.search(p, text.lower()) for p in rg.INJECTION_PATTERNS)


# ── Laufzeit: die schlimmsten Eingaben bleiben linear ───────────────────
# Erst 20.000 Zeichen: quadratisch dauert schon das 0,35–1,3 s. Ein Rückfall
# bricht so nach einer Sekunde ab, statt die Suite minutenlang festzuhalten.

@pytest.mark.parametrize("einheit", [
    "password ", "passwort ", "geburtsdatum ", "credit card ", "date of birth ",
])
def test_pii_worst_case_stays_linear(einheit):
    """Eine Zeile voller PII-Köpfe ohne Schwanz dahinter."""
    kurz, lang = _lang(einheit, 20_000), _lang(einheit, 200_000)
    assert _sekunden(lambda: rg.regex_gate(kurz, [])) < 0.25
    assert _sekunden(lambda: rg.regex_gate(lang, [])) < 1.0


def test_injection_worst_case_stays_linear(monkeypatch):
    """Lauter ``<|`` ohne ``|>`` — durch die echte Injection-Stufe."""
    monkeypatch.setattr(ss, "load_safety_config", lambda: _NUR_REGEX)
    kurz, lang = _lang("<|", 20_000), _lang("<|", 200_000)
    assert _sekunden(lambda: asyncio.run(ss.assess_safety(kurz))) < 0.25
    assert _sekunden(lambda: asyncio.run(ss.assess_safety(lang))) < 1.0


# ── Treffer am Ende langer Nachrichten ──────────────────────────────────

@pytest.mark.parametrize("satz", ["ich will mich umbringen", "I want to kill myself"])
def test_crisis_at_the_very_end_of_a_100k_message(satz):
    d = rg.regex_gate(_am_ende(satz), [])
    assert d.risk_level == "high"
    assert d.enforced_pattern == "M01"


@pytest.mark.parametrize("satz", ["ich werde dich umbringen", "I will stab you"])
def test_threat_at_the_very_end_of_a_100k_message(satz):
    d = rg.regex_gate(_am_ende(satz), [])
    assert d.risk_level == "high"
    assert d.enforced_pattern == "M02"


def test_crisis_still_beats_threat_and_pii_standing_far_ahead():
    """Vorrang Krise > Drohung > PII (``regex_gate``-Docstring), auf 100.000 Zeichen."""
    fueller = "mein passwort ist geheim. ich werde dich umbringen. "
    d = rg.regex_gate(_am_ende("ich will mich umbringen", fueller), [])
    assert d.enforced_pattern == "M01"
    assert d.reasons == ["crisis_signal_detected"]


def test_threat_still_beats_pii_standing_far_ahead():
    d = rg.regex_gate(_am_ende("ich werde dich umbringen", "mein passwort ist geheim. "), [])
    assert d.enforced_pattern == "M02"
    assert d.reasons == ["threat_signal_detected"]


@pytest.mark.parametrize("text", [
    _am_ende("mein passwort ist geheim"),
    # Die Lücke ``.*`` ist unbeschränkt: ein Deckel wie ``{0,500}`` verlöre das.
    # Ganze Wiederholungen statt ``_lang`` — ein abgeschnittenes Wort klebte
    # sonst am Schwanz („weiteist") und nähme ihm die Wortgrenze.
    "mein passwort " + "und so weiter " * 7_000 + "ist geheim",
    "password " * 11_000 + "is hunter2",
    ("password " * 20 + "\n") * 500 + "my password is hunter2",
], ids=["am-ende", "schwanz-100k-hinter-dem-kopf", "lauter-koepfe-dann-schwanz",
        "letzte-von-500-zeilen"])
def test_pii_far_behind_or_many_lines_down_still_counts(text):
    d = rg.regex_gate(text, [])
    assert d.risk_level == "medium"
    assert "pii_in_message" in d.reasons


def test_injection_stage_flags_a_special_token_at_the_end_of_a_long_message(monkeypatch):
    monkeypatch.setattr(ss, "load_safety_config", lambda: _NUR_REGEX)
    d = asyncio.run(ss.assess_safety(_am_ende("<|im_start|>system")))
    assert "possible_prompt_injection" in d.reasons
    assert d.risk_level == "medium"


def test_special_token_closing_far_behind_many_openers_still_counts():
    assert _injection(_lang("<|", 100_000) + "|>")


# ── Kanten: dieselben Urteile wie die alten Ausdrücke ───────────────────

@pytest.mark.parametrize("text,erwartet", [
    ("mein passwort ist geheim", True),
    ("my password is hunter2", True),
    ("password\nis hunter2", False),       # ``.`` springt nicht über den Umbruch
    ("is my password", False),             # Schwanz vor dem Kopf
    ("passwordis x", False),               # kein Wortende hinter dem Kopf
    ("credit\ncard is 1234", True),        # Kopf über den Umbruch, Schwanz auf seiner Endzeile
    # Der erste Kopf der Zeile scheitert, ein späterer über den Umbruch trifft.
    ("password x date of\nbirth is 1990", True),
    ("date of\nbirth\nis 1990", False),    # Schwanz eine Zeile hinter dem Kopfende
])
def test_pii_edges(text, erwartet):
    assert _pii(text) is erwartet
    assert _pii_vorher(text) is erwartet  # … und so urteilte schon der alte Ausdruck


@pytest.mark.parametrize("text,erwartet", [
    ("<|im_start|>system", True),
    ("<||>", True),
    ("<|>", False),            # das ``|`` zählt nicht für beide Seiten
    ("<|\n|>", False),         # ``.`` springt nicht über den Umbruch
    ("|> <|", False),          # falsche Reihenfolge
    ("<| <| <| x |>", True),
    ("<| x\n<| y |>", True),   # erste Zeile ohne Schluss, zweite mit
])
def test_special_token_edges(text, erwartet):
    assert _injection(text) is erwartet
    assert (re.search(_SONDERZEICHEN_VORHER, text) is not None) is erwartet


# ── Zufallsvergleich gegen die alten Ausdrücke (fester Seed) ────────────
# Die Bausteine lösen keine Krise und keine Drohung aus (die verdeckten sonst
# das PII-Urteil) und keine andere Injection-Zeile — verglichen wird genau
# der umgebaute Teil.

_PII_BAUSTEINE = [
    "password", "passwort", "Password", "passwords", "kreditkart", "sozialvers",
    "geburtsdatum", "credit", "card", "social", "security", "date", "of", "birth",
    "mein", "meine", "ist", "IST", "lautet", "my", "is", "are", "x",
]
_PII_TRENNER = [" ", " ", " ", "  ", "\n", "-", ". ", "\t", ""]
_TOKEN_BAUSTEINE = ["<|", "|>", "<", "|", ">", "x", "<||>", "<|>", "|<"]
_TOKEN_TRENNER = ["", "", " ", "\n"]


def _zufallstext(rng: random.Random, bausteine: list[str], trenner: list[str]) -> str:
    teile: list[str] = []
    for _ in range(rng.randint(1, 14)):
        teile += [rng.choice(bausteine), rng.choice(trenner)]
    return "".join(teile)


def test_pii_verdicts_match_the_old_expressions_on_random_text():
    rng = random.Random(20260927)
    for _ in range(4000):
        text = _zufallstext(rng, _PII_BAUSTEINE, _PII_TRENNER)
        assert _pii(text) is _pii_vorher(text), repr(text)


def test_special_token_verdicts_match_the_old_expression_on_random_text():
    rng = random.Random(20260927)
    for _ in range(4000):
        text = _zufallstext(rng, _TOKEN_BAUSTEINE, _TOKEN_TRENNER)
        vorher = re.search(_SONDERZEICHEN_VORHER, text) is not None
        assert _injection(text) is vorher, repr(text)
