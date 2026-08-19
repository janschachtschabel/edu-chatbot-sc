"""Die Wissensdatenbank in der Agent-Schleife (Paket P).

**Der Befund, der das Paket ausloest** (gemessen 2026-08-18): ``query_knowledge``
wird ausschliesslich in ``response_tool_selection._select_active_tools`` gebaut
und in ``tool_loop`` bedient — beides Muster-Weg. Die Agent-Schleife hatte weder
den Vorabruf der ``mode: always``-Bereiche noch das Werkzeug. Im Agent-Modus gab
es also **gar kein** internes Wissen; jede Frage nach WLO, OER oder edu-sharing
lief ins Modellgedaechtnis.

Nutzer-Vorgabe zur Behebung: „immer alle Wissensbereiche, ausser man spricht
explizit einzelne an oder schliesst sie aus."
"""

from __future__ import annotations

import pytest

from boerdi.services import agent_knowledge as ak

_CONFIG = {
    "WirLernenOnline": {"mode": "always", "description": "Die Bildungsplattform."},
    "OER-Wissen": {"mode": "always", "description": "Lizenzen und freie Inhalte."},
    "FAQ": {"mode": "on-demand"},
}

#: Derselbe Bestand, aber ein Bereich ist fuer die Schleife abgewaehlt (Q).
_CONFIG_MIT_ABWAHL = {
    "WirLernenOnline": {"mode": "always", "description": "Die Bildungsplattform."},
    "OER-Wissen": {"mode": "always", "agent": False},
    "FAQ": {"mode": "on-demand", "agent": True},
}


class TestWerkzeug:
    def test_ohne_bereiche_gibt_es_kein_werkzeug(self):
        assert ak.wissen_werkzeug({}) is None

    def test_alle_bereiche_stehen_im_enum(self):
        w = ak.wissen_werkzeug(_CONFIG)
        assert w is not None
        eigenschaften = w["function"]["parameters"]["properties"]
        for feld in ("bereiche", "ohne"):
            assert eigenschaften[feld]["items"]["enum"] == list(_CONFIG)

    def test_der_modus_der_bereiche_spielt_keine_rolle(self):
        """Im Muster-Weg trennt ``mode`` Vorabruf von Abruf-auf-Zuruf. Hier gibt
        es keinen Vorabruf — also auch keinen Grund, einen Bereich zu verstecken."""
        w = ak.wissen_werkzeug(_CONFIG)
        assert "FAQ" in w["function"]["parameters"]["properties"]["bereiche"]["items"]["enum"]

    def test_die_beschreibungen_stehen_in_der_werkzeug_beschreibung(self):
        # Ohne sie muesste das Modell aus dem Bereichsnamen raten, was drinsteht.
        text = ak.wissen_werkzeug(_CONFIG)["function"]["description"]
        assert "Die Bildungsplattform." in text
        assert "Lizenzen und freie Inhalte." in text

    def test_nur_die_frage_ist_pflicht(self):
        w = ak.wissen_werkzeug(_CONFIG)
        assert w["function"]["parameters"]["required"] == ["frage"]


class TestBereicheAufloesen:
    def test_ohne_angabe_alle(self):
        assert ak.bereiche_aufloesen({}, _CONFIG) == list(_CONFIG)

    def test_genannte_gewinnen(self):
        assert ak.bereiche_aufloesen({"bereiche": ["FAQ"]}, _CONFIG) == ["FAQ"]

    def test_ausgeschlossene_fallen_heraus(self):
        assert ak.bereiche_aufloesen({"ohne": ["FAQ"]}, _CONFIG) == [
            "WirLernenOnline", "OER-Wissen"]

    def test_beides_zusammen(self):
        gewaehlt = ak.bereiche_aufloesen(
            {"bereiche": ["FAQ", "OER-Wissen"], "ohne": ["FAQ"]}, _CONFIG)
        assert gewaehlt == ["OER-Wissen"]

    def test_unbekannte_namen_werden_still_verworfen(self):
        # Ein erfundener Bereich darf die Suche nicht sprengen — er hat nur
        # nichts beizutragen.
        assert ak.bereiche_aufloesen({"bereiche": ["Erfunden"]}, _CONFIG) == list(_CONFIG)

    def test_wer_alles_ausschliesst_bekommt_nichts(self):
        assert ak.bereiche_aufloesen({"ohne": list(_CONFIG)}, _CONFIG) == []


