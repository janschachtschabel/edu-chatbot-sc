"""Paket U2-c (Plan 2026-11-04, T-4/T-9): ``ui_strukturentwurf`` als Werkzeug und sein Aufruf.

Die KI sieht nur den Auftrag (``dienst.parameter``); der Aufruf läuft wie eine Datenquelle
asynchron (``werkzeuge.ist_asynchron`` → ``ui_module/aufruf``) und liefert Block, Quittung und
``ToolOutcome``. Ein Fehler geht als Text an die KI, ohne Block. Keine echten LLM-Aufrufe.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.ui_module import aufruf, katalog, werkzeuge
from boerdi.ui_module.namen import STRUKTURENTWURF, THEMENBAUM


def _umgebung(**mehr: Any) -> aufruf.Umgebung:
    return aufruf.Umgebung(**mehr)


@pytest.fixture
def erzeugt(monkeypatch):
    """Der Dienst als Attrappe: gibt fest vorgegebene Daten zurück und merkt sich den Auftrag."""
    gesehen: dict[str, Any] = {}
    antwort: dict[str, Any] = {"wert": dienst.Erzeugt({
        "titel": "Optik", "quelle": "ki", "thema": "Optik",
        "knoten": [{"id": "k1", "titel": "Licht", "kinder": [{"id": "k1-1", "titel": "Quellen"}]},
                   {"id": "k2", "titel": "Farben", "ausstehend": True}]})}

    async def attrappe(auftrag, *, llm, frist_ende, vorlage=None, dokument=None, moderieren=None):
        gesehen.update(auftrag=auftrag, frist_ende=frist_ende, vorlage=vorlage, llm=llm,
                       dokument=dokument, moderieren=moderieren)
        return antwort["wert"]

    monkeypatch.setattr(dienst, "erzeugen", attrappe)
    return gesehen, antwort


def test_das_werkzeug_nennt_nur_den_auftrag():
    w = werkzeuge.werkzeug_aus_manifest(katalog.katalog()[STRUKTURENTWURF])["function"]
    assert w["name"] == STRUKTURENTWURF
    assert w["parameters"]["required"] == ["thema"]
    assert "knoten" not in w["parameters"]["properties"]
    assert "NEUE Gliederung" in w["description"] and "ui_themenbaum" in w["description"]


def test_angeboten_ohne_mcp_werkzeug_und_asynchron():
    namen = [w["function"]["name"] for w in werkzeuge.modul_werkzeuge(
        [STRUKTURENTWURF, THEMENBAUM], verfuegbar=[], fuer="agent")]
    assert namen == [STRUKTURENTWURF]           # der Baum braucht sein MCP-Werkzeug
    assert werkzeuge.ist_asynchron(STRUKTURENTWURF) and werkzeuge.ist_asynchron(THEMENBAUM)
    assert not werkzeuge.ist_asynchron("ui_entscheidung")
    assert werkzeuge.ist_abfragendes_modul(STRUKTURENTWURF)


async def test_ein_aufruf_ergibt_einen_offenen_block_und_eine_kurze_quittung(erzeugt):
    gesehen, _ = erzeugt
    zaehler: dict[str, Any] = {}
    ende = asyncio.get_running_loop().time() + 60
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "tiefe": 3, "fach": "Physik"},
                                 _umgebung(usage_acc=zaehler, frist_ende=ende))
    b = erg.block
    assert b is not None and b.modul == STRUKTURENTWURF and b.art == "abfragen"
    assert b.status == "offen" and b.text.startswith("**Entwurf (KI): Optik**")
    assert "Licht; Farben" in erg.text and "Quellen" not in erg.text
    assert erg.outcome.status == "success" and erg.outcome.item_count == 3
    a = gesehen["auftrag"]
    assert (a.thema, a.tiefe, a.fach, a.anzahl_oben) == ("Optik", 3, "Physik", 10)
    # Reserve für den Begleitsatz: der Dienst endet vor dem Lauf.
    assert gesehen["frist_ende"] == pytest.approx(ende - aufruf.RESERVE_S)


async def test_ohne_lauffrist_gilt_die_gesamtfrist_des_dienstes(erzeugt):
    gesehen, _ = erzeugt
    jetzt = asyncio.get_running_loop().time()
    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"}, _umgebung())
    assert gesehen["frist_ende"] == pytest.approx(jetzt + dienst.GESAMT_FRIST_S, abs=1)


@pytest.mark.parametrize("args", [{}, {"thema": "x"}, {"thema": "Optik", "tiefe": 4},
                                  {"thema": "Optik", "anzahl_oben": 30}, "kaputt"])
async def test_ein_falscher_auftrag_geht_als_fehler_an_die_ki(erzeugt, args):
    erg = await aufruf.asynchron(STRUKTURENTWURF, args, _umgebung())
    assert erg.block is None and erg.text.startswith("Fehler:")
    assert erg.outcome.status == "error" and erg.outcome.error == "argumente"
    assert "auftrag" not in erzeugt[0]


async def test_vorlage_ohne_mitgeschickten_entwurf_ist_ein_fehler(erzeugt):
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True}, _umgebung())
    assert erg.block is None and "mitgeschickt" in erg.text


async def test_vorlage_und_vertiefen_gehen_an_den_dienst(erzeugt):
    gesehen, _ = erzeugt
    vorlage = {"titel": "Optik", "quelle": "ki", "knoten": [{"id": "k1", "titel": "Licht"}],
               "uebernommen": False, "bearbeitet": True}
    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True,
                                             "vertiefen": ["Licht"]}, _umgebung(vorlage=vorlage))
    assert gesehen["vorlage"] is vorlage and gesehen["auftrag"].vertiefen == ("Licht",)


@pytest.mark.parametrize("grund,wort", [("ausgelastet", "ausgelastet"), ("frist", "Zeit"),
                                        ("fehler", "nicht erzeugen"), ("leer", "nicht erzeugen")])
async def test_scheitert_der_dienst_bekommt_die_ki_einen_ehrlichen_satz(erzeugt, grund, wort):
    erzeugt[1]["wert"] = dienst.Erzeugt(None, grund)
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"}, _umgebung())
    assert erg.block is None and wort in erg.text
    assert erg.outcome.error == grund


async def test_daten_ausserhalb_des_vertrags_ergeben_keinen_block(erzeugt):
    erzeugt[1]["wert"] = dienst.Erzeugt({"titel": "Optik", "quelle": "ki", "knoten": [
        {"id": "k1", "titel": "A"}, {"id": "k1", "titel": "B"}]})        # Kennung doppelt
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"}, _umgebung())
    assert erg.block is None and erg.outcome.error == "abweichung"


async def test_der_baum_laeuft_weiter_ueber_die_datenquelle(monkeypatch):
    from boerdi.ui_module import datenquelle

    gerufen: list[Any] = []

    async def attrappe(name, args, *, titel=None):
        gerufen.append((name, args))
        return datenquelle.Ergebnis(None, "x", None)

    monkeypatch.setattr(datenquelle, "aufruf", attrappe)
    await aufruf.asynchron(THEMENBAUM, {"subject": "Physik"}, _umgebung())
    assert gerufen == [(THEMENBAUM, {"subject": "Physik"})]



# ── Review U2 (Backend) ───────────────────────────────────────────────────


async def test_review_5_vertiefen_ohne_vorlage_und_nichts_zu_vertiefen(erzeugt):
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vertiefen": ["Licht"]},
                                 _umgebung())
    assert erg.block is None and "vorlage" in erg.text and "auftrag" not in erzeugt[0]
    erzeugt[1]["wert"] = dienst.Erzeugt(None, "nichts_zu_vertiefen")
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True},
                                 _umgebung(vorlage={"titel": "O", "quelle": "ki", "knoten": []}))
    assert erg.block is None and "Titel" in erg.text and erg.outcome.error == "nichts_zu_vertiefen"


# ── Drittes Review U2 ─────────────────────────────────────────────────────


async def test_drittes_review_7_ein_thema_nur_aus_leerzeichen_ist_kein_auftrag(erzeugt):
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "    "}, _umgebung())
    assert erg.block is None and erg.outcome.error == "argumente" and "auftrag" not in erzeugt[0]


def test_drittes_review_5_alle_bildungsstufen_stehen_in_der_beschreibung():
    from boerdi.ui_module import strukturentwurf as se

    beschreibung = katalog.katalog()[STRUKTURENTWURF]["dienst"]["parameter"]["properties"][
        "bildungsstufe"]["description"]
    assert all(stufe in beschreibung for stufe in se.BILDUNGSSTUFEN)


# ── Paket U3-2b: aus_dokument — das Dokument der Sitzung, serverseitig gelesen ──

async def test_aus_dokument_laedt_das_dokument_und_gibt_es_dem_dienst(erzeugt):
    gesehen, _ = erzeugt
    stand = object()
    gerufen: list[int] = []

    async def lader():
        gerufen.append(1)
        return stand

    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Lehrplan Physik", "aus_dokument": True},
                           _umgebung(dokument=lader))
    assert gesehen["dokument"] is stand and gerufen == [1]


async def test_ohne_aus_dokument_wird_nichts_geladen(erzeugt):
    gesehen, _ = erzeugt

    async def lader():
        raise AssertionError("nur mit aus_dokument")

    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"}, _umgebung(dokument=lader))
    assert gesehen["dokument"] is None


@pytest.mark.parametrize("lader", [None, "leer"])
async def test_ohne_dokument_ein_ehrlicher_satz_statt_eines_entwurfs(erzeugt, lader):
    gesehen, _ = erzeugt

    async def leer():
        return None

    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Lehrplan", "aus_dokument": True},
                                 _umgebung(dokument=leer if lader else None))
    assert erg.block is None and "kein Dokument" in erg.text
    assert erg.outcome.error == "kein_dokument" and "auftrag" not in gesehen


async def test_aus_dokument_und_vorlage_schliessen_sich_aus(erzeugt):
    gesehen, _ = erzeugt
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "aus_dokument": True,
                                                   "vorlage": True},
                                 _umgebung(vorlage={"titel": "x"}))
    assert erg.block is None and erg.outcome.error == "argumente" and "auftrag" not in gesehen


# ── Paket V1: Vorlage aus dem Vorgang ──

async def test_vorlage_ohne_mitgeschickten_entwurf_kommt_aus_dem_vorgang(erzeugt):
    gesehen, _ = erzeugt
    entwurf = {"titel": "Optik", "quelle": "ki", "knoten": [{"id": "k1", "titel": "Licht"}]}
    gefragt: list[str] = []

    async def teile(name):
        gefragt.append(name)
        return entwurf

    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True},
                           _umgebung(teile=teile))
    assert gesehen["vorlage"] is entwurf and gefragt == ["draft"]


async def test_ein_mitgeschickter_entwurf_geht_dem_vorgang_vor(erzeugt):
    gesehen, _ = erzeugt
    mitgeschickt = {"titel": "Neu", "quelle": "ki", "knoten": [{"id": "k1", "titel": "A"}]}

    async def teile(name):
        raise AssertionError("nicht nötig")

    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True},
                           _umgebung(vorlage=mitgeschickt, teile=teile))
    assert gesehen["vorlage"] is mitgeschickt


async def test_querschnitt_mit_dokument_geht_die_moderation_mit(erzeugt):
    """Querschnitts-Review 2026-11-06: die Abschnittstexte für Ebene 2 gehen erst geprüft hin —
    mit Dokument reicht der Aufruf die Moderation an den Dienst, ohne Dokument nicht (Nachprüfung
    Q4, Befund 2: das prüfte der Test vorher nicht)."""
    gesehen, _ = erzeugt
    from boerdi.services.safety.moderation import moderate

    async def lader():
        return object()

    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Lehrplan Physik", "aus_dokument": True},
                           _umgebung(dokument=lader))
    pruefen = gesehen["moderieren"]
    # Review Q4, Befund 1: unter eigener Stufe gezählt, nicht im Alarm der Chat-Züge.
    assert pruefen.func is moderate and pruefen.keywords == {"stufe": "strukturentwurf_auszug"}
    await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik"}, _umgebung(dokument=lader))
    assert gesehen["moderieren"] is None
