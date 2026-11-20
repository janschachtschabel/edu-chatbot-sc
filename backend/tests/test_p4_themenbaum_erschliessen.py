"""Plan 2026-11-20, P4 (UO-3, UO-6): der Seed „Themenbaum erstellen“ ohne Rückfrage.

- Die Rückfrage ``metadaten_frage`` entfällt. Nach einer WLO-Ablage dieses Blocks entscheidet
  ``erschliessen_weg`` nach dem Häkchen (``ablage.erschliessen``): an → ``metadaten`` (Auftrag mit
  ``zustimmung: upload`` — der Klick „In WLO ablegen und erschließen“ ist die Zustimmung), aus →
  ``lesen``.
- Auch der Dokument-Weg (Lehrplan) geht über WLO in den Flow (UO-6, hebt E3 auf); hier im Chat
  gelesen bleibt er wie bisher (→ ``wofuer``). Nach dem Lesen führt er zu den Fragen und zum
  Entwurf aus dem Dokument, nie zu den Dateinamen.
- Vorhandene Inhalte (nicht frisch von diesem Upload) bekommen weiter die Freigabe-Box.
"""

from __future__ import annotations

import asyncio
import pathlib
from typing import Any

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.services.ablage import vorgang_teil
from boerdi.services.ablauf import pruefung, simulation, treiber
from tests.test_p3_upload_zustimmung import (  # noqa: F401  (Fixture ``person``)
    BLOCK,
    IDS,
    TOKEN,
    WLO_ANTWORT,
    _ablage,
    _Starter,
    _Wahl,
    person,
)

_SEED = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe" / "themenbaum.yaml"
DOKUMENT = "Ein Dokument mit Gliederung, etwa ein Lehrplan"
DATEIEN = "Meine Dateien"
#: Die Upload-Schritte, an denen die Person WLO wählen kann (``dokument_chat`` nur den Chat).
_MIT_WLO = ("dokument_laden", "ordner_laden", "dateien_laden")
_UPLOADS = (*_MIT_WLO, "dokument_chat")
#: Die Antworten des Moduls nach „Nur hier im Chat lesen“ bzw. „Nur die Dateinamen senden“.
CHAT_ANTWORT = {"aktion": "bereitgestellt", "ort": "chat", "dateien": []}
NAMEN_ANTWORT = {"aktion": "bereitgestellt", "ort": "namen", "dateien": []}


def _themenbaum() -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(_SEED.read_text(encoding="utf-8")))


def _schritt(ablauf: AblaufArea, sid: str) -> Any:
    return next(s for s in ablauf.schritte if s.id == sid)


# ── Seed: Wege und Schritt-Daten ──────────────────────────────────────────────────────────────

def test_keine_rueckfrage_mehr_das_haekchen_entscheidet():
    ablauf = _themenbaum()
    ids = [s.id for s in ablauf.schritte]
    assert "metadaten_frage" not in ids
    assert len(ids) <= pruefung.MAX_SCHRITTE
    weg = _schritt(ablauf, "erschliessen_weg")
    assert weg.typ == "verzweigung"
    erste, sonst = weg.weiter
    assert erste.wenn_wert.quelle == "teil.ablage.erschliessen" and erste.dann == "metadaten"
    assert sonst.sonst is not None and sonst.dann is None and sonst.sonst == "lesen"


def test_der_auftrag_traegt_die_zustimmung_durch_den_upload():
    ablauf = _themenbaum()
    i = [s.id for s in ablauf.schritte].index("metadaten")
    assert ablauf.schritte[i].zustimmung == "upload"
    assert pruefung.upload_zustimmung_passt(ablauf, i)


def test_alle_wlo_ablagen_fuehren_zum_haekchen():
    """``ordner_geladen``, ``dateien_weg`` und ``dokument_gelesen``: eine Ablage dieses Blocks
    führt zu ``erschliessen_weg`` — beim Dokument als erste Regel. Review P4, MAJOR 1: nicht die
    ``block_id`` der Ablage (die schreibt schon ``/vorbereiten`` für die Vorschau), sondern die
    Marke ``abgelegt_block``, die der Server erst mit der ersten abgelegten Datei setzt."""
    ablauf = _themenbaum()
    for sid in ("ordner_geladen", "dateien_weg", "dokument_gelesen"):
        quellen = {r.wenn_wert.quelle: r.dann for r in _schritt(ablauf, sid).weiter
                   if r.wenn_wert is not None and r.wenn_wert.quelle.startswith("teil.ablage.")}
        assert quellen == {"teil.ablage.abgelegt_block": "erschliessen_weg"}, sid
    erste = _schritt(ablauf, "dokument_gelesen").weiter[0]
    assert erste.wenn_wert.wert == "{teil.struktur.block_id}"


