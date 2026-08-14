"""Die Naht zwischen Muster-Maschine und Werkzeug-Auswahl (F-neu, 2026-08-10).

Die Bestandstests in ``test_response_tool_selection.py`` bauen ``pattern_output``
**von Hand**. Im Betrieb baut es ``phase3_modulate`` — und das schreibt
``"tools": list(pattern.tools)`` BEDINGUNGSLOS, weil ``PatternDef.tools`` ein
``default_factory=list`` hat. Der Schlüssel ist damit IMMER da, auch wenn im
Seed kein ``tools:`` steht.

Gemessen 2026-08-10 an derselben Muster-Definition (``sources: [mcp]``, kein
``tools:``):

* über ``phase3_modulate`` (Betriebspfad): **0** MCP-Werkzeuge
* als handgebautes Dict (Bestandstests): **23** Werkzeuge, der ganze Katalog

Was daraus folgt und kein Bestandstest zeigen konnte:

1. Der Zweig ``tools == []`` ist NICHT tot — er trägt 8 der 17 Muster. Der
   ALT-Kommentar „Pattern explicitly set tools=[]" beschreibt eine Handlung,
   die kein einziges Muster ausführt; die acht kommen durch WEGLASSEN dorthin.
2. Unerreichbar sind statt dessen die beiden Zweige darunter: ``has_mcp_source``
   (ganzer Katalog) und der Rückfall (``search_wlo_collections`` +
   ``search_wlo_topic_pages``).
3. Damit ist die Plan-Sorge gegenstandslos: kein Muster bekommt still
   Such-Werkzeuge, und M15 kann seine eigene Regel „KEIN MCP-Tool aufrufen"
   gar nicht verletzen.

Dieselbe Ursache wie bei den LiteLLM-Antwortformen (P11) und ``_export_non_empty``
(E2): die Attrappe war nach dem Code gebaut, nicht nach der Wirklichkeit.
Deshalb fährt diese Datei ausschliesslich über ``phase3_modulate``.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from boerdi.domain.pattern_engine import PatternDef, phase3_modulate
from boerdi.services import response_tool_selection as rts

_PATTERN_DIR = pathlib.Path(__file__).resolve().parents[1] / "seeds" / "03-patterns"


def _modulate(**felder) -> dict:
    """``pattern_output`` so, wie der Betrieb es baut — nicht von Hand."""
    return phase3_modulate(
        PatternDef(id="MXX", label="Test", priority=100, **felder),
        signals=[], device="desktop", entities={}, persona_id="P-AND",
    )


def _seed_frontmatter() -> list[dict]:
    return [
        yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1]) or {}
        for p in sorted(_PATTERN_DIR.glob("*.md"))
    ]


@pytest.fixture(autouse=True)
def _ohne_select_top_cards(monkeypatch):
    # Isoliert die Basis-Auswahl; select_top_cards hängt unabhängig vom Zweig an.
    monkeypatch.setenv("CHAT_DISABLE_SELECT_TOP_CARDS", "1")


class TestNahtform:
    """Was ``phase3_modulate`` an die Werkzeug-Auswahl übergibt."""

    def test_tools_schluessel_ist_immer_da(self):
        # Trägt die ganze Datei: ohne diese Zusicherung wären die beiden
        # unteren Zweige erreichbar und alles hier hinfällig.
        assert _modulate() == {**_modulate(), "tools": []}
        assert "tools" in _modulate()

    def test_mcp_zweig_ist_unerreichbar(self):
        # Der Code verspricht hier den ganzen Katalog (23 Werkzeuge).
        aktiv, *_ = rts._select_active_tools(
            {}, _modulate(sources=["mcp"]), None, None, False, False,
        )
        assert aktiv == []

    def test_rueckfall_zweig_ist_unerreichbar(self):
        # Der Code verspricht hier search_wlo_collections + search_wlo_topic_pages.
        aktiv, *_ = rts._select_active_tools(
            {}, _modulate(sources=["rag"]), None, None, False, False,
        )
        assert aktiv == []

    def test_genannte_werkzeuge_kommen_weiterhin_an(self):
        # Gegenprobe: der lebende Zweig funktioniert unverändert.
        aktiv, *_ = rts._select_active_tools(
            {}, _modulate(tools=["search_wlo_content"]), None, None, False, False,
        )
        assert "search_wlo_content" in [t["function"]["name"] for t in aktiv]


class TestSourcesVorgabe:
    """``PatternDef.sources`` hat die Vorgabe ``["mcp"]`` — „nicht gesetzt" ist
    im Betrieb ununterscheidbar von „ausdrücklich mcp". Deshalb kann eine
    Laufzeit-Warnung „mcp genannt, aber keine Werkzeuge" nicht funktionieren:
    sie träfe fünf ausgelieferte Muster, die nie eine Quelle gewählt haben."""

    def test_fehlender_schluessel_wird_zu_mcp(self):
        assert _modulate()["sources"] == ["mcp"]

    def test_fuenf_seed_muster_erben_die_vorgabe(self):
        ohne = [
            fm.get("id") for fm in _seed_frontmatter() if not fm.get("sources")
        ]
        assert ohne == ["M01", "M02", "M03", "M13", "M14"]

    def test_vorgabe_kostet_kein_rag(self):
        # Entwarnung: dieselbe Vorgabe schaltet auch ``_rag_allowed_for_pattern``
        # ab. Das bleibt folgenlos, weil genau diese fünf Muster keine
        # ``rag_areas`` deklarieren — es gäbe ohnehin nichts abzufragen.
        ohne_quelle = [fm for fm in _seed_frontmatter() if not fm.get("sources")]
        assert all(not fm.get("rag_areas") for fm in ohne_quelle)


class TestSeedWaechter:
    """Der Fall, den die Messung als echte Gefahr übrig lässt: wer ``mcp``
    AUSDRÜCKLICH als Quelle einträgt, will suchen — und bekommt ohne
    ``tools:`` nichts. Am Seed ist das prüfbar, zur Laufzeit nicht (siehe
    ``TestSourcesVorgabe``). Muster aus dem Studio deckt dieser Wächter
    NICHT ab; dafür müsste ``sources`` auf ``None`` umgestellt werden."""

    def test_wer_mcp_nennt_nennt_auch_werkzeuge(self):
        stumm = [
            fm.get("id") for fm in _seed_frontmatter()
            if "mcp" in (fm.get("sources") or []) and not fm.get("tools")
        ]
        assert stumm == [], (
            f"Muster {stumm} nennen die Quelle mcp, aber keine Werkzeuge — "
            "sie bekommen im Betrieb KEIN einziges MCP-Werkzeug angeboten."
        )


class TestGegenrichtung:
    """Die Gegenrichtung zu ``TestSeedWaechter`` (A-Kuration, 2026-08-10).

    Jener prüft „wer mcp nennt, nennt auch Werkzeuge". Dieser prüft, was dabei
    unbemerkt bleiben kann: **ein Werkzeug im Katalog, das kein Muster nennt.**

    Das ist kein theoretischer Fall. Gemessen 2026-08-10 traf es **16 von 36**
    Katalog-Werkzeugen — darunter ALLE VIERZEHN kuratierenden. Sie waren gebaut,
    getestet, hinter dem Zugangsblock-Tor sauber verdrahtet — und trotzdem für
    das Modell unerreichbar, weil ``_select_active_tools`` nur den namentlichen
    Zweig lebend hat: **was kein Muster nennt, wird nie angeboten.**

    Die Ausnahmen sind einzeln begründet, nicht pauschal. Wer ein Werkzeug in
    den Katalog legt, muss es entweder einem Muster geben oder hier eintragen,
    warum nicht.
    """

    # Betriebs-Sonden. Sie beantworten „läuft der Server / bin ich angemeldet",
    # ändern nichts und tragen zu keiner Nutzerfrage bei. Ein Muster, das sie
    # nennt, lüde das Modell ein, den Zug mit einer Diagnose zu verbringen.
    NUR_BETRIEB = {"wlo_health_check"}

    # Bewusst stillgelegt (Nutzer-Entscheid 2026-08-13). `search_skill` sucht
    # Anleitungen im GESAMTBESTAND; freigegeben werden sie aber je Sammlung.
    # Gemessen am selben Tag: mit der nodeId einer Fachsammlung liefert es
    # nichts — die Anleitungen liegen im Arbeitsbereich, die Sammlung führt nur
    # die Freigabeliste. Und es sagt dem Modell, das Nichts sei normal. Der Weg
    # führt deshalb ausschliesslich über `get_skill_registry` + `get_skill`.
    # Die Definition bleibt im Katalog (der MCP-Server hat das Werkzeug),
    # `agent_tools.AUS_DEM_KATALOG` hält sie aus jedem Lauf heraus.
    STILLGELEGT = {"search_skill"}

    def test_kein_katalog_werkzeug_ohne_muster(self):
        from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
        from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

        katalog = {
            t["function"]["name"]
            for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)
        }
        genannt: set[str] = set()
        for fm in _seed_frontmatter():
            genannt |= set(fm.get("tools") or ())

        verwaist = sorted(katalog - genannt - self.NUR_BETRIEB - self.STILLGELEGT)
        assert verwaist == [], (
            f"{len(verwaist)} Katalog-Werkzeuge nennt kein einziges Muster: "
            f"{verwaist}. Sie werden dem Modell nie angeboten — der namentliche "
            "Zweig in `_select_active_tools` ist der einzige lebende."
        )

    def test_die_ausnahmeliste_bleibt_ehrlich(self):
        """Eine Ausnahme für ein Werkzeug, das es nicht mehr gibt, verdeckt beim
        nächsten Umbau eine echte Lücke."""
        from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS

        katalog = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert self.NUR_BETRIEB <= katalog


class TestKurationskatalogErreichbar:
    """Der Nachweis, dass die Scheibe wirkt — über den ECHTEN Seed und den
    ECHTEN Betriebspfad, nicht über ein handgebautes ``pattern_output``.

    Genau diese Unterscheidung hat F-neu gelehrt: ein von Hand gebautes Dict
    sah 23 Werkzeuge, wo der Betrieb 0 lieferte.
    """

    def _m18(self) -> dict:
        fm = next(f for f in _seed_frontmatter() if f.get("id") == "M18")
        return phase3_modulate(
            PatternDef(**{k: v for k, v in fm.items()
                          if k in PatternDef.model_fields}),
            signals=[], device="desktop", entities={}, persona_id="P-AND",
        )

    def test_mit_zugangsblock_sind_alle_vierzehn_da(self, monkeypatch):
        from boerdi.domain.write_confirm import CURATION_TOOLS
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)

        aktiv, *_ = rts._select_active_tools(
            {}, self._m18(), None, None, False, False, pattern_label="M18",
        )
        namen = {t["function"]["name"] for t in aktiv}
        assert CURATION_TOOLS <= namen, (
            f"fehlend: {sorted(CURATION_TOOLS - namen)}"
        )

    def test_ohne_zugangsblock_ist_keins_dabei(self, monkeypatch):
        from boerdi.domain.write_confirm import CURATION_TOOLS
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)

        aktiv, *_ = rts._select_active_tools(
            {}, self._m18(), None, None, False, False, pattern_label="M18",
        )
        namen = {t["function"]["name"] for t in aktiv}
        assert not (CURATION_TOOLS & namen)
        # Die lesenden Helfer bleiben — ohne sie könnte das Muster nicht einmal
        # sagen, WORÜBER es gerade nicht schreiben kann.
        assert "get_node_details" in namen

    def test_und_genau_dann_meldet_die_e3_warnung(self, monkeypatch):
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        assert rts.curation_blocked_by_mode(self._m18())
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        assert not rts.curation_blocked_by_mode(self._m18())


class TestVierFaehigkeitenErreichbar:
    """Die vier Vorhaben aus der Use-Case-Liste, je über den ECHTEN Seed und den
    ECHTEN Betriebspfad geprüft (H5–H8).

    Der Test fragt nicht „steht das Werkzeug im Katalog" — das tut der Wächter
    oben. Er fragt: **kommt es beim Modell an, wenn dieses Muster gewinnt.**
    """

    def _aktiv(self, pattern_id: str, classification: dict | None = None) -> set[str]:
        fm = next(f for f in _seed_frontmatter() if f.get("id") == pattern_id)
        po = phase3_modulate(
            PatternDef(**{k: v for k, v in fm.items() if k in PatternDef.model_fields}),
            signals=[], device="desktop", entities={}, persona_id="P-AND",
        )
        aktiv, *_ = rts._select_active_tools(
            classification or {}, po, None, None, False, False, pattern_label=pattern_id,
        )
        return {t["function"]["name"] for t in aktiv}

    def test_qualitaetssicherung_kann_soll_gegen_ist_halten(self, monkeypatch):
        """Die Kernfunktion von M19: der Kompendiumstext ist das Soll, die
        Inhaltsliste das Ist. Fehlt eines von beiden, ist kein Abgleich möglich
        — dann bliebe nur eine Aufzählung."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        namen = self._aktiv("M19")
        assert {"get_compendium_text", "get_collection_contents"} <= namen
        assert "get_collection_stats" in namen
        # Lesend: QS ändert nichts, auch nicht mit Zugangsblock.
        from boerdi.domain.write_confirm import CURATION_TOOLS
        assert not (CURATION_TOOLS & namen)

    def test_erschliessung_hat_den_ganzen_weg(self, monkeypatch):
        """M20 führt von einer fremden Adresse bis in eine Sammlung. Fehlt ein
        Glied, bricht der Weg an einer Stelle ab, an der die Person schon
        Arbeit hineingesteckt hat."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        namen = self._aktiv("M20")
        assert "get_url_text" in namen                       # Text holen
        assert {"search_wlo_content", "search_wlo_all"} <= namen  # Dublette
        assert "lookup_wlo_vocabulary" in namen              # Metadaten belegen
        assert {"wlo_create_content", "wlo_add_to_collection"} <= namen

    def test_erschliessung_bleibt_ohne_block_lesend_brauchbar(self, monkeypatch):
        """Lesen, Prüfen und Vorschlagen brauchen kein Konto — nur das Ablegen.
        Das Muster muss anonym so weit kommen, dass es das SAGEN kann."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        namen = self._aktiv("M20")
        assert {"get_url_text", "search_wlo_content", "lookup_wlo_vocabulary"} <= namen
        assert "wlo_create_content" not in namen

    def test_ki_erzeugung_kann_gegenpruefen(self, monkeypatch):
        """Nutzer-Vorgabe: Wikipedia als Gegenprobe bei KI-Erzeugung."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        assert "get_wikipedia_summary" in self._aktiv("M10")

    def test_kuration_kennt_den_eigenen_anmeldestatus(self, monkeypatch):
        """Vor dem Ankündigen einer Änderung ist die Auskunft besser als die
        Vermutung — und erklärt bei authenticated=false, warum alles scheitert."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        assert "wlo_auth_status" in self._aktiv("M18")


