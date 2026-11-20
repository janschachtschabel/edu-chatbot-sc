"""Plan 2026-11-20, P3 (UO-3, sicherheitsrelevant): der Klick „In WLO ablegen und erschließen“ ist
die Zustimmung zum Metadaten-Flow — nur für Knoten, die genau dieser Upload neu angelegt hat.

Ein Auftragsschritt mit ``zustimmung: upload`` startet ohne Freigabe-Box (Vorschau + Bestätigung
des MCP im selben Zug), wenn ALLES gilt: persönliche Anmeldung, Teil ``ablage`` mit Häkchen
(``erschliessen``), vom selben Aufrufer, aus dem Upload-Block dieses Laufs, und jede ``node_id``
steht in den aktuellen ``inhalte`` mit ``stand: stored`` und ``neu: true``. Sonst — fail closed —
die Freigabe-Box wie bisher.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Any

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.services.ablage import vorgang_teil
from boerdi.services.ablauf import pruefung, treiber, werkzeuge
from boerdi.services.ablauf.auftrag_freigabe import AuftragVorlage
from boerdi.services.ablauf.pruefung_texte import _T as TEXTE
from boerdi.services.auftraege.client import AuftragFehler
from tests.test_ui_ablage_api import (  # noqa: F401  (Fixtures der Ablage-API)
    _datei,
    _umgebung,
    _vorbereiten,
    client,
    lage,
)

PERSON = "p:streuwert-a"
BLOCK = "b0000001"
IDS = ["n-0", "n-1", "n-2"]
TOKEN = "ct_vorschau_0123456789"


def _uz() -> Any:
    """Das neue Modul — einzeln geladen, damit jeder Test für sich rot wird."""
    return importlib.import_module("boerdi.services.ablauf.upload_zustimmung")


@pytest.fixture
def person(monkeypatch):
    """Angemeldet als ``PERSON`` — ``kennung`` lässt sich im Test wechseln."""
    lage_ = {"auth": True, "kennung": PERSON}
    monkeypatch.setattr(vorgang_teil, "aufrufer_kennung", lambda: lage_["kennung"],
                        raising=False)
    try:
        monkeypatch.setattr(_uz(), "has_personal_auth", lambda: lage_["auth"])
    except ModuleNotFoundError:
        pass
    return lage_


def _ablage(*, erschliessen: bool = True, block: str = BLOCK, n: int = 3,
            already: tuple[int, ...] = (), frueher: list[dict] | None = None) -> dict:
    """Ein Teil ``ablage`` wie nach ``/vorbereiten`` und ``/datei`` je Eintrag."""
    plan = {"folderName": "Physik", "layout": "folder",
            "entries": [{"index": i, "title": f"T{i}", "ext": "pdf", "size": 5,
                         "fileName": f"t{i}.pdf"} for i in range(n)]}
    teil = vorgang_teil.aus_plan(plan, "batch-token-0123456789", block, erschliessen=erschliessen)
    for i in range(n):
        ergebnis = {"status": "stored", "nodeId": f"n-{i}"}
        if i in already:
            ergebnis["already"] = True
        teil = vorgang_teil.mit_ergebnis(teil, i, ergebnis)
    if frueher is not None:
        teil["frueher"] = frueher
    return teil


# ── Modell ────────────────────────────────────────────────────────────────────────────────────

def _auftrag(**mehr) -> dict:
    return {"id": "metadaten", "typ": "auftrag", "flow": METADATEN_FLOW, "repo_schreibt": True,
            "argumente": {"node_ids": {"$teil": "ablage", "liste": "inhalte",
                                       "wo": {"stand": "stored"}, "feld": "node_id"},
                          "language": "de"},
            "aufteilen": {"argument": "node_ids", "hoechstens": 2},
            "schreibt": "metadatenlauf", "bei_fehler": "ohne", "weiter": "fertig",
            "text": {"de": "Ich lasse die Metadaten erzeugen."}, **mehr}


def _roh(auftrag: dict | None = None, *, vorher: dict | None = None) -> dict:
    return {"id": "themen", "titel": {"de": "Themen"}, "aktiv": True,
            "ausloeser": [{"art": "knopf"}], "voraussetzungen": ["anmeldung"],
            "schritte": [
                vorher or {"id": "laden", "typ": "modul", "modul": "ui_upload", "daten": {}},
                auftrag or _auftrag(zustimmung="upload"),
                {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
                {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Metadaten."}}]}


def _ablauf(**kw) -> AblaufArea:
    return AblaufArea.model_validate(_roh(**kw))


def test_zustimmung_vorgabe_ist_nicht_gesetzt_und_aendert_keine_fassung():
    """Vorgabe ``freigabe`` = nicht gesetzt (``None``) — sonst änderte das Feld die Fassung jedes
    Ablaufs, und jeder wartende Lauf bräche beim Deploy ab (``treiber.fassung``)."""
    ohne = _ablauf(auftrag=_auftrag())
    mit_freigabe = _ablauf(auftrag=_auftrag(zustimmung="freigabe"))
    leer = _ablauf(auftrag=_auftrag(zustimmung=""))
    assert ohne.schritte[1].zustimmung is None
    assert mit_freigabe.schritte[1].zustimmung is None and leer.schritte[1].zustimmung is None
    assert treiber.fassung(ohne) == treiber.fassung(mit_freigabe)
    assert _ablauf().schritte[1].zustimmung == "upload"


def test_zustimmung_nimmt_nur_bekannte_werte():
    with pytest.raises(ValidationError):
        _ablauf(auftrag=_auftrag(zustimmung="ja"))


# ── Teil ``ablage``: Aufrufer und „neu“ ──────────────────────────────────────────────────────

def test_ablage_merkt_den_aufrufer_nur_als_marke(person):
    teil = _ablage()
    assert teil["aufrufer"] and PERSON not in str(teil)
    person["kennung"] = "p:jemand-anderes"
    assert _ablage()["aufrufer"] != teil["aufrufer"]
    person["kennung"] = ""                       # ohne Kennung keine Marke
    assert _ablage()["aufrufer"] == ""


def test_neu_nur_fuer_frisch_abgelegte_eintraege(person):
    # Review P3, Befund 5 (Entscheid 20.11.): ``already`` = derselbe Index unter DEMSELBEN
    # Stapel-Schlüssel schon eingelöst — der Knoten stammt von diesem Upload, also neu
    teil = _ablage(already=(1,))
    assert [e.get("neu") for e in teil["inhalte"]] == [True, True, True]
    teil = vorgang_teil.mit_ergebnis(teil, 2, {"status": "unverified", "ohne_antwort": True})
    assert teil["inhalte"][2]["neu"] is False


def test_datei_endpunkt_haelt_neu_fest(client, lage, person):  # noqa: F811
    assert _vorbereiten(client).status_code == 200
    assert lage.teil["aufrufer"]
    assert _datei(client, 0).status_code == 200
    lage.ablegen = {"status": "stored", "nodeId": "n-1", "already": True}
    assert _datei(client, 1).status_code == 200
    assert [e.get("neu") for e in lage.teil["inhalte"]] == [True, True]


# ── upload_zustimmung.gilt ───────────────────────────────────────────────────────────────────

def test_gilt_fuer_frische_knoten_dieses_uploads(person):
    assert _uz().gilt(_ablage(), BLOCK, IDS) is True
    assert _uz().gilt(_ablage(already=(0,)), BLOCK, IDS) is True     # Befund 5
    assert _uz().gilt(_ablage(), BLOCK, ["n-1"]) is True


@pytest.mark.parametrize("fall", [
    "abgemeldet", "ohne_haekchen", "haekchen_fehlt", "anderer_block", "ohne_block",
    "anderer_aufrufer", "ohne_marke", "frueher", "fremder_knoten", "leer",
    "keine_liste", "ohne_ablage", "falsches_format", "nicht_abgelegt"])
def test_gilt_nicht(person, fall):
    ablage, block, ids = _ablage(), BLOCK, list(IDS)
    if fall == "abgemeldet":
        person["auth"] = False
    elif fall == "ohne_haekchen":
        ablage = _ablage(erschliessen=False)
    elif fall == "haekchen_fehlt":
        ablage.pop("erschliessen")
    elif fall == "anderer_block":
        block = "b0000099"
    elif fall == "ohne_block":
        block = None
    elif fall == "anderer_aufrufer":
        person["kennung"] = "p:jemand-anderes"
    elif fall == "ohne_marke":
        ablage.pop("aufrufer")
    elif fall == "frueher":
        ablage["frueher"] = [{"titel": "alt", "node_id": "n-alt", "rolle": "inhalt"}]
        ids.append("n-alt")
    elif fall == "fremder_knoten":
        ids.append("n-fremd")
    elif fall == "leer":
        ids = []
    elif fall == "keine_liste":
        ids = "n-0"
    elif fall == "ohne_ablage":
        ablage = None
    elif fall == "falsches_format":
        ablage["format"] = "wlo.metadaten@1"
    elif fall == "nicht_abgelegt":
        ablage = vorgang_teil.mit_ergebnis(ablage, 0, {"status": "failed"})
    assert _uz().gilt(ablage, block, ids) is False


# ── Treiber ───────────────────────────────────────────────────────────────────────────────────

class _Starter:
    """Der Starter des MCP-Wegs (``auftrag_zug._Starter``) als Attrappe: Vorschau je Teil,
    Bestätigung mit dem Schlüssel des ersten Teils."""

    nur_ueber_wlo = False

    def __init__(self, *, job: str | None = "job-1", grund: str | None = None,
                 probleme: list | None = None, zusatz: str | None = None,
                 vorlaeufig: bool = False, ausfall: str | None = None) -> None:
        self.job, self.grund, self.probleme = job, grund, list(probleme or [])
        # Review P3, Befund 4: ``zusatz`` („args“ oder „erst“) — die Vorschau des MCP nennt einen
        # Knoten, den der Upload nicht angelegt hat
        self.zusatz, self.vorlaeufig = zusatz, vorlaeufig
        # Review P4, MAJOR 2: ``ausfall`` („abgelehnt“ oder „voruebergehend“) — die Vorschau
        # scheitert wie in ``auftrag_freigabe._ausfall`` (mit dem Grund im Starter)
        self.ausfall = ausfall
        self.gerufen: list[tuple] = []
        self._fehler: str | None = None

    async def vorlegen(self, flow: str, args: dict, aufteilen: Any) -> AuftragVorlage:
        self.gerufen.append(("vorlegen", flow, args["node_ids"]))
        if self.ausfall is not None:
            grund = "nicht_verfuegbar" if self.ausfall == "voruebergehend" else "abgewiesen"
            self._fehler = grund
            return AuftragVorlage(ausfall=self.ausfall, fehler=AuftragFehler(grund))
        erst = {**args, "node_ids": args["node_ids"][:aufteilen.hoechstens]}
        args = dict(args)
        if self.zusatz == "args":
            args["node_ids"] = [*args["node_ids"], "n-fremd"]
        elif self.zusatz == "erst":
            erst["node_ids"] = [*erst["node_ids"], "n-fremd"]
        return AuftragVorlage(args=args, erst=erst, token=TOKEN,
                              laeuft_ab=time.time() + 600,
                              eintraege=[(n, f"T{n}") for n in args["node_ids"]],
                              probleme=self.probleme)

    async def bestaetigen(self, flow: str, args: dict, token: str) -> str | None:
        self.gerufen.append(("bestaetigen", flow, args["node_ids"], token))
        self._fehler = None if self.job else self.grund
        return self.job

    async def __call__(self, flow: str, eingaben: dict) -> str | None:
        self.gerufen.append(("starten", flow))
        return "direkt-job"

    @property
    def grund_des_fehlers(self) -> str | None:
        return self._fehler

    def hinweis(self, sprache: str) -> str | None:
        return None

    def voruebergehend(self) -> bool:
        return self.vorlaeufig or self.ausfall == "voruebergehend"


class _Wahl:
    def __init__(self, starter: _Starter) -> None:
        self.starter = starter

    def fuer(self, repo_schreibt: bool) -> _Starter:
        return self.starter

    async def __call__(self, flow: str, eingaben: dict) -> str | None:
        return await self.starter(flow, eingaben)


def _umgebung_mit(ablage: dict | None, starter: _Starter) -> treiber.Umgebung:
    async def lader(name: str) -> Any:
        return ablage if name == "ablage" else None

    return treiber.Umgebung(teile=lader, auftrag_starten=_Wahl(starter))


def _wartet_am_upload(ablauf: AblaufArea, block: str = BLOCK) -> dict:
    return {"ablauf": ablauf.id, "fassung": treiber.fassung(ablauf), "schritt": "laden",
            "offener_block": block, "status": treiber.WARTET, "gewaehlt": [], "start": "s1",
            "halte": 0}


#: Die Antwort des Moduls nach „In WLO ablegen und erschließen“ (``upload-antwort.ts``): alles
#: abgelegt, nichts angehalten.
WLO_ANTWORT = {"aktion": "bereitgestellt", "ort": "wlo", "dateien": [],
               "ablage": {"layout": "ordner", "gesamt": 3, "abgelegt": 3, "unklar": 0, "fehler": 0,
                          "abgebrochen": 0, "ordner_verweigert": False, "vorgang_abgelegt": True,
                          "erschliessen": True}}


def _nach_upload(ablauf: AblaufArea, ablage: dict | None, starter: _Starter,
                 block: str = BLOCK, antwort: dict | None = None) -> treiber.Ausgabe:
    """Die Person hat im Upload-Block ``block`` abgelegt — der Lauf setzt fort."""
    aus = asyncio.run(treiber.weiter(ablauf, _wartet_am_upload(ablauf, block),
                                     WLO_ANTWORT if antwort is None else antwort,
                                     _umgebung_mit(ablage, starter)))
    assert aus is not None
    return aus


def _box(aus: treiber.Ausgabe, starter: _Starter) -> None:
    assert aus.auftrag_freigabe is not None and aus.auftrag is None
    assert aus.lauf["status"] == treiber.WARTET_FREIGABE
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


def test_upload_zustimmung_startet_ohne_box(person):
    starter = _Starter()
    aus = _nach_upload(_ablauf(), _ablage(), starter)
    assert starter.gerufen == [("vorlegen", METADATEN_FLOW, IDS),
                               ("bestaetigen", METADATEN_FLOW, IDS[:2], TOKEN)]
    assert aus.auftrag_freigabe is None
    assert aus.auftrag == {"flow": METADATEN_FLOW, "job_id": "job-1", "schritt": "metadaten"}
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert not aus.lauf.get("freigabe_id") and "freigabe_args" not in aus.lauf
    assert aus.lauf["auftrag_teile"]["n"] == 2                       # 3 Knoten, je 2 → 2 Teile
    assert "Ich lasse die Metadaten erzeugen." in aus.texte


def test_ohne_box_wie_nach_freigeben(person):
    """Derselbe Stand wie Box + „Freigeben“ (``weiter_nach_freigabe``): Status, Auftrag, Stapel,
    Texte."""
    direkt = _nach_upload(_ablauf(), _ablage(), _Starter())
    mit_box = _nach_upload(_ablauf(auftrag=_auftrag()), _ablage(), _Starter())
    ablauf = _ablauf(auftrag=_auftrag())
    nach = asyncio.run(treiber.weiter_nach_freigabe(ablauf, mit_box.lauf,
                                                    _umgebung_mit(_ablage(), _Starter()),
                                                    "job-1"))
    assert nach is not None
    assert direkt.lauf["status"] == nach.lauf["status"]
    assert direkt.lauf["auftrag_teile"] == nach.lauf["auftrag_teile"]
    assert direkt.auftrag == nach.auftrag
    assert mit_box.texte == [] and direkt.texte == nach.texte


def test_audit_zeile_ohne_kennungen(person, caplog):
    with caplog.at_level("INFO"):
        _nach_upload(_ablauf(), _ablage(), _Starter())
    assert "Zustimmung durch Upload" in caplog.text
    assert TOKEN not in caplog.text and "n-0" not in caplog.text and PERSON not in caplog.text


@pytest.mark.parametrize("fall", [
    "vorgabe_freigabe", "ohne_haekchen", "anderer_aufrufer", "abgemeldet",
    "anderer_block", "probleme"])
def test_sonst_die_freigabe_box(person, fall):
    ablauf, ablage, starter, block = _ablauf(), _ablage(), _Starter(), BLOCK
    if fall == "vorgabe_freigabe":
        ablauf = _ablauf(auftrag=_auftrag())
    elif fall == "ohne_haekchen":
        ablage = _ablage(erschliessen=False)
    elif fall == "anderer_aufrufer":
        ablage = _ablage()
        person["kennung"] = "p:jemand-anderes"
    elif fall == "abgemeldet":
        person["auth"] = False
    elif fall == "anderer_block":
        ablage = _ablage(block="b0000099")
    elif fall == "probleme":
        starter = _Starter(probleme=[("n-9", "not_writable")])
    _box(_nach_upload(ablauf, ablage, starter, block), starter)


def test_ohne_upload_in_diesem_lauf_die_box(person):
    """Ein Lauf, der den Upload-Block nie gezeigt hat (Direktstart ab dem Auftrag, Modul-Auslöser,
    neu gestartet) — eine alte Ablage im Vorgang zählt nicht."""
    ablauf, starter = _ablauf(), _Starter()
    aus = asyncio.run(treiber.starten(ablauf, _umgebung_mit(_ablage(), starter), ab=1))
    _box(aus, starter)


def test_nur_ein_upload_block_bindet_den_lauf(person):
    """Die Antwort eines anderen Moduls bindet nichts — auch nicht mit derselben Kennung."""
    vorher = {"id": "laden", "typ": "modul", "modul": "ui_strukturabgleich", "daten": {}}
    ablauf, starter = _ablauf(vorher=vorher), _Starter()
    _box(_nach_upload(ablauf, _ablage(), starter), starter)


def test_abgelaufener_schluessel_faellt_auf_die_box(person):
    starter = _Starter(job=None, grund="abgelaufen")
    aus = _nach_upload(_ablauf(), _ablage(), starter)
    assert aus.auftrag_freigabe is not None and aus.auftrag is None
    assert aus.lauf["status"] == treiber.WARTET_FREIGABE


def test_abgelehnte_bestaetigung_nimmt_den_ersatzweg_mit_satz(person):
    starter = _Starter(job=None, grund="abgewiesen")
    aus = _nach_upload(_ablauf(), _ablage(), starter)
    assert aus.auftrag is None and aus.auftrag_freigabe is None
    assert aus.lauf["status"] == "fertig" and aus.lauf["schritt"] == "ohne"
    assert aus.texte and aus.texte[-1] == "Ohne Metadaten."
    assert len(aus.texte) >= 2                       # ein Satz vor dem Ersatzweg


# ── Prüfung und Direktstart ─────────────────────────────────────────────────────────────────

def _befunde(ablauf: AblaufArea) -> list[str]:
    return pruefung.pruefe(ablauf)


def _hat(befunde: list[str], schluessel: str) -> bool:
    kopf = TEXTE[schluessel]["de"].split("{s}")[1][:25]
    return any(kopf in b for b in befunde)


def test_pruefung_upload_zustimmung_ersetzt_die_rueckfrage():
    befunde = _befunde(_ablauf())
    assert not _hat(befunde, "auftrag_rueckfrage"), befunde
    assert not _hat(befunde, "zustimmung_upload"), befunde
    # Vorgabe (Freigabe): ohne Rückfrage direkt davor bleibt der Befund
    assert _hat(_befunde(_ablauf(auftrag=_auftrag())), "auftrag_rueckfrage")


@pytest.mark.parametrize("fall", ["ohne_upload_schritt", "knoten_fest", "knoten_aus_frueher",
                                  "anderer_teil", "ohne_repo_schreibt"])
def test_pruefung_meldet_eine_unpassende_upload_zustimmung(fall):
    auftrag, vorher = _auftrag(zustimmung="upload"), None
    if fall == "ohne_upload_schritt":
        vorher = {"id": "laden", "typ": "nachricht", "text": {"de": "Los geht's."}}
    elif fall == "knoten_fest":
        auftrag["argumente"] = {"node_ids": ["n-0"], "language": "de"}
    elif fall == "knoten_aus_frueher":
        auftrag["argumente"]["node_ids"]["liste"] = "frueher"
    elif fall == "anderer_teil":
        auftrag["argumente"]["node_ids"]["$teil"] = "metadaten"
    elif fall == "ohne_repo_schreibt":
        auftrag["repo_schreibt"] = None
    befunde = _befunde(_ablauf(auftrag=auftrag, vorher=vorher))
    assert _hat(befunde, "zustimmung_upload"), befunde


def test_pruefung_zustimmung_upload_texte_de_en():
    assert set(TEXTE["zustimmung_upload"]) == {"de", "en"}
    assert "{s}" in TEXTE["zustimmung_upload"]["en"]


def test_direktstart_zaehlt_die_upload_zustimmung_als_frage():
    """Die KI darf den Ablauf direkt starten: der Flow startet erst nach dem Upload-Klick der
    Person (Lauf gebunden an den Upload-Block, siehe ``test_ohne_upload_in_diesem_lauf_die_box``)
    — oder es kommt die Box. Mit Vorgabe (Freigabe) und ohne Frage davor bleibt er gesperrt."""
    assert werkzeuge.ablauf_schreibt_ungefragt(_ablauf()) is False
    assert werkzeuge.ablauf_schreibt_ungefragt(_ablauf(auftrag=_auftrag())) is True
    # der frische Vorgang (N14) bleibt Pflicht — der Ablauf schreibt weiter „selbst“
    assert werkzeuge.ablauf_schreibt_selbst(_ablauf()) is True


def test_freier_chat_ergibt_nie_eine_zustimmung(person):
    """Im freien Chat gibt es kein Häkchen — ``ablage.erschliessen`` bleibt aus (Entscheid 20.11.).
    ``gilt`` ist dann falsch; ein danach gestarteter Lauf (Modul-Auslöser) ohne Upload-Block im
    Lauf → Box, auch wenn ``erschliessen`` wahr ist."""
    frei = _ablage(erschliessen=False)
    assert _uz().gilt(frei, BLOCK, IDS) is False
    for ablage in (frei, _ablage()):
        starter = _Starter()
        aus = asyncio.run(treiber.starten(_ablauf(), _umgebung_mit(ablage, starter), ab=1))
        _box(aus, starter)


# ── Review P3 (20.11.) ──────────────────────────────────────────────────────────────────────────

ANDERER_FLOW = "edusharing.chatbot/anderer-schreibender-flow"


def test_befund1_nur_der_metadaten_flow_startet_ohne_box(person):
    """Befund 1 (MAJOR): ``zustimmung: upload`` gilt nur für den Metadaten-Flow — jeder andere
    schreibende Flow bekommt die Box."""
    starter = _Starter()
    _box(_nach_upload(_ablauf(auftrag=_auftrag(zustimmung="upload", flow=ANDERER_FLOW)),
                      _ablage(), starter), starter)


def test_befund1_pruefung_meldet_einen_anderen_flow():
    befunde = _befunde(_ablauf(auftrag=_auftrag(zustimmung="upload", flow=ANDERER_FLOW)))
    assert _hat(befunde, "zustimmung_upload"), befunde
    assert "Metadaten-Flow" in TEXTE["zustimmung_upload"]["de"]
    assert "metadata flow" in TEXTE["zustimmung_upload"]["en"]


def _am_auftrag(ablauf: AblaufArea, lauf: dict, ablage: dict, starter: _Starter
                ) -> treiber.Ausgabe:
    """Der Lauf erreicht den Auftrag (noch einmal) — etwa über eine Schleife oder Rückkante."""
    i = next(n for n, s in enumerate(ablauf.schritte) if s.typ == "auftrag")
    return asyncio.run(treiber._rechne(ablauf, {**lauf, "status": "laeuft"}, i,
                                       _umgebung_mit(ablage, starter)))


def test_befund2_der_upload_block_gilt_nur_einmal(person):
    """Befund 2: nach dem Start ohne Box ist der Upload-Block verbraucht — ein zweiter Besuch des
    Auftrags (Schleife, Rückkante, zweiter Auftrag) bekommt die Box."""
    uz = _uz()
    ablauf = _ablauf()
    erst = _nach_upload(ablauf, _ablage(), _Starter())
    assert erst.auftrag is not None and uz.BLOCK not in erst.lauf
    starter = _Starter()
    _box(_am_auftrag(ablauf, erst.lauf, _ablage(), starter), starter)


def _ablauf_mit_frage() -> AblaufArea:
    """Upload, dann eine Rückfrage, deren Wahl zum Auftrag führt."""
    roh = _roh()
    roh["schritte"].insert(1, {"id": "frage", "typ": "nachricht", "text": {"de": "Erzeugen?"},
                               "optionen": [{"id": "ja", "label": {"de": "Ja, erzeugen"},
                                             "ziel": "metadaten"}]})
    return AblaufArea.model_validate(roh)


@pytest.mark.parametrize("mit_frage", [True, False])
def test_befund4_voruebergehend_wie_nach_der_box(person, mit_frage):
    """Befund 4: ist der Träger beim Start ohne Box nur gerade nicht verfügbar, geht es wie nach
    „Freigeben“ weiter — zurück an die Frage davor (der Upload-Block bleibt für den neuen Versuch),
    sonst ``bei_fehler``."""
    uz = _uz()
    ablauf = _ablauf_mit_frage() if mit_frage else _ablauf()
    lauf = {**_wartet_am_upload(ablauf), uz.BLOCK: BLOCK}
    starter = _Starter(job=None, grund="nicht_verfuegbar", vorlaeufig=True)
    direkt = _am_auftrag(ablauf, lauf, _ablage(), starter)
    assert [g[0] for g in starter.gerufen] == ["vorlegen", "bestaetigen"]
    # derselbe Ausgang wie Box + „Freigeben“ mit vorübergehendem Fehler
    box_ablauf = AblaufArea.model_validate({**ablauf.model_dump(mode="json", exclude_none=True)})
    mit_box = _am_auftrag(box_ablauf, {**lauf, uz.BLOCK: None}, _ablage(erschliessen=False),
                          _Starter())
    assert mit_box.auftrag_freigabe is not None
    nach = asyncio.run(treiber.weiter_nach_freigabe(
        box_ablauf, mit_box.lauf, _umgebung_mit(_ablage(), _Starter()), None, zurueck=True))
    assert nach is not None and direkt.auftrag is None and direkt.auftrag_freigabe is None
    assert (direkt.lauf["schritt"], direkt.lauf["status"]) == (nach.lauf["schritt"],
                                                               nach.lauf["status"])
    if mit_frage:
        assert direkt.lauf["schritt"] == "frage" and direkt.lauf[uz.BLOCK] == BLOCK
    else:
        assert direkt.lauf["schritt"] == "ohne"


@pytest.mark.parametrize("wo", ["args", "erst"])
def test_befund4_fremder_knoten_in_der_vorschau_gibt_die_box(person, wo):
    starter = _Starter(zusatz=wo)
    _box(_nach_upload(_ablauf(), _ablage(), starter), starter)


@pytest.mark.parametrize("fall", ["angehalten", "chat", "namen", "leer"])
def test_befund3_nur_eine_fertige_wlo_ablage_bindet_den_lauf(person, fall):
    """Befund 3: „Anhalten“ (``abgebrochen > 0``) oder eine Antwort „Hier im Chat“ / „nur Namen“
    im selben Block nach einer teilweisen Ablage bindet den Lauf nicht an den Block → Box."""
    uz = _uz()
    antwort: dict[str, Any] = {"aktion": "bereitgestellt", "ort": fall, "dateien": []}
    if fall == "angehalten":
        antwort = {**WLO_ANTWORT, "ablage": {**WLO_ANTWORT["ablage"], "abgelegt": 2,
                                             "abgebrochen": 1}}
    elif fall == "leer":
        antwort = {}
    starter = _Starter()
    aus = _nach_upload(_ablauf(), _ablage(), starter, antwort=antwort)
    _box(aus, starter)
    assert not aus.lauf.get(uz.BLOCK)


def test_befund3_eine_alte_bindung_faellt_mit_einer_anderen_antwort(person):
    """Antwortet die Person im selben Lauf noch einmal am Upload — diesmal ohne WLO —, gilt die
    frühere Bindung nicht weiter."""
    uz = _uz()
    ablauf, starter = _ablauf(), _Starter()
    lauf = {**_wartet_am_upload(ablauf), uz.BLOCK: BLOCK}
    aus = asyncio.run(treiber.weiter(ablauf, lauf, {"aktion": "bereitgestellt", "ort": "chat",
                                                    "dateien": []},
                                     _umgebung_mit(_ablage(), starter)))
    assert aus is not None
    _box(aus, starter)


def test_befund3_alte_antwort_uebertragen_bindet(person):
    """Die ältere Antwortform ``aktion: uebertragen`` (offene Verläufe) ist auch eine Ablage in
    WLO."""
    antwort = {"aktion": "uebertragen", "ablage": WLO_ANTWORT["ablage"]}
    aus = _nach_upload(_ablauf(), _ablage(), _Starter(), antwort=antwort)
    assert aus.auftrag is not None and aus.auftrag_freigabe is None


def test_befund6_eine_im_zug_geschriebene_ablage_zaehlt_nicht(person):
    """Befund 6: liest der Auftrag den GESPEICHERTEN Teil ``ablage`` — ein Schritt, der im selben
    Zug ``ablage`` schreibt (hier ein Werkzeug), fälscht keine Zustimmung."""
    roh = _roh()
    roh["schritte"].insert(1, {"id": "faelschen", "typ": "werkzeug", "werkzeug": "bereitgestellt",
                               "schreibt": "ablage"})
    ablauf, starter = AblaufArea.model_validate(roh), _Starter()

    async def ersatz(_s: str, _w: str, _a: dict) -> Any:
        return _ablage()

    async def lader(name: str) -> Any:
        return _ablage(erschliessen=False) if name == "ablage" else None

    umgebung = treiber.Umgebung(teile=lader, auftrag_starten=_Wahl(starter), ersatz=ersatz)
    aus = asyncio.run(treiber.weiter(ablauf, _wartet_am_upload(ablauf), WLO_ANTWORT, umgebung))
    assert aus is not None
    _box(aus, starter)


@pytest.mark.parametrize("schritt", [
    {"id": "x", "typ": "werkzeug", "werkzeug": "bereitgestellt", "schreibt": "ablage"},
    {"id": "x", "typ": "agent",
     "agent": {"werkzeuge": ["ui_strukturentwurf"], "ausgabe": "ablage"}},
    {"id": "x", "typ": "nachricht", "text": {"de": "Was noch?"},
     "freitext": {"ziel": "metadaten", "schreibt": "ablage"}},
])
def test_befund6_pruefung_ablage_schreibt_nur_der_server(schritt):
    roh = _roh()
    roh["schritte"].insert(1, schritt)
    befunde = _befunde(AblaufArea.model_validate(roh))
    assert _hat(befunde, "ablage_reserviert"), befunde


def test_befund6_der_upload_schritt_darf_ablage_hinterlassen():
    assert not _hat(_befunde(_ablauf()), "ablage_reserviert")


def test_koordinator_offene_frage_merkt_ob_der_block_ein_haekchen_zeigt():
    """Die offene Frage von ``ui_upload`` merkt, ob der Schritt ``erschliessen`` ausdrücklich
    setzt (nur dann zeigt der Block das Häkchen) — ``/vorbereiten`` liest es dort."""
    from boerdi.ui_module import upload_antwort

    assert upload_antwort.merken("b1", "ui_upload", {"zweck": "x", "erschliessen": False}
                                 )["haekchen"] is True
    assert upload_antwort.merken("b1", "ui_upload", {"zweck": "x"})["haekchen"] is False


# ── Zweites Review P3 (20.11.) ────────────────────────────────────────────────────────────────

def test_r2_1_nach_der_box_bleibt_die_box_der_einzige_weg(person):
    """MINOR 1: fällt der Auftrag auf die Box zurück (hier: die Vorschau meldet Probleme), ist der
    Upload-Block gelöst — „Vorschau erneut zeigen“ startet danach nicht ohne Box, auch wenn die
    Probleme weg sind."""
    uz = _uz()
    ablauf = _ablauf()
    starter = _Starter(probleme=[{"nodeId": "n-0", "grund": "gesperrt"}])
    erst = _nach_upload(ablauf, _ablage(), starter)
    _box(erst, starter)
    assert uz.BLOCK not in erst.lauf
    sauber = _Starter()
    nochmal = asyncio.run(treiber.erneut_vorlegen(ablauf, erst.lauf,
                                                 _umgebung_mit(_ablage(), sauber)))
    assert nochmal is not None
    _box(nochmal, sauber)


def test_r2_3_der_lauf_vermerkt_die_zustimmung_durch_den_upload(person):
    """NIT 3: für spätere Prüfung steht am Lauf (im Vorgang), dass der Auftrag ohne Box startete —
    nach „Freigeben“ an der Box nicht."""
    uz = _uz()
    ohne_box = _nach_upload(_ablauf(), _ablage(), _Starter())
    assert ohne_box.lauf[uz.ZUSTIMMUNG] == uz.UPLOAD
    ablauf = _ablauf(auftrag=_auftrag())
    mit_box = _nach_upload(ablauf, _ablage(), _Starter())
    nach = asyncio.run(treiber.weiter_nach_freigabe(
        ablauf, {**mit_box.lauf, uz.ZUSTIMMUNG: uz.UPLOAD}, _umgebung_mit(_ablage(), _Starter()),
        "job-1"))
    assert nach is not None and nach.auftrag is not None
    assert uz.ZUSTIMMUNG not in nach.lauf


def test_r2_4_die_knotenliste_heisst_an_einer_stelle():
    """NIT 4: der Name der Knotenliste (``node_ids``) steht einmal, in ``auftrag_teile``."""
    import inspect

    from boerdi.services.ablauf import auftrag_freigabe, auftrag_teile

    assert auftrag_teile.KNOTEN_LISTE == "node_ids"
    for modul in (_uz(), pruefung, auftrag_freigabe):
        assert '"node_ids"' not in inspect.getsource(modul), modul.__name__
    assert inspect.getsource(auftrag_teile).count('"node_ids"') == 1
