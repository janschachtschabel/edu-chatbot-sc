"""Paket A1: Abläufe im Zug — Start per Direktaktion, Fortsetzen über die Antwort, Lauf im Vorgang.

Die Datenbank ist durch einen Speicher im Arbeitsspeicher ersetzt (Vorgänge, Teile, Lauf); geprüft
wird der Weg: Katalog → Treiber → Teile/Lauf festhalten → Antwort mit Block → Antwort der Person →
Teil gespeichert → Treiber setzt fort.
"""

from __future__ import annotations

import asyncio
import copy
import json
import pathlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import yaml

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ausloeser, wahl_zug, zug, zug_basis
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

#: Plan 2026-11-20, G1: der kleine Ordner-Ablauf ist kein Werks-Seed mehr — die Tests der
#: Ablauf-Maschine nehmen ihn als eingefrorenes Beispiel (``tests/ablauf_beispiele``).
_SEED = pathlib.Path(__file__).parent / "ablauf_beispiele" / "sammlungsstruktur.yaml"


def _katalog(aktiv=True, **mehr):
    """Der Beispiel-Ablauf (seit AS-0 ein Dokument) in der Form ``{ablaeufe: [...]}``, die die
    Tests der Laufzeit unterschieben (``ausloeser._roh_liste``)."""
    roh = yaml.safe_load(_SEED.read_text(encoding="utf-8"))
    roh["aktiv"] = aktiv
    roh.update(mehr)
    return {"ablaeufe": [roh]}


def test_der_beispiel_ablauf_besteht_die_pruefung():
    ablauf = AblaufArea.model_validate(yaml.safe_load(_SEED.read_text(encoding="utf-8")))
    assert ablauf.id == "sammlungsstruktur" == _SEED.stem
    assert pruefe(ablauf) == []


class _Speicher:
    def __init__(self):
        self.v: dict[str, SimpleNamespace] = {}

    async def lesen(self, s, vid, aufrufer):
        v = self.v.get(vid)
        return copy.deepcopy(v) if v is not None and v.aufrufer == aufrufer else None

    async def loeschen(self, s, vid, aufrufer):
        if (v := self.v.get(vid)) is not None and v.aufrufer == aufrufer:
            del self.v[vid]

    async def sperren(self, s, vid, aufrufer):
        return None

    async def alle_sperren(self, s, aufrufer):
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
                            status="aktiv", session_id=session_id,
                            verfaellt_am=datetime.now(UTC) + timedelta(days=3),
                            akte={"teile": {}, "historie": {}, "lauf": None}, akte_version=0)
        self.v[v.id] = v
        return copy.deepcopy(v)

    async def sitzung_setzen(self, s, vid, session_id):
        if vid in self.v:
            self.v[vid].session_id = session_id

    async def teil_setzen(self, s, v, name, *, typ, wert, zusammenfassung, tage):
        gespeichert = self.v[v.id]
        alt = gespeichert.akte["teile"].get(name, {"version": 0})
        gespeichert.akte["teile"][name] = {"typ": typ, "version": alt["version"] + 1,
                                           "wert": copy.deepcopy(wert),
                                           "zusammenfassung": zusammenfassung}
        return copy.deepcopy(gespeichert)

    async def teil_entfernen(self, s, v, name, *, tage):
        gespeichert = self.v[v.id]
        gespeichert.akte["teile"].pop(name, None)
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
    for name in ("lesen", "anlegen", "teil_setzen", "teil_entfernen",
                 "lauf_setzen", "teil_wert",
                 "beruehren", "loeschen", "alle_loeschen", "sperren", "alle_sperren",
                 "anonyme_der_sitzung_loeschen", "sitzung_setzen"):
        monkeypatch.setattr(vorgaenge, name, getattr(sp, name))
    from boerdi.services.dokumente import ablage as dokumente

    async def kein_dokument(*_a, **_k):
        return 0

    monkeypatch.setattr(dokumente, "der_sitzung_loeschen", kein_dokument)
    from boerdi.services.auftraege import ablage as auftraege_ablage

    async def keine_auftraege(*_a, **_k):
        return []

    monkeypatch.setattr(auftraege_ablage, "offene_job_ids", keine_auftraege)
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
    monkeypatch.setattr(ausloeser, "_roh_liste",
                        lambda: (katalog["wert"]).get("ablaeufe") or [])
    return SimpleNamespace(speicher=sp, gesendet=gesendet, katalog=katalog)


def _req(**mehr):
    return ChatRequest(session_id="sitzung-0123456789", message="", environment=Environment(
        ui_module=[UPLOAD, STRUKTURENTWURF]), **mehr)


