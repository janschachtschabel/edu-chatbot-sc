"""Format-Wächter der Beispiel-Abläufe der UI-Module (``evals/ui-module-flows.yaml``, U1-g).

Eigene Datei neben der Tor-Suite wie ``skill-bruecke-flows.yaml``. Geprüft ohne Netz: das Laden
mit dem Katalog (``ui_any``/``ui_none`` nur mit Katalog-Namen), die erlaubten Felder, der
Judge-Auftrag je Zug — und dass die Datei misst, wofür sie da ist: Themenbaum, Auswahlfeld
samt Antwort darin, eine Gegenprobe und ein Ablauf für beide Maschinen.
"""

from __future__ import annotations

from tests.test_golden_runner import EVALS, rg

FLOWS = EVALS / "ui-module-flows.yaml"

_FLOW_FELDER = {"id", "zielgruppe", "title", "erwartung", "turns"}
_ZUG_FELDER = {"message", "anwendungsfall", "expect", "ui_antwort"}
_EXPECT_FELDER = {"register", "structure", "tools_any", "tools_none", "tools_max", "text_any",
                  "text_none", "qr", "ui_any", "ui_none", "must_offer"}


def _flows() -> list[dict]:
    return rg.load_flows(FLOWS, module=rg.katalog_module())


def _flow(flow_id: str) -> dict:
    """Ein Ablauf über seine Kennung — nicht über die Stelle in der Datei (Review U1-g #12)."""
    return next(f for f in _flows() if f["id"] == flow_id)


def test_die_ablaeufe_laden_mit_dem_katalog_und_tragen_nur_bekannte_felder() -> None:
    flows = _flows()
    ids = [f["id"] for f in flows]
    assert ids == [f"GV-UI-{i}" for i in range(1, 17)]      # U2: 8 … 12, U3-5/U4/U5: 13 … 16
    for flow in flows:
        assert set(flow) <= _FLOW_FELDER, flow["id"]
        assert flow["zielgruppe"] in {"P-LEH", "P-LER", "P-AND"}
        for i, turn in enumerate(flow["turns"], start=1):
            wo = f"{flow['id']} T{i}"
            assert set(turn) <= _ZUG_FELDER, wo
            assert str(turn["message"]).strip(), wo
            assert set(turn["expect"]) <= _EXPECT_FELDER, wo
            assert str(turn["expect"].get("must_offer") or "").strip(), f"{wo} ohne must_offer"
            # Jeder Zug prüft etwas Hartes über die UI-Module oder die Anrede.
            assert {"ui_any", "ui_none", "register"} & set(turn["expect"]), wo


def test_jede_antwort_im_auswahlfeld_folgt_auf_eine_erwartete_frage() -> None:
    antworten = 0
    for flow in _flows():
        for vorher, turn in zip(flow["turns"], flow["turns"][1:], strict=False):
            if "ui_antwort" in turn and "uebernehmen" in turn["ui_antwort"]:
                # U2: übernommen wird der Entwurf des vorigen Zugs.
                assert "ui_strukturentwurf" in vorher["expect"].get("ui_any", []), flow["id"]
            elif "ui_antwort" in turn:
                antworten += 1
                assert "ui_entscheidung" in vorher["expect"].get("ui_any", []), flow["id"]
                assert turn["ui_antwort"]["waehle"], flow["id"]
    assert antworten >= 3


def test_die_datei_misst_themenbaum_auswahlfeld_und_gegenprobe() -> None:
    erwartet = [turn["expect"] for flow in _flows() for turn in flow["turns"]]
    assert any("ui_themenbaum" in e.get("ui_any", []) for e in erwartet)
    assert any("ui_entscheidung" in e.get("ui_any", []) for e in erwartet)
    assert any({"ui_entscheidung", "ui_themenbaum"} <= set(e.get("ui_none", []))
               for e in erwartet)
    assert any("ui_inhaltsrahmen" in e.get("ui_any", []) for e in erwartet)


