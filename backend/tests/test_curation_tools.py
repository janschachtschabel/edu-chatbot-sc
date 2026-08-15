"""E2: die kuratierenden Werkzeuge im Katalog — und ihr Betriebsart-Gate.

Gemessen 2026-08-10 an ``tools/list`` des echten Servers: 14 kuratierende
Werkzeuge, 13 davon mit ``confirmToken``. Sie stehen für JEDEN Aufrufer in der
Werkzeugliste, auch anonym — sie verweigern erst beim Aufruf. Ob unser Modell
sie *angeboten* bekommt, entscheiden wir deshalb selbst.

Zwei Regeln, die dieser Test festhält, weil beide leicht still verletzt werden:

1. **Sie stehen nicht in ``TOOL_DEFINITIONS``.** Der Zweig ``has_mcp_source``
   in ``_select_active_tools`` reicht diese Liste als GANZES weiter — läge ein
   Schreibwerkzeug darin, bekäme es jedes Muster mit ``sources: [mcp]``, also
   auch die reinen Suchmuster.
2. **Der Katalog nennt ``confirmToken`` nicht.** Der Wall aus E1 entfernt einen
   vom Modell gesetzten Schlüssel ohnehin; ihn im Schema anzubieten hieße, das
   Modell zum Erfinden einzuladen. Dieselbe Entscheidung wie bei D1, wo
   ``outputFormat`` aus demselben Grund fehlt.
"""

from __future__ import annotations

import pathlib

import yaml

from boerdi.domain.write_confirm import CONFIRMABLE_TOOLS, CURATION_TOOLS
from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_cache import _TOOL_CACHE_BLOCKLIST
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from boerdi.services.response_tool_selection import _select_active_tools

_REGISTRY = (
    pathlib.Path(__file__).resolve().parents[1] / "seeds" / "05-knowledge" / "mcp-servers.yaml"
)


def _kuration() -> dict[str, dict]:
    return {t["function"]["name"]: t["function"] for t in CURATION_TOOL_DEFINITIONS}


def _beispielwert(feld: str):
    """Ein gueltiger Wert je Pflichtfeld — die Enums vertragen keinen Platzhalter."""
    if feld == "decision":
        return "accept"
    if feld == "suggestions":
        return [{"field": "title", "value": "Neu", "reason": "praeziser"}]
    return f"probe-{feld}"


def _auswahl(monkeypatch, *, dienst: bool, pattern_output: dict) -> set[str]:
    from boerdi.services import response_tool_selection

    monkeypatch.setattr(response_tool_selection, "has_auth_token", lambda: dienst)
    aktiv, *_ = _select_active_tools(
        classification={}, pattern_output=pattern_output,
        available_rag_areas=None, rag_config=None,
        _cards_inline_mode=False, _degradation_no_tools=False,
    )
    return {t["function"]["name"] for t in aktiv}


# ── Der Katalog ──────────────────────────────────────────────────────────


