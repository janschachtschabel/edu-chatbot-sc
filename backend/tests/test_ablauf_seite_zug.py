"""AS-7a (Plan 2026-11-09 §5m): Führungen im Zug — Navigations-Chip (F-2), Seiten-Ping (F-4),
der Chip unter jeder Antwort, solange der Schritt wartet (F-5)."""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.hintergrund_zug import ist_hintergrund_anfrage
from boerdi.domain.wahl_knopf import ist_wahl_knopf
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import fortschritt, seite_zug, treiber, zug
from tests.test_ablauf_zug import _S, umgebung  # noqa: F401 — Fixture

_HIN = {"id": "hin", "typ": "seite", "text": {"de": "Schau dir die Seite an."},
        "url": "/mitmachen/", "label": {"de": "Zur Mitmach-Seite"}, "ankunft": ["/mitmachen*"]}
_ENDE = {"id": "ende", "typ": "ende", "text": {"de": "Angekommen."}}
_SID = "sitzung-0123456789"


def _roh(*schritte) -> dict:
    return AblaufArea.model_validate({
        "id": "fuehrung", "titel": {"de": "Führung"}, "aktiv": True,
        "ausloeser": [{"art": "knopf"}], "schritte": list(schritte or [_HIN, _ENDE]),
    }).model_dump(exclude_none=True)


def _req(seite: str = "/", **mehr) -> ChatRequest:
    return ChatRequest(session_id=_SID, message=mehr.pop("message", ""),
                       environment=Environment(page=seite, **mehr.pop("env", {})), **mehr)


def _starten(umgebung, roh, seite="/"):  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    zustand: dict = {"entities": {}}
    antwort = asyncio.run(zug.starten(_S(), _req(seite, action=zug.AKTION,
                                                 action_params={"ablauf": roh["id"]}), zustand))
    return zustand, antwort


def _ping(zustand, seite):
    return asyncio.run(seite_zug.angekommen(
        _S(), _req(seite, message="[ablauf-seite]", env={"page_event": seite_zug.PING}), zustand))


def test_der_knopf_hat_ein_eigenes_praefix_und_uebersteht_jeden_deckel():
    knopf = seite_zug.knopf({"url": "/mitmachen/", "label": "Zur | Seite"})
    assert knopf == "__fuehrung__|Zur / Seite|/mitmachen/"
    assert ist_wahl_knopf(knopf)


def test_der_seiten_ping_ist_ein_hintergrund_zug():
    assert ist_hintergrund_anfrage(Environment(page_event=seite_zug.PING))
    assert ist_hintergrund_anfrage(Environment(page_event="Ablauf_Seite"))


def test_der_start_zeigt_den_weg_und_wartet(umgebung):  # noqa: F811 — Fixture
    zustand, antwort = _starten(umgebung, _roh())
    assert antwort.content == "Schau dir die Seite an."
    assert antwort.quick_replies == ["__fuehrung__|Zur Mitmach-Seite|/mitmachen/"]
    stand = fortschritt.stand(zustand["entities"], arbeitsstand.aufrufer_fuer(_SID), "de")
    assert stand["status"] == treiber.WARTET_SEITE


def test_steht_die_person_schon_dort_laeuft_es_gleich_weiter(umgebung):  # noqa: F811
    _zustand, antwort = _starten(umgebung, _roh(), seite="/mitmachen/")
    assert "Angekommen." in antwort.content


def test_der_ping_auf_einer_anderen_seite_bleibt_leer(umgebung):  # noqa: F811 — Fixture
    zustand, _ = _starten(umgebung, _roh())
    antwort = _ping(zustand, "/home/")
    assert antwort.content == "" and antwort.quick_replies == []
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_SEITE


def test_der_ping_auf_der_zielseite_setzt_fort(umgebung):  # noqa: F811 — Fixture
    zustand, _ = _starten(umgebung, _roh())
    antwort = _ping(zustand, "https://wirlernenonline.de/mitmachen/?x=1")
    assert antwort.content == "Angekommen."
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fertig"


def test_ohne_wartenden_lauf_bleibt_der_ping_leer(umgebung):  # noqa: F811 — Fixture
    assert _ping({"entities": {}}, "/mitmachen/").content == ""