class TestAntwort:
    @pytest.mark.anyio
    async def test_sucht_alle_bereiche_in_einem_zug(self, monkeypatch):
        """Der Grund, warum „immer alle" nichts extra kostet: ``get_rag_context``
        bettet die Frage EINMAL ein und durchsucht die Bereiche nebenlaeufig."""
        gesehen: dict = {}

        async def _fake(session, query, **kw):
            gesehen["query"] = query
            gesehen["areas"] = kw.get("areas")
            return "Treffer-Text"

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        text = await ak.antwort(None, {"frage": "Was ist OER?"}, _CONFIG)
        assert gesehen["areas"] == list(_CONFIG)
        assert gesehen["query"] == "Was ist OER?"
        assert text == "Treffer-Text"

    @pytest.mark.anyio
    async def test_ohne_treffer_sagt_es_der_text(self, monkeypatch):
        async def _fake(session, query, **kw):
            return ""

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        text = await ak.antwort(None, {"frage": "x"}, _CONFIG)
        assert "Keine" in text

    @pytest.mark.anyio
    async def test_ohne_bereich_gar_keine_suche(self, monkeypatch):
        async def _fake(session, query, **kw):  # pragma: no cover - darf nicht laufen
            raise AssertionError("es gibt nichts zu durchsuchen")

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        text = await ak.antwort(None, {"frage": "x", "ohne": list(_CONFIG)}, _CONFIG)
        assert "Keine" in text

    @pytest.mark.anyio
    async def test_leere_frage_wird_abgewiesen(self, monkeypatch):
        async def _fake(session, query, **kw):  # pragma: no cover - darf nicht laufen
            raise AssertionError("ohne Frage keine Einbettung")

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        assert "Frage" in await ak.antwort(None, {"frage": "  "}, _CONFIG)

    @pytest.mark.anyio
    async def test_ein_fehler_beendet_den_zug_nicht(self, monkeypatch, caplog):
        """Dieselbe Regel wie beim Master-Skill: ein Chat, der wegen einer
        Wissensquelle nicht antwortet, ist schlechter als einer ohne sie."""
        async def _fake(session, query, **kw):
            raise RuntimeError("pgvector weg")

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        text = await ak.antwort(None, {"frage": "x"}, _CONFIG)
        assert "nicht erreichbar" in text

    @pytest.mark.anyio
    async def test_der_text_ist_gedeckelt(self, monkeypatch):
        async def _fake(session, query, **kw):
            return "A" * 20000

        monkeypatch.setattr(ak, "get_rag_context", _fake)
        text = await ak.antwort(None, {"frage": "x"}, _CONFIG)
        assert len(text) <= ak.MAX_ZEICHEN


class TestAbwahlFuerDieSchleife:
    """Q (Nutzer-Auftrag 2026-08-18): „neben der bisherigen Steuerung noch eine
    Option, um es im Agent zu nutzen oder nicht."

    Die Vorgabe bleibt „alle" — die zweite Haelfte desselben Satzes. Abgewaehlt
    wird nur, wer ausdruecklich ``agent: false`` traegt.
    """

    def test_ohne_das_feld_ist_alles_dabei(self):
        w = ak.wissen_werkzeug(_CONFIG)
        namen = w["function"]["parameters"]["properties"]["bereiche"]["items"]["enum"]
        assert namen == list(_CONFIG)

    def test_abgewaehlter_bereich_steht_nicht_im_werkzeug(self):
        w = ak.wissen_werkzeug(_CONFIG_MIT_ABWAHL)
        namen = w["function"]["parameters"]["properties"]["bereiche"]["items"]["enum"]
        assert namen == ["WirLernenOnline", "FAQ"]
        assert "OER-Wissen" not in w["function"]["description"]

    def test_abgewaehlter_bereich_wird_auch_nicht_durchsucht(self):
        # Sonst haette das Modell ihn zwar nicht im enum, koennte ihn aber
        # erraten — und die Abwahl waere eine Empfehlung statt einer Regel.
        assert ak.bereiche_aufloesen({}, _CONFIG_MIT_ABWAHL) == ["WirLernenOnline", "FAQ"]
        assert ak.bereiche_aufloesen(
            {"bereiche": ["OER-Wissen"]}, _CONFIG_MIT_ABWAHL) == ["WirLernenOnline", "FAQ"]

    def test_sind_alle_abgewaehlt_gibt_es_kein_werkzeug(self):
        assert ak.wissen_werkzeug({"A": {"mode": "always", "agent": False}}) is None

    def test_der_muster_weg_bleibt_unberuehrt(self):
        # Der Schalter gehoert der Schleife. `load_rag_config` und
        # `_resolve_rag_areas` lesen ihn nicht — sonst naehme eine
        # Agent-Entscheidung dem Mustermodus einen Bereich weg.
        from boerdi.domain.route_head import _resolve_rag_areas
        assert "OER-Wissen" in _resolve_rag_areas({}, _CONFIG_MIT_ABWAHL)
