"""Plan 2026-11-16, Durchtest TG-7 — Behebung: der Lauf geht nach „Übernehmen“ selbst weiter (M1),
Lesewerkzeug ``dokument_lesen`` (M2), Vorbelegung des Themas (m1/m2), Volltext-Sätze (m3), kleiner
Bestand (m4), Fehlercode der b-api (m5), Kleinigkeiten.
"""

from __future__ import annotations

import asyncio
import pathlib
from types import SimpleNamespace

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import ki_schritt, zug
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from tests.test_ablauf_zug import _S, _geprueft, _katalog, _req, _start, umgebung  # noqa: F401

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _seed() -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / "themenbaum.yaml").read_text(encoding="utf-8")))


# ── M1b: „Übernehmen“ am KI-Schritt mit ``ausgabe: draft`` setzt den Lauf fort ──────────────────

_KI_KATALOG = {"schritte": [
    {"id": "erfassen", "typ": "modul", "modul": UPLOAD, "daten": {"zweck": "sammlungsstruktur"}},
    {"id": "entwurf", "typ": "agent", "text": {"de": "Ich entwerfe."},
     "agent": {"werkzeuge": [STRUKTURENTWURF], "ausgabe": "draft"}},
    {"id": "ende", "typ": "ende", "text": {"de": "Gespeichert."}}]}


def _entwurf(uebernommen: bool | None = True) -> dict:
    daten = {"titel": "Optik", "quelle": "ki", "knoten": [{"titel": "Linsen"}, {"titel": "Licht"}]}
    if uebernommen is not None:
        daten["uebernommen"] = uebernommen
    return {"modul": STRUKTURENTWURF, "block_id": "entwurf0001", "daten": daten}


def _bis_zur_ki(umgebung, state) -> None:  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = _katalog(**_KI_KATALOG)
    block = _start(state).ui.ui_bloecke[0]
    asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block, "erfasst")))
    assert state["entities"][arbeitsstand.VERWEIS]["lauf"]["status"] == "wartet_ki"


def test_m1b_uebernehmen_beendet_den_ki_schritt_ohne_ki(umgebung):  # noqa: F811 — Fixture
    state: dict = {"entities": {}}
    _bis_zur_ki(umgebung, state)
    assert ki_schritt.uebernimmt(state, "sitzung-0123456789", _entwurf()) is not None
    antwort = asyncio.run(zug.nach_uebernahme(_S(), _req(), state, _entwurf()))
    assert antwort is not None and antwort.content == "Gespeichert."
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fertig"
    assert v.akte["teile"]["draft"]["wert"]["titel"] == "Optik"
    assert "uebernommen" not in v.akte["teile"]["draft"]["wert"]


@pytest.mark.parametrize("antwort", [
    _entwurf(uebernommen=None),                                   # nur mitgeschickt
    _entwurf(uebernommen=False),
    {"modul": UPLOAD, "block_id": "x", "daten": {"uebernommen": True}},   # anderes Modul
])
def test_m1b_nur_eine_uebernahme_des_entwurfs(umgebung, antwort):  # noqa: F811 — Fixture
    state: dict = {"entities": {}}
    _bis_zur_ki(umgebung, state)
    assert ki_schritt.uebernimmt(state, "sitzung-0123456789", antwort) is None
    assert asyncio.run(zug.nach_uebernahme(_S(), _req(), state, antwort)) is None
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_ki"


def test_m1b_ohne_wartenden_ki_schritt_nichts(umgebung):  # noqa: F811 — Fixture
    state: dict = {"entities": {}}
    assert ki_schritt.uebernimmt(state, "sitzung-0123456789", _entwurf()) is None
    assert asyncio.run(zug.nach_uebernahme(_S(), _req(), state, _entwurf())) is None


def test_m1b_eine_andere_ausgabe_als_der_entwurf_geht_den_gewoehnlichen_weg(umgebung):  # noqa: F811
    state: dict = {"entities": {}}
    katalog = {"schritte": [_KI_KATALOG["schritte"][0],
                            {**_KI_KATALOG["schritte"][1],
                             "agent": {"werkzeuge": [STRUKTURENTWURF], "ausgabe": "structure"}},
                            _KI_KATALOG["schritte"][2]]}
    umgebung.katalog["wert"] = _katalog(**katalog)
    block = _start(state).ui.ui_bloecke[0]
    asyncio.run(zug.fortsetzen(_S(), _req(), state, _geprueft(block, "erfasst")))
    assert ki_schritt.uebernimmt(state, "sitzung-0123456789", _entwurf()) is None


