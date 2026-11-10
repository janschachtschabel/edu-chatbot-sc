"""Paket AS-8a: Probe-Sitzungen aus der Studio-Vorschau — Trockenlauf (Plan 2026-11-09 §5n,
P-1…P-7).

Eine Probe erkennt das Backend nur mit gültigem Studio-Cookie. Sie klebt an der Sitzung
(``entities._probe``), schreibt nichts (MCP, Ablage), startet keinen echten Auftrag und darf jeden
Ablauf des Katalogs starten — auch einen ausgeschalteten.
"""

from __future__ import annotations

import asyncio
import contextvars

import httpx
import pytest
from starlette.requests import Request

from boerdi.api import probe_anfrage
from boerdi.api.schemas import ChatRequest
from boerdi.api.studio_auth import COOKIE_NAME, studio_token
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import probe
from boerdi.services.ablauf import auftrag_zug, treiber, zug, zug_basis
from boerdi.services.auftraege import client as auftraege
from boerdi.services.mcp import client as mcp_client
from boerdi.settings import get_settings
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)

_PASSWORT = "ein-langes-studio-passwort"


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setenv("STUDIO_PASSWORD", _PASSWORT)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    get_settings.cache_clear()
    # der Merker gehört diesem Test — danach wie vorher (sonst träfe er Folgetests)
    marke = probe._merker.set(None)
    yield
    probe._merker.reset(marke)
    get_settings.cache_clear()


def _anfrage(cookie: str | None) -> Request:
    kopf = ([(b"cookie", f"{COOKIE_NAME}={cookie}".encode("latin-1"))]
            if cookie is not None else [])
    return Request({"type": "http", "method": "POST", "path": "/api/chat", "headers": kopf,
                    "client": ("127.0.0.1", 5000), "query_string": b""})


def _chat(probe_flag: bool) -> ChatRequest:
    return ChatRequest(session_id="sitzung-0123456789", message="hallo", probe=probe_flag)


# ── P-1: Erkennung nur mit Studio-Cookie ───────────────────────────────────────────────────────

def test_ohne_probe_wird_das_cookie_gar_nicht_gelesen():
    assert probe_anfrage.probe_erlaubt(_anfrage(studio_token(_PASSWORT)), _chat(False)) is False


def test_probe_mit_gueltigem_cookie_gilt():
    assert probe_anfrage.probe_erlaubt(_anfrage(studio_token(_PASSWORT)), _chat(True)) is True


@pytest.mark.parametrize("cookie", [None, "", "falsch", "ü" * 64])
def test_probe_ohne_gueltiges_cookie_bleibt_wirkungslos(cookie):
    assert probe_anfrage.probe_erlaubt(_anfrage(cookie), _chat(True)) is False


def test_probe_ohne_passwort_und_ohne_offenen_admin_gilt_nie(monkeypatch):
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    get_settings.cache_clear()
    assert probe_anfrage.probe_erlaubt(_anfrage(None), _chat(True)) is False


# ── P-2: der Zug-Merker klebt an der Sitzung ───────────────────────────────────────────────────

def test_ohne_gebundenen_merker_ist_keine_probe():
    probe._merker.set(None)
    assert probe.aktiv() is False
    entities: dict = {probe.ENTITY_KEY: True}
    assert probe.uebernehmen(entities) is False      # ohne Merker nichts zu übernehmen


def test_eine_erkannte_probe_merkt_sich_die_sitzung():
    probe.binde(True)
    entities: dict = {}
    assert probe.uebernehmen(entities) is True       # neu gesetzt — der Aufrufer schreibt fest
    assert entities[probe.ENTITY_KEY] is True
    assert probe.uebernehmen(entities) is False      # schon gemerkt


def test_eine_probe_sitzung_bleibt_probe_auch_ohne_flag():
    probe.binde(False)
    assert probe.uebernehmen({probe.ENTITY_KEY: True}) is False
    assert probe.aktiv() is True


def test_nur_true_zaehlt_als_marke():
    probe.binde(False)
    probe.uebernehmen({probe.ENTITY_KEY: "ja"})
    assert probe.aktiv() is False
    assert probe.in_sitzung({probe.ENTITY_KEY: 1}) is False
    assert probe.in_sitzung(None) is False
    assert probe.in_sitzung({probe.ENTITY_KEY: True}) is True


