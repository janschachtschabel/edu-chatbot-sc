"""Plan 2026-11-19, N2: Fach und Bildungsstufe aus dem WLO-Vokabular.

Die Kurzangaben bekommen die Labels von ``discipline`` und ``educationalContext`` als geschlossene
Liste in den Prompt; jedes Ergebnis wird danach auf das Vokabular abgebildet (genau, ohne Groß-
und Kleinschreibung, über Aliase wie der Filter-Resolver) — kein Treffer → leer. Dieselbe
Abbildung gilt in der Vorbelegung aus den Metadaten der Strukturdokumente. Ohne Vokabular bleibt
es wie bisher. Das Vokabular ist eine Attrappe: der Text, den ``lookup_wlo_vocabulary`` liefert,
geht durch den echten Leser in ``arg_resolvers``."""

from __future__ import annotations

import asyncio
import logging

import pytest

from boerdi.domain.config_models.ablauf import Schritt
from boerdi.services.ablauf import vorbelegung as vb
from boerdi.services.dokumente import inhalt_angaben as ia
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp import vokabular_labels as vl
from tests.helfer_vokabular import ECHT as _ECHT
from tests.helfer_vokabular import leeren, mit_vokabular

_TEXTE = {
    "discipline": (
        "- **Geografie** | Aliases: Erdkunde, Geographie\n"
        "  URI: http://w3id.org/openeduhub/vocabs/discipline/220\n"
        "- **Mathematik** | Aliases: Mathe\n"
        "  URI: http://w3id.org/openeduhub/vocabs/discipline/380\n"
        "- **Physik**\n"
        "  URI: http://w3id.org/openeduhub/vocabs/discipline/460\n"),
    "educationalContext": (
        "- **Sekundarstufe I** | Aliases: Sek I, Mittelstufe\n"
        "  URI: http://w3id.org/openeduhub/vocabs/educationalContext/sekundarstufe_1\n"
        "- **Primarstufe** | Aliases: Grundschule\n"
        "  URI: http://w3id.org/openeduhub/vocabs/educationalContext/grundschule\n"),
}


@pytest.fixture
def vokabular(monkeypatch):
    """Das Vokabular über die echte Naht, mit der Attrappe des MCP-Servers dahinter."""
    gefragt = mit_vokabular(monkeypatch, _TEXTE)
    yield gefragt
    leeren()


def _run(coro):
    return asyncio.run(coro)


# ── Abbildung ────────────────────────────────────────────────────────────────

def test_erdkunde_und_geografie_ergeben_dasselbe_label(vokabular):
    assert _run(vl.fach("Erdkunde")) == _run(vl.fach("Geografie")) == "Geografie"
    assert _run(vl.fach("  erdkunde ")) == "Geografie"


def test_ein_unsinnswert_wird_leer(vokabular):
    assert _run(vl.fach("Quatschfach 123")) is None
    assert _run(vl.stufe("irgendwas")) is None
    assert _run(vl.fach(None)) is None


def test_stufe_ueber_alias_und_synonym(vokabular):
    assert _run(vl.stufe("Mittelstufe")) == "Sekundarstufe I"
    assert _run(vl.stufe("Grundschule")) == "Primarstufe"
    # „Oberstufe“ kennt der Entwurf als Sekundarstufe II — die führt dieses Vokabular nicht
    assert _run(vl.stufe("Oberstufe")) is None


def test_die_labels_als_liste(vokabular):
    assert _run(vl.labels("discipline")) == ["Geografie", "Mathematik", "Physik"]
    assert _run(vl.labels("educationalContext")) == ["Primarstufe", "Sekundarstufe I"]


def test_ohne_vokabular_wie_bisher():
    """``conftest``: kein Vokabular — die Prüfer des Entwurfs gelten unverändert."""
    assert _run(vl.labels("discipline")) is None
    assert _run(vl.fach("Erdkunde")) == "Erdkunde"
    assert _run(vl.stufe("Sek I")) == "Sekundarstufe I"


def test_ein_leeres_vokabular_gilt_als_keines(monkeypatch):
    async def mcp(name, args):
        return "MCP error: nicht erreichbar"

    leeren()
    monkeypatch.setattr(mcp_client, "call_mcp_tool", mcp)
    monkeypatch.setattr(vl, "_vokabular", _ECHT)
    try:
        assert _run(vl.labels("discipline")) is None
        assert _run(vl.fach("Erdkunde")) == "Erdkunde"
    finally:
        leeren()