def test_m1b_der_preflight_leitet_die_uebernahme_weiter(monkeypatch):
    from boerdi.graph.nodes import preflight_ablauf

    gesehen: list = []

    async def nach(session, req, state, geprueft, *, blocked_tools=()):
        gesehen.append(geprueft)
        return SimpleNamespace(content="weiter")

    monkeypatch.setattr(zug, "nach_uebernahme", nach)
    ctx = SimpleNamespace(req=_req(), session_state={"entities": {}}, ui_antwort=_entwurf())
    a = preflight_ablauf.Ausloeser(False, None, None, None, uebernahme=True)
    assert a.irgendeiner
    antwort = asyncio.run(preflight_ablauf.antwort(ctx, _S(), a, []))
    assert antwort.antwort.content == "weiter" and gesehen == [_entwurf()]


# ── M1c: der Seed lädt nach der Übernahme nicht zum zweiten Entwurf ein ────────────────────────

def test_m1c_die_hinweise_sagen_einmal_entwerfen():
    for s in _seed().schritte:
        if s.typ == "agent":
            for sprache, wort in (("de", "nicht neu entwerfen"), ("en", "do not draft again")):
                assert wort in s.agent.hinweis[sprache], (s.id, sprache)
                assert "Sonst ui_strukturentwurf" not in s.agent.hinweis[sprache]


# ── m1: das Thema ohne getippte Grundlage ──────────────────────────────────────────────────────

def _belegt(teile: dict, sid: str = "entwurf_dokument") -> dict:
    from boerdi.services.ablauf import vorbelegung as vb

    ablauf = _seed()
    schritt = next(s for s in ablauf.schritte if s.id == sid)

    async def lader(name):
        return teile.get(name)

    return asyncio.run(vb.vorbelegung(schritt, lader, [k for k in teile if isinstance(
        teile[k], str)], "de", ablauf=ablauf))


_SD = {"eintraege": [{"ref": "dokument:11111111-2222-4333-8444-555555555555",
                      "quelle": "chatbot", "name": "Lehrplan-Biologie-Sek1.md"},
                     {"ref": "dokument:21111111-2222-4333-8444-555555555555",
                      "quelle": "chatbot", "name": "Chemie.pdf"}]}


def test_m1_dokument_weg_das_erste_strukturdokument_ohne_endung():
    from boerdi.services.dokumente import strukturdokument_teil as sd

    teile = {sd.TEIL: sd.wert(_SD["eintraege"]), "zweck": "Unterricht planen",
             "grundlage": "Ein Dokument mit Gliederung, etwa ein Lehrplan"}
    assert _belegt(teile)["thema"] == "Lehrplan-Biologie-Sek1"
    # nur das Teil ``document`` (Stand vor TG-3d)
    assert _belegt({"document": {"name": "Rahmenplan Physik.docx"}})["thema"] == \
        "Rahmenplan Physik"


def test_m1_ordner_weg_der_wurzelordner():
    teile = {"ordnerweg": "Mit deinen Angaben verfeinern",
             "structure": {"struktur": {"name": "Physik", "kinder": []}},
             "metadaten": {"inhalte": []}}
    assert _belegt(teile, "entwurf_ordner")["thema"] == "Physik"


def test_m1_datei_weg_ohne_thema_und_die_ki_geht_vor():
    from boerdi.services.ablauf import vorbelegung as vb

    teile = {"metadaten": {"inhalte": [{"titel": "Brüche"}]},
             "structure": {"struktur": {"name": "Mathe-Material"}}, "zweck": "Unterricht planen"}
    assert "thema" not in _belegt(teile, "entwurf_inhalte")
    # eine getippte Grundlage bleibt das Thema
    assert _belegt({"grundlage": "Optik (Physik)", "document": {"name": "X.md"}},
                   "entwurf_thema")["thema"] == "Optik (Physik)"
    # die KI bleibt vorrangig
    belegt = _belegt({"document": {"name": "Rahmenplan.md"}})
    assert vb.vorbelegt({"thema": "Lernfelder IT"}, belegt)["thema"] == "Lernfelder IT"