# ── P-3: MCP-Schreiben im Trockenlauf ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(("name", "args", "trocken"), [
    ("wlo_create_content", {"confirmToken": "k"}, True),
    ("wlo_create_collection_tree", {"continuationToken": "k"}, True),
    ("wlo_create_content", {"title": "x"}, False),            # Vorschau ohne Schlüssel
    ("wlo_list_suggestions", {"confirmToken": "k"}, False),   # lesend
    ("wlo_auth_status", {}, False),
    ("search_wlo_all", {"query": "x"}, False),
    ("wlo_ganz_neu_schreibend", {}, True),                    # schreibend ohne Bestätigung
])
def test_was_im_trockenlauf_nicht_laeuft(name, args, trocken):
    assert probe.trocken_noetig(name, args) is trocken


def test_der_trockenlauf_ruft_kein_schreibendes_werkzeug(monkeypatch):
    gerufen: list = []

    async def transport(name, args, **_k):
        gerufen.append(name)
        raise AssertionError("darf nicht laufen")

    monkeypatch.setattr(mcp_client.transport, "call_tool", transport)
    probe.binde(True, "en")
    antwort = asyncio.run(mcp_client.call_mcp_tool_antwort(
        "wlo_create_content", {"title": "x", "confirmToken": "k"}))
    assert gerufen == []
    assert antwort.art == "" and not mcp_client.is_mcp_error(antwort.text)
    assert "wlo_create_content" in antwort.text and "Dry run" in antwort.text
    assert antwort.strukturiert == {"trockenlauf": True, "werkzeug": "wlo_create_content",
                                    "complete": True}


def test_ohne_probe_laeuft_das_schreiben_wie_bisher(monkeypatch):
    gerufen: list = []

    async def transport(name, args, **_k):
        gerufen.append(name)
        return {"result": {"content": [{"type": "text", "text": "ok"}]}}

    monkeypatch.setattr(mcp_client.transport, "call_tool", transport)
    asyncio.run(mcp_client.call_mcp_tool_antwort("wlo_create_content", {"confirmToken": "k"}))
    assert gerufen == ["wlo_create_content"]


# ── P-5: Aufträge im Trockenlauf ───────────────────────────────────────────────────────────────

def _keine_b_api(monkeypatch):
    def nie(_anfrage):
        raise AssertionError("b-api darf nicht angefragt werden")

    monkeypatch.setattr(auftraege, "_transport", httpx.MockTransport(nie))


def test_der_starter_der_probe_braucht_keine_b_api(monkeypatch):
    _keine_b_api(monkeypatch)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: False)
    probe.binde(True)
    starte = auftrag_zug.starter()
    assert starte is not None
    job = asyncio.run(starte("ns/flow", {"a": 1}))
    assert auftraege.ist_trocken(job) and auftraege._ID.fullmatch(job)


def test_querschnitt_as8_3_auch_in_der_probe_braucht_ein_auftrag_die_anmeldung(monkeypatch):
    """P-8: die Probe zeigt, was die Person sieht — ohne Anmeldung geht ein Auftrag im Betrieb zu
    ``bei_fehler``, also auch hier. Übersprungen werden nur b-api und Schlüssel."""
    _keine_b_api(monkeypatch)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: False)
    probe.binde(True)
    assert auftrag_zug.starter() is None


def test_ohne_probe_bleibt_der_starter_an_die_anmeldung_gebunden(monkeypatch):
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: False)
    assert auftrag_zug.starter() is None


def test_ein_trockener_auftrag_ist_sofort_fertig_und_leer(monkeypatch):
    _keine_b_api(monkeypatch)
    job = auftraege.trocken_kennung()
    stand = asyncio.run(auftraege.stand(job))
    assert (stand.status, stand.outputs, stand.dateien) == ("fertig", {}, [])
    assert asyncio.run(auftraege.abbrechen(job)) == "abgebrochen"
    with pytest.raises(auftraege.AuftragFehler):
        asyncio.run(auftraege.datei(job, "datei", 10))


def test_ein_trockener_auftrag_wird_nicht_im_hintergrund_abgebrochen(monkeypatch):
    _keine_b_api(monkeypatch)

    async def lauf():
        auftraege.abbrechen_im_hintergrund(auftraege.trocken_kennung())
        assert auftraege._abbrueche == set()

    asyncio.run(lauf())


def test_eine_echte_kennung_ist_nie_trocken():
    assert auftraege.ist_trocken("1234-abc") is False
    assert auftraege.ist_trocken("trocken-") is False


# ── P-6: ausgeschaltete Abläufe in der Probe ───────────────────────────────────────────────────