class TestKatalog:
    def test_alle_vierzehn_sind_definiert(self):
        assert set(_kuration()) == set(CURATION_TOOLS)

    def test_keines_steht_im_lese_katalog(self):
        # Sonst reicht der ``has_mcp_source``-Zweig sie an JEDES Suchmuster.
        lesend = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert lesend & set(CURATION_TOOLS) == set()

    def test_der_katalog_bietet_keinen_confirmtoken_an(self):
        for name, fn in _kuration().items():
            felder = fn["parameters"]["properties"]
            assert "confirmToken" not in felder, (
                f"{name} bietet dem Modell den Bestätigungsschlüssel an — der "
                "kommt ausschließlich von uns (E1)."
            )

    def test_jede_beschreibung_nennt_die_zweistufigkeit(self):
        # Ohne diesen Hinweis hält das Modell die Vorschau für einen Fehlschlag
        # und versucht es wortreich erneut, statt den Nutzer zu fragen.
        for name in CONFIRMABLE_TOOLS:
            beschreibung = _kuration()[name]["description"].lower()
            assert "vorschau" in beschreibung, f"{name} erklärt die Vorschau nicht"

    def test_keine_beschreibung_verlangt_die_nacherzaehlung(self):
        # Zwilling zu ``test_m18_laesst_die_vorschau_zeigen_statt_nacherzaehlen``
        # im Seed-Baum, und beide gehören zusammen: Werkzeug-Beschreibung
        # (Code, wirkt sofort) und Muster-Kernregel (Seed, wirkt nach dem
        # Import) sprechen BEIDE zum selben Modell. Widersprechen sie sich,
        # bekommt es zwei Aufträge — der Fall, den Doppel-Konfigurationen
        # zuverlässig produzieren.
        #
        # Seit S2 legt der Chat den Vorschautext selbst vor. „Zeige dem
        # Nutzer, was sich ändern würde" hieße jetzt: zeig es ein zweites Mal.
        for name in CONFIRMABLE_TOOLS:
            beschreibung = _kuration()[name]["description"]
            assert "Zeige dem Nutzer" not in beschreibung, (
                f"{name}: der Chat zeigt die Vorschau selbst — das Modell ordnet nur ein"
            )

    def test_pflichtfelder_wie_am_server_gemessen(self):
        # Live abgeholt 2026-08-10, nicht abgetippt.
        erwartet = {
            "wlo_create_content": ["title"],
            "wlo_update_content": ["nodeId"],
            "wlo_delete_content": ["nodeId"],
            "wlo_submit_content": ["nodeId"],
            "wlo_create_collection": ["title"],
            "wlo_rename_collection": ["nodeId", "title"],
            "wlo_delete_collection": ["nodeId"],
            "wlo_add_to_collection": ["collectionId", "nodeId"],
            "wlo_remove_from_collection": ["collectionId", "nodeId"],
            "wlo_update_compendium": ["nodeId"],
            "wlo_set_topic_page": ["collectionId", "variantId"],
            "wlo_suggest_metadata": ["nodeId", "suggestions"],
            "wlo_list_suggestions": ["nodeId"],
            "wlo_decide_suggestion": ["nodeId", "suggestionId", "decision"],
        }
        katalog = _kuration()
        for name, pflicht in erwartet.items():
            assert katalog[name]["parameters"]["required"] == pflicht, name


# ── Argument-Validierung ─────────────────────────────────────────────────


class TestArgumente:
    def test_jedes_werkzeug_hat_ein_modell(self):
        # Ohne Modell reicht ``validate_tool_args`` die Rohargumente durch —
        # bei einem Schreibwerkzeug ist das die Stelle, an der ein vertippter
        # Feldname unbemerkt zum Server geht.
        #
        # Die Pflichtfelder MUESSEN mitgegeben werden: fehlen sie, scheitert die
        # Validierung und der Fallback reicht ebenfalls die Rohargumente durch —
        # der Test faende dann „kein Modell", wo nur seine eigene Eingabe
        # unvollstaendig war.
        for name, fn in _kuration().items():
            args = {feld: _beispielwert(feld) for feld in fn["parameters"]["required"]}
            geprueft = validate_tool_args(name, {**args, "erfunden": "x"})
            assert "erfunden" not in geprueft, f"{name} hat kein Argument-Modell"

    def test_kein_none_erreicht_den_server(self):
        # ``_export_non_empty`` entfernt nur leere Strings. Ein ``None`` reiste
        # als JSON-``null`` weiter, und der Server fuehrt seine optionalen
        # Felder als „weglassen", nicht als „null" — er lehnte den Aufruf ab.
        for name, fn in _kuration().items():
            args = {feld: _beispielwert(feld) for feld in fn["parameters"]["required"]}
            geprueft = validate_tool_args(name, args)
            assert None not in geprueft.values(), f"{name} schickt ein None: {geprueft}"

    def test_leere_felder_fallen_raus(self):
        geprueft = validate_tool_args(
            "wlo_create_collection", {"title": "Bruchrechnung", "description": ""})
        assert geprueft == {"title": "Bruchrechnung"}

    def test_entscheidung_bleibt_erhalten(self):
        geprueft = validate_tool_args(
            "wlo_decide_suggestion",
            {"nodeId": "n1", "suggestionId": "s1", "decision": "accept"})
        assert geprueft["decision"] == "accept"

    def test_vorschlagsliste_uebersteht_die_validierung(self):
        # Das einzige verschachtelte Schema — ein zu enges Modell würde die
        # Vorschläge still auf die Hälfte kürzen.
        vorschlaege = [
            {"field": "title", "value": "Besserer Titel", "reason": "praeziser",
             "confidence": 0.8},
            {"field": "discipline", "value": "Mathematik", "reason": "Fach fehlte"},
        ]
        geprueft = validate_tool_args(
            "wlo_suggest_metadata", {"nodeId": "n1", "suggestions": vorschlaege})
        assert len(geprueft["suggestions"]) == 2
        assert geprueft["suggestions"][0]["confidence"] == 0.8
        # Ohne ``confidence`` darf kein Ersatzwert erfunden werden: der Server
        # führt das Feld als optional, und eine erfundene Sicherheit wäre eine
        # Aussage, die niemand getroffen hat.
        assert "confidence" not in geprueft["suggestions"][1]


