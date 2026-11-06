"""Paket A1: Abläufe im Zug — Start per Direktaktion, Fortsetzen über die Antwort, Lauf im Vorgang.

Die Datenbank ist durch einen Speicher im Arbeitsspeicher ersetzt (Vorgänge, Teile, Lauf); geprüft
wird der Weg: Katalog → Treiber → Teile/Lauf festhalten → Antwort mit Block → Antwort der Person →
Teil gespeichert → Treiber setzt fort.
"""

from __future__ import annotations

import asyncio
import copy
import pathlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import yaml

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.config_models.ablauf import AblaufKatalogArea
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ausloeser, zug, zug_basis
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

_SEED = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "katalog.yaml"


def _katalog(aktiv=True, **mehr):
    roh = yaml.safe_load(_SEED.read_text(encoding="utf-8"))
    roh["ablaeufe"][0]["aktiv"] = aktiv
    roh["ablaeufe"][0].update(mehr)
    return roh


def test_der_mitgelieferte_ablauf_besteht_die_pruefung():
    katalog = AblaufKatalogArea.model_validate(yaml.safe_load(_SEED.read_text(encoding="utf-8")))
    assert [a.id for a in katalog.ablaeufe] == ["sammlungsstruktur"]
    assert pruefe(katalog.ablaeufe[0]) == []


class _Speicher:
    def __init__(self):
        self.v: dict[str, SimpleNamespace] = {}

    async def lesen(self, s, vid, aufrufer):
        v = self.v.get(vid)
        return copy.deepcopy(v) if v is not None and v.aufrufer == aufrufer else None

    async def juengster(self, s, aufrufer):
        # wie ``vorgaenge.juengster``: nur offene (Querschnitts-Review, M6)
        eigene = [v for v in self.v.values() if v.aufrufer == aufrufer
                  and v.status not in ("fertig", "abgebrochen")]
        return copy.deepcopy(eigene[-1]) if eigene else None

    async def loeschen(self, s, vid, aufrufer):
        if (v := self.v.get(vid)) is not None and v.aufrufer == aufrufer:
            del self.v[vid]

    async def sperren(self, s, vid, aufrufer):
        return None

    async def anonyme_der_sitzung_loeschen(self, s, session_id):
        return await self.alle_loeschen(s, f"sitzung:{session_id}")

    async def alle_loeschen(self, s, aufrufer):
        weg = [k for k, v in self.v.items() if v.aufrufer == aufrufer]
        for vid in weg:
            del self.v[vid]
        return len(weg)

    async def anlegen(self, s, *, aufrufer, session_id, titel, zweck, tage):
        v = SimpleNamespace(id=f"v-{len(self.v) + 1}", aufrufer=aufrufer, titel=titel,
                            status="aktiv",
                            verfaellt_am=datetime.now(UTC) + timedelta(days=3),
                            akte={"teile": {}, "historie": {}, "lauf": None}, akte_version=0)
        self.v[v.id] = v
        return copy.deepcopy(v)

    async def teil_setzen(self, s, v, name, *, typ, wert, zusammenfassung, tage):
        gespeichert = self.v[v.id]
        alt = gespeichert.akte["teile"].get(name, {"version": 0})
        gespeichert.akte["teile"][name] = {"typ": typ, "version": alt["version"] + 1,
                                           "wert": copy.deepcopy(wert),
                                           "zusammenfassung": zusammenfassung}
        return copy.deepcopy(gespeichert)

    async def lauf_setzen(self, s, v, lauf, *, status, tage):
        gespeichert = self.v[v.id]
        gespeichert.akte["lauf"] = copy.deepcopy(lauf)
        gespeichert.status = status
        return copy.deepcopy(gespeichert)

    async def teil_wert(self, s, v, name):
        return (self.v[v.id].akte["teile"].get(name) or {}).get("wert")

    async def beruehren(self, s, vid, *, tage):
        return None


class _S:
    class _Punkt:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

    def begin_nested(self):
        return self._Punkt()

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.fixture
def umgebung(monkeypatch):
    sp = _Speicher()
    for name in ("lesen", "juengster", "anlegen", "teil_setzen", "lauf_setzen", "teil_wert",
                 "beruehren", "loeschen", "alle_loeschen", "sperren",
                 "anonyme_der_sitzung_loeschen"):
        monkeypatch.setattr(vorgaenge, name, getattr(sp, name))
    from boerdi.services.dokumente import ablage as dokumente

    async def kein_dokument(*_a, **_k):
        return 0

    monkeypatch.setattr(dokumente, "der_sitzung_loeschen", kein_dokument)
    for modul in (arbeitsstand, ausloeser):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")
    gesendet: list[str] = []

    async def speichern(session, sid, rolle, text, **_k):
        gesendet.append(text)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(zug_basis, "save_message", speichern)
    monkeypatch.setattr(zug_basis, "update_session", nichts)
    katalog = {"wert": _katalog()}
    monkeypatch.setattr(ausloeser, "area",
                        lambda key: katalog["wert"] if key == ausloeser.BEREICH else {})
    return SimpleNamespace(speicher=sp, gesendet=gesendet, katalog=katalog)


