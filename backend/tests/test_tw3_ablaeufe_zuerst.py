"""Plan 2026-11-11, TW-3: Abläufe zuerst (Nutzer-Vorgabe N16).

- Die Beschreibung jedes Ablauf-Werkzeugs sagt der KI: Passt der Ablauf, geht er einem
  einzelnen Modul oder Werkzeug vor.
- Im Angebot stehen die Ablauf-Werkzeuge vor den Modulen.
- Wendungen: Der längste passende Treffer gewinnt, nicht die Reihenfolge der Kennungen.
- Startknopf am KI-Schritt: Beim Eintritt in den Schritt steht er als Schnellantwort da. Sein
  Text geht als Nachricht der Person an die KI. Er darf nie eine Direktaktion vortäuschen.
"""

from __future__ import annotations

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, ki_schritt, vorschlag
from tests.test_ablauf_zug import umgebung  # noqa: F401 — Fixture


def _ablauf(kennung: str, *wendungen: str, **mehr) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": kennung, "titel": {"de": kennung}, "aktiv": True,
        "ausloeser": [{"art": "text", "wendungen": list(wendungen)}, {"art": "agent"}],
        "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Ende."}}], **mehr})


@pytest.fixture
def katalog(monkeypatch):
    liste: list[AblaufArea] = []
    monkeypatch.setattr(ausloeser, "katalog", lambda: liste)
    return liste


def test_die_laengste_wendung_gewinnt(katalog):
    katalog += [_ablauf("aaa_allgemein", "themenbaum zu", "themenbaum"),
                _ablauf("zzz_dateien", "themenbaum aus meinen dateien")]
    assert ausloeser.per_text("Bitte einen Themenbaum aus meinen Dateien").id == "zzz_dateien"
    assert ausloeser.per_text("Themenbaum zu Karate").id == "aaa_allgemein"
    assert ausloeser.per_text("Was ist ein Baum?") is None


def test_gleich_lange_treffer_nehmen_die_reihenfolge(katalog):
    katalog += [_ablauf("a", "themenbaum"), _ablauf("b", "themenbaum")]
    assert ausloeser.per_text("themenbaum bitte").id == "a"


def test_die_beschreibung_gibt_dem_ablauf_vorrang(katalog):
    katalog.append(_ablauf("tb", "x", wann=["Die Person will einen Themenbaum"]))
    [werkzeug] = vorschlag.werkzeuge("de")
    text = werkzeug["function"]["description"]
    assert "einzelnen Modulen und Werkzeugen vor" in text
    assert "Die Person will einen Themenbaum" in text


def test_ablauf_werkzeuge_stehen_vor_den_modulen(monkeypatch):
    from boerdi.services import agent_tools

    monkeypatch.setattr(agent_tools, "_mcp_werkzeuge", lambda **_k: [])
    ablauf = {"type": "function", "function": {"name": "ablauf-tb", "description": "d",
                                                "parameters": {"type": "object"}}}
    namen = [t["function"]["name"] for t in agent_tools.build_agent_tools(
        ui_module=["ui_strukturentwurf"], ablauf_tools=[ablauf])]
    assert namen.index("ablauf-tb") < namen.index("ui_strukturentwurf")


