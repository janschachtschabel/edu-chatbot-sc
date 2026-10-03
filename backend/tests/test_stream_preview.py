"""Vorschau-Filter für das Token-Streaming (Plan ``2026-10-01-token-streaming``, T4).

``stabiler_teil`` hält zurück, was die Endverarbeitung noch umdeuten könnte;
``VorschauStrom`` formt den Rest mit denselben Funktionen um wie später die
Endverarbeitung und sendet nur, was das schon Gesendete fortsetzt.
"""

from __future__ import annotations

import re

import pytest

from boerdi.domain.stream_preview import VorschauStrom, stabiler_teil

# ── stabiler_teil ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("roh, stabil", [
    ("Hallo Welt", "Hallo Welt"),
    ("Hallo [Lin", "Hallo "),                       # Link-Text noch offen
    ("Hallo [Link]", "Hallo "),                     # kann noch ein Link werden
    ("Hallo [Link](https://x.de", "Hallo "),        # Adresse noch offen
    ("Hallo [Link](https://x.de) und", "Hallo [Link](https://x.de) und"),
    ("Siehe [1] oben", "Siehe [1] oben"),           # Klammer ohne Link
    ("Text\n[ edu-sharing Skill ] Titel", "Text\n"),  # Ansage-Kandidat ohne Zeilenende
    ("Text\n[ edu-sharing Skill ] Titel\nweiter", "Text\n[ edu-sharing Skill ] Titel\nweiter"),
    ("Das ist **wich", "Das ist "),                 # ungepaartes ** im letzten Absatz
    ("Das ist **wichtig** und", "Das ist **wichtig** und"),
    ("Alt **offen\n\nNeu", "Alt **offen\n\nNeu"),   # früherer Absatz zählt nicht
    ("Das ist *", "Das ist "),                      # kann noch ** werden
    # Review M2: Zeilen, die die Endverarbeitung als Ganzes entfernen kann —
    # Aufzählungen nur aus einem Link, Modell-Ansagen „▸ … aktiv“ —, erst mit
    # ihrem Zeilenende (sonst stand „- “ schon da und der Strom staute).
    ("Quellen:\n- [WLO", "Quellen:\n"),
    ("Quellen:\n- Erster Punkt", "Quellen:\n"),
    ("Quellen:\n- Erster Punkt\nweiter", "Quellen:\n- Erster Punkt\nweiter"),
    ("Text\n1. Schritt", "Text\n"),
    ("Text\n1", "Text\n"),                          # kann noch „1. “ werden
    ("Text\n▸ stunde-planen ak", "Text\n"),
    ("*kursiv* am Anfang", "*kursiv* am Anfang"),   # kein Aufzählungszeichen
])
def test_stabiler_teil(roh, stabil):
    assert stabiler_teil(roh) == stabil


# ── VorschauStrom ─────────────────────────────────────────────────────────

def _labels(text: str) -> str:
    """Wie die Endverarbeitung: ``[Label](url)`` → ``Label``."""
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)


def test_sendet_nur_den_stabilen_teil_und_den_rest_am_ende():
    strom = VorschauStrom(lambda t: t)
    assert strom.weiter("Text [of") == "Text "
    assert strom.weiter("fen") == ""
    assert strom.ende() == "[offen"
    assert strom.gesendet == "Text [offen"


def test_formt_mit_der_endverarbeitung_um():
    strom = VorschauStrom(_labels)
    gesendet = "".join(strom.weiter(s) for s in ("Siehe [WLO", "](https://wlo.de", ") dazu."))
    assert gesendet == "Siehe WLO dazu."


def test_ein_vorangestelltes_kommt_zuerst():
    strom = VorschauStrom(lambda t: "ANSAGE\n\n" + t)
    assert strom.weiter("Hal") == "ANSAGE\n\nHal"
    assert strom.weiter("lo") == "lo"


def test_was_das_gesendete_nicht_fortsetzt_wird_nicht_gesendet():
    """Ändert die Umformung schon Gesendetes, wartet der Strom — den Rest richtet
    am Ende ``result`` (Präfix-Regel)."""
    strom = VorschauStrom(lambda t: t.replace("geheim", "") if "Ende" in t else t)
    assert strom.weiter("geheim ") == "geheim "
    assert strom.weiter("Ende") == ""
    assert strom.rueckschritte == 1
    assert strom.gesendet == "geheim "
