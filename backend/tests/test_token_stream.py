"""``TokenStrom`` (Plan ``2026-10-01-token-streaming``, T6): bindet den
Vorschau-Filter an den Fortschritts-Sink, taktet die Rahmen und misst am Ende,
ob die fertige Antwort zum Gesendeten passt."""

from __future__ import annotations

import logging

from boerdi.obs.progress import TurnProgress
from boerdi.services.token_stream import TokenStrom


class _Uhr:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _strom(takt_s: float = 0.05):
    ereignisse: list[dict] = []
    uhr = _Uhr()
    return TokenStrom(TurnProgress(ereignisse.append), takt_s=takt_s, uhr=uhr), ereignisse, uhr


def _texte(ereignisse: list[dict]) -> list[tuple[str, int]]:
    return [(e["data"]["text"], e["data"]["pos"]) for e in ereignisse if e["kind"] == "text"]


def test_das_erste_stueck_sofort_danach_im_takt():
    strom, ereignisse, uhr = _strom()
    strom.oeffnen(lambda t: t, muster="M04")
    strom("Hal")
    uhr.t = 0.01
    strom("lo ")
    uhr.t = 0.03
    strom("Welt")
    uhr.t = 0.06
    strom("!")
    assert _texte(ereignisse) == [("Hal", 0), ("lo Welt!", 3)]


def test_schliessen_sendet_den_rest_samt_zurueckgehaltenem():
    strom, ereignisse, uhr = _strom()
    strom.oeffnen(lambda t: t, muster="M04")
    strom("Hal")
    uhr.t = 0.01
    strom("lo [off")
    strom.schliessen()
    assert "".join(t for t, _pos in _texte(ereignisse)) == "Hallo [off"
    assert strom.gesendet == "Hallo [off"


def test_ohne_oeffnen_oder_gesperrt_geht_nichts_hinaus():
    strom, ereignisse, _uhr = _strom()
    strom("Hallo")
    strom.schliessen()
    strom.sperren("suchmuster", muster="M05")
    strom("Hallo")
    strom.schliessen()
    assert _texte(ereignisse) == []


def test_abschluss_ohne_drift_wenn_das_ende_nur_anhaengt(caplog):
    strom, _e, uhr = _strom()
    strom.oeffnen(lambda t: t, muster="M04")
    uhr.t = 1.5
    strom("Hallo Welt")
    strom.schliessen()
    with caplog.at_level(logging.INFO):
        kennzahlen = strom.abschluss("Hallo  Welt\n\n_Hinweis: KI-generiert_")
    assert kennzahlen["drift"] is False
    assert (kennzahlen["rahmen"], kennzahlen["zeichen"], kennzahlen["erstes_ms"]) == (1, 10, 1500)
    assert "Token-Strom: muster=M04" in caplog.text


def test_abschluss_meldet_drift_wenn_der_anfang_sich_aendert():
    strom, _e, _uhr = _strom()
    strom.oeffnen(lambda t: t, muster="M05")
    strom("Hier sind passende Videos.")
    strom.schliessen()
    assert strom.abschluss("Für Videos schau in die Suche unten.")["drift"] is True


def test_abschluss_nennt_den_sperrgrund(caplog):
    strom, _e, _uhr = _strom()
    strom.sperren("suchmuster", muster="M05")
    with caplog.at_level(logging.INFO):
        assert strom.abschluss("egal") == {"gesperrt": "suchmuster", "muster": "M05"}
    assert "gesperrt (suchmuster)" in caplog.text


def test_die_vorschau_rechnet_nur_im_takt():
    """Review L4: die Umformung läuft über den ganzen bisherigen Text — je Stück
    gerechnet, kostete sie bei 6 000 Zeichen rund 0,3 s Rechenzeit auf der
    Ereignisschleife. Gerechnet wird höchstens einmal je Takt und am Ende."""
    aufrufe: list[int] = []

    def umformen(text: str) -> str:
        aufrufe.append(len(text))
        return text

    strom, ereignisse, uhr = _strom()
    strom.oeffnen(umformen, muster="M04")
    for _ in range(100):
        uhr.t += 0.01
        strom("abc ")
    strom.schliessen()

    assert len(aufrufe) <= 25
    assert "".join(t for t, _pos in _texte(ereignisse)) == "abc " * 100