def test_der_chip_steht_unter_jeder_antwort_solange_der_schritt_wartet(umgebung):  # noqa: F811
    zustand, _ = _starten(umgebung, _roh())
    assert seite_zug.aktueller_knopf(_SID, zustand, "de") == [
        "__fuehrung__|Zur Mitmach-Seite|/mitmachen/"]
    _ping(zustand, "/mitmachen/")
    assert seite_zug.aktueller_knopf(_SID, zustand, "de") == []


def test_ohne_ankunft_steht_der_chip_unter_der_antwort_und_es_geht_weiter(umgebung):  # noqa: F811
    hin = {k: v for k, v in _HIN.items() if k != "ankunft"}
    _zustand, antwort = _starten(umgebung, _roh(hin, _ENDE))
    assert "Angekommen." in antwort.content
    assert "__fuehrung__|Zur Mitmach-Seite|/mitmachen/" in antwort.quick_replies


# ── Review AS-7a ───────────────────────────────────────────────────────────────────────────────

def test_review_2_bei_wartet_seite_gilt_der_lauf_als_wartend(umgebung):  # noqa: F811 — Fixture
    """Befund 2: sonst startete eine Wendung oder Modul-Antwort einen Ablauf über den wartenden."""
    zustand, _ = _starten(umgebung, _roh())
    assert zug.lauf_wartet(_SID, zustand)


def test_review_3_die_tour_laesst_den_seiten_ping_durch():
    """Befund 3: während einer Tour beendete der Ping sie (weicher Ausstieg) bzw. galt in
    ``setup`` nicht als Hintergrund-Zug."""
    from boerdi.graph.nodes.setup import _hintergrund_zug
    from boerdi.graph.nodes.tour import tour
    from boerdi.graph.state import TurnContext

    req = _req("/x", message="[ablauf-seite]", env={"page_event": seite_zug.PING})
    zustand = {"tour_state": {"active": True, "step": "content", "group": "lehrkraefte"}}
    ctx = asyncio.run(tour(TurnContext(req=req, session_state=zustand), session=None))
    assert ctx.early_response is None and zustand["tour_state"]["active"] is True
    assert _hintergrund_zug(req, zustand)


def test_review_8_die_kennzeile_nennt_den_wartenden_lauf(umgebung):  # noqa: F811 — Fixture
    from boerdi.services import arbeitsstand_verweis

    zustand, _ = _starten(umgebung, _roh())
    zeile = arbeitsstand_verweis.kennzeile(zustand["entities"], arbeitsstand.aufrufer_fuer(_SID))
    assert "wartet_seite" in zeile



# ── Zweites Review AS-7a ───────────────────────────────────────────────────────────────────────

def test_zweites_review_2_ein_anderswo_bewegter_lauf_frischt_den_verweis_auf(umgebung):  # noqa: F811
    """Befund 2: hat eine zweite Sitzung den Lauf weitergeschoben, bleibt der Verweis nicht auf
    ``wartet_seite`` stehen (sonst pingte das Widget weiter und zeigte einen toten Chip)."""
    zustand, _ = _starten(umgebung, _roh())
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"]["status"] = "fertig"
    assert _ping(zustand, "/mitmachen/").content == ""
    assert seite_zug.aktueller_knopf(_SID, zustand, "de") == []


def test_zweites_review_2_ein_abgeschalteter_ablauf_wartet_nicht_weiter(umgebung):  # noqa: F811
    zustand, _ = _starten(umgebung, _roh())
    roh = _roh()
    roh["aktiv"] = False
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    _ping(zustand, "/mitmachen/")
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"


def test_zweites_review_3_der_seiten_ping_geht_der_tour_aktion_vor():
    assert ist_hintergrund_anfrage(Environment(page_event=seite_zug.PING, tour_action="start"))


# ── AS-7b: Auslöser ``seite`` (F-7) ────────────────────────────────────────────────────────────