def _ablauf(aktiv=False, ausloeser=("knopf",), start=None):
    return AblaufArea.model_validate({
        "id": "probe_ablauf", "titel": {"de": "Probe"}, "aktiv": aktiv,
        "ausloeser": [{"art": a} for a in ausloeser], "start": start,
        "schritte": [{"id": "hallo", "typ": "nachricht", "text": {"de": "Hallo Probe."}},
                     {"id": "e", "typ": "ende"}]})


def test_gilt_kennt_aktiv_probe_und_fassung():
    an, aus = _ablauf(aktiv=True), _ablauf(aktiv=False)
    lauf = {"fassung": treiber.fassung(an)}
    assert treiber.gilt(an, lauf) is True
    assert treiber.gilt(aus, {"fassung": treiber.fassung(aus)}) is False
    assert treiber.gilt(aus, {"fassung": treiber.fassung(aus), "probe": True}) is True
    assert treiber.gilt(aus, {"fassung": "alt", "probe": True}) is False
    assert treiber.gilt(None, {"probe": True}) is False
    assert treiber.gilt(aus, {"fassung": treiber.fassung(aus), "probe": "ja"}) is False


def test_der_treiber_markiert_einen_lauf_der_probe():
    async def keine(_name):
        return None

    async def mcp(_name, _args):
        return None

    mit = treiber.Umgebung(teile=keine, sprache="de", mcp=mcp, probe=True)
    ohne = treiber.Umgebung(teile=keine, sprache="de", mcp=mcp)
    assert asyncio.run(treiber.starten(_ablauf(), mit)).lauf.get("probe") is True
    assert "probe" not in asyncio.run(treiber.starten(_ablauf(), ohne)).lauf


def test_die_umgebung_des_zugs_traegt_die_probe():
    probe.binde(True)
    u = zug_basis.umgebung(_S(), _req(), {}, ())
    assert u.probe is True
    probe.binde(False)
    assert zug_basis.umgebung(_S(), _req(), {}, ()).probe is False


def _starten(umgebung, ablauf, params):  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    state: dict = {"entities": {}}
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": ablauf.id, **params})
    return asyncio.run(zug.starten(_S(), anfrage, state))


def test_ohne_probe_startet_ein_ausgeschalteter_ablauf_nicht(umgebung):  # noqa: F811
    antwort = _starten(umgebung, _ablauf(), {})
    assert umgebung.speicher.v == {}
    assert "Hallo Probe" not in antwort.content


def test_in_der_probe_startet_ein_ausgeschalteter_ablauf(umgebung):  # noqa: F811
    probe.binde(True)
    antwort = _starten(umgebung, _ablauf(ausloeser=("text",)), {"quelle": "gastseite"})
    assert "Hallo Probe" in antwort.content


_FELD = [{"name": "thema", "typ": "text"}]