def test_eine_auswahl_der_beispiel_frage_trifft_eine_beschriftung() -> None:
    """Die Wendungen von GV-UI-3 treffen eine Beschriftung, wie das Modell sie typisch setzt."""
    turn = _flow("GV-UI-3")["turns"][1]
    frage = {"block_id": "abcd1234", "modul": "ui_entscheidung", "art": "abfragen",
             "daten": {"frage": "Für welches Fach?", "optionen": [
                 {"id": "bio", "label": "Biologie"}, {"id": "phy", "label": "Physik"}]}}
    antwort, text, _ = rg.baue_ui_antwort(turn["ui_antwort"], frage, turn["message"])
    assert antwort == {"block_id": "abcd1234", "daten": {"gewaehlt": ["phy"]}}
    assert text == "Physik"


def test_die_wendungen_von_gv_ui_5_treffen_nur_was_gemeint_ist() -> None:
    """Review U1-g #2: „Grundlagen“ und „6.“ trafen fremde Möglichkeiten einer Vorwissens-Frage
    („Grundlagen sitzen …“, „Klasse 6./7. gemischt“). Mehrfachwahl, wie sie das Modell setzen
    kann: gewählt werden nur Klasse und „gar nicht“."""
    turn = _flow("GV-UI-5")["turns"][1]
    optionen = ["Klasse 5", "Klasse 6", "Klasse 6./7. gemischt",
                "Ich weiß gar nicht, was ein Bruch ist", "Grundlagen sitzen, Rechnen hakt"]
    frage = {"block_id": "abcd1234", "modul": "ui_entscheidung", "art": "abfragen",
             "daten": {"frage": "Wo stehst du?", "mehrfach": True, "optionen": [
                 {"id": f"o{i}", "label": label} for i, label in enumerate(optionen)]}}
    _, text, _ = rg.baue_ui_antwort(turn["ui_antwort"], frage, turn["message"])
    assert text == "Klasse 6, Ich weiß gar nicht, was ein Bruch ist"


def test_optik_tiefer_darf_auch_als_trefferliste_kommen() -> None:
    """Review U1-g #5: die Quittung des Themenbaums nennt keine Knoten — ein Unterknoten ist
    getippt kaum erreichbar; Treffer zur Optik sind die ehrliche Alternative."""
    expect = _flow("GV-UI-1")["turns"][1]["expect"]
    assert set(expect["ui_any"]) == {"ui_themenbaum", "ui_trefferliste"}


def test_smalltalk_verbietet_nur_den_baum() -> None:
    """Review U1-g #6: ein Auswahlfeld „Wobei kann ich helfen?“ ist auf Smalltalk vertretbar;
    die Gegenprobe gegen das Auswahlfeld trägt der zweite Zug."""
    erster, zweiter = _flow("GV-UI-6")["turns"]
    assert erster["expect"]["ui_none"] == ["ui_themenbaum"]
    assert set(zweiter["expect"]["ui_none"]) == {"ui_entscheidung", "ui_themenbaum"}


def test_die_datei_trennt_bestand_und_entwurf() -> None:
    """Plan 2026-11-04 T-14: Bestand eindeutig, Entwurf samt Übernehmen, mehrdeutig, Gegenprobe."""
    assert "ui_strukturentwurf" in _flow("GV-UI-8")["turns"][0]["expect"]["ui_none"]
    entwurf = _flow("GV-UI-9")["turns"]
    assert entwurf[0]["expect"]["ui_any"] == ["ui_strukturentwurf"]
    assert entwurf[1]["ui_antwort"] == {"uebernehmen": True}
    # Drittes Review U2, Befund 2: ein Zug später vertieft der Bot den gemerkten Entwurf.
    assert entwurf[2]["expect"]["ui_any"] == ["ui_strukturentwurf"]
    assert "ui_antwort" not in entwurf[2]
    mehrdeutig = _flow("GV-UI-10")["turns"][0]["expect"]
    assert mehrdeutig["ui_any"] == ["ui_themenbaum"] and "Neue Gliederung dazu entwerfen" in (
        mehrdeutig["must_offer"])
    assert {"ui_themenbaum", "ui_strukturentwurf"} <= set(
        _flow("GV-UI-11")["turns"][0]["expect"]["ui_none"])