def test_m1_die_vorgaben_fuer_dateien_nennen_den_zweck_nicht_als_thema():
    s = next(x for x in _seed().schritte if x.id == "entwurf_inhalte")
    assert "nie den Zweck als Thema" in s.agent.vorgaben["de"]
    assert "never use the purpose as the topic" in s.agent.vorgaben["en"]


def test_r2_1_die_vorgaben_verbieten_platzhalter_als_thema():
    # Zweiter Durchtest: die KI setzte "Themen aus den bereitgestellten Dateien" als Thema.
    s = next(x for x in _seed().schritte if x.id == "entwurf_inhalte")
    assert "kein Platzhalter" in s.agent.vorgaben["de"]
    assert "no placeholder" in s.agent.vorgaben["en"]
    assert "kein Platzhalter" in s.agent.hinweis["de"]


# ── m2: der verfeinerte Ordner-Entwurf trägt Stufe und Thema ──────────────────────────────────

async def test_m2_die_vorlage_bekommt_stufe_und_thema_aus_dem_auftrag():
    from boerdi.services import strukturentwurf_dienst as dienst
    from tests.test_strukturentwurf_dienst import Attrappe, _erzeugen, _k

    vorlage = {"titel": "Physik", "quelle": "ordner", "knoten": [
        {"id": "k1", "titel": "Optik"}, {"id": "k2", "titel": "Mechanik"}]}
    llm = Attrappe([], {"Optik": [_k("Licht")], "Mechanik": [_k("Kraft")]})
    erg = await _erzeugen(dienst.Auftrag(thema="Physik", bildungsstufe="Sekundarstufe I",
                                         tiefe=2), llm, vorlage=vorlage)
    assert erg.daten["bildungsstufe"] == "Sekundarstufe I" and erg.daten["thema"] == "Physik"
    assert erg.daten["titel"] == "Physik" and erg.daten["quelle"] == "ordner"
    # ein Thema der Vorlage bleibt
    erg = await _erzeugen(dienst.Auftrag(thema="Anderes", tiefe=2), llm,
                          vorlage={**vorlage, "thema": "Physik 7"})
    assert erg.daten["thema"] == "Physik 7" and "bildungsstufe" not in erg.daten


# ── NIT: ein Entwurf aus losen Dateien ist kein Dokument-Entwurf ──────────────────────────────

def test_nit_quelle_aus_inhalten_ist_ki(monkeypatch):
    from boerdi.services import strukturentwurf_dienst as dienst
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module.aufruf import Umgebung
    from boerdi.ui_module.katalog import katalog

    async def erzeugen(auftrag, *, llm, frist_ende, vorlage=None, dokument=None, moderieren=None):
        return dienst.Erzeugt(daten={"titel": "Zahlen", "quelle": "dokument", "thema": "Zahlen",
                                     "knoten": [{"id": "k1", "titel": "Brüche"}]})

    async def nicht_beanstandet(_text):
        return None

    async def teile(name):
        return {"format": "wlo.metadaten@1", "titel": "M", "fehlend": [], "inhalte": [
            {"i": 0, "titel": "Brüche", "rolle": "inhalt"}]} if name == "metadaten" else None

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    monkeypatch.setattr(modul_dienst, "_ebene_eins_pruefen", nicht_beanstandet)
    ergebnis = asyncio.run(modul_dienst.aufruf(
        katalog()["ui_strukturentwurf"], {"thema": "Zahlen", "aus_inhalten": True},
        Umgebung(teile=teile)))
    assert ergebnis.block is not None and ergebnis.block.daten["quelle"] == "ki"


# ── m3: eine Datei ohne Text ist nicht „in einigen Minuten“ lesbar ─────────────────────────────

