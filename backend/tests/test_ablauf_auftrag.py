"""Paket K1a: der Schritt ``auftrag`` — ein b-api-Auftrag (Kestra-Flow) im Ablauf.

Der Treiber startet den Flow über die Umgebung (nur mit Anmeldung, nur freigeschaltete Flows) und
hält an (``wartet_auftrag``); die Job-ID liegt in ``vorgang_auftraege``. „Stand prüfen“
(``ablauf_auftrag_pruefen``) fragt im Zug der Person ab: läuft noch → Hinweis; fertig → die Ausgaben
werden Teil ``schreibt``, der Treiber setzt fort; Fehler → ``bei_fehler`` oder Ende mit Hinweis.
"""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgaenge, vorgang_aktion
from boerdi.services.ablauf import auftrag_zug, ausloeser, treiber, zug, zug_basis
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.services.auftraege import ablage, client
from boerdi.settings import get_settings
from tests.test_ablauf_zug import _S, _req, _Speicher

_SCHRITTE = [
    {"id": "lesen", "typ": "auftrag", "flow": "wlo/volltext",
     "argumente": {"dokument": {"$teil": "document"}}, "schreibt": "volltext",
     "bei_fehler": "schade", "text": {"de": "Ich lasse das Dokument lesen."}},
    {"id": "fertig", "typ": "ende", "text": {"de": "Gelesen."}},
    {"id": "schade", "typ": "ende", "text": {"de": "Das Lesen hat nicht geklappt."}},
]


def _roh(**mehr):
    return {"id": "lesen", "titel": {"de": "Lesen"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
            "voraussetzungen": ["anmeldung"], "schritte": copy.deepcopy(_SCHRITTE), **mehr}


@pytest.fixture
def freigeschaltet(monkeypatch):
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/flows/{flow}/jobs")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Prüfung ─────────────────────────────────────────────────────────────────────────────────

def test_ein_gueltiger_auftrag_schritt(freigeschaltet):
    assert pruefe(AblaufArea.model_validate(_roh())) == []


@pytest.mark.parametrize(("aenderung", "erwartet"), [
    ({"flow": None}, "Flow"),
    ({"flow": "wlo/nicht-frei"}, "freigeschaltet"),
    ({"schreibt": None}, "Ergebnis"),
])
def test_befunde_am_auftrag_schritt(freigeschaltet, aenderung, erwartet):
    roh = _roh()
    roh["schritte"][0].update(aenderung)
    befunde = pruefe(AblaufArea.model_validate(roh))
    assert any(erwartet in b for b in befunde), befunde


def test_ein_auftrag_braucht_die_anmeldung(freigeschaltet):
    befunde = pruefe(AblaufArea.model_validate(_roh(voraussetzungen=[])))
    assert any("Anmeldung" in b for b in befunde), befunde


def test_ohne_einrichtung_ist_jeder_flow_ein_befund(monkeypatch):
    monkeypatch.delenv("B_API_JOBS_START_PATH", raising=False)
    get_settings.cache_clear()
    assert any("freigeschaltet" in b for b in pruefe(AblaufArea.model_validate(_roh())))


# ── Treiber ────────────────────────────────────────────────────────────────────────────────

def _umgebung(teile=None, job="job-1"):
    teile = teile or {}
    gestartet: list = []

    async def lader(name):
        return teile.get(name)

    async def starte(flow, args):
        gestartet.append((flow, args))
        return job

    return treiber.Umgebung(teile=lader, auftrag_starten=starte), gestartet


def test_der_treiber_startet_den_auftrag_und_haelt_an():
    ablauf = AblaufArea.model_validate(_roh())
    umgebung, gestartet = _umgebung({"document": {"upload_id": "u1"}})
    aus = asyncio.run(treiber.starten(ablauf, umgebung))
    assert gestartet == [("wlo/volltext", {"dokument": {"upload_id": "u1"}})]
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG and aus.lauf["schritt"] == "lesen"
    assert aus.auftrag == {"flow": "wlo/volltext", "job_id": "job-1", "schritt": "lesen"}
    assert aus.texte == ["Ich lasse das Dokument lesen."]


def test_ohne_start_oder_ohne_teil_geht_es_zu_bei_fehler():
    ablauf = AblaufArea.model_validate(_roh())
    ohne_teil, gestartet = _umgebung()
    aus = asyncio.run(treiber.starten(ablauf, ohne_teil))
    assert gestartet == [] and aus.texte[-1] == "Das Lesen hat nicht geklappt."
    abgelehnt, _ = _umgebung({"document": {"upload_id": "u1"}}, job=None)
    assert asyncio.run(treiber.starten(ablauf, abgelehnt)).texte[-1] == \
        "Das Lesen hat nicht geklappt."
    keiner = treiber.Umgebung(teile=ohne_teil.teile)
    assert asyncio.run(treiber.starten(ablauf, keiner)).texte[-1] == \
        "Das Lesen hat nicht geklappt."


def test_ein_fertiger_auftrag_wird_teil_und_der_lauf_geht_weiter():
    ablauf = AblaufArea.model_validate(_roh())
    umgebung, _ = _umgebung({"document": {"upload_id": "u1"}})
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    ergebnis = {"outputs": {"markdown": "# T"}, "dateien": []}
    aus = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, ergebnis, umgebung))
    assert aus.texte == ["Gelesen."] and aus.lauf["status"] == "fertig"
    [(name, typ, wert, _z)] = aus.neue_teile
    assert (name, typ, wert) == ("volltext", "wlo.auftrag@1", ergebnis)