def test_in_der_probe_nimmt_jeder_ablauf_mit_startschema_daten(umgebung):  # noqa: F811
    probe.binde(True)
    _starten(umgebung, _ablauf(start=_FELD), {"start": {"thema": "Optik"}, "quelle": "gastseite"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["start"]["wert"] == {"thema": "Optik"}
    assert v.akte["lauf"]["probe"] is True


def test_auch_in_der_probe_werden_startdaten_geprueft(umgebung):  # noqa: F811
    probe.binde(True)
    _starten(umgebung, _ablauf(start=_FELD), {"start": {"fremd": "x"}, "quelle": "gastseite"})
    assert umgebung.speicher.v == {}


# ── P-2: Verdrahtung Endpunkt → begin_turn → setup ─────────────────────────────────────────────

def test_der_endpunkt_entscheidet_die_probe_genau_einmal():
    """Zweites Review AS-8a, Befund 3: der Zug übernimmt die Entscheidung aus ``pruefe_probe`` —
    eine zweite Prüfung später (nach Handschlag und Sitzungssperre) könnte anders ausgehen und den
    Zug still echt laufen lassen."""
    import inspect

    from boerdi.api import chat as chat_api

    assert chat_api.turn_kontext(_chat(True), True).probe is True
    assert chat_api.turn_kontext(_chat(True), False).probe is False
    assert "probe_erlaubt" not in inspect.getsource(chat_api.turn_kontext)
    for endpunkt in (chat_api.chat, chat_api.chat_stream):
        assert "= pruefe_probe(" in inspect.getsource(endpunkt)


def test_begin_turn_bindet_die_probe_des_zugs():
    from boerdi.graph.build import begin_turn
    from boerdi.graph.state import TurnContext

    def zug(mit_probe: bool) -> bool:
        begin_turn(TurnContext(req=_chat(True), probe=mit_probe))
        return probe.aktiv()

    # in einer Kopie des Kontexts: ``begin_turn`` bindet auch Zugakte und Zug-Sammler
    assert contextvars.copy_context().run(zug, True) is True
    # ``req.probe`` allein ist kein Recht — nur, was der Endpunkt mit dem Cookie festgestellt hat
    assert contextvars.copy_context().run(zug, False) is False


def test_setup_haelt_eine_neue_probe_sofort_an_der_sitzung_fest(monkeypatch):
    from boerdi.graph.nodes import setup as setup_mod
    from boerdi.graph.state import TurnContext

    gespeichert: list = []

    async def zeile(_s, sid):
        return {"session_id": sid, "entities": {}}

    async def verlauf(*_a, **_k):
        return []

    async def merken(_s, _sid, **spalten):
        gespeichert.append(spalten)

    monkeypatch.setattr(setup_mod, "get_or_create_session", zeile)
    monkeypatch.setattr(setup_mod, "get_messages", verlauf)
    monkeypatch.setattr(setup_mod, "update_session", merken)
    probe.binde(True)
    ctx = asyncio.run(setup_mod.setup(TurnContext(req=_chat(True), probe=True), object()))
    assert ctx.session_state["entities"][probe.ENTITY_KEY] is True
    assert any(s.get("entities", {}).get(probe.ENTITY_KEY) is True for s in gespeichert)


# ── Review AS-8a, Befund 1: Probe- und echte Vorgänge bleiben getrennt ─────────────────────────

_SITZUNG = "sitzung-0123456789"


def _wartet(aktiv=True, ablauf_id="echt"):
    return AblaufArea.model_validate({
        "id": ablauf_id, "titel": {"de": "Wartet"}, "aktiv": aktiv,
        "ausloeser": [{"art": "knopf"}],
        "schritte": [{"id": "hin", "typ": "seite", "text": {"de": "Als Nächstes die Seite."},
                      "url": "/ziel", "ankunft": ["/ziel*"]},
                     {"id": "e", "typ": "ende"}]})


def test_review_1_in_der_probe_hat_die_person_eine_eigene_kennung(umgebung):  # noqa: F811
    from boerdi.services import arbeitsstand

    assert arbeitsstand.aufrufer_fuer(_SITZUNG) == "person-a"
    probe.binde(True)
    assert arbeitsstand.aufrufer_fuer(_SITZUNG) == f"probe:{_SITZUNG}"
    # außerhalb des Graphen (ohne Merker) aus den Entities der Sitzung
    probe._merker.set(None)
    assert arbeitsstand.aufrufer_fuer(_SITZUNG, {probe.ENTITY_KEY: True}) == f"probe:{_SITZUNG}"
    assert arbeitsstand.aufrufer_fuer(_SITZUNG, {}) == "person-a"


def test_review_1_die_probe_findet_den_echten_vorgang_der_person_nicht(umgebung):  # noqa: F811
    from boerdi.services import arbeitsstand

    _starten(umgebung, _wartet(), {})
    [echt] = umgebung.speicher.v.values()
    probe.binde(True)
    entities: dict = {}
    asyncio.run(arbeitsstand.auffrischen(_S(), _SITZUNG, entities))
    assert arbeitsstand.VERWEIS not in entities


def test_review_1_ein_probe_lauf_taucht_in_echten_sitzungen_nicht_auf(umgebung):  # noqa: F811
    from boerdi.services import arbeitsstand

    probe.binde(True)
    _starten(umgebung, _wartet(aktiv=False, ablauf_id="probe_ablauf"), {"quelle": "gastseite"})
    assert len(umgebung.speicher.v) == 1
    probe.binde(False)
    entities: dict = {}
    asyncio.run(arbeitsstand.auffrischen(_S(), "sitzung-anders-0123", entities))
    assert arbeitsstand.VERWEIS not in entities


# ── Review AS-8a, Befund 3: Probe ohne Recht läuft nie still als echter Zug ────────────────────

def test_review_3_probe_ohne_recht_wird_abgewiesen():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as fehler:
        probe_anfrage.pruefe_probe(_anfrage("falsch"), _chat(True))
    assert (fehler.value.status_code, fehler.value.detail) == (403, "probe_ohne_recht")
    assert probe_anfrage.pruefe_probe(_anfrage(studio_token(_PASSWORT)), _chat(True)) is True
    assert probe_anfrage.pruefe_probe(_anfrage(None), _chat(False)) is False


def test_review_3_beide_chat_endpunkte_pruefen_die_probe_zuerst():
    import inspect

    from boerdi.api import chat as chat_api

    for endpunkt in (chat_api.chat, chat_api.chat_stream):
        quelle = inspect.getsource(endpunkt)
        assert quelle.index("pruefe_probe(") < quelle.index("uebernimm_zugang(")


# ── Review AS-8a, Befund 4: Rechte nur mit dem Cookie dieses Zuges ─────────────────────────────

def test_review_4_eine_gemerkte_probe_schraenkt_ein_erweitert_aber_nicht():
    probe.binde(False)
    probe.uebernehmen({probe.ENTITY_KEY: True})
    assert probe.aktiv() is True        # Trockenlauf gilt
    assert probe.recht() is False       # aber kein Start ausgeschalteter Abläufe
    probe.binde(True)
    assert probe.recht() is True


def test_review_4_ohne_cookie_im_zug_startet_kein_ausgeschalteter_ablauf(umgebung):  # noqa: F811
    probe.binde(False)
    probe.uebernehmen({probe.ENTITY_KEY: True})
    antwort = _starten(umgebung, _ablauf(ausloeser=("text",)), {"quelle": "gastseite"})
    assert umgebung.speicher.v == {} and "Hallo Probe" not in antwort.content


# ── Review AS-8a, Befund 7: das Einlösen einer Freigabe in der Probe, Ende zu Ende ──────────────

@pytest.mark.asyncio
async def test_review_7_das_einloesen_eines_plans_schreibt_nichts_und_bietet_kein_fortsetzen(
        monkeypatch):
    from boerdi.services import plan_fortsetzen
    from boerdi.services import write_approval as wa_mod
    from tests.test_mcp_vertrag_m5 import _zustand
    from tests.test_write_approval import _SESSION, _req, _Spy

    for modul in (wa_mod, plan_fortsetzen):
        monkeypatch.setattr(modul, "update_session", _Spy())
        monkeypatch.setattr(modul, "save_message", _Spy())
        monkeypatch.setattr(modul, "schreiben_erlaubt", lambda: True)
        monkeypatch.setattr(modul, "aufrufer_kennung", lambda: "person-a")

    async def nie(name, *_a, **_k):
        raise AssertionError(f"{name} darf in der Probe nicht laufen")

    monkeypatch.setattr(mcp_client.transport, "call_tool", nie)
    probe.binde(True)
    zustand = _zustand()
    antwort = await wa_mod.redeem_write_approval(_SESSION, _req(), zustand)
    assert "Trockenlauf" in antwort.content and "wlo_create_collection_tree" in antwort.content
    assert not antwort.quick_replies and antwort.prepared_write is None
    assert plan_fortsetzen.KEY not in zustand["entities"]
    assert zustand["_eingeloest_ergebnis"]["trockenlauf"] is True



# ── Zweites Review AS-8a ───────────────────────────────────────────────────────────────────────

def test_zweites_review_1_der_verweis_traegt_die_marke_der_probe():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from boerdi.services.arbeitsstand_verweis import verweis_fuer

    def v(lauf):
        return SimpleNamespace(id="v-1", titel="T", verfaellt_am=datetime.now(UTC),
                               akte={"lauf": lauf})

    lauf = {"ablauf": "a", "schritt": "s", "status": "wartet_seite", "fassung": "f"}
    assert verweis_fuer(v({**lauf, "probe": True}), "probe:x")["lauf"]["probe"] is True
    assert "probe" not in verweis_fuer(v(lauf), "person-a")["lauf"]
    assert "probe" not in verweis_fuer(v({**lauf, "probe": "ja"}), "person-a")["lauf"]


def test_zweites_review_1_2_ein_ausgeschalteter_ablauf_zeigt_in_der_probe_seine_leiste(
        umgebung):  # noqa: F811
    from boerdi.services import arbeitsstand
    from boerdi.services.ablauf import fortschritt, seite_zug

    probe.binde(True)
    umgebung.katalog["wert"] = {"ablaeufe": [_wartet(aktiv=False, ablauf_id="probe_ablauf")
                                             .model_dump(exclude_none=True)]}
    state: dict = {"entities": {}}
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "probe_ablauf",
                                                     "quelle": "gastseite"})
    asyncio.run(zug.starten(_S(), anfrage, state))
    entities = state["entities"]
    aufrufer = arbeitsstand.aufrufer_fuer(_SITZUNG, entities)
    stand = fortschritt.stand(entities, aufrufer, "de")
    assert stand is not None and stand["status"] == "wartet_seite"
    assert stand["persoenlich"] is False          # Befund 2: die Probe hängt nicht an der Anmeldung
    assert seite_zug.wartend(_SITZUNG, state) is not None