def test_m3_ohne_text_aus_der_datei_ein_ehrlicher_sammelsatz():
    """Das MCP sagt ``not_extracted`` für „noch nicht“ UND „nie“ (Bild, PDF ohne Textschicht) —
    unterscheiden lässt es sich nicht; der Satz nennt beides."""
    from boerdi.services.dokumente import stand
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module import katalog
    from boerdi.ui_module.aufruf import Umgebung

    assert modul_dienst._volltext_satz((("a", "not_extracted"),)) == "volltext_fehlt_datei"
    assert modul_dienst._volltext_satz((("a", "text_unreadable"),)) == "volltext_fehlt"
    assert modul_dienst._volltext_satz((("a", "frist"), ("b", "not_extracted"))) == (
        "volltext_fehlt_datei")

    async def ohne():
        return stand.OhneVolltext((("Scan.pdf", "not_extracted"),))

    erg = asyncio.run(modul_dienst.aufruf(katalog.katalog()["ui_strukturentwurf"],
                                          {"thema": "Physik", "aus_dokument": True},
                                          Umgebung(dokument=ohne)))
    assert erg.outcome.error == "volltext_fehlt"
    assert "Scan" in erg.text and "lesbaren Text" in erg.text and "Fassung mit Text" in erg.text
    assert "erzeugt gerade" not in erg.text
    assert "keinen lesbaren Text" in modul_dienst._ohne_volltext((("Scan.pdf", "not_extracted"),))


# ── m4: wenige Dateien → erst fragen, ob nach Stoff ───────────────────────────────────────────

@pytest.mark.parametrize(("anzahl", "frage"), [(3, "soll_wenig"), (4, "soll_wenig"),
                                               (5, "soll_ist")])
def test_m4_unter_fuenf_inhalten_die_eigene_frage(anzahl, frage):
    from boerdi.domain.config_models.ablauf import AblaufTest
    from boerdi.services.ablauf import simulation

    inhalte = [{"i": n, "titel": f"T{n}", "rolle": "inhalt"} for n in range(anzahl)]
    fall = AblaufTest.model_validate({
        "name": "Probe", "ab": "hinweise", "angemeldet": False,
        "teile": {"metadaten": {"format": "wlo.metadaten@1", "titel": "M", "fehlend": [],
                                "inhalte": inhalte}},
        "eingaben": [{"bei": "hinweise", "option": "keine"}, {"bei": frage, "option": "ist"}],
        "erwartet": {"weg": ["hinweise", "zum_entwurf", frage, "entwurf_inhalte"],
                     "status": "wartet_ki"}})
    ergebnis = asyncio.run(simulation.testen(_seed(), fall))
    assert ergebnis.ok, ergebnis.abweichungen


def test_m4_die_ist_regel_haelt_mindestens_zwei_punkte():
    s = next(x for x in _seed().schritte if x.id == "entwurf_inhalte")
    assert "mindestens 2 Punkte oben" in s.agent.vorgaben["de"]
    assert "Einzelkinder vermeiden" in s.agent.vorgaben["de"]
    assert "Trotzdem nur meine Dateien" in s.agent.vorgaben["de"]


# ── m5: eine Abweisung der b-api mit Code im Log und passendem Satz ───────────────────────────

@pytest.mark.parametrize(("koerper", "code"), [
    ({"error": {"code": "EDU_USER_NOT_VERIFIED", "message": "user x not verified"}},
     "EDU_USER_NOT_VERIFIED"),
    ({"code": "EDU_USER_NOT_VERIFIED"}, "EDU_USER_NOT_VERIFIED"),
    ({"error": {"code": "Geheimer Servertext mit Person"}}, None),
    ({}, None),
])
def test_m5_der_fehlercode_nur_aus_der_festen_liste(monkeypatch, caplog, koerper, code):
    import logging

    import httpx

    from boerdi.services.auftraege import client

    with caplog.at_level(logging.INFO, logger=client.logger.name):
        with pytest.raises(client.AuftragFehler) as fehler:
            client._pruefe_antwort(httpx.Response(403, json=koerper))
    assert fehler.value.grund == "abgewiesen" and fehler.value.code == code
    log = caplog.text
    assert (code or "unbekannt") in log
    assert "Geheimer" not in log and "user x" not in log


def _starter(monkeypatch, code):
    from boerdi.services.ablauf import auftrag_zug
    from boerdi.services.auftraege import client

    async def starten(flow, eingaben):
        raise client.AuftragFehler("abgewiesen", code=code)

    monkeypatch.setattr(client, "freigeschaltet", lambda: True)
    monkeypatch.setattr(client, "starten", starten)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: True)
    return auftrag_zug.starter().fuer(False)       # Paket K, Review A4: Direktweg je Schritt