def _ja(antwort, state):
    """TW-6: der Ablauf fragt zuerst (``einstieg``) — „Ja, Ordner wählen“ führt zum Upload-Feld.
    Ohne die Frage (kein Start) bleibt die Antwort, wie sie ist."""
    for chip in antwort.quick_replies:
        _praefix, _label, aktion, params = chip.split("|", 3)
        if aktion == wahl_zug.AKTION and json.loads(params)["wahl"] == "ja":
            return asyncio.run(wahl_zug.waehlen(
                _S(), _req(action=wahl_zug.AKTION, action_params=json.loads(params)), state))
    return antwort


def _start(state):
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "sammlungsstruktur"})
    return _ja(asyncio.run(zug.starten(_S(), anfrage, state)), state)


def test_der_start_zeigt_das_erste_modul_und_haelt_den_lauf(umgebung):
    state: dict = {"entities": {}}
    antwort = _start(state)
    [block] = antwort.ui.ui_bloecke
    assert block.modul == UPLOAD and "Ordner" in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["schritt"] == "erfassen" and v.status == "wartet_person"
    assert v.akte["lauf"]["offener_block"] == block.block_id
    vw = state["entities"][arbeitsstand.VERWEIS]
    # ``start``: Marke des Laufs für die Leiste im Widget (zweites Review AS-U, Befund 2)
    assert vw["lauf"] == {"ablauf": "sammlungsstruktur", "schritt": "erfassen",
                          "status": "wartet_person", "fassung": v.akte["lauf"]["fassung"],
                          "start": v.akte["lauf"]["start"], "freigabe_id": "",
                          # Plan 2026-11-16, Review TG-4–6, Befund 10: Einstieg und Upload-Feld
                          # sind zwei Halte — die Leiste zählt daraus
                          "halte": 2}
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
    # ``bereit``: was zu Beginn nutzbar bereitlag (zweites Review TG-2)
    assert set(v.akte["teile"]) == {"bereit", "structure", "draft"}
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

