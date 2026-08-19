"""Die Sitzungs-Ansage der Gesamtanleitung (``domain/skill_ansagen``).

Eigenes Modul seit der Durchsicht 2026-08-19: ``skill_precedence`` trug drei
Verantwortungen. Die Lade-Ansage bleibt dort — sie liest die Notiz, die dieselbe
Datei schreibt. Diese hier braucht davon nichts.
"""

from __future__ import annotations

from boerdi.domain.skill_ansagen import ANSAGE_KEY, mit_master_ansage


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

    def test_erste_antwort_bekommt_die_ansage(self):
        merker: dict = {}
        aus = mit_master_ansage("Guten Tag!", self.ZEILE, merker)
        assert aus.splitlines()[0] == self.ZEILE
        assert "Guten Tag!" in aus

    def test_spaetere_antworten_bekommen_sie_nicht(self):
        merker: dict = {}
        mit_master_ansage("Guten Tag!", self.ZEILE, merker)
        assert mit_master_ansage("Weiter geht's.", self.ZEILE, merker) == "Weiter geht's."

    def test_die_ansage_wird_in_der_sitzung_vermerkt(self):
        merker: dict = {}
        mit_master_ansage("Guten Tag!", self.ZEILE, merker)
        assert merker[ANSAGE_KEY] is True

    def test_ein_zug_ohne_zaehlerfortschritt_wiederholt_sie_nicht(self):
        """Der Befund, der den Merker gegen den Zugzaehler tauscht.

        Live gemessen 2026-08-19: nach einem Tour-Zug stand die Zeile ein
        zweites Mal im Chat. Der Tour-Knoten beantwortet den Zug selbst und
        kehrt vor ``turn_persist`` zurueck — dort sitzt das ``turn_count + 1``.
        Der Zaehler stand also noch auf 0, und „erster Zug" traf ein zweites Mal
        zu. Dasselbe gilt fuer die Schreib-Abnahme, die den Zaehler bewusst
        stehen laesst. Ein Merker in der Sitzung kennt diesen Fall nicht.
        """
        merker: dict = {}
        mit_master_ansage("Erste Antwort.", self.ZEILE, merker)
        zweite = mit_master_ansage("Nach dem Tour-Zug.", self.ZEILE, merker)
        assert zweite == "Nach dem Tour-Zug."

    def test_die_eigene_kopie_des_modells_wird_entfernt(self):
        """Sonst staende sie im ersten Zug zweimal — und in spaeteren Zuegen
        taucht sie zufaellig auf (gemessen)."""
        merker: dict = {}
        roh = f"{self.ZEILE}\n\nGuten Tag!"
        aus = mit_master_ansage(roh, self.ZEILE, merker)
        assert aus.count(self.ZEILE) == 1
        assert aus.splitlines()[0] == self.ZEILE

    def test_in_spaeteren_zuegen_wird_die_kopie_still_entfernt(self):
        merker = {ANSAGE_KEY: True}
        roh = f"{self.ZEILE}\n\nZur Sache."
        assert mit_master_ansage(roh, self.ZEILE, merker) == "Zur Sache."

    def test_ohne_geladene_anleitung_bleibt_alles_wie_es_war(self):
        # Kein Skill geladen ⇒ keine Zeile ⇒ nichts behaupten, nichts merken.
        merker: dict = {}
        assert mit_master_ansage("Text.", "", merker) == "Text."
        assert merker == {}

    def test_an_eine_leere_antwort_kommt_nichts(self):
        # Gleiche Regel wie ``mit_ladehinweis``/``append_answer_notes``. Der
        # Merker bleibt leer: angesagt wurde nichts, also ist nichts verbraucht.
        merker: dict = {}
        assert mit_master_ansage("", self.ZEILE, merker) == ""
        assert mit_master_ansage("   ", self.ZEILE, merker) == "   "
        assert merker == {}

    def test_ohne_merker_wird_nichts_behauptet(self):
        """Kein Ort zum Merken ⇒ keine Ansage — sonst käme sie in JEDEM Zug.

        Dieselbe Vorsicht wie in ``mit_ladehinweis``: eine Sitzung, deren
        ``entities`` nicht lesbar sind, bekommt lieber keine Ansage als eine
        falsche.
        """
        assert mit_master_ansage("Text.", self.ZEILE, None) == "Text."
        assert mit_master_ansage("Text.", self.ZEILE, "kaputt") == "Text."

    def test_zwei_ansagen_bilden_EINEN_block(self):
        """Durchsicht 2026-08-19: laedt im ersten Zug zusaetzlich ein Zug-Skill,
        standen beide Zeilen mit Leerzeile dazwischen — das las sich wie eine
        Doppelung. Sie sagen Verschiedenes (Zustand vs. Ereignis) und gehoeren
        deshalb zusammen, nicht auseinander.
        """
        merker: dict = {}
        roh = "[ edu-sharing Skill ] Stunde planen - wird geladen\n\nDein Entwurf."
        aus = mit_master_ansage(roh, self.ZEILE, merker)
        zeilen = aus.splitlines()
        assert zeilen[0] == self.ZEILE
        assert zeilen[1].startswith("[ edu-sharing Skill ] Stunde planen")
        assert "" not in zeilen[:2], "keine Leerzeile zwischen den beiden Ansagen"

    def test_vor_gewoehnlichem_text_bleibt_die_leerzeile(self):
        merker: dict = {}
        aus = mit_master_ansage("Guten Tag!", self.ZEILE, merker)
        assert aus.splitlines()[:3] == [self.ZEILE, "", "Guten Tag!"]