def test_ein_fehlschlag_wird_kurz_gemerkt(monkeypatch):
    """Nicht jede Inhaltsdatei soll erneut auf einen toten MCP warten: nach einem Fehlschlag
    fragt ``vokabular_labels`` erst nach :data:`SPERRE_S` wieder."""
    versuche: list[str] = []
    uhr = [1000.0]

    async def mcp(name, args):
        versuche.append(args["vocabulary"])
        return "MCP error: nicht erreichbar"

    leeren()
    monkeypatch.setattr(mcp_client, "call_mcp_tool", mcp)
    monkeypatch.setattr(vl, "_vokabular", _ECHT)
    monkeypatch.setattr(vl, "_jetzt", lambda: uhr[0])
    try:
        assert _run(vl.fach("Erdkunde")) == "Erdkunde"
        assert _run(vl.fach("Physik")) == "Physik"
        assert versuche == ["discipline"]
        uhr[0] += vl.SPERRE_S + 1
        _run(vl.fach("Erdkunde"))
        assert versuche == ["discipline", "discipline"]
    finally:
        leeren()


# ── Kurzangaben ──────────────────────────────────────────────────────────────

def _attrappe(antwort: dict, merk: list):
    async def rufe(nachrichten):
        merk.append(nachrichten)
        return antwort
    return rufe


def test_kurzangaben_bekommen_die_geschlossene_liste_und_werden_abgebildet(vokabular):
    merk: list = []
    roh = {"titel": "Karten lesen", "fach": "Erdkunde", "stufe": "Mittelstufe"}
    erg = _run(ia.ermitteln("Text", "karten.pdf", llm=_attrappe(roh, merk)))
    assert erg["fach"] == "Geografie" and erg["stufe"] == "Sekundarstufe I"
    system = merk[0][0]["content"]
    assert "Geografie; Mathematik; Physik" in system
    assert "Primarstufe; Sekundarstufe I" in system
    # die Liste steht in der Anweisung, nicht im Daten-Rahmen der Datei
    assert "Geografie" not in merk[0][-1]["content"]


def test_kurzangaben_ohne_treffer_bleiben_leer(vokabular):
    roh = {"titel": "T", "fach": "Astrologie", "stufe": "Sekundarstufe II"}
    erg = _run(ia.ermitteln("Text", "a.pdf", llm=_attrappe(roh, [])))
    assert "fach" not in erg and "stufe" not in erg


def test_kurzangaben_ohne_vokabular_wie_bisher_mit_hinweis(caplog):
    merk: list = []
    roh = {"titel": "T", "fach": "Physik", "stufe": "Sek I"}
    with caplog.at_level(logging.INFO, logger=ia.logger.name):
        erg = _run(ia.ermitteln("Text", "a.pdf", llm=_attrappe(roh, merk)))
    assert erg["fach"] == "Physik" and erg["stufe"] == "Sekundarstufe I"
    assert "Geografie" not in merk[0][0]["content"]
    assert any("Vokabular" in r.getMessage() for r in caplog.records)


# ── Vorbelegung aus den Strukturdokumenten ───────────────────────────────────

_STRUKTUR = "22222222-2222-4222-8222-222222222222"


def _belegt(faecher: list[str], stufen: list[str]) -> dict:
    ablage = {"format": "wlo.ablage@1", "inhalte": [
        {"index": 0, "i": 0, "titel": "Plan.pdf", "stand": "stored", "node_id": _STRUKTUR,
         "rolle": "struktur"}]}
    metadaten = {"format": "wlo.metadaten@1", "inhalte": [
        {"node_id": _STRUKTUR, "rolle": "struktur", "titel": "Plan", "faecher": faecher,
         "stufen": stufen}]}
    teile = {"ablage": ablage, "metadaten": metadaten}
    schritt = Schritt.model_validate({"id": "entwurf", "typ": "agent", "agent": {
        "werkzeuge": ["ui_strukturentwurf"], "ausgabe": "draft", "vorbelegen": True}})

    async def lader(name):
        return teile.get(name)

    return _run(vb.vorbelegung(schritt, lader, ()))


def test_vorbelegung_bildet_fach_und_stufe_ab(vokabular):
    belegt = _belegt(["Quatsch", "Erdkunde"], ["Mittelstufe"])
    assert belegt["fach"] == "Geografie"
    assert belegt["bildungsstufe"] == "Sekundarstufe I"


def test_vorbelegung_ohne_treffer_belegt_nichts(vokabular):
    belegt = _belegt(["Astrologie"], ["Sekundarstufe II"])
    assert "fach" not in belegt and "bildungsstufe" not in belegt