def _geprueft(block, aktion="erfasst"):
    return {"modul": UPLOAD, "block_id": block.block_id, "daten": {
        "aktion": aktion,
        "struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2, "kinder": [
            {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
            {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
        "zahlen": {"ordner": 3, "inhalte": 2}}}


def test_der_ordner_knopf_setzt_den_lauf_fort(umgebung):
    """Befund 1: der Hauptknopf von ui_upload („Senden“, seit TG-2 auch der alte
    ``ordner_als_entwurf`` nach der Prüfung) gehört zum Lauf."""
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
    state: dict = {"entities": {}}
    antwort = asyncio.run(zug.starten_mit(_S(), _req(), state, ablauf))
    assert "Einverstanden?" in antwort.content and not antwort.ui.ui_bloecke   # TW-6: Einstieg
    assert _ja(antwort, state).ui.ui_bloecke[0].modul == UPLOAD


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


# ── Zweites Review TG-2: freie Arbeit nach einem beendeten Lauf, Übernahme, „Andere wählen“ ──────

_DOK_SEED = _SEED.with_name("themenbaum_aus_dokument.yaml")
_UPLOAD_ID = "11111111-1111-4111-8111-111111111111"
_ORDNER = {"aktion": "erfasst", "struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2,
                                           "kinder": [
    {"name": "01_Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
    {"name": "02_Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
    "zahlen": {"ordner": 3, "inhalte": 2}}


def _wahl(antwort, state, wahl):
    """Den Chip ``wahl`` der Antwort drücken (wie das Widget)."""
    for chip in antwort.quick_replies:
        _praefix, _label, aktion, params = chip.split("|", 3)
        if aktion == wahl_zug.AKTION and json.loads(params)["wahl"] == wahl:
            return asyncio.run(wahl_zug.waehlen(
                _S(), _req(action=wahl_zug.AKTION, action_params=json.loads(params)), state))
    raise AssertionError(f"kein Chip {wahl}: {antwort.quick_replies}")


def _wahlen(antwort) -> set[str]:
    return {json.loads(chip.split("|", 3)[3])["wahl"] for chip in antwort.quick_replies
            if chip.split("|", 3)[2] == wahl_zug.AKTION}


def _starte(state, ablauf_id):
    return asyncio.run(zug.starten(
        _S(), _req(action=zug.AKTION, action_params={"ablauf": ablauf_id}), state))


def test_zweites_review_m2_freie_arbeit_nach_beendetem_lauf_wird_uebernommen(umgebung):
    """MAJOR 2, nach der Nachprüfung: ein Lauf endet (hier: „Ohne Führung“), danach erfasst die
    Person im freien Chat Ordner — sie landen im selben Vorgang (wie vor der zweiten Behebung). Der
    nächste Start schließt ihn und übernimmt die Bereitstellungs-Teile in den neuen; kein
    ``draft``, kein Lauf, keine Antworten des alten."""
    state: dict = {"entities": {}}
    _wahl(_starte(state, "sammlungsstruktur"), state, "ohne")
    [alt] = umgebung.speicher.v.values()
    assert alt.akte["lauf"]["status"] == "fertig"
    assert asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                                {"modul": UPLOAD, "block_id": "b1",
                                                 "daten": _ORDNER}))
    assert list(umgebung.speicher.v) == ["v-1"] and "structure" in alt.akte["teile"]
    antwort = _starte(state, "sammlungsstruktur")
    alt, neu = umgebung.speicher.v["v-1"], umgebung.speicher.v["v-2"]
    assert alt.status == "fertig"
    assert set(neu.akte["teile"]) == {"structure", "bereit"}
    assert neu.akte["teile"]["structure"]["wert"] == alt.akte["teile"]["structure"]["wert"]
    assert state["entities"][arbeitsstand.VERWEIS]["id"] == "v-2"
    assert _wahlen(antwort) == {"verwenden", "andere", "ohne"}
    assert "„Physik“" in antwort.content
    entwurf = _wahl(antwort, state, "verwenden")
    assert entwurf.ui.ui_bloecke[0].modul == STRUKTURENTWURF


def test_zweites_review_m2_ein_wartender_lauf_nimmt_die_freie_arbeit_weiter_auf(umgebung):
    """Gegenprobe: nur ein BEENDETER Lauf trennt; ohne Lauf bleibt alles in einem Vorgang."""
    state: dict = {"entities": {}}
    for _ in range(2):
        asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                             {"modul": UPLOAD, "block_id": "b1",
                                              "daten": _ORDNER}))
    assert list(umgebung.speicher.v) == ["v-1"]


def _dokument_umgebung(umgebung, monkeypatch, lesbar=_UPLOAD_ID):
    umgebung.katalog["wert"] = {"ablaeufe": [{**yaml.safe_load(
        _DOK_SEED.read_text(encoding="utf-8")), "aktiv": True}]}

    async def bestaetigt(s, session_id, wert, *_merk):
        return ({"ref": f"dokument:{wert['upload_id']}", "name": wert["name"], "format": "pdf",
                 "befund": {}}, "Lehrplan")

    async def lesbares(s, session_id):
        return lesbar

    monkeypatch.setattr(arbeitsstand, "_dokument_bestaetigt", bestaetigt)
    monkeypatch.setattr(arbeitsstand, "lesbares_dokument", lesbares)


def _dokument_antwort(block_id="b1", upload_id=_UPLOAD_ID):
    return {"modul": UPLOAD, "block_id": block_id, "daten": {
        "aktion": "dokument", "struktur": {"name": "", "dateien": 1, "alle_dateien": 1,
                                           "kinder": []},
        "zahlen": {"ordner": 0, "inhalte": 0, "strukturdokumente": 1},
        "dokument": {"upload_id": upload_id, "name": "Lehrplan.pdf", "format": "pdf",
                     "befund": {"abschnitte": 3}, "vorschau": []}}}


def test_zweites_review_m2_dokument_nach_beendetem_lauf_wird_angeboten(umgebung, monkeypatch):
    """MAJOR 2 mit „aus einem Dokument“: Ablauf beendet → Dokument im freien Chat gelesen → Start
    → die Frage nennt das Dokument und bietet es an."""
    _dokument_umgebung(umgebung, monkeypatch)
    state: dict = {"entities": {}}
    _wahl(_starte(state, "themenbaum_aus_dokument"), state, "ohne")
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                         _dokument_antwort()))
    antwort = _starte(state, "themenbaum_aus_dokument")
    assert _wahlen(antwort) == {"verwenden", "andere", "ohne"}
    assert "Lehrplan" in antwort.content


def test_zweites_review_m5_ein_unlesbares_dokument_wird_nicht_angeboten(umgebung, monkeypatch):
    """MINOR 5: das Dokument einer anderen Sitzung (oder abgelaufen) ist nicht lesbar — dann der
    gewöhnliche Einstieg."""
    _dokument_umgebung(umgebung, monkeypatch, lesbar=None)
    state: dict = {"entities": {}}
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                         _dokument_antwort()))
    assert _wahlen(_starte(state, "themenbaum_aus_dokument")) == {"fragen", "gleich", "ohne"}