@pytest.mark.parametrize(("code", "satz"), [
    ("EDU_USER_NOT_VERIFIED", "Dein Konto ist dort noch nicht freigeschaltet"),
    (None, "Der Dienst hat den Auftrag abgelehnt."),
])
def test_m5_die_person_erfaehrt_den_grund(monkeypatch, code, satz):
    from boerdi.services.ablauf import treiber

    starte = _starter(monkeypatch, code)
    assert asyncio.run(starte("f/x", {})) is None
    assert satz in starte.hinweis("de")
    assert "declined the job" in starte.hinweis("en")
    ablauf = AblaufArea.model_validate({
        "id": "x", "titel": {"de": "X"}, "voraussetzungen": ["anmeldung"],
        "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Los?"},
             "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "a"},
                          {"id": "nein", "label": {"de": "Nein"}, "ziel": "e"}]},
            # Paket K2: ohne ``repo_schreibt`` — der Direktweg dieses Starters startet einen
            # schreibenden Flow gar nicht mehr (test_paket_k_traeger); hier geht es um den Satz
            # nach einer Abweisung der b-api
            {"id": "a", "typ": "auftrag", "flow": "f/x", "bei_fehler": "e"},
            {"id": "e", "typ": "ende", "text": {"de": "Ohne Auftrag weiter."}}]})

    async def teile(_name):
        return None

    umg = treiber.Umgebung(teile=teile, auftrag_starten=starte)
    aus = asyncio.run(treiber.starten(ablauf, umg, ab=1))
    assert aus.texte[0].startswith("Der Dienst hat den Auftrag abgelehnt")
    assert aus.texte[-1] == "Ohne Auftrag weiter."


# ── NIT: dieselbe Fundstelle an jedem Punkt ist keine ───────────────────────────────────────────

def test_nit_eine_fundstelle_fuer_alle_punkte_entfaellt():
    from boerdi.services import strukturentwurf_dokument as sdok

    alle_gleich = [{"titel": "A", "fundstelle": "Teil 1", "abschnitte": ["a1"]},
                   {"titel": "B", "fundstelle": "Teil 1", "abschnitte": ["a1"]}]
    sdok.ohne_gleiche_fundstelle(alle_gleich)
    assert all("fundstelle" not in k for k in alle_gleich)
    assert all(k["abschnitte"] == ["a1"] for k in alle_gleich)
    verschieden = [{"titel": "A", "fundstelle": "LF 1"}, {"titel": "B", "fundstelle": "LF 2"}]
    sdok.ohne_gleiche_fundstelle(verschieden)
    assert [k["fundstelle"] for k in verschieden] == ["LF 1", "LF 2"]
    einer = [{"titel": "A", "fundstelle": "Teil 1"}]
    sdok.ohne_gleiche_fundstelle(einer)
    assert einer[0]["fundstelle"] == "Teil 1"


# ── Review der Behebung ───────────────────────────────────────────────────────────────────────

def test_r3_ein_veralteter_verweis_auf_einen_anderen_ki_schritt(umgebung):  # noqa: F811 — Fixture
    """R3: der Verweis nennt den Schritt ``entwurf``, im Vorgang steht der Lauf schon woanders."""
    state: dict = {"entities": {}}
    _bis_zur_ki(umgebung, state)
    [v] = umgebung.speicher.v.values()
    umgebung.speicher.v[v.id].akte["lauf"]["schritt"] = "anderer"
    assert asyncio.run(zug.nach_uebernahme(_S(), _req(), state, _entwurf())) is None
    assert "draft" not in umgebung.speicher.v[v.id].akte["teile"]


def test_r6_ein_leerer_entwurf_ist_keine_uebernahme(umgebung):  # noqa: F811 — Fixture
    state: dict = {"entities": {}}
    _bis_zur_ki(umgebung, state)
    leer = _entwurf()
    leer["daten"]["knoten"] = []
    assert ki_schritt.uebernimmt(state, "sitzung-0123456789", leer) is None


def test_r7_der_seed_sagt_was_gezaehlt_wird():
    text = (_SEEDS / "themenbaum.yaml").read_text(encoding="utf-8")
    assert "fehlend" in text.split("id: zum_entwurf")[0].rsplit("- id:", 1)[-1]