def _mit_startknopf(**knopf) -> AblaufArea:
    return AblaufArea.model_validate({"id": "tb", "titel": {"de": "TB"}, "schritte": [
        {"id": "entwurf", "typ": "agent", "text": {"de": "Schwerpunkte?"},
         "agent": {"werkzeuge": ["ui_strukturentwurf"], **knopf}},
        {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})


def test_der_startknopf_in_der_sprache_sonst_deutsch():
    ablauf = _mit_startknopf(startknopf={"de": "Entwurf erstellen", "en": "Create draft"})
    assert ki_schritt.start_knopf(ablauf, "entwurf", "en") == "Create draft"
    assert ki_schritt.start_knopf(ablauf, "entwurf", "fr") == "Entwurf erstellen"
    assert ki_schritt.start_knopf(_mit_startknopf(), "entwurf", "de") is None
    assert ki_schritt.start_knopf(ablauf, "gibts_nicht", "de") is None


def test_der_startknopf_ist_nie_eine_direktaktion():
    def knopf(label):
        return ki_schritt.start_knopf(_mit_startknopf(startknopf={"de": label}), "entwurf", "de")

    assert knopf("__action__|x|ablauf_weiter|{}") is None
    assert knopf("a|b") == "a/b"


def test_beim_eintritt_steht_der_startknopf_vor_weiter(umgebung):  # noqa: F811
    """Der Zug, der in den KI-Schritt führt, zeigt zuerst den Startknopf, dann „Weiter“."""
    import asyncio

    from boerdi.services.ablauf import zug
    from tests.test_ablauf_zug import _S, _req

    ki = {"id": "ki", "titel": {"de": "KI"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
          "schritte": [{"id": "entwurf", "typ": "agent", "text": {"de": "Schwerpunkte?"},
                        "agent": {"werkzeuge": ["ui_strukturentwurf"],
                                  "startknopf": {"de": "Entwurf erstellen"}}},
                       {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]}
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], ki]}
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                                 action_params={"ablauf": "ki"}),
                                      {"entities": {}}))
    assert antwort.quick_replies[0] == "Entwurf erstellen"
    assert antwort.quick_replies[1].startswith("__action__|")


# ── Review TW-3 ───────────────────────────────────────────────────────────────────────────────

def test_review_1_ein_langes_wann_bleibt_ganz(katalog):
    wann = ("Die Person will einen Themenbaum, eine Gliederung oder Sammlungsstruktur zu einem "
            "Thema, ohne eigene Dateien")
    katalog.append(_ablauf("tb", "x", wann=[wann]))
    [werkzeug] = vorschlag.werkzeuge("de")
    assert wann in werkzeug["function"]["description"]


def test_review_1_gekuerzt_wird_an_der_wortgrenze():
    assert vorschlag._gekuerzt("eins zwei drei", 20) == "eins zwei drei"
    assert vorschlag._gekuerzt("eins zwei drei", 11) == "eins zwei…"


def test_review_8_eine_leere_wendung_trifft_nichts(katalog):
    katalog.append(_ablauf("leer", "   "))
    assert ausloeser.per_text("irgendwas") is None


def test_review_5_weiter_im_ablauf_uebersteht_den_deckel():
    from boerdi.domain.wahl_knopf import ist_wahl_knopf, ist_weiter_knopf
    from boerdi.services.widget_postprocess import _auftrags_knoepfe_behalten

    weiter = ki_schritt.knopf("tb", "de")
    assert ist_weiter_knopf(weiter) and not ist_wahl_knopf(weiter)
    assert not ist_weiter_knopf("Entwurf erstellen")
    assert _auftrags_knoepfe_behalten(["Entwurf erstellen", weiter], ["Entwurf erstellen"],
                                      ist_weiter_knopf) == [weiter]


def test_review_7_ein_startknopf_der_nie_erschiene_ist_ein_befund():
    from boerdi.services.ablauf.pruefung import pruefe

    assert any("Startknopf" in b for b in pruefe(_mit_startknopf(startknopf={"de": "a|b"})))
    assert not any("Startknopf" in b
                   for b in pruefe(_mit_startknopf(startknopf={"de": "Entwurf erstellen"})))


def test_review_4_zu_frueh_weiter_zeigt_wieder_den_startknopf(umgebung):  # noqa: F811
    import asyncio

    from boerdi.services.ablauf import zug
    from tests.test_ablauf_zug import _S, _req

    ki = {"id": "ki", "titel": {"de": "KI"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
          "schritte": [{"id": "entwurf", "typ": "agent", "text": {"de": "Schwerpunkte?"},
                        "agent": {"werkzeuge": ["ui_strukturentwurf"], "ausgabe": "draft",
                                  "startknopf": {"de": "Entwurf erstellen"}}},
                       {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]}
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [*umgebung.katalog["wert"]["ablaeufe"], ki]}
    state: dict = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "ki"}), state))
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION_WEITER,
                                                 action_params={"ablauf": "ki"}), state))
    assert antwort.quick_replies[0] == "Entwurf erstellen"

