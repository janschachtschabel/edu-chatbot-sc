"""Die Anmelde-Rückfrage als Quick-Reply (C5-c2a).

Zwei Chips, zwei **verschiedene Sorten** — und dieser Unterschied ist der Kern
der Scheibe:

* Chip 1 löst eine Handlung **im Browser** aus (das Anmeldefenster). Er trägt
  deshalb bewusst KEINE Beschriftung: die ist Beiwerk der Oberfläche, wird
  nirgends hingeschickt und soll beim Sprachwechsel im Widget sofort mitgehen.
* Chip 2 ist eine **Nachricht, die der Mensch absendet**. Dort IST die
  Beschriftung die Nachricht — sie muss übersetzt sein, sonst schickt eine
  englischsprachige Person einen deutschen Satz ab (Regel aus C1-g2b).

Der Test pinnt beide Sorten getrennt, damit eine spätere Vereinheitlichung
("gib dem Anmelde-Chip doch auch ein Label") auffällt statt durchzurutschen.
"""

from __future__ import annotations

import pytest

from boerdi.domain.auth_qr import AUTH_QR_MARKER, inject_auth_qr
from boerdi.i18n import bot_text


class TestOhneSperre:
    def test_die_liste_bleibt_unveraendert(self):
        vorher = ["Zeig mir mehr", "Anderes Thema"]
        assert inject_auth_qr(vorher, blocked=False, lang="de") == vorher

    def test_leere_liste_bleibt_leer(self):
        assert inject_auth_qr([], blocked=False, lang="de") == []

    def test_none_wird_zur_leeren_liste(self):
        # ``quick_replies`` ist an der Naht ``list | None`` — der Nachbar
        # ``inject_guide_qr`` nimmt das ebenfalls entgegen.
        assert inject_auth_qr(None, blocked=False, lang="de") == []


class TestMitSperre:
    def test_beide_chips_stehen_vorn(self):
        ergebnis = inject_auth_qr(["Zeig mir mehr"], blocked=True, lang="de")
        assert ergebnis[0] == AUTH_QR_MARKER
        assert ergebnis[1] == bot_text("de", "auth.readOnly")

    def test_der_anmelde_chip_traegt_keine_beschriftung(self):
        """Kein ``|``, kein Text — sonst wäre die Beschriftung Backend-Sache."""
        ergebnis = inject_auth_qr([], blocked=True, lang="de")
        assert ergebnis[0] == "__auth__"
        assert "|" not in ergebnis[0]

    def test_der_nur_lesen_chip_ist_die_nachricht_selbst(self):
        """Was auf dem Chip steht, wird abgeschickt — also muss es ein Satz sein."""
        ergebnis = inject_auth_qr([], blocked=True, lang="de")
        assert ergebnis[1] == "Such einfach, ohne Anmeldung"

    def test_auf_englisch_ist_die_nachricht_englisch(self):
        ergebnis = inject_auth_qr([], blocked=True, lang="en")
        assert ergebnis[0] == AUTH_QR_MARKER  # sprachlos, also unverändert
        assert ergebnis[1] == bot_text("en", "auth.readOnly")
        assert ergebnis[1] != bot_text("de", "auth.readOnly")

    def test_bestandschips_ueberleben_soweit_platz_ist(self):
        ergebnis = inject_auth_qr(["A", "B"], blocked=True, lang="de")
        assert ergebnis[2:] == ["A", "B"]


class TestKeineVerdopplung:
    """Zweimal ausgeführt darf nicht zwei Anmelde-Chips ergeben.

    Der Zug läuft über mehrere Stationen; ein zweiter Aufruf ist billiger zu
    verhindern als zu beweisen, dass es ihn nie gibt.
    """

    def test_zweiter_aufruf_fuegt_nichts_hinzu(self):
        einmal = inject_auth_qr(["A"], blocked=True, lang="de")
        zweimal = inject_auth_qr(einmal, blocked=True, lang="de")
        assert zweimal == einmal

    def test_ein_vorhandener_marker_verhindert_den_zweiten(self):
        ergebnis = inject_auth_qr([AUTH_QR_MARKER, "A"], blocked=True, lang="de")
        assert ergebnis.count(AUTH_QR_MARKER) == 1


class TestDeckel:
    def test_die_liste_bleibt_bei_vier(self):
        ergebnis = inject_auth_qr(["A", "B", "C", "D"], blocked=True, lang="de")
        assert len(ergebnis) == 4
        # Die beiden neuen verdrängen die schwächsten (hintersten) —
        # dieselbe Regel wie beim Lotsen-Chip.
        assert ergebnis[2:] == ["A", "B"]

    @pytest.mark.parametrize("deckel", [0, 1, 2])
    def test_ein_engerer_deckel_wird_eingehalten(self, deckel):
        ergebnis = inject_auth_qr(["A"], blocked=True, lang="de", max_qrs=deckel)
        assert len(ergebnis) == deckel