def test_upload_schritte_setzen_rolle_vorauswahl_und_haekchen():
    ablauf = _themenbaum()
    daten = {sid: _schritt(ablauf, sid).daten for sid in _UPLOADS}
    assert daten["dokument_laden"] == {"zweck": "bereitstellen", "rolle_vorgabe": "gliederung",
                                       "vorauswahl": "auto", "erschliessen": True}
    assert daten["dokument_chat"] == {"zweck": "bereitstellen", "rolle_vorgabe": "gliederung",
                                      "vorauswahl": "auto", "orte": ["chat"]}
    for sid in ("ordner_laden", "dateien_laden"):
        assert daten[sid] == {"zweck": "bereitstellen", "rolle_vorgabe": "material",
                              "vorauswahl": "auto", "erschliessen": True}, sid
    assert "einzeldatei_als_struktur" not in _SEED.read_text(encoding="utf-8")


def test_texte_nennen_nur_knoepfe_und_orte_die_es_gibt():
    ablauf = _themenbaum()
    alt_de = ("„Hochladen“", "„Hier im Chat“", "„Nur Namen senden“")
    alt_en = ("“Upload”", "“Here in the chat”", "“Send names only”")
    for sid in _UPLOADS:
        text = _schritt(ablauf, sid).text
        assert not any(a in text["de"] for a in alt_de), sid
        assert not any(a in text["en"] for a in alt_en), sid
    for sid in _MIT_WLO:
        text = _schritt(ablauf, sid).text
        assert "„In WLO ablegen und erschließen“" in text["de"], sid
        assert "„Nur hier im Chat lesen“" in text["de"], sid
        assert "“Store and index in WLO”" in text["en"], sid
        assert "“Only read here in the chat”" in text["en"], sid
    chat = _schritt(ablauf, "dokument_chat").text
    assert "„Hier lesen“" in chat["de"] and "“Read here”" in chat["en"]


def test_texte_nennen_haekchen_und_anmeldung_gleich():
    """Review P4, NIT 5: wo WLO wählbar ist, nennen die Texte das Häkchen (es entscheidet über die
    Erschließung) und gleich „(nur angemeldet)“; der Auftrag sagt nicht „deine Dateien“, wenn es
    ein Dokument ist."""
    ablauf = _themenbaum()
    for sid in _MIT_WLO:
        text = _schritt(ablauf, sid).text
        assert "„Metadaten von WLO erzeugen lassen“" in text["de"], sid
        assert "“Let WLO create metadata”" in text["en"], sid
        assert "„In WLO ablegen und erschließen“ (nur angemeldet)" in text["de"], sid
        assert "“Store and index in WLO” (signed in only)" in text["en"], sid
    auftrag = _schritt(ablauf, "metadaten").text
    assert "deine Dateien" not in auftrag["de"] and "your files" not in auftrag["en"]


def test_der_auftrag_sagt_warten_oder_spaeter_weitermachen():
    text = _schritt(_themenbaum(), "metadaten").text
    assert "„Meine Vorgänge“" in text["de"] and "warten" in text["de"]
    assert "“My tasks”" in text["en"] and "wait" in text["en"]


def test_der_seed_besteht_die_pruefung():
    assert pruefung.pruefe(_themenbaum()) == []


# ── Treiber: nach dem Upload-Klick ────────────────────────────────────────────────────────────

def _lauf_am(ablauf: AblaufArea, schritt: str) -> dict:
    return {"ablauf": ablauf.id, "fassung": treiber.fassung(ablauf), "schritt": schritt,
            "offener_block": BLOCK, "status": treiber.WARTET, "gewaehlt": [], "start": "s1",
            "halte": 5}