# ── Der Weg des Schlüssels zum Server (S5, 2026-08-15) ───────────────────
#
# Befund des Nutzers: „er will eine Bestätigung — die aber immer wieder gefragt
# wird und es geht nicht weiter." Ursache waren zwei stille Stellen auf dem Weg
# nach draussen, und beide sind hier festgeklemmt. Sie greifen ineinander: ohne
# den Schlüssel ist der Ausführungsaufruf wieder eine Vorschau, und weil der
# Schlüssel VOR dem Cache-Schlüssel wegfiel, war er sogar dieselbe — beantwortet
# aus dem Zwischenspeicher, ohne dass der Server je davon erfuhr.


class TestSchluesselErreichtDenServer:
    def test_der_schluessel_ueberlebt_die_validierung(self):
        # Gemessen 2026-08-15: ``validate_tool_args`` gab
        # ``{'title': 'Optik'}`` zurück — der Schlüssel war weg. ``confirmToken``
        # steht bewusst in KEINEM Argument-Modell (er gehört nicht zu dem, was
        # ein Modell bestimmen darf, siehe ``schemas_mcp_curation``), und
        # pydantic ignoriert unbekannte Felder stillschweigend.
        for name in sorted(CONFIRMABLE_TOOLS & set(_kuration())):
            fn = _kuration()[name]
            args = {feld: _beispielwert(feld) for feld in fn["parameters"]["required"]}
            geprueft = validate_tool_args(name, {**args, "confirmToken": "TOK-123"})
            assert geprueft.get("confirmToken") == "TOK-123", (
                f"{name}: ohne Schlüssel wird aus der Ausführung wieder eine Vorschau"
            )

    def test_erfundene_felder_fallen_weiterhin_raus(self):
        # Gegenprobe: die Ausnahme gilt genau einem Namen, nicht allen.
        geprueft = validate_tool_args(
            "wlo_create_collection",
            {"title": "Optik", "confirmToken": "TOK-123", "erfunden": "x"})
        assert geprueft["confirmToken"] == "TOK-123"
        assert "erfunden" not in geprueft

    def test_ohne_schluessel_bleibt_das_feld_weg(self):
        # Ein leeres Feld wäre kein Nichts: der Server unterscheidet „ohne
        # confirmToken" (Vorschau) von einem ungültigen Schlüssel (Absage).
        geprueft = validate_tool_args("wlo_create_collection", {"title": "Optik"})
        assert "confirmToken" not in geprueft

    def test_bei_lesenden_werkzeugen_ist_confirmtoken_ein_fremdes_feld(self):
        geprueft = validate_tool_args(
            "search_wlo_collections", {"searchTerm": "Optik", "confirmToken": "TOK-123"})
        assert "confirmToken" not in geprueft


