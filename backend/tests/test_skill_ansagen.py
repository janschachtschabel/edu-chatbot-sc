"""Die Sitzungs-Ansage der Gesamtanleitung (``domain/skill_ansagen``).

Eigenes Modul seit der Durchsicht 2026-08-19: ``skill_precedence`` trug drei
Verantwortungen. Die Lade-Ansage bleibt dort — sie liest die Notiz, die dieselbe
Datei schreibt. Diese hier braucht davon nichts.
"""

from __future__ import annotations

from boerdi.domain.skill_ansagen import mit_master_ansage


class TestMasterAnsage:
    """Die Sitzungs-Ansage des Master-Skills (Nutzer-Vorgabe 2026-08-19).

    **Der Befund**, der das ausloest: die Zeile hing am Modell. Ueber drei Zuege
    einer Sitzung gemessen — Zug 1 ja, Zug 2 nein, Zug 3 wieder ja. Damit ist
    sie weder ein verlaessliches Signal „Anleitung aktiv" noch bleibt sie da,
    wo sie hingehoert.

    Dieselbe Lehre wie bei :func:`mit_ladehinweis`: eine Ansage, die das Modell
    umformuliert oder vergisst, ist eine Behauptung. Diese hier entsteht, weil
    der Abruf lief — sie ist ein Beleg.
    """

    ZEILE = "[ edu-sharing Skill ] Chatbot Masterskill - aktiv"

    def test_erster_zug_bekommt_die_ansage(self):
        aus = mit_master_ansage("Guten Tag!", self.ZEILE, 0)
        assert aus.splitlines()[0] == self.ZEILE
        assert "Guten Tag!" in aus

    def test_spaetere_zuege_bekommen_sie_nicht(self):
        assert mit_master_ansage("Weiter geht's.", self.ZEILE, 1) == "Weiter geht's."

    def test_die_eigene_kopie_des_modells_wird_entfernt(self):
        """Sonst staende sie im ersten Zug zweimal — und in spaeteren Zuegen
        taucht sie zufaellig auf (gemessen)."""
        roh = f"{self.ZEILE}\n\nGuten Tag!"
        aus = mit_master_ansage(roh, self.ZEILE, 0)
        assert aus.count(self.ZEILE) == 1
        assert aus.splitlines()[0] == self.ZEILE

    def test_im_spaeteren_zug_wird_die_kopie_still_entfernt(self):
        roh = f"{self.ZEILE}\n\nZur Sache."
        assert mit_master_ansage(roh, self.ZEILE, 3) == "Zur Sache."

    def test_ohne_geladene_anleitung_bleibt_alles_wie_es_war(self):
        # Kein Skill geladen ⇒ keine Zeile ⇒ nichts behaupten.
        assert mit_master_ansage("Text.", "", 0) == "Text."

    def test_an_eine_leere_antwort_kommt_nichts(self):
        # Gleiche Regel wie ``mit_ladehinweis``/``append_answer_notes``.
        assert mit_master_ansage("", self.ZEILE, 0) == ""
        assert mit_master_ansage("   ", self.ZEILE, 0) == "   "

    def test_unsinniger_zaehler_erzeugt_keine_ansage(self):
        assert mit_master_ansage("Text.", self.ZEILE, None) == "Text."
        assert mit_master_ansage("Text.", self.ZEILE, True) == "Text."

    def test_zwei_ansagen_bilden_EINEN_block(self):
        """Durchsicht 2026-08-19: laedt im ersten Zug zusaetzlich ein Zug-Skill,
        standen beide Zeilen mit Leerzeile dazwischen — das las sich wie eine
        Doppelung. Sie sagen Verschiedenes (Zustand vs. Ereignis) und gehoeren
        deshalb zusammen, nicht auseinander.
        """
        roh = "[ edu-sharing Skill ] Stunde planen - wird geladen\n\nDein Entwurf."
        aus = mit_master_ansage(roh, self.ZEILE, 0)
        zeilen = aus.splitlines()
        assert zeilen[0] == self.ZEILE
        assert zeilen[1].startswith("[ edu-sharing Skill ] Stunde planen")
        assert "" not in zeilen[:2], "keine Leerzeile zwischen den beiden Ansagen"

    def test_vor_gewoehnlichem_text_bleibt_die_leerzeile(self):
        aus = mit_master_ansage("Guten Tag!", self.ZEILE, 0)
        assert aus.splitlines()[:3] == [self.ZEILE, "", "Guten Tag!"]
