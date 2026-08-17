"""Der Gesprächsverlauf als Prompt-Schicht (H8-3).

Der Verlauf war bisher nur nach **Anzahl** gedeckelt (``history[-10:]``), nicht
nach Größe. Über 490 gespeicherte Nachrichten gemessen: Median 95 Zeichen, p95
3 904, Maximum 8 190 — typisch also leicht, im Randfall aber 10 × 8 190 Zeichen
und damit ein Drittel des Token-Budgets, bevor der Lauf arbeitet.

**Der wichtigste Test dieser Datei ist die Vorfahrt der jüngsten Nachricht.** Die
iterative Nachbearbeitung (M11: „mach den zweiten Punkt kürzer") bezieht sich auf
die *letzte* Antwort. Ein Deckel, der alle Nachrichten gleich behandelt, spart
Token und zerstört genau diesen Fall — deshalb bekommt die jüngste mehr Raum als
die älteren, und weggeworfen wird von vorn.
"""

from __future__ import annotations

from boerdi.domain.history_window import (
    KUERZUNGS_HINWEIS,
    MAX_ZEICHEN_AELTERE,
    MAX_ZEICHEN_GESAMT,
    MAX_ZEICHEN_JUENGSTE,
    verlaufs_fenster,
)


def _n(rolle: str, zeichen: int) -> dict:
    return {"role": rolle, "content": "x" * zeichen}


def _laenge(fenster: list[dict]) -> int:
    return sum(len(m["content"]) for m in fenster)


def test_kurzer_verlauf_bleibt_unberuehrt():
    verlauf = [_n("user", 20), _n("assistant", 300), _n("user", 15)]
    assert verlaufs_fenster(verlauf, max_nachrichten=10) == verlauf


def test_nur_die_letzten_n_nachrichten():
    verlauf = [_n("user", 10) for _ in range(25)]
    assert len(verlaufs_fenster(verlauf, max_nachrichten=10)) == 10


def test_eine_alte_riesenantwort_wird_gekuerzt():
    verlauf = [_n("assistant", 8190), _n("user", 30)]
    fenster = verlaufs_fenster(verlauf, max_nachrichten=10)
    assert len(fenster[0]["content"]) <= MAX_ZEICHEN_AELTERE + len(KUERZUNGS_HINWEIS)
    assert fenster[0]["content"].endswith(KUERZUNGS_HINWEIS)


def test_die_juengste_nachricht_behaelt_mehr_raum():
    """M11 bezieht sich auf die letzte Antwort — sie darf nicht auf denselben
    Stumpf gekürzt werden wie eine drei Züge alte."""
    verlauf = [_n("assistant", 6000), _n("assistant", 6000)]
    fenster = verlaufs_fenster(verlauf, max_nachrichten=10)
    assert len(fenster[-1]["content"]) > len(fenster[0]["content"])
    assert len(fenster[-1]["content"]) <= MAX_ZEICHEN_JUENGSTE + len(KUERZUNGS_HINWEIS)


def test_gesamt_deckel_wirft_von_vorn_weg():
    verlauf = [_n("assistant", MAX_ZEICHEN_AELTERE) for _ in range(20)]
    fenster = verlaufs_fenster(verlauf, max_nachrichten=15)
    assert _laenge(fenster) <= MAX_ZEICHEN_GESAMT
    assert len(fenster) < 15


def test_die_juengste_bleibt_auch_wenn_sie_allein_zu_gross_ist():
    """Sonst käme ein Zug ohne jeden Verlauf heraus — und die Rückfrage
    „und jetzt kürzer" verlöre ihren Gegenstand vollständig."""
    verlauf = [_n("user", 50), _n("assistant", MAX_ZEICHEN_GESAMT * 3)]
    fenster = verlaufs_fenster(verlauf, max_nachrichten=10)
    assert len(fenster) >= 1
    assert fenster[-1]["role"] == "assistant"


def test_fehlender_inhalt_bricht_nicht():
    verlauf = [{"role": "assistant"}, {"role": "user", "content": None}]
    fenster = verlaufs_fenster(verlauf, max_nachrichten=10)
    assert [m["content"] for m in fenster] == ["", ""]


def test_die_quelle_wird_nicht_veraendert():
    """``ctx.history`` gehört dem Zug und wird noch anderswo gelesen (``assess``,
    ``context_greeting``) — das Fenster darf sie nicht in der Hand umschreiben."""
    verlauf = [_n("assistant", 5000)]
    original = verlauf[0]["content"]
    verlaufs_fenster(verlauf, max_nachrichten=10)
    assert verlauf[0]["content"] == original