def _umgebung(teile: dict[str, Any], starter: _Starter,
              lesen: dict[str, Any] | None = None) -> tuple[treiber.Umgebung, list[str]]:
    """Teile des Vorgangs, der Starter des MCP-Wegs und ``metadaten_lesen`` als Attrappe (``lesen``
    liefert den Teil, ``None`` = gescheitert); die übrigen Werkzeuge liefern nichts."""
    gerufen: list[str] = []

    async def lader(name: str) -> Any:
        return teile.get(name)

    async def ersatz(schritt: str, name: str, _args: dict[str, Any]) -> Any:
        gerufen.append(name)
        return lesen if name == "metadaten_lesen" else None

    return treiber.Umgebung(teile=lader, auftrag_starten=_Wahl(starter), ersatz=ersatz), gerufen


def _vorgang(grundlage: str, ablage: dict | None) -> dict[str, Any]:
    teile: dict[str, Any] = {
        "grundlage": grundlage,
        "struktur": {"block_id": BLOCK, "zahlen": {"ordner": 1, "dateien": 3, "inhalte": 3},
                     "struktur": {"name": "Auswahl", "kinder": []}}}
    if ablage is not None:
        teile["ablage"] = ablage
    return teile


def _gelesen() -> dict[str, Any]:
    """Wie ``metadaten_lesen``: die ``block_id`` der Ablage reist mit."""
    return {"format": "wlo.metadaten@1", "block_id": BLOCK, "titel": "Metadaten zu 0 Inhalten",
            "fehlend": [], "inhalte": [{"node_id": "n-0", "i": 0, "rolle": "struktur",
                                        "titel": "Rahmenlehrplan"}]}


def _weiter(ablauf: AblaufArea, schritt: str, teile: dict[str, Any], starter: _Starter,
            lesen: dict[str, Any] | None = None) -> tuple[treiber.Ausgabe, list[str]]:
    umgebung, gerufen = _umgebung(teile, starter, lesen)
    aus = asyncio.run(treiber.weiter(ablauf, _lauf_am(ablauf, schritt), WLO_ANTWORT, umgebung))
    assert aus is not None
    return aus, gerufen


@pytest.mark.usefixtures("person")
def test_dokument_in_wlo_mit_haekchen_startet_den_flow_ohne_box():
    ablauf, starter = _themenbaum(), _Starter()
    aus, gerufen = _weiter(ablauf, "dokument_laden", _vorgang(DOKUMENT, _ablage()), starter)
    assert aus.auftrag_freigabe is None and aus.wahl is None
    assert aus.auftrag == {"flow": METADATEN_FLOW, "job_id": "job-1", "schritt": "metadaten"}
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert [g[0] for g in starter.gerufen] == ["vorlegen", "bestaetigen"]
    assert starter.gerufen[1][3] == TOKEN and set(starter.gerufen[0][2]) == set(IDS)
    assert gerufen == []


@pytest.mark.usefixtures("person")
def test_dokument_in_wlo_ohne_haekchen_liest_nur_und_fragt_dann():
    ablauf, starter = _themenbaum(), _Starter()
    aus, gerufen = _weiter(ablauf, "dokument_laden",
                           _vorgang(DOKUMENT, _ablage(erschliessen=False)), starter, _gelesen())
    assert starter.gerufen == [] and aus.auftrag is None and aus.auftrag_freigabe is None
    assert gerufen == ["metadaten_lesen"]
    assert aus.lauf["schritt"] == "wofuer" and aus.lauf["status"] == treiber.WARTET_WAHL


@pytest.mark.usefixtures("person")
def test_dokument_ohne_angaben_aus_wlo_geht_zu_den_fragen_nicht_zu_den_dateinamen():
    """Liest WLO nichts (``ohne_metadaten`` → „Ohne Angaben aus WLO weiter“), bleibt der
    Dokument-Weg beim Dokument — nicht ``aus_dateien`` (die Dateinamen)."""
    ablauf, starter = _themenbaum(), _Starter()
    teile = _vorgang(DOKUMENT, _ablage(erschliessen=False))
    aus, gerufen = _weiter(ablauf, "dokument_laden", teile, starter, lesen=None)
    assert aus.lauf["schritt"] == "ohne_metadaten"
    umgebung, gerufen = _umgebung(teile, starter)
    nach = asyncio.run(treiber.weiter_wahl(ablauf, aus.lauf, "ohne", None, umgebung))
    assert nach is not None and gerufen == []
    assert nach.lauf["schritt"] == "wofuer" and nach.lauf["status"] == treiber.WARTET_WAHL