def _req(**mehr):
    return ChatRequest(session_id="sitzung-0123456789", message="", environment=Environment(
        ui_module=[UPLOAD, STRUKTURENTWURF]), **mehr)


def _start(state):
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "sammlungsstruktur"})
    return asyncio.run(zug.starten(_S(), anfrage, state))


def test_der_start_zeigt_das_erste_modul_und_haelt_den_lauf(umgebung):
    state: dict = {"entities": {}}
    antwort = _start(state)
    [block] = antwort.ui.ui_bloecke
    assert block.modul == UPLOAD and "Ordner" in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["schritt"] == "erfassen" and v.status == "wartet_person"
    assert v.akte["lauf"]["offener_block"] == block.block_id
    vw = state["entities"][arbeitsstand.VERWEIS]
    assert vw["lauf"] == {"ablauf": "sammlungsstruktur", "schritt": "erfassen",
                          "status": "wartet_person", "fassung": v.akte["lauf"]["fassung"]}
    assert "Ablauf sammlungsstruktur: Schritt erfassen" in arbeitsstand.kennzeile(
        state["entities"], "person-a")


def test_die_antwort_auf_den_offenen_block_setzt_bis_zum_entwurf_fort(umgebung):
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    geprueft = {"modul": UPLOAD, "block_id": block.block_id, "daten": {
        "aktion": "erfasst",
        "struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2, "kinder": [
            {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
            {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
        "zahlen": {"ordner": 3, "inhalte": 2}}}
    assert asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, geprueft)) is True
    antwort = asyncio.run(zug.fortsetzen(_S(), _req(), state, geprueft))
    [entwurf] = antwort.ui.ui_bloecke
    assert entwurf.modul == STRUKTURENTWURF and entwurf.daten["quelle"] == "ordner"
    [v] = umgebung.speicher.v.values()
    assert set(v.akte["teile"]) == {"structure", "draft"}
    assert v.akte["lauf"]["schritt"] == "bearbeiten"


def test_eine_fremde_antwort_gehoert_nicht_zum_lauf(umgebung):
    state: dict = {"entities": {}}
    _start(state)
    fremd = {"modul": UPLOAD, "block_id": "anderer0001", "daten": {}}
    assert asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, fremd)) is False


def test_ein_ausgeschalteter_ablauf_startet_nicht(umgebung):
    umgebung.katalog["wert"] = _katalog(aktiv=False)
    antwort = _start({"entities": {}})
    assert not antwort.ui.ui_bloecke and umgebung.speicher.v == {}
    assert "ausgeschaltet" in antwort.content


def test_die_voraussetzung_anmeldung(umgebung, monkeypatch):
    umgebung.katalog["wert"] = _katalog(voraussetzungen=["anmeldung"])
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: False)
    antwort = _start({"entities": {}})
    assert "bei WLO an" in antwort.content and umgebung.speicher.v == {}


# ── Review A1: Besitz, abgebrochene Läufe, Konflikt, Ordner-Knopf, Voraussetzungen, Fehler ──────

def _geprueft(block, aktion="ordner_als_entwurf"):
    return {"modul": UPLOAD, "block_id": block.block_id, "daten": {
        "aktion": aktion,
        "struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2, "kinder": [
            {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
            {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
        "zahlen": {"ordner": 3, "inhalte": 2}}}


def test_der_ordner_knopf_setzt_den_lauf_fort(umgebung):
    """Befund 1: der Hauptknopf von ui_upload (``ordner_als_entwurf``) gehört zum Lauf."""
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    antwort = asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block)))
    assert antwort.ui.ui_bloecke[0].modul == STRUKTURENTWURF


def test_eine_andere_person_setzt_den_lauf_nicht_fort(umgebung, monkeypatch):
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-b")
    assert asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, _geprueft(block))) is False
    assert asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block))) is None


def test_ein_ausgeschalteter_ablauf_bricht_den_wartenden_lauf_ab(umgebung):
    """Befund 5: aus = kein Fortsetzen; der Lauf wird ``abgebrochen``, die Antwort geht den
    gewöhnlichen Weg (nichts schon gespeichert)."""
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    umgebung.katalog["wert"] = _katalog(aktiv=False)
    assert asyncio.run(zug.wartet_auf(_S(), "sitzung-0123456789", state, _geprueft(block))) is False
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen" and "structure" not in v.akte["teile"]
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == "abgebrochen"
    assert asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block))) is None


