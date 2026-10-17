"""Was die Einbettung ANZEIGT und ERLAUBT (Paket O).

Die Aussagen hier sind gegen das FRONTEND gemessen, nicht geraten — siehe den
Modulkopf von ``domain/host_capabilities``. Der wichtigste Test ist deshalb
``test_kein_satz_ueber_fehlende_kacheln``: er haelt eine Behauptung fern, die
der Entwurf zunaechst enthielt und die das Widget widerlegt.
"""

from boerdi.domain import host_capabilities as hc


class TestPromptBlock:
    def test_vorgabe_erzeugt_keinen_block(self):
        # Ein Satz ueber den Normalfall kostet in JEDEM Zug Token und sagt nichts.
        assert hc.prompt_block() == ""
        assert hc.prompt_block(inline_result_grouping=True, tool_mode=hc.VOLL) == ""

    def test_ohne_gliederung_verlangt_eigene_struktur(self):
        block = hc.prompt_block(inline_result_grouping=False)
        assert block.startswith(hc.KOPF)
        assert "gruppiert" in block.lower()

    def test_nur_lesend_sagt_es_ausdruecklich(self):
        block = hc.prompt_block(tool_mode=hc.LESEND)
        assert "nichts" in block.lower() and "aendern" in block.lower()

    def test_kuratierend_nennt_die_zweistufigkeit(self):
        block = hc.prompt_block(tool_mode=hc.KURATIEREND)
        assert "Vorschau" in block

    def test_unbekannter_modus_erzeugt_keinen_satz(self):
        # Ein Tippfehler darf nicht heimlich Rechte beschreiben, die niemand hat.
        assert hc.prompt_block(tool_mode="lesend") == ""

    def test_beide_abweichungen_stehen_unter_einer_ueberschrift(self):
        block = hc.prompt_block(inline_result_grouping=False, tool_mode=hc.LESEND)
        assert block.count(hc.KOPF) == 1
        assert len(block.splitlines()) == 3

    def test_kein_satz_ueber_fehlende_kacheln(self):
        # Gemessen am Widget (chat-shell.component.html): die beiden Zweige
        # ``!cardsVisible`` und ``cardsVisible`` sind vollstaendig und schliessen
        # einander aus — Treffer werden IMMER gezeigt, entweder als Kacheln mit
        # Vorschaubild oder als Textlinks in Boxen. Ein Satz „diese Anwendung
        # zeigt keine Kacheln" waere also falsch, egal wie die Einbettung steht.
        alle = " ".join(
            hc.prompt_block(inline_result_grouping=g, tool_mode=m)
            for g in (None, True, False)
            for m in (None, hc.LESEND, hc.KURATIEREND, hc.VOLL)
        ).lower()
        assert "keine ergebnis-kacheln" not in alle
        assert "keine kacheln" not in alle


class TestErlaubt:
    def test_ohne_modus_ist_alles_erlaubt(self):
        assert hc.erlaubt("wlo_create_collection", None)
        assert hc.erlaubt("get_wikipedia_summary", "")
        assert hc.erlaubt("wlo_create_collection", hc.VOLL)

    def test_lesend_nimmt_die_schreibenden_heraus(self):
        assert not hc.erlaubt("wlo_create_collection", hc.LESEND)
        assert not hc.erlaubt("wlo_add_to_collection", hc.LESEND)
        assert hc.erlaubt("search_wlo_all", hc.LESEND)
        assert hc.erlaubt("get_compendium_text", hc.LESEND)

    def test_kuratierend_erlaubt_schreiben_aber_nicht_den_blick_nach_draussen(self):
        assert hc.erlaubt("wlo_add_to_collection", hc.KURATIEREND)
        assert hc.erlaubt("search_wlo_all", hc.KURATIEREND)
        assert not hc.erlaubt("get_wikipedia_summary", hc.KURATIEREND)
        assert not hc.erlaubt("get_url_text", hc.KURATIEREND)

    def test_unbekannter_modus_sperrt_nichts(self):
        # Lieber der Bestand als eine stille Teilsperre aus einem Tippfehler.
        assert hc.erlaubt("wlo_create_collection", "readonly")


class TestLesendeWloWerkzeuge:
    """Befund aus der Durchsicht (2026-08-18): das Praefix ``wlo_`` trennt NICHT
    sauber Schreiben von Lesen — zwei Bestandswerkzeuge tragen es, ohne etwas zu
    aendern. Ohne Ausnahme faellt in ``read-only`` die Frage „ist die Person
    angemeldet?" weg, und das Modell muesste raten.
    """

    def test_der_zustand_darf_auch_lesend_erfragt_werden(self):
        assert hc.erlaubt("wlo_auth_status", hc.LESEND)
        assert hc.erlaubt("wlo_health_check", hc.LESEND)

    def test_die_schreibenden_bleiben_draussen(self):
        assert not hc.erlaubt("wlo_create_content", hc.LESEND)
        assert not hc.erlaubt("wlo_add_to_collection", hc.LESEND)
        assert not hc.erlaubt("wlo_decide_suggestion", hc.LESEND)

    def test_die_ausnahmeliste_deckt_sich_mit_dem_katalog(self):
        """Waechter gegen das Auseinanderlaufen: jeder Name der Ausnahmeliste
        muss ein LESENDES Werkzeug sein, keines aus dem Kuratier-Katalog."""
        from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
        from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

        lesend = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        schreibend = {t["function"]["name"] for t in CURATION_TOOL_DEFINITIONS}
        # Paket 11, C-5: ``wlo_list_suggestions`` steht im Kuratier-Katalog, weil es eine
        # Anmeldung braucht — es liest aber nur (Server: ``readOnlyHint: true``).
        nur_lesend_im_kuratier_katalog = {"wlo_list_suggestions"}
        assert hc.LESENDE_WLO_WERKZEUGE <= lesend | nur_lesend_im_kuratier_katalog
        assert not (hc.LESENDE_WLO_WERKZEUGE & (schreibend - nur_lesend_im_kuratier_katalog))

    def test_kein_schreibendes_werkzeug_entkommt_dem_praefix(self):
        """Die andere Richtung: erfuellt der Bestand die Annahme ueberhaupt?
        Ein kuratierendes Werkzeug ohne ``wlo_`` waere in ``read-only`` erlaubt
        — und das waere ein Loch, keine Unbequemlichkeit."""
        from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

        for t in CURATION_TOOL_DEFINITIONS:
            name = t["function"]["name"]
            if name == "wlo_list_suggestions":  # liest nur (C-5), siehe oben
                continue
            assert not hc.erlaubt(name, hc.LESEND), name


def test_fremde_mcp_server_sind_der_blick_nach_draussen():
    """Paket 11 (E): „kuratierend“ heißt WLO ohne Blick nach außen — ein fremder Server ist außen.
    Lesend bleibt er erlaubt (angeboten werden ohnehin nur lesende fremde Werkzeuge)."""
    from boerdi.domain.host_capabilities import erlaubt

    assert erlaubt("wikidata__search_entities", "read-only")
    assert erlaubt("wikidata__search_entities", "full")
    assert not erlaubt("wikidata__search_entities", "curate")


def test_vorschlaege_auflisten_ist_lesend():
    """Paket 11, C-5: ``wlo_list_suggestions`` ändert nichts (Server: ``readOnlyHint: true``) — im
    Lesemodus einer Einbettung erlaubt, trotz Präfix ``wlo_``."""
    from boerdi.domain.host_capabilities import erlaubt

    assert erlaubt("wlo_list_suggestions", "read-only")
    assert not erlaubt("wlo_suggest_metadata", "read-only")