@pytest.mark.usefixtures("person")
def test_dokument_hier_im_chat_bleibt_ohne_flow():
    ablauf, starter = _themenbaum(), _Starter()
    teile = {**_vorgang(DOKUMENT, None),
             "strukturdokument": {"dokumente": [{"name": "Rahmenlehrplan.pdf",
                                                 "quelle": "chatbot"}]}}
    aus, gerufen = _weiter(ablauf, "dokument_laden", teile, starter)
    assert starter.gerufen == [] and gerufen == []
    assert aus.lauf["schritt"] == "wofuer"


@pytest.mark.usefixtures("person")
def test_dateien_in_wlo_mit_haekchen_ohne_rueckfrage_und_ohne_box():
    ablauf, starter = _themenbaum(), _Starter()
    aus, _ = _weiter(ablauf, "dateien_laden", _vorgang(DATEIEN, _ablage()), starter)
    assert aus.wahl is None and aus.auftrag_freigabe is None
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG
    assert aus.auftrag is not None and aus.auftrag["schritt"] == "metadaten"


@pytest.mark.usefixtures("person")
def test_vorhandene_inhalte_bekommen_die_freigabe_box():
    """Ein Knoten, den nicht genau dieser Upload neu anlegte (Eintrag ohne ``neu: true``, etwa aus
    einem älteren Stand), ist keine Zustimmung — die Box kommt wie bisher."""
    ablauf, starter = _themenbaum(), _Starter()
    ablage = _ablage()
    ablage["inhalte"][1]["neu"] = False
    aus, _ = _weiter(ablauf, "dateien_laden", _vorgang(DATEIEN, ablage), starter)
    assert aus.auftrag_freigabe is not None and aus.auftrag is None
    assert aus.lauf["status"] == treiber.WARTET_FREIGABE
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


# ── P4-Nachtrag (Entscheid Nutzer 20.11.): „Erschließung nochmal versuchen“ an ``ohne_metadaten``

def test_ohne_metadaten_bietet_die_erschliessung_nochmal_an():
    s = _schritt(_themenbaum(), "ohne_metadaten")
    nochmal = next(o for o in s.optionen if o.id == "erschliessen")
    assert nochmal.ziel == "metadaten" and not nochmal.synonyme
    # Review P4, MINOR 3: „nochmal“ stimmte nicht, wenn nie erschlossen wurde (Häkchen aus,
    # ``lesen`` gescheitert) oder die Erschließung schon lief
    assert nochmal.label == {"de": "Von WLO erschließen lassen (dieselben Dateien)",
                             "en": "Have WLO index the same files"}


def _wahl(ablauf: AblaufArea, lauf: dict, teile: dict[str, Any], starter: _Starter,
          lesen: dict[str, Any] | None = None) -> treiber.Ausgabe:
    umgebung, _ = _umgebung(teile, starter, lesen)
    aus = asyncio.run(treiber.weiter_wahl(ablauf, lauf, "erschliessen", None, umgebung))
    assert aus is not None
    return aus


@pytest.mark.usefixtures("person")
def test_nach_einem_voruebergehenden_ausfall_startet_der_zweite_versuch_ohne_box():
    """Der Träger ist nur gerade nicht verfügbar — zurück an die Frage, die zum Auftrag führt
    (``ohne_metadaten``); der Upload-Block bleibt gebunden. „Erschließung nochmal versuchen“
    startet dieselben Dateien dann ohne Box: die Zustimmung durch den Upload ist noch nicht
    verbraucht."""
    from boerdi.services.ablauf import upload_zustimmung

    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile,
                      _Starter(job=None, grund="nicht_verfuegbar", vorlaeufig=True))
    assert erst.auftrag is None and erst.auftrag_freigabe is None
    assert erst.lauf["schritt"] == "ohne_metadaten"
    assert erst.lauf["status"] == treiber.WARTET_WAHL
    assert erst.lauf[upload_zustimmung.BLOCK] == BLOCK
    starter = _Starter()
    nochmal = _wahl(ablauf, erst.lauf, teile, starter)
    assert nochmal.auftrag_freigabe is None
    assert nochmal.auftrag == {"flow": METADATEN_FLOW, "job_id": "job-1", "schritt": "metadaten"}
    assert [g[0] for g in starter.gerufen] == ["vorlegen", "bestaetigen"]
    assert upload_zustimmung.BLOCK not in nochmal.lauf