class TestMedientypStrip(TestVierFaehigkeitenErreichbar):
    """Der Medientyp-Strip trifft seit den neuen Mustern auch schreibende (R2).

    ``_select_active_tools`` entfernt bei gesetztem ``entities.medientyp`` die
    Sammlungs- und Themenseiten-Suche: bei „nur Videos bitte" will der Nutzer
    Einzelinhalte mit Filter, und Sammlungen lassen sich nicht nach Typ filtern.
    Für Suchmuster ist das richtig.

    Bei einem SCHREIBAUFTRAG stimmt die Voraussetzung nicht mehr. In „Pack das
    Arbeitsblatt in meine Sammlung Optik" — der eigenen Trigger-Phrase von I09 —
    ist „Arbeitsblatt" der GEGENSTAND, nicht der Filter. Gemessen: M18 verlor
    dadurch ``search_wlo_collections`` und konnte die Zielsammlung nicht mehr
    über ihren Titel finden; es blieb ``browse_collection_tree``, das eine
    nodeId oder einen Fachportal-Namen braucht.

    Kein Bestandstest konnte das zeigen: alle übergeben ``{}`` als
    ``classification``, also die eine Achse, in der der Defekt sitzt.
    """

    MIT_TYP = {"entities": {"medientyp": "Arbeitsblatt"}}

    def test_kuration_behaelt_die_sammlungssuche(self, monkeypatch):
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        assert "search_wlo_collections" in self._aktiv("M18", self.MIT_TYP)

    def test_erschliessung_behaelt_die_kombinierte_suche(self, monkeypatch):
        """M20 braucht sie für die Dublettenprüfung vor dem Anlegen."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        assert "search_wlo_all" in self._aktiv("M20", self.MIT_TYP)

    def test_suchmuster_verlieren_sie_weiterhin(self, monkeypatch):
        """Die Gegenprobe. Ohne sie wäre der Fix eine pauschale Abschaltung —
        und das Nutzer-Feedback, das den Strip veranlasst hat, wieder offen."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        namen = self._aktiv("M06", self.MIT_TYP)
        assert not ({"search_wlo_collections", "search_wlo_topic_pages",
                     "search_wlo_all"} & namen)
        assert "search_wlo_content" in namen


