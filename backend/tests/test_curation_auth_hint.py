"""E3 (= C4): was passiert, wenn ein Muster kuratieren will und niemand angemeldet ist.

Gemessen 2026-08-10 nach E2: nennt ein Muster ``wlo_create_collection`` und ist
kein Zugangsblock hinterlegt, fällt das Werkzeug **spurlos** aus der Liste —
kein Protokolleintrag, kein Hinweis an das Modell. Das Muster verspricht dann
etwas, wovon der Rest des Zuges nichts weiß.

**Der Plan wollte hier einen Verweis auf die ``/auth``-Seite in die Antwort.**
Ich hielt das für die falsche Zielgruppe, weil der Block ein *Server*-Geheimnis
sei (``MCP_AUTH_TOKEN`` in der ``.env`` — ``deploy/README.md``).

**Diese Begründung war falsch und ist seit C5-a überholt.** Sie gilt nur für die
Betriebsart ``service``; der MCP-Server kennt drei (`docs/AUTH.md` §2), und in
``user`` holt sich *jede Person* ihren eigenen Block. Ein Zug trägt seit C5-a den
Block der angemeldeten Person (Kopfzeile → ``set_turn_auth_block``), die Anlage
ist nur noch der Rückfall.

Was von der Aufteilung bleibt — und weiterhin gilt, weil es zwei Ursachen für
denselben Verlust gibt:

* **Modell** → die Wahrheit über die eigene Fähigkeit, ohne Adresse. Es soll
  offen sagen, dass es nichts ändern kann, statt es zu versuchen oder zu
  behaupten.
* **Betreiber** → ein Protokolleintrag genau an der Stelle des Verlusts, der
  ``MCP_AUTH_TOKEN`` nennt. Der Eintrag nennt seit C5-a beide Ursachen, weil von
  dort aus nicht zu unterscheiden ist, welche vorliegt.

Der Verweis auf ``/auth`` gehört damit doch in die Antwort — aber als
zweistufige Rückfrage („anmelden" / „nur lesen") und nicht als nackte Adresse.
Das ist C5-c, nicht diese Datei.
"""

from __future__ import annotations

import pytest

from boerdi.services import response_tool_selection as rts
from boerdi.services.response_prompt_tools_text import render_curation_unavailable
from boerdi.services.response_tool_selection import curation_blocked_by_mode

# ── Die Bedingung ────────────────────────────────────────────────────────


class TestBedingung:
    @pytest.fixture(autouse=True)
    def _ohne_block(self, monkeypatch):
        monkeypatch.setattr(rts, "has_auth_token", lambda: False)

    def test_muster_will_kuratieren_ohne_block(self):
        assert curation_blocked_by_mode({"tools": ["wlo_create_collection"]})

    def test_reines_suchmuster_ist_nicht_betroffen(self):
        assert not curation_blocked_by_mode({"tools": ["search_wlo_content"]})

    def test_muster_ohne_werkzeugliste_ist_nicht_betroffen(self):
        # Ohne genannte Werkzeuge kann auch keines verloren gehen. (Der Grund
        # stand hier bis F-neu falsch: „der Rückfall-Zweig gibt nur
        # Suchwerkzeuge" — dieser Zweig ist über ``phase3_modulate`` gar nicht
        # erreichbar, das Muster bekommt schlicht nichts. Siehe
        # ``test_pattern_tool_naht``.)
        assert not curation_blocked_by_mode({})
        assert not curation_blocked_by_mode({"sources": ["mcp"]})

    def test_mit_block_kein_hinweis(self, monkeypatch):
        monkeypatch.setattr(rts, "has_auth_token", lambda: True)
        assert not curation_blocked_by_mode({"tools": ["wlo_create_collection"]})


# ── Was das Modell erfährt ───────────────────────────────────────────────


class TestHinweisAnDasModell:
    def test_sagt_dass_nichts_geaendert_werden_kann(self):
        block = render_curation_unavailable("de").lower()
        assert "nicht" in block
        assert "ändern" in block or "aendern" in block

    def test_fordert_offenheit_statt_stillschweigen(self):
        # Der Kern: das Modell soll es SAGEN. Ein Hinweis, den es für sich
        # behält, ersetzt das Schweigen nur durch anderes Schweigen.
        block = render_curation_unavailable("de").lower()
        assert "sag" in block

    def test_nennt_keine_anmeldeadresse(self):
        # Die Adresse gehört dem Betreiber, nicht dem Chat. Sie hier zu nennen
        # hiesse, einer beliebigen Person einen Schreib-Zugang anzubieten.
        block = render_curation_unavailable("de")
        assert "/auth" not in block
        assert "http" not in block
        assert "MCP_AUTH_TOKEN" not in block, "Betreiber-Sache, nicht Chat-Sache"

    def test_englisch_ist_uebersetzt(self):
        de = render_curation_unavailable("de")
        en = render_curation_unavailable("en")
        assert de != en
        assert "cannot" in en.lower() or "can't" in en.lower()