@pytest.mark.usefixtures("person")
def test_nach_einem_endgueltigen_fehlschlag_fragt_der_zweite_versuch_die_box():
    """Zweites Review P3, MINOR 1: lehnt der Träger endgültig ab (``bei_fehler``), ist die Bindung
    gelöst — der zweite Versuch geht über die Freigabe-Box."""
    from boerdi.services.ablauf import upload_zustimmung

    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile, _Starter(job=None, grund="abgelehnt"))
    assert erst.lauf["schritt"] == "ohne_metadaten"
    assert upload_zustimmung.BLOCK not in erst.lauf
    starter = _Starter()
    nochmal = _wahl(ablauf, erst.lauf, teile, starter)
    assert nochmal.auftrag is None and nochmal.auftrag_freigabe is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


@pytest.mark.usefixtures("person")
def test_nach_einem_gelungenen_start_bekommt_ein_zweiter_versuch_die_box():
    """Der Flow lief schon (der Upload-Block ist verbraucht); scheitert danach das Lesen, führt
    „Erschließung nochmal versuchen“ zur Freigabe-Box — fail closed."""
    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile, _Starter())
    assert erst.auftrag is not None
    lauf = {**erst.lauf, "schritt": "ohne_metadaten", "status": treiber.WARTET_WAHL}
    starter = _Starter()
    nochmal = _wahl(ablauf, lauf, teile, starter)
    assert nochmal.auftrag is None and nochmal.auftrag_freigabe is not None
    assert nochmal.lauf["status"] == treiber.WARTET_FREIGABE
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


@pytest.mark.usefixtures("person")
def test_ohne_haekchen_startet_der_knopf_keinen_flow_ohne_box():
    """Ohne Häkchen kam der Lauf über ``lesen`` an ``ohne_metadaten`` — die Person hat keine
    Erschließung gewählt. Der Knopf startet dann nichts von selbst: die Freigabe-Box fragt."""
    ablauf, starter = _themenbaum(), _Starter()
    teile = _vorgang(DOKUMENT, _ablage(erschliessen=False))
    erst, gerufen = _weiter(ablauf, "dokument_laden", teile, starter, lesen=None)
    assert erst.lauf["schritt"] == "ohne_metadaten" and starter.gerufen == []
    nochmal = _wahl(ablauf, erst.lauf, teile, starter)
    assert nochmal.auftrag is None and nochmal.auftrag_freigabe is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


# ── Selbsttests im Seed ───────────────────────────────────────────────────────────────────────

def test_selbsttests_decken_den_dokument_weg_ueber_wlo():
    ablauf = _themenbaum()
    wege = {t.name: t.erwartet.weg or [] for t in ablauf.tests}
    ueber_wlo = [w for w in wege.values() if "dokument_gelesen" in w and "erschliessen_weg" in w]
    assert any("metadaten" in w and w[-2:] == ["entwurf_dokument", "ende"] for w in ueber_wlo)
    assert any("metadaten" not in w and "lesen" in w and w[-2:] == ["entwurf_dokument", "ende"]
               for w in ueber_wlo)
    ergebnisse = asyncio.run(simulation.alle(ablauf))
    assert [(e.name, e.abweichungen) for e in ergebnisse if not e.ok] == []


@pytest.mark.usefixtures("person")
def test_nach_abbrechen_an_der_box_fragt_der_zweite_versuch_wieder():
    """Zweites Review P3, MINOR 1: kam die Box (hier: Probleme in der Vorschau) und bricht die
    Person ab, führt „Erschließung nochmal versuchen“ wieder zur Box — die Box ist dann der einzige
    Weg zur Zustimmung."""
    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile,
                      _Starter(probleme=[{"nodeId": "n-0", "grund": "gesperrt"}]))
    assert erst.auftrag_freigabe is not None
    umgebung, _ = _umgebung(teile, _Starter())
    ab = asyncio.run(treiber.weiter_nach_freigabe(ablauf, erst.lauf, umgebung, None))
    assert ab is not None and ab.lauf["schritt"] == "ohne_metadaten"
    starter = _Starter()
    nochmal = _wahl(ablauf, ab.lauf, teile, starter)
    assert nochmal.auftrag is None and nochmal.auftrag_freigabe is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