class TestKiErzeugungSuchtNicht(TestVierFaehigkeitenErreichbar):
    """M10 erzeugt Text; es sucht nicht (R1).

    Seine ``forbidden_phrases`` nennen „Such-Tool-Calls" und „Hier sind passende
    Sammlungen", seine ``core_rule`` sagt „niemals auf Vorhandenes verweisen,
    niemals Such-CTA". Gemessen am Vorzustand (``sources: [llm]``, kein
    ``tools:``): über ``phase3_modulate`` bekam M10 **null** Werkzeuge — der
    Rückfall-Zweig, der ``search_wlo_collections`` + ``search_wlo_topic_pages``
    verspricht, ist unerreichbar (siehe ``TestNahtform``). Sie mit der
    Skill-Anbindung auszuschreiben hätte sie also nicht bewahrt, sondern neu
    vergeben — samt der beiden Helfer, die ``phase3_modulate`` an jedes
    Suchwerkzeug hängt.
    """

    def test_keine_suchwerkzeuge(self, monkeypatch):
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        suchend = {n for n in self._aktiv("M10") if n.startswith("search_wlo")}
        assert suchend == set(), (
            f"M10 verbietet Such-Tool-Calls, bekommt aber {sorted(suchend)}."
        )

    def test_die_gegenprobe_bleibt(self, monkeypatch):
        """Was M10 sehr wohl braucht: die unabhängige Quelle und die
        Redaktions-Anleitungen."""
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)
        namen = self._aktiv("M10")
        assert {"get_wikipedia_summary", "get_url_text"} <= namen
        assert {"get_skill", "get_skill_registry"} <= namen
        assert "search_skill" not in namen