def _mit_seiten_ausloeser(**mehr) -> dict:
    roh = _roh()
    roh["ausloeser"] = [{"art": "seite", "muster": ["/mitmachen*"]}]
    roh["titel"] = {"de": "Führung", "en": "Tour"}
    return {**roh, **mehr}


def test_as7b_der_chip_unter_der_begruessung_darf_starten():
    from boerdi.services.ablauf import ausloeser

    assert ausloeser.per_knopf(AblaufArea.model_validate(_mit_seiten_ausloeser()))


def test_as7b_die_angebote_nennen_aktive_ablaeufe_mit_seiten_ausloeser(umgebung):  # noqa: F811
    from boerdi.services.ablauf import ausloeser

    aus = {**_mit_seiten_ausloeser(), "id": "aus", "aktiv": False}
    umgebung.katalog["wert"] = {"ablaeufe": [_mit_seiten_ausloeser(), aus,
                                              {**_roh(), "id": "knopf"}]}
    assert ausloeser.seiten_angebote() == [
        {"id": "fuehrung", "titel": {"de": "Führung", "en": "Tour"}, "muster": ["/mitmachen*"]}]


def test_as7b_das_boot_buendel_traegt_die_angebote(umgebung, monkeypatch):  # noqa: F811
    from types import SimpleNamespace

    from boerdi.api import config as api_config

    umgebung.katalog["wert"] = {"ablaeufe": [_mit_seiten_ausloeser()]}
    for name in ("load_guide_mode_config", "load_header_nav_config", "load_welcome_config"):
        monkeypatch.setattr(api_config.cl, name, lambda: {})
    antwort = asyncio.run(api_config.get_guide_mode(SimpleNamespace(headers={})))
    assert [a["id"] for a in antwort["ablauf_seiten"]] == ["fuehrung"]


# ── Querschnitts-Review AS-7 ───────────────────────────────────────────────────────────────────

def test_quer_1_der_stand_traegt_den_weg_solange_die_fuehrung_wartet(umgebung):  # noqa: F811
    """Befund 1: nach dem Neuladen (Chips der alten Blase sind weg) bleibt der Weg in der Leiste."""
    zustand, _ = _starten(umgebung, _roh())
    stand = fortschritt.stand(zustand["entities"], arbeitsstand.aufrufer_fuer(_SID), "de")
    assert stand["weg"] == {"label": "Zur Mitmach-Seite", "url": "/mitmachen/"}
    _ping(zustand, "/mitmachen/")
    assert fortschritt.stand(zustand["entities"], arbeitsstand.aufrufer_fuer(_SID), "de") is None


def test_quer_2_ein_schon_erreichter_schritt_zeigt_keinen_chip(umgebung):  # noqa: F811
    """Befund 2: auf /home/ stand „Zur Startseite“ vor dem eigentlichen nächsten Weg."""
    start = {**_HIN, "id": "start", "url": "/home/", "label": {"de": "Zur Startseite"},
             "ankunft": ["/home/*"]}
    _zustand, antwort = _starten(umgebung, _roh(start, _HIN, _ENDE), seite="/home/")
    assert antwort.quick_replies == ["__fuehrung__|Zur Mitmach-Seite|/mitmachen/"]


def test_quer_3_ein_abgeschalteter_ablauf_raeumt_den_wartenden_seiten_lauf_auf(umgebung):  # noqa: F811
    """Befund 3: ohne Stand pingt das Widget nie — der getippte Text räumt den Lauf auf."""
    from boerdi.services.ablauf import wahl_zug

    zustand, _ = _starten(umgebung, _roh())
    roh = _roh()
    roh["aktiv"] = False
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    asyncio.run(wahl_zug.aufraeumen(_S(), _SID, zustand))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"


def test_quer_5_angebote_ohne_ablaeufe_die_eine_anmeldung_brauchen(umgebung):  # noqa: F811
    from boerdi.services.ablauf import ausloeser

    mit = {**_mit_seiten_ausloeser(), "id": "angemeldet", "voraussetzungen": ["anmeldung"]}
    umgebung.katalog["wert"] = {"ablaeufe": [_mit_seiten_ausloeser(), mit]}
    assert [a["id"] for a in ausloeser.seiten_angebote()] == ["fuehrung"]