# ── Review P4 (20.11.), MAJOR 1: Vorschau geöffnet, abgebrochen, dann hier im Chat ─────────────

def _nur_vorschau(erschliessen: bool = True) -> dict:
    """Der Teil ``ablage`` nach ``/vorbereiten`` (Vorschau gezeigt), ohne abgelegte Datei — so
    steht er im Vorgang, wenn die Person in der Vorschau abbricht."""
    plan = {"folderName": "Physik", "layout": "folder",
            "entries": [{"index": i, "title": f"T{i}", "ext": "pdf", "size": 5,
                         "fileName": f"t{i}.pdf"} for i in range(3)]}
    return vorgang_teil.aus_plan(plan, "batch-token-0123456789", BLOCK, erschliessen=erschliessen)


def _gelesen_hier(block: str = BLOCK) -> dict[str, Any]:
    """Wie „Nur hier im Chat lesen“: Angaben zu dieser Auswahl (``quelle: chatbot``)."""
    return {"format": "wlo.metadaten@1", "quelle": "chatbot", "block_id": block,
            "titel": "Inhalte aus 3 Dateien", "fehlend": [],
            "inhalte": [{"i": 0, "rolle": "inhalt", "titel": "Linsen", "lesbar": True}]}


def _nach_antwort(ablauf: AblaufArea, schritt: str, teile: dict[str, Any],
                  antwort: dict[str, Any]) -> tuple[treiber.Ausgabe, _Starter, list[str]]:
    starter = _Starter()
    umgebung, gerufen = _umgebung(teile, starter)
    aus = asyncio.run(treiber.weiter(ablauf, _lauf_am(ablauf, schritt), antwort, umgebung))
    assert aus is not None
    return aus, starter, gerufen


@pytest.mark.usefixtures("person")
def test_dokument_vorschau_abgebrochen_dann_hier_im_chat_geht_zu_den_fragen():
    ablauf = _themenbaum()
    teile = {**_vorgang(DOKUMENT, _nur_vorschau()),
             "strukturdokument": {"dokumente": [{"name": "Rahmenlehrplan.pdf",
                                                 "quelle": "chatbot"}]}}
    aus, starter, gerufen = _nach_antwort(ablauf, "dokument_laden", teile, CHAT_ANTWORT)
    assert starter.gerufen == [] and gerufen == []
    assert aus.lauf["schritt"] == "wofuer" and aus.auftrag is None


@pytest.mark.usefixtures("person")
def test_ordner_vorschau_abgebrochen_dann_hier_im_chat_geht_zu_den_fragen():
    ablauf = _themenbaum()
    teile = {**_vorgang("Meine Ordner", _nur_vorschau()), "metadaten": _gelesen_hier()}
    aus, starter, gerufen = _nach_antwort(ablauf, "ordner_laden", teile, CHAT_ANTWORT)
    assert starter.gerufen == [] and gerufen == []
    assert aus.lauf["schritt"] == "wofuer" and aus.auftrag is None


@pytest.mark.usefixtures("person")
def test_dateien_vorschau_abgebrochen_dann_nur_namen_nimmt_die_dateinamen():
    ablauf = _themenbaum()
    teile = _vorgang(DATEIEN, _nur_vorschau())
    aus, starter, gerufen = _nach_antwort(ablauf, "dateien_laden", teile, NAMEN_ANTWORT)
    assert starter.gerufen == [] and aus.auftrag is None and aus.auftrag_freigabe is None
    assert gerufen == ["inhalte_aus_dateien"]


@pytest.mark.usefixtures("person")
def test_dateien_vorschau_abgebrochen_dann_hier_im_chat_geht_zu_den_fragen():
    ablauf = _themenbaum()
    teile = {**_vorgang(DATEIEN, _nur_vorschau()), "metadaten": _gelesen_hier()}
    aus, starter, gerufen = _nach_antwort(ablauf, "dateien_laden", teile, CHAT_ANTWORT)
    assert starter.gerufen == [] and gerufen == []
    assert aus.lauf["schritt"] == "wofuer"


# ── Review P4 (20.11.), MAJOR 2: ein endgültiges Ergebnis löst die Bindung an den Upload ───────