class TestSkillProzess:
    """Die Prozessänderung bei Skills (H9): eine Anleitung hängt nicht mehr im
    luftleeren Raum, sondern an einer SAMMLUNG, die eine Freigabeliste führt.

    Gemessen am Server 2026-08-10, und dieser Befund entscheidet den Schnitt:

    * ``formatter.ts`` hängt die Registry-Kurzfassung (Titel + nodeId) an jedes
      Sammlungs-Ergebnis und schreibt dazu wörtlich „vollständig mit
      get_skill_registry" — **der Server weist das Modell also auf ein Werkzeug
      hin**. Boten wir es nicht an, wäre das ein Verweis ins Leere.
    * ``call_mcp_tool`` gibt den Rohtext des Servers zurück; kein Parser
      dazwischen. Die Kurzfassung KOMMT also bereits beim Modell an — gefehlt
      hat nur der zweite Schritt.
    * ``server.ts:129`` registriert ``get_skill_registry`` **bedingungslos**:
      es braucht keine Konfiguration, und eine Sammlung ohne Registry sagt das
      schlicht. Genau deshalb ist es baubar, bevor ein Skill existiert.
    """

    def _tools(self, pattern_id: str) -> list[str]:
        fm = next(f for f in _seed_frontmatter() if f.get("id") == pattern_id)
        return list(fm.get("tools") or ())

    @pytest.mark.parametrize("pattern_id", ["M08", "M09", "M10", "M18", "M19", "M20"])
    def test_arbeitende_muster_kommen_an_die_freigabeliste(self, pattern_id):
        assert "get_skill_registry" in self._tools(pattern_id)

    @pytest.mark.parametrize("pattern_id", ["M08", "M09", "M10", "M18", "M19", "M20"])
    def test_und_koennen_die_genannte_anleitung_auch_laden(self, pattern_id):
        """Die Registry nennt nur nodeIds. Ohne ``get_skill`` endet der Weg bei
        einer Liste von Titeln, die niemand öffnen kann."""
        assert "get_skill" in self._tools(pattern_id)

    def test_die_anleitung_ist_fremdinhalt(self):
        """Ein Registry-Dokument ist hochgeladener Text. Der Server schreibt
        seinen Warnsatz hinein — aber IM Text, also fälschbar. Der Rahmen kommt
        von aussen."""
        from boerdi.domain.untrusted_text import FREE_TEXT_TOOLS, frame_untrusted

        assert "get_skill_registry" in FREE_TEXT_TOOLS
        gerahmt = frame_untrusted("get_skill_registry", "Freigegebene Skills …")
        assert "keine Anweisung" in gerahmt

    @pytest.mark.parametrize(
        "pattern_id", ["M08", "M09", "M10", "M18", "M19", "M20"])
    def test_kein_muster_bietet_die_freie_skill_suche_an(self, pattern_id):
        """Es gibt KEINEN zweiten Weg — und das ist die Entscheidung.

        Bis 2026-08-13 stand hier das Gegenteil: `search_skill` als Rückfall,
        wenn die Sammlung keine Registry führt. Die Live-Messung an diesem Tag
        kehrte das um. Mit der nodeId einer Fachsammlung liefert das Werkzeug
        nichts (die Anleitungen liegen im Arbeitsbereich, die Sammlung führt nur
        die Freigabeliste) — und seine Beschreibung sagt dem Modell dann, das
        Nichts sei normal und es solle ohne Anleitung weiterarbeiten, ohne sie
        zu erwähnen. Ein Rückfall, der stumm scheitert, ist schlimmer als kein
        Rückfall: er verdeckt, dass es 28 freigegebene Anleitungen gab.

        Freigegeben wird je Sammlung. Also führt der Weg über die Sammlung.
        """
        assert "search_skill" not in self._tools(pattern_id)

    @pytest.mark.parametrize(
        "datei",
        ["m08-sammlung-drilldown.md", "m09-lernpfad-erstellung.md",
         "m10-ki-inhalt-generierung.md", "m18-kuration.md",
         "m19-qualitaetssicherung.md", "m20-erschliessen.md"],
    )
    def test_jedes_dieser_muster_erklaert_die_reihenfolge(self, datei):
        """Registry IMMER, freie Suche NIE, sonst normal lösen.

        Seit 2026-08-13 ist Schritt 2 eine Verneinung: die freie Katalogsuche
        wurde gestrichen. Geprüft wird deshalb ihre AUSSAGE und nicht mehr nur
        das Vorkommen von `search_skill` — das Wort steht jetzt in der
        Begründung, warum es das Werkzeug nicht mehr gibt, und ein Test darauf
        wäre grün, ohne etwas zu wissen.

        R8 (2026-08-11): der Abschnitt steht sechsmal wortgleich in sechs
        Dateien; ein Einbau-Mechanismus fehlt, weil jeder Musterkörper allein in
        den Prompt geht. Damit ist Drift die eigentliche Gefahr — die Überschrift
        allein zu prüfen ließe eine Kopie unbemerkt ihre Aussage verlieren.
        Geprüft wird deshalb, dass jede Kopie alle DREI Schritte trägt.
        """
        koerper = (_PATTERN_DIR / datei).read_text(encoding="utf-8").split("---", 2)[2]
        assert "## Freigegebene Anleitungen der Redaktion" in koerper
        abschnitt = koerper.split("## Freigegebene Anleitungen der Redaktion")[1]
        for schritt in (
            "get_skill_registry",
            "**immer** geholt",
            "**nicht** frei nach Anleitungen gesucht",
            "normal gelöst",
        ):
            assert schritt in abschnitt, (
                f"{datei}: die Kopie nennt {schritt!r} nicht mehr — der Abschnitt "
                "ist gegenüber den fünf anderen abgedriftet."
            )

    def test_der_prozess_steht_auch_im_musterkoerper(self):
        """Ein Werkzeug in der Liste sagt nur, DASS es gerufen werden darf.
        WANN es gerufen werden soll, steht in der Prosa — sonst bleibt es
        ungenutzt."""
        pfad = _PATTERN_DIR / "m19-qualitaetssicherung.md"
        koerper = pfad.read_text(encoding="utf-8").split("---", 2)[2]
        assert "get_skill_registry" in koerper
        assert "Freigabeliste" in koerper