def test_zweites_review_m1_andere_waehlen_verwirft_das_alte_dokument(umgebung, monkeypatch):
    """MAJOR 1: „Anderes wählen“ entfernt das alte Dokument aus dem Vorgang; schickt die Person
    danach nur „Senden“, kommt die Rückfrage — nicht still der Entwurf aus dem alten."""
    _dokument_umgebung(umgebung, monkeypatch)
    state: dict = {"entities": {}}
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                         _dokument_antwort()))
    upload = _wahl(_starte(state, "themenbaum_aus_dokument"), state, "andere")
    [v] = umgebung.speicher.v.values()
    assert "document" not in v.akte["teile"]
    assert "document" not in state["entities"][arbeitsstand.VERWEIS]["teile"]
    block = upload.ui.ui_bloecke[0]
    nur_senden = {"modul": UPLOAD, "block_id": block.block_id, "daten": {
        **_ORDNER, "struktur": {"name": "", "dateien": 1, "alle_dateien": 1, "kinder": []}}}
    antwort = asyncio.run(zug.fortsetzen(_S(), _req(), state, nur_senden))
    assert umgebung.speicher.v[v.id].akte["lauf"]["schritt"] == "ohne_dokument"
    assert _wahlen(antwort) == {"nochmal", "beenden"}


# ── Nachprüfung TG-2: Übernahme beim Start statt Trennung beim Speichern (Fälle 1–4) ─────────────

def _beide_ablaeufe(umgebung):
    umgebung.katalog["wert"] = {"ablaeufe": [
        {**yaml.safe_load(_SEED.read_text(encoding="utf-8")), "aktiv": True},
        {**yaml.safe_load(_DOK_SEED.read_text(encoding="utf-8")), "aktiv": True}]}


def test_nachpruefung_fall3_upload_waehrend_fremdem_lauf_geht_beim_start_mit(umgebung,
                                                                             monkeypatch):
    """Fall 3: ein anderer Ablauf wartet (hier „aus Ordnern“ am Einstieg); im freien Chat liest die
    Person ein Dokument — es landet in dessen Vorgang. Startet sie „aus einem Dokument“, schließt
    der Start den fremden Vorgang und übernimmt das Dokument (als Verweis auf das
    Sitzungsdokument); der Einstieg bietet es an."""
    _dokument_umgebung(umgebung, monkeypatch)
    _beide_ablaeufe(umgebung)
    state: dict = {"entities": {}}
    _starte(state, "sammlungsstruktur")                       # wartet auf die Wahl
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                         _dokument_antwort()))
    antwort = _starte(state, "themenbaum_aus_dokument")
    assert _wahlen(antwort) == {"verwenden", "andere", "ohne"}
    alt, neu = umgebung.speicher.v["v-1"], umgebung.speicher.v["v-2"]
    assert alt.status == "fertig" and alt.akte["lauf"]["status"] == "abgebrochen"
    dok = neu.akte["teile"]["document"]["wert"]
    assert dok["ref"] == f"dokument:{_UPLOAD_ID}" and dok["name"] == "Lehrplan.pdf"


def test_nachpruefung_fall1_ein_fremder_wartender_lauf_bleibt_unberuehrt(umgebung):
    """Fall 1 (zwei Tabs derselben Person): Tab A wartet in „aus Ordnern“; Tab B erfasst im freien
    Chat Ordner. Seit Plan 2026-11-20, Entscheid E-F übernimmt ein neues Gespräch keinen Vorgang
    still: Tab B bekommt einen eigenen Vorgang. Der Lauf von Tab A bleibt, wo er war."""
    tab_a: dict = {"entities": {}}
    _starte(tab_a, "sammlungsstruktur")
    vorher = copy.deepcopy(umgebung.speicher.v["v-1"].akte["lauf"])
    tab_b: dict = {}
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-zweiter-tab-01", tab_b,
                                         {"modul": UPLOAD, "block_id": "b9", "daten": _ORDNER}))
    assert list(umgebung.speicher.v) == ["v-1", "v-2"]      # E-F: eigener Vorgang für Tab B
    assert umgebung.speicher.v["v-1"].akte["lauf"] == vorher