@pytest.mark.usefixtures("person")
def test_vorschau_endgueltig_abgelehnt_der_zweite_versuch_fragt_die_box():
    """Der MCP lehnt die Vorschau endgültig ab (``ausfall: abgelehnt``) — die Bindung an den
    Upload ist gelöst; „Von WLO erschließen lassen“ geht dann über die Freigabe-Box."""
    from boerdi.services.ablauf import upload_zustimmung

    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile, _Starter(ausfall="abgelehnt"))
    assert erst.lauf["schritt"] == "ohne_metadaten"
    assert upload_zustimmung.BLOCK not in erst.lauf
    starter = _Starter()
    nochmal = _wahl(ablauf, erst.lauf, teile, starter)
    assert nochmal.auftrag is None and nochmal.auftrag_freigabe is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]


@pytest.mark.usefixtures("person")
def test_vorschau_voruebergehend_aus_der_zweite_versuch_startet_ohne_box():
    from boerdi.services.ablauf import upload_zustimmung

    ablauf = _themenbaum()
    teile = _vorgang(DOKUMENT, _ablage())
    erst, _ = _weiter(ablauf, "dokument_laden", teile, _Starter(ausfall="voruebergehend"))
    assert erst.lauf["schritt"] == "ohne_metadaten"
    assert erst.lauf[upload_zustimmung.BLOCK] == BLOCK
    starter = _Starter()
    nochmal = _wahl(ablauf, erst.lauf, teile, starter)
    assert nochmal.auftrag_freigabe is None and nochmal.auftrag is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen", "bestaetigen"]


# ── Zweites Review P4–P6, MINOR 1: abgelegt, dann „Andere Auswahl“ und eine Antwort ohne WLO ──

@pytest.mark.usefixtures("person")
def test_abgelegt_dann_andere_auswahl_hier_im_chat_geht_zu_den_fragen_ohne_box():
    """Im selben Block lagen schon Dateien in WLO (Marke ``abgelegt_block``), dann „Andere
    Auswahl“ und „Nur hier im Chat lesen“: der Lauf nimmt den Chat-Weg (``wofuer``), keinen Flow
    und keine Box — und der Teil ``ablage`` verliert die Marke (nur sie)."""
    ablauf = _themenbaum()
    ablage = _ablage()
    assert ablage[vorgang_teil.ABGELEGT] == BLOCK
    teile = {**_vorgang(DOKUMENT, ablage),
             "strukturdokument": {"dokumente": [{"name": "Rahmenlehrplan.pdf",
                                                 "quelle": "chatbot"}]}}
    aus, starter, gerufen = _nach_antwort(ablauf, "dokument_laden", teile, CHAT_ANTWORT)
    assert starter.gerufen == [] and gerufen == []
    assert aus.lauf["schritt"] == "wofuer"
    assert aus.auftrag is None and aus.auftrag_freigabe is None
    neu = {n: w for n, _t, w, _z in aus.neue_teile}
    assert vorgang_teil.ABGELEGT not in neu["ablage"]
    assert {k: v for k, v in ablage.items() if k != vorgang_teil.ABGELEGT} == neu["ablage"]


@pytest.mark.usefixtures("person")
def test_abgelegt_dann_andere_auswahl_nur_namen_nimmt_die_dateinamen():
    ablauf = _themenbaum()
    aus, starter, gerufen = _nach_antwort(ablauf, "dateien_laden", _vorgang(DATEIEN, _ablage()),
                                          NAMEN_ANTWORT)
    assert starter.gerufen == [] and aus.auftrag is None and aus.auftrag_freigabe is None
    assert gerufen == ["inhalte_aus_dateien"]


@pytest.mark.usefixtures("person")
def test_eine_angehaltene_wlo_ablage_behaelt_die_marke():
    """„Anhalten“ und „Im Chat weitermachen“ ist eine WLO-Antwort (``abgebrochen`` > 0): sie bindet
    den Lauf nicht (Box), nimmt aber den WLO-Weg — die Marke bleibt."""
    ablauf = _themenbaum()
    antwort = {**WLO_ANTWORT, "ablage": {**WLO_ANTWORT["ablage"], "abgelegt": 2, "abgebrochen": 1}}
    aus, starter, _ = _nach_antwort(ablauf, "dateien_laden", _vorgang(DATEIEN, _ablage()), antwort)
    assert "ablage" not in {n for n, *_ in aus.neue_teile}
    assert aus.auftrag_freigabe is not None
    assert [g[0] for g in starter.gerufen] == ["vorlegen"]