def test_ein_inzwischen_bewegter_lauf_wird_nicht_ueberschrieben(umgebung, monkeypatch):
    """Befund 7: nach dem Übernehmen gehört der offene Block nicht mehr zu dieser Antwort."""
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    echt = arbeitsstand.uebernehmen

    async def uebernehmen_und_bewegen(session, sid, entities, geprueft, **_k):
        await echt(session, sid, entities, geprueft)
        [v] = umgebung.speicher.v.values()
        v.akte["lauf"] = {**v.akte["lauf"], "schritt": "bearbeiten", "offener_block": "neu0001"}

    monkeypatch.setattr(arbeitsstand, "uebernehmen", uebernehmen_und_bewegen)
    antwort = asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block)))
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    assert not (antwort.ui and antwort.ui.ui_bloecke)
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["offener_block"] == "neu0001"


def test_eine_unbekannte_voraussetzung_startet_nicht(umgebung):
    """Befund 8: was das Studio nicht kennt, gilt als nicht erfüllt."""
    umgebung.katalog["wert"] = _katalog(voraussetzungen=["login"])
    antwort = _start({"entities": {}})
    assert not (antwort.ui and antwort.ui.ui_bloecke) and umgebung.speicher.v == {}


def test_ein_fehler_des_treibers_endet_mit_hinweis(umgebung, monkeypatch):
    """Befund 11: kein 500, kein angelegter Vorgang."""
    async def kaputt(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(zug.treiber, "starten", kaputt)
    antwort = _start({"entities": {}})
    assert "nicht weiter" in antwort.content and umgebung.speicher.v == {}


def test_texte_und_fehlerhinweis_zusammen():
    from boerdi.services.ablauf import treiber

    aus = treiber.Ausgabe(lauf={"status": "fehler"}, texte=["Los."], fehler="x")
    text = zug_basis.antwort_text("de", aus)
    assert text.startswith("Los.") and "nicht weiter" in text
    fertig = treiber.Ausgabe(lauf={"status": "fertig"})
    assert zug_basis.antwort_text("de", fertig) == bot_text("de", "action.ablauf.fertig")


# ── Paket A2a: Start über eine Modul-Antwort und über eine Wendung ─────────────────────────────

def test_eine_modul_antwort_startet_den_ablauf_nach_dem_modul(umgebung):
    """Auslöser ``modul``: die Antwort wird erst Teil, dann rechnet der Treiber ab ``entwurf``."""
    umgebung.katalog["wert"] = _katalog(ausloeser=[{"art": "modul", "modul": UPLOAD,
                                                    "wenn_teil": "structure"}])
    state: dict = {"entities": {}}
    geprueft = {"modul": UPLOAD, "block_id": "fremd0001", "daten": _geprueft_daten()}
    treffer = zug.modul_ausloeser(geprueft)
    assert treffer is not None
    antwort = asyncio.run(zug.per_modul_starten(_S(), _req(), state, geprueft, treffer))
    assert antwort.ui.ui_bloecke[0].modul == STRUKTURENTWURF
    [v] = umgebung.speicher.v.values()
    assert set(v.akte["teile"]) == {"structure", "draft"}
    assert v.akte["lauf"]["schritt"] == "bearbeiten"


def test_der_modul_ausloeser_braucht_die_voraussetzung(umgebung, monkeypatch):
    umgebung.katalog["wert"] = _katalog(ausloeser=[{"art": "modul", "modul": UPLOAD}],
                                        voraussetzungen=["anmeldung"])
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: False)
    geprueft = {"modul": UPLOAD, "block_id": "b", "daten": _geprueft_daten()}
    assert zug.modul_ausloeser(geprueft) is None


def test_eine_wendung_startet_den_ablauf(umgebung):
    umgebung.katalog["wert"] = _katalog(ausloeser=[{"art": "text",
                                                    "wendungen": ["themenbaum aus meinem ordner"]}])
    ablauf = zug.text_ausloeser("Bitte einen Themenbaum aus meinem Ordner")
    assert ablauf is not None and zug.text_ausloeser("Hallo") is None
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), {"entities": {}}, ablauf))
    assert antwort.ui.ui_bloecke[0].modul == UPLOAD


