"""B1–B3: der offene Vorgang eines Zuges („Frame", E2) — reine Domänenlogik.

Diese Tests halten das Verhalten fest, das die B0-Messung als fehlend belegt
hat. Gemessener Ist-Stand (zwei Läufe, identisch): auf „Erstell mir ein
Arbeitsblatt." folgten dreimal wortgleich dieselbe Rückfrage, dann übernahm der
Bot die Ausweich-Floskel als Thema („Arbeitsblatt zum Thema *such du was aus*")
und erzeugte darunter ein Dokument über ein nie genanntes Thema.

Der Frame zählt deshalb, wie oft der Klärer in Folge gefragt hat, OHNE dass der
Nutzer etwas beigesteuert hat — und lässt ihn ab der Grenze nicht mehr wählen.
Die Zählung setzt zurück, sobald ein Slot dazukommt: dann war die Rückfrage
erfolgreich, auch wenn direkt die nächste folgt.
"""

from __future__ import annotations

from boerdi.domain.turn_frame import (
    CLARIFICATION_ATTEMPT_LIMIT,
    CLARIFIER_PATTERN_ID,
    clarification_exhausted,
    clear_frame,
    note_clarification,
    resolve_frame,
)

# ── Zählen ───────────────────────────────────────────────────────────────


class TestNoteClarification:
    def test_erste_rueckfrage_oeffnet_den_vorgang(self):
        ents: dict = {"material_typ": "arbeitsblatt"}
        note_clarification(ents)
        assert ents["_frame"]["attempts"] == 1

    def test_zweite_rueckfrage_ohne_fortschritt_zaehlt_hoch(self):
        ents: dict = {"material_typ": "arbeitsblatt"}
        note_clarification(ents)
        note_clarification(ents)
        assert ents["_frame"]["attempts"] == 2

    def test_neuer_slot_setzt_die_zaehlung_zurueck(self):
        # Der Nutzer hat geliefert — die Rückfrage war erfolgreich, auch wenn
        # sofort die nächste folgt (M03 fragt nach dem WICHTIGSTEN Slot, nie
        # nach zweien gleichzeitig).
        ents: dict = {"material_typ": "arbeitsblatt"}
        note_clarification(ents)
        note_clarification(ents)
        ents["fach"] = "Mathematik"
        note_clarification(ents)
        assert ents["_frame"]["attempts"] == 1

    def test_leere_werte_zaehlen_nicht_als_fortschritt(self):
        # ``merge`` setzt Platzhalter-Themen auf "" statt sie zu entfernen —
        # ein leerer Wert ist kein gelieferter Slot.
        ents: dict = {"material_typ": "arbeitsblatt"}
        note_clarification(ents)
        ents["thema"] = ""
        note_clarification(ents)
        assert ents["_frame"]["attempts"] == 2

    def test_private_marker_zaehlen_nicht_als_fortschritt(self):
        # ``_canvas_topic`` & Co. schreibt die Maschine, nicht der Nutzer.
        ents: dict = {"material_typ": "arbeitsblatt"}
        note_clarification(ents)
        ents["_last_pattern"] = "M03"
        note_clarification(ents)
        assert ents["_frame"]["attempts"] == 2


class TestClearFrame:
    def test_verwirft_den_vorgang(self):
        ents: dict = {}
        note_clarification(ents)
        clear_frame(ents)
        assert "_frame" not in ents

    def test_ohne_vorgang_unschaedlich(self):
        ents: dict = {"thema": "Bruchrechnung"}
        clear_frame(ents)
        assert ents == {"thema": "Bruchrechnung"}


# ── Grenze ───────────────────────────────────────────────────────────────


class TestClarificationExhausted:
    def test_ohne_vorgang_nicht_erschoepft(self):
        assert clarification_exhausted({}) is False

    def test_unterhalb_der_grenze_nicht_erschoepft(self):
        ents: dict = {}
        note_clarification(ents)
        assert clarification_exhausted(ents) is False

    def test_an_der_grenze_erschoepft(self):
        ents: dict = {}
        for _ in range(CLARIFICATION_ATTEMPT_LIMIT):
            note_clarification(ents)
        assert clarification_exhausted(ents) is True

    def test_fremder_inhalt_unter_dem_schluessel_kippt_nicht(self):
        # Der Frame reist in einer JSONB-Spalte mit; alte Sessions können dort
        # etwas anderes stehen haben.
        assert clarification_exhausted({"_frame": "kaputt"}) is False
        assert clarification_exhausted({"_frame": {"attempts": "viele"}}) is False


# ── Auflösung vor der Musterwahl ─────────────────────────────────────────


class TestResolveFrame:
    def _erschoepft(self) -> dict:
        ents: dict = {}
        for _ in range(CLARIFICATION_ATTEMPT_LIMIT):
            note_clarification(ents)
        return ents

    def test_erschoepfter_klaerer_wird_umgeleitet(self):
        assert resolve_frame(self._erschoepft(), CLARIFIER_PATTERN_ID) == "M15"

    def test_nicht_erschoepft_greift_nicht_ein(self):
        ents: dict = {}
        note_clarification(ents)
        assert resolve_frame(ents, CLARIFIER_PATTERN_ID) is None

    def test_anderes_muster_greift_nicht_ein(self):
        # Der Nutzer hat das Thema geliefert und der Klassifikator will jetzt
        # den Erzeuger — der Frame darf das nicht umbiegen.
        assert resolve_frame(self._erschoepft(), "M10") is None

    def test_ohne_hinweis_greift_nicht_ein(self):
        assert resolve_frame(self._erschoepft(), None) is None