def test_nachpruefung_fall2_entwurf_nach_dem_ende_bleibt_im_selben_vorgang(umgebung):
    """Fall 2 (M6): nach dem Ende bearbeitet die Person den Entwurf im freien Chat weiter — er
    bleibt im selben Vorgang bei seiner Quelle, nichts wird getrennt."""
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    entwurf = asyncio.run(zug.fortsetzen(_S(), _req(), state, {
        "modul": UPLOAD, "block_id": block.block_id, "daten": _ORDNER})).ui.ui_bloecke[0]
    daten = {**entwurf.daten, "uebernommen": True}
    asyncio.run(zug.fortsetzen(_S(), _req(), state, {
        "modul": STRUKTURENTWURF, "block_id": entwurf.block_id, "daten": daten}))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fertig"
    weiter = {**daten, "titel": "Physik, überarbeitet"}
    asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                         {"modul": STRUKTURENTWURF, "block_id": "frei1",
                                          "daten": weiter}))
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["draft"]["wert"]["titel"] == "Physik, überarbeitet"
    assert "structure" in v.akte["teile"]


def test_nachpruefung_fall4_die_zahl_der_vorgaenge_steigt_nur_beim_start(umgebung):
    """Fall 4: freie Arbeit legt keinen Vorgang an, solange einer da ist — nur ein Start, der einen
    beendeten oder fremden schließt (wie vor der zweiten Behebung)."""
    state: dict = {"entities": {}}
    _wahl(_starte(state, "sammlungsstruktur"), state, "ohne")
    for block in ("b1", "b2", "b3"):
        asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                             {"modul": UPLOAD, "block_id": block,
                                              "daten": _ORDNER}))
    assert len(umgebung.speicher.v) == 1


def test_nachpruefung_uebernommen_wird_nur_was_es_gibt_und_nur_bereitstellung(umgebung):
    """Nur Bereitstellungs-Teile (``arbeitsstand_teile.BEREITSTELLUNG``), nur die vorhandenen: kein
    ``draft``, kein ``document`` ohne Dokument, keine Antworten des alten Laufs."""
    from boerdi.services.arbeitsstand_teile import BEREITSTELLUNG

    # Plan 2026-11-16, TG-3a: dazu die Auswahl mit Dateien (``struktur``); TG-3d die Verweise auf
    # die Strukturdokumente (``strukturdokument``)
    assert set(BEREITSTELLUNG) == {"structure", "struktur", "document", "strukturdokument"}
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    asyncio.run(zug.fortsetzen(_S(), _req(), state, {
        "modul": UPLOAD, "block_id": block.block_id, "daten": _ORDNER}))
    alt = umgebung.speicher.v["v-1"]
    assert {"structure", "draft"} <= set(alt.akte["teile"])
    _beide_ablaeufe(umgebung)
    umgebung.katalog["wert"]["ablaeufe"][1]["voraussetzungen"] = []
    _starte(state, "themenbaum_aus_dokument")                  # ein anderer Ablauf: neuer Vorgang
    neu = umgebung.speicher.v["v-2"]
    assert set(neu.akte["teile"]) == {"structure", "bereit"}


def test_tg3a_die_auswahl_mit_dateien_geht_beim_start_mit(umgebung):
    """Plan 2026-11-16, TG-3a: eine Antwort mit Dateien je Ordner hinterlässt ``struktur`` neben
    ``structure`` — ein neuer Vorgang übernimmt beide (``BEREITSTELLUNG``)."""
    datei = {"i": 0, "name": "hebel.pdf", "endung": "pdf", "groesse": 5, "rolle": "inhalt"}
    kinder = _ORDNER["struktur"]["kinder"]
    mit = {**_ORDNER, "struktur": {**_ORDNER["struktur"], "dateiliste": [], "kinder": [
        {**k, "dateiliste": [{**datei, "i": n}]} for n, k in enumerate(kinder)]},
        "zahlen": {"ordner": 3, "dateien": 2, "inhalte": 2, "ignoriert": 0, "strukturdokumente": 0,
                   "bytes": 10},
        "strukturdokument": None, "warnungen": []}
    state: dict = {"entities": {}}
    block = _start(state).ui.ui_bloecke[0]
    asyncio.run(zug.fortsetzen(_S(), _req(), state, {
        "modul": UPLOAD, "block_id": block.block_id, "daten": mit}))
    alt = umgebung.speicher.v["v-1"]
    assert {"structure", "struktur"} <= set(alt.akte["teile"])
    _beide_ablaeufe(umgebung)
    umgebung.katalog["wert"]["ablaeufe"][1]["voraussetzungen"] = []
    _starte(state, "themenbaum_aus_dokument")
    neu = umgebung.speicher.v["v-2"]
    assert set(neu.akte["teile"]) == {"structure", "struktur", "bereit"}
    assert neu.akte["teile"]["struktur"]["typ"] == "wlo.auswahl@1"