def test_ein_gescheiterter_auftrag_geht_zu_bei_fehler():
    ablauf = AblaufArea.model_validate(_roh())
    umgebung, _ = _umgebung({"document": {"upload_id": "u1"}})
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    aus = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, None, umgebung))
    assert aus.texte == ["Das Lesen hat nicht geklappt."] and aus.neue_teile == []
    assert asyncio.run(treiber.weiter_auftrag(ablauf, {**lauf, "status": "fertig"}, None,
                                              umgebung)) is None


# ── Im Zug: Start mit Anmeldung, Stand prüfen ──────────────────────────────────────────────

class _Ablage:
    def __init__(self):
        self.auftraege: list[SimpleNamespace] = []

    async def anlegen(self, s, vorgang_id, *, job_id, flow, schritt):
        for a in self.auftraege:
            if a.vorgang_id == vorgang_id and a.status == "laeuft":
                a.status = "abgebrochen"
        a = SimpleNamespace(vorgang_id=vorgang_id, job_id=job_id, flow=flow, schritt=schritt,
                            status="laeuft")
        self.auftraege.append(a)
        return a

    async def offen(self, s, vorgang_id):
        return next((a for a in reversed(self.auftraege)
                     if a.vorgang_id == vorgang_id and a.status == "laeuft"), None)

    async def abschliessen(self, s, a, status):
        a.status = status

    async def offene_job_ids(self, s, aufrufer):
        return [a.job_id for a in self.auftraege if a.status == "laeuft"
                and getattr(self.speicher.v.get(a.vorgang_id), "aufrufer", None) in aufrufer]


@pytest.fixture
def im_zug(monkeypatch, freigeschaltet):
    sp, ab = _Speicher(), _Ablage()
    ab.speicher = sp
    for name in ("lesen", "juengster", "anlegen", "teil_setzen", "lauf_setzen", "teil_wert",
                 "beruehren", "alle_loeschen", "anonyme_der_sitzung_loeschen",
                 "sitzung_setzen"):
        monkeypatch.setattr(vorgaenge, name, getattr(sp, name))
    for name in ("anlegen", "offen", "abschliessen", "offene_job_ids"):
        monkeypatch.setattr(ablage, name, getattr(ab, name))
    for modul in (arbeitsstand, ausloeser, auftrag_zug):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: True)
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: True)
    monkeypatch.setattr(arbeitsstand, "aufrufer_kennung", lambda: "person-a")

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(zug_basis, "save_message", nichts)
    monkeypatch.setattr(zug_basis, "update_session", nichts)
    katalog = {"ablaeufe": [_roh(schritte=[{**_SCHRITTE[0], "argumente": {"text": "fest"}},
                                           *_SCHRITTE[1:]])]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    gestartet: list = []
    staende: list = []

    async def starten(flow, eingaben):
        gestartet.append((flow, eingaben))
        return "job-1"

    async def stand(job_id):
        return staende.pop(0)

    monkeypatch.setattr(client, "starten", starten)
    monkeypatch.setattr(client, "stand", stand)
    return SimpleNamespace(speicher=sp, ablage=ab, gestartet=gestartet, staende=staende)


def _starte(state):
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "lesen"})
    return asyncio.run(zug.starten(_S(), anfrage, state))