# ── Was der Betreiber erfährt ────────────────────────────────────────────


def test_verlust_wird_protokolliert(monkeypatch, caplog):
    """Der stille Verlust bekommt eine Stimme — für den, der ihn beheben kann."""
    monkeypatch.setattr(rts, "has_auth_token", lambda: False)
    with caplog.at_level("WARNING"):
        aktiv, *_ = rts._select_active_tools(
            classification={}, pattern_output={"tools": [
                "wlo_create_collection", "search_wlo_content"]},
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=False, _degradation_no_tools=False,
        )
    namen = {t["function"]["name"] for t in aktiv}
    assert "wlo_create_collection" not in namen, "Werkzeug darf nicht durchrutschen"
    assert "search_wlo_content" in namen, "Der Rest des Musters bleibt unberührt"
    assert "MCP_AUTH_TOKEN" in caplog.text, "Der Betreiber braucht den Namen der Stellschraube"
    assert "wlo_create_collection" in caplog.text, "…und welches Werkzeug fehlte"


def test_protokoll_benennt_das_muster(monkeypatch, caplog):
    """F-neu (2026-08-10): E3 protokollierte ``pattern_output.get("id")`` — den
    Schlüssel gibt es dort nicht. ``phase3_modulate`` schreibt weder ``id`` noch
    ``label`` ins Dict, also stand im Betrieb immer „Muster ?". Der Eintrag sah
    informativ aus und sagte dem Betreiber nicht, wo er nachsehen soll."""
    from boerdi.domain.pattern_engine import PatternDef, phase3_modulate

    monkeypatch.setattr(rts, "has_auth_token", lambda: False)
    betrieblich = phase3_modulate(
        PatternDef(id="M13", label="Inhalt-Einreichen", priority=540,
                   tools=["wlo_create_collection"]),
        signals=[], device="desktop", entities={}, persona_id="P-AND",
    )
    with caplog.at_level("WARNING"):
        rts._select_active_tools(
            classification={}, pattern_output=betrieblich,
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=False, _degradation_no_tools=False,
            pattern_label="M13 Inhalt-Einreichen",
        )
    assert "M13" in caplog.text, caplog.text
    assert "Muster ?" not in caplog.text


def test_mit_block_kein_protokolleintrag(monkeypatch, caplog):
    monkeypatch.setattr(rts, "has_auth_token", lambda: True)
    with caplog.at_level("WARNING"):
        rts._select_active_tools(
            classification={}, pattern_output={"tools": ["wlo_create_collection"]},
            available_rag_areas=None, rag_config=None,
            _cards_inline_mode=False, _degradation_no_tools=False,
        )
    assert "MCP_AUTH_TOKEN" not in caplog.text


# ── Der Hinweis erreicht den Prompt wirklich ─────────────────────────────


def _systemprompt(rpb, pattern_output: dict) -> str:
    return rpb._build_system_prompt(
        classification={}, pattern_output=pattern_output, pattern_label="M13",
        session_state={}, environment={"locale": "de"}, rag_context="",
        available_rag_areas=None, rag_config=None,
    )[0]


def test_hinweis_steht_im_systemprompt(monkeypatch):
    """Ein Baustein, den der Prompt nicht einsetzt, wäre wirkungslos."""
    from boerdi.services import response_prompt_builder as rpb

    monkeypatch.setattr(rpb, "curation_blocked_by_mode", lambda _po: True)
    system = _systemprompt(rpb, {"tools": ["wlo_create_collection"]})
    assert render_curation_unavailable("de").strip() in system


def test_ohne_die_bedingung_bleibt_der_prompt_unveraendert(monkeypatch):
    from boerdi.services import response_prompt_builder as rpb

    monkeypatch.setattr(rpb, "curation_blocked_by_mode", lambda _po: False)
    system = _systemprompt(rpb, {"tools": ["search_wlo_content"]})
    assert render_curation_unavailable("de").strip() not in system
