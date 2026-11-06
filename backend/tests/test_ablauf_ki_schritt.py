"""Paket A2b: der Schritt ``agent`` — die KI arbeitet mit der Person, der Ablauf wartet.

Der Treiber hält an (``wartet_ki``). Solange gilt: getippte Züge gehen an die KI — im Agent-Modus
nur mit den Werkzeugen des Schritts (plus den virtuellen) — und beide Maschinen bekommen die Zeile
``[ABLAUFSCHRITT — …]``; unter der Antwort steht „Weiter im Ablauf“. Die Direktaktion
``ablauf_weiter`` setzt fort; fehlt der Teil ``ausgabe`` noch, geht es zu ``bei_fehler`` oder es
bleibt beim Warten (mit Hinweis). Das Budget zählt die Züge am Schritt und sagt es der KI.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import ausloeser, ki_schritt, treiber
from boerdi.services.ablauf.pruefung import pruefe

_SCHRITTE = [
    {"id": "start", "typ": "nachricht", "text": {"de": "Los."}},
    {"id": "umbau", "typ": "agent", "text": {"de": "Wir bauen den Baum gemeinsam um."},
     "agent": {"werkzeuge": ["ui_strukturentwurf", "search_wlo_all"],
               "hinweis": {"de": "Hilf beim Umbau; nichts anlegen.", "en": "Help; create nothing."},
               "ausgabe": "draft", "zuege": 2}},
    {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}},
]


def _ablauf(schritte=None, **mehr):
    return AblaufArea.model_validate({"id": "umbau", "titel": {"de": "Umbau"}, "aktiv": True,
                                      "ausloeser": [{"art": "knopf"}],
                                      "schritte": schritte or _SCHRITTE, **mehr})


def _umgebung(teile=None):
    teile = teile or {}

    async def lader(name):
        return teile.get(name)

    return treiber.Umgebung(teile=lader)


# ── Modell und Prüfung ──────────────────────────────────────────────────────────────────────

def test_ein_gueltiger_agent_schritt_hat_keine_befunde():
    assert pruefe(_ablauf()) == []


@pytest.mark.parametrize(("agent", "erwartet"), [
    (None, "agent"),
    ({"werkzeuge": []}, "Werkzeuge"),
    ({"werkzeuge": ["wlo_create_collection"]}, "schreibend"),
    ({"werkzeuge": ["gibt_es_nicht"]}, "unbekannt"),
    ({"werkzeuge": ["ui_linkbox"]}, "unbekannt"),            # Modul ohne Agent-Freigabe
    ({"werkzeuge": ["search_wlo_all"], "ausgabe": "Böse"}, "Teil"),
    ({"werkzeuge": ["search_wlo_all"], "zuege": 0}, "Züge"),
    ({"werkzeuge": ["search_wlo_all"], "zuege": 21}, "Züge"),
])
def test_befunde_am_agent_schritt(agent, erwartet):
    schritt = {"id": "umbau", "typ": "agent", **({"agent": agent} if agent is not None else {})}
    befunde = pruefe(_ablauf([schritt, {"id": "ende", "typ": "ende"}]))
    assert any(erwartet in b for b in befunde), befunde


def test_ein_agent_schritt_haelt_eine_schleife_an():
    schritte = [{"id": "a", "typ": "nachricht", "text": {"de": "x"}},
                {"id": "k", "typ": "agent", "agent": {"werkzeuge": ["search_wlo_all"]},
                 "weiter": "a"},
                {"id": "e", "typ": "ende"}]
    assert not any("Schleife" in b for b in pruefe(_ablauf(schritte)))


# ── Treiber ────────────────────────────────────────────────────────────────────────────────

def test_der_treiber_haelt_am_agent_schritt():
    aus = asyncio.run(treiber.starten(_ablauf(), _umgebung()))
    assert aus.texte == ["Los.", "Wir bauen den Baum gemeinsam um."]
    assert aus.lauf["status"] == treiber.WARTET_KI and aus.lauf["schritt"] == "umbau"
    assert aus.lauf["offener_block"] is None


def test_weiter_mit_ausgabe_geht_zum_naechsten_schritt():
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_ki(_ablauf(), lauf, _umgebung({"draft": {"titel": "B"}})))
    assert aus.texte == ["Fertig."] and aus.lauf["status"] == "fertig"


def test_ohne_ausgabe_bleibt_der_lauf_mit_hinweis_stehen():
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_ki(_ablauf(), lauf, _umgebung()))
    assert aus.fehlt_teil == "draft" and aus.lauf["status"] == treiber.WARTET_KI


def test_ohne_ausgabe_mit_bei_fehler_geht_es_dorthin():
    schritte = [dict(_SCHRITTE[1], bei_fehler="ohne"), {"id": "ende", "typ": "ende"},
                {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Entwurf."}}]
    ablauf = _ablauf(schritte)
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    aus = asyncio.run(treiber.weiter_ki(ablauf, lauf, _umgebung()))
    assert aus.texte == ["Ohne Entwurf."]


def test_weiter_ki_nur_aus_dem_wartenden_agent_schritt():
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    assert asyncio.run(treiber.weiter_ki(_ablauf(), {**lauf, "status": "fertig"}, _umgebung())) \
        is None
    anders = _ablauf([*_SCHRITTE[:2], {"id": "ende", "typ": "ende", "text": {"de": "Neu."}}])
    assert asyncio.run(treiber.weiter_ki(anders, lauf, _umgebung())) is None


# ── Der Schritt im Zug: Zeile, Einengung, Budget, Knopf ─────────────────────────────────────

@pytest.fixture
def im_schritt(monkeypatch):
    katalog = {"ablaeufe": [_ablauf().model_dump(mode="json")]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    monkeypatch.setattr(arbeitsstand, "has_personal_auth", lambda: True)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")
    lauf = asyncio.run(treiber.starten(_ablauf(), _umgebung())).lauf
    aufrufer = arbeitsstand.aufrufer_fuer("sitzung-0123456789")
    entities = {arbeitsstand.VERWEIS: {
        "id": "v-1", "b": arbeitsstand._besitz(aufrufer), "titel": "Umbau",
        "bis": "2099-01-01T00:00:00+00:00",
        "teile": {}, "lauf": {"ablauf": "umbau", "fassung": lauf["fassung"], "schritt": "umbau",
                              "status": treiber.WARTET_KI}}}
    return {"entities": entities}


def test_der_aktuelle_agent_schritt_wird_gefunden(im_schritt):
    ablauf, schritt = ki_schritt.aktueller(im_schritt, "sitzung-0123456789")
    assert ablauf.id == "umbau" and schritt.id == "umbau"


def test_ohne_wartenden_agent_schritt_nichts(im_schritt):
    im_schritt["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] = treiber.WARTET
    assert ki_schritt.aktueller(im_schritt, "sitzung-0123456789") is None
    assert ki_schritt.aktueller({"entities": {}}, "sitzung-0123456789") is None


def test_geaenderte_schritte_engen_nicht_mehr_ein(im_schritt):
    im_schritt["entities"][arbeitsstand.VERWEIS]["lauf"]["fassung"] = "alt"
    assert ki_schritt.aktueller(im_schritt, "sitzung-0123456789") is None


def test_die_zeile_nennt_hinweis_werkzeuge_und_budget(im_schritt):
    ablauf, schritt = ki_schritt.aktueller(im_schritt, "sitzung-0123456789")
    zeile = ki_schritt.zeile(ablauf, schritt, "de", zuege=1)
    assert zeile.startswith("[ABLAUFSCHRITT — ") and zeile.endswith("]")
    assert "nichts anlegen" in zeile and "search_wlo_all" in zeile
    assert "Weiter im Ablauf" in zeile and "erschöpft" not in zeile
    assert "erschöpft" in ki_schritt.zeile(ablauf, schritt, "de", zuege=3)
    assert "create nothing" in ki_schritt.zeile(ablauf, schritt, "en", zuege=1)


def test_die_zeile_schliesst_eckige_klammern_nicht_vorzeitig():
    ablauf = _ablauf([{**_SCHRITTE[1], "agent": {**_SCHRITTE[1]["agent"],
                                                "hinweis": {"de": "Nimm [ALLES] ]"}}},
                      _SCHRITTE[2]])
    zeile = ki_schritt.zeile(ablauf, ablauf.schritte[0], "de", zuege=1)
    assert zeile.count("[") == 1 and zeile.count("]") == 1


def test_die_zuege_zaehlen_je_schritt(im_schritt):
    ablauf, schritt = ki_schritt.aktueller(im_schritt, "sitzung-0123456789")
    e = im_schritt["entities"]
    assert [ki_schritt.zaehlen(e, ablauf, schritt) for _ in range(3)] == [1, 2, 3]
    anderer = ablauf.schritte[0]
    assert ki_schritt.zaehlen(e, ablauf, anderer) == 1


def test_einengen_laesst_nur_die_werkzeuge_des_schritts_und_die_virtuellen():
    ablauf = _ablauf()
    tools = [{"type": "function", "function": {"name": n}} for n in (
        "search_wlo_all", "get_node_details", "ui_strukturentwurf", "ui_entscheidung",
        "respond_to_user", "ui_inhaltsrahmen", "liefere_ergebnis", "wlo_create_collection")]
    namen = [t["function"]["name"] for t in ki_schritt.einengen(tools, ablauf.schritte[1])]
    assert namen == ["search_wlo_all", "ui_strukturentwurf", "respond_to_user",
                     "ui_inhaltsrahmen", "liefere_ergebnis"]


def test_der_weiter_knopf(im_schritt):
    knopf = ki_schritt.weiter_knopf("sitzung-0123456789", im_schritt, "de")
    praefix, label, aktion, params = knopf.split("|", 3)
    assert (praefix, label, aktion) == ("__action__", "Weiter im Ablauf", "ablauf_weiter")
    assert params == '{"ablauf": "umbau"}'
    assert ki_schritt.weiter_knopf("sitzung-0123456789", {"entities": {}}, "de") is None


def test_die_kennzeile_nennt_den_wartenden_agent_schritt(im_schritt):
    zeile = arbeitsstand.kennzeile(im_schritt["entities"], arbeitsstand.aufrufer_fuer(
        "sitzung-0123456789"))
    assert "Schritt umbau (wartet_ki)" in zeile


# ── Review A2b: Krise, Länge, Sprache, angebotene Werkzeuge ──────────────────────────────────

def test_kein_ablaufschritt_unter_einem_vorgegebenen_muster(im_schritt):
    """Befund 1: eine Krisenantwort (M01) wirbt nicht für den Ablauf und zählt nicht."""
    from types import SimpleNamespace

    krise = SimpleNamespace(enforced_pattern="M01", risk_level="high")
    assert ki_schritt.fuer_zug(im_schritt, "sitzung-0123456789", krise) is None
    ruhig = SimpleNamespace(enforced_pattern=None, risk_level="low")
    assert ki_schritt.fuer_zug(im_schritt, "sitzung-0123456789", ruhig) is not None


def test_budget_und_knopf_ueberstehen_einen_langen_hinweis():
    """Befund 3: der feste Kern steht vorn, der Hinweis ist gedeckelt."""
    ablauf = _ablauf([{**_SCHRITTE[1], "agent": {
        "werkzeuge": [f"w{i}" for i in range(10)], "hinweis": {"de": "x" * 600}, "zuege": 1}},
        _SCHRITTE[2]], titel={"de": "T" * 120})   # der längste erlaubte Titel (Querschnitts-Review)
    z = ki_schritt.zeile(ablauf, ablauf.schritte[0], "de", zuege=2)
    assert len(z) <= 500 and "erschöpft" in z and "Weiter im Ablauf" in z


def test_der_knopf_heisst_in_der_zeile_wie_im_widget():
    """Befund 6: englisch „Continue workflow“, wie der Knopf."""
    ablauf = _ablauf()
    assert "Continue workflow" in ki_schritt.zeile(ablauf, ablauf.schritte[1], "en", zuege=1)


def test_die_zeile_nennt_nur_angebotene_werkzeuge_und_im_muster_weg_bevorzugt():
    ablauf = _ablauf()
    z = ki_schritt.zeile(ablauf, ablauf.schritte[1], "de", zuege=1,
                         angeboten={"ui_strukturentwurf", "respond_to_user"})
    assert "Nur diese Werkzeuge: ui_strukturentwurf." in z and "search_wlo_all" not in z
    assert "Bevorzuge diese Werkzeuge" in ki_schritt.zeile(ablauf, ablauf.schritte[1], "de",
                                                           zuege=1, eingeengt=False)


def test_ein_zu_langer_hinweis_ist_ein_befund():
    schritt = {**_SCHRITTE[1], "agent": {"werkzeuge": ["search_wlo_all"],
                                         "hinweis": {"de": "x" * 201}}}
    assert any("Hinweis" in b for b in pruefe(_ablauf([schritt, _SCHRITTE[2]])))