def _pruefe(state):
    anfrage = _req(action=auftrag_zug.AKTION, action_params={"ablauf": "lesen"})
    return asyncio.run(auftrag_zug.pruefen(_S(), anfrage, state))


def test_der_start_haelt_die_job_id_und_zeigt_stand_pruefen(im_zug):
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert im_zug.gestartet == [("wlo/volltext", {"text": "fest"})]
    [a] = im_zug.ablage.auftraege
    assert a.job_id == "job-1" and a.schritt == "lesen"
    assert antwort.quick_replies[0].split("|")[2] == auftrag_zug.AKTION
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == "wartet_auftrag"


def test_stand_pruefen_laeuft_noch(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("laeuft"))
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragLaeuft")
    assert antwort.quick_replies and im_zug.ablage.auftraege[0].status == "laeuft"


def test_stand_pruefen_fertig_setzt_fort(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, [{"name": "a.md",
                                                                       "groesse": 3}]))
    antwort = _pruefe(state)
    # Kein „Stand prüfen“ mehr — unter einem fertigen Lauf stehen die Vorgangs-Knöpfe (Q3).
    assert antwort.content == "Gelesen." and antwort.quick_replies == vorgang_aktion.knoepfe("de")
    [v] = im_zug.speicher.v.values()
    assert v.akte["teile"]["volltext"]["wert"] == {"outputs": {"markdown": "# T"},
                                                   "dateien": [{"name": "a.md", "groesse": 3}]}
    assert im_zug.ablage.auftraege[0].status == "fertig"


def test_stand_pruefen_fehler_geht_zu_bei_fehler(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fehler"))
    antwort = _pruefe(state)
    assert antwort.content == "Das Lesen hat nicht geklappt."
    assert im_zug.ablage.auftraege[0].status == "fehler"


def test_stand_nicht_abrufbar(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)

    async def kaputt(job_id):
        raise client.AuftragFehler("fehler")

    monkeypatch.setattr(client, "stand", kaputt)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNichtAbrufbar")
    assert antwort.quick_replies


def test_ohne_anmeldung_startet_kein_auftrag(im_zug, monkeypatch):
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: False)
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: True)   # Voraussetzung täuschen
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert im_zug.gestartet == [] and antwort.content == "Das Lesen hat nicht geklappt."


def test_stand_pruefen_ohne_wartenden_auftrag(im_zug):
    antwort = _pruefe({"entities": {}})
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")


# ── Review K1a ───────────────────────────────────────────────────────────────────────────────

def test_ohne_durchgereichten_schluessel_startet_kein_auftrag(im_zug, monkeypatch):
    """Befund 1: nicht auf dem Schlüssel aller (``B_API_KEY``)."""
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: False)
    antwort = _starte({"entities": {}})
    assert im_zug.gestartet == [] and antwort.content == "Das Lesen hat nicht geklappt."


def test_ohne_durchgereichten_schluessel_wird_nicht_abgefragt(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)
    monkeypatch.setattr(auftrag_zug, "hat_zug_schluessel", lambda: False)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNichtAbrufbar")
    assert im_zug.staende == [] and im_zug.ablage.auftraege[0].status == "laeuft"


def test_ein_konflikt_beim_abholen_laesst_den_auftrag_offen(im_zug, monkeypatch):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    zurueck = {"n": 0}

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v-1")

    class _Rueck(_S):
        async def rollback(self):
            zurueck["n"] += 1
            # die Attrappe kennt keine Transaktion: ein Rollback setzt den Stand zurück
            for a in im_zug.ablage.auftraege:
                a.status = "laeuft"

    monkeypatch.setattr(vorgaenge, "lauf_setzen", konflikt)
    anfrage = _req(action=auftrag_zug.AKTION, action_params={"ablauf": "lesen"})
    antwort = asyncio.run(auftrag_zug.pruefen(_Rueck(), anfrage, state))
    assert antwort.content == bot_text("de", "action.ablauf.konflikt") and zurueck["n"] == 1
    assert im_zug.ablage.auftraege[0].status == "laeuft"