def _geprueft_daten():
    return {"aktion": "erfasst", "struktur": {
        "name": "Physik", "dateien": 0, "alle_dateien": 2, "kinder": [
            {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
            {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
        "zahlen": {"ordner": 3, "inhalte": 2}}


# ── Review A2a: Knopf nur mit Auslöser knopf/agent; Modul-Start folgt ``weiter`` und der Wahl ────

def test_der_knopf_startet_nur_einen_ablauf_mit_knopf_oder_ki_ausloeser(umgebung):
    umgebung.katalog["wert"] = _katalog(ausloeser=[{"art": "text", "wendungen": ["themenbaum x"]}])
    antwort = _start({"entities": {}})
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")
    assert umgebung.speicher.v == {}


# ── Paket A2b: „Weiter im Ablauf“ am agent-Schritt ────────────────────────────────────────────

_AGENT_KATALOG = {"schritte": [
    {"id": "erfassen", "typ": "modul", "modul": UPLOAD, "daten": {"zweck": "sammlungsstruktur"}},
    {"id": "umbau", "typ": "agent", "text": {"de": "Jetzt gemeinsam umbauen."},
     "agent": {"werkzeuge": ["search_wlo_all"], "ausgabe": "structure"}},
    {"id": "ende", "typ": "ende", "text": {"de": "Geschafft."}}]}


def test_weiter_am_agent_schritt_setzt_den_lauf_fort(umgebung):
    umgebung.katalog["wert"] = _katalog(**_AGENT_KATALOG)
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    antwort = asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block, "erfasst")))
    assert "gemeinsam umbauen" in antwort.content
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == "wartet_ki"
    weiter = _req(action=zug.AKTION_WEITER, action_params={"ablauf": "sammlungsstruktur"})
    antwort = asyncio.run(zug.weiter_nach_ki(_S(), weiter, state))
    assert antwort.content == "Geschafft."
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fertig"


def test_weiter_ohne_ausgabe_bleibt_mit_hinweis(umgebung):
    umgebung.katalog["wert"] = _katalog(**{**_AGENT_KATALOG, "schritte": [
        _AGENT_KATALOG["schritte"][1] | {"agent": {"werkzeuge": ["search_wlo_all"],
                                                   "ausgabe": "draft"}},
        _AGENT_KATALOG["schritte"][2]]})
    state: dict = {"entities": {}}
    _start(state)
    weiter = _req(action=zug.AKTION_WEITER, action_params={"ablauf": "sammlungsstruktur"})
    antwort = asyncio.run(zug.weiter_nach_ki(_S(), weiter, state))
    assert antwort.content == bot_text("de", "action.ablauf.fehltNoch")
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_ki"


def test_weiter_fuer_einen_anderen_oder_keinen_lauf(umgebung):
    umgebung.katalog["wert"] = _katalog(**_AGENT_KATALOG)
    state: dict = {"entities": {}}
    weiter = _req(action=zug.AKTION_WEITER, action_params={"ablauf": "sammlungsstruktur"})
    assert asyncio.run(zug.weiter_nach_ki(_S(), weiter, state)).content == bot_text(
        "de", "action.ablauf.unbekannt")
    _start(state)     # wartet am Modul, nicht am agent-Schritt
    assert asyncio.run(zug.weiter_nach_ki(_S(), weiter, state)).content == bot_text(
        "de", "action.ablauf.unbekannt")
    assert zug.lauf_wartet("sitzung-0123456789", state)



def test_weiter_nach_dem_ausschalten_bricht_den_lauf_ab(umgebung):
    """Review A2b, Befund 7: ein Lauf, der nicht mehr kann, blockiert die Person nicht weiter."""
    umgebung.katalog["wert"] = _katalog(**{**_AGENT_KATALOG, "schritte": _AGENT_KATALOG[
        "schritte"][1:]})
    state: dict = {"entities": {}}
    _start(state)
    umgebung.katalog["wert"] = _katalog(aktiv=False, **{**_AGENT_KATALOG, "schritte":
                                                         _AGENT_KATALOG["schritte"][1:]})
    weiter = _req(action=zug.AKTION_WEITER, action_params={"ablauf": "sammlungsstruktur"})
    antwort = asyncio.run(zug.weiter_nach_ki(_S(), weiter, state))
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert not zug.lauf_wartet("sitzung-0123456789", state)


def test_ein_neuer_lauf_zaehlt_seine_ki_zuege_neu(umgebung):
    """Review A2b, Befund 4."""
    from boerdi.services.ablauf import ki_schritt

    state: dict = {"entities": {ki_schritt.ZUEGE_KEY: {"schritt": "sammlungsstruktur/umbau",
                                                        "zuege": 9}}}
    _start(state)
    assert ki_schritt.ZUEGE_KEY not in state["entities"]