class TestKeinZwischenspeicherFuerAenderungen:
    def test_kuratierende_werkzeuge_werden_nie_zwischengespeichert(self):
        # Der Zwischenspeicher ist prozessweit und cacht per Vorgabe ALLES.
        # Für eine Änderung ist das dreifach falsch: die Ausführung würde aus
        # dem Speicher beantwortet statt ausgeführt; eine zwischengespeicherte
        # Vorschau reichte einen längst verbrauchten Schlüssel weiter; und eine
        # Liste offener Vorschläge wäre nach einer Entscheidung veraltet.
        for name in sorted(CURATION_TOOLS):
            assert name in _TOOL_CACHE_BLOCKLIST, (
                f"{name} ändert oder liest den Bestand live — nichts zum Aufheben"
            )

    def test_die_auskunft_ueber_die_anmeldung_wird_nie_aufgehoben(self):
        # ``wlo_auth_status`` beantwortet „unter welchem Namen würde geschrieben".
        # Der Zwischenspeicher kennt den Zugangsblock nicht (der reist im
        # ContextVar, nicht in den Argumenten) — eine aufgehobene Antwort
        # gehörte also womöglich einer anderen Person.
        assert "wlo_auth_status" in _TOOL_CACHE_BLOCKLIST

    def test_suchen_werden_weiterhin_zwischengespeichert(self):
        # Gegenprobe: die Sperre ist eine Liste, kein Abschalten.
        assert "search_wlo_collections" not in _TOOL_CACHE_BLOCKLIST


# ── Das Betriebsart-Gate ─────────────────────────────────────────────────


class TestBetriebsartGate:
    def test_dienst_betriebsart_liefert_das_genannte_werkzeug(self, monkeypatch):
        namen = _auswahl(monkeypatch, dienst=True,
                         pattern_output={"tools": ["wlo_create_collection"]})
        assert "wlo_create_collection" in namen

    def test_ohne_zugangsblock_kein_schreibwerkzeug(self, monkeypatch):
        # Anonym verweigert der Server ohnehin. Es GAR NICHT anzubieten ist
        # trotzdem richtig: sonst kündigt der Bot eine Fähigkeit an, die der
        # nächste Schritt zurücknimmt.
        namen = _auswahl(monkeypatch, dienst=False,
                         pattern_output={"tools": ["wlo_create_collection"]})
        assert "wlo_create_collection" not in namen

    def test_alle_werkzeuge_heisst_nicht_die_schreibenden(self, monkeypatch):
        # ``sources: [mcp]`` ohne ``tools`` reicht den GANZEN Lesekatalog
        # weiter. Kuratieren muss ein Muster ausdrücklich nennen.
        namen = _auswahl(monkeypatch, dienst=True,
                         pattern_output={"sources": ["mcp"]})
        assert namen & set(CURATION_TOOLS) == set()
        assert "search_wlo_content" in namen, "Der Lesekatalog muss unberührt bleiben"

    def test_lesekatalog_unveraendert_ohne_zugangsblock(self, monkeypatch):
        # Regression: das Gate darf die Bestandsauswahl nicht anfassen.
        mit = _auswahl(monkeypatch, dienst=True, pattern_output={"sources": ["mcp"]})
        ohne = _auswahl(monkeypatch, dienst=False, pattern_output={"sources": ["mcp"]})
        assert mit == ohne


# ── Wächter der Gegenrichtung ────────────────────────────────────────────


def test_registry_und_katalog_stimmen_ueberein():
    daten = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    registry = {t for s in daten["servers"] for t in s.get("tools", [])}
    fehlend = set(CURATION_TOOLS) - registry
    assert not fehlend, (
        f"Ohne Registry-Eintrag fällt der Aufruf still auf die Default-URL: {sorted(fehlend)}"
    )