def test_ein_ausgeschalteter_ablauf_bricht_lauf_und_auftrag_ab(im_zug, monkeypatch):
    """Befund 9: der Auftrag gilt danach nicht mehr als offen, kein Knopf mehr (Befund 11)."""
    state: dict = {"entities": {}}
    _starte(state)
    katalog = {"ablaeufe": [_roh(aktiv=False)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    assert auftrag_zug.pruefen_knoepfe("sitzung-0123456789", state, "de") == []
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.unbekannt")
    assert im_zug.ablage.auftraege[0].status == "abgebrochen"
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"


# ── Job-Vertrag 2026-11-07: Warnungen und Abbrechen bei der B-API ───────────────────────────

@pytest.fixture
def abbrueche(monkeypatch):
    from boerdi.services import llm_auth

    gesehen: list[str] = []
    monkeypatch.setattr(client, "abbrechen_im_hintergrund", gesehen.append)
    monkeypatch.setattr(llm_auth, "hat_zug_schluessel", lambda: True)
    return gesehen


def test_ein_teilerfolg_reist_im_teil_mit(im_zug):
    state: dict = {"entities": {}}
    _starte(state)
    im_zug.staende.append(client.Stand("fertig", {"n": 3}, [], warnungen=True))
    _pruefe(state)
    [v] = im_zug.speicher.v.values()
    assert v.akte["teile"]["volltext"]["wert"] == {"outputs": {"n": 3}, "dateien": [],
                                                   "warnungen": True}


def test_ein_abgebrochener_lauf_beendet_den_auftrag_auch_bei_der_b_api(im_zug, monkeypatch,
                                                                       abbrueche):
    state: dict = {"entities": {}}
    _starte(state)
    katalog = {"ablaeufe": [_roh(aktiv=False)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    _pruefe(state)
    assert abbrueche == ["job-1"]


def test_ohne_schluessel_der_person_kein_abbruch_bei_der_b_api(im_zug, monkeypatch, abbrueche):
    from boerdi.services import llm_auth

    monkeypatch.setattr(llm_auth, "hat_zug_schluessel", lambda: False)
    state: dict = {"entities": {}}
    _starte(state)
    katalog = {"ablaeufe": [_roh(aktiv=False)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    _pruefe(state)
    assert abbrueche == []


def test_ein_ersetzter_lauf_beendet_seinen_auftrag_bei_der_b_api(im_zug, abbrueche):
    state: dict = {"entities": {}}
    _starte(state)
    _starte(state)                  # derselbe Ablauf neu: der wartende Lauf wird ersetzt
    assert abbrueche == ["job-1"]
    assert [a.status for a in im_zug.ablage.auftraege] == ["abgebrochen", "laeuft"]


def _ersetzbar(im_zug, monkeypatch):
    """Jeder Start bekommt eine eigene Job-ID (job-1, job-2, …)."""
    async def starten(flow, eingaben):
        im_zug.gestartet.append((flow, eingaben))
        return f"job-{len(im_zug.gestartet)}"

    monkeypatch.setattr(client, "starten", starten)


def test_ein_konflikt_beim_ersetzen_bricht_den_alten_auftrag_nicht_ab(im_zug, monkeypatch,
                                                                      abbrueche):
    """Review Job-Vertrag, Befund 1: der Abbruch geht erst nach dem Festschreiben raus — sonst
    endete bei einem Rollback ein Auftrag, auf den der Lauf noch wartet. Der eben gestartete, nicht
    festgehaltene endet dagegen (Befund 3)."""
    _ersetzbar(im_zug, monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v-1")

    monkeypatch.setattr(vorgaenge, "lauf_setzen", konflikt)
    antwort = _starte(state)
    assert antwort.content == bot_text("de", "action.ablauf.konflikt")
    assert abbrueche == ["job-2"]


def test_neues_vorhaben_beendet_den_wartenden_auftrag_bei_der_b_api(im_zug, abbrueche):
    """Review Job-Vertrag, Befund 2."""
    state: dict = {"entities": {}}
    _starte(state)
    # Zweites Review K2b, Befund 5: bei einem wartenden Auftrag erst die Rückfrage, dann das Ja.
    asyncio.run(vorgang_aktion.neu(_S(), _req(action=vorgang_aktion.AKTION_NEU), state))
    assert abbrueche == []
    ja = {"bestaetigt": True, "kuerzel": client.kuerzel("job-1")}
    asyncio.run(vorgang_aktion.neu(_S(), _req(action=vorgang_aktion.AKTION_NEU,
                                              action_params=ja), state))
    assert abbrueche == ["job-1"]
    assert im_zug.ablage.auftraege[0].status == "abgebrochen"


def test_arbeitsstand_loeschen_beendet_offene_auftraege_bei_der_b_api(im_zug, monkeypatch,
                                                                      abbrueche):
    """Review Job-Vertrag, Befund 2: die Kaskade nimmt die Zeilen mit, der Job lief weiter."""
    from boerdi.services.dokumente import ablage as dokumente

    async def kein_dokument(*_a, **_k):
        return 0

    monkeypatch.setattr(dokumente, "der_sitzung_loeschen", kein_dokument)
    state: dict = {"entities": {}}
    _starte(state)
    asyncio.run(vorgang_aktion.loeschen(
        _S(), _req(action=vorgang_aktion.AKTION_LOESCHEN, action_params={"bestaetigt": True}),
        state))
    assert abbrueche == ["job-1"]


def test_ein_abgewiesener_schluessel_bricht_nicht_bei_der_b_api_ab(im_zug, monkeypatch,
                                                                   abbrueche):
    """Review Job-Vertrag, Befund 5: kein DELETE mit dem Schlüssel, den die b-api eben abwies."""
    state: dict = {"entities": {}}
    _starte(state)

    async def abgewiesen(job_id):
        raise client.AuftragFehler("abgewiesen")

    monkeypatch.setattr(client, "stand", abgewiesen)
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragAbgewiesen")
    assert abbrueche == [] and im_zug.ablage.auftraege[0].status == "abgebrochen"


def test_der_start_eines_anderen_ablaufs_beendet_den_wartenden_auftrag(im_zug, monkeypatch,
                                                                       abbrueche):
    """Review Job-Vertrag (Nachprüfung): ``_ziel_vorbereiten`` schließt den Vorgang mit dem
    wartenden Lauf — sein Auftrag endet nach dem Festschreiben auch bei der b-api."""
    state: dict = {"entities": {}}
    _starte(state)
    gruss = {"id": "gruss", "titel": {"de": "Gruß"}, "aktiv": True,
             "ausloeser": [{"art": "knopf"}],
             "schritte": [{"id": "ende", "typ": "ende", "text": {"de": "Hallo."}}]}
    katalog = {"ablaeufe": [_roh(), gruss]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "gruss"}),
                            state))
    assert abbrueche == ["job-1"]
    assert im_zug.ablage.auftraege[0].status == "abgebrochen"


def test_ein_konflikt_beim_abbrechen_sendet_kein_delete(im_zug, monkeypatch, abbrueche):
    """Review Job-Vertrag, Befund 1 für ``zug_basis.abbrechen``: Rollback → kein Abbruch."""
    state: dict = {"entities": {}}
    _starte(state)
    katalog = {"ablaeufe": [_roh(aktiv=False)]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})

    async def konflikt(*_a, **_k):
        raise vorgaenge.VorgangKonflikt("v-1")

    monkeypatch.setattr(vorgaenge, "lauf_setzen", konflikt)
    _pruefe(state)
    assert abbrueche == []


def test_ein_wartender_lauf_merkt_sein_gespraech(im_zug):
    """Paket K2a (Review, Befund 1): „fortsetzen“ führt in das Gespräch, in dem der Lauf zuletzt zu
    warten begann — auf einen Auftrag oder auf die Person; ein beendeter Lauf ändert es nicht."""
    state: dict = {"entities": {}}
    _starte(state)
    [v] = im_zug.speicher.v.values()
    assert v.session_id == "sitzung-0123456789"
    lauf = {**v.akte["lauf"]}
    fertig = treiber.Ausgabe(lauf={**lauf, "status": "fertig"})
    asyncio.run(zug_basis.festhalten(_S(), v, fertig, session_id="gespraech-b"))
    assert im_zug.speicher.v[v.id].session_id == "sitzung-0123456789"
    wartet = treiber.Ausgabe(lauf={**lauf, "status": treiber.WARTET})
    asyncio.run(zug_basis.festhalten(_S(), im_zug.speicher.v[v.id], wartet,
                                     session_id="gespraech-b"))
    assert im_zug.speicher.v[v.id].session_id == "gespraech-b"
